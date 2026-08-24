import { z } from "zod";

import { api } from "./client";

export const commentSchema = z.object({
	id: z.string().uuid(),
	issue_id: z.string().uuid(),
	author_id: z.string().uuid(),
	author_display_name: z.string().nullish(),
	author_avatar_url: z.string().nullish(),
	body: z.string(),
	created_at: z.coerce.date(),
	edited_at: z.coerce.date().nullish(),
});

export type Comment = z.infer<typeof commentSchema>;

/** List an Issue's Comments, oldest first (full list, no pagination). */
export async function listIssueComments(issueId: string): Promise<Comment[]> {
	const data = await api.get(`/issues/${issueId}/comments`);
	return z.array(commentSchema).parse(data);
}

/** Create a Comment (any Team member or Admin). */
export async function createComment(
	issueId: string,
	input: { body: string },
): Promise<Comment> {
	const data = await api.post(`/issues/${issueId}/comments`, input);
	return commentSchema.parse(data);
}

/** Edit a Comment's body (author only). Unversioned (ADR 0008). */
export async function updateComment(
	issueId: string,
	commentId: string,
	input: { body: string },
): Promise<Comment> {
	const data = await api.patch(
		`/issues/${issueId}/comments/${commentId}`,
		input,
	);
	return commentSchema.parse(data);
}

/** Delete a Comment (author, Team owner, or Admin). */
export async function deleteComment(
	issueId: string,
	commentId: string,
): Promise<void> {
	await api.delete(`/issues/${issueId}/comments/${commentId}`);
}
