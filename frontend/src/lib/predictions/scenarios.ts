/**
 * Calculations and wording for Comprar, Vender and Comparar.
 *
 * Pure functions with no imports, so they run unchanged in the browser and under
 * `node --test`. Amounts are euros at full precision; rounding happens only when
 * a value is turned into text. Every text describes arithmetic against the
 * model's range or a reference: none of them recommends buying or selling.
 */

const MILLION = 1_000_000;
/** Largest amount accepted in an input, in millions of euros. */
export const MAX_INPUT_MILLIONS = 1000;

const millions = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const euros = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0, useGrouping: "always" });

/** "14,6 M€" from one million upwards, otherwise euros rounded to thousands ("480.000 €"). */
export function formatEur(value: number): string {
  const absolute = Math.abs(value);
  const text = absolute >= MILLION ? `${millions.format(absolute / MILLION)} M€` : `${euros.format(Math.round(absolute / 1000) * 1000)} €`;
  return `${value < 0 ? "−" : ""}${text}`;
}

/** Like formatEur, but a difference that is not zero is never shown as zero. */
export function formatDifference(value: number): string {
  if (value !== 0 && Math.abs(value) < 1000) return `${value < 0 ? "−" : ""}menos de 1.000 €`;
  return formatEur(value);
}

export type AmountInput =
  | { status: "empty" }
  | { status: "invalid"; message: string }
  | { status: "ok"; value: number };

/** Reads an amount typed in millions of euros ("0,3" = 300.000 €). */
export function parseMillions(text: string, options: { allowZero?: boolean } = {}): AmountInput {
  const trimmed = text.trim();
  if (!trimmed) return { status: "empty" };
  const number = Number(trimmed.replace(",", "."));
  if (!Number.isFinite(number)) return { status: "invalid", message: "Escribe el importe con números, en millones de euros." };
  if (number < 0 || (number === 0 && !options.allowZero)) {
    return { status: "invalid", message: options.allowZero ? "El importe debe ser 0 o mayor." : "Introduce un importe mayor que 0." };
  }
  if (number > MAX_INPUT_MILLIONS) return { status: "invalid", message: `Introduce un importe de hasta ${MAX_INPUT_MILLIONS.toLocaleString("es-ES", { useGrouping: "always" })} M€.` };
  // Whole euros: "16,173467" must equal 16.173.467 €, not 16.173.467,000000002 €.
  return { status: "ok", value: Math.round(number * MILLION) };
}

export type RangePosition = "below" | "inside" | "above";

/** Where an amount falls against [low, high]. A limit itself counts as inside. */
export function positionInRange(amount: number, low: number, high: number): RangePosition {
  return amount < low ? "below" : amount > high ? "above" : "inside";
}

export const POSITION_TITLES: Record<RangePosition, string> = {
  below: "Por debajo del rango",
  inside: "Dentro del rango",
  above: "Por encima del rango",
};

export interface PositionText { position: RangePosition; title: string; main: string; detail: string }

/**
 * Full description of an amount against the xValue range. `subject` opens the
 * sentence ("El precio", "La oferta"); `insideNote` is added when it falls inside.
 */
export function describePosition(amount: number, low: number, high: number, subject: string, insideNote = ""): PositionText {
  const position = positionInRange(amount, low, high);
  if (position === "below") {
    return { position, title: POSITION_TITLES.below, main: `${subject} está ${formatDifference(low - amount)} por debajo del límite inferior.`, detail: `Distancia al límite superior: ${formatDifference(high - amount)}.` };
  }
  if (position === "above") {
    return { position, title: POSITION_TITLES.above, main: `${subject} está ${formatDifference(amount - high)} por encima del límite superior.`, detail: `Distancia al límite inferior: ${formatDifference(amount - low)}.` };
  }
  const detail = amount === low ? `Coincide con el límite inferior. Distancia al límite superior: ${formatDifference(high - amount)}.`
    : amount === high ? `Coincide con el límite superior. Distancia al límite inferior: ${formatDifference(amount - low)}.`
    : `Distancia al límite inferior: ${formatDifference(amount - low)} · al límite superior: ${formatDifference(high - amount)}.`;
  return { position, title: POSITION_TITLES.inside, main: `${subject} está entre los límites estimados.${insideNote ? ` ${insideNote}` : ""}`, detail };
}

/** One-line version for Comparar: "el precio está 2,0 M€ por debajo del límite inferior de su rango." */
export function describePositionShort(amount: number, low: number, high: number): string {
  const position = positionInRange(amount, low, high);
  if (position === "below") return `el precio está ${formatDifference(low - amount)} por debajo del límite inferior de su rango.`;
  if (position === "above") return `el precio está ${formatDifference(amount - high)} por encima del límite superior de su rango.`;
  return "el precio está entre los límites de su rango.";
}

