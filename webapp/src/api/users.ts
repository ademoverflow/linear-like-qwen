import { z } from "zod";

import { api } from "./client";
import { queryKeys } from "./query-keys";

export const userSchema = z.object({
	id: z.string().uuid(),
	email: z.string(),
	display_name: z.string().nullish(),
	avatar_url: z.string().nullish(),
	is_admin: z.boolean(),
	is_active: z.boolean(),
	created_at: z.coerce.date(),
});

export type User = z.infer<typeof userSchema>;

export async function listUsers(): Promise<User[]> {
	const data = await api.get("/users");
	return z.array(userSchema).parse(data);
}

export type UserAction = "deactivate" | "reactivate" | "promote" | "demote";

async function manageUser(userId: string, action: UserAction): Promise<User> {
	const data = await api.post(`/users/${userId}/${action}`);
	return userSchema.parse(data);
}

export function deactivateUser(userId: string): Promise<User> {
	return manageUser(userId, "deactivate");
}

export function reactivateUser(userId: string): Promise<User> {
	return manageUser(userId, "reactivate");
}

export function promoteUser(userId: string): Promise<User> {
	return manageUser(userId, "promote");
}

export function demoteUser(userId: string): Promise<User> {
	return manageUser(userId, "demote");
}

export { queryKeys };
