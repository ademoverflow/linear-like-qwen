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

export async function listTeams(): Promise<Team[]> {
	const data = await api.get("/teams");
	return z.array(teamSchema).parse(data);
}

export async function createTeam(input: {
	name: string;
	key: string;
	description?: string;
}): Promise<Team> {
	const data = await api.post("/teams", input);
	return teamSchema.parse(data);
}
