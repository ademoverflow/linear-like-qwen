import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Vitest runs without `globals`, so Testing Library's automatic cleanup
// never registers — clean the DOM manually between tests.
afterEach(() => {
	cleanup();
});
