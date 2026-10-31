import { queryToSearchParams } from "./query";
import type { PredictionPage, PredictionQuery } from "./types";

/** Browser-side access to the predictions API. Point it to another backend by changing this URL. */
export const PREDICTIONS_ENDPOINT = "/api/predictions";

export async function fetchPredictions(query: PredictionQuery, signal?: AbortSignal): Promise<PredictionPage> {
  const response = await fetch(`${PREDICTIONS_ENDPOINT}?${queryToSearchParams(query)}`, { signal });
  if (!response.ok) throw new Error(`predictions ${response.status}`);
  return response.json() as Promise<PredictionPage>;
}