/** Entered amount against the published market value, in words and without sign. */
export function describeMarketDifference(amount: number, marketValue: number, subject: string): string {
  if (amount === marketValue) return `${subject} coincide con el valor de mercado.`;
  return amount > marketValue
    ? `${subject} es ${formatDifference(amount - marketValue)} superior al valor de mercado.`
    : `${subject} es ${formatDifference(marketValue - amount)} inferior al valor de mercado.`;
}

export interface GapText { main: string; limits: string | null }

/**
 * xValue Gap as delivered by the model output: gap = central − market value,
 * gapLow / gapHigh = each range limit − market value. Expressed in words.
 */
export function describeGap(gap: number, gapLow: number | null, gapHigh: number | null): GapText {
  const main = gap === 0 ? "La estimación central de xValue coincide con el valor de mercado."
    : `La estimación central de xValue está ${formatDifference(Math.abs(gap))} ${gap > 0 ? "por encima" : "por debajo"} del valor de mercado.`;
  if (gapLow === null || gapHigh === null) return { main, limits: null };
  if (gapLow > 0) return { main, limits: `Con los límites del rango, la diferencia va de ${formatDifference(gapLow)} a ${formatDifference(gapHigh)} por encima del valor de mercado.` };
  if (gapHigh < 0) return { main, limits: `Con los límites del rango, la diferencia va de ${formatDifference(-gapHigh)} a ${formatDifference(-gapLow)} por debajo del valor de mercado.` };
  const lower = gapLow === 0 ? "coincide con el límite inferior" : `está ${formatDifference(-gapLow)} sobre el límite inferior`;
  const upper = gapHigh === 0 ? "coincide con el límite superior" : `${formatDifference(gapHigh)} bajo el superior`;
  return { main, limits: `El valor de mercado queda dentro del rango: ${lower} y ${upper}.` };
}

/** Short form of the xValue Gap for compact panels: "16,3 M€ por encima del valor de mercado". */
export function describeGapShort(gap: number): string {
  if (gap === 0) return "Igual al valor de mercado";
  return `${formatDifference(Math.abs(gap))} ${gap > 0 ? "por encima" : "por debajo"} del valor de mercado`;
}

export interface MarginText { value: number; formatted: string; note: string }

/** Gross margin of an offer: offer − amount paid for the transfer. It can be negative. */
export function grossMargin(offer: number, paid: number): MarginText {
  const value = offer - paid;
  const note = value < 0 ? "La oferta es inferior al importe pagado."
    : value === 0 ? "La oferta iguala el importe pagado."
    : paid === 0 ? "Sin importe de traspaso pagado, el margen bruto coincide con la oferta."
    : "Oferta de venta menos importe pagado por el traspaso.";
  return { value, formatted: formatDifference(value), note };
}

export type Overlap =
  | { kind: "shared"; low: number; high: number }
  | { kind: "touch"; at: number }
  | { kind: "disjoint"; higher: "a" | "b" };

export function rangeOverlap(aLow: number, aHigh: number, bLow: number, bHigh: number): Overlap {
  const low = Math.max(aLow, bLow), high = Math.min(aHigh, bHigh);
  if (low < high) return { kind: "shared", low, high };
  if (low === high) return { kind: "touch", at: low };
  return { kind: "disjoint", higher: aLow > bHigh ? "a" : "b" };
}

/** Overlap is context for the chart: it never implies equal value or sporting equivalence. */
export function describeOverlap(overlap: Overlap, labelA: string, labelB: string): string {
  if (overlap.kind === "shared") return `Los rangos comparten importes entre ${formatEur(overlap.low)} y ${formatEur(overlap.high)}. Esto no implica que los jugadores tengan el mismo valor ni que sean equivalentes deportivamente.`;
  if (overlap.kind === "touch") return `Los rangos coinciden únicamente en ${formatEur(overlap.at)}.`;
  const [higher, lower] = overlap.higher === "a" ? [labelA, labelB] : [labelB, labelA];
  return `El rango de ${higher} queda completamente por encima del de ${lower}.`;
}

/** Transfer-fee difference between two entered prices; it depends only on those prices. */
export function describePriceDifference(labelA: string, priceA: number, labelB: string, priceB: number): string {
  if (priceA === priceB) return "Ambos precios de traspaso coinciden.";
  const [cheaper, dearer] = priceA > priceB ? [labelB, labelA] : [labelA, labelB];
  return `Con los precios introducidos, fichar a ${cheaper} supondría ${formatDifference(Math.abs(priceA - priceB))} menos en importe de traspaso que fichar a ${dearer}.`;
}

/** Rounds an axis end up to a round step × 10^n so the scale reads cleanly. */
export function niceCeil(value: number): number {
  if (!(value > 0)) return 1;
  const power = 10 ** Math.floor(Math.log10(value)), unit = value / power;
  return ([1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].find((step) => unit <= step) ?? 10) * power;
}
