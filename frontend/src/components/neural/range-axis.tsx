"use client";

import { useEffect, useRef, useState } from "react";
import { formatEur, niceCeil } from "@/lib/predictions/scenarios";

export interface RangeAxisLane {
  key: string;
  label?: string;
  low: number;
  high: number;
  /** Amount typed by the user (price or offer). */
  amount?: number | null;
  /** Amount paid for the transfer (Vender). */
  paid?: number | null;
  market?: number | null;
  /** Central estimate (pred_fee_eur): the point the xValue Gap is measured from. */
  central?: number | null;
}

type MarkKind = "paid" | "amount" | "low" | "high";
interface Mark { kind: MarkKind; value: number; caption: string }

const ROW = 28, BAND = 26, GAP = 10;
const isNumber = (value: number | null | undefined): value is number => typeof value === "number";
/** Width of a one-line label, estimated from its text (13 px caption, 14 px bold value) plus padding. */
const labelWidth = (mark: Mark) => mark.caption.length * 6.9 + formatEur(mark.value).length * 8.6 + 26;

/**
 * Greedy row packing: each label goes into the first row where it does not
 * touch another. Labels grow away from the middle of the axis, so they never
 * leave it. Without a measured width every label gets its own row.
 */
function packRows(marks: Mark[], percent: (value: number) => number, width: number): number[] {
  const rows: Array<Array<[number, number]>> = [];
  return marks.map((mark) => {
    const position = percent(mark.value) / 100 * width, size = labelWidth(mark);
    const span: [number, number] = percent(mark.value) < 50 ? [position, position + size] : [position - size, position];
    let row = width > 0 ? rows.findIndex((taken) => taken.every(([left, right]) => span[1] + GAP <= left || span[0] >= right + GAP)) : -1;
    if (row === -1) { rows.push([]); row = rows.length - 1; }
    rows[row].push(span);
    return row;
  });
}

/**
 * xValue range on a linear euro axis starting at €0. The band is the range with
 * marked limits; the entered amount (and the amount paid) are labelled above it,
 * the limits below. The market value is a secondary diamond on the band, named
 * in the legend. Every lane shares one scale that includes every visible value.
 */
