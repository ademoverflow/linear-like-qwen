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

export async function listTeams(): Promise<Team[]> {
	const data = await api.get("/teams");
	return z.array(teamSchema).parse(data);
}

export async function listTeamMembers(teamId: string): Promise<TeamMember[]> {
	const data = await api.get(`/teams/${teamId}/members`);
	return z.array(teamMemberSchema).parse(data);
}
export async function createTeam(input: {
	name: string;
	key: string;
	description?: string;
}): Promise<Team> {
	const data = await api.post("/teams", input);
	return teamSchema.parse(data);
}
