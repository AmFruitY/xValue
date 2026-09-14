import { calculateFeaturedScore } from "@/lib/data/featured-player";
import type { Player, PlayerPresentation } from "@/types/player";

// A full league season is roughly 3,000–3,420 minutes. Demo 1 uses a simple
// 3,000-minute ceiling for bar width only; this is not a model output.
const PLAYING_TIME_DISPLAY_BENCHMARK = 3_000;

export function createPlayerPresentation(player: Player): PlayerPresentation {
  const names = player.name.trim().split(/\s+/);
  const initials = names
    .slice(0, 2)
    .map((name) => name.charAt(0).toUpperCase())
    .join("");

  const gapDirection =
    player.modelOutputs.xValueGapEur > 0
      ? "positive"
      : player.modelOutputs.xValueGapEur < 0
        ? "negative"
        : "neutral";

  return {
    initials,
    featuredScore: calculateFeaturedScore(player),
    playingTimeDisplayPct: Math.min(
      100,
      Math.max(
        0,
        (player.inputs.minutes / PLAYING_TIME_DISPLAY_BENCHMARK) * 100,
      ),
    ),
    gapDirection,
  };
}
