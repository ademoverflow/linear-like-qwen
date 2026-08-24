import { useQuery } from "@tanstack/react-query";
import { type Activity, listIssueActivity } from "@/api/issues";
import { queryKeys } from "@/api/query-keys";
import { Skeleton } from "@/components/ui/Skeleton";

const FIELD_LABELS: Record<string, string> = {
	title: "Title",
	description: "Description",
	priority: "Priority",
	assignee_id: "Assignee",
	parent_id: "Parent",
	due_date: "Due date",
	estimate: "Estimate",
};

function truncate(value: string, max = 120): string {
	return value.length > max ? `${value.slice(0, max)}…` : value;
}

function describeChange(activity: Activity): string {
	const from = activity.from_value ?? null;
	const to = activity.to_value ?? null;
	if (activity.kind === "issue.created") return "created this Issue";
	const label =
		FIELD_LABELS[activity.field ?? ""] ?? activity.field ?? "the Issue";
	if (from !== null && to !== null) {
		return `changed ${label} from ${truncate(from)} to ${truncate(to)}`;
	}
	if (to !== null) {
		return `changed ${label} to ${truncate(to)}`;
	}
	if (from !== null) {
		return `cleared ${label} (was ${truncate(from)})`;
	}
	return `changed ${label}`;
}

/** The Issue's Activity feed, chronological (oldest first; ticket 03). */
export function ActivityFeed({ issueId }: { issueId: string }) {
	const { data, isLoading, isError, error } = useQuery({
		queryKey: queryKeys.issues.activity(issueId),
		queryFn: () => listIssueActivity(issueId),
	});

	if (isLoading) {
		return (
			<div className="flex flex-col gap-2">
				<Skeleton className="h-4 w-2/3" />
				<Skeleton className="h-4 w-1/2" />
			</div>
		);
	}
	if (isError) {
		return (
			<p className="text-sm text-neutral-500">
				{error instanceof Error ? error.message : "Unknown error"}
			</p>
		);
	}
	if (!data || data.length === 0) {
		return <p className="text-sm text-neutral-500">No Activity yet.</p>;
	}
	return (
		<ul className="flex flex-col gap-2">
			{data.map((activity) => (
				<li key={activity.id} className="flex items-baseline gap-2 text-sm">
					<span className="shrink-0 font-medium">
						{activity.actor_display_name ?? "Someone"}
					</span>
					<span className="min-w-0 flex-1 break-words text-neutral-600 dark:text-neutral-400">
						{describeChange(activity)}
					</span>
					<time
						className="shrink-0 text-xs text-neutral-400"
						dateTime={activity.created_at.toISOString()}
					>
						{activity.created_at.toLocaleString()}
					</time>
				</li>
			))}
		</ul>
	);
}
