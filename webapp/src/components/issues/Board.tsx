import {
	closestCorners,
	DndContext,
	type DragEndEvent,
	type DragOverEvent,
	type DragStartEvent,
	KeyboardSensor,
	PointerSensor,
	useDndContext,
	useDroppable,
	useSensor,
	useSensors,
} from "@dnd-kit/core";
import {
	SortableContext,
	type SortingStrategy,
	sortableKeyboardCoordinates,
	useSortable,
} from "@dnd-kit/sortable";
import { Link } from "@tanstack/react-router";
import { GripVertical } from "lucide-react";
import { Fragment, useCallback, useState } from "react";
import type { Issue } from "@/api/issues";
import type { WorkflowState } from "@/api/teams";
import { Avatar } from "@/components/ui/Avatar";
import { useTransitionIssue } from "@/hooks/use-transition-issue";
import { PriorityGlyph } from "@/lib/priorities";
import { LabelChip } from "./LabelChip";

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

// Columns are transition targets, not reorderable lists: the built-in item
// displacement would double the space the drop placeholder already makes.
// Keyboard movement is unaffected (dnd-kit derives the coordinates from
// droppable rects, not from the strategy).
const noReflowStrategy: SortingStrategy = () => null;

/** Where the dragged card will land if dropped now (column + insertion index). */
interface DropHint {
	columnId: string;
	index: number;
}

/**
 * Kanban Board (brief §7.2.4, ADR 0006 + ADR 0011): one column per
 * Workflow State in position order — including backlog and canceled.
 * Dragging a card between columns performs the transition through the
 * single mutation path with optimistic update + rollback (ADR 0008).
 * While a card hovers a column, a ghost of the card marks the insertion
 * point (the Linear/Trello "pending" drop indicator). Cards carry ARIA
 * roles and are keyboard-operable (dnd-kit keyboard sensor on the drag
 * handle: Space/Enter lifts, arrows move, Space/Enter drops, Esc cancels).
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
	const [draggedIssue, setDraggedIssue] = useState<Issue | null>(null);
	const [placeholderHeight, setPlaceholderHeight] = useState<number | null>(
		null,
	);
	const [dropHint, setDropHint] = useState<DropHint | null>(null);

	const computeDropHint = useCallback(
		(event: DragOverEvent): DropHint | null => {
			const { active, over } = event;
			if (!over) return null;
			const overId = String(over.id);
			const activeRect = active.rect.current.translated;
			const overColumn = states.find((state) => state.id === overId);
			if (overColumn) {
				// Hovering the column body or header: the top half inserts
				// at the top, the bottom half at the end (Trello convention).
				const columnIssues = issues.filter(
					(item) => item.state_id === overColumn.id,
				);
				const atTop =
					activeRect == null
						? true
						: activeRect.top + activeRect.height / 2 <
							over.rect.top + over.rect.height / 2;
				return {
					columnId: overColumn.id,
					index: atTop ? 0 : columnIssues.length,
				};
			}
			const overIssue = issues.find((item) => item.id === overId);
			if (!overIssue) return null;
			const columnIssues = issues.filter(
				(item) => item.state_id === overIssue.state_id,
			);
			const index = columnIssues.findIndex((item) => item.id === overIssue.id);
			// The top half of a hovered card inserts above it, the bottom
			// half below it (the Linear/Trello convention).
			const above =
				activeRect == null
					? true
					: activeRect.top + activeRect.height / 2 <
						over.rect.top + over.rect.height / 2;
			return {
				columnId: overIssue.state_id,
				index: above ? index : index + 1,
			};
		},
		[issues, states],
	);

	const handleDragStart = useCallback(
		(event: DragStartEvent) => {
			const issue = issues.find((item) => item.id === String(event.active.id));
			setDraggedIssue(issue ?? null);
			setPlaceholderHeight(event.active.rect.current.initial?.height ?? null);
			setDropHint(null);
		},
		[issues],
	);

	const handleDragOver = useCallback(
		(event: DragOverEvent) => {
			const hint = computeDropHint(event);
			setDropHint((previous) =>
				previous?.columnId === hint?.columnId && previous?.index === hint?.index
					? previous
					: hint,
			);
		},
		[computeDropHint],
	);

	const endDrag = useCallback(() => {
		setDraggedIssue(null);
		setPlaceholderHeight(null);
		setDropHint(null);
	}, []);

	const handleDragEnd = useCallback(
		(event: DragEndEvent) => {
			const { active, over } = event;
			endDrag();
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
		[issues, states, transition, endDrag],
	);

	return (
		<DndContext
			sensors={sensors}
			collisionDetection={closestCorners}
			measuring={{ droppable: { frequency: 50 } }}
			onDragStart={handleDragStart}
			onDragOver={handleDragOver}
			onDragEnd={handleDragEnd}
			onDragCancel={endDrag}
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
							dropHint={dropHint?.columnId === state.id ? dropHint : null}
							draggedIssue={draggedIssue}
							placeholderHeight={placeholderHeight}
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
	dropHint,
	draggedIssue,
	placeholderHeight,
}: {
	state: WorkflowState;
	issues: Issue[];
	teamKey: string;
	dropHint: DropHint | null;
	draggedIssue: Issue | null;
	placeholderHeight: number | null;
}) {
	const { active } = useDndContext();
	const { isOver, setNodeRef } = useDroppable({ id: state.id });
	// The whole column (header strip included) is the drop target, so
	// drops on empty columns or the header are not discarded.
	return (
		<section
			ref={setNodeRef}
			aria-label={state.name}
			className={
				"flex h-full w-72 shrink-0 flex-col rounded-lg border border-neutral-200 dark:border-neutral-800 " +
				(isOver || dropHint != null
					? "bg-accent/10"
					: "bg-neutral-100/60 dark:bg-neutral-900/40")
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
				className={
					"flex min-h-24 flex-1 flex-col gap-2 p-2 " +
					// A dragged card leaves the list: an overflowing list
					// would clip it at the column edge (and spawn a
					// horizontal scrollbar inside the column), so the
					// list opens up while a drag is active.
					(active ? "overflow-visible" : "overflow-y-auto")
				}
			>
				<SortableContext
					items={issues.map((item) => item.id)}
					strategy={noReflowStrategy}
				>
					{issues.map((issue, index) => (
						<Fragment key={issue.id}>
							{dropHint?.index === index && draggedIssue && (
								<DropPlaceholder
									issue={draggedIssue}
									height={placeholderHeight}
								/>
							)}
							<BoardCard issue={issue} teamKey={teamKey} />
						</Fragment>
					))}
					{dropHint?.index === issues.length && draggedIssue && (
						<DropPlaceholder issue={draggedIssue} height={placeholderHeight} />
					)}
				</SortableContext>
			</ul>
		</section>
	);
}

/**
 * The "pending" preview of the dragged card in its target column (the
 * Linear/Trello drop indicator): a ghost of the card at the insertion
 * point while the card hovers the column.
 */
