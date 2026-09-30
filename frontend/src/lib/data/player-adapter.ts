import type { Player } from "@/types/player";
import type { MockPredictionRow } from "./mock-predictions-parser";

function toFiniteNumber(value: string, field: string, playerId: string): number {
  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    throw new Error(`Invalid ${field} for player ${playerId}.`);
  }

  return parsed;
}

/** Maps the source-specific CSV shape to the stable frontend domain model. */
export function adaptMockPredictionToPlayer(row: MockPredictionRow): Player {
  return {
    id: row.player_id,
    name: row.player_name,
    league: row.league,
    club: row.club,
    position: row.position,
    age: toFiniteNumber(row.age, "age", row.player_id),
    isU23: row.is_u23.toLowerCase() === "true",
    season: row.season,
    inputs: {
      minutes: toFiniteNumber(row.minutes, "minutes", row.player_id),
      performanceIndex: toFiniteNumber(
        row.performance_index,
        "performance_index",
        row.player_id,
      ),
      availabilityPct: toFiniteNumber(
        row.availability_pct,
        "availability_pct",
        row.player_id,
      ),
      marketValueEur: toFiniteNumber(
        row.market_value_eur,
        "market_value_eur",
        row.player_id,
      ),
    },
    modelOutputs: {
      xValueEur: toFiniteNumber(row.xvalue_eur, "xvalue_eur", row.player_id),
      xValueGapEur: toFiniteNumber(
        row.xvalue_gap_eur,
        "xvalue_gap_eur",
        row.player_id,
      ),
      xValueGapPct: toFiniteNumber(
        row.xvalue_gap_pct,
        "xvalue_gap_pct",
        row.player_id,
      ),
    },
  };
}
