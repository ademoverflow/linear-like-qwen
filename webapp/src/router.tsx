import type { QueryClient } from "@tanstack/react-query";
import {
	createRootRoute,
	createRoute,
	createRouter,
	Outlet,
	type RouterHistory,
	redirect,
} from "@tanstack/react-router";
import { getMe, queryKeys } from "@/api/auth";
import { ApiError } from "@/api/client";
import { listTeams } from "@/api/teams";
import { AppShell } from "@/components/layout/AppShell";
import { Home } from "@/pages/Home";
import { Login } from "@/pages/Login";
import { Register } from "@/pages/Register";
import { TeamIssues } from "@/pages/TeamIssues";

export type AppRouterContext = { queryClient: QueryClient };

/**
 * Code-based routes type `beforeLoad`'s context as `{}` until the router is
 * registered (circular), so unwrap it here.
 */
function queryClientOf(context: unknown): QueryClient {
	return (context as { queryClient: QueryClient }).queryClient;
}

/**
 * Auth guard for the public screens: an already-authenticated user is
 * redirected to the app; 401 (or a transient failure) stays on the screen.
 */
async function authRedirectIfAuthenticated(queryClient: QueryClient) {
	try {
		await queryClient.ensureQueryData({
			queryKey: queryKeys.auth.me(),
			queryFn: getMe,
		});
	} catch {
		return;
	}
	throw redirect({ to: "/" });
}

/**
 * The route tree. `createRoute`/`addChildren` mutate the route objects, so
 * a fresh tree is built per router instance (tests render many).
 */
function buildRouteTree() {
	const rootRoute = createRootRoute({
		component: () => <Outlet />,
	});

	const loginRoute = createRoute({
		getParentRoute: () => rootRoute,
		path: "/login",
		component: Login,
		beforeLoad: async ({ context }) => {
			await authRedirectIfAuthenticated(queryClientOf(context));
		},
	});

	const registerRoute = createRoute({
		getParentRoute: () => rootRoute,
		path: "/register",
		component: Register,
		beforeLoad: async ({ context }) => {
			await authRedirectIfAuthenticated(queryClientOf(context));
		},
	});

	// Authenticated area: 401 from /auth/me redirects to /login; other
	// errors are left to the shell (it can show them and retry). The layout
	// is pathless (id only) so its index child can keep the "/" path.
	const appRoute = createRoute({
		getParentRoute: () => rootRoute,
		id: "app",
		component: AppShell,
		beforeLoad: async ({ context }) => {
			try {
				await queryClientOf(context).ensureQueryData({
					queryKey: queryKeys.auth.me(),
					queryFn: getMe,
				});
			} catch (error) {
				if (error instanceof ApiError && error.status === 401) {
					throw redirect({ to: "/login" });
				}
			}
		},
	});

	// Index: a user with Teams lands on their first Team's Issues; without
	// Teams they see the Home empty state.
	const homeRoute = createRoute({
		getParentRoute: () => appRoute,
		path: "/",
		component: Home,
		beforeLoad: async ({ context }) => {
			const teams = await queryClientOf(context).ensureQueryData({
				queryKey: queryKeys.teams.all(),
				queryFn: listTeams,
			});
			if (teams.length > 0) {
				throw redirect({
					to: "/teams/$teamKey/issues",
					params: { teamKey: teams[0].key },
				});
			}
		},
	});

	const teamIssuesRoute = createRoute({
		getParentRoute: () => appRoute,
		path: "/teams/$teamKey/issues",
		component: TeamIssues,
	});

	return rootRoute.addChildren([
		loginRoute,
		registerRoute,
		appRoute.addChildren([homeRoute, teamIssuesRoute]),
	]);
}

export function createAppRouter(
	context: AppRouterContext,
	history?: RouterHistory,
) {
	return createRouter({
		routeTree: buildRouteTree(),
		context,
		...(history ? { history } : {}),
		defaultPreload: "intent",
		scrollRestoration: true,
		defaultStructuralSharing: true,
		defaultPreloadStaleTime: 0,
	});
}

declare module "@tanstack/react-router" {
	interface Register {
		router: ReturnType<typeof createAppRouter>;
	}
}
