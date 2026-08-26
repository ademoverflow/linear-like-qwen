import { Link, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import type { Issue, IssueDetail, IssueUpdateInput } from "@/api/issues";
import type { Label, TeamMember, WorkflowState } from "@/api/teams";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { useCurrentUser } from "@/hooks/use-current-user";
import { useIssueActions } from "@/hooks/use-issue-actions";
import { useTransitionIssue } from "@/hooks/use-transition-issue";
import { useUpdateIssue } from "@/hooks/use-update-issue";
import { Markdown } from "@/lib/markdown";
import { isOwnerOrAdmin } from "@/lib/permissions";
import { PRIORITY_OPTIONS } from "@/lib/priorities";
import { IssueFeed } from "./IssueFeed";
import { LabelChip } from "./LabelChip";
import { MarkdownEditor } from "./MarkdownEditor";
import { StateDot } from "./StateDot";

const ESTIMATE_OPTIONS = [
	{ value: "", label: "No estimate" },
	...Array.from({ length: 22 }, (_, value) => ({
		value: String(value),
		label: String(value),
	})),
];

/**
 * The Issue detail panel (brief §7.2.3, ticket 03 + 04 + 06): inline-
 * editable title, Markdown description with edit/preview, the properties
 * column and the story — the Comments thread merged chronologically with
 * Activity (ticket 06). State is a picker on the same transition path as
 * the Board (ticket 04); Labels are a picker (ticket 05) that applies the
 * full set through the same optimistic edit path (ADR 0008).
 */
export function IssueDetailPanel({
	issue,
	teamKey,
	teamId,
	issues,
	members,
	states,
	labels,
}: {
	issue: IssueDetail;
	teamKey: string;
	teamId: string;
	issues: Issue[];
	members: TeamMember[];
	states: WorkflowState[];
	labels: Label[];
}) {
	const update = useUpdateIssue(teamId, issue.id);
	const transition = useTransitionIssue(teamId);
	const me = useCurrentUser();
	const dueDateId = useId();
	const navigate = useNavigate();
	const issueActions = useIssueActions();
	const [labelPickerOpen, setLabelPickerOpen] = useState(false);
	const [selectedLabelIds, setSelectedLabelIds] = useState<string[]>([]);
	const [deleteOpen, setDeleteOpen] = useState(false);
	const [confirmValue, setConfirmValue] = useState("");

	const canArchive = isOwnerOrAdmin(me.data, teamId);

	const navigateToIssues = useCallback(() => {
		navigate({ to: "/teams/$teamKey/issues", params: { teamKey } });
	}, [navigate, teamKey]);

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
					className="rounded-md px-2 py-1 text-sm text-muted hover:bg-surface-subtle"
				>
					‹ {teamKey} / Issues
				</Link>
				<span className="font-mono text-xs text-muted">{issue.identifier}</span>
				<span className="flex-1" />
				<StateDot color={issue.state_color} category={issue.state_category} />
				<span className="text-xs text-muted">{issue.state_name}</span>
				{canArchive && (
					<Button
						variant="ghost"
						onClick={() =>
							issueActions.archive.mutate(issue.id, {
								onSuccess: () => navigateToIssues(),
							})
						}
					>
						Archive
					</Button>
				)}
				{me?.data?.is_admin === true && (
					<Button variant="ghost" onClick={() => setDeleteOpen(true)}>
						Delete
					</Button>
				)}
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
					<span className="text-sm font-medium text-foreground">Labels</span>
					<button
						type="button"
						aria-label="Change labels"
						onClick={() => {
							setSelectedLabelIds(issue.labels.map((label) => label.id));
							setLabelPickerOpen(true);
						}}
						className="flex h-9 items-center gap-1.5 rounded-md border border-neutral-300 bg-surface px-2 text-sm focus:border-accent dark:border-neutral-700"
					>
						{issue.labels.length === 0 ? (
							<span className="text-faint">No labels</span>
						) : (
							issue.labels.map((label) => (
								<LabelChip key={label.id} label={label} compact />
							))
						)}
					</button>
				</div>
				<LabelPicker
					open={labelPickerOpen}
					labels={labels}
					selectedIds={selectedLabelIds}
					onSelectedIdsChange={setSelectedLabelIds}
					onClose={() => setLabelPickerOpen(false)}
					onSave={() => {
						patch({ label_ids: selectedLabelIds });
						setLabelPickerOpen(false);
					}}
				/>
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
						className="text-sm font-medium text-foreground"
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
						className="h-9 rounded-md border border-neutral-300 bg-surface px-2 text-sm text-foreground focus:border-accent dark:border-neutral-700"
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

			<IssueFeed issueId={issue.id} teamId={teamId} me={me.data ?? null} />

			<Dialog
				open={deleteOpen}
				title="Delete this Issue?"
				onClose={() => setDeleteOpen(false)}
			>
				<p className="text-sm text-foreground">
					This permanently deletes {issue.identifier} — including its children,
					Comments and Activity. This cannot be undone.
				</p>
				<div className="mt-4">
					<Input
						label={
							<>
								Type <span className="font-mono">{issue.identifier}</span> to
								confirm
							</>
						}
						value={confirmValue}
						onChange={setConfirmValue}
					/>
				</div>
				<div className="mt-4 flex justify-end gap-2">
					<Button variant="secondary" onClick={() => setDeleteOpen(false)}>
						Cancel
					</Button>
					<Button
						disabled={
							confirmValue.trim() !== issue.identifier ||
							issueActions.hardDelete.isPending
						}
						onClick={() => {
							setDeleteOpen(false);
							issueActions.hardDelete.mutate(
								{
									issueId: issue.id,
									identifier: confirmValue.trim(),
								},
								{ onSuccess: () => navigateToIssues() },
							);
						}}
					>
						Delete {issue.identifier}
					</Button>
				</div>
			</Dialog>
		</div>
	);
}

