import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger";
const styles: Record<Variant, string> = {
  primary: "bg-slate-900 text-white hover:bg-slate-700",
  secondary:
    "border border-slate-300 bg-white text-slate-800 hover:bg-slate-50",
  danger: "bg-red-600 text-white hover:bg-red-700",
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
      className={`rounded-md px-3 py-1.5 text-sm font-medium focus:outline-2 focus:outline-offset-2 focus:outline-slate-900 disabled:opacity-50 ${styles[variant]} ${className}`}
    />
  );
}
