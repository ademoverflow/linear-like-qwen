import { useQuery } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import { listIssues } from "@/api/issues";
import { queryKeys } from "@/api/query-keys";
import { listTeamStates, listTeams } from "@/api/teams";
import { Board } from "@/components/issues/Board";
import { useNewIssue } from "@/components/layout/new-issue-context";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";

/**
 * Team Board (brief §7.2.4, ticket 04): a Kanban with one column per
 * Workflow State (position order, incl. backlog and canceled — ADR 0011);
 * dragging a card between columns transitions it via the API.
 */
export function TeamBoard() {
	// `from` matches by routeId; the pathless "app" layout prefixes child ids.
	const { teamKey } = useParams({ from: "/app/teams/$teamKey/board" });
	const newIssue = useNewIssue();

	const teamsQuery = useQuery({
		queryKey: queryKeys.teams.all(),
		queryFn: listTeams,
	});
	const team = teamsQuery.data?.find((item) => item.key === teamKey);

	const statesQuery = useQuery({
		queryKey: queryKeys.teams.states(team?.id ?? ""),
		queryFn: () => (team ? listTeamStates(team.id) : Promise.resolve([])),
		enabled: team !== undefined,
	});
	const issuesQuery = useQuery({
		queryKey: queryKeys.issues.team(team?.id ?? ""),
		queryFn: () => (team ? listIssues(team.id) : Promise.resolve([])),
		enabled: team !== undefined,
	});

	if (teamsQuery.isLoading) {
		return <BoardSkeleton />;
	}
	if (!team) {
		return (
			<CenteredMessage>
				<h1 className="text-lg font-semibold">Team not found</h1>
				<p className="mt-2 text-sm text-neutral-500">
					No Team with the key {teamKey} is visible to you.
				</p>
			</CenteredMessage>
		);
	}

	const loading = statesQuery.isLoading || issuesQuery.isLoading;
	// Both queries must succeed: a states failure would otherwise render
	// zero columns silently (issues could still load fine).
	const loadError = statesQuery.isError || issuesQuery.isError;
	const loadFailure = statesQuery.isError
		? statesQuery.error
		: issuesQuery.error;

	return (
		<div className="flex h-full flex-col">
			<div className="sticky top-0 z-10 flex items-center justify-between border-b border-neutral-200 bg-white/90 px-4 py-2 backdrop-blur dark:border-neutral-800 dark:bg-neutral-900/90">
				<nav aria-label="Breadcrumb">
					<span className="text-sm font-semibold">{team.key}</span>
					<span className="mx-1.5 text-neutral-400">›</span>
					<span className="text-sm text-neutral-500">Board</span>
				</nav>
				<Button variant="secondary" onClick={() => newIssue.open(team.id)}>
					New Issue
				</Button>
			</div>

			<div className="flex-1 overflow-x-auto p-4">
				{loading ? (
					<BoardSkeleton />
				) : loadError ? (
					<CenteredMessage>
						<h1 className="text-lg font-semibold">Could not load the Board</h1>
						<p className="mt-2 text-sm text-neutral-500">
							{loadFailure instanceof Error
								? loadFailure.message
								: "Unknown error"}
						</p>
						<div className="mt-4 flex justify-center">
							<Button
								onClick={() => {
									void statesQuery.refetch();
									void issuesQuery.refetch();
								}}
							>
								Retry
							</Button>
						</div>
					</CenteredMessage>
				) : (issuesQuery.data ?? []).length === 0 ? (
					<CenteredMessage>
						<h1 className="text-lg font-semibold">No Issues yet</h1>
						<p className="mt-2 text-sm text-neutral-500">
							Press{" "}
							<kbd className="rounded border border-neutral-300 px-1.5 py-0.5 font-mono text-xs dark:border-neutral-700">
								C
							</kbd>{" "}
							to create the first one.
						</p>
					</CenteredMessage>
				) : (
					<Board
						teamKey={team.key}
						teamId={team.id}
						states={statesQuery.data ?? []}
						issues={issuesQuery.data ?? []}
					/>
				)}
			</div>
		</div>
	);
}

function BoardSkeleton() {
	return (
		<div className="flex gap-3 p-4">
			<Skeleton className="h-64 w-72" />
			<Skeleton className="h-64 w-72" />
			<Skeleton className="h-64 w-72" />
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
