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
	updated_at: z.coerce.date(),
});

export type Issue = z.infer<typeof issueSchema>;

export async function listIssues(teamId: string): Promise<Issue[]> {
	const data = await api.get("/issues", { query: { team_id: teamId } });
	return z.array(issueSchema).parse(data);
}

export async function createIssue(input: {
	team_id: string;
	title: string;
}): Promise<Issue> {
	const data = await api.post("/issues", input);
	return issueSchema.parse(data);
}
