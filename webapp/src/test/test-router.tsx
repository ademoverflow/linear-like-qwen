import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { render } from "@testing-library/react";
import { createAppRouter } from "@/router";

/** Render the real route tree at `path` with a fresh, no-retry QueryClient. */
export function renderAt(path: string) {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	const router = createAppRouter(
		{ queryClient },
		createMemoryHistory({ initialEntries: [path] }),
	);
	render(
		<QueryClientProvider client={queryClient}>
			<RouterProvider router={router} />
		</QueryClientProvider>,
	);
	return { queryClient };
}
