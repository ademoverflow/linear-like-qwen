import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useCallback, useMemo, useState } from "react";
import {
	type IssueListPage,
	type IssueListParams,
	listIssues,
} from "@/api/issues";
import { queryKeys } from "@/api/query-keys";
import {
	listTeamLabels,
	listTeamMembers,
	listTeamStates,
	listTeams,
} from "@/api/teams";
import { IssueCard } from "@/components/issues/IssueCard";
import {
	EMPTY_ISSUE_FILTERS,
	IssueFilterDialog,
	type IssueListFilters,
	SORT_OPTIONS,
} from "@/components/issues/IssueFilterDialog";
import { IssueQuickActions } from "@/components/issues/IssueQuickActions";
import { LabelManagerDialog } from "@/components/issues/LabelManagerDialog";
import { StateDot } from "@/components/issues/StateDot";
import { useNewIssue } from "@/components/layout/new-issue-context";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { toast } from "@/components/ui/Toast";
import { useBulkIssues } from "@/hooks/use-bulk-issues";
import { useCurrentUser } from "@/hooks/use-current-user";
import { useIssueActions } from "@/hooks/use-issue-actions";
import {
	type QuickActionKind,
	useIssueListKeyboard,
} from "@/hooks/use-issue-list-keyboard";
import { useShortcut } from "@/hooks/use-shortcut";
import { useTransitionIssue } from "@/hooks/use-transition-issue";
import { useUpdateIssue } from "@/hooks/use-update-issue";
import { isOwnerOrAdmin } from "@/lib/permissions";
import { SELECT_CLASS } from "@/lib/styles";

const DEFAULT_SORT = "created:desc";
const PAGE_SIZE = 50;

function filtersToParams(
	filters: IssueListFilters,
	showArchived: boolean,
): IssueListParams {
	const params: IssueListParams = { limit: PAGE_SIZE };
	if (showArchived) params.include_archived = true;
	if (filters.stateIds.length > 0) params.state_ids = filters.stateIds;
	if (filters.assigneeIds.length > 0) params.assignee_ids = filters.assigneeIds;
	if (filters.labelIds.length > 0) params.label_ids = filters.labelIds;
	if (filters.priorities.length > 0) params.priority = filters.priorities;
	return params;
}

/**
 * Team Issues list (brief §7.2.2, ticket 05): toolbar with combinable
 * filters, sort and the owner-only Labels manager; the Issues are grouped
 * by Workflow State (position order, non-empty groups) and paged with a
 * cursor ("Load more"). Selection mode adds a bulk bar (State, Assignee
 * and owner-only Archive; all-or-nothing, non-optimistic). The "Archived"
 * toggle lists archived Issues alongside the active ones (ticket 07);
 * archived rows show a badge and a per-Row Restore for owners/Admins.
 */
