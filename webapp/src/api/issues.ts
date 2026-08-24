import { z } from "zod";

import { api } from "./client";
import { labelSchema } from "./teams";

/** A Label attached to an Issue (embedded, no Team/timestamps). */
export const issueLabelSchema = labelSchema.pick({
	id: true,
	name: true,
	color: true,
});

export type IssueLabel = z.infer<typeof issueLabelSchema>;

export const issueSchema = z.object({
	id: z.string().uuid(),
	team_id: z.string().uuid(),
	number: z.number().int(),
	identifier: z.string(),
	title: z.string(),
	description: z.string().nullish(),
	state_id: z.string().uuid(),
	state_name: z.string(),
	state_category: z.enum([
		"backlog",
		"unstarted",
		"started",
		"completed",
		"canceled",
	]),
	state_color: z.string(),
	priority: z.enum(["none", "urgent", "high", "medium", "low"]),
	assignee_id: z.string().uuid().nullish(),
	assignee_display_name: z.string().nullish(),
	assignee_avatar_url: z.string().nullish(),
	creator_id: z.string().uuid(),
	parent_id: z.string().uuid().nullish(),
	due_date: z.coerce.date().nullish(),
	estimate: z.number().int().nullish(),
	completed_at: z.coerce.date().nullish(),
	canceled_at: z.coerce.date().nullish(),
	archived_at: z.coerce.date().nullish(),
	created_at: z.coerce.date(),
	labels: z.array(issueLabelSchema),
	// Raw server string on purpose: PATCH must echo the exact timestamptz
	// value (ADR 0008) and a JS Date would truncate microseconds.
	updated_at: z.string(),
});

export type Issue = z.infer<typeof issueSchema>;

export const issueDetailSchema = issueSchema.extend({
	parent_identifier: z.string().nullish(),
	parent_title: z.string().nullish(),
});

export type IssueDetail = z.infer<typeof issueDetailSchema>;

export const activitySchema = z.object({
	id: z.string().uuid(),
	actor_id: z.string().uuid().nullish(),
	actor_display_name: z.string().nullish(),
	kind: z.string(),
	field: z.string().nullish(),
	from_value: z.string().nullish(),
	to_value: z.string().nullish(),
	created_at: z.coerce.date(),
});

export type Activity = z.infer<typeof activitySchema>;

export interface IssueListParams {
	state_ids?: string[];
	assignee_ids?: string[];
	label_ids?: string[];
	priority?: string[];
	sort?: string;
	limit?: number;
	cursor?: string;
}

export const issueListSchema = z.object({
	issues: z.array(issueSchema),
	next_cursor: z.string().nullish(),
});

export type IssueListPage = z.infer<typeof issueListSchema>;

export async function listIssues(
	teamId: string,
	params: IssueListParams = {},
): Promise<IssueListPage> {
	const query: Record<string, string | number | string[]> = {
		team_id: teamId,
	};
	if (params.state_ids?.length) query.state_id = params.state_ids;
	if (params.assignee_ids?.length) query.assignee_id = params.assignee_ids;
	if (params.label_ids?.length) query.label_id = params.label_ids;
	if (params.priority?.length) query.priority = params.priority;
	if (params.sort) query.sort = params.sort;
	if (params.limit) query.limit = params.limit;
	if (params.cursor) query.cursor = params.cursor;
	const data = await api.get("/issues", { query });
	return issueListSchema.parse(data);
}

/**
 * Fetch a Team's full Issue set by paging through the list endpoint
 * (limit 200 per page) until there is no next cursor. Used by the Board
 * and the Issue-detail sidebar, which need every Issue at once.
 */
export async function listAllIssues(teamId: string): Promise<Issue[]> {
	const issues: Issue[] = [];
	let cursor: string | null = null;
	for (;;) {
		const page = await listIssues(teamId, {
			limit: 200,
			cursor: cursor ?? undefined,
		});
		issues.push(...page.issues);
		cursor = page.next_cursor ?? null;
		if (!cursor) break;
	}
	return issues;
}

export async function getIssue(issueId: string): Promise<IssueDetail> {
	const data = await api.get(`/issues/${issueId}`);
	return issueDetailSchema.parse(data);
}

export interface IssueUpdateInput {
	updated_at: string;
	title?: string | null;
	description?: string | null;
	priority?: Issue["priority"] | null;
	assignee_id?: string | null;
	parent_id?: string | null;
	due_date?: string | null;
	estimate?: number | null;
	label_ids?: string[];
}

export async function updateIssue(
	issueId: string,
	input: IssueUpdateInput,
): Promise<Issue> {
	const data = await api.patch(`/issues/${issueId}`, input);
	return issueSchema.parse(data);
}

export interface IssueTransitionInput {
	state_id: string;
	// Raw server string on purpose: the transition must echo the exact
	// timestamptz value (ADR 0008) and a JS Date would truncate microseconds.
	updated_at: string;
}

export async function transitionIssue(
	issueId: string,
	input: IssueTransitionInput,
): Promise<Issue> {
	const data = await api.post(`/issues/${issueId}/transitions`, input);
	return issueSchema.parse(data);
}

export async function listIssueActivity(issueId: string): Promise<Activity[]> {
	const data = await api.get(`/issues/${issueId}/activity`);
	return z.array(activitySchema).parse(data);
}
export async function createIssue(input: {
	team_id: string;
	title: string;
}): Promise<Issue> {
	const data = await api.post("/issues", input);
	return issueSchema.parse(data);
}

export interface IssueBulkInput {
	issue_ids: string[];
	state_id?: string | null;
	assignee_id?: string | null;
	archive?: boolean;
}

export const issueBulkResponseSchema = z.object({
	issues: z.array(issueSchema),
});

export async function bulkUpdateIssues(
	input: IssueBulkInput,
): Promise<Issue[]> {
	const data = await api.post("/issues/bulk", input);
	return issueBulkResponseSchema.parse(data).issues;
}