function DropPlaceholder({
	issue,
	height,
}: {
	issue: Issue;
	height: number | null;
}) {
	return (
		<div
			aria-hidden
			style={height == null ? undefined : { height }}
			className="flex shrink-0 items-start rounded-lg border-2 border-dashed border-neutral-300 bg-white/60 p-2.5 dark:border-neutral-600 dark:bg-neutral-800/40"
		>
			<div className="min-w-0 flex-1">
				<div className="flex items-center gap-1.5">
					<span className="shrink-0 font-mono text-xs text-neutral-400">
						{issue.identifier}
					</span>
					<span
						className="inline-block h-2 w-2 shrink-0 rounded-full"
						style={{ backgroundColor: issue.state_color }}
						aria-hidden
					/>
					<span className="truncate text-xs text-neutral-400">
						{issue.state_name}
					</span>
				</div>
				<p className="mt-1 truncate text-sm font-medium text-neutral-500 dark:text-neutral-400">
					{issue.title}
				</p>
				<div className="mt-1.5 flex items-center gap-2">
					<PriorityGlyph priority={issue.priority} />
				</div>
			</div>
		</div>
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
				(isDragging ? "z-20 opacity-90 shadow-lg" : "")
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
				{issue.labels.length > 0 && (
					<div className="mt-1.5 flex flex-wrap gap-1">
						{issue.labels.map((label) => (
							<LabelChip key={label.id} label={label} compact />
						))}
					</div>
				)}
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
