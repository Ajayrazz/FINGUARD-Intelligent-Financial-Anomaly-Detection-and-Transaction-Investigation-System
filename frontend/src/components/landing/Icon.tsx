const PATHS: Record<string, React.ReactNode> = {
  anomaly: <path d="M3 12h4l3-8 4 16 3-8h4" />,
  graph: (
    <>
      <circle cx="6" cy="12" r="2.5" />
      <circle cx="18" cy="6" r="2.5" />
      <circle cx="18" cy="18" r="2.5" />
      <path d="M8.2 10.9l7.6-3.8M8.2 13.1l7.6 3.8" />
    </>
  ),
  explain: (
    <path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.4 1 2.5h6c0-1.1.3-1.8 1-2.5A6 6 0 0 0 12 3z" />
  ),
  cases: <path d="M4 8h16v11H4zM9 8V5h6v3" />,
  risk: <path d="M4 17a8 8 0 1 1 16 0M12 17l4-5" />,
  duplicates: <path d="M9 9h10v10H9zM5 15V5h10" />,
  audit: <path d="M6 3h9l3 3v15H6zM9 11h6M9 15h6" />,
  upload: <path d="M12 16V4m0 0-4 4m4-4 4 4M4 20h16" />,
  shield: (
    <path d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-3zM9 12l2 2 4-4" />
  ),
};

/** Small stroke icons (decorative). */
export function Icon({
  name,
  size = 22,
}: {
  name: keyof typeof PATHS;
  size?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  );
}
