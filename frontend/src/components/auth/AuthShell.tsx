import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Logo } from "../fx/Logo";
import { NetworkBackground } from "../fx/NetworkBackground";

/** Centered glass card on the animated background, shared by the signed-out account pages. */
export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <div className="relative min-h-screen overflow-hidden font-sans text-slate-800">
      <NetworkBackground />
      <main className="relative z-10 mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-10">
        <Link
          to="/"
          className="mb-6 flex items-center justify-center gap-2 text-lg font-semibold no-underline"
        >
          <Logo size={28} />
          <span className="gradient-text">FinGuard</span>
        </Link>
        <section
          aria-labelledby="auth-title"
          className="glass animate-rise rounded-2xl p-6"
        >
          <h1 id="auth-title" className="text-2xl font-semibold">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-1 text-sm text-slate-600">{subtitle}</p>
          )}
          <div className="mt-5">{children}</div>
        </section>
      </main>
    </div>
  );
}

export function Field({
  id,
  label,
  error,
  hint,
  children,
}: {
  id: string;
  label: string;
  error?: string | undefined;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
      {error && (
        <p id={`${id}-err`} className="mt-1 text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}
