import {
	createRootRoute,
	createRoute,
	createRouter,
	Outlet,
	RouterProvider,
} from "@tanstack/react-router";
import { StrictMode } from "react";
import ReactDOM from "react-dom/client";
import * as TanStackQueryProvider from "./integrations/tanstack-query/root-provider.tsx";

import "./styles.css";

import App from "./App.tsx";
import IssueViewsPrototype from "./pages/__prototype__/issue-views.tsx";
import About from "./pages/About.tsx";

const rootRoute = createRootRoute({
	component: () => (
		<>
			<Outlet />
		</>
	),
});

const indexRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: "/",
	component: App,
});

const aboutRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: "/about",
	component: About,
});

// Throwaway Phase-1 prototype (issue list density + board card anatomy).
// Delete this route and webapp/src/pages/__prototype__ once the design is folded in.
const prototypeIssueViewsRoute = createRoute({
	getParentRoute: () => rootRoute,
	path: "/prototype/issue-views",
	component: IssueViewsPrototype,
	validateSearch: (search: Record<string, unknown>) => ({
		variant: (search.variant as string | undefined) ?? "a",
	}),
});

const routeTree = rootRoute.addChildren([
	indexRoute,
	aboutRoute,
	prototypeIssueViewsRoute,
]);

const TanStackQueryProviderContext = TanStackQueryProvider.getContext();
const router = createRouter({
	routeTree,
	context: {
		...TanStackQueryProviderContext,
	},
	defaultPreload: "intent",
	scrollRestoration: true,
	defaultStructuralSharing: true,
	defaultPreloadStaleTime: 0,
});

declare module "@tanstack/react-router" {
	interface Register {
		router: typeof router;
	}
}

const rootElement = document.getElementById("app");
if (rootElement && !rootElement.innerHTML) {
	const root = ReactDOM.createRoot(rootElement);
	root.render(
		<StrictMode>
			<TanStackQueryProvider.Provider {...TanStackQueryProviderContext}>
				<RouterProvider router={router} />
			</TanStackQueryProvider.Provider>
		</StrictMode>,
	);
}
