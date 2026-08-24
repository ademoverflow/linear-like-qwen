import { z } from "zod";

import { api } from "./client";

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

export async function listIssues(teamId: string): Promise<Issue[]> {
	const data = await api.get("/issues", { query: { team_id: teamId } });
	return z.array(issueSchema).parse(data);
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
