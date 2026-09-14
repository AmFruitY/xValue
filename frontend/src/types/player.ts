export type GapDirection = "positive" | "negative" | "neutral";

/**
 * Frontend domain model produced by the mock-data adapter.
 * Numeric values remain unformatted so the same type can accept real outputs later.
 */
export interface Player {
  id: string;
  name: string;
  league: string;
  club: string;
  position: string;
  age: number;
  isU23: boolean;
  season: string;
  inputs: {
    minutes: number;
    performanceIndex: number;
    availabilityPct: number;
    marketValueEur: number;
  };
  modelOutputs: {
    xValueEur: number;
    xValueGapEur: number;
    xValueGapPct: number;
  };
}

/** Values derived only for display. None are xValue model outputs. */
export interface PlayerPresentation {
  initials: string;
  featuredScore: number;
  playingTimeDisplayPct: number;
  gapDirection: GapDirection;
}
