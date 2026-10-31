"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import gsap from "gsap";
import { displayName } from "@/lib/predictions/display";
import { formatEur } from "@/lib/predictions/scenarios";
import type { PredictionFacets, PredictionRecord } from "@/lib/predictions/types";
import { BuyWorkspace } from "./buy-workspace";
import { CompareWorkspace } from "./compare-workspace";
import { Footballer } from "./footballer";
import { HowItWorks } from "./how-it-works";
import { NeuralField } from "./synaptic-field";
import { NeuralWordmark } from "./neural-wordmark";
import { SellWorkspace } from "./sell-workspace";
import { SignalConnections } from "./signal-connections";
import { WORKSPACE_ROUTES, emitNeuralSignal, type SignalKind, type SignalRoute, type Workspace } from "./neural-signals";
import "./neural-demo.css";
import "./neural-results.css";

export interface NeuralDemoProps { facets: PredictionFacets; primary: PredictionRecord | null; secondary: PredictionRecord | null; loadError?: boolean }
const tabs: Array<{ id: Workspace; name: string }> = [{ id: "buy", name: "Comprar" }, { id: "sell", name: "Vender" }, { id: "compare", name: "Comparar" }, { id: "how", name: "Cómo funciona" }];
/** The three entry points of the intro; «Cómo funciona» stays a tab, not an entry. */
const entries: Array<{ id: Exclude<Workspace, "how">; name: string; description: string }> = [
  { id: "buy", name: "Comprar", description: "Sitúa un precio de compra frente al rango xValue del jugador." },
  { id: "sell", name: "Vender", description: "Calcula qué diferencia deja una oferta respecto a lo pagado." },
  { id: "compare", name: "Comparar", description: "Compara el rango xValue y el precio de traspaso de dos jugadores." },
];
/** Compact heading: a short title and one line, so the workspace fits a desktop screen without scrolling. */
const headings: Record<Workspace, { title: string; description: string }> = {
  buy: { title: "Comprar", description: "¿Dónde queda un precio de compra respecto al rango xValue del jugador en 2025/26?" },
  sell: { title: "Vender", description: "¿Qué diferencia deja una oferta respecto a lo pagado? La oferta también se sitúa frente al rango xValue." },
  compare: { title: "Comparar", description: "Rangos xValue y precios de traspaso de dos registros en una misma escala." },
  how: { title: "Cómo funciona", description: "Entiende las cifras y descubre cómo utilizarlas." },
};
const messages: Record<Workspace, string> = {
  buy: "Introduce un precio de compra y lo sitúo frente al rango xValue del jugador.",
  sell: "Introduce la oferta y lo que se pagó por el jugador para calcular el margen bruto.",
  compare: "Dos registros en la misma escala. Que los rangos se solapen no significa que valgan lo mismo.",
  how: "Descubre qué significa cada cifra y cómo usar Comprar, Vender y Comparar.",
};
const AVATAR_ROUTES: Record<Workspace, SignalRoute> = {
  // Each line ends at the first panel below the heading, so it never crosses a panel on its way.
  buy: { from: "avatar", to: "chart", fromPort: "bottom", toPort: "top" },
  sell: { from: "avatar", to: "chart", fromPort: "bottom", toPort: "top" },
  // B sits under the avatar side by side; stacked, the line keeps to the left gutter (signal-connections).
  compare: { from: "avatar", to: "compare-b", fromPort: "bottom", toPort: "top" },
  how: { from: "avatar", to: "how-flow", fromPort: "bottom", toPort: "top" },
};
const SIGNAL_KINDS: Record<Workspace, SignalKind> = { buy: "select", sell: "select", compare: "compare", how: "how" };
/** The avatar first, then the workspace's own relations. */
const workspaceRoutes = (next: Workspace, delay = 0): SignalRoute[] => [
  { ...AVATAR_ROUTES[next], delay },
  ...WORKSPACE_ROUTES[next].map((route) => ({ ...route, delay: (route.delay ?? 0) + delay + .25 })),
];

function Arrow() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 12h15m-6-6 6 6-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

