"use client";

import { useEffect, useId, useRef, useState } from "react";
import { fetchPredictions } from "@/lib/predictions/client";
import { DEFAULT_QUERY, matchesSearch } from "@/lib/predictions/query";
import { displayName } from "@/lib/predictions/display";
import { formatEur } from "@/lib/predictions/scenarios";
import type { PredictionRecord } from "@/lib/predictions/types";

/** Records per request. The API pages through the whole catalogue, alphabetically. */
export const PICKER_PAGE_SIZE = 20;

interface Results { query: string; items: PredictionRecord[]; total: number }

const integer = (value: number) => value.toLocaleString("es-ES", { useGrouping: "always" });

/** Text typed into the closed field, which shows the selected record: only what the user inserted. */
function insertedText(shown: string, next: string): string {
  let start = 0;
  while (start < shown.length && start < next.length && shown[start] === next[start]) start++;
  let end = 0;
  while (end < shown.length - start && end < next.length - start && shown[shown.length - 1 - end] === next[next.length - 1 - end]) end++;
  return next.slice(start, next.length - end);
}

/**
 * Searchable combobox over every player–club observation. Results come from the
 * API in pages with «Cargar más», so the last record is reachable without
 * knowing its name. Each page is tied to the text it answers: Enter and «Cargar
 * más» never mix a page from an earlier search into the current one.
 */
