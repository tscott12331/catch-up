import { ApiError, isAbortError } from "./errors";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

type ErrorBody = {
  error?: { code?: unknown; message?: unknown; details?: unknown };
  detail?: unknown;
};

export type FetchImplementation = typeof fetch;

export type ApiTransport = {
  request(path: string, init?: RequestInit): Promise<Response>;
  requestJson<T>(path: string, init?: RequestInit): Promise<T>;
  errorFromResponse(response: Response): Promise<ApiError>;
};

export type TransportOptions = {
  baseUrl?: string;
  fetch?: FetchImplementation;
};

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function normalizeError(status: number, body: unknown): ApiError {
  const errorBody = body as ErrorBody | null;
  const nested = errorBody?.error;
  if (typeof nested?.message === "string" && nested.message) {
    return new ApiError(status, {
      code: typeof nested.code === "string" && nested.code ? nested.code : "request_failed",
      message: nested.message,
      details: nested.details,
    });
  }

  if (typeof errorBody?.detail === "string") {
    return new ApiError(status, { code: "request_failed", message: errorBody.detail });
  }

  return new ApiError(status, {
    code: "request_failed",
    message: status >= 500 ? "The backend could not complete the request." : "The request could not be completed.",
  });
}

export function createTransport(options: TransportOptions = {}): ApiTransport {
  const baseUrl = (options.baseUrl ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, "");

  async function request(path: string, init?: RequestInit): Promise<Response> {
    const headers = new Headers(init?.headers);
    if (!headers.has("Accept")) headers.set("Accept", "application/json");

    try {
      const fetchImplementation = options.fetch ?? globalThis.fetch;
      return await fetchImplementation(`${baseUrl}${path}`, { ...init, headers });
    } catch (error) {
      if (isAbortError(error)) throw error;
      throw new ApiError(0, {
        code: "network_error",
        message: "The backend is unavailable. Check that FastAPI is running.",
      });
    }
  }

  async function errorFromResponse(response: Response): Promise<ApiError> {
    return normalizeError(response.status, await readJson(response));
  }

  async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await request(path, init);
    const body = await readJson(response);
    if (!response.ok) throw normalizeError(response.status, body);
    return body as T;
  }

  return { request, requestJson, errorFromResponse };
}
