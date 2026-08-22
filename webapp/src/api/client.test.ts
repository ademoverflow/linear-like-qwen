import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.stubEnv("VITE_API_URL", "http://api.test");

const { api, ApiError } = await import("./client");

function jsonResponse(status: number, body: unknown): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { "Content-Type": "application/json" },
	});
}

describe("api client", () => {
	const fetchMock = vi.fn<typeof fetch>();

	beforeEach(() => {
		vi.stubGlobal("fetch", fetchMock);
	});

	afterEach(() => {
		fetchMock.mockReset();
		vi.unstubAllGlobals();
	});

	it("prefixes /api/v1, includes credentials and serialises query arrays", async () => {
		fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }));

		await api.get("/issues", {
			query: { team_id: "t1", priority: ["high", "urgent"] },
		});

		const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
		expect(url).toBe(
			"http://api.test/api/v1/issues?team_id=t1&priority=high&priority=urgent",
		);
		expect(init.credentials).toBe("include");
		expect(init.method).toBe("GET");
	});

	it("sends JSON bodies", async () => {
		fetchMock.mockResolvedValueOnce(jsonResponse(201, { id: "1" }));

		const result = await api.post<{ id: string }>("/teams", {
			name: "Eng",
			key: "ENG",
		});

		const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
		expect(init.body).toBe(JSON.stringify({ name: "Eng", key: "ENG" }));
		expect(result).toEqual({ id: "1" });
	});

	it("turns the error envelope into ApiError", async () => {
		fetchMock.mockResolvedValueOnce(
			jsonResponse(422, {
				error: {
					code: "rule_violation",
					message: "Need one started state",
					details: { x: 1 },
				},
			}),
		);

		const error = await api.post("/states").catch((e: unknown) => e);

		expect(error).toBeInstanceOf(ApiError);
		expect(error).toMatchObject({
			status: 422,
			code: "rule_violation",
			details: { x: 1 },
		});
	});

	it("handles non-JSON error bodies", async () => {
		fetchMock.mockResolvedValueOnce(
			new Response("<html/>", { status: 502, statusText: "Bad Gateway" }),
		);

		const error = await api.get("/anything").catch((e: unknown) => e);

		expect(error).toBeInstanceOf(ApiError);
		expect(error).toMatchObject({
			status: 502,
			code: "http_error",
			message: "Bad Gateway",
		});
	});
});
