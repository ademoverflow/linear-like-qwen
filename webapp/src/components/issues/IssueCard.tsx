import { Link } from "@tanstack/react-router";
import type { Issue } from "@/api/issues";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { PriorityGlyph } from "@/lib/priorities";
import { LabelChip } from "./LabelChip";
import { StateDot } from "./StateDot";

/**
 * Issue card, prototype variant B (card stack): identifier + title + state
 * on row one, priority glyph + Label chips on row two, assignee on the
 * right. Links to the detail. In selection mode (bulk, ticket 05) a
 * checkbox is added and the card does not navigate on checkbox clicks.
 * Archived Issues (ticket 07) carry an "Archived" badge, do not navigate
 * (the detail 404s while archived) and offer a Restore action when given.
 */
export function IssueCard({
	issue,
	teamKey,
	selectable = false,
	checked = false,
	selected = false,
	onToggle,
	onRestore,
}: {
	issue: Issue;
	teamKey: string;
	selectable?: boolean;
	checked?: boolean;
	/** Keyboard-cursor highlight (ticket 09; separate from bulk selection). */
	selected?: boolean;
	onToggle?: (issueId: string) => void;
	/** Shown only for archived Issues: restore this Issue (owner/Admin). */
	onRestore?: (issueId: string) => void;
}) {
	const archived = issue.archived_at !== null;
	const body = (
		<>
			<div className="flex items-center gap-2">
				<span className="shrink-0 font-mono text-xs text-muted">
					{issue.identifier}
				</span>
				<span className="min-w-0 flex-1 truncate text-sm font-medium">
					{issue.title}
				</span>
				<StateDot color={issue.state_color} category={issue.state_category} />
				<span className="shrink-0 text-xs text-muted">{issue.state_name}</span>
			</div>
			<div className="mt-2 flex flex-wrap items-center gap-2">
				<PriorityGlyph priority={issue.priority} />
				{archived && (
					<span className="rounded-full border border-neutral-300 px-1.5 py-0.5 text-xs text-muted dark:border-neutral-700">
						Archived
					</span>
				)}
				{issue.labels.map((label) => (
					<LabelChip key={label.id} label={label} />
				))}
				<span className="flex-1" />
				<Avatar
					user={
						issue.assignee_id
							? {
									displayName: issue.assignee_display_name ?? "Unknown",
									avatarUrl: issue.assignee_avatar_url,
								}
							: null
					}
				/>
			</div>
		</>
	);
	const cardClass =
		"block min-w-0 flex-1 rounded-lg border border-line bg-surface p-3 shadow-sm hover:shadow";
	return (
		<div className="flex items-start gap-2" data-issue-id={issue.id}>
			{selectable && (
				<input
					type="checkbox"
					aria-label={`Select ${issue.identifier}`}
					checked={checked}
					onChange={() => onToggle?.(issue.id)}
					className="mt-3.5 h-4 w-4 shrink-0 accent-accent"
				/>
			)}
			{archived ? (
				<div
					className={cardClass + (selected ? " ring-2 ring-accent" : "")}
					aria-current={selected ? "true" : undefined}
				>
					{body}
				</div>
			) : (
				<Link
					to="/teams/$teamKey/issues/$issueId"
					params={{ teamKey, issueId: issue.id }}
					className={cardClass + (selected ? " ring-2 ring-accent" : "")}
					aria-current={selected ? "true" : undefined}
				>
					{body}
				</Link>
			)}
			{archived && onRestore ? (
				<Button variant="ghost" onClick={() => onRestore(issue.id)}>
					Restore
				</Button>
			) : null}
		</div>
	);
}
