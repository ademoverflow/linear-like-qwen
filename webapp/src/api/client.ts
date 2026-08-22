import { env } from "@/env";

/** Shape of every error response from the core API (see core/src/core/domain/errors.py). */
export interface ApiErrorPayload {
	error: {
		code: string;
		message: string;
		details?: Record<string, unknown>;
	};
}

export class ApiError extends Error {
	readonly status: number;
	readonly code: string;
	readonly details?: Record<string, unknown>;

	constructor(status: number, payload: ApiErrorPayload["error"]) {
		super(payload.message);
		this.name = "ApiError";
		this.status = status;
		this.code = payload.code;
		this.details = payload.details;
	}
}

export const API_BASE = `${env.VITE_API_URL}/api/v1`;

type Query = Record<
	string,
	string | number | boolean | undefined | (string | number)[]
>;

function buildUrl(path: string, query?: Query): string {
	const url = new URL(`${API_BASE}${path}`);
	if (query) {
		for (const [key, value] of Object.entries(query)) {
			if (value === undefined) continue;
			if (Array.isArray(value)) {
				for (const item of value) url.searchParams.append(key, String(item));
			} else {
				url.searchParams.set(key, String(value));
			}
		}
	}
	return url.toString();
}

async function parseError(response: Response): Promise<ApiError> {
	try {
		const payload = (await response.json()) as Partial<ApiErrorPayload>;
		if (payload.error) return new ApiError(response.status, payload.error);
	} catch {
		// fall through: non-JSON body (proxy error, HTML page, ...)
	}
	return new ApiError(response.status, {
		code: "http_error",
		message: response.statusText || `HTTP ${response.status}`,
	});
}

export interface RequestOptions {
	query?: Query;
	body?: unknown;
	signal?: AbortSignal;
}

/**
 * Minimal typed fetch wrapper. Always sends the auth cookie (the API lives on another
 * origin in dev), always speaks JSON, and turns the API error envelope into `ApiError`.
 */
export async function request<T>(
	method: "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
	path: string,
	options: RequestOptions = {},
): Promise<T> {
	const response = await fetch(buildUrl(path, options.query), {
		method,
		credentials: "include",
		headers:
			options.body === undefined
				? { Accept: "application/json" }
				: { Accept: "application/json", "Content-Type": "application/json" },
		body: options.body === undefined ? undefined : JSON.stringify(options.body),
		signal: options.signal,
	});

	if (!response.ok) throw await parseError(response);
	if (response.status === 204) return undefined as T;
	return (await response.json()) as T;
}

export const api = {
	get: <T>(path: string, options?: RequestOptions) =>
		request<T>("GET", path, options),
	post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
		request<T>("POST", path, { ...options, body }),
	patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
		request<T>("PATCH", path, { ...options, body }),
	put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
		request<T>("PUT", path, { ...options, body }),
	delete: <T>(path: string, options?: RequestOptions) =>
		request<T>("DELETE", path, options),
};
