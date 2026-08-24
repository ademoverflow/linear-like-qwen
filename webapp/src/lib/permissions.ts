import type { Me } from "@/api/auth";

/**
 * Owner or workspace Admin for a Team (brief §5.2). Computed client-side
 * from `/auth/me`, as ADR 0004 sanctions for action visibility.
 */
export function isOwnerOrAdmin(
	me: Me | null | undefined,
	teamId: string | null | undefined,
): boolean {
	if (me?.is_admin === true) return true;
	if (me == null || teamId == null) return false;
	return me.memberships.some(
		(membership) =>
			membership.team_id === teamId && membership.role === "owner",
	);
}
