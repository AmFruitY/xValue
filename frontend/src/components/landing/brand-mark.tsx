interface BrandMarkProps {
  className?: string;
}

export function BrandMark({ className = "" }: BrandMarkProps) {
  return (
    <div
      className={`inline-flex items-baseline tracking-[-0.055em] ${className}`}
      aria-label="xVALUE"
    >
      <span className="text-accent font-mono text-[0.78em] font-semibold">x</span>
      <span className="font-semibold">VALUE</span>
    </div>
  );
}
