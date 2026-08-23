import { useQuery } from "@tanstack/react-query";
import { getMe, queryKeys } from "@/api/auth";

/** The authenticated user (profile, admin flag, team memberships). */
export function useCurrentUser() {
	return useQuery({
		queryKey: queryKeys.auth.me(),
		queryFn: getMe,
	});
}