export function TeamIssues() {
	// `from` matches by routeId; the pathless "app" layout prefixes child ids.
	const { teamKey } = useParams({ from: "/app/teams/$teamKey/issues" });
	const navigate = useNavigate();
	const newIssue = useNewIssue();
	const queryClient = useQueryClient();
	const bulk = useBulkIssues();

	const [filters, setFilters] = useState<IssueListFilters>(EMPTY_ISSUE_FILTERS);
	const [sort, setSort] = useState<string>(DEFAULT_SORT);
	const [filterOpen, setFilterOpen] = useState(false);
	const [labelsOpen, setLabelsOpen] = useState(false);
	const [selecting, setSelecting] = useState(false);
	const [quick, setQuick] = useState<QuickActionKind | null>(null);
	const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
	const [loadingMore, setLoadingMore] = useState(false);
	const [showArchived, setShowArchived] = useState(false);
	const issueActions = useIssueActions();

	const teamsQuery = useQuery({
		queryKey: queryKeys.teams.all(),
		queryFn: listTeams,
	});
	const team = teamsQuery.data?.find((item) => item.key === teamKey);
	const me = useCurrentUser().data;
	const isOwner = isOwnerOrAdmin(me, team?.id);

	const statesQuery = useQuery({
		queryKey: queryKeys.teams.states(team?.id ?? ""),
		queryFn: () => (team ? listTeamStates(team.id) : Promise.resolve([])),
		enabled: team !== undefined,
	});
	const membersQuery = useQuery({
		queryKey: queryKeys.teams.members(team?.id ?? ""),
		queryFn: () => (team ? listTeamMembers(team.id) : Promise.resolve([])),
		enabled: team !== undefined,
	});
	const labelsQuery = useQuery({
		queryKey: queryKeys.teams.labels(team?.id ?? ""),
		queryFn: () => (team ? listTeamLabels(team.id) : Promise.resolve([])),
		enabled: team !== undefined,
	});

	const filtersKey = JSON.stringify({ filters, sort, showArchived });
	const pageKey = queryKeys.issues.page(team?.id ?? "", filtersKey);
	const issuesQuery = useQuery({
		queryKey: pageKey,
		queryFn: (): Promise<IssueListPage> =>
			team
				? listIssues(team.id, {
						...filtersToParams(filters, showArchived),
						sort,
					})
				: Promise.resolve({ issues: [], next_cursor: null }),
		enabled: team !== undefined,
	});

	const issues = issuesQuery.data?.issues ?? [];
	const filterCount =
		filters.stateIds.length +
		filters.assigneeIds.length +
		filters.labelIds.length +
		filters.priorities.length;
	const hasFilters = filterCount > 0;

	const groups = useMemo(() => {
		const states = (statesQuery.data ?? [])
			.slice()
			.sort((a, b) => a.position - b.position);
		return states
			.map((state) => ({
				state,
				items: issues.filter((issue) => issue.state_id === state.id),
			}))
			.filter((group) => group.items.length > 0);
	}, [statesQuery.data, issues]);

	// The list keyboard set (ticket 09): a cursor over the flat display
	// order (State groups); bulk mode suspends it.
	const flatIssues = useMemo(
		() => groups.flatMap((group) => group.items),
		[groups],
	);
	const { cursorId, setCursorId } = useIssueListKeyboard({
		issueIds: flatIssues.map((issue) => issue.id),
		disabled: selecting || quick !== null,
		onOpen: (issueId) => {
			const issue = flatIssues.find((item) => item.id === issueId);
			if (issue) {
				navigate({
					to: "/teams/$teamKey/issues/$issueId",
					params: { teamKey, issueId: issue.id },
				});
			}
		},
		onQuickAction: setQuick,
	});
	useShortcut("Escape", () => {
		if (quick !== null) {
			setQuick(null);
		} else if (selecting) {
			setSelecting(false);
			setSelected(new Set());
		} else {
			setCursorId(null);
		}
	});

	const cursorIssue = flatIssues.find((issue) => issue.id === cursorId) ?? null;
	const transition = useTransitionIssue(team?.id ?? "");
	const update = useUpdateIssue(team?.id ?? "", cursorIssue?.id ?? "");

	const loadMore = useCallback(() => {
		const current = issuesQuery.data;
		if (!team || !current?.next_cursor || loadingMore) return;
		setLoadingMore(true);
		listIssues(team.id, {
			...filtersToParams(filters, showArchived),
			sort,
			cursor: current.next_cursor,
		})
			.then((next) => {
				queryClient.setQueryData<IssueListPage>(pageKey, (previous) =>
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
	}, [
		issuesQuery.data,
		team,
		filters,
		sort,
		showArchived,
		loadingMore,
		queryClient,
		pageKey,
	]);

	const toggleSelect = useCallback((issueId: string) => {
		setSelected((previous) => {
			const next = new Set(previous);
			if (next.has(issueId)) {
				next.delete(issueId);
			} else {
				next.add(issueId);
			}
			return next;
		});
	}, []);

	const selectedIds = useMemo(() => [...selected], [selected]);
	const runBulk = useCallback(
		(action: Omit<Parameters<typeof bulk.mutate>[0], "issue_ids">) => {
			bulk.mutate({ issue_ids: selectedIds, ...action });
		},
		[bulk, selectedIds],
	);

	if (teamsQuery.isLoading) {
		return <ListSkeleton />;
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
	if (team.archived_at != null) {
		return (
			<CenteredMessage>
				<h1 className="text-lg font-semibold">This Team is archived</h1>
				<p className="mt-2 text-sm text-muted">
					Its Issues are hidden from the list. A workspace Admin can restore the
					Team from the settings.
				</p>
				{isOwnerOrAdmin(me, team.id) && (
					<Link
						to="/teams/$teamKey/settings"
						params={{ teamKey: team.key }}
						className="mt-4 rounded-md px-3 py-1.5 text-sm text-accent underline-offset-2 hover:underline"
					>
						Open Team settings
					</Link>
				)}
			</CenteredMessage>
		);
	}

	return (
		<div className="flex h-full flex-col">
			<div className="sticky top-0 z-10 flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line bg-surface/90 px-4 py-2 backdrop-blur">
				<nav aria-label="Breadcrumb">
					<span className="text-sm font-semibold">{team.key}</span>
					<span className="mx-1.5 text-faint">›</span>
					<span className="text-sm text-muted">Issues</span>
				</nav>
				<div className="ml-auto flex flex-wrap items-center gap-2">
					<Button
						variant="secondary"
						aria-pressed={showArchived}
						className={showArchived ? "border-accent text-accent" : ""}
						onClick={() => setShowArchived((value) => !value)}
					>
						Archived
					</Button>
					<Button variant="secondary" onClick={() => setFilterOpen(true)}>
						Filter
						{hasFilters ? ` (${filterCount})` : ""}
					</Button>
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
					{isOwner && (
						<Button variant="secondary" onClick={() => setLabelsOpen(true)}>
							Labels
						</Button>
					)}
					{selecting && (
						<Button variant="secondary" onClick={() => setSelecting(false)}>
							Done
						</Button>
					)}
					{!selecting && (
						<Button
							variant="secondary"
							onClick={() => {
								setSelecting(true);
								setSelected(new Set());
							}}
						>
							Select
						</Button>
					)}
					<Button variant="secondary" onClick={() => newIssue.open(team.id)}>
						New Issue
					</Button>
				</div>
			</div>

			{filterOpen && (
				<IssueFilterDialog
					open
					onClose={() => setFilterOpen(false)}
					filters={filters}
					onFiltersChange={setFilters}
					states={statesQuery.data ?? []}
					members={membersQuery.data ?? []}
					labels={labelsQuery.data ?? []}
				/>
			)}
			{labelsOpen && (
				<LabelManagerDialog
					teamId={team.id}
					onClose={() => setLabelsOpen(false)}
				/>
			)}

			<div className="flex-1 overflow-y-auto">
				{issuesQuery.isLoading ? (
					<ListSkeleton />
				) : issuesQuery.isError ? (
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
				) : issues.length === 0 ? (
					<CenteredMessage>
						<h1 className="text-lg font-semibold">
							{hasFilters ? "No Issues match the filters" : "No Issues yet"}
						</h1>
						{hasFilters ? (
							<Button
								variant="secondary"
								className="mt-4"
								onClick={() => setFilters(EMPTY_ISSUE_FILTERS)}
							>
								Clear filters
							</Button>
						) : (
							<p className="mt-2 text-sm text-muted">
								Press{" "}
								<kbd className="rounded border border-neutral-300 px-1.5 py-0.5 font-mono text-xs dark:border-neutral-700">
									C
								</kbd>{" "}
								to create the first one.
							</p>
						)}
					</CenteredMessage>
				) : (
					<div className="mx-auto flex w-full max-w-2xl flex-col gap-4 p-4">
						{groups.map(({ state, items }) => (
							<section
								key={state.id}
								aria-label={`${state.name} Issues`}
								className="flex flex-col gap-2"
							>
								<div className="flex items-center gap-2">
									<StateDot color={state.color} category={state.category} />
									<span className="text-sm font-semibold">{state.name}</span>
									<span className="text-xs text-faint">{items.length}</span>
								</div>
								{items.map((issue) => (
									<IssueCard
										key={issue.id}
										issue={issue}
										teamKey={team.key}
										selectable={selecting}
										checked={selected.has(issue.id)}
										selected={cursorId === issue.id}
										onToggle={toggleSelect}
										onRestore={
											isOwner
												? (issueId: string) =>
														issueActions.restore.mutate(issueId)
												: undefined
										}
									/>
								))}
							</section>
						))}
						{issuesQuery.data?.next_cursor && (
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
						transition.mutate({
							issue_id: cursorIssue.id,
							state_id: stateId,
							updated_at: cursorIssue.updated_at,
						});
						setQuick(null);
					}}
					onAssigneeChange={(userId) => {
						update.mutate({
							updated_at: cursorIssue.updated_at,
							assignee_id: userId,
						});
						setQuick(null);
					}}
					onPriorityChange={(priority) => {
						update.mutate({
							updated_at: cursorIssue.updated_at,
							priority,
						});
						setQuick(null);
					}}
					onToggleLabel={(label, add) => {
						const labelIds = add
							? [...cursorIssue.labels.map((item) => item.id), label.id]
							: cursorIssue.labels
									.filter((item) => item.id !== label.id)
									.map((item) => item.id);
						update.mutate({
							updated_at: cursorIssue.updated_at,
							label_ids: labelIds,
						});
						setQuick(null);
					}}
				/>
			)}

			{selecting && selected.size > 0 && (
				<div className="fixed bottom-4 left-1/2 z-20 flex -translate-x-1/2 flex-wrap items-center gap-3 rounded-lg border border-line bg-surface px-4 py-2 shadow-lg">
					<span className="text-sm font-medium">{selected.size} selected</span>
					<select
						aria-label="Set state"
						value=""
						onChange={(event) => {
							if (event.target.value) runBulk({ state_id: event.target.value });
						}}
						className={SELECT_CLASS}
					>
						<option value="" disabled>
							Set State…
						</option>
						{(statesQuery.data ?? []).map((state) => (
							<option key={state.id} value={state.id}>
								{state.name}
							</option>
						))}
					</select>
					<select
						aria-label="Assign to"
						value=""
						onChange={(event) => {
							if (event.target.value)
								runBulk({ assignee_id: event.target.value });
						}}
						className={SELECT_CLASS}
					>
						<option value="" disabled>
							Assign to…
						</option>
						{(membersQuery.data ?? []).map((member) => (
							<option key={member.id} value={member.id}>
								{member.display_name}
							</option>
						))}
					</select>
					{isOwner && (
						<Button variant="ghost" onClick={() => runBulk({ archive: true })}>
							Archive
						</Button>
					)}
					<Button variant="ghost" onClick={() => setSelected(new Set())}>
						Clear
					</Button>
					<Button variant="ghost" onClick={() => setSelecting(false)}>
						Done
					</Button>
				</div>
			)}
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
