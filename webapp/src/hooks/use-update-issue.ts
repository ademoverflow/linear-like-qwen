import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/api/client";
import {
	type Issue,
	type IssueDetail,
	type IssueUpdateInput,
	updateIssue,
} from "@/api/issues";
import { queryKeys } from "@/api/query-keys";
import type { TeamMember } from "@/api/teams";
import { toast } from "@/components/ui/Toast";

function applyPatchToIssue(
	issue: Issue,
	input: IssueUpdateInput,
	members: TeamMember[] | undefined,
	allIssues: Issue[] | undefined,
): Issue {
	// Placeholder timestamp; the refetch after success replaces it with the
	// authoritative server value (written into the cache on success).
	const next: Issue = { ...issue, updated_at: new Date().toISOString() };
	if (input.title !== undefined && input.title !== null)
		next.title = input.title;
	if (input.description !== undefined) next.description = input.description;
	if (input.priority !== undefined)
		next.priority = (input.priority ?? "none") as Issue["priority"];
	if (input.assignee_id !== undefined) {
		next.assignee_id = input.assignee_id;
		const member = members?.find((m) => m.id === input.assignee_id);
		next.assignee_display_name = member?.display_name ?? null;
		next.assignee_avatar_url = member?.avatar_url ?? null;
	}
	if (input.parent_id !== undefined) {
		next.parent_id = input.parent_id;
		if ("parent_identifier" in next && "parent_title" in next) {
			const parent = allIssues?.find((i) => i.id === input.parent_id);
			next.parent_identifier = parent?.identifier ?? null;
			next.parent_title = parent?.title ?? null;
		}
	}
	if (input.due_date !== undefined) {
		next.due_date = input.due_date ? new Date(input.due_date) : null;
	}
	if (input.estimate !== undefined) next.estimate = input.estimate;
	return next;
}

/**
 * Optimistic Issue editing (ADR 0008): apply the change to the cached
 * Issue, roll back on error; a 409 (stale `updated_at`) refetches the
 * latest state. On success the server response (authoritative
 * `updated_at`) is written into the detail and list caches, and only the
 * Activity feed refetches.
 */
export function useUpdateIssue(teamId: string, issueId: string) {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: (input: IssueUpdateInput) => updateIssue(issueId, input),
		onMutate: async (input) => {
			await queryClient.cancelQueries({
				queryKey: queryKeys.issues.detail(issueId),
			});
			const previousDetail = queryClient.getQueryData<IssueDetail>(
				queryKeys.issues.detail(issueId),
			);
			const previousList = queryClient.getQueryData<Issue[]>(
				queryKeys.issues.team(teamId),
			);
			const members = queryClient.getQueryData<TeamMember[]>(
				queryKeys.teams.members(teamId),
			);
			if (previousDetail) {
				queryClient.setQueryData<IssueDetail>(
					queryKeys.issues.detail(issueId),
					applyPatchToIssue(previousDetail, input, members, previousList),
				);
			}
			if (previousList) {
				queryClient.setQueryData<Issue[]>(
					queryKeys.issues.team(teamId),
					previousList.map((issue) =>
						issue.id === issueId
							? applyPatchToIssue(issue, input, members, previousList)
							: issue,
					),
				);
			}
			return { previousDetail, previousList };
		},
		onError: (error, _input, context) => {
			if (context?.previousDetail) {
				queryClient.setQueryData(
					queryKeys.issues.detail(issueId),
					context.previousDetail,
				);
			}
			if (context?.previousList) {
				queryClient.setQueryData(
					queryKeys.issues.team(teamId),
					context.previousList,
				);
			}
			if (error instanceof ApiError && error.status === 409) {
				void queryClient.invalidateQueries({
					queryKey: queryKeys.issues.detail(issueId),
				});
				void queryClient.invalidateQueries({
					queryKey: queryKeys.issues.team(teamId),
				});
				void queryClient.invalidateQueries({
					queryKey: queryKeys.issues.activity(issueId),
				});
				toast(
					"This Issue was changed by someone else. Loaded the latest version.",
				);
			} else {
				toast(
					error instanceof Error ? error.message : "Could not update the Issue",
				);
			}
		},
		onSuccess: (data) => {
			queryClient.setQueryData<IssueDetail>(
				queryKeys.issues.detail(issueId),
				(cached) =>
					cached
						? {
								...data,
								parent_identifier: cached.parent_identifier,
								parent_title: cached.parent_title,
							}
						: cached,
			);
			queryClient.setQueryData<Issue[]>(
				queryKeys.issues.team(teamId),
				(cached) =>
					cached
						? cached.map((issue) => (issue.id === issueId ? data : issue))
						: cached,
			);
			void queryClient.invalidateQueries({
				queryKey: queryKeys.issues.activity(issueId),
			});
		},
	});
}
