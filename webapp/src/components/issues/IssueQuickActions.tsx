import type { Issue } from "@/api/issues";
import type { Label, TeamMember, WorkflowState } from "@/api/teams";
import type { QuickActionKind } from "@/hooks/use-issue-list-keyboard";
import { PRIORITY_OPTIONS, type Priority } from "@/lib/priorities";
import { SELECT_CLASS } from "@/lib/styles";

interface IssueQuickActionsProps {
	issue: Issue;
	kind: QuickActionKind;
	states: WorkflowState[];
	members: TeamMember[];
	labels: Label[];
	onStateChange: (stateId: string) => void;
	onAssigneeChange: (userId: string | null) => void;
	onPriorityChange: (priority: Priority) => void;
	onToggleLabel: (label: Label, add: boolean) => void;
}

const KIND_LABEL: Record<QuickActionKind, string> = {
	state: "Set State",
	assignee: "Set Assignee",
	priority: "Set Priority",
	labels: "Toggle Labels",
};

/**
 * Quick-edit bar for the Issue at the keyboard cursor (ticket 09, brief
 * §7.3): State/Assignee/Priority are selects, Labels are checkboxes. The
 * parent closes the bar after an action; mutations reuse the optimistic
 * hooks (brief §7.4).
 */
export function IssueQuickActions({
	issue,
	kind,
	states,
	members,
	labels,
	onStateChange,
	onAssigneeChange,
	onPriorityChange,
	onToggleLabel,
}: IssueQuickActionsProps) {
	return (
		<div className="fixed bottom-4 left-1/2 z-20 w-full max-w-md -translate-x-1/2 rounded-lg border border-line bg-surface px-4 py-3 shadow-lg">
			<div className="mb-2 flex items-center justify-between gap-3">
				<span className="truncate text-sm font-medium">
					<span className="font-mono text-xs text-muted">
						{issue.identifier}
					</span>{" "}
					— {KIND_LABEL[kind]}
				</span>
				<kbd className="shrink-0 rounded border border-neutral-300 px-1.5 py-0.5 font-mono text-xs text-faint dark:border-neutral-700">
					Esc
				</kbd>
			</div>
			{kind === "state" && (
				<select
					aria-label="Set State"
					value=""
					onChange={(event) => {
						if (event.target.value) onStateChange(event.target.value);
					}}
					className={SELECT_CLASS}
				>
					<option value="" disabled>
						Set State…
					</option>
					{states.map((state) => (
						<option key={state.id} value={state.id}>
							{state.name}
						</option>
					))}
				</select>
			)}
			{kind === "assignee" && (
				<select
					aria-label="Set Assignee"
					value=""
					onChange={(event) => {
						const value = event.target.value;
						if (value === "") return;
						onAssigneeChange(value === "unassigned" ? null : value);
					}}
					className={SELECT_CLASS}
				>
					<option value="" disabled>
						Assign to…
					</option>
					<option value="unassigned">Unassigned</option>
					{members.map((member) => (
						<option key={member.id} value={member.id}>
							{member.display_name}
						</option>
					))}
				</select>
			)}
			{kind === "priority" && (
				<select
					aria-label="Set Priority"
					value=""
					onChange={(event) => {
						if (event.target.value)
							onPriorityChange(event.target.value as Priority);
					}}
					className={SELECT_CLASS}
				>
					<option value="" disabled>
						Set Priority…
					</option>
					{PRIORITY_OPTIONS.map((option) => (
						<option key={option.value} value={option.value}>
							{option.label}
						</option>
					))}
				</select>
			)}
			{kind === "labels" && (
				<ul className="flex max-h-48 flex-col gap-1 overflow-y-auto">
					{labels.length === 0 && (
						<li className="text-sm text-muted">No Labels in this Team yet.</li>
					)}
					{labels.map((label) => {
						const attached = issue.labels.some(
							(owned) => owned.id === label.id,
						);
						return (
							<li key={label.id}>
								<label className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-sm hover:bg-surface-subtle">
									<input
										type="checkbox"
										checked={attached}
										onChange={() => onToggleLabel(label, !attached)}
										className="h-4 w-4 accent-accent"
									/>
									<span
										className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
										style={{ backgroundColor: label.color }}
										aria-hidden
									/>
									{label.name}
								</label>
							</li>
						);
					})}
				</ul>
			)}
		</div>
	);
}
