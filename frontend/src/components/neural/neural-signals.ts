/**
 * Visual relations between interface elements. They guide attention through the
 * UI (player → range → scenario, and the market reference beside it); they do not
 * depict the model, its features, weights or inference.
 */
export type Workspace = "buy" | "sell" | "compare" | "how";
export type SignalKind = "welcome" | "select" | "scenario" | "compare" | "how" | "kick";
export type Port = "left" | "right" | "top" | "bottom";
export interface SignalRoute {
  from: string; to: string; delay?: number; fromPort?: Port; toPort?: Port;
  /** Pick ports from the live layout: side by side, arched over a neighbour, or stacked. */
  auto?: boolean;
}
export interface NeuralSignal { kind: SignalKind; routes: SignalRoute[]; time: number; origin?: { x: number; y: number } }
export const SIGNAL_EVENT = "xvalue:neural-signal";
/** Comprar and Vender share one layout: player and range → scenario → chart. */
export const SCENARIO_ROUTES: SignalRoute[] = [
  { from: "range", to: "scenario", delay: 0.6, auto: true },
  { from: "scenario", to: "chart", delay: 1.2, auto: true },
];
export const COMPARE_ROUTES: SignalRoute[] = [
  { from: "compare-a", to: "compare-axis", fromPort: "bottom", toPort: "top", delay: 0.1 },
  { from: "compare-b", to: "compare-axis", fromPort: "bottom", toPort: "top", delay: 0.25 },
  { from: "compare-axis", to: "compare-price", fromPort: "bottom", toPort: "top", delay: 1.1 },
];
export const HOW_ROUTES: SignalRoute[] = [
  { from: "how-0", to: "how-1", delay: 0.2, auto: true },
  { from: "how-1", to: "how-3", delay: 1.1, auto: true },
  { from: "how-2", to: "how-3", delay: 1.3, auto: true },
  { from: "how-3", to: "how-4", delay: 2.2, auto: true },
];
export const WORKSPACE_ROUTES: Record<Workspace, SignalRoute[]> = { buy: SCENARIO_ROUTES, sell: SCENARIO_ROUTES, compare: COMPARE_ROUTES, how: HOW_ROUTES };
export function emitNeuralSignal(kind: SignalKind, routes: SignalRoute[] = [], origin?: { x: number; y: number }) {
  window.dispatchEvent(new CustomEvent<NeuralSignal>(SIGNAL_EVENT, { detail: { kind, routes, origin, time: performance.now() } }));
}
