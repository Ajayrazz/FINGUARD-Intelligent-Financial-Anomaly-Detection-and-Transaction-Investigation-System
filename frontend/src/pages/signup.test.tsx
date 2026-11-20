import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthValue } from "../auth/AuthContext";
import ForgotPasswordPage from "./ForgotPasswordPage";
import LoginPage from "./LoginPage";
import RegisterPage from "./RegisterPage";
import ResetPasswordPage from "./ResetPasswordPage";
import VerifyEmailPage from "./VerifyEmailPage";

afterEach(() => vi.unstubAllGlobals());

const anon: AuthValue = {
  status: "anonymous",
  user: null,
  login: vi.fn(),
  logout: vi.fn(),
  can: () => false,
};
const json = (status: number, body: unknown) =>
  ({
    ok: status < 400,
    status,
    statusText: "x",
    json: async () => body,
  }) as Response;

function renderAt(
  path: string,
  ui: React.ReactNode,
  route: string,
  fetchMock: ReturnType<typeof vi.fn>,
  auth: AuthValue = anon,
) {
  vi.stubGlobal("fetch", fetchMock);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={auth}>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path={route} element={ui} />
            <Route path="/login" element={<p>login page</p>} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

async function fillRegister(over: Partial<Record<string, string>> = {}) {
  await userEvent.type(
    screen.getByLabelText("Full name"),
    over.name ?? "Asha Rao",
  );
  await userEvent.type(
    screen.getByLabelText("Work email"),
    over.email ?? "asha@example.com",
  );
  await userEvent.type(
    screen.getByLabelText("Password"),
    over.password ?? "Correct-Horse-Battery-9",
  );
  await userEvent.type(
    screen.getByLabelText("Repeat password"),
    over.confirm ?? over.password ?? "Correct-Horse-Battery-9",
  );
}

describe("RegisterPage", () => {
  it("validates before sending, then shows the check-your-email message without revealing anything else", async () => {
    const f = vi.fn(async () => json(202, { detail: "ok" }));
    renderAt("/register", <RegisterPage />, "/register", f);
    await userEvent.click(
      screen.getByRole("button", { name: "Create account" }),
    );
    expect(await screen.findByText("Enter your name")).toBeInTheDocument();
    expect(f).not.toHaveBeenCalled();

    await fillRegister({ confirm: "different-password-123" });
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(
      screen.getByRole("button", { name: "Create account" }),
    );
    expect(
      await screen.findByText("Passwords do not match"),
    ).toBeInTheDocument();
    expect(f).not.toHaveBeenCalled();

    await userEvent.clear(screen.getByLabelText("Repeat password"));
    await userEvent.type(
      screen.getByLabelText("Repeat password"),
      "Correct-Horse-Battery-9",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Create account" }),
    );
    expect(await screen.findByText("Check your email")).toBeInTheDocument();
    expect(
      screen.getByText(/administrator has to approve/),
    ).toBeInTheDocument();
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/auth/register/");
    expect(JSON.parse(String(init.body))).toEqual({
      email: "asha@example.com",
      full_name: "Asha Rao",
      password: "Correct-Horse-Battery-9",
      accept_terms: true,
    });
  });

  it("requires accepting the terms and shows server-side password complaints on the field", async () => {
    const f = vi.fn(async () =>
      json(400, {
        error: {
          code: "validation_error",
          message: "bad",
          details: { password: ["This password is too common."] },
        },
      }),
    );
    renderAt("/register", <RegisterPage />, "/register", f);
    await fillRegister();
    await userEvent.click(
      screen.getByRole("button", { name: "Create account" }),
    );
    expect(
      await screen.findByText("You must accept the terms"),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(
      screen.getByRole("button", { name: "Create account" }),
    );
    expect(
      await screen.findByText("This password is too common."),
    ).toBeInTheDocument();
  });

  it("explains a rate limit", async () => {
    const f = vi.fn(async () =>
      json(429, {
        error: { code: "throttled", message: "slow down", details: {} },
      }),
    );
    renderAt("/register", <RegisterPage />, "/register", f);
    await fillRegister();
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(
      screen.getByRole("button", { name: "Create account" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Too many attempts",
    );
  });
});

describe("VerifyEmailPage", () => {
  it("confirms with the token from the link and says approval is next", async () => {
    const f = vi.fn(async () => json(200, { status: "pending_approval" }));
    renderAt(
      "/verify-email?token=abc",
      <VerifyEmailPage />,
      "/verify-email",
      f,
    );
    expect(
      await screen.findByText(/email address is confirmed/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/administrator now has to approve/),
    ).toBeInTheDocument();
    expect(
      JSON.parse(
        String((f.mock.calls[0] as unknown as [string, RequestInit])[1].body),
      ),
    ).toEqual({ token: "abc" });
  });
  it("shows the server's message for a bad or expired link, and handles a missing token", async () => {
    const f = vi.fn(async () =>
      json(400, {
        error: {
          code: "invalid_token",
          message: "This link is invalid or has expired. Request a new one.",
          details: {},
        },
      }),
    );
    const { unmount } = renderAt(
      "/verify-email?token=bad",
      <VerifyEmailPage />,
      "/verify-email",
      f,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "invalid or has expired",
    );
    unmount();
    renderAt("/verify-email", <VerifyEmailPage />, "/verify-email", vi.fn());
    expect(await screen.findByRole("alert")).toHaveTextContent("incomplete");
  });
});

describe("ForgotPasswordPage and ResetPasswordPage", () => {
  it("always says an email is on the way, whoever asked", async () => {
    const f = vi.fn(async () => json(202, { detail: "ok" }));
    renderAt("/forgot-password", <ForgotPasswordPage />, "/forgot-password", f);
    await userEvent.type(screen.getByLabelText("Email"), "anyone@example.com");
    await userEvent.click(
      screen.getByRole("button", { name: "Send reset link" }),
    );
    expect(
      await screen.findByText(/If an account exists for/),
    ).toBeInTheDocument();
  });
  it("sets a new password from the link and sends the uid and token", async () => {
    const f = vi.fn(async () => json(204, undefined));
    renderAt(
      "/reset-password?uid=MQ&token=t-123",
      <ResetPasswordPage />,
      "/reset-password",
      f,
    );
    await userEvent.type(
      screen.getByLabelText("New password"),
      "Brand-New-Passphrase-42",
    );
    await userEvent.type(
      screen.getByLabelText("Repeat password"),
      "Brand-New-Passphrase-42",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Change password" }),
    );
    expect(
      await screen.findByText(/Your password was changed/),
    ).toBeInTheDocument();
    expect(
      JSON.parse(
        String((f.mock.calls[0] as unknown as [string, RequestInit])[1].body),
      ),
    ).toEqual({
      uid: "MQ",
      token: "t-123",
      new_password: "Brand-New-Passphrase-42",
    });
  });
  it("refuses an incomplete link and reports an expired one", async () => {
    const { unmount } = renderAt(
      "/reset-password",
      <ResetPasswordPage />,
      "/reset-password",
      vi.fn(),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("incomplete");
    unmount();
    const f = vi.fn(async () =>
      json(400, {
        error: { code: "invalid_token", message: "x", details: {} },
      }),
    );
    renderAt(
      "/reset-password?uid=MQ&token=old",
      <ResetPasswordPage />,
      "/reset-password",
      f,
    );
    await userEvent.type(
      screen.getByLabelText("New password"),
      "Brand-New-Passphrase-42",
    );
    await userEvent.type(
      screen.getByLabelText("Repeat password"),
      "Brand-New-Passphrase-42",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Change password" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "invalid or has expired",
    );
  });
});

describe("LoginPage account states", () => {
  const login = (code: string, message: string) =>
    vi.fn(async () => {
      throw Object.assign(new Error(message), {
        status: 403,
        code,
        details: {},
      });
    });
  async function attempt(code: string, message: string) {
    const { ApiError } = await import("../api/client");
    const fn = vi.fn(async () => {
      throw new ApiError(403, code, message);
    });
    renderAt(
      "/login",
      <LoginPage />,
      "/login",
      vi.fn(async () => json(202, {})),
      { ...anon, login: fn },
    );
    await userEvent.type(screen.getByLabelText("Email"), "asha@example.com");
    await userEvent.type(
      screen.getByLabelText("Password"),
      "Correct-Horse-Battery-9",
    );
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  }
  it("offers to resend the confirmation email, and links to sign-up and password reset", async () => {
    void login;
    await attempt(
      "email_not_verified",
      "Confirm your email address first: use the link we emailed you.",
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Confirm your email address first",
    );
    expect(
      screen.getByRole("button", { name: "Resend the confirmation email" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Forgot your password?" }),
    ).toHaveAttribute("href", "/forgot-password");
    expect(
      screen.getByRole("link", { name: "Create an account" }),
    ).toHaveAttribute("href", "/register");
    await userEvent.click(
      screen.getByRole("button", { name: "Resend the confirmation email" }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "a new link is on its way",
    );
  });
  it("tells a confirmed user that approval is pending", async () => {
    await attempt(
      "pending_approval",
      "Your email is confirmed. An administrator still has to approve your account.",
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "administrator still has to approve",
    );
    expect(
      screen.queryByRole("button", { name: "Resend the confirmation email" }),
    ).not.toBeInTheDocument();
  });
});
