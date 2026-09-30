import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parse } from "csv-parse/sync";

export interface MockPredictionRow {
  player_id: string;
  player_name: string;
  season: string;
  league: string;
  club: string;
  position: string;
  age: string;
  is_u23: string;
  minutes: string;
  performance_index: string;
  market_value_eur: string;
  xvalue_eur: string;
  xvalue_gap_eur: string;
  xvalue_gap_pct: string;
  availability_pct: string;
}

const MOCK_PREDICTIONS_PATH = join(
  process.cwd(),
  "synthetic-test-data",
  "v0_1",
  "xvalue_mock_predictions.csv",
);

/** Infrastructure boundary: reads CSV and returns raw string records only. */
export function parseMockPredictionRows(): MockPredictionRow[] {
  const csv = readFileSync(MOCK_PREDICTIONS_PATH, "utf8");

  return parse(csv, {
    bom: true,
    columns: true,
    skip_empty_lines: true,
    trim: true,
  }) as MockPredictionRow[];
}
