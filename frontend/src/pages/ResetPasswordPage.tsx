import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";
import { api, ApiError } from "../api/client";
import { AuthShell, Field } from "../components/auth/AuthShell";
import { Button } from "../components/ui/Button";
import { usePageTitle } from "../lib/usePageTitle";

const schema = z
  .object({
    new_password: z.string().min(12, "Use at least 12 characters"),
    confirm: z.string().min(1, "Repeat the password"),
  })
  .refine((v) => v.new_password === v.confirm, {
    path: ["confirm"],
    message: "Passwords do not match",
  });
type Values = z.infer<typeof schema>;

/** Opened from the emailed link: /reset-password?uid=…&token=… */
export default function ResetPasswordPage() {
  usePageTitle("Choose a new password");
  const [params] = useSearchParams();
  const uid = params.get("uid") ?? "";
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const [done, setDone] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema) });
  const input = "mt-1 w-full rounded-md border border-slate-300 px-3 py-2";

  const onSubmit = async (v: Values) => {
    setServerError(null);
    try {
      await api.post(
        "/auth/password-reset/confirm/",
        { uid, token, new_password: v.new_password },
        { skipAuthRetry: true },
      );
      setDone(true);
      setTimeout(() => navigate("/login", { replace: true }), 2500);
    } catch (e) {
      if (e instanceof ApiError && e.details.new_password) {
        const m = e.details.new_password;
        setError("new_password", {
          message: Array.isArray(m) ? m.join(" ") : String(m),
        });
      } else if (e instanceof ApiError && e.code === "invalid_token") {
        setServerError(
          "This reset link is invalid or has expired. Request a new one.",
        );
      } else {
        setServerError("Could not change the password. Please try again.");
      }
    }
  };

  if (!uid || !token)
    return (
      <AuthShell title="Reset link incomplete">
        <p role="alert" className="text-sm text-red-700">
          This link is incomplete. Open the link from the email again, or{" "}
          <Link to="/forgot-password">request a new one</Link>.
        </p>
      </AuthShell>
    );
  if (done)
    return (
      <AuthShell title="Password changed">
        <p role="status" className="text-sm">
          Your password was changed and all other sessions were signed out.
          Taking you to sign in…
        </p>
      </AuthShell>
    );
  return (
    <AuthShell title="Choose a new password">
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <Field
          id="new_password"
          label="New password"
          error={errors.new_password?.message}
          hint="At least 12 characters; avoid common passwords."
        >
          <input
            id="new_password"
            type="password"
            autoComplete="new-password"
            aria-invalid={!!errors.new_password}
            className={input}
            {...register("new_password")}
          />
        </Field>
        <Field
          id="confirm"
          label="Repeat password"
          error={errors.confirm?.message}
        >
          <input
            id="confirm"
            type="password"
            autoComplete="new-password"
            aria-invalid={!!errors.confirm}
            className={input}
            {...register("confirm")}
          />
        </Field>
        {serverError && (
          <p role="alert" className="text-sm text-red-700">
            {serverError} <Link to="/forgot-password">Request a new link</Link>
          </p>
        )}
        <Button type="submit" disabled={isSubmitting} className="w-full">
          {isSubmitting ? "Saving…" : "Change password"}
        </Button>
      </form>
    </AuthShell>
  );
}
