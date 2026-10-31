"use client";

import { useEffect, useRef } from "react";
import { SIGNAL_EVENT, WORKSPACE_ROUTES, type NeuralSignal, type Port, type SignalRoute, type Workspace } from "./neural-signals";

interface Point { x: number; y: number }
interface Flight { route: SignalRoute; start: number; arrived: boolean }
const direction = { left: [-1, 0], right: [1, 0], top: [0, -1], bottom: [0, 1] };
const curvePoint = (a: Point, c: Point, d: Point, b: Point, t: number) => { const s = 1 - t; return { x: s ** 3 * a.x + 3 * s ** 2 * t * c.x + 3 * s * t ** 2 * d.x + t ** 3 * b.x, y: s ** 3 * a.y + 3 * s ** 2 * t * c.y + 3 * s * t ** 2 * d.y + t ** 3 * b.y }; };

export function SignalConnections({ workspace }: { workspace: Workspace }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current, root = canvas?.closest<HTMLElement>(".neural-demo"), context = canvas?.getContext("2d");
    if (!canvas || !root || !context) return;
    const preference = matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0, last = 0, width = 0, height = 0, flights: Flight[] = [], disposed = false;
    const timers = new Map<HTMLElement, ReturnType<typeof setTimeout>>();
    const baseline = WORKSPACE_ROUTES[workspace];
    const find = (id: string) => root.querySelector<HTMLElement>(`[data-neural="${id}"]`);
    const endpoint = (rect: DOMRect, port: Port, parent: DOMRect): Point => ({ x: (port === "left" ? rect.left - 5 : port === "right" ? rect.right + 5 : rect.left + rect.width / 2) - parent.left, y: (port === "top" ? rect.top - 6 : port === "bottom" ? rect.bottom + 6 : rect.top + rect.height / 2) - parent.top });
    // The avatar sits top right: in Comprar and Vender it points at the right-most panel of the first row
    // (the chart in three columns, the scenario in two, the card when stacked), never across another panel.
    const avatarTarget = () => {
      const panels = ["range", "scenario", "chart"].map(find).filter((element): element is HTMLElement => element !== null);
      const top = Math.min(...panels.map((element) => element.getBoundingClientRect().top));
      return panels.filter((element) => element.getBoundingClientRect().top <= top + 4).sort((a, b) => b.getBoundingClientRect().left - a.getBoundingClientRect().left)[0] ?? null;
    };
    const panelBetween = (sourceRect: DOMRect, targetRect: DOMRect, source: HTMLElement, destination: HTMLElement) => {
      const [upper, lower] = sourceRect.top < targetRect.top ? [sourceRect, targetRect] : [targetRect, sourceRect];
      const x = (upper.left + upper.right) / 2;
      return [...root.querySelectorAll<HTMLElement>(".neural-workspace [data-neural]")].some((element) => {
        if (element === source || element === destination || element.contains(source) || element.contains(destination)) return false;
        const rect = element.getBoundingClientRect();
        return rect.left < x && rect.right > x && rect.top >= upper.bottom - 4 && rect.bottom <= lower.top + 4;
      });
    };
    const resolve = (route: SignalRoute) => {
      const source = find(route.from), destination = route.from === "avatar" && route.to === "chart" ? avatarTarget() : find(route.to); if (!source || !destination) return null;
      const parent = root.getBoundingClientRect(), sourceRect = source.getBoundingClientRect(), targetRect = destination.getBoundingClientRect();
      let fromPort = route.fromPort ?? "right", toPort = route.toPort ?? "left";
      // Stacked compare profiles: the avatar reaches B along the left gutter instead of crossing A.
      if (route.from === "avatar" && route.to === "compare-b" && (find("compare-b")?.getBoundingClientRect().top ?? 0) > (find("compare-a")?.getBoundingClientRect().bottom ?? 0) - 4) { fromPort = "left"; toPort = "left"; }
      // Stacked compare profiles: A reaches the axis along the left gutter instead of crossing B.
      if (route.from === "compare-a" && route.to === "compare-axis" && (find("compare-b")?.getBoundingClientRect().top ?? 0) > sourceRect.bottom - 4) { fromPort = "left"; toPort = "left"; }
      let betweenColumns = false;
      if (route.auto) {
        const sameRow = Math.abs(sourceRect.top - targetRect.top) < 100;
        // Neighbouring columns of different heights are side by side even when their tops differ.
        const sideBySide = targetRect.left >= sourceRect.right - 4 || sourceRect.left >= targetRect.right - 4;
        const adjacent = Math.abs(targetRect.left - sourceRect.right) < sourceRect.width * .5 || Math.abs(sourceRect.left - targetRect.right) < sourceRect.width * .5;
        if (sameRow) [fromPort, toPort] = adjacent ? (targetRect.left > sourceRect.left ? ["right", "left"] : ["left", "right"]) : ["top", "top"];
        else if (sideBySide) { [fromPort, toPort] = targetRect.left > sourceRect.left ? ["right", "left"] : ["left", "right"]; betweenColumns = true; }
        // Stacked with another panel in the vertical corridor between them: along the left gutter instead of through it.
        else if (panelBetween(sourceRect, targetRect, source, destination)) [fromPort, toPort] = ["left", "left"];
        else [fromPort, toPort] = ["bottom", "top"];
      }
      const a = endpoint(sourceRect, fromPort, parent), b = endpoint(targetRect, toPort, parent);
      const distance = Math.hypot(a.x - b.x, a.y - b.y), bend = fromPort === toPort ? Math.min(fromPort === "top" ? 30 : 35, Math.max(18, distance * (fromPort === "top" ? .14 : .08))) : Math.min(85, Math.max(18, distance * .33));
      const c = { x: a.x + direction[fromPort][0] * bend, y: a.y + direction[fromPort][1] * bend }, d = { x: b.x + direction[toPort][0] * bend, y: b.y + direction[toPort][1] * bend };
      // Row-to-card signals travel through the outer gutter, not across other rows.
      if (route.from.startsWith("row-")) { c.x = d.x = Math.max(a.x, b.x) + 18; }
      // Columns at different heights: run down the gap between them instead of across their content.
      if (betweenColumns) { c.x = d.x = (a.x + b.x) / 2; c.y = a.y; d.y = b.y; }
      return { a, b, c, d, source, destination };
    };
    const light = (element: HTMLElement) => { clearTimeout(timers.get(element)); element.dataset.neuralLit = "true"; timers.set(element, setTimeout(() => { delete element.dataset.neuralLit; timers.delete(element); }, 1200)); };
    function draw(now: number) {
      if (!context) return;
      context.clearRect(0, 0, width, height);
      baseline.forEach((route) => {
        const path = resolve(route); if (!path) return;
        context.beginPath(); context.moveTo(path.a.x, path.a.y); context.bezierCurveTo(path.c.x, path.c.y, path.d.x, path.d.y, path.b.x, path.b.y);
        context.strokeStyle = "rgba(61,173,210,.25)"; context.lineWidth = .8; context.stroke();
        [path.a, path.b].forEach((point) => { context.fillStyle = "rgba(111,224,246,.5)"; context.beginPath(); context.arc(point.x, point.y, 1.7, 0, Math.PI * 2); context.fill(); });
      });
      flights = flights.filter((flight) => now - flight.start < 2000);
      flights.forEach((flight) => {
        const path = resolve(flight.route); if (!path) return;
        const age = (now - flight.start) / 1000; if (age < 0) return;
        const t = Math.min(1, age / .85), fade = age > .85 ? Math.max(0, 1 - (age - .85) / 1.1) : 1;
        if (t === 1 && !flight.arrived) { flight.arrived = true; light(path.destination); }
        context.beginPath(); context.moveTo(path.a.x, path.a.y); context.bezierCurveTo(path.c.x, path.c.y, path.d.x, path.d.y, path.b.x, path.b.y);
        context.strokeStyle = `rgba(63,206,244,${fade * .45})`; context.lineWidth = 1; context.stroke();
        context.beginPath(); for (let step = 0; step <= 12; step++) { const point = curvePoint(path.a, path.c, path.d, path.b, Math.max(0, t - .22 + step * .22 / 12)); if (step === 0) context.moveTo(point.x, point.y); else context.lineTo(point.x, point.y); }
        context.lineWidth = 2; context.strokeStyle = `rgba(163,244,255,${fade * .95})`; context.stroke();
        const point = curvePoint(path.a, path.c, path.d, path.b, t), glow = context.createRadialGradient(point.x, point.y, 0, point.x, point.y, 13); glow.addColorStop(0, `rgba(226,253,255,${fade})`); glow.addColorStop(.22, `rgba(74,213,255,${fade * .65})`); glow.addColorStop(1, "rgba(74,213,255,0)"); context.fillStyle = glow; context.fillRect(point.x - 13, point.y - 13, 26, 26);
        if (t === 1) { context.beginPath(); context.arc(point.x, point.y, 4 + (age - .85) * 15, 0, Math.PI * 2); context.lineWidth = .9; context.strokeStyle = `rgba(128,238,255,${fade * .65})`; context.stroke(); }
      });
      canvas!.dataset.routes = String(baseline.filter((route) => resolve(route)).length);
      canvas!.dataset.flights = String(flights.length);
    }
    const tick = (now: number) => { frame = 0; if (document.hidden) { flights = []; return; } if (now - last > 32) { last = now; draw(now); } if (flights.length && !preference.matches) frame = requestAnimationFrame(tick); };
    const refresh = () => { if (disposed) return; const rect = root.getBoundingClientRect(); width = rect.width; height = rect.height; const dpr = Math.min(devicePixelRatio || 1, 1.5); canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr); context.setTransform(dpr, 0, 0, dpr, 0, 0); draw(performance.now()); };
    const receive = (event: Event) => {
      const signal = (event as CustomEvent<NeuralSignal>).detail; if (!signal.routes.length) return;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => { if (disposed) return; refresh();
        if (preference.matches) { signal.routes.forEach((route) => { const path = resolve(route); if (path) light(path.destination); }); draw(performance.now()); return; }
        flights = signal.routes.map((route) => ({ route, start: performance.now() + (route.delay ?? 0) * 1000, arrived: false }));
        const source = find(signal.routes[0].from); if (source) light(source);
        canvas.dataset.signal = signal.kind; frame = requestAnimationFrame(tick);
      });
    };
    const motionChanged = () => { cancelAnimationFrame(frame); flights = []; refresh(); };
    const observer = new ResizeObserver(refresh); observer.observe(root);
    const mutation = new MutationObserver(() => { if (!flights.length) refresh(); }); mutation.observe(root.querySelector(".neural-workspace") ?? root, { childList: true, subtree: true });
    window.addEventListener(SIGNAL_EVENT, receive); window.addEventListener("resize", refresh); preference.addEventListener("change", motionChanged);
    refresh();
    return () => { disposed = true; cancelAnimationFrame(frame); observer.disconnect(); mutation.disconnect(); window.removeEventListener(SIGNAL_EVENT, receive); window.removeEventListener("resize", refresh); preference.removeEventListener("change", motionChanged); timers.forEach((timer, element) => { clearTimeout(timer); delete element.dataset.neuralLit; }); };
  }, [workspace]);
  return <canvas ref={canvasRef} className="neural-component-connections" aria-hidden="true" />;
}
