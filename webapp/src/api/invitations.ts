import { z } from "zod";

import { api } from "./client";

export const invitationSchema = z.object({
	id: z.string().uuid(),
	email: z.string(),
	invited_by: z.string().uuid(),
	expires_at: z.coerce.date(),
	accepted_at: z.coerce.date().nullish(),
	created_at: z.coerce.date(),
});

export type Invitation = z.infer<typeof invitationSchema>;

/** The invite response: the raw token is revealed exactly once, here. */
export const invitationCreatedSchema = invitationSchema.extend({
	token: z.string(),
});

export type InvitationCreated = z.infer<typeof invitationCreatedSchema>;

export async function listInvitations(): Promise<Invitation[]> {
	const data = await api.get("/invitations");
	return z.array(invitationSchema).parse(data);
}

export async function createInvitation(
	email: string,
): Promise<InvitationCreated> {
	const data = await api.post("/invitations", { email });
	return invitationCreatedSchema.parse(data);
}
