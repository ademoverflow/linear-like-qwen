import { z } from "zod";

import { api } from "./client";
import { queryKeys } from "./query-keys";

export const membershipSchema = z.object({
	team_id: z.string().uuid(),
	team_key: z.string(),
	team_name: z.string(),
	role: z.enum(["owner", "member"]),
});

export const themeSchema = z.enum(["system", "light", "dark"]);

export type Theme = z.infer<typeof themeSchema>;

export const meSchema = z.object({
	id: z.string().uuid(),
	email: z.string(),
	display_name: z.string().nullish(),
	avatar_url: z.string().nullish(),
	theme: themeSchema,
	is_admin: z.boolean(),
	is_active: z.boolean(),
	created_at: z.coerce.date(),
	memberships: z.array(membershipSchema),
});

export const authStatusSchema = z.object({
	bootstrap_open: z.boolean(),
});

export type Me = z.infer<typeof meSchema>;
export type AuthStatus = z.infer<typeof authStatusSchema>;

export async function getMe(): Promise<Me> {
	const data = await api.get("/auth/me");
	return meSchema.parse(data);
}

export async function getAuthStatus(): Promise<AuthStatus> {
	const data = await api.get("/auth/status");
	return authStatusSchema.parse(data);
}

export async function register(input: {
	email: string;
	password: string;
	token?: string;
}): Promise<Me> {
	const data = await api.post("/auth/register", input);
	return meSchema.parse(data);
}

export async function login(input: {
	email: string;
	password: string;
}): Promise<Me> {
	const data = await api.post("/auth/login", input);
	return meSchema.parse(data);
}

export async function logout(): Promise<void> {
	await api.post("/auth/logout");
}

/** Partial profile update (brief §9); the response is the updated me. */
export async function updateMe(input: {
	display_name?: string | null;
	avatar_url?: string | null;
	theme?: Theme;
}): Promise<Me> {
	const data = await api.patch("/auth/me", input);
	return meSchema.parse(data);
}

export { queryKeys };
