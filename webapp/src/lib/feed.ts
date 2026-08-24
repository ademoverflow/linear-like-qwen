import type { Comment } from "@/api/comments";
import type { Activity } from "@/api/issues";

export type FeedEntry =
	| { type: "comment"; comment: Comment }
	| { type: "activity"; activity: Activity };

/**
 * Merge an Issue's Comments and Activity into one chronological feed
 * (brief §7.2.3, ticket 06).
 *
 * Both lists arrive server-ordered: Activity in insertion (seq) order,
 * Comments in creation order. A Comment's own `comment.created` Activity
 * row marks its position in the feed and is replaced by the Comment card.
 * Rows are paired to Comments by `comment_id` (set on every `comment.*`
 * row); rows without an id fall back to creation order. `comment.updated`
 * rows render as a small line (the card itself carries the "edited"
 * marker); `comment.deleted` rows render as a "deleted a Comment" line.
 * Deleting a Comment removes its created/updated rows, so surviving rows
 * always pair with a surviving Comment.
 */
export function mergeFeed(
	activities: Activity[],
	comments: Comment[],
): FeedEntry[] {
	const byId = new Map(comments.map((comment) => [comment.id, comment]));
	const used = new Set<string>();
	const entries: FeedEntry[] = [];
	let positional = 0;
	for (const activity of activities) {
		if (activity.kind !== "comment.created") {
			entries.push({ type: "activity", activity });
			continue;
		}
		const rowCommentId = activity.comment_id;
		const byRowId =
			rowCommentId !== null && rowCommentId !== undefined
				? byId.get(rowCommentId)
				: undefined;
		const comment =
			byRowId !== undefined && !used.has(byRowId.id)
				? byRowId
				: comments[positional];
		if (comment !== undefined && !used.has(comment.id)) {
			used.add(comment.id);
			positional += 1;
			entries.push({ type: "comment", comment });
			continue;
		}
		entries.push({ type: "activity", activity });
	}
	// Defensive: Comments without a surviving comment.created row (should
	// not happen) are appended in creation order.
	for (const comment of comments) {
		if (!used.has(comment.id)) entries.push({ type: "comment", comment });
	}
	return entries;
}
