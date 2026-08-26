import { useCallback, useEffect, useState } from "react";
import { useShortcut } from "./use-shortcut";

export type QuickActionKind = "state" | "assignee" | "priority" | "labels";

interface IssueListKeyboardOptions {
	/** The visible Issue ids in display order (the cursor's domain). */
	issueIds: string[];
	/** Suspends the cursor keys (e.g. bulk selection mode). */
	disabled?: boolean;
	/** `Enter`: open the Issue at the cursor. */
	onOpen: (issueId: string) => void;
	/** `S`/`A`/`P`/`L`: open a quick-edit action for the Issue at the cursor. */
	onQuickAction: (kind: QuickActionKind) => void;
}

/**
 * The list-level keyboard set (brief §7.3, ticket 09): `J`/`K` or the
 * arrows move a keyboard cursor, `Enter` opens the selected Issue and
 * `S`/`A`/`P`/`L` open quick-edit actions (State/Assignee/Priority/Labels).
 * The cursor is an Issue *id* (separate from the bulk checkbox set), so it
 * survives State re-grouping; with nothing selected, `S`/`A`/`P`/`L`
 * select the first row. Like every single-key shortcut, none of these fire
 * while focus is in a typing target (via `useShortcut`).
 */
export function useIssueListKeyboard({
	issueIds,
	disabled = false,
	onOpen,
	onQuickAction,
}: IssueListKeyboardOptions) {
	const [cursorId, setCursorId] = useState<string | null>(null);

	const move = useCallback(
		(delta: number) => {
			if (issueIds.length === 0) return;
			setCursorId((previous) => {
				const index = previous === null ? -1 : issueIds.indexOf(previous);
				const next =
					index === -1
						? 0
						: (index + delta + issueIds.length) % issueIds.length;
				return issueIds[next];
			});
		},
		[issueIds],
	);

	const open = useCallback(() => {
		const issueId = cursorId ?? issueIds[0];
		if (issueId) onOpen(issueId);
	}, [cursorId, issueIds, onOpen]);

	const quick = useCallback(
		(kind: QuickActionKind) => {
			const issueId = cursorId ?? issueIds[0];
			if (!issueId) return;
			if (cursorId === null) setCursorId(issueId);
			onQuickAction(kind);
		},
		[cursorId, issueIds, onQuickAction],
	);

	// Every list shortcut passes through this disabled-guard (bulk mode).
	const guarded = useCallback(
		(action: () => void) => {
			if (!disabled) action();
		},
		[disabled],
	);

	useShortcut("j", () => guarded(() => move(1)));
	useShortcut("k", () => guarded(() => move(-1)));
	useShortcut("ArrowDown", () => guarded(() => move(1)));
	useShortcut("ArrowUp", () => guarded(() => move(-1)));
	useShortcut("Enter", () => guarded(open));
	useShortcut("s", () => guarded(() => quick("state")));
	useShortcut("a", () => guarded(() => quick("assignee")));
	useShortcut("p", () => guarded(() => quick("priority")));
	useShortcut("l", () => guarded(() => quick("labels")));

	useEffect(() => {
		if (cursorId === null) return;
		const row = document.querySelector(`[data-issue-id="${cursorId}"]`);
		// jsdom (and very old browsers) have no scrollIntoView.
		if (row && typeof row.scrollIntoView === "function") {
			row.scrollIntoView({ block: "nearest" });
		}
	}, [cursorId]);

	return { cursorId, setCursorId };
}