export function RangeAxis({ lanes, amountLabel = "Importe introducido", slots = ["amount"], overlap, neural, className = "" }: {
  lanes: RangeAxisLane[]; amountLabel?: string; slots?: Array<"paid" | "amount">; overlap?: { low: number; high: number } | null; neural?: string; className?: string;
}) {
  const lanesRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const element = lanesRef.current; if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const values = lanes.flatMap((lane) => [lane.high, lane.amount ?? 0, lane.paid ?? 0, lane.market ?? 0]);
  const max = niceCeil(Math.max(...values) * 1.06);
  const percent = (value: number) => Math.max(0, Math.min(100, (value / max) * 100));
  const at = (value: number) => `${percent(value)}%`;
  const has = (key: "amount" | "paid" | "market") => lanes.some((lane) => isNumber(lane[key]));
  const singleMarket = lanes.length === 1 && isNumber(lanes[0].market) ? lanes[0].market : null;
  const singleCentral = lanes.length === 1 && isNumber(lanes[0].central) ? lanes[0].central : null;
  const description = lanes.map((lane) => [
    `${lane.label ? `${lane.label}: ` : ""}rango xValue con límite inferior ${formatEur(lane.low)} y límite superior ${formatEur(lane.high)}`,
    isNumber(lane.amount) ? `${amountLabel.toLowerCase()} ${formatEur(lane.amount)}` : "",
    isNumber(lane.paid) ? `importe pagado ${formatEur(lane.paid)}` : "",
    isNumber(lane.central) ? `estimación central ${formatEur(lane.central)}` : "",
    isNumber(lane.market) ? `valor de mercado ${formatEur(lane.market)}` : "",
  ].filter(Boolean).join(", ")).join("; ");

  return <figure className={`range-axis ${className}`} data-neural={neural} role="img" aria-label={`Escala lineal desde 0 € hasta ${formatEur(max)}. ${description}.`}>
    <div className="range-axis-lanes" ref={lanesRef} aria-hidden="true">
      {lanes.map((lane) => {
        const above: Mark[] = slots.flatMap((slot): Mark[] => slot === "paid"
          ? (isNumber(lane.paid) ? [{ kind: "paid", value: lane.paid, caption: "Importe pagado" }] : [])
          : (isNumber(lane.amount) ? [{ kind: "amount", value: lane.amount, caption: amountLabel }] : []));
        const below: Mark[] = [{ kind: "low", value: lane.low, caption: "Límite inferior" }, { kind: "high", value: lane.high, caption: "Límite superior" }];
        const aboveRows = packRows(above, percent, width), belowRows = packRows(below, percent, width);
        // One row stays reserved above the band, so it does not jump when the first amount is typed.
        const aboveCount = Math.max(slots.length ? 1 : 0, ...aboveRows.map((row) => row + 1));
        const belowCount = Math.max(1, ...belowRows.map((row) => row + 1));
        const bandTop = aboveCount * ROW, bandBottom = bandTop + BAND;
        const tag = (mark: Mark, top: number) => <span key={`${mark.kind}-tag`} className={`range-axis-tag is-${mark.kind} ${percent(mark.value) < 50 ? "is-start" : "is-end"}`} style={{ left: at(mark.value), top }}>
          <small>{mark.caption}</small> <strong>{formatEur(mark.value)}</strong>
        </span>;
        return <div className="range-axis-row" key={lane.key}>
          {lane.label && <span className="range-axis-label">{lane.label}</span>}
          <div className="range-axis-lane" style={{ height: bandBottom + belowCount * ROW + 2 }}>
            <span className="range-axis-track" style={{ top: bandTop + BAND / 2 }} />
            <span className="range-axis-band" style={{ top: bandTop, height: BAND, left: at(lane.low), width: `calc(${at(lane.high)} - ${at(lane.low)})` }} />
            {overlap && <span className="range-axis-overlap" style={{ top: bandTop, height: BAND, left: at(overlap.low), width: `calc(${at(overlap.high)} - ${at(overlap.low)})` }} />}
            <span className="range-axis-cap" style={{ left: at(lane.low), top: bandTop - 5, height: BAND + 10 }} />
            <span className="range-axis-cap" style={{ left: at(lane.high), top: bandTop - 5, height: BAND + 10 }} />
            {isNumber(lane.central) && <span className="range-axis-central" style={{ left: at(lane.central), top: bandTop + BAND / 2 }} />}
            {isNumber(lane.market) && <span className="range-axis-market" style={{ left: at(lane.market), top: bandTop + BAND / 2 }} />}
            {above.map((mark, index) => {
              const rowBottom = aboveRows[index] * ROW + ROW - 4;
              return [
                <span key={`${mark.kind}-guide`} className={`range-axis-guide is-${mark.kind}`} style={{ left: at(mark.value), top: rowBottom, height: bandBottom + 4 - rowBottom }} />,
                mark.kind === "amount" && <span key="amount-pin" className="range-axis-pin" style={{ left: at(mark.value), top: bandTop - 10 }} />,
                tag(mark, aboveRows[index] * ROW + 2),
              ];
            })}
            {below.map((mark, index) => [
              <span key={`${mark.kind}-guide`} className={`range-axis-guide is-${mark.kind}`} style={{ left: at(mark.value), top: bandBottom, height: belowRows[index] * ROW + 8 }} />,
              tag(mark, bandBottom + belowRows[index] * ROW + 5),
            ])}
          </div>
        </div>;
      })}
      <div className="range-axis-scale">
        {[0, .25, .5, .75, 1].map((step) => <span key={step} style={{ left: `${step * 100}%` }}>{formatEur(max * step)}</span>)}
      </div>
    </div>
    <ul className="range-axis-legend" aria-hidden="true">
      <li><i className="is-band" />Rango xValue</li>
      {has("amount") && <li><i className="is-amount" />{amountLabel}</li>}
      {has("paid") && <li><i className="is-paid" />Importe pagado</li>}
      {lanes.some((lane) => isNumber(lane.central)) && <li><i className="is-central" />Estimación central{singleCentral !== null ? `: ${formatEur(singleCentral)}` : ""}</li>}
      {has("market") && <li><i className="is-market" />Valor de mercado{singleMarket !== null ? `: ${formatEur(singleMarket)}` : ""}</li>}
      {overlap && <li><i className="is-overlap" />Importes comunes</li>}
      <li>Escala lineal desde 0 €</li>
    </ul>
  </figure>;
}
