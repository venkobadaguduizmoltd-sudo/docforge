const TONE: Record<string, string> = {
  ok: "bg-success/15 text-success",
  success: "bg-success/15 text-success",
  completed: "bg-success/15 text-success",
  running: "bg-accent-soft text-accent",
  queued: "bg-accent-soft text-accent",
  warning: "bg-warning/15 text-warning",
  failed: "bg-danger/15 text-danger",
  error: "bg-danger/15 text-danger",
  inactive: "bg-border/50 text-muted",
  default: "bg-border/40 text-muted",
};

type StatusPillProps = {
  label: string;
  tone?: keyof typeof TONE | string;
};

export function StatusPill({ label, tone }: StatusPillProps) {
  const key = (tone ?? label).toLowerCase();
  const classes = TONE[key] ?? TONE.default;
  return (
    <span className={`inline-flex rounded-md px-2 py-0.5 font-mono text-[0.68rem] uppercase tracking-wider ${classes}`}>
      {label}
    </span>
  );
}
