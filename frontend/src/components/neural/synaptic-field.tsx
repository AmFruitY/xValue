"use client";

import { useEffect, useRef } from "react";
import { SIGNAL_EVENT, type NeuralSignal } from "./neural-signals";

interface Neuron { x: number; y: number; phase: number; depth: number; hub: boolean; links: number[]; activated: number }
interface Edge { a: number; b: number; bend: number }
interface Pulse { a: number; b: number; start: number; duration: number; hops: number; strength: number }
const clamp = (value: number) => Math.max(0, Math.min(1, value));

export function NeuralField({ quiet = false }: { quiet?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current, context = canvas?.getContext("2d");
    if (!canvas || !context) return;
    const motion = matchMedia("(prefers-reduced-motion: reduce)");
    let width = 0, height = 0, frame = 0, last = 0, time = 0, nextPulse = .5, seed = 42;
    let nodes: Neuron[] = [], edges: Edge[] = [], pulses: Pulse[] = [], positions: Array<{ x: number; y: number }> = [];
    let shock: { x: number; y: number; start: number } | null = null;
    const pointer = { x: -1000, y: -1000, strength: 0, target: 0 };
    let protectedAreas: DOMRect[] = [], lastAreas = 0;
    const random = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
    const connect = (a: number, b: number) => {
      if (a === b || nodes[a].links.includes(b)) return;
      nodes[a].links.push(b); nodes[b].links.push(a); edges.push({ a, b, bend: (random() - .5) * 60 });
    };
    const resize = () => {
      const rect = canvas.getBoundingClientRect(); width = rect.width; height = rect.height;
      const ratio = Math.min(devicePixelRatio || 1, 1.5); canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio); context.setTransform(ratio, 0, 0, ratio, 0, 0);
      seed = 42; nodes = []; edges = []; pulses = [];
      const hubs = width < 700 ? 14 : 30;
      for (let cluster = 0; cluster < hubs; cluster++) {
        const x = (cluster % 5 + .2 + random() * .7) / 5 * width, y = (Math.floor(cluster / 5) + .1 + random() * .8) / Math.ceil(hubs / 5) * height;
        const hub = nodes.length;
        nodes.push({ x, y, phase: random() * 6, depth: .7 + random() * .3, hub: true, links: [], activated: -10 });
        const branches = width < 700 ? 5 : 7;
        for (let branch = 0; branch < branches; branch++) {
          const angle = branch / branches * Math.PI * 2 + random() * .5, radius = 24 + random() * (width < 700 ? 57 : 90), index = nodes.length;
          nodes.push({ x: x + Math.cos(angle) * radius, y: y + Math.sin(angle) * radius, phase: random() * 6, depth: .3 + random() * .7, hub: false, links: [], activated: -10 }); connect(hub, index);
          if (branch % 2 === 0) { const end = nodes.length; nodes.push({ x: nodes[index].x + Math.cos(angle + .5) * radius * .65, y: nodes[index].y + Math.sin(angle + .5) * radius * .65, phase: random() * 6, depth: .2 + random() * .6, hub: false, links: [], activated: -10 }); connect(index, end); }
        }
      }
      const hubsList = nodes.map((node, i) => node.hub ? i : -1).filter((i) => i >= 0);
      hubsList.forEach((a) => { hubsList.filter((b) => b !== a).sort((b, c) => Math.hypot(nodes[a].x - nodes[b].x, nodes[a].y - nodes[b].y) - Math.hypot(nodes[a].x - nodes[c].x, nodes[a].y - nodes[c].y)).slice(0, 3).forEach((b) => connect(a, b)); });
      canvas.dataset.nodes = String(nodes.length); draw();
    };
    const activate = (index: number, strength = 1) => {
      if (!nodes[index]) return;
      nodes[index].activated = time;
      nodes[index].links.slice(0, 3).forEach((b, i) => pulses.push({ a: index, b, start: time + i * .11, duration: .65 + random() * .5, hops: 2, strength }));
    };
    const pointAt = (a: { x: number; y: number }, b: { x: number; y: number }, bend: number, t: number) => {
      const length = Math.max(1, Math.hypot(b.x - a.x, b.y - a.y)), cx = (a.x + b.x) / 2 - (b.y - a.y) / length * bend, cy = (a.y + b.y) / 2 + (b.x - a.x) / length * bend, inv = 1 - t;
      return { x: inv * inv * a.x + 2 * inv * t * cx + t * t * b.x, y: inv * inv * a.y + 2 * inv * t * cy + t * t * b.y, cx, cy };
    };
    const protection = (x: number, y: number) => protectedAreas.some((rect) => x > rect.left - 18 && x < rect.right + 18 && y > rect.top - 10 && y < rect.bottom + 10) ? .22 : 1;
    function draw() {
      if (!context) return;
      context.clearRect(0, 0, width, height); pointer.strength += (pointer.target - pointer.strength) * .08;
      const intensity = quiet ? .72 : 1;
      if (performance.now() - lastAreas > 700) { protectedAreas = Array.from(document.querySelectorAll<HTMLElement>(".neural-hero-copy h1,.neural-hero-copy h2,.neural-product h1,.neural-detail-figures strong,.neural-filters,.neural-comparison-table")).map((node) => node.getBoundingClientRect()); lastAreas = performance.now(); }
      positions = nodes.map((node) => ({ x: node.x + Math.sin(time * .19 + node.phase) * 12 * node.depth, y: node.y + Math.cos(time * .16 + node.phase) * 10 * node.depth }));
      for (let i = 0; i < 9; i++) {
        const y = height * (i + .5) / 9;
        context.beginPath(); context.moveTo(width * .28, y + 60); context.bezierCurveTo(width * .47, y - 100 + Math.sin(time * .2 + i) * 36, width * .72, y + 145, width * 1.08, y - 80);
        context.strokeStyle = `rgba(22,114,166,${.13 * intensity})`; context.lineWidth = 2; context.stroke();
      }
      edges.forEach((edge) => {
        const a = positions[edge.a], b = positions[edge.b], middle = pointAt(a, b, edge.bend, .5), excitation = clamp(1 - Math.hypot(middle.x - pointer.x, middle.y - pointer.y) / 180) * pointer.strength;
        context.beginPath(); context.moveTo(a.x, a.y); context.quadraticCurveTo(middle.cx, middle.cy, b.x, b.y); context.lineWidth = nodes[edge.a].hub && nodes[edge.b].hub ? .85 : .55;
        context.strokeStyle = `rgba(49,170,220,${(.19 + excitation * .28) * intensity * protection(middle.x, middle.y)})`; context.stroke();
      });
      const remaining: Pulse[] = [];
      pulses.forEach((pulse) => {
        const progress = (time - pulse.start) / pulse.duration;
        if (progress >= 1) {
          nodes[pulse.b].activated = time;
          if (pulse.hops > 0 && remaining.length < 110) nodes[pulse.b].links.filter((index) => index !== pulse.a).slice(0, 2).forEach((b, i) => remaining.push({ a: pulse.b, b, start: time + .12 + i * .12, duration: .65 + random() * .45, hops: pulse.hops - 1, strength: pulse.strength * .72 })); return;
        }
        remaining.push(pulse); if (progress < 0) return;
        const edge = edges.find((candidate) => candidate.a === pulse.a && candidate.b === pulse.b || candidate.b === pulse.a && candidate.a === pulse.b), bend = edge ? edge.bend * (edge.a === pulse.a ? 1 : -1) : 0;
        const a = positions[pulse.a], b = positions[pulse.b], point = pointAt(a, b, bend, progress), alpha = pulse.strength * intensity * protection(point.x, point.y);
        context.beginPath(); for (let step = 0; step < 7; step++) { const tail = pointAt(a, b, bend, Math.max(0, progress - (6 - step) * .025)); if (step === 0) context.moveTo(tail.x, tail.y); else context.lineTo(tail.x, tail.y); }
        context.lineWidth = 1.6; context.strokeStyle = `rgba(155,241,255,${alpha * .85})`; context.stroke();
        const glow = context.createRadialGradient(point.x, point.y, 0, point.x, point.y, 10); glow.addColorStop(0, `rgba(195,250,255,${alpha})`); glow.addColorStop(.25, `rgba(45,196,255,${alpha * .5})`); glow.addColorStop(1, "rgba(45,196,255,0)"); context.fillStyle = glow; context.fillRect(point.x - 10, point.y - 10, 20, 20);
      }); pulses = remaining.slice(-140);
      positions.forEach((point, i) => {
        const node = nodes[i], activation = Math.max(0, 1 - (time - node.activated) / 1.25), excitation = clamp(1 - Math.hypot(point.x - pointer.x, point.y - pointer.y) / 140) * pointer.strength, power = Math.max(activation, excitation), alpha = intensity * protection(point.x, point.y);
        if (node.hub || power > .3) { const radius = (node.hub ? 10 : 6) + power * 12, glow = context.createRadialGradient(point.x, point.y, 0, point.x, point.y, radius); glow.addColorStop(0, `rgba(73,200,245,${(.16 + power * .46) * alpha})`); glow.addColorStop(1, "rgba(31,168,241,0)"); context.fillStyle = glow; context.fillRect(point.x - radius, point.y - radius, radius * 2, radius * 2); }
        context.fillStyle = `rgba(150,234,255,${(.3 + power * .7) * alpha})`; context.beginPath(); context.arc(point.x, point.y, node.hub ? 1.6 + power * 1.2 : .6 + node.depth * .5, 0, Math.PI * 2); context.fill();
        if (activation > .3) { context.strokeStyle = `rgba(67,204,250,${activation * .3 * alpha})`; context.lineWidth = .7; context.beginPath(); context.arc(point.x, point.y, 4 + (1 - activation) * 13, 0, Math.PI * 2); context.stroke(); }
      });
      if (shock && time - shock.start < 2.8) { const age = time - shock.start, radius = 15 + age * 120; context.strokeStyle = `rgba(100,228,255,${Math.max(0, .45 - age * .16)})`; context.lineWidth = 1.1; context.beginPath(); context.ellipse(shock.x, shock.y, radius, radius * .45, -.1, 0, Math.PI * 2); context.stroke(); }
    }
    const tick = (timestamp: number) => {
      frame = requestAnimationFrame(tick); if (document.hidden || timestamp - last < 32) return;
      time += Math.min((timestamp - (last || timestamp)) / 1000, .09); last = timestamp;
      if (time > nextPulse && nodes.length) { activate(Math.floor(random() * nodes.length), .9); nextPulse = time + (quiet ? 1.3 : .8) + random() * .7; } draw();
    };
    const move = (event: PointerEvent) => { pointer.x = event.clientX; pointer.y = event.clientY; pointer.target = event.pointerType === "touch" ? 0 : 1; };
    const leave = () => { pointer.target = 0; };
    const receive = (event: Event) => {
      if (motion.matches) return;
      const signal = (event as CustomEvent<NeuralSignal>).detail, anchor = signal.routes[0] && document.querySelector<HTMLElement>(`[data-neural="${signal.routes[0].from}"]`), rect = anchor?.getBoundingClientRect();
      const origin = signal.origin ?? (rect ? { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 } : { x: width * .72, y: height * .5 });
      nodes.map((node, index) => ({ index, distance: Math.hypot(node.x - origin.x, node.y - origin.y) })).sort((a, b) => a.distance - b.distance).slice(0, signal.kind === "kick" ? 4 : 2).forEach(({ index }) => activate(index, 1.35));
      if (signal.kind === "kick") shock = { ...origin, start: time };
    };
    const setMotion = () => { cancelAnimationFrame(frame); if (!motion.matches) frame = requestAnimationFrame(tick); else { pulses = []; shock = null; draw(); } };
    const visibility = () => { last = 0; };
    const observer = new ResizeObserver(resize); observer.observe(canvas);
    window.addEventListener("pointermove", move, { passive: true }); document.addEventListener("pointerleave", leave); window.addEventListener(SIGNAL_EVENT, receive); document.addEventListener("visibilitychange", visibility); motion.addEventListener("change", setMotion);
    resize(); setMotion();
    return () => { observer.disconnect(); cancelAnimationFrame(frame); window.removeEventListener("pointermove", move); document.removeEventListener("pointerleave", leave); window.removeEventListener(SIGNAL_EVENT, receive); document.removeEventListener("visibilitychange", visibility); motion.removeEventListener("change", setMotion); };
  }, [quiet]);
  return <canvas ref={canvasRef} className={`neural-field ${quiet ? "neural-field-quiet" : ""}`} aria-hidden="true" />;
}
