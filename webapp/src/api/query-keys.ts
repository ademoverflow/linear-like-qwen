/** Central query-key factory (TanStack Query). */
export const queryKeys = {
	auth: {
		status: () => ["auth", "status"] as const,
		me: () => ["auth", "me"] as const,
	},
	teams: {
		all: () => ["teams"] as const,
	},
	issues: {
		team: (teamId: string) => ["issues", "team", teamId] as const,
	},
	admin: {
		users: () => ["admin", "users"] as const,
		invitations: () => ["admin", "invitations"] as const,
	},
};
