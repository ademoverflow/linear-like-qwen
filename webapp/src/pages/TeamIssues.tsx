import { useQuery } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import { listIssues } from "@/api/issues";
import { queryKeys } from "@/api/query-keys";
import { listTeams } from "@/api/teams";
import { IssueCard } from "@/components/issues/IssueCard";
import { useNewIssue } from "@/components/layout/new-issue-context";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";

/**
 * Team Issues list (brief §7.2.2, prototype variant B): breadcrumb, New
 * Issue button, card stack with skeleton / error / empty states.
 */
export function TeamIssues() {
	// `from` matches by routeId; the pathless "app" layout prefixes child ids.
	const { teamKey } = useParams({ from: "/app/teams/$teamKey/issues" });
	const newIssue = useNewIssue();

	const teamsQuery = useQuery({
		queryKey: queryKeys.teams.all(),
		queryFn: listTeams,
	});
	const team = teamsQuery.data?.find((item) => item.key === teamKey);

	const issuesQuery = useQuery({
		queryKey: queryKeys.issues.team(team?.id ?? ""),
		queryFn: () => (team ? listIssues(team.id) : Promise.resolve([])),
		enabled: team !== undefined,
	});

	if (teamsQuery.isLoading) {
		return <ListSkeleton />;
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

	return (
		<div className="flex h-full flex-col">
			<div className="sticky top-0 z-10 flex items-center justify-between border-b border-neutral-200 bg-white/90 px-4 py-2 backdrop-blur dark:border-neutral-800 dark:bg-neutral-900/90">
				<nav aria-label="Breadcrumb">
					<span className="text-sm font-semibold">{team.key}</span>
					<span className="mx-1.5 text-neutral-400">›</span>
					<span className="text-sm text-neutral-500">Issues</span>
				</nav>
				<Button variant="secondary" onClick={() => newIssue.open(team.id)}>
					New Issue
				</Button>
			</div>

			<div className="flex-1 p-4">
				{issuesQuery.isLoading ? (
					<ListSkeleton />
				) : issuesQuery.isError ? (
					<CenteredMessage>
						<h1 className="text-lg font-semibold">Could not load Issues</h1>
						<p className="mt-2 text-sm text-neutral-500">
							{issuesQuery.error instanceof Error
								? issuesQuery.error.message
								: "Unknown error"}
						</p>
						<div className="mt-4 flex justify-center">
							<Button onClick={() => issuesQuery.refetch()}>Retry</Button>
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
					<div className="flex max-w-2xl flex-col gap-2">
						{(issuesQuery.data ?? []).map((issue) => (
							<IssueCard key={issue.id} issue={issue} teamKey={team.key} />
						))}
					</div>
				)}
			</div>
		</div>
	);
}

function ListSkeleton() {
	return (
		<div className="flex max-w-2xl flex-col gap-2 p-4">
			<Skeleton className="h-[72px] w-full" />
			<Skeleton className="h-[72px] w-full" />
			<Skeleton className="h-[72px] w-full" />
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
