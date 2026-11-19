import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Logo } from "../components/fx/Logo";
import { NetworkBackground } from "../components/fx/NetworkBackground";
import { OrbitRing } from "../components/fx/OrbitRing";
import { Button } from "../components/ui/Button";

const schema = z.object({
  email: z
    .string()
    .min(1, "Email is required")
    .email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});
type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const { status, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const from = (location.state as { from?: string } | null)?.from ?? "/dashboard";
  if (status === "authenticated") return <Navigate to={from} replace />;

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    try {
      await login(values.email, values.password);
      navigate(from, { replace: true });
    } catch (e) {
      setServerError(
        e instanceof ApiError && e.status === 429
          ? "Too many attempts. Please wait before trying again."
          : e instanceof ApiError && e.status === 401
            ? "Invalid email or password."
            : "Unable to sign in. Please try again.",
      );
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden font-sans text-slate-800">
      <NetworkBackground />
      <main className="relative z-10 mx-auto grid min-h-screen max-w-6xl items-center gap-10 px-4 py-10 lg:grid-cols-2">
        <div className="animate-rise">
          <p className="flex items-center gap-2 font-mono text-xs tracking-[0.25em] text-indigo-300">
            <Logo size={22} /> FINANCIAL CRIME INVESTIGATION
          </p>
          <h1 className="mt-4 text-4xl font-semibold leading-tight md:text-5xl">
            <span className="gradient-text">FinGuard</span>
            <br />
            Spot anomalies. Trace networks. Explain every flag.
          </h1>
          <p className="mt-4 max-w-md text-slate-600">
            Machine learning, graph analytics and explainable AI for transaction
            investigation.
          </p>
          <div className="mt-8 hidden lg:block">
            <OrbitRing />
          </div>
        </div>
        <section
          aria-labelledby="signin-title"
          className="glass animate-rise mx-auto w-full max-w-sm rounded-2xl p-6"
        >
          <h2 id="signin-title" className="text-2xl font-semibold">
            Sign in
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Sign in to the investigation platform
          </p>
          <form
            onSubmit={handleSubmit(onSubmit)}
            noValidate
            className="mt-6 space-y-4"
          >
            <div>
              <label htmlFor="email" className="block text-sm font-medium">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                aria-invalid={!!errors.email}
                aria-describedby={errors.email ? "email-err" : undefined}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                {...register("email")}
              />
              {errors.email && (
                <p id="email-err" className="mt-1 text-sm text-red-700">
                  {errors.email.message}
                </p>
              )}
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                aria-invalid={!!errors.password}
                aria-describedby={errors.password ? "pw-err" : undefined}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                {...register("password")}
              />
              {errors.password && (
                <p id="pw-err" className="mt-1 text-sm text-red-700">
                  {errors.password.message}
                </p>
              )}
            </div>
            {serverError && (
              <p role="alert" className="text-sm text-red-700">
                {serverError}
              </p>
            )}
            <Button type="submit" disabled={isSubmitting} className="w-full">
              {isSubmitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </section>
      </main>
    </div>
  );
}
