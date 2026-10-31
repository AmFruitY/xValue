"use client";

import { useState } from "react";
import { describePosition, grossMargin, parseMillions, type PositionText } from "@/lib/predictions/scenarios";
import type { PredictionRecord } from "@/lib/predictions/types";
import { AmountField } from "./amount-field";
import { PlayerCard } from "./player-card";
import { useNamesakes } from "./player-picker";
import { RangeAxis } from "./range-axis";

/** One line of secondary context: the state is visible, the distances open on demand. */
function ContextItem({ label, text }: { label: string; text: PositionText }) {
  return <li><details>
    <summary><span>{label}:</span> <strong>{text.title}</strong></summary>
    <p>{text.main} {text.detail}</p>
  </details></li>;
}

/**
 * Vender: gross margin of an offer against what was paid. The range estimates
 * the transfer to the current club, so it situates the offer and the amount
 * paid; it is never turned into a resale margin.
 */
export function SellWorkspace({ record, onSelect }: { record: PredictionRecord; onSelect: (record: PredictionRecord) => void }) {
  const [offer, setOffer] = useState("");
  const [paid, setPaid] = useState("");
  const offerInput = parseMillions(offer), paidInput = parseMillions(paid, { allowZero: true });
  const offerAmount = offerInput.status === "ok" ? offerInput.value : null;
  const paidAmount = paidInput.status === "ok" ? paidInput.value : null;
  const namesakes = useNamesakes(record);
  const low = record.rangeLowEur, high = record.rangeHighEur;

  const margin = offerAmount !== null && paidAmount !== null ? grossMargin(offerAmount, paidAmount) : null;
  const offerPosition = offerAmount === null ? null : describePosition(offerAmount, low, high, "La oferta");
  // A free arrival has no transfer to compare with the range.
  const paidPosition = paidAmount !== null && paidAmount > 0 ? describePosition(paidAmount, low, high, "El importe pagado") : null;

  return <div className="xv-workspace xv-task">
    <PlayerCard record={record} namesakes={namesakes} onSelect={onSelect} />
    <section className="xv-panel xv-scenario" data-neural="scenario" aria-label="Margen bruto de la oferta">
      <h2 className="neural-eyebrow">OFERTA Y LO PAGADO</h2>
      <div className="xv-amount-row">
        <AmountField label="Oferta de venta (M€)" help="0,3 = 300.000 €" value={offer} parsed={offerInput} onChange={setOffer} />
        <AmountField label="Importe pagado (M€) — opcional" help="0 si no se pagó traspaso" value={paid} parsed={paidInput} onChange={setPaid} />
      </div>
      <div className="xv-result" aria-live="polite">
        {margin ? <>
          <span className="xv-label">MARGEN BRUTO DE LA OFERTA</span>
          <p className="xv-result-figure">{margin.formatted}</p>
          <p className="xv-result-detail">{margin.note}</p>
        </> : offerPosition ? <>
          <span className="xv-label">LA OFERTA FRENTE AL RANGO xVALUE</span>
          <span className={`xv-position is-${offerPosition.position}`}>{offerPosition.title}</span>
          <p className="xv-result-main">{offerPosition.main}</p>
          <p className="xv-result-detail">{offerPosition.detail} Añade el importe pagado para calcular el margen bruto.</p>
        </> : offerInput.status === "empty" && <p className="xv-result-empty">Introduce una oferta de venta para ver el resultado.</p>}
      </div>
      {(margin && offerPosition) || paidPosition ? <ul className="xv-context">
        {margin && offerPosition && <ContextItem label="Oferta frente al rango" text={offerPosition} />}
        {paidPosition && <ContextItem label={`Importe pagado frente al rango de su traspaso a ${record.club}`} text={paidPosition} />}
      </ul> : null}
    </section>
    <section className="xv-panel xv-chart" data-neural="chart" aria-label="Rango xValue, oferta e importe pagado">
      <h2 className="neural-eyebrow">RANGO xVALUE, OFERTA Y LO PAGADO</h2>
      <RangeAxis lanes={[{ key: record.id, low, high, amount: offerAmount, paid: paidAmount, market: record.marketValueEur, central: record.centralEur }]} amountLabel="Oferta de venta" slots={["paid", "amount"]} />
    </section>
  </div>;
}
