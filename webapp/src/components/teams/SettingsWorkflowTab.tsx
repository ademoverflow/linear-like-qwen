import {
	DndContext,
	type DragEndEvent,
	KeyboardSensor,
	PointerSensor,
	useSensor,
	useSensors,
} from "@dnd-kit/core";
import {
	arrayMove,
	SortableContext,
	sortableKeyboardCoordinates,
	useSortable,
	verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GripVertical } from "lucide-react";
import { useEffect, useId, useMemo, useState } from "react";
import { ApiError } from "@/api/client";
import { listAllIssues } from "@/api/issues";
import { queryKeys } from "@/api/query-keys";
import {
	createTeamState,
	deleteTeamState,
	listTeamStates,
	reorderTeamStates,
	updateTeamState,
	type WorkflowState,
} from "@/api/teams";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { toast } from "@/components/ui/Toast";

const DEFAULT_COLOR = "#f2c94c";

const CATEGORIES = [
	{ value: "backlog", label: "Backlog" },
	{ value: "unstarted", label: "Unstarted" },
	{ value: "started", label: "Started" },
	{ value: "completed", label: "Completed" },
	{ value: "canceled", label: "Canceled" },
];

const NAME_INPUT_CLASS =
	"min-w-0 flex-1 rounded-md border border-neutral-300 bg-white px-2 py-1 text-sm text-neutral-900 focus:border-accent focus:outline-none dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100";

function StateRow({
	state,
	issueCount,
	teamId,
	onRequestMigrate,
}: {
	state: WorkflowState;
	issueCount: number;
	teamId: string;
	onRequestMigrate: (state: WorkflowState) => void;
}) {
	const queryClient = useQueryClient();
	const [name, setName] = useState(state.name);
	const [color, setColor] = useState(state.color);
	const [confirmDelete, setConfirmDelete] = useState(false);
	const {
		attributes,
		listeners,
		setNodeRef,
		setActivatorNodeRef,
		transform,
		transition: dndTransition,
		isDragging,
	} = useSortable({ id: state.id });

	// The query refetches after every mutation: re-sync the drafts so the
	// inputs never show a stale name/colour (ADR 0008 — no optimistic edits).
	useEffect(() => {
		setName(state.name);
	}, [state.name]);
	useEffect(() => {
		setColor(state.color);
	}, [state.color]);

	const edit = useMutation({
		mutationFn: (input: { name?: string; color?: string; category?: string }) =>
			updateTeamState(teamId, state.id, { version: state.version, ...input }),
		// Also on error: a stale 409 must refetch the States (ADR 0008).
		onSettled: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeys.teams.states(teamId),
			});
		},
		onError: (error) =>
			toast(
				error instanceof Error ? error.message : "Could not update the State",
			),
	});

	const remove = useMutation({
		mutationFn: () =>
			deleteTeamState(teamId, state.id, { version: state.version }),
		onSettled: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeys.teams.states(teamId),
			});
		},
		onError: (error) => {
			// A 400 without a target means the State still holds Issues the
			// UI does not count (archived-only): offer the migration.
			if (error instanceof ApiError && error.status === 400) {
				onRequestMigrate(state);
				return;
			}
			toast(
				error instanceof Error ? error.message : "Could not delete the State",
			);
		},
	});

	const commitName = () => {
		const trimmed = name.trim();
		if (trimmed.length > 0 && trimmed !== state.name) {
			edit.mutate({ name: trimmed });
		} else {
			setName(state.name);
		}
	};

	const handleDelete = () => {
		if (!confirmDelete) {
			setConfirmDelete(true);
			setTimeout(() => setConfirmDelete(false), 3000);
			return;
		}
		setConfirmDelete(false);
		if (issueCount > 0) {
			onRequestMigrate(state);
		} else {
			remove.mutate();
		}
	};

	const style: React.CSSProperties = {
		transform: transform
			? `translate(${transform.x}px, ${transform.y}px)`
			: undefined,
		transition: dndTransition,
	};

	return (
		<li
			ref={setNodeRef}
			style={style}
			className={
				"flex items-center gap-2 rounded-md border border-neutral-200 bg-white px-2 py-1.5 " +
				(isDragging ? "z-20 opacity-90 shadow-lg" : "")
			}
		>
			<button
				type="button"
				ref={setActivatorNodeRef}
				{...attributes}
				{...listeners}
				aria-label={`Drag ${state.name}`}
				className="-m-1 shrink-0 cursor-grab rounded p-1 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-600 focus-visible:ring-2 focus-visible:ring-accent active:cursor-grabbing dark:hover:bg-neutral-800 dark:hover:text-neutral-300"
			>
				<GripVertical size={14} aria-hidden />
			</button>
			<input
				type="color"
				aria-label={`Colour for ${state.name}`}
				value={color}
				onChange={(event) => setColor(event.target.value)}
				onBlur={() => {
					if (color !== state.color) edit.mutate({ color });
				}}
				className="h-7 w-7 shrink-0 cursor-pointer rounded border border-neutral-300 bg-white p-0.5 dark:border-neutral-700 dark:bg-neutral-900"
			/>
			<input
				type="text"
				aria-label={`Name for ${state.name}`}
				value={name}
				maxLength={50}
				onChange={(event) => setName(event.target.value)}
				onBlur={commitName}
				onKeyDown={(event) => {
					if (event.key === "Enter") event.currentTarget.blur();
				}}
				className={NAME_INPUT_CLASS}
			/>
			<select
				aria-label={`Category for ${state.name}`}
				value={state.category}
				onChange={(event) => edit.mutate({ category: event.target.value })}
				className="h-8 shrink-0 rounded-md border border-neutral-300 bg-white px-2 text-sm text-neutral-900 focus:border-accent focus:outline-none dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100"
			>
				{CATEGORIES.map((option) => (
					<option key={option.value} value={option.value}>
						{option.label}
					</option>
				))}
			</select>
			<span className="shrink-0 text-xs text-neutral-400">{issueCount}</span>
			<Button variant="ghost" onClick={handleDelete} className="shrink-0">
				{confirmDelete ? "Confirm?" : "Delete"}
			</Button>
		</li>
	);
}

