import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger";
const styles: Record<Variant, string> = {
  primary: "btn-glow text-white",
  secondary:
    "border border-slate-300 bg-white/5 text-slate-800 hover:bg-white/10",
  danger: "bg-red-600 text-white hover:bg-red-500",
};

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type="button"
      {...props}
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition focus:outline-2 focus:outline-offset-2 focus:outline-indigo-300 disabled:opacity-50 ${styles[variant]} ${className}`}
    />
  );
}
