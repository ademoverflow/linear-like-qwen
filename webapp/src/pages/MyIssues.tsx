import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { type Issue, type IssueListPage, listIssues } from "@/api/issues";
import { queryKeys } from "@/api/query-keys";
import { listTeamLabels, listTeamMembers, listTeamStates } from "@/api/teams";
import { IssueCard } from "@/components/issues/IssueCard";
import { SORT_OPTIONS } from "@/components/issues/IssueFilterDialog";
import { IssueQuickActions } from "@/components/issues/IssueQuickActions";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { toast } from "@/components/ui/Toast";
import { useCurrentUser } from "@/hooks/use-current-user";
import {
	type QuickActionKind,
	useIssueListKeyboard,
} from "@/hooks/use-issue-list-keyboard";
import { useShortcut } from "@/hooks/use-shortcut";
import { useTransitionIssue } from "@/hooks/use-transition-issue";
import { useUpdateIssue } from "@/hooks/use-update-issue";
import { SELECT_CLASS } from "@/lib/styles";

const DEFAULT_SORT = "created:desc";
const PAGE_SIZE = 50;

/**
 * My Issues (brief §6, ticket 09): Issues assigned to the current User
 * across all their Teams, grouped by Team. Reuses the Issue list
 * endpoint without `team_id` (the server scopes to the user's Memberships)
 * plus the same keyboard set as the Team Issues list.
 */
