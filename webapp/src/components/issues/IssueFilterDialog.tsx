import { useState } from "react";
import type { Label, TeamMember, WorkflowState } from "@/api/teams";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { PRIORITY_OPTIONS } from "@/lib/priorities";

/** The combinable list filters (brief §7.2.2: AND across, OR within). */
export interface IssueListFilters {
	stateIds: string[];
	assigneeIds: string[];
	labelIds: string[];
	priorities: string[];
}

export const EMPTY_ISSUE_FILTERS: IssueListFilters = {
	stateIds: [],
	assigneeIds: [],
	labelIds: [],
	priorities: [],
};

export const SORT_OPTIONS = [
	{ value: "created:desc", label: "Newest first" },
	{ value: "created:asc", label: "Oldest first" },
	{ value: "updated:desc", label: "Recently updated" },
	{ value: "updated:asc", label: "Least recently updated" },
	{ value: "priority:desc", label: "Priority: high to low" },
	{ value: "priority:asc", label: "Priority: low to high" },
] as const;

function toggleValue(values: string[], value: string): string[] {
	return values.includes(value)
		? values.filter((item) => item !== value)
		: [...values, value];
}

function FilterGroup({
	legend,
	options,
	selected,
	onToggle,
}: {
	legend: string;
	options: { value: string; label: string }[];
	selected: string[];
	onToggle: (value: string) => void;
}) {
	if (options.length === 0) return null;
	return (
		<fieldset className="flex flex-col gap-1.5">
			<legend className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
				{legend}
			</legend>
			{options.map((option) => (
				<label
					key={option.value}
					className="flex cursor-pointer items-center gap-2 text-sm text-neutral-600 dark:text-neutral-300"
				>
					<input
						type="checkbox"
						name={`${legend} filter`}
						value={option.value}
						checked={selected.includes(option.value)}
						onChange={() => onToggle(option.value)}
						className="h-4 w-4 accent-accent"
					/>
					{option.label}
				</label>
			))}
		</fieldset>
	);
}

/**
 * List filters (brief §7.2.2): multi-checkbox per dimension (State,
 * Assignee, Label, Priority), combinable, applied live as the user
 * checks/unchecks; "Clear" resets all dimensions.
 */
export function IssueFilterDialog({
	open,
	onClose,
	filters,
	onFiltersChange,
	states,
	members,
	labels,
}: {
	open: boolean;
	onClose: () => void;
	filters: IssueListFilters;
	onFiltersChange: (filters: IssueListFilters) => void;
	states: WorkflowState[];
	members: TeamMember[];
	labels: Label[];
}) {
	const [draft, setDraft] = useState<IssueListFilters>(filters);
	const apply = (next: IssueListFilters) => {
		setDraft(next);
		onFiltersChange(next);
	};

	return (
		<Dialog open={open} title="Filter Issues" onClose={onClose}>
			<div className="flex max-h-[60vh] flex-col gap-4 overflow-y-auto">
				<FilterGroup
					legend="State"
					options={states.map((state) => ({
						value: state.id,
						label: state.name,
					}))}
					selected={draft.stateIds}
					onToggle={(value) =>
						apply({ ...draft, stateIds: toggleValue(draft.stateIds, value) })
					}
				/>
				<FilterGroup
					legend="Assignee"
					options={members.map((member) => ({
						value: member.id,
						label: member.display_name,
					}))}
					selected={draft.assigneeIds}
					onToggle={(value) =>
						apply({
							...draft,
							assigneeIds: toggleValue(draft.assigneeIds, value),
						})
					}
				/>
				<FilterGroup
					legend="Label"
					options={labels.map((label) => ({
						value: label.id,
						label: label.name,
					}))}
					selected={draft.labelIds}
					onToggle={(value) =>
						apply({ ...draft, labelIds: toggleValue(draft.labelIds, value) })
					}
				/>
				<FilterGroup
					legend="Priority"
					options={[...PRIORITY_OPTIONS]}
					selected={draft.priorities}
					onToggle={(value) =>
						apply({
							...draft,
							priorities: toggleValue(draft.priorities, value),
						})
					}
				/>
			</div>
			<div className="mt-4 flex justify-end gap-2">
				<Button
					variant="secondary"
					onClick={() => apply({ ...EMPTY_ISSUE_FILTERS })}
				>
					Clear
				</Button>
				<Button onClick={onClose}>Done</Button>
			</div>
		</Dialog>
	);
}
