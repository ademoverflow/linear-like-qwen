import {
	type QueryClient,
	useMutation,
	useQueryClient,
} from "@tanstack/react-query";

import { archiveIssue, deleteIssue, restoreIssue } from "@/api/issues";
import { toast } from "@/components/ui/Toast";

/**
 * One archive/restore/hard-delete mutation (brief §3.4, ticket 07). Plain
 * (non-optimistic): on success the Issue caches (list, board, open details)
 * are invalidated and refetched.
 */
function useIssueAction<TArg, TData>(
	queryClient: QueryClient,
	mutationFn: (arg: TArg) => Promise<TData>,
	fallback: string,
) {
	return useMutation({
		mutationFn,
		onSuccess: () => {
			void queryClient.invalidateQueries({ queryKey: ["issues"] });
		},
		onError: (error) =>
			toast(error instanceof Error ? error.message : fallback),
	});
}

/**
 * Archive / restore / hard-delete operations (brief §3.4, ticket 07). The
 * hard delete replies 204 and returns no resource.
 */
export function useIssueActions() {
	const queryClient = useQueryClient();

	const archive = useIssueAction(
		queryClient,
		(issueId: string) => archiveIssue(issueId),
		"Could not archive the Issue",
	);
	const restore = useIssueAction(
		queryClient,
		(issueId: string) => restoreIssue(issueId),
		"Could not restore the Issue",
	);
	const hardDelete = useIssueAction(
		queryClient,
		(input: { issueId: string; identifier: string }) =>
			deleteIssue(input.issueId, input.identifier),
		"Could not delete the Issue",
	);

	return { archive, restore, hardDelete };
}
