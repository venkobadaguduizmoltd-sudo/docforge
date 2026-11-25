type LoadingStateProps = {
  label?: string;
  rows?: number;
};

export function LoadingState({ label = "Loading…", rows = 3 }: LoadingStateProps) {
  return (
    <div className="space-y-3 animate-fade-in" role="status" aria-live="polite" aria-label={label}>
      <p className="df-kicker">{label}</p>
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="df-skeleton h-12 w-full" />
      ))}
    </div>
  );
}
