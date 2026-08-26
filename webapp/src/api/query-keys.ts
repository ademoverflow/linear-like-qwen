/** Central query-key factory (TanStack Query). */
export const queryKeys = {
	auth: {
		status: () => ["auth", "status"] as const,
		me: () => ["auth", "me"] as const,
	},
	teams: {
		all: () => ["teams"] as const,
		detail: (teamId: string) => ["teams", "detail", teamId] as const,
		candidates: (teamId: string) => ["teams", "candidates", teamId] as const,
		members: (teamId: string) => ["teams", "members", teamId] as const,
		states: (teamId: string) => ["teams", "states", teamId] as const,
		labels: (teamId: string) => ["teams", "labels", teamId] as const,
	},
	issues: {
		team: (teamId: string) => ["issues", "team", teamId] as const,
		page: (teamId: string, filters: string) =>
			["issues", "page", teamId, filters] as const,
		// Cross-Team My Issues page (ticket 09).
		myPage: (sort: string) => ["issues", "my", sort] as const,
		detail: (issueId: string) => ["issues", "detail", issueId] as const,
		activity: (issueId: string) => ["issues", "activity", issueId] as const,
		comments: (issueId: string) => ["issues", "comments", issueId] as const,
	},
	admin: {
		users: () => ["admin", "users"] as const,
		invitations: () => ["admin", "invitations"] as const,
	},
};
