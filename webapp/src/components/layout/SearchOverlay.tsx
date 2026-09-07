import { useNavigate } from "@tanstack/react-router";
import { Search, X } from "lucide-react";
import {
	type KeyboardEvent,
	useCallback,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import { createPortal } from "react-dom";
import { type SearchIssue, searchIssues } from "@/api/issues";
import { StateDot } from "@/components/issues/StateDot";
import { Skeleton } from "@/components/ui/Skeleton";

const DEBOUNCE_MS = 150;

interface SearchOverlayProps {
	open: boolean;
	onClose: () => void;
}

/**
 * Global search overlay (brief §7.2.8, ticket 09): opens on `/` or
 * Cmd/Ctrl+K (wired in AppShell), debounced query, results grouped by
 * Team, arrow keys move the selection (wrapping), Enter opens the Issue
 * and Esc closes (and clears). Deliberately stateful — no query cache:
 * a transient view, fresh on every open. Arrow/Enter/Esc are handled on
 * the input itself (the global shortcuts are suppressed while typing).
 */
export function SearchOverlay({ open, onClose }: SearchOverlayProps) {
	const navigate = useNavigate();
	const inputRef = useRef<HTMLInputElement>(null);
	const [query, setQuery] = useState("");
	const [results, setResults] = useState<SearchIssue[]>([]);
	const [searching, setSearching] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [selected, setSelected] = useState(0);

	useEffect(() => {
		if (!open) return;
		setQuery("");
		setResults([]);
		setError(null);
		setSelected(0);
		inputRef.current?.focus();
	}, [open]);

	useEffect(() => {
		if (!open || query.trim() === "") {
			setResults([]);
			setSearching(false);
			setError(null);
			return;
		}
		const controller = new AbortController();
		setSearching(true);
		const timer = setTimeout(() => {
			searchIssues(query, controller.signal)
				.then((data) => {
					if (controller.signal.aborted) return;
					setResults(data.issues);
					setSelected(0);
					setError(null);
				})
				.catch((err: unknown) => {
					if (controller.signal.aborted) return;
					setError(err instanceof Error ? err.message : "Search failed");
				})
				.finally(() => {
					if (!controller.signal.aborted) setSearching(false);
				});
		}, DEBOUNCE_MS);
		return () => {
			clearTimeout(timer);
			controller.abort();
		};
	}, [open, query]);

	const openIssue = useCallback(
		(issue: SearchIssue) => {
			onClose();
			navigate({
				to: "/teams/$teamKey/issues/$issueId",
				params: { teamKey: issue.team_key, issueId: issue.id },
			});
		},
		[navigate, onClose],
	);

	const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
		if (event.key === "ArrowDown") {
			event.preventDefault();
			if (results.length > 0)
				setSelected((index) => (index + 1) % results.length);
		} else if (event.key === "ArrowUp") {
			event.preventDefault();
			if (results.length > 0)
				setSelected((index) => (index - 1 + results.length) % results.length);
		} else if (event.key === "Enter") {
			const issue = results[selected];
			if (issue) {
				event.preventDefault();
				openIssue(issue);
			}
		} else if (event.key === "Escape") {
			event.preventDefault();
			onClose();
		}
	};

	const groups = useMemo(() => {
		const byTeam = new Map<
			string,
			{ teamName: string; items: SearchIssue[] }
		>();
		for (const issue of results) {
			const group = byTeam.get(issue.team_key) ?? {
				teamName: issue.team_name,
				items: [],
			};
			group.items.push(issue);
			byTeam.set(issue.team_key, group);
		}
		return [...byTeam.values()];
	}, [results]);

	if (!open) return null;

	return createPortal(
		// biome-ignore lint/a11y/noStaticElementInteractions: backdrop click closes the overlay; Esc is the keyboard path
		<div
			className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-[12vh]"
			onMouseDown={(event) => {
				if (event.target === event.currentTarget) onClose();
			}}
		>
			<div
				role="dialog"
				aria-modal="true"
				aria-label="Search"
				className="w-full max-w-lg overflow-hidden rounded-lg border border-line bg-surface shadow-xl"
			>
				<div className="flex items-center gap-2 border-b border-line px-3">
					<Search size={16} className="shrink-0 text-faint" aria-hidden />
					<input
						ref={inputRef}
						value={query}
						onChange={(event) => setQuery(event.target.value)}
						onKeyDown={onKeyDown}
						aria-label="Search Issues"
						placeholder="Search Issues by identifier or title ( / )"
						className="h-11 w-full bg-transparent text-sm text-foreground placeholder:text-faint"
					/>
					<button
						type="button"
						onClick={onClose}
						aria-label="Close search"
						className="rounded p-1 text-faint hover:bg-surface-subtle hover:text-foreground"
					>
						<X size={16} />
					</button>
				</div>
				<div className="max-h-[50vh] overflow-y-auto p-2">
					{query.trim() === "" ? (
						<p className="px-2 py-3 text-sm text-muted">
							Search across your Teams by identifier (e.g.{" "}
							<span className="font-mono">ENG-1</span>) or title.
						</p>
					) : searching ? (
						<div className="flex flex-col gap-2 p-2">
							<Skeleton className="h-12 w-full" />
							<Skeleton className="h-12 w-full" />
						</div>
					) : error !== null ? (
						<p className="px-2 py-3 text-sm text-red-500">{error}</p>
					) : results.length === 0 ? (
						<p className="px-2 py-3 text-sm text-muted">
							No Issues match “{query.trim()}”.
						</p>
					) : (
						groups.map((group) => (
							<section key={group.teamName} className="mb-1">
								<div className="px-2 py-1 text-[11px] font-semibold uppercase tracking-wider text-faint">
									{group.teamName}
								</div>
								{group.items.map((issue) => {
									const index = results.indexOf(issue);
									return (
										<button
											key={issue.id}
											type="button"
											aria-current={index === selected}
											onClick={() => openIssue(issue)}
											className={
												"flex w-full flex-col gap-0.5 rounded-md px-2 py-1.5 text-left " +
												(index === selected ? "bg-surface-subtle" : "")
											}
										>
											<span className="flex items-center gap-2">
												<span className="shrink-0 font-mono text-xs text-muted">
													{issue.identifier}
												</span>
												<span className="min-w-0 flex-1 truncate text-sm font-medium">
													{issue.title}
												</span>
											</span>
											<span className="flex items-center gap-1.5 pl-0.5 text-xs text-faint">
												<StateDot
													color={issue.state_color}
													category={issue.state_category}
													small
												/>
												{issue.state_name}
											</span>
										</button>
									);
								})}
							</section>
						))
					)}
				</div>
			</div>
		</div>,
		document.body,
	);
}
