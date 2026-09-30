import { formatCompactEur, formatSignedPercentage } from "@/lib/format";
import type { Player, PlayerPresentation } from "@/types/player";

interface PlayerValueGridProps {
  player: Player;
  presentation: PlayerPresentation;
}

export function PlayerValueGrid({
  player,
  presentation,
}: PlayerValueGridProps) {
  const gapIsPositive = presentation.gapDirection === "positive";
  const gapIsNegative = presentation.gapDirection === "negative";
  const gapColor = gapIsPositive
    ? "text-accent"
    : gapIsNegative
      ? "text-negative"
      : "text-white";

  return (
    <div className="grid grid-cols-2 overflow-hidden rounded-2xl border border-white/10 bg-white/[0.025] lg:grid-cols-[0.78fr_0.78fr_1.25fr]">
      <div className="value-card border-r border-b border-white/10 p-4 sm:p-5 lg:border-b-0">
        <p className="text-xs font-semibold tracking-[0.12em] text-muted uppercase">
          Market Value
        </p>
        <p className="mt-2 text-[clamp(1.45rem,2.1vw,2.15rem)] font-medium tracking-[-0.045em] text-white/85">
          {formatCompactEur(player.inputs.marketValueEur)}
        </p>
        <p className="mt-1 text-xs text-muted">Reference</p>
      </div>

      <div className="value-card border-b border-white/10 p-4 sm:p-5 lg:border-r lg:border-b-0">
        <p className="text-xs font-semibold tracking-[0.12em] text-muted uppercase">
          xValue
        </p>
        <p className="mt-2 text-[clamp(1.45rem,2.1vw,2.15rem)] font-medium tracking-[-0.045em] text-white">
          {formatCompactEur(player.modelOutputs.xValueEur)}
        </p>
        <p className="mt-1 text-xs text-muted">Model estimate</p>
      </div>

      <div className="gap-card col-span-2 p-4 sm:p-5 lg:col-span-1">
        <p className="flex items-center gap-2 text-xs font-semibold tracking-[0.12em] text-muted uppercase">
          xValue Gap
          <span className={`text-sm ${gapColor}`} aria-hidden="true">
            {gapIsPositive ? "↗" : gapIsNegative ? "↘" : "→"}
          </span>
        </p>
        <div className="mt-2 flex items-baseline justify-between gap-4">
          <p
            className={`text-[clamp(2.1rem,4.2vw,4rem)] leading-none font-semibold tracking-[-0.065em] ${gapColor}`}
          >
            {formatSignedPercentage(player.modelOutputs.xValueGapPct)}
          </p>
          <p className={`font-mono text-sm font-medium ${gapColor}`}>
            {formatCompactEur(player.modelOutputs.xValueGapEur, {
              signed: true,
            })}
          </p>
        </div>
      </div>
    </div>
  );
}