/**
 * Workflow tab of the Team settings (ticket 08, brief §4.3, ADR 0006/0008):
 * a dnd-kit sortable list of the Team's Workflow States with inline
 * rename/recolor, a category Select, and a two-step delete. A State that
 * still holds Issues asks for a migration target (same category only).
 * Every edit carries the last-seen `version`; nothing is optimistic — a
 * stale 409 refetches the States and shows the server message.
 */
export function SettingsWorkflowTab({ teamId }: { teamId: string }) {
	const queryClient = useQueryClient();
	const [stateToDelete, setStateToDelete] = useState<WorkflowState | null>(
		null,
	);
	const [migrateTargetId, setMigrateTargetId] = useState("");
	const [addOpen, setAddOpen] = useState(false);
	const newColorId = useId();
	const [newName, setNewName] = useState("");
	const [newCategory, setNewCategory] = useState("unstarted");
	const [newColor, setNewColor] = useState(DEFAULT_COLOR);

	const statesQuery = useQuery({
		queryKey: queryKeys.teams.states(teamId),
		queryFn: () => listTeamStates(teamId),
	});
	const issuesQuery = useQuery({
		queryKey: queryKeys.issues.team(teamId),
		queryFn: () => listAllIssues(teamId),
	});

	const states = useMemo(
		() =>
			(statesQuery.data ?? []).slice().sort((a, b) => a.position - b.position),
		[statesQuery.data],
	);
	const issueCount = useMemo(() => {
		const counts = new Map<string, number>();
		for (const issue of issuesQuery.data ?? []) {
			counts.set(issue.state_id, (counts.get(issue.state_id) ?? 0) + 1);
		}
		return counts;
	}, [issuesQuery.data]);

	const sensors = useSensors(
		useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
		useSensor(KeyboardSensor, {
			coordinateGetter: sortableKeyboardCoordinates,
		}),
	);

	const reorder = useMutation({
		mutationFn: (ordered: { id: string; version: number }[]) =>
			reorderTeamStates(teamId, ordered),
		// Also on error: a stale 409 must refetch the States (ADR 0008).
		onSettled: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeys.teams.states(teamId),
			});
		},
		onError: (error) =>
			toast(
				error instanceof Error ? error.message : "Could not reorder the States",
			),
	});

	const handleDragEnd = (event: DragEndEvent) => {
		const { active, over } = event;
		if (!over || active.id === over.id) return;
		const from = states.findIndex((state) => state.id === active.id);
		const to = states.findIndex((state) => state.id === over.id);
		if (from === -1 || to === -1) return;
		const ordered = arrayMove(states, from, to);
		reorder.mutate(
			ordered.map((state) => ({ id: state.id, version: state.version })),
		);
	};

	const migrate = useMutation({
		mutationFn: (targetId: string) =>
			stateToDelete
				? deleteTeamState(teamId, stateToDelete.id, {
						version: stateToDelete.version,
						migrate_to_state_id: targetId,
					})
				: Promise.reject(new Error("No State to delete")),
		onSettled: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeys.teams.states(teamId),
			});
		},
		onSuccess: () => {
			setStateToDelete(null);
			setMigrateTargetId("");
			// The moved Issues changed State: keep every Issue cache fresh.
			void queryClient.invalidateQueries({ queryKey: ["issues"] });
		},
		onError: (error) =>
			toast(
				error instanceof Error ? error.message : "Could not delete the State",
			),
	});

	const create = useMutation({
		mutationFn: () =>
			createTeamState(teamId, {
				name: newName.trim(),
				category: newCategory,
				color: newColor,
			}),
		onSettled: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeys.teams.states(teamId),
			});
		},
		onSuccess: () => {
			setAddOpen(false);
			setNewName("");
			setNewCategory("unstarted");
			setNewColor(DEFAULT_COLOR);
		},
		onError: (error) =>
			toast(
				error instanceof Error ? error.message : "Could not create the State",
			),
	});

	const targets = stateToDelete
		? states.filter(
				(state) =>
					state.category === stateToDelete.category &&
					state.id !== stateToDelete.id,
			)
		: [];

	return (
		<div>
			<Button
				variant="secondary"
				className="mb-2"
				aria-expanded={addOpen}
				onClick={() => setAddOpen((open) => !open)}
			>
				{addOpen ? "Hide new State" : "New State"}
			</Button>
			<DndContext sensors={sensors} onDragEnd={handleDragEnd}>
				<SortableContext
					items={states.map((state) => state.id)}
					strategy={verticalListSortingStrategy}
				>
					<ul aria-label="Workflow States" className="flex flex-col gap-2">
						{states.map((state) => (
							<StateRow
								key={state.id}
								state={state}
								issueCount={issueCount.get(state.id) ?? 0}
								teamId={teamId}
								onRequestMigrate={setStateToDelete}
							/>
						))}
					</ul>
				</SortableContext>
			</DndContext>

			{addOpen && (
				<Dialog open title="New State" onClose={() => setAddOpen(false)}>
					<form
						className="flex flex-col gap-3"
						onSubmit={(event) => {
							event.preventDefault();
							if (newName.trim().length > 0 && !create.isPending)
								create.mutate();
						}}
					>
						<Input
							label="Name"
							value={newName}
							onChange={setNewName}
							placeholder="State name"
						/>
						<Select
							label="Category"
							value={newCategory}
							onChange={setNewCategory}
							options={CATEGORIES.map((option) => ({
								value: option.value,
								label: option.label,
							}))}
						/>
						<div className="flex flex-col gap-1.5">
							<label
								className="text-sm font-medium text-neutral-700 dark:text-neutral-300"
								htmlFor={newColorId}
							>
								Colour
							</label>
							<input
								type="color"
								id={newColorId}
								value={newColor}
								onChange={(event) => setNewColor(event.target.value)}
								className="h-9 w-9 cursor-pointer rounded-md border border-neutral-300 bg-white p-1 dark:border-neutral-700 dark:bg-neutral-900"
							/>
						</div>
						<div className="flex justify-end">
							<Button
								type="submit"
								disabled={newName.trim().length === 0 || create.isPending}
							>
								Add
							</Button>
						</div>
					</form>
				</Dialog>
			)}
			{stateToDelete && (
				<Dialog
					open
					title={`Delete ${stateToDelete.name}?`}
					onClose={() => {
						setStateToDelete(null);
						setMigrateTargetId("");
					}}
				>
					<p className="text-sm text-neutral-500">
						This State still holds {issueCount.get(stateToDelete.id) ?? 0} Issue
						{(issueCount.get(stateToDelete.id) ?? 0) === 1 ? "" : "s"}. Choose a
						State of the same category to move them to; the State is deleted in
						the same step.
					</p>
					<div className="mt-3">
						{targets.length === 0 ? (
							<p className="text-sm text-red-600 dark:text-red-400">
								No other State of this category exists — add one before
								deleting.
							</p>
						) : (
							<Select
								label="Migrate Issues to"
								value={migrateTargetId}
								onChange={setMigrateTargetId}
								options={targets.map((target) => ({
									value: target.id,
									label: target.name,
								}))}
							/>
						)}
					</div>
					<div className="mt-4 flex justify-end gap-2">
						<Button
							variant="secondary"
							onClick={() => {
								setStateToDelete(null);
								setMigrateTargetId("");
							}}
						>
							Cancel
						</Button>
						<Button
							disabled={targets.length === 0 || migrateTargetId === ""}
							onClick={() => {
								if (migrateTargetId !== "") migrate.mutate(migrateTargetId);
							}}
						>
							Migrate and delete
						</Button>
					</div>
				</Dialog>
			)}
		</div>
	);
}