export function NeuralDemo({ facets, primary, secondary, loadError = false }: NeuralDemoProps) {
  const [screen, setScreen] = useState<"intro" | "product">("intro");
  const [workspace, setWorkspace] = useState<Workspace>("buy");
  const [reducedMotion, setReducedMotion] = useState(false);
  const [player, setPlayer] = useState<PredictionRecord | null>(primary);
  const [left, setLeft] = useState<PredictionRecord | null>(primary);
  const [right, setRight] = useState<PredictionRecord | null>(secondary);
  const [avatar, setAvatar] = useState<{ message: string; event: number } | null>(null);
  const [avatarVisible, setAvatarVisible] = useState(false);
  const actorRef = useRef<HTMLDivElement>(null);
  const avatarRef = useRef<HTMLDivElement>(null);
  const flightRef = useRef<HTMLDivElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const transitionRef = useRef<gsap.core.Timeline | null>(null);
  const transitioning = useRef(false);
  const productRef = useRef<HTMLElement>(null);
  const signalFrame = useRef(0);

  useEffect(() => {
    const preference = matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(preference.matches);
    update(); preference.addEventListener("change", update);
    return () => { preference.removeEventListener("change", update); transitionRef.current?.kill(); cancelAnimationFrame(signalFrame.current); };
  }, []);

  // Signals wait two frames so the routes resolve against the freshly rendered DOM.
  const signal = useCallback((kind: SignalKind, routes: SignalRoute[]) => {
    cancelAnimationFrame(signalFrame.current);
    signalFrame.current = requestAnimationFrame(() => { signalFrame.current = requestAnimationFrame(() => emitNeuralSignal(kind, routes)); });
  }, []);
  const announce = useCallback((message: string, kind: SignalKind, routes: SignalRoute[] = []) => {
    setAvatar({ message, event: Date.now() }); setAvatarVisible(true);
    signal(kind, routes);
  }, [signal]);

  useEffect(() => {
    if (!avatar) return;
    const timer = setTimeout(() => setAvatarVisible(false), workspace === "how" ? 12000 : 7000);
    return () => clearTimeout(timer);
  }, [avatar, workspace]);

  /** Leaves the intro straight into the chosen option. The intro waits for a choice; it no longer advances on its own. */
  const enter = useCallback((next: Workspace) => {
    if (screen !== "intro" || transitioning.current) return;
    transitioning.current = true;
    const origin = actorRef.current?.getBoundingClientRect();
    setWorkspace(next);
    setScreen("product");
    announce(`Bienvenido a xValue. ${messages[next]}`, "welcome", workspaceRoutes(next, 1.15));
    requestAnimationFrame(() => {
      const destination = avatarRef.current?.getBoundingClientRect();
      const flight = flightRef.current;
      // The heading takes focus only if the user has not already moved into the product (e.g. into a search field).
      const finish = () => { transitioning.current = false; if (!productRef.current?.contains(document.activeElement)) headingRef.current?.focus({ preventScroll: true }); };
      if (reducedMotion || !origin || !destination || !flight) { finish(); return; }
      gsap.set(avatarRef.current, { opacity: 0 });
      transitionRef.current = gsap.timeline({ onComplete: () => { gsap.set(flight, { display: "none" }); gsap.set(avatarRef.current, { clearProps: "opacity" }); finish(); } })
        .fromTo(flight, { display: "block", left: origin.left, top: origin.top, width: origin.width, height: origin.height, opacity: 1 }, { left: destination.left, top: destination.top, width: destination.width, height: destination.height, duration: 1.12, ease: "power3.inOut" }, 0)
        .fromTo(productRef.current, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.65, ease: "power2.out", clearProps: "transform,opacity" }, 0.3);
    });
  }, [screen, reducedMotion, announce]);

  function switchWorkspace(next: Workspace) {
    setWorkspace(next);
    announce(messages[next], SIGNAL_KINDS[next], workspaceRoutes(next));
  }
  function choose(record: PredictionRecord) {
    setPlayer(record);
    announce(`${displayName(record.playerName)} · ${record.club}: rango xValue entre ${formatEur(record.rangeLowEur)} y ${formatEur(record.rangeHighEur)} para su traspaso en 2025/26.`, "select",
      [AVATAR_ROUTES.buy, ...WORKSPACE_ROUTES.buy.map((route) => ({ ...route, delay: (route.delay ?? 0) + .2 }))]);
  }
  function compare(side: "a" | "b", record: PredictionRecord) {
    if (side === "a") setLeft(record); else setRight(record);
    announce("Registros actualizados. Las cifras proceden de los resultados del modelo; no hay ganador.", "compare", [AVATAR_ROUTES.compare, ...WORKSPACE_ROUTES.compare.map((route) => ({ ...route, delay: (route.delay ?? 0) + .2 }))]);
  }
  function replay() {
    transitionRef.current?.kill(); transitioning.current = false;
    if (flightRef.current) gsap.set(flightRef.current, { display: "none" });
    setAvatarVisible(false); setWorkspace("buy"); setScreen("intro"); window.scrollTo({ top: 0, behavior: "instant" });
  }
  const heading = headings[workspace];

  return <div className={`neural-demo ${screen === "intro" ? "is-intro" : "is-product"} ${reducedMotion ? "motion-reduced" : ""}`}>
    <NeuralField quiet={screen === "product"} />
    {screen === "product" && <SignalConnections workspace={workspace} />}
    <div className="neural-atmosphere" aria-hidden="true" />
    {screen === "intro" ? <section className="neural-intro" aria-label="Presentación de xValue">
      <header className="neural-intro-header"><span className="neural-small-brand">xValue<span className="neural-brand-dot" /></span><span className="neural-edition">INTELIGENCIA DEL FÚTBOL / 03</span><button type="button" className="neural-skip" onClick={() => enter("how")}>Cómo funciona <Arrow /></button></header>
      <div className="neural-hero-layout">
        <div className="neural-hero-copy">
          <p className="neural-eyebrow"><span /> INTELIGENCIA VIVA APLICADA AL FÚTBOL</p>
          <NeuralWordmark />
          <h2>Cada conexión<br /><span>revela valor.</span></h2>
          <p className="neural-hero-description">Un rango de importe de traspaso para cada jugador en 2025/26.<br />Úsalo frente a un precio, una oferta u otro jugador.</p>
          <nav className="neural-entries" aria-label="¿Qué quieres analizar?">
            {entries.map((entry) => <button key={entry.id} type="button" className="neural-entry" onClick={() => enter(entry.id)}>
              <span><strong>{entry.name}</strong><small>{entry.description}</small></span><Arrow />
            </button>)}
          </nav>
          <div className="neural-hero-caption"><span className="neural-signal-dot" /> Resultados del modelo xValue · {facets.total ? `${facets.total.toLocaleString("es-ES", { useGrouping: "always" })} registros jugador–club · ` : ""}temporada 2025/26.</div>
        </div>
        <div className="neural-hero-scene" role="img" aria-label="Ilustración: futbolista holográfico en cian que controla un balón; impulsos decorativos recorren sus líneas">
          <div className="neural-scene-orbit" aria-hidden="true" /><div ref={actorRef} className="neural-hero-actor"><Footballer animated={!reducedMotion} /></div>
          <div className="neural-scene-label" aria-hidden="true"><span>01 / EL JUGADOR</span><span className="neural-scene-status"><i /> CONEXIÓN ACTIVA</span></div>
        </div>
      </div>
      <footer className="neural-intro-footer"><span>CONEXIONES <i>→</i> INFORMACIÓN <i>→</i> ESTIMACIÓN</span><div className="neural-intro-progress"><span>ELIGE UNA OPCIÓN PARA EMPEZAR</span></div></footer>
    </section> : <section ref={productRef} className="neural-product" aria-label="xValue: resultados del modelo">
      <header className="neural-product-header"><button type="button" className="neural-small-brand neural-home" onClick={replay} aria-label="xValue: volver a la presentación">xValue<span className="neural-brand-dot" /></button><nav aria-label="Opciones principales" role="tablist" onKeyDown={(event) => {
        if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        const current = tabs.findIndex((tab) => tab.id === workspace);
        const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
        switchWorkspace(tabs[next].id); document.getElementById(`tab-${tabs[next].id}`)?.focus();
      }}>{tabs.map((tab) => <button type="button" key={tab.id} id={`tab-${tab.id}`} role="tab" tabIndex={workspace === tab.id ? 0 : -1} aria-selected={workspace === tab.id} aria-controls={`panel-${tab.id}`} className={workspace === tab.id ? "is-selected" : ""} onClick={() => switchWorkspace(tab.id)}>{tab.name}</button>)}</nav><span className="neural-data-badge"><i /> RESULTADOS DEL MODELO · 2025/26</span></header>
      <main className="neural-product-main">
        <div className="neural-product-heading is-compact"><div><h1 ref={headingRef} tabIndex={-1}>{heading.title}</h1><p className="neural-heading-description">{heading.description}</p></div>
          {/* The small avatar stays; its message collapses when it is not speaking, so no empty area is reserved. */}
          <aside className={`neural-avatar-slot is-compact ${avatarVisible ? "is-visible" : ""}`} aria-label="Avatar de xValue"><div ref={avatarRef} className="neural-avatar-figure" data-neural="avatar"><Footballer compact animated={!reducedMotion} visible={avatarVisible} /></div><div className="neural-avatar-message"><p role="status" aria-live="polite" aria-atomic="true">{avatarVisible ? avatar?.message : ""}</p></div></aside>
        </div>
        <div role="tabpanel" id={`panel-${workspace}`} aria-labelledby={`tab-${workspace}`} className="neural-workspace" key={workspace}>
          {loadError && <p className="neural-empty" role="alert">No se pudieron leer los resultados del modelo. Comprueba que el archivo Parquet está disponible.</p>}
          {!loadError && workspace === "buy" && (player ? <BuyWorkspace record={player} onSelect={choose} /> : <p className="neural-empty">No hay registros disponibles.</p>)}
          {!loadError && workspace === "sell" && (player ? <SellWorkspace record={player} onSelect={choose} /> : <p className="neural-empty">No hay registros disponibles.</p>)}
          {!loadError && workspace === "compare" && (left && right ? <CompareWorkspace left={left} right={right} onChange={compare} onSwap={() => { setLeft(right); setRight(left); }} /> : <p className="neural-empty">Se necesitan al menos dos registros para comparar.</p>)}
          {!loadError && workspace === "how" && <HowItWorks />}
        </div>
        <footer className="neural-product-footer is-compact"><span>xValue aporta una referencia; la decisión corresponde al club.</span></footer>
      </main>
    </section>}
    <div ref={flightRef} className="neural-character-flight" aria-hidden="true"><Footballer animated={!reducedMotion} visible={screen === "product"} /></div>
  </div>;
}
