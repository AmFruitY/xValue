interface MetricBarProps {
  label: string;
  value: number;
  displayValue: string;
}

export function MetricBar({
  label,
  value,
  displayValue,
}: MetricBarProps) {
  const safeValue = Math.min(100, Math.max(0, value));

  return (
    <div className="metric-item min-w-0" data-metric>
      <div className="mb-3 flex items-center justify-between gap-5">
        <p className="text-sm font-medium text-white/78">{label}</p>
        <span className="shrink-0 font-mono text-sm font-medium whitespace-nowrap text-white/88">
          {displayValue}
        </span>
      </div>
      <div
        className="h-1.5 overflow-hidden rounded-full bg-white/[0.07]"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(safeValue)}
      >
        <div
          className="metric-fill h-full rounded-full bg-gradient-to-r from-[#6fbf8d] to-accent"
          style={{ width: `${safeValue}%` }}
        />
      </div>
    </div>
  );
}
