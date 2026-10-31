/**
 * Domain contract for xValue model results (predicciones_xvalue_final_v1.parquet).
 *
 * One record is one player–club–season observation: the model estimates the fee
 * of that player's transfer to that club in that season (club is a model input).
 * There is no player_id in the source, so `id` identifies the observation by
 * name, club and season, never a person.
 */
export interface PredictionRecord {
  id: string;
  playerName: string;
  league: string;
  club: string;
  /** Age in the season of the record; null when the source has none. */
  age: number | null;
  /** Starting year of the season: 2025 = 2025/26. */
  season: number;
  /** Lower and upper limits of the xValue range (pred_fee_bajo_eur, pred_fee_alto_eur). */
  rangeLowEur: number;
  rangeHighEur: number;
  /** Central estimate (pred_fee_eur). Shown as a secondary figure beside the range (player card, chart and Comparar); it underlies the xValue Gap. */
  centralEur: number;
  /** Published market value (current_mv_eur); null when the source has none. */
  marketValueEur: number | null;
  /** xvalue_gap = central estimate − market value, as delivered by the model output. */
  gapEur: number | null;
  /** xvalue_gap_bajo and xvalue_gap_alto: the same difference taken at the range limits. */
  gapLowEur: number | null;
  gapHighEur: number | null;
}

export interface PredictionQuery {
  /** Matches player name, club or league, accent- and case-insensitive. */
  search: string;
  offset: number;
  limit: number;
}

export interface PredictionPage {
  items: PredictionRecord[];
  total: number;
  offset: number;
  limit: number;
}

/** Dataset-derived context for the interface. */
export interface PredictionFacets {
  total: number;
  leagues: string[];
  seasons: number[];
  /** Records with a market value, and therefore an xValue Gap. */
  withMarketValue: number;
  /**
   * Spread of the range multipliers across the file: central ÷ lower limit and
   * upper limit ÷ central. Read from the data, since the margin varies by record.
   */
  rangeFactors: { lowMin: number; lowMax: number; highMin: number; highMax: number } | null;
  source: string;
}
