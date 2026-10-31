"use client";

import { useState } from "react";
import { describePosition, parseMillions } from "@/lib/predictions/scenarios";
import type { PredictionRecord } from "@/lib/predictions/types";
import { AmountField } from "./amount-field";
import { PlayerCard } from "./player-card";
import { useNamesakes } from "./player-picker";
import { RangeAxis } from "./range-axis";

const INSIDE_NOTE = "Estar dentro no basta para concluir que sea conveniente.";

/**
 * Comprar: where a purchase price falls against the xValue range. Player,
 * scenario and chart sit side by side so the whole task fits one desktop screen.
 */
export function BuyWorkspace({ record, onSelect }: { record: PredictionRecord; onSelect: (record: PredictionRecord) => void }) {
  const [price, setPrice] = useState("");
  const parsed = parseMillions(price);
  const amount = parsed.status === "ok" ? parsed.value : null;
  const namesakes = useNamesakes(record);
  const result = amount === null ? null : describePosition(amount, record.rangeLowEur, record.rangeHighEur, "El precio", INSIDE_NOTE);

  return <div className="xv-workspace xv-task">
    <PlayerCard record={record} namesakes={namesakes} onSelect={onSelect} />
    <section className="xv-panel xv-scenario" data-neural="scenario" aria-label="Precio de compra frente al rango xValue">
      <h2 className="neural-eyebrow">DIFERENCIA CON EL RANGO xVALUE</h2>
      <AmountField label="Precio de compra (M€)" help="Precio solicitado u oferta que valoras · 0,3 = 300.000 €" value={price} parsed={parsed} onChange={setPrice} />
      <div className="xv-result" aria-live="polite">
        {result ? <>
          <span className={`xv-position is-${result.position}`}>{result.title}</span>
          <p className="xv-result-main">{result.main}</p>
          <p className="xv-result-detail">{result.detail}</p>
        </> : parsed.status === "empty" && <p className="xv-result-empty">Introduce un importe para ver el resultado.</p>}
      </div>
    </section>
    <section className="xv-panel xv-chart" data-neural="chart" aria-label="Rango xValue y precio de compra">
      <h2 className="neural-eyebrow">RANGO xVALUE Y PRECIO</h2>
      <RangeAxis lanes={[{ key: record.id, low: record.rangeLowEur, high: record.rangeHighEur, amount, market: record.marketValueEur, central: record.centralEur }]} amountLabel="Precio de compra" />
    </section>
  </div>;
}
