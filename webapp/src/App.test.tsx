import {
	createMemoryHistory,
	createRootRoute,
	createRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

function renderWithRouter() {
	const rootRoute = createRootRoute();
	const indexRoute = createRoute({
		getParentRoute: () => rootRoute,
		path: "/",
		component: App,
	});
	rootRoute.addChildren([indexRoute]);

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
	});

	// @ts-expect-error -- router type mismatch in test context
	render(<RouterProvider router={router} />);
}

describe("App", () => {
	it("renders the heading", async () => {
		renderWithRouter();
		const heading = await screen.findByRole("heading", { level: 1 });
		expect(heading.textContent).toBe("Hello World");
	});
});
