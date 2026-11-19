/** FinGuard mark: a shield with a small node graph inside. Decorative; the name is always next to it. */
export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient id="fg-logo" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#818cf8" />
          <stop offset="1" stopColor="#a78bfa" />
        </linearGradient>
      </defs>
      <path
        d="M16 2 4 6.5v8.6c0 7.1 4.9 12.6 12 14.9 7.1-2.3 12-7.8 12-14.9V6.5L16 2Z"
        fill="none"
        stroke="url(#fg-logo)"
        strokeWidth="2"
      />
      <g stroke="#a5b4fc" strokeWidth="1.4" fill="#c7d2fe">
        <path d="M10.5 17 16 11l5.5 6M10.5 17h11" fill="none" />
        <circle cx="16" cy="11" r="2" />
        <circle cx="10.5" cy="17" r="2" />
        <circle cx="21.5" cy="17" r="2" />
      </g>
    </svg>
  );
}
