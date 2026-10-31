import "server-only";
import { readPredictionRecords } from "./parquet-source";
import { compareRecords, runQuery } from "./query";
import type { PredictionFacets, PredictionPage, PredictionQuery, PredictionRecord } from "./types";

/** Records the interface opens with: one for Comprar and Vender, a second one for Comparar. */
export interface FeaturedRecords { primary: PredictionRecord | null; secondary: PredictionRecord | null }

/**
 * Server-side access to model results. Components and route handlers depend on
 * this interface only; a DuckDB or FastAPI implementation can replace the
 * Parquet one without touching the UI.
 */
export interface PredictionRepository {
  facets(): Promise<PredictionFacets>;
  query(query: PredictionQuery): Promise<PredictionPage>;
  byId(id: string): Promise<PredictionRecord | null>;
  featured(): Promise<FeaturedRecords>;
}

const parquetRepository: PredictionRepository = {
  async facets() {
    const { records, source } = await readPredictionRecords();
    const lows = records.map((record) => record.centralEur / record.rangeLowEur), highs = records.map((record) => record.rangeHighEur / record.centralEur);
    return {
      rangeFactors: records.length ? { lowMin: Math.min(...lows), lowMax: Math.max(...lows), highMin: Math.min(...highs), highMax: Math.max(...highs) } : null,
      total: records.length,
      leagues: [...new Set(records.map((record) => record.league))].sort((a, b) => a.localeCompare(b, "es")),
      seasons: [...new Set(records.map((record) => record.season))].sort((a, b) => b - a),
      withMarketValue: records.filter((record) => record.marketValueEur !== null).length,
      source,
    };
  },
  async query(query) {
    return runQuery((await readPredictionRecords()).records, query);
  },
  async byId(id) {
    return (await readPredictionRecords()).records.find((record) => record.id === id) ?? null;
  },
  // Deterministic and neutral: the first observation alphabetically, then the next one from the same league.
  async featured() {
    const sorted = (await readPredictionRecords()).records.toSorted(compareRecords);
    const primary = sorted[0] ?? null;
    const secondary = sorted.find((record) => record.id !== primary?.id && record.league === primary?.league) ?? sorted[1] ?? null;
    return { primary, secondary };
  },
};

export function getPredictionRepository(): PredictionRepository {
  return parquetRepository;
}
