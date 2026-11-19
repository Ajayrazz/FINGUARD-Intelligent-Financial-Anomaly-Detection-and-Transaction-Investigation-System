import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  api,
  ApiError,
  setAccessToken,
  setSessionExpiredHandler,
} from "./client";

const json = (status: number, body: unknown) =>
  ({
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: async () => body,
  }) as Response;

beforeEach(() => setAccessToken("old-token"));
afterEach(() => {
  vi.unstubAllGlobals();
  setSessionExpiredHandler(null);
});

describe("api client", () => {
  it("sends the bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await api.get("/x/");
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer old-token",
    );
  });

  it("refreshes once on 401 and retries with the new token", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        json(401, { error: { code: "token_not_valid", message: "expired" } }),
      )
      .mockResolvedValueOnce(json(200, { access: "new-token" })) // refresh
      .mockResolvedValueOnce(json(200, { data: 1 })); // retry
    vi.stubGlobal("fetch", fetchMock);
    expect(await api.get("/x/")).toEqual({ data: 1 });
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/auth/refresh/");
    const retryInit = fetchMock.mock.calls[2]?.[1] as RequestInit;
    expect((retryInit.headers as Record<string, string>).Authorization).toBe(
      "Bearer new-token",
    );
  });

  it("ends the session when the refresh fails", async () => {
    const expired = vi.fn();
    setSessionExpiredHandler(expired);
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(json(401, {}))
        .mockResolvedValueOnce(
          json(401, {
            error: {
              code: "invalid_refresh_token",
              message: "Session expired.",
            },
          }),
        ),
    );
    await expect(api.get("/x/")).rejects.toMatchObject({
      code: "session_expired",
    });
    expect(expired).toHaveBeenCalledOnce();
  });

  it("surfaces the backend error envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          json(400, {
            error: {
              code: "validation_error",
              message: "Validation failed",
              details: { email: ["bad"] },
            },
          }),
        ),
    );
    const err = await api.post("/users/", {}).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({
      status: 400,
      code: "validation_error",
      details: { email: ["bad"] },
    });
  });

  it("does not try to refresh when skipAuthRetry is set (login)", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        json(401, { error: { code: "invalid_credentials", message: "no" } }),
      );
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      api.post("/auth/login/", {}, { skipAuthRetry: true }),
    ).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
