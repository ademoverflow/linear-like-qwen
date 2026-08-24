import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createComment, deleteComment, updateComment } from "@/api/comments";
import { queryKeys } from "@/api/query-keys";
import { toast } from "@/components/ui/Toast";

/**
 * Comment mutations (ticket 06): plain, non-optimistic writes — the brief's
 * optimistic list (state/assignee/priority/label) does not name Comments.
 * On success the Issue's Comments and Activity caches refetch (the Activity
 * feed carries the comment.* rows of the merged story).
 */
export function useComments(issueId: string) {
	const queryClient = useQueryClient();

	const refetchFeed = () => {
		void queryClient.invalidateQueries({
			queryKey: queryKeys.issues.comments(issueId),
		});
		void queryClient.invalidateQueries({
			queryKey: queryKeys.issues.activity(issueId),
		});
	};

	const create = useMutation({
		mutationFn: (body: string) => createComment(issueId, { body }),
		onSuccess: refetchFeed,
		onError: (error) =>
			toast(
				error instanceof Error ? error.message : "Could not post the Comment",
			),
	});

	const update = useMutation({
		mutationFn: (input: { commentId: string; body: string }) =>
			updateComment(issueId, input.commentId, { body: input.body }),
		onSuccess: refetchFeed,
		onError: (error) =>
			toast(
				error instanceof Error ? error.message : "Could not update the Comment",
			),
	});

	const remove = useMutation({
		mutationFn: (commentId: string) => deleteComment(issueId, commentId),
		onSuccess: refetchFeed,
		onError: (error) =>
			toast(
				error instanceof Error ? error.message : "Could not delete the Comment",
			),
	});

	return { create, update, remove };
}
