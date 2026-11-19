/**
 * Centralised API client.
 * - Access token lives in memory only (never localStorage); the refresh token is an httpOnly cookie.
 * - On a 401 the client refreshes once (single-flight) and retries; if that fails the session is over.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;
  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

let accessToken: string | null = null;
let onSessionExpired: (() => void) | null = null;
let refreshing: Promise<string> | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}
export function setSessionExpiredHandler(fn: (() => void) | null): void {
  onSessionExpired = fn;
}

async function parseError(res: Response): Promise<ApiError> {
  const body: unknown = await res.json().catch(() => null);
  const err = (
    body as {
      error?: {
        code?: string;
        message?: string;
        details?: Record<string, unknown>;
      };
    } | null
  )?.error;
  return new ApiError(
    res.status,
    err?.code ?? "error",
    err?.message ?? res.statusText,
    err?.details ?? {},
  );
}

/** Exchange the refresh cookie for a new access token. Concurrent callers share one request. */
export function refreshAccessToken(): Promise<string> {
  refreshing ??= fetch("/api/v1/auth/refresh/", {
    method: "POST",
    credentials: "same-origin",
  })
    .then(async (res) => {
      if (!res.ok) throw await parseError(res);
      const body = (await res.json()) as { access: string };
      accessToken = body.access;
      return body.access;
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

interface RequestOptions {
  body?: unknown;
  signal?: AbortSignal;
  /** Do not attempt a token refresh on 401 (login/logout). */
  skipAuthRetry?: boolean;
}

export async function request<T>(
  method: string,
  path: string,
  opts: RequestOptions = {},
): Promise<T> {
  const send = (): Promise<Response> => {
    const headers: Record<string, string> = { Accept: "application/json" };
    const isForm = opts.body instanceof FormData;
    if (opts.body !== undefined && !isForm)
      headers["Content-Type"] = "application/json"; // browser sets multipart boundary
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
    const init: RequestInit = { method, headers, credentials: "same-origin" };
    if (opts.body !== undefined)
      init.body = isForm ? (opts.body as FormData) : JSON.stringify(opts.body);
    if (opts.signal) init.signal = opts.signal;
    return fetch(`/api/v1${path}`, init);
  };

  let res = await send();
  if (res.status === 401 && !opts.skipAuthRetry) {
    try {
      await refreshAccessToken();
      res = await send();
    } catch {
      setAccessToken(null);
      onSessionExpired?.();
      throw new ApiError(
        401,
        "session_expired",
        "Your session has expired. Please sign in again.",
      );
    }
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) =>
    request<T>("GET", path, signal ? { signal } : {}),
  post: <T>(
    path: string,
    body?: unknown,
    opts: Omit<RequestOptions, "body"> = {},
  ) => request<T>("POST", path, { ...opts, body }),
  patch: <T>(path: string, body: unknown) =>
    request<T>("PATCH", path, { body }),
};

/** Fetch an authenticated file as a Blob (e.g. an invoice image for preview). */
export async function fetchBlob(path: string): Promise<Blob> {
  const send = () =>
    fetch(`/api/v1${path}`, {
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    });
  let res = await send();
  if (res.status === 401) {
    await refreshAccessToken();
    res = await send();
  }
  if (!res.ok) throw await parseError(res);
  return res.blob();
}

/** Download an authenticated file (the browser cannot attach the bearer token to a plain link). */
export async function downloadFile(
  path: string,
  filename: string,
): Promise<void> {
  const send = () =>
    fetch(`/api/v1${path}`, {
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    });
  let res = await send();
  if (res.status === 401) {
    await refreshAccessToken();
    res = await send();
  }
  if (!res.ok) throw await parseError(res);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export interface ReadinessResponse {
  status: "ok" | "degraded";
  checks: Record<string, string>;
}
