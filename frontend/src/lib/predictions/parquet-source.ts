import "server-only";
import { readFile, stat } from "node:fs/promises";
import { basename, resolve } from "node:path";
import { parquetMetadata, parquetReadObjects } from "hyparquet";
import { normalizeText } from "./query";
import type { PredictionRecord } from "./types";

/** Infrastructure boundary: the only module that knows about the Parquet file and its column names. */
const REQUIRED_COLUMNS = [
  "player_name", "league", "club", "age", "season",
  "pred_fee_eur", "pred_fee_bajo_eur", "pred_fee_alto_eur",
  "current_mv_eur", "xvalue_gap", "xvalue_gap_bajo", "xvalue_gap_alto",
] as const;

/** Display names for league labels as they arrive in the source. */
const LEAGUE_LABELS: Record<string, string> = { Laliga: "LaLiga" };

export function predictionsParquetPath(): string {
  return process.env.XVALUE_PREDICTIONS_PARQUET
    ?? resolve(process.cwd(), "..", "data", "processed", "model_outputs", "predicciones_xvalue_final_v1.parquet");
}

const toNumber = (value: unknown) => typeof value === "bigint" ? Number(value) : typeof value === "number" ? value : Number.NaN;
const toNullableNumber = (value: unknown) => { const number = toNumber(value); return Number.isFinite(number) ? number : null; };
const slug = (text: string) => normalizeText(text).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

let cache: { path: string; mtimeMs: number; records: PredictionRecord[] } | null = null;

/** Reads the file once per modification time; the original file is opened read-only. It is read at runtime, not traced into the build output. */
export async function readPredictionRecords(): Promise<{ records: PredictionRecord[]; source: string }> {
  const path = predictionsParquetPath();
  const { mtimeMs } = await stat(/*turbopackIgnore: true*/ path);
  if (cache && cache.path === path && cache.mtimeMs === mtimeMs) return { records: cache.records, source: basename(path) };

  const buffer = await readFile(/*turbopackIgnore: true*/ path);
  const file = buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength) as ArrayBuffer;
  const columns = parquetMetadata(file).schema.map((element) => element.name);
  const missing = REQUIRED_COLUMNS.filter((column) => !columns.includes(column));
  if (missing.length) throw new Error(`Parquet schema mismatch in ${basename(path)}: missing ${missing.join(", ")}`);

  const rows = await parquetReadObjects({ file, columns: [...REQUIRED_COLUMNS] });
  const records: PredictionRecord[] = [];
  const seen = new Map<string, number>();
  let inverted = 0;
  for (const row of rows) {
    const playerName = typeof row.player_name === "string" ? row.player_name.trim() : "";
    const club = typeof row.club === "string" ? row.club.trim() : "";
    const league = typeof row.league === "string" ? row.league.trim() : "";
    const season = toNumber(row.season), low = toNumber(row.pred_fee_bajo_eur), high = toNumber(row.pred_fee_alto_eur), central = toNumber(row.pred_fee_eur);
    // Incomplete rows are skipped rather than filled with invented values.
    if (!playerName || !club || !Number.isFinite(season) || !Number.isFinite(low) || !Number.isFinite(high) || !Number.isFinite(central)) continue;
    // A range must contain its central estimate; a regenerated file that breaks this is reported, not displayed.
    if (!(low <= central && central <= high)) { inverted++; continue; }
    const marketValue = toNullableNumber(row.current_mv_eur);
    // The Gap is only meaningful next to its market value; a stray Gap without one is ignored.
    const gap = marketValue === null ? null : toNullableNumber(row.xvalue_gap);
    // Stable key from the observation itself, so it survives a regenerated file with a different row order.
    const base = `${slug(playerName)}--${slug(club)}--${season}`;
    const count = (seen.get(base) ?? 0) + 1; seen.set(base, count);
    records.push({
      id: count === 1 ? base : `${base}--${count}`,
      playerName, club, league: LEAGUE_LABELS[league] ?? league,
      age: toNullableNumber(row.age), season,
      rangeLowEur: low, rangeHighEur: high, centralEur: central,
      marketValueEur: marketValue, gapEur: gap,
      gapLowEur: marketValue === null ? null : toNullableNumber(row.xvalue_gap_bajo),
      gapHighEur: marketValue === null ? null : toNullableNumber(row.xvalue_gap_alto),
    });
  }
  if (inverted) console.warn(`${basename(path)}: ${inverted} rows skipped because their range does not contain the central estimate.`);
  cache = { path, mtimeMs, records };
  return { records, source: basename(path) };
}
