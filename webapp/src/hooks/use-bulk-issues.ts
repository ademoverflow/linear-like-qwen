import { useMutation, useQueryClient } from "@tanstack/react-query";
import { bulkUpdateIssues, type IssueBulkInput } from "@/api/issues";
import { toast } from "@/components/ui/Toast";

/**
 * Bulk operations (brief §4.4, ticket 05): all-or-nothing, so no
 * optimistic update — on success the Issue caches (full list, paginated
 * pages, open details) are invalidated and refetched.
 */
export function useBulkIssues() {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: (input: IssueBulkInput) => bulkUpdateIssues(input),
		onSuccess: () => {
			void queryClient.invalidateQueries({ queryKey: ["issues"] });
		},
		onError: (error) => {
			toast(error instanceof Error ? error.message : "Bulk operation failed");
		},
	});
}
