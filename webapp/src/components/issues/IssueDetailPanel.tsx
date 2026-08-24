import { Link } from "@tanstack/react-router";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import type { Issue, IssueDetail, IssueUpdateInput } from "@/api/issues";
import type { TeamMember, WorkflowState } from "@/api/teams";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { useTransitionIssue } from "@/hooks/use-transition-issue";
import { useUpdateIssue } from "@/hooks/use-update-issue";
import { Markdown } from "@/lib/markdown";
import { ActivityFeed } from "./ActivityFeed";

const PRIORITY_OPTIONS = [
	{ value: "none", label: "No priority" },
	{ value: "urgent", label: "Urgent" },
	{ value: "high", label: "High" },
	{ value: "medium", label: "Medium" },
	{ value: "low", label: "Low" },
];

const ESTIMATE_OPTIONS = [
	{ value: "", label: "No estimate" },
	...Array.from({ length: 22 }, (_, value) => ({
		value: String(value),
		label: String(value),
	})),
];

/**
 * The Issue detail panel (brief §7.2.3, ticket 03 + 04): inline-editable
 * title, Markdown description with edit/preview, the properties column and
 * Activity feed. State is a picker on the same transition path as the
 * Board (ticket 04); Labels are a placeholder until ticket 05.
 */
export function IssueDetailPanel({
	issue,
	teamKey,
	teamId,
	issues,
	members,
	states,
}: {
	issue: IssueDetail;
	teamKey: string;
	teamId: string;
	issues: Issue[];
	members: TeamMember[];
	states: WorkflowState[];
}) {
	const update = useUpdateIssue(teamId, issue.id);
	const transition = useTransitionIssue(teamId);
	const dueDateId = useId();

	const patch = useCallback(
		(fields: Omit<IssueUpdateInput, "updated_at">) => {
			update.mutate({ updated_at: issue.updated_at, ...fields });
		},
		[update, issue.updated_at],
	);

	const parentOptions = [
		{ value: "", label: "No parent" },
		...issues
			.filter((item) => item.id !== issue.id && !item.parent_id)
			.map((item) => ({
				value: item.id,
				label: `${item.identifier} — ${item.title}`,
			})),
	];

	const assigneeOptions = [
		{ value: "", label: "Unassigned" },
		...members.map((member) => ({
			value: member.id,
			label: member.display_name,
		})),
	];

	return (
		<div className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
			<div className="flex items-center gap-3">
				<Link
					to="/teams/$teamKey/issues"
					params={{ teamKey }}
					className="rounded-md px-2 py-1 text-sm text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
				>
					‹ {teamKey} / Issues
				</Link>
				<span className="font-mono text-xs text-neutral-500">
					{issue.identifier}
				</span>
				<span className="flex-1" />
				<span
					className="inline-block h-2.5 w-2.5 rounded-full"
					style={{ backgroundColor: issue.state_color }}
					aria-hidden
				/>
				<span className="text-xs text-neutral-500">{issue.state_name}</span>
			</div>

			<InlineTitle value={issue.title} onSave={(title) => patch({ title })} />

			<DescriptionEditor
				description={issue.description ?? null}
				onSave={(description) => patch({ description })}
			/>

			<section
				aria-label="Properties"
				className="grid grid-cols-2 gap-4 md:grid-cols-3"
			>
				<Select
					label="State"
					value={issue.state_id}
					onChange={(value) =>
						transition.mutate({
							issue_id: issue.id,
							state_id: value,
							updated_at: issue.updated_at,
						})
					}
					options={states.map((state) => ({
						value: state.id,
						label: state.name,
					}))}
				/>
				<div className="flex flex-col gap-1.5">
					<span className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
						Labels
					</span>
					<span className="flex h-9 items-center text-sm text-neutral-400">
						No labels yet
					</span>
				</div>
				<Select
					label="Priority"
					value={issue.priority}
					onChange={(value) => patch({ priority: value as Issue["priority"] })}
					options={PRIORITY_OPTIONS}
				/>
				<Select
					label="Assignee"
					value={issue.assignee_id ?? ""}
					onChange={(value) =>
						patch({ assignee_id: value === "" ? null : value })
					}
					options={assigneeOptions}
				/>
				<Select
					label="Parent"
					value={issue.parent_id ?? ""}
					onChange={(value) =>
						patch({ parent_id: value === "" ? null : value })
					}
					options={parentOptions}
				/>
				<div className="flex flex-col gap-1.5">
					<label
						htmlFor={dueDateId}
						className="text-sm font-medium text-neutral-700 dark:text-neutral-300"
					>
						Due date
					</label>
					<input
						id={dueDateId}
						type="date"
						value={
							issue.due_date ? issue.due_date.toISOString().slice(0, 10) : ""
						}
						onChange={(event) =>
							patch({
								due_date: event.target.value === "" ? null : event.target.value,
							})
						}
						className="h-9 rounded-md border border-neutral-300 bg-white px-2 text-sm text-neutral-900 focus:border-accent focus:outline-none dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100"
					/>
				</div>
				<Select
					label="Estimate"
					value={issue.estimate === null ? "" : String(issue.estimate)}
					onChange={(value) =>
						patch({ estimate: value === "" ? null : Number(value) })
					}
					options={ESTIMATE_OPTIONS}
				/>
			</section>

			<section aria-label="Activity" className="flex flex-col gap-3">
				<h2 className="text-sm font-semibold">Activity</h2>
				<ActivityFeed issueId={issue.id} />
			</section>
		</div>
	);
}

