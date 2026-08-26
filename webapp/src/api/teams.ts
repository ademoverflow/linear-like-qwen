import { z } from "zod";

import { api } from "./client";

export const teamSchema = z.object({
	id: z.string().uuid(),
	name: z.string(),
	key: z.string(),
	description: z.string().nullish(),
	archived_at: z.coerce.date().nullish(),
	created_at: z.coerce.date(),
	updated_at: z.coerce.date(),
});

export type Team = z.infer<typeof teamSchema>;

export const teamMemberSchema = z.object({
	id: z.string().uuid(),
	display_name: z.string(),
	avatar_url: z.string().nullish(),
	role: z.enum(["owner", "member"]),
});

export type TeamMember = z.infer<typeof teamMemberSchema>;

export const workflowStateSchema = z.object({
	id: z.string().uuid(),
	name: z.string(),
	category: z.enum([
		"backlog",
		"unstarted",
		"started",
		"completed",
		"canceled",
	]),
	color: z.string(),
	position: z.number().int(),
	version: z.number().int(),
});

export type WorkflowState = z.infer<typeof workflowStateSchema>;

export async function listTeams(): Promise<Team[]> {
	const data = await api.get("/teams");
	return z.array(teamSchema).parse(data);
}

export async function listTeamMembers(teamId: string): Promise<TeamMember[]> {
	const data = await api.get(`/teams/${teamId}/members`);
	return z.array(teamMemberSchema).parse(data);
}
export async function listTeamStates(teamId: string): Promise<WorkflowState[]> {
	const data = await api.get(`/teams/${teamId}/states`);
	return z.array(workflowStateSchema).parse(data);
}

export async function createTeam(input: {
	name: string;
	key: string;
	description?: string;
}): Promise<Team> {
	const data = await api.post("/teams", input);
	return teamSchema.parse(data);
}

/** A Team-scoped Label (brief §2; owner-managed, ticket 05). */
export const labelSchema = z.object({
	id: z.string().uuid(),
	team_id: z.string().uuid(),
	name: z.string(),
	color: z.string(),
	created_at: z.coerce.date(),
	updated_at: z.coerce.date(),
});

export type Label = z.infer<typeof labelSchema>;

export async function listTeamLabels(teamId: string): Promise<Label[]> {
	const data = await api.get(`/teams/${teamId}/labels`);
	return z.array(labelSchema).parse(data);
}

export async function createTeamLabel(
	teamId: string,
	input: { name: string; color: string },
): Promise<Label> {
	const data = await api.post(`/teams/${teamId}/labels`, input);
	return labelSchema.parse(data);
}

export async function updateTeamLabel(
	teamId: string,
	labelId: string,
	input: { name?: string; color?: string },
): Promise<Label> {
	const data = await api.patch(`/teams/${teamId}/labels/${labelId}`, input);
	return labelSchema.parse(data);
}

export async function deleteTeamLabel(
	teamId: string,
	labelId: string,
): Promise<void> {
	await api.delete(`/teams/${teamId}/labels/${labelId}`);
}

/** A User who can be added to the Team (the members-tab picker, ticket 08). */
export const teamMemberCandidateSchema = z.object({
	id: z.string().uuid(),
	display_name: z.string(),
	email: z.string(),
	avatar_url: z.string().nullish(),
});

export type TeamMemberCandidate = z.infer<typeof teamMemberCandidateSchema>;

export async function getTeam(teamId: string): Promise<Team> {
	const data = await api.get(`/teams/${teamId}`);
	return teamSchema.parse(data);
}

export async function updateTeam(
	teamId: string,
	input: { name?: string; description?: string | null },
): Promise<Team> {
	const data = await api.patch(`/teams/${teamId}`, input);
	return teamSchema.parse(data);
}

export async function archiveTeam(teamId: string): Promise<Team> {
	const data = await api.post(`/teams/${teamId}/archive`);
	return teamSchema.parse(data);
}

export async function restoreTeam(teamId: string): Promise<Team> {
	const data = await api.post(`/teams/${teamId}/restore`);
	return teamSchema.parse(data);
}

export async function listTeamMemberCandidates(
	teamId: string,
): Promise<TeamMemberCandidate[]> {
	const data = await api.get(`/teams/${teamId}/member-candidates`);
	return z.array(teamMemberCandidateSchema).parse(data);
}

export async function addTeamMember(
	teamId: string,
	userId: string,
): Promise<TeamMember> {
	const data = await api.post(`/teams/${teamId}/members`, { user_id: userId });
	return teamMemberSchema.parse(data);
}

export async function updateTeamMemberRole(
	teamId: string,
	userId: string,
	role: "owner" | "member",
): Promise<TeamMember> {
	const data = await api.patch(`/teams/${teamId}/members/${userId}`, { role });
	return teamMemberSchema.parse(data);
}

export async function removeTeamMember(
	teamId: string,
	userId: string,
): Promise<void> {
	await api.delete(`/teams/${teamId}/members/${userId}`);
}

export async function createTeamState(
	teamId: string,
	input: { name: string; category: string; color: string },
): Promise<WorkflowState> {
	const data = await api.post(`/teams/${teamId}/states`, input);
	return workflowStateSchema.parse(data);
}

export async function updateTeamState(
	teamId: string,
	stateId: string,
	input: {
		version: number;
		name?: string;
		color?: string;
		category?: string;
	},
): Promise<WorkflowState> {
	const data = await api.patch(`/teams/${teamId}/states/${stateId}`, input);
	return workflowStateSchema.parse(data);
}

export async function reorderTeamStates(
	teamId: string,
	states: { id: string; version: number }[],
): Promise<WorkflowState[]> {
	const data = await api.patch(`/teams/${teamId}/states/reorder`, { states });
	return z.array(workflowStateSchema).parse(data);
}

export async function deleteTeamState(
	teamId: string,
	stateId: string,
	input: { version: number; migrate_to_state_id?: string },
): Promise<void> {
	await api.delete(`/teams/${teamId}/states/${stateId}`, { body: input });
}
