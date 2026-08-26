import { useQuery } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import { getIssue, listAllIssues } from "@/api/issues";
import { queryKeys } from "@/api/query-keys";
import {
	listTeamLabels,
	listTeamMembers,
	listTeamStates,
	listTeams,
} from "@/api/teams";
import { IssueCard } from "@/components/issues/IssueCard";
import { IssueDetailPanel } from "@/components/issues/IssueDetailPanel";
import { useNewIssue } from "@/components/layout/new-issue-context";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { useMediaQuery } from "@/hooks/use-media-query";

/**
 * Issue detail (ticket 03): the Team's Issues in the left column on wide
 * screens, the detail panel on the right; below 768px the list column is
 * not rendered and the panel is the full page — the back link in the panel
 * header ("‹ ENG / Issues") is the navigation back (brief §7.1, §7.4,
 * ticket 10).
 */
export function IssueDetail() {
	// `from` matches by routeId; the pathless "app" layout prefixes child ids.
	const { teamKey, issueId } = useParams({
		from: "/app/teams/$teamKey/issues/$issueId",
	});
	const newIssue = useNewIssue();
	const isDesktop = useMediaQuery("(min-width: 768px)");

	const teamsQuery = useQuery({
		queryKey: queryKeys.teams.all(),
		queryFn: listTeams,
	});
	const team = teamsQuery.data?.find((item) => item.key === teamKey);

	const issuesQuery = useQuery({
		queryKey: queryKeys.issues.team(team?.id ?? ""),
		queryFn: () => (team ? listAllIssues(team.id) : Promise.resolve([])),
		enabled: team !== undefined,
	});
	const issueQuery = useQuery({
		queryKey: queryKeys.issues.detail(issueId),
		queryFn: () => getIssue(issueId),
	});
	const membersQuery = useQuery({
		queryKey: queryKeys.teams.members(team?.id ?? ""),
		queryFn: () => (team ? listTeamMembers(team.id) : Promise.resolve([])),
		enabled: team !== undefined,
	});
	const statesQuery = useQuery({
		queryKey: queryKeys.teams.states(team?.id ?? ""),
		queryFn: () => (team ? listTeamStates(team.id) : Promise.resolve([])),
		enabled: team !== undefined,
	});
	const labelsQuery = useQuery({
		queryKey: queryKeys.teams.labels(team?.id ?? ""),
		queryFn: () => (team ? listTeamLabels(team.id) : Promise.resolve([])),
		enabled: team !== undefined,
	});

	if (teamsQuery.isLoading) {
		return <PanelSkeleton />;
	}
	if (!team) {
		return (
			<CenteredMessage>
				<h1 className="text-lg font-semibold">Team not found</h1>
				<p className="mt-2 text-sm text-muted">
					No Team with the key {teamKey} is visible to you.
				</p>
			</CenteredMessage>
		);
	}

	return (
		<div className="flex h-full">
			{isDesktop && (
				<div className="flex w-2/5 min-w-80 max-w-md flex-col border-r border-line bg-surface">
					<div className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-surface/90 px-4 py-2 backdrop-blur">
						<nav aria-label="Breadcrumb">
							<span className="text-sm font-semibold">{team.key}</span>
							<span className="mx-1.5 text-faint">›</span>
							<span className="text-sm text-muted">Issues</span>
						</nav>
						<Button variant="secondary" onClick={() => newIssue.open(team.id)}>
							New Issue
						</Button>
					</div>
					<div className="flex-1 p-4">
						{(issuesQuery.data ?? []).length === 0 ? (
							<p className="text-sm text-muted">No Issues yet</p>
						) : (
							<div className="flex flex-col gap-2">
								{(issuesQuery.data ?? []).map((issue) => (
									<IssueCard key={issue.id} issue={issue} teamKey={team.key} />
								))}
							</div>
						)}
					</div>
				</div>
			)}
			<div className="min-w-0 flex-1 overflow-y-auto">
				{issueQuery.isLoading ? (
					<PanelSkeleton />
				) : issueQuery.isError ? (
					<CenteredMessage>
						<h1 className="text-lg font-semibold">Could not load the Issue</h1>
						<p className="mt-2 text-sm text-muted">
							{issueQuery.error instanceof Error
								? issueQuery.error.message
								: "Unknown error"}
						</p>
						<div className="mt-4 flex justify-center">
							<Button onClick={() => issueQuery.refetch()}>Retry</Button>
						</div>
					</CenteredMessage>
				) : issueQuery.data ? (
					<IssueDetailPanel
						issue={issueQuery.data}
						teamKey={team.key}
						teamId={team.id}
						issues={issuesQuery.data ?? []}
						members={membersQuery.data ?? []}
						states={statesQuery.data ?? []}
						labels={labelsQuery.data ?? []}
					/>
				) : (
					<PanelSkeleton />
				)}
			</div>
		</div>
	);
}

function PanelSkeleton() {
	return (
		<div className="flex flex-col gap-3 p-6">
			<Skeleton className="h-5 w-40" />
			<Skeleton className="h-8 w-2/3" />
			<Skeleton className="h-24 w-full" />
			<Skeleton className="h-40 w-full" />
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