/** Click to edit, Enter or blur to save, Escape to cancel. */
function InlineTitle({
	value,
	onSave,
}: {
	value: string;
	onSave: (title: string) => void;
}) {
	const [editing, setEditing] = useState(false);
	const [draft, setDraft] = useState(value);
	const inputRef = useRef<HTMLInputElement | null>(null);

	useEffect(() => {
		if (editing) inputRef.current?.focus();
	}, [editing]);

	if (editing) {
		return (
			<input
				ref={inputRef}
				value={draft}
				maxLength={255}
				aria-label="Edit title"
				onChange={(event) => setDraft(event.target.value)}
				onKeyDown={(event) => {
					if (event.key === "Enter") {
						setEditing(false);
						if (draft.trim() !== value) onSave(draft);
					} else if (event.key === "Escape") {
						setDraft(value);
						setEditing(false);
					}
				}}
				onBlur={() => {
					setEditing(false);
					if (draft.trim() !== value) onSave(draft);
				}}
				className="w-full rounded-md border border-neutral-300 bg-white px-2 py-1 text-lg font-semibold focus:border-accent focus:outline-none dark:border-neutral-700 dark:bg-neutral-900"
			/>
		);
	}
	return (
		<button
			type="button"
			aria-label={`Edit title: ${value}`}
			onClick={() => {
				setDraft(value);
				setEditing(true);
			}}
			className="w-full rounded-md px-2 py-1 text-left text-lg font-semibold hover:bg-neutral-100 dark:hover:bg-neutral-800"
		>
			{value}
		</button>
	);
}

/** Markdown description with Write/Preview modes (ADR 0007). */
function DescriptionEditor({
	description,
	onSave,
}: {
	description: string | null;
	onSave: (description: string) => void;
}) {
	const [editing, setEditing] = useState(false);
	const [mode, setMode] = useState<"write" | "preview">("write");
	const [draft, setDraft] = useState(description ?? "");

	const startEditing = () => {
		setDraft(description ?? "");
		setMode("write");
		setEditing(true);
	};
	const cancel = () => setEditing(false);
	const save = () => {
		setEditing(false);
		if (draft !== description) onSave(draft);
	};

	if (!editing) {
		return (
			<section aria-label="Description">
				<div className="mb-2 flex items-center justify-between">
					<h2 className="text-sm font-semibold">Description</h2>
					<Button variant="ghost" onClick={startEditing}>
						Edit
					</Button>
				</div>
				{description ? (
					<Markdown content={description} />
				) : (
					<p className="text-sm text-neutral-500">No description.</p>
				)}
			</section>
		);
	}

	return (
		<section aria-label="Edit description">
			<div className="mb-2 flex items-center gap-1">
				<Button
					variant={mode === "write" ? "primary" : "secondary"}
					onClick={() => setMode("write")}
				>
					Write
				</Button>
				<Button
					variant={mode === "preview" ? "primary" : "secondary"}
					onClick={() => setMode("preview")}
				>
					Preview
				</Button>
			</div>
			{mode === "write" ? (
				<textarea
					value={draft}
					rows={10}
					aria-label="Description"
					onChange={(event) => setDraft(event.target.value)}
					className="w-full rounded-md border border-neutral-300 bg-white p-2 text-sm focus:border-accent focus:outline-none dark:border-neutral-700 dark:bg-neutral-900"
				/>
			) : (
				<div className="rounded-md border border-neutral-200 p-3 dark:border-neutral-800">
					{draft ? (
						<Markdown content={draft} />
					) : (
						<p className="text-sm text-neutral-500">Nothing to preview.</p>
					)}
				</div>
			)}
			<div className="mt-2 flex gap-2">
				<Button onClick={save}>Save</Button>
				<Button variant="secondary" onClick={cancel}>
					Cancel
				</Button>
			</div>
		</section>
	);
}