export function PlayerPicker({ label, value, exclude, onChange }: { label: string; value: PredictionRecord; exclude?: PredictionRecord; onChange: (record: PredictionRecord) => void }) {
  const id = useId(), listId = `${id}-list`, statusId = `${id}-status`;
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [results, setResults] = useState<Results | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [more, setMore] = useState<{ query: string; state: "loading" | "error" } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const moreRequest = useRef<AbortController | null>(null);
  // Closed, the field names the selected player; its club is shown next to it by the card.
  const shownValue = displayName(value.playerName);

  // First page for the current text; a new text starts the pagination again.
  useEffect(() => {
    if (!open) return;
    moreRequest.current?.abort();
    const controller = new AbortController();
    const timer = setTimeout(() => {
      fetchPredictions({ ...DEFAULT_QUERY, search: text, offset: 0, limit: PICKER_PAGE_SIZE }, controller.signal)
        .then((page) => { setResults({ query: text, items: page.items, total: page.total }); setFailed(null); setActive(0); })
        .catch((error: unknown) => { if ((error as Error).name !== "AbortError") setFailed(text); });
    }, 150);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [open, text, attempt]);
  useEffect(() => () => moreRequest.current?.abort(), []);

  const current = results !== null && results.query === text ? results : null;
  const status = current ? "ready" : failed === text ? "error" : "loading";
  const options = (current?.items ?? []).filter((item) => item.id !== exclude?.id);
  const excludedHere = current !== null && exclude !== undefined && matchesSearch(exclude, current.query);
  const available = current ? current.total - (excludedHere ? 1 : 0) : 0;
  const hasMore = current !== null && current.items.length < current.total;
  const loadingMore = more?.query === text && more.state === "loading";
  const moreFailed = more?.query === text && more.state === "error";
  const activeIndex = Math.min(active, options.length - 1);
  const activeOption = activeIndex >= 0 ? options[activeIndex] : undefined;

  useEffect(() => {
    if (open && activeOption) document.getElementById(`${id}-${activeOption.id}`)?.scrollIntoView({ block: "nearest" });
  }, [open, activeOption, id]);

  const loadMore = () => {
    if (!current || !hasMore || loadingMore) return;
    moreRequest.current?.abort();
    const controller = new AbortController(); moreRequest.current = controller;
    const query = current.query, offset = current.items.length;
    setMore({ query, state: "loading" });
    fetchPredictions({ ...DEFAULT_QUERY, search: query, offset, limit: PICKER_PAGE_SIZE }, controller.signal)
      .then((page) => {
        // Appended only onto the same search and the same length it was asked for.
        setResults((previous) => previous && previous.query === query && previous.items.length === offset ? { query, items: [...previous.items, ...page.items], total: page.total } : previous);
        setMore(null);
      })
      .catch((error: unknown) => { if ((error as Error).name !== "AbortError") setMore({ query, state: "error" }); });
  };
  const close = () => { moreRequest.current?.abort(); setMore(null); setOpen(false); setText(""); };
  const choose = (record: PredictionRecord) => {
    if (record.id === exclude?.id) return;
    onChange(record); close(); inputRef.current?.blur();
  };
  const retry = () => { setFailed(null); setAttempt((count) => count + 1); };

  const onlyExcluded = current !== null && available === 0 && excludedHere;
  const counter = !current ? "" : onlyExcluded ? "El único registro que coincide ya está elegido en el otro lado." : available === 0 ? "Sin coincidencias." :
    `Mostrando ${integer(options.length)} de ${integer(available)} ${available === 1 ? "registro" : "registros"}${current.query.trim() ? ` para «${current.query.trim()}»` : ""}${excludedHere ? ", sin el registro elegido en el otro lado" : ""}.`;

  return <div className="neural-picker" onBlur={(event) => { if (open && !event.currentTarget.contains(event.relatedTarget as Node | null)) close(); }}
    onKeyDown={(event) => { if (event.key === "Escape" && open) { event.preventDefault(); close(); inputRef.current?.focus(); } }}>
    <label className="neural-eyebrow" htmlFor={id}>{label}</label>
    <div className="neural-picker-field">
      <input ref={inputRef} id={id} role="combobox" aria-expanded={open} aria-controls={listId} aria-autocomplete="list" aria-busy={open && status === "loading"} aria-describedby={open ? statusId : undefined}
        aria-activedescendant={open && activeOption ? `${id}-${activeOption.id}` : undefined}
        value={open ? text : shownValue} placeholder="Busca por nombre, club o liga" autoComplete="off"
        // Focus, a click or typing reopen it, also after Escape left the focus in the field.
        onFocus={() => { if (!open) { setOpen(true); setText(""); } }}
        onClick={() => { if (!open) { setOpen(true); setText(""); } }}
        onChange={(event) => {
          moreRequest.current?.abort(); setMore(null);
          setText(open ? event.target.value : insertedText(shownValue, event.target.value));
          setOpen(true); setActive(0);
        }}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault(); setOpen(true);
            // Past the last loaded option, the next page is fetched.
            if (activeIndex >= options.length - 1) loadMore(); else setActive(activeIndex + 1);
          } else if (event.key === "ArrowUp") { event.preventDefault(); setActive(Math.max(activeIndex - 1, 0)); }
          else if (event.key === "Enter" && open) { event.preventDefault(); if (activeOption) choose(activeOption); }
        }} />
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m6 9 6 6 6-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
    </div>
    {open && <div className="neural-picker-dropdown">
      <ul id={listId} role="listbox" className="neural-picker-list" aria-label={`Registros para ${label.toLowerCase()}`}>
        {options.map((option, index) => <li key={option.id} id={`${id}-${option.id}`} role="option" aria-selected={index === activeIndex} className={index === activeIndex ? "is-active" : ""}
          onMouseDown={(event) => event.preventDefault()} onMouseEnter={() => setActive(index)} onClick={() => choose(option)}>
          <span><strong>{displayName(option.playerName)}</strong><small>{option.club} · {option.league} · 2025/26</small></span><em>{formatEur(option.rangeLowEur)} – {formatEur(option.rangeHighEur)}</em>
        </li>)}
        {status === "loading" && <li className="neural-picker-empty" role="presentation">Buscando…</li>}
        {status === "error" && <li className="neural-picker-empty is-error" role="presentation">No se pudieron cargar los registros.</li>}
        {status === "ready" && options.length === 0 && <li className="neural-picker-empty" role="presentation">{onlyExcluded ? "El único registro que coincide ya está elegido en el otro lado." : "Sin coincidencias."}</li>}
      </ul>
      <div className="neural-picker-footer">
        <p id={statusId} role="status" aria-live="polite">{status === "loading" ? "Buscando…" : status === "error" ? "Error al cargar los registros." : moreFailed ? "No se pudo cargar la página siguiente." : counter}</p>
        {status === "error" && <button type="button" onMouseDown={(event) => event.preventDefault()} onClick={retry}>Reintentar</button>}
        {status === "ready" && hasMore && <button type="button" onMouseDown={(event) => event.preventDefault()} onClick={loadMore} disabled={loadingMore}>{loadingMore ? "Cargando…" : moreFailed ? "Reintentar" : `Cargar más (${integer(Math.min(PICKER_PAGE_SIZE, current!.total - current!.items.length))})`}</button>}
      </div>
    </div>}
  </div>;
}

/** Other observations with the same player name: without player_id they stay separate records. */
export function useNamesakes(record: PredictionRecord): PredictionRecord[] {
  const [namesakes, setNamesakes] = useState<{ id: string; items: PredictionRecord[] }>({ id: "", items: [] });
  useEffect(() => {
    const controller = new AbortController();
    fetchPredictions({ ...DEFAULT_QUERY, search: record.playerName, limit: 10 }, controller.signal)
      .then((page) => setNamesakes({ id: record.id, items: page.items.filter((item) => item.id !== record.id && item.playerName === record.playerName) }))
      .catch(() => {});
    return () => controller.abort();
  }, [record.id, record.playerName]);
  return namesakes.id === record.id ? namesakes.items : [];
}
