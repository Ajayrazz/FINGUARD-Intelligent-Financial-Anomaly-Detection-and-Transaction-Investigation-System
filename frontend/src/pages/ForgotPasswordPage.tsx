import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import { api, ApiError } from "../api/client";
import { AuthShell, Field } from "../components/auth/AuthShell";
import { Button } from "../components/ui/Button";
import { usePageTitle } from "../lib/usePageTitle";

const schema = z.object({
  email: z
    .string()
    .min(1, "Email is required")
    .email("Enter a valid email address"),
});
type Values = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  usePageTitle("Forgot password");
  const [sent, setSent] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema) });
  const onSubmit = async (v: Values) => {
    setServerError(null);
    try {
      await api.post("/auth/password-reset/", v, { skipAuthRetry: true });
      setSent(v.email);
    } catch (e) {
      setServerError(
        e instanceof ApiError && e.status === 429
          ? "Too many requests. Please wait a while and try again."
          : "Could not send the email. Please try again.",
      );
    }
  };
  if (sent)
    return (
      <AuthShell title="Check your email">
        <div role="status" className="space-y-3 text-sm">
          <p>
            If an account exists for <strong>{sent}</strong>, we sent a link to
            choose a new password. It works once and expires in one hour.
          </p>
          <p>
            <Link to="/login">Back to sign in</Link>
          </p>
        </div>
      </AuthShell>
    );
  return (
    <AuthShell
      title="Forgot your password?"
      subtitle="Enter your email and we will send a reset link."
    >
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <Field id="email" label="Email" error={errors.email?.message}>
          <input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={!!errors.email}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            {...register("email")}
          />
        </Field>
        {serverError && (
          <p role="alert" className="text-sm text-red-700">
            {serverError}
          </p>
        )}
        <Button type="submit" disabled={isSubmitting} className="w-full">
          {isSubmitting ? "Sending…" : "Send reset link"}
        </Button>
        <p className="text-center text-sm">
          <Link to="/login">Back to sign in</Link>
        </p>
      </form>
    </AuthShell>
  );
}
