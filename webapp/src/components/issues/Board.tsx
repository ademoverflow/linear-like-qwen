import {
	closestCorners,
	DndContext,
	type DragEndEvent,
	KeyboardSensor,
	PointerSensor,
	useDroppable,
	useSensor,
	useSensors,
} from "@dnd-kit/core";
import {
	SortableContext,
	sortableKeyboardCoordinates,
	useSortable,
	verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { Link } from "@tanstack/react-router";
import { GripVertical } from "lucide-react";
import { useCallback } from "react";
import type { Issue } from "@/api/issues";
import type { WorkflowState } from "@/api/teams";
import { Avatar } from "@/components/ui/Avatar";
import { useTransitionIssue } from "@/hooks/use-transition-issue";
import { PriorityGlyph } from "@/lib/priorities";

/**
 * Resolve the target State of a drop (board DnD, ticket 04). Dropping on a
 * column targets that column's State; dropping on a card targets the State
 * of the card it lands on.
 */
export function targetStateForDrop(
	overId: string,
	issues: Issue[],
	states: WorkflowState[],
): string | null {
	const state = states.find((item) => item.id === overId);
	if (state) return state.id;
	const overIssue = issues.find((item) => item.id === overId);
	return overIssue?.state_id ?? null;
}

/**
 * Kanban Board (brief §7.2.4, ADR 0006 + ADR 0011): one column per
 * Workflow State in position order — including backlog and canceled.
 * Dragging a card between columns performs the transition through the
 * single mutation path with optimistic update + rollback (ADR 0008).
 * Cards carry ARIA roles and are keyboard-operable (dnd-kit keyboard
 * sensor on the drag handle: Space/Enter lifts, arrows move, Space/Enter
 * drops, Escape cancels).
 */
export function Board({
	teamKey,
	teamId,
	states,
	issues,
}: {
	teamKey: string;
	teamId: string;
	states: WorkflowState[];
	issues: Issue[];
}) {
	const sensors = useSensors(
		useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
		useSensor(KeyboardSensor, {
			coordinateGetter: sortableKeyboardCoordinates,
		}),
	);
	const transition = useTransitionIssue(teamId);

	const handleDragEnd = useCallback(
		(event: DragEndEvent) => {
			const { active, over } = event;
			if (!over) return;
			const issueId = String(active.id);
			const issue = issues.find((item) => item.id === issueId);
			if (!issue) return;
			const targetStateId = targetStateForDrop(String(over.id), issues, states);
			if (!targetStateId || targetStateId === issue.state_id) return;
			transition.mutate({
				issue_id: issueId,
				state_id: targetStateId,
				updated_at: issue.updated_at,
			});
		},
		[issues, states, transition],
	);

	return (
		<DndContext
			sensors={sensors}
			collisionDetection={closestCorners}
			onDragEnd={handleDragEnd}
		>
			<div className="flex h-full min-w-max gap-3">
				{states.map((state) => {
					const columnIssues = issues.filter(
						(item) => item.state_id === state.id,
					);
					return (
						<BoardColumn
							key={state.id}
							state={state}
							issues={columnIssues}
							teamKey={teamKey}
						/>
					);
				})}
			</div>
		</DndContext>
	);
}

function BoardColumn({
	state,
	issues,
	teamKey,
}: {
	state: WorkflowState;
	issues: Issue[];
	teamKey: string;
}) {
	const { isOver, setNodeRef } = useDroppable({ id: state.id });
	// The whole column (header strip included) is the drop target, so
	// drops on empty columns or the header are not discarded.
	return (
		<section
			ref={setNodeRef}
			aria-label={state.name}
			className={
				"flex h-full w-72 shrink-0 flex-col rounded-lg border border-neutral-200 dark:border-neutral-800 " +
				(isOver ? "bg-accent/10" : "bg-neutral-100/60 dark:bg-neutral-900/40")
			}
		>
			<header className="flex items-center gap-2 px-3 py-2.5">
				<span
					className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
					style={{ backgroundColor: state.color }}
					aria-hidden
				/>
				<span className="text-sm font-semibold">{state.name}</span>
				<span className="ml-auto rounded-full bg-neutral-200 px-2 py-0.5 text-xs text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400">
					{issues.length}
				</span>
			</header>
			<ul
				aria-label={`${state.name} Issues`}
				className="flex min-h-24 flex-1 flex-col gap-2 overflow-y-auto p-2"
			>
				<SortableContext
					items={issues.map((item) => item.id)}
					strategy={verticalListSortingStrategy}
				>
					{issues.map((issue) => (
						<BoardCard key={issue.id} issue={issue} teamKey={teamKey} />
					))}
				</SortableContext>
			</ul>
		</section>
	);
}

function BoardCard({ issue, teamKey }: { issue: Issue; teamKey: string }) {
	const {
		attributes,
		listeners,
		setNodeRef,
		setActivatorNodeRef,
		transform,
		transition: dndTransition,
		isDragging,
	} = useSortable({ id: issue.id });

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
				"relative flex items-start gap-1 rounded-lg border border-neutral-200 bg-white p-2.5 shadow-sm " +
				(isDragging ? "z-10 opacity-90 shadow-lg" : "")
			}
		>
			<button
				type="button"
				ref={setActivatorNodeRef}
				{...attributes}
				{...listeners}
				aria-label={`Drag ${issue.identifier}: ${issue.title}`}
				className="-m-1 cursor-grab rounded p-1 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-600 focus-visible:ring-2 focus-visible:ring-accent active:cursor-grabbing dark:hover:bg-neutral-800 dark:hover:text-neutral-300"
			>
				<GripVertical size={14} aria-hidden />
			</button>
			<Link
				to="/teams/$teamKey/issues/$issueId"
				params={{ teamKey, issueId: issue.id }}
				className="min-w-0 flex-1 rounded focus-visible:ring-2 focus-visible:ring-accent"
			>
				<div className="flex items-center gap-1.5">
					<span className="shrink-0 font-mono text-xs text-neutral-500">
						{issue.identifier}
					</span>
					<span
						className="inline-block h-2 w-2 shrink-0 rounded-full"
						style={{ backgroundColor: issue.state_color }}
						aria-hidden
					/>
					<span className="truncate text-xs text-neutral-500">
						{issue.state_name}
					</span>
				</div>
				<p className="mt-1 truncate text-sm font-medium">{issue.title}</p>
				<div className="mt-1.5 flex items-center gap-2">
					<PriorityGlyph priority={issue.priority} />
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
			</Link>
		</li>
	);
}
