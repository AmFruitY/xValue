import type { PredictionPage, PredictionQuery, PredictionRecord } from "./types";

export const PAGE_SIZE = 8;
export const MAX_PAGE_SIZE = 50;

export const DEFAULT_QUERY: PredictionQuery = { search: "", offset: 0, limit: PAGE_SIZE };

export const normalizeText = (text: string) => text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

/** Alphabetical by player, then club: a repeated name lists each observation next to the other. */
export function compareRecords(a: PredictionRecord, b: PredictionRecord): number {
  return a.playerName.localeCompare(b.playerName, "es") || a.club.localeCompare(b.club, "es") || a.season - b.season || a.id.localeCompare(b.id);
}

/** Every word of the search must appear in the player name, club or league. Shared by the API and the browser. */
export function matchesSearch(record: PredictionRecord, search: string): boolean {
  const words = normalizeText(search).split(/\s+/).filter(Boolean);
  if (!words.length) return true;
  const haystack = normalizeText(`${record.playerName} ${record.club} ${record.league}`);
  return words.every((word) => haystack.includes(word));
}

/**
 * Reference in-memory implementation of the query contract. A SQL-backed
 * repository (DuckDB, an API) must return the same page for the same query.
 */
export function runQuery(records: PredictionRecord[], query: PredictionQuery): PredictionPage {
  const matches = records.filter((record) => matchesSearch(record, query.search)).toSorted(compareRecords);
  return { items: matches.slice(query.offset, query.offset + query.limit), total: matches.length, offset: query.offset, limit: query.limit };
}

const numberOrNull = (value: string | null) => {
  if (value === null || value.trim() === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

/** URL ⇄ query mapping shared by the route handler and the browser client. */
export function queryFromSearchParams(params: URLSearchParams): PredictionQuery {
  return {
    search: (params.get("search") ?? "").slice(0, 80),
    offset: Math.max(0, Math.trunc(numberOrNull(params.get("offset")) ?? 0)),
    limit: Math.min(MAX_PAGE_SIZE, Math.max(1, Math.trunc(numberOrNull(params.get("limit")) ?? PAGE_SIZE))),
  };
}

export function queryToSearchParams(query: PredictionQuery): URLSearchParams {
  const params = new URLSearchParams();
  if (query.search) params.set("search", query.search);
  params.set("offset", String(query.offset));
  params.set("limit", String(query.limit));
  return params;
}
