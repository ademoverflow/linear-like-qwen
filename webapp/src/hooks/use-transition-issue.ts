import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/api/client";
import { type Issue, type IssueDetail, transitionIssue } from "@/api/issues";
import { queryKeys } from "@/api/query-keys";
import type { WorkflowState } from "@/api/teams";
import { toast } from "@/components/ui/Toast";

interface TransitionInput {
	issue_id: string;
	state_id: string;
	updated_at: string;
}

/**
 * Apply the optimistic State change to a cached Issue. The placeholder
 * `updated_at` is replaced by the authoritative server response on
 * success. Timestamp stamping/clearing mirrors the domain rules
 * (brief §4.2): completed → completed_at, canceled → canceled_at,
 * anything else clears both.
 */
function applyTransitionToIssue(
	issue: Issue,
	stateId: string,
	states: WorkflowState[] | undefined,
): Issue {
	const state = states?.find((item) => item.id === stateId);
	const now = new Date().toISOString();
	const next: Issue = {
		...issue,
		updated_at: now,
		state_id: stateId,
		state_name: state?.name ?? issue.state_name,
		state_category: state?.category ?? issue.state_category,
		state_color: state?.color ?? issue.state_color,
		completed_at: null,
		canceled_at: null,
	};
	if (state?.category === "completed") next.completed_at = new Date(now);
	if (state?.category === "canceled") next.canceled_at = new Date(now);
	return next;
}

/**
 * Optimistic State transitions (ADR 0008): apply the move to the cached
 * Issue (detail + Team list), roll back on error; a 409 (stale
 * `updated_at`) refetches the latest state. On success the server
 * response (authoritative `updated_at`) is written into the caches and
 * only the Activity feed refetches.
 */
export function useTransitionIssue(teamId: string) {
	const queryClient = useQueryClient();

	return useMutation({
		mutationFn: ({ issue_id, state_id, updated_at }: TransitionInput) =>
			transitionIssue(issue_id, { state_id, updated_at }),
		onMutate: async (input) => {
			const issueId = input.issue_id;
			await queryClient.cancelQueries({
				queryKey: queryKeys.issues.detail(issueId),
			});
			const previousDetail = queryClient.getQueryData<IssueDetail>(
				queryKeys.issues.detail(issueId),
			);
			const previousList = queryClient.getQueryData<Issue[]>(
				queryKeys.issues.team(teamId),
			);
			const states = queryClient.getQueryData<WorkflowState[]>(
				queryKeys.teams.states(teamId),
			);
			if (previousDetail) {
				queryClient.setQueryData<IssueDetail>(
					queryKeys.issues.detail(issueId),
					applyTransitionToIssue(previousDetail, input.state_id, states),
				);
			}
			if (previousList) {
				queryClient.setQueryData<Issue[]>(
					queryKeys.issues.team(teamId),
					previousList.map((issue) =>
						issue.id === issueId
							? applyTransitionToIssue(issue, input.state_id, states)
							: issue,
					),
				);
			}
			return { issueId, previousDetail, previousList };
		},
		onError: (error, _input, context) => {
			if (context?.previousDetail) {
				queryClient.setQueryData(
					queryKeys.issues.detail(context.issueId),
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
					queryKey: queryKeys.issues.detail(context?.issueId ?? ""),
				});
				void queryClient.invalidateQueries({
					queryKey: queryKeys.issues.team(teamId),
				});
				void queryClient.invalidateQueries({
					queryKey: queryKeys.issues.activity(context?.issueId ?? ""),
				});
				toast(
					"This Issue was changed by someone else. Loaded the latest version.",
				);
			} else {
				toast(
					error instanceof Error ? error.message : "Could not move the Issue",
				);
			}
		},
		onSuccess: (data, input) => {
			queryClient.setQueryData<IssueDetail>(
				queryKeys.issues.detail(input.issue_id),
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
						? cached.map((issue) =>
								issue.id === input.issue_id ? data : issue,
							)
						: cached,
			);
			void queryClient.invalidateQueries({
				queryKey: queryKeys.issues.activity(input.issue_id),
			});
		},
	});
}
