"use client";

import { useState } from "react";
import { displayName } from "@/lib/predictions/display";
import { describeGap, describeOverlap, describePositionShort, describePriceDifference, formatEur, parseMillions, rangeOverlap } from "@/lib/predictions/scenarios";
import type { PredictionRecord } from "@/lib/predictions/types";
import { AmountField } from "./amount-field";
import { PlayerPicker } from "./player-picker";
import { RangeAxis } from "./range-axis";

type Side = "a" | "b";

/**
 * Two observations on one scale. Overlap is chart context, not a verdict, and
 * the price difference depends only on the prices entered. No winner is assigned.
 */
export function CompareWorkspace({ left, right, onChange, onSwap }: { left: PredictionRecord; right: PredictionRecord; onChange: (side: Side, record: PredictionRecord) => void; onSwap: () => void }) {
  const [prices, setPrices] = useState<Record<Side, string>>({ a: "", b: "" });
  const parsed = { a: parseMillions(prices.a), b: parseMillions(prices.b) };
  const amounts = { a: parsed.a.status === "ok" ? parsed.a.value : null, b: parsed.b.status === "ok" ? parsed.b.value : null };
  const sameName = left.playerName === right.playerName;
  const names = { a: displayName(left.playerName), b: displayName(right.playerName) };
  const labels = { a: sameName ? `${names.a} (${left.club})` : names.a, b: sameName ? `${names.b} (${right.club})` : names.b };
  const overlap = rangeOverlap(left.rangeLowEur, left.rangeHighEur, right.rangeLowEur, right.rangeHighEur);
  const shared = overlap.kind === "shared" ? { low: overlap.low, high: overlap.high } : overlap.kind === "touch" ? { low: overlap.at, high: overlap.at } : null;
  const invalid = parsed.a.status === "invalid" ? parsed.a : parsed.b.status === "invalid" ? parsed.b : null;
  const records: Array<[Side, PredictionRecord, PredictionRecord]> = [["a", left, right], ["b", right, left]];

  return <div className="xv-workspace">
    <div className="xv-compare">
      {records.map(([side, record, other]) => {
        const gap = record.marketValueEur !== null && record.gapEur !== null ? describeGap(record.gapEur, record.gapLowEur, record.gapHighEur) : null;
        return <article key={side} className="xv-panel xv-compare-side" data-neural={`compare-${side}`}>
          <PlayerPicker label={`JUGADOR ${side.toUpperCase()}`} value={record} exclude={other} onChange={(next) => onChange(side, next)} />
          <ul className="xv-chips">
            <li>Club en 2025/26: {record.club}</li>
            <li>{record.league}</li>
            {record.age !== null && <li>{record.age} años</li>}
          </ul>
          <div className="xv-range is-compact">
            <span className="neural-eyebrow">RANGO xVALUE 2025/26</span>
            <strong>Entre {formatEur(record.rangeLowEur)} y {formatEur(record.rangeHighEur)}</strong>
            <p>Estimación central: <strong className="xv-central">{formatEur(record.centralEur)}</strong></p>
          </div>
          <AmountField label={`Precio de compra de ${side.toUpperCase()} (M€) — opcional`} help="En millones: 0,3 = 300.000 €" value={prices[side]} parsed={parsed[side]} onChange={(value) => setPrices((current) => ({ ...current, [side]: value }))} />
          <div className="xv-compare-market">
            <span className="xv-label">REFERENCIA DE MERCADO</span>
            <p>Valor de mercado: <strong className={record.marketValueEur === null ? "is-missing" : ""}>{record.marketValueEur === null ? "No disponible" : formatEur(record.marketValueEur)}</strong></p>
            <p>{gap ? `xValue Gap: ${gap.main.charAt(0).toLowerCase()}${gap.main.slice(1, -1)} (calculado con la estimación central, no con los extremos del rango).` : "Sin valor de mercado no se calcula el xValue Gap."}</p>
            {gap?.limits && <p className="xv-compare-detail">{gap.limits}</p>}
          </div>
        </article>;
      })}
      <button type="button" className="neural-swap" onClick={() => { setPrices((current) => ({ a: current.b, b: current.a })); onSwap(); }} aria-label="Intercambiar jugadores A y B"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 8h15m-4-4 4 4-4 4M20 16H5m4-4-4 4 4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg></button>
    </div>
    {sameName && <p className="xv-note">Los dos registros comparten nombre ({left.club} y {right.club}). Sin identificador de jugador, cada uno es una observación distinta con su propia estimación; se distinguen por el club.</p>}

    <section className="xv-panel" data-neural="compare-axis" aria-label="Rangos xValue en la misma escala">
      <h2 className="neural-eyebrow">RANGOS xVALUE EN LA MISMA ESCALA</h2>
      <RangeAxis amountLabel="Precio de compra" overlap={shared} lanes={records.map(([side, record]) => ({ key: side, label: labels[side], low: record.rangeLowEur, high: record.rangeHighEur, amount: amounts[side], market: record.marketValueEur, central: record.centralEur }))} />
      <p className="xv-footnote">{describeOverlap(overlap, labels.a, labels.b)}</p>
    </section>

    <section className="xv-panel xv-price" data-neural="compare-price" aria-label="Diferencia de precio">
      <h2 className="neural-eyebrow">DIFERENCIA DE PRECIO</h2>
      <div aria-live="polite">
        {amounts.a !== null && amounts.b !== null
          ? <p className="xv-result-main">{describePriceDifference(labels.a, amounts.a, labels.b, amounts.b)}</p>
          : <p className="xv-result-empty">{invalid ? "Revisa los importes: deben ser mayores que 0 y de hasta 1.000 M€." : "Introduce los dos precios de compra para comparar el importe de traspaso."}</p>}
        {(amounts.a !== null || amounts.b !== null) && <ul className="xv-context">
          {records.filter(([side]) => amounts[side] !== null).map(([side, record]) => <li key={side}><strong>{labels[side]}:</strong> {describePositionShort(amounts[side]!, record.rangeLowEur, record.rangeHighEur)}</li>)}
        </ul>}
      </div>
      <p className="xv-footnote">Solo el importe de traspaso introducido; no incluye salarios, comisiones ni otros gastos.</p>
    </section>
    <p className="neural-list-note">Comparación económica y de perfil. Los datos no incluyen posición ni rendimiento deportivo. La comparación no ordena a los jugadores por conveniencia.</p>
  </div>;
}
