import { selectFeaturedPlayer } from "./featured-player";
import { parseMockPredictionRows } from "./mock-predictions-parser";
import { adaptMockPredictionToPlayer } from "./player-adapter";

/** CSV -> parser -> adapter -> Player -> featured UI selection. */
export function getFeaturedPlayer() {
  const players = parseMockPredictionRows().map(adaptMockPredictionToPlayer);
  return selectFeaturedPlayer(players);
}
