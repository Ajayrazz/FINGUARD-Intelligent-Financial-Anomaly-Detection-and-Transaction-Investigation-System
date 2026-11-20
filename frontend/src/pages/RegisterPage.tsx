import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import { api, ApiError } from "../api/client";
import { AuthShell, Field } from "../components/auth/AuthShell";
import { Button } from "../components/ui/Button";
import { usePageTitle } from "../lib/usePageTitle";

const schema = z
  .object({
    full_name: z.string().trim().min(2, "Enter your name"),
    email: z
      .string()
      .min(1, "Email is required")
      .email("Enter a valid email address"),
    password: z.string().min(12, "Use at least 12 characters"),
    confirm: z.string().min(1, "Repeat the password"),
    accept_terms: z.boolean().refine((v) => v, "You must accept the terms"),
  })
  .refine((v) => v.password === v.confirm, {
    path: ["confirm"],
    message: "Passwords do not match",
  });
type Values = z.infer<typeof schema>;

export default function RegisterPage() {
  usePageTitle("Create account");
  const [done, setDone] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { accept_terms: false },
  });
  const input = "mt-1 w-full rounded-md border border-slate-300 px-3 py-2";

  const onSubmit = async (v: Values) => {
    setServerError(null);
    try {
      await api.post(
        "/auth/register/",
        {
          email: v.email,
          full_name: v.full_name,
          password: v.password,
          accept_terms: v.accept_terms,
        },
        { skipAuthRetry: true },
      );
      setDone(v.email);
    } catch (e) {
      if (e instanceof ApiError && e.status === 400) {
        for (const [field, msgs] of Object.entries(e.details)) {
          if (
            field in v ||
            field === "password" ||
            field === "email" ||
            field === "full_name"
          )
            setError(field as keyof Values, {
              message: Array.isArray(msgs) ? msgs.join(" ") : String(msgs),
            });
        }
        const general = e.details.non_field_errors;
        if (general)
          setServerError(
            Array.isArray(general) ? general.join(" ") : String(general),
          );
        else if (Object.keys(e.details).length === 0) setServerError(e.message);
      } else if (e instanceof ApiError && e.status === 429) {
        setServerError("Too many attempts. Please wait a while and try again.");
      } else {
        setServerError("Could not create the account. Please try again.");
      }
    }
  };

  if (done)
    return (
      <AuthShell title="Check your email" subtitle="One more step">
        <div role="status" className="space-y-3 text-sm">
          <p>
            If <strong>{done}</strong> can be used, we sent a confirmation link
            to it. Open the link to confirm your address.
          </p>
          <p className="text-slate-600">
            After that, an administrator has to approve your account before you
            can sign in. You will get an email when that happens.
          </p>
          <p className="text-slate-600">
            Nothing arrived after a few minutes? Check spam, or{" "}
            <Link to="/login">sign in</Link> and use "Resend the confirmation
            email".
          </p>
        </div>
      </AuthShell>
    );

  return (
    <AuthShell
      title="Create your account"
      subtitle="Accounts are approved by an administrator before they can be used."
    >
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <Field
          id="full_name"
          label="Full name"
          error={errors.full_name?.message}
        >
          <input
            id="full_name"
            autoComplete="name"
            aria-invalid={!!errors.full_name}
            className={input}
            {...register("full_name")}
          />
        </Field>
        <Field id="email" label="Work email" error={errors.email?.message}>
          <input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={!!errors.email}
            className={input}
            {...register("email")}
          />
        </Field>
        <Field
          id="password"
          label="Password"
          error={errors.password?.message}
          hint="At least 12 characters; avoid common passwords and your own name or email."
        >
          <input
            id="password"
            type="password"
            autoComplete="new-password"
            aria-invalid={!!errors.password}
            className={input}
            {...register("password")}
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
        <div>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-1"
              {...register("accept_terms")}
            />
            <span>
              I understand FinGuard handles sensitive financial data, and I
              agree to use it only for authorised investigation work.
            </span>
          </label>
          {errors.accept_terms && (
            <p className="mt-1 text-sm text-red-700">
              {errors.accept_terms.message}
            </p>
          )}
        </div>
        {serverError && (
          <p role="alert" className="text-sm text-red-700">
            {serverError}
          </p>
        )}
        <Button type="submit" disabled={isSubmitting} className="w-full">
          {isSubmitting ? "Creating account…" : "Create account"}
        </Button>
        <p className="text-center text-sm text-slate-600">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </AuthShell>
  );
}
