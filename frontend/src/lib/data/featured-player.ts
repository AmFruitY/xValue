import type { Player } from "@/types/player";

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

/**
 * Presentation-only ranking for the Demo 1 hero.
 *
 * IMPORTANT: featuredScore is not part of the xValue model, is not a scientific
 * metric, and must never be exposed as an analytical result. It balances a few
 * transparent UI preferences so the landing does not simply pick the largest
 * gap percentage.
 */
export function calculateFeaturedScore(player: Player): number {
  const positiveGapEur = Math.max(0, player.modelOutputs.xValueGapEur);
  const positiveGapPct = Math.max(0, player.modelOutputs.xValueGapPct);

  const u23Bonus = player.isU23 ? 20 : 0;
  const positiveGapBonus = positiveGapEur > 0 ? 15 : 0;
  const absoluteGapScore = clamp01(positiveGapEur / 6_000_000) * 20;
  const percentageGapScore = clamp01(positiveGapPct / 35) * 15;
  const minutesScore = clamp01(player.inputs.minutes / 2_400) * 20;
  const marketValueFloorScore = clamp01(
    player.inputs.marketValueEur / 5_000_000,
  ) * 10;

  return (
    u23Bonus +
    positiveGapBonus +
    absoluteGapScore +
    percentageGapScore +
    minutesScore +
    marketValueFloorScore
  );
}

export function selectFeaturedPlayer(players: Player[]): Player {
  if (players.length === 0) {
    throw new Error("The mock predictions dataset contains no players.");
  }

  return players.reduce((best, candidate) =>
    calculateFeaturedScore(candidate) > calculateFeaturedScore(best)
      ? candidate
      : best,
  );
}