/**
 * The Labels picker (ticket 05): a checkbox per Team Label; saving
 * applies the full set via the optimistic edit path (one Activity row
 * per added/removed label server-side).
 */
function LabelPicker({
	open,
	labels,
	selectedIds,
	onSelectedIdsChange,
	onClose,
	onSave,
}: {
	open: boolean;
	labels: Label[];
	selectedIds: string[];
	onSelectedIdsChange: (ids: string[]) => void;
	onClose: () => void;
	onSave: () => void;
}) {
	const toggle = (id: string) => {
		onSelectedIdsChange(
			selectedIds.includes(id)
				? selectedIds.filter((item) => item !== id)
				: [...selectedIds, id],
		);
	};
	return (
		<Dialog open={open} title="Labels" onClose={onClose}>
			{labels.length === 0 ? (
				<p className="text-sm text-muted">This Team has no Labels yet.</p>
			) : (
				<div className="flex flex-col gap-1.5">
					{labels.map((label) => (
						<label
							key={label.id}
							className="flex cursor-pointer items-center gap-2 text-sm text-foreground"
						>
							<input
								type="checkbox"
								name="issue label"
								value={label.id}
								checked={selectedIds.includes(label.id)}
								onChange={() => toggle(label.id)}
								className="h-4 w-4 accent-accent"
							/>
							<LabelChip label={label} />
						</label>
					))}
				</div>
			)}
			<div className="mt-4 flex justify-end gap-2">
				<Button variant="secondary" onClick={onClose}>
					Cancel
				</Button>
				<Button onClick={onSave}>Save</Button>
			</div>
		</Dialog>
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
				className="w-full rounded-md border border-neutral-300 bg-surface px-2 py-1 text-lg font-semibold focus:border-accent dark:border-neutral-700"
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
			className="w-full rounded-md px-2 py-1 text-left text-lg font-semibold hover:bg-surface-subtle"
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

	const startEditing = () => setEditing(true);

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
					<p className="text-sm text-muted">No description.</p>
				)}
			</section>
		);
	}

	return (
		<section aria-label="Edit description">
			<MarkdownEditor
				initial={description ?? ""}
				ariaLabel="Description"
				rows={10}
				maxLength={50_000}
				onSave={(draft) => {
					setEditing(false);
					if (draft !== description) onSave(draft);
				}}
				onCancel={() => setEditing(false)}
			/>
		</section>
	);
}
