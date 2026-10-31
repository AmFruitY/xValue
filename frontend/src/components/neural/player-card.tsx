import { displayName } from "@/lib/predictions/display";
import { describeGapShort, formatEur } from "@/lib/predictions/scenarios";
import type { PredictionRecord } from "@/lib/predictions/types";
import { PlayerPicker } from "./player-picker";

/** Range multiplier as shown to the user, e.g. "2,6". */
export const factor = (value: number) => value.toLocaleString("es-ES", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/**
 * The player panel of Comprar and Vender: the search field names the selected
 * record, followed by its club, league, age, season, xValue range and the
 * figures behind the xValue Gap (central estimate, market value, Gap).
 */
export function PlayerCard({ record, namesakes, onSelect }: { record: PredictionRecord; namesakes: PredictionRecord[]; onSelect: (record: PredictionRecord) => void }) {
  const market = record.marketValueEur;
  return <article className="xv-panel xv-player" data-neural="range" aria-label={`Jugador: ${displayName(record.playerName)}, ${record.club}, temporada 2025/26`}>
    <PlayerPicker label="JUGADOR" value={record} onChange={onSelect} />
    <ul className="xv-chips">
      <li>Club en 2025/26: {record.club}</li>
      <li>{record.league}</li>
      {record.age !== null && <li>{record.age} años</li>}
    </ul>
    {namesakes.length > 0 && <p className="xv-note">{namesakes.length + 1} registros con este nombre ({[record, ...namesakes].map((item) => item.club).join(" y ")}); cada uno con su estimación.</p>}
    <div className="xv-range">
      <span className="neural-eyebrow">RANGO xVALUE 2025/26</span>
      <strong>Entre {formatEur(record.rangeLowEur)} y {formatEur(record.rangeHighEur)}</strong>
    </div>
    <dl className="xv-figures">
      <div><dt>Estimación central</dt><dd>{formatEur(record.centralEur)}</dd></div>
      <div><dt>Valor de mercado</dt><dd className={market === null ? "is-missing" : ""}>{market === null ? "No disponible" : formatEur(market)}</dd></div>
      <div><dt>xValue Gap</dt><dd className={record.gapEur === null ? "is-missing" : ""}>{record.gapEur === null ? "Sin valor de mercado" : describeGapShort(record.gapEur)}</dd></div>
    </dl>
  </article>;
}
