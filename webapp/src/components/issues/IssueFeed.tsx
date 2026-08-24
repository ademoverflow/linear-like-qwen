import { useQuery } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import type { Me } from "@/api/auth";
import type { Comment } from "@/api/comments";
import { listIssueComments } from "@/api/comments";
import type { Activity } from "@/api/issues";
import { listIssueActivity } from "@/api/issues";
import { queryKeys } from "@/api/query-keys";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { useComments } from "@/hooks/use-comments";
import { mergeFeed } from "@/lib/feed";
import { Markdown } from "@/lib/markdown";
import { MarkdownEditor } from "./MarkdownEditor";

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
	if (activity.kind === "comment.updated") return "edited their Comment";
	if (activity.kind === "comment.deleted") return "deleted a Comment";
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

/**
 * The Issue's story (brief §7.2.3, ticket 06): the Comments thread merged
 * chronologically with Activity, plus a comment composer at the bottom.
 * Comments are plain (non-optimistic) mutations; the feed refetches.
 */
export function IssueFeed({
	issueId,
	teamId,
	me,
}: {
	issueId: string;
	teamId: string;
	me: Me | null;
}) {
	const commentsQuery = useQuery({
		queryKey: queryKeys.issues.comments(issueId),
		queryFn: () => listIssueComments(issueId),
	});
	const activityQuery = useQuery({
		queryKey: queryKeys.issues.activity(issueId),
		queryFn: () => listIssueActivity(issueId),
	});
	const { create, update, remove } = useComments(issueId);

	const isTeamOwner =
		me?.memberships.find((membership) => membership.team_id === teamId)
			?.role === "owner";

	const canDelete = (comment: Comment) =>
		(me?.is_admin ?? false) || isTeamOwner || me?.id === comment.author_id;

	const isLoading = commentsQuery.isLoading || activityQuery.isLoading;
	const error = commentsQuery.error ?? activityQuery.error;
	const entries = mergeFeed(activityQuery.data ?? [], commentsQuery.data ?? []);

	return (
		<section aria-label="Story" className="flex flex-col gap-3">
			<h2 className="text-sm font-semibold">Story</h2>
			{isLoading ? (
				<div className="flex flex-col gap-2">
					<Skeleton className="h-4 w-2/3" />
					<Skeleton className="h-4 w-1/2" />
				</div>
			) : error ? (
				<p className="text-sm text-neutral-500">
					{error instanceof Error ? error.message : "Unknown error"}
				</p>
			) : entries.length === 0 ? (
				<p className="text-sm text-neutral-500">Nothing here yet.</p>
			) : (
				<ul className="flex flex-col gap-3">
					{entries.map((entry) =>
						entry.type === "comment" ? (
							<li key={entry.comment.id}>
								<CommentCard
									comment={entry.comment}
									isAuthor={me?.id === entry.comment.author_id}
									canDelete={canDelete(entry.comment)}
									onSave={(body) =>
										update.mutate({
											commentId: entry.comment.id,
											body,
										})
									}
									onDelete={() => remove.mutate(entry.comment.id)}
								/>
							</li>
						) : (
							<li
								key={entry.activity.id}
								className="flex items-baseline gap-2 text-sm"
							>
								<span className="shrink-0 font-medium">
									{entry.activity.actor_display_name ?? "Someone"}
								</span>
								<span className="min-w-0 flex-1 break-words text-neutral-600 dark:text-neutral-400">
									{describeChange(entry.activity)}
								</span>
								<time
									className="shrink-0 text-xs text-neutral-400"
									dateTime={entry.activity.created_at.toISOString()}
								>
									{entry.activity.created_at.toLocaleString()}
								</time>
							</li>
						),
					)}
				</ul>
			)}
			<CommentComposer
				onPost={(body) => create.mutate(body)}
				disabled={create.isPending}
			/>
		</section>
	);
}

/**
 * A Comment in the story: author, timestamp, rendered Markdown body (ADR
 * 0007), an "edited" marker, and — for the author / a Team owner / an Admin —
 * inline edit and two-step delete.
 */
function CommentCard({
	comment,
	isAuthor,
	canDelete,
	onSave,
	onDelete,
}: {
	comment: Comment;
	isAuthor: boolean;
	canDelete: boolean;
	onSave: (body: string) => void;
	onDelete: () => void;
}) {
	const [editing, setEditing] = useState(false);
	const [confirmDelete, setConfirmDelete] = useState(false);

	useEffect(() => {
		if (!confirmDelete) return;
		const timer = setTimeout(() => setConfirmDelete(false), 3000);
		return () => clearTimeout(timer);
	}, [confirmDelete]);

	return (
		<article className="flex flex-col gap-2 rounded-md border border-neutral-200 p-3 dark:border-neutral-800">
			<div className="flex flex-wrap items-center gap-2">
				<span className="text-sm font-medium">
					{comment.author_display_name ?? "Someone"}
				</span>
				<time
					className="text-xs text-neutral-400"
					dateTime={comment.created_at.toISOString()}
				>
					{comment.created_at.toLocaleString()}
				</time>
				{comment.edited_at ? (
					<span className="text-xs text-neutral-400">edited</span>
				) : null}
				<span className="flex-1" />
				{isAuthor ? (
					<Button
						variant="ghost"
						aria-label="Edit comment"
						onClick={() => setEditing(true)}
					>
						<Pencil size={14} aria-hidden />
						Edit
					</Button>
				) : null}
				{canDelete ? (
					<Button
						variant="ghost"
						aria-label="Delete comment"
						onClick={() => {
							if (confirmDelete) {
								setConfirmDelete(false);
								onDelete();
							} else {
								setConfirmDelete(true);
							}
						}}
					>
						<Trash2 size={14} aria-hidden />
						{confirmDelete ? "Confirm?" : "Delete"}
					</Button>
				) : null}
			</div>
			{editing ? (
				<MarkdownEditor
					initial={comment.body}
					ariaLabel="Comment body"
					rows={4}
					maxLength={20_000}
					disableEmpty
					onSave={(body) => {
						setEditing(false);
						onSave(body);
					}}
					onCancel={() => setEditing(false)}
				/>
			) : (
				<Markdown content={comment.body} />
			)}
		</article>
	);
}

/** The comment composer at the bottom of the story (GFM, sanitised on render). */
function CommentComposer({
	onPost,
	disabled,
}: {
	onPost: (body: string) => void;
	disabled: boolean;
}) {
	// Remounting the editor (key) resets its draft after each post.
	const [postCount, setPostCount] = useState(0);

	const post = (body: string) => {
		onPost(body);
		setPostCount((count) => count + 1);
	};

	return (
		<MarkdownEditor
			key={postCount}
			initial=""
			ariaLabel="Write a comment"
			rows={3}
			placeholder="Write a comment…"
			maxLength={20_000}
			saveLabel="Comment"
			saveDisabled={disabled}
			disableEmpty
			actionAlign="end"
			onSave={post}
		/>
	);
}