export function MyIssues() {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const me = useCurrentUser().data;

	const [sort, setSort] = useState<string>(DEFAULT_SORT);
	const [loadingMore, setLoadingMore] = useState(false);
	const [quick, setQuick] = useState<QuickActionKind | null>(null);

	const myPageKey = queryKeys.issues.myPage(sort);
	const issuesQuery = useQuery({
		queryKey: myPageKey,
		queryFn: () =>
			me
				? listIssues(undefined, {
						assignee_ids: [me.id],
						limit: PAGE_SIZE,
						sort,
					})
				: Promise.resolve({ issues: [], next_cursor: null }),
		enabled: me !== undefined,
	});

	const issues = issuesQuery.data?.issues ?? [];
	const nextCursor = issuesQuery.data?.next_cursor ?? null;

	const loadMore = () => {
		if (!me || !nextCursor || loadingMore) return;
		setLoadingMore(true);
		listIssues(undefined, {
			assignee_ids: [me.id],
			limit: PAGE_SIZE,
			sort,
			cursor: nextCursor,
		})
			.then((next) => {
				queryClient.setQueryData<IssueListPage>(myPageKey, (previous) =>
					previous
						? {
								issues: [...previous.issues, ...next.issues],
								next_cursor: next.next_cursor,
							}
						: previous,
				);
			})
			.catch(() => toast("Could not load more Issues"))
			.finally(() => setLoadingMore(false));
	};

	// Group by Team (the server scopes to the user's Memberships; the
	// Team's key/name come from /auth/me).
	const teamInfo = useMemo(() => {
		const map = new Map<string, { key: string; name: string }>();
		for (const membership of me?.memberships ?? []) {
			map.set(membership.team_id, {
				key: membership.team_key,
				name: membership.team_name,
			});
		}
		return map;
	}, [me]);

	const groups = useMemo(() => {
		const byTeam = new Map<string, Issue[]>();
		for (const issue of issues) {
			byTeam.set(issue.team_id, [...(byTeam.get(issue.team_id) ?? []), issue]);
		}
		return [...byTeam.entries()]
			.map(([teamId, items]) => ({
				team: teamInfo.get(teamId),
				items,
			}))
			.filter(
				(
					group,
				): group is {
					team: { key: string; name: string };
					items: Issue[];
				} => group.team !== undefined,
			);
	}, [issues, teamInfo]);

	const flatIssues = useMemo(
		() => groups.flatMap((group) => group.items),
		[groups],
	);

	const { cursorId, setCursorId } = useIssueListKeyboard({
		issueIds: flatIssues.map((issue) => issue.id),
		disabled: quick !== null,
		onOpen: (issueId) => {
			const issue = flatIssues.find((item) => item.id === issueId);
			const team = issue ? teamInfo.get(issue.team_id) : undefined;
			if (issue && team) {
				navigate({
					to: "/teams/$teamKey/issues/$issueId",
					params: { teamKey: team.key, issueId: issue.id },
				});
			}
		},
		onQuickAction: setQuick,
	});
	useShortcut("Escape", () => {
		if (quick !== null) {
			setQuick(null);
		} else {
			setCursorId(null);
		}
	});

	const cursorIssue = flatIssues.find((issue) => issue.id === cursorId) ?? null;
	const cursorTeamId = cursorIssue?.team_id ?? "";
	const statesQuery = useQuery({
		queryKey: queryKeys.teams.states(cursorTeamId),
		queryFn: () =>
			cursorIssue ? listTeamStates(cursorIssue.team_id) : Promise.resolve([]),
		enabled: cursorIssue !== null,
	});
	const membersQuery = useQuery({
		queryKey: queryKeys.teams.members(cursorTeamId),
		queryFn: () =>
			cursorIssue ? listTeamMembers(cursorIssue.team_id) : Promise.resolve([]),
		enabled: cursorIssue !== null,
	});
	const labelsQuery = useQuery({
		queryKey: queryKeys.teams.labels(cursorTeamId),
		queryFn: () =>
			cursorIssue ? listTeamLabels(cursorIssue.team_id) : Promise.resolve([]),
		enabled: cursorIssue !== null,
	});

	// The optimistic hooks patch per-Team caches, which do not include the
	// cross-Team My Issues page: refresh it after each quick action.
	const refreshMyIssues = {
		onSuccess: () => {
			void queryClient.invalidateQueries({ queryKey: ["issues"] });
		},
	};
	const transition = useTransitionIssue(cursorTeamId);
	const update = useUpdateIssue(cursorTeamId, cursorIssue?.id ?? "");

	if (issuesQuery.isLoading) {
		return (
			<div className="flex max-w-2xl flex-col gap-2 p-4">
				<Skeleton className="h-[72px] w-full" />
				<Skeleton className="h-[72px] w-full" />
				<Skeleton className="h-[72px] w-full" />
			</div>
		);
	}
	if (issuesQuery.isError) {
		return (
			<CenteredMessage>
				<h1 className="text-lg font-semibold">Could not load Issues</h1>
				<p className="mt-2 text-sm text-muted">
					{issuesQuery.error instanceof Error
						? issuesQuery.error.message
						: "Unknown error"}
				</p>
				<div className="mt-4 flex justify-center">
					<Button onClick={() => issuesQuery.refetch()}>Retry</Button>
				</div>
			</CenteredMessage>
		);
	}

	return (
		<div className="flex h-full flex-col">
			<div className="sticky top-0 z-10 flex items-center gap-4 border-b border-line bg-surface/90 px-4 py-2 backdrop-blur">
				<nav aria-label="Breadcrumb">
					<span className="text-sm font-semibold">My Issues</span>
				</nav>
				<div className="ml-auto flex items-center gap-2">
					<select
						aria-label="Sort"
						value={sort}
						onChange={(event) => setSort(event.target.value)}
						className={SELECT_CLASS}
					>
						{SORT_OPTIONS.map((option) => (
							<option key={option.value} value={option.value}>
								{option.label}
							</option>
						))}
					</select>
				</div>
			</div>

			<div className="flex-1 overflow-y-auto">
				{issues.length === 0 ? (
					<CenteredMessage>
						<h1 className="text-lg font-semibold">No Issues assigned to you</h1>
						<p className="mt-2 text-sm text-muted">
							Issues you are assigned to, across all your Teams, appear here.
						</p>
					</CenteredMessage>
				) : (
					<div className="mx-auto flex w-full max-w-2xl flex-col gap-4 p-4">
						{groups.map((group) => (
							<section
								key={group.team.key}
								aria-label={`${group.team.name} Issues`}
								className="flex flex-col gap-2"
							>
								<div className="flex items-center gap-2">
									<span className="shrink-0 font-mono text-xs text-muted">
										{group.team.key}
									</span>
									<span className="text-sm font-semibold">
										{group.team.name}
									</span>
									<span className="text-xs text-faint">
										{group.items.length}
									</span>
								</div>
								{group.items.map((issue) => (
									<IssueCard
										key={issue.id}
										issue={issue}
										teamKey={group.team.key}
										selected={cursorId === issue.id}
									/>
								))}
							</section>
						))}
						{nextCursor && (
							<div className="flex justify-center">
								<Button
									variant="secondary"
									disabled={loadingMore}
									onClick={loadMore}
								>
									{loadingMore ? "Loading…" : "Load more"}
								</Button>
							</div>
						)}
					</div>
				)}
			</div>

			{quick !== null && cursorIssue && (
				<IssueQuickActions
					issue={cursorIssue}
					kind={quick}
					states={statesQuery.data ?? []}
					members={membersQuery.data ?? []}
					labels={labelsQuery.data ?? []}
					onStateChange={(stateId) => {
						transition.mutate(
							{
								issue_id: cursorIssue.id,
								state_id: stateId,
								updated_at: cursorIssue.updated_at,
							},
							refreshMyIssues,
						);
						setQuick(null);
					}}
					onAssigneeChange={(userId) => {
						update.mutate(
							{ updated_at: cursorIssue.updated_at, assignee_id: userId },
							refreshMyIssues,
						);
						setQuick(null);
					}}
					onPriorityChange={(priority) => {
						update.mutate(
							{ updated_at: cursorIssue.updated_at, priority },
							refreshMyIssues,
						);
						setQuick(null);
					}}
					onToggleLabel={(label, add) => {
						const labelIds = add
							? [...cursorIssue.labels.map((item) => item.id), label.id]
							: cursorIssue.labels
									.filter((item) => item.id !== label.id)
									.map((item) => item.id);
						update.mutate(
							{ updated_at: cursorIssue.updated_at, label_ids: labelIds },
							refreshMyIssues,
						);
						setQuick(null);
					}}
				/>
			)}
		</div>
	);
}

function CenteredMessage({ children }: { children: React.ReactNode }) {
	return (
		<div className="flex min-h-[50vh] flex-col items-center justify-center p-8 text-center">
			{children}
		</div>
	);
}
