"use client";

import { useEffect, useRef } from "react";
import { SIGNAL_EVENT, type NeuralSignal } from "./neural-signals";

export function NeuralWordmark() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const textRef = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current, text = textRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !text || !context) return;
    const motion = matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0, width = 0, height = 0, points: Array<{ x: number; y: number; neighbours: number[] }> = [];
    let start = 0, last = 0, impactAt = -10000;
    const resize = () => {
      const rect = text.getBoundingClientRect(), style = getComputedStyle(text);
      width = rect.width; height = rect.height;
      if (width < 1 || height < 1) return;
      const dpr = Math.min(devicePixelRatio || 1, 2); canvas.width = width * dpr; canvas.height = height * dpr;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      const mask = document.createElement("canvas"); mask.width = Math.ceil(width); mask.height = Math.ceil(height);
      const painter = mask.getContext("2d", { willReadFrequently: true }); if (!painter) return;
      painter.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`; painter.textBaseline = "middle";
      painter.letterSpacing = style.letterSpacing; painter.fillStyle = "white"; painter.fillText("xValue", 0, height * 0.52);
      const pixels = painter.getImageData(0, 0, mask.width, mask.height).data;
      points = [];
      const gap = width < 350 ? 5 : 7;
      for (let y = 0; y < height; y += gap) for (let x = 0; x < width; x += gap) if (pixels[(y * mask.width + x) * 4 + 3] > 100) points.push({ x, y, neighbours: [] });
      const byCell = new Map(points.map((point, i) => [`${point.x},${point.y}`, i]));
      points.forEach((point) => { [[gap, 0], [0, gap], [gap, gap]].forEach(([dx, dy]) => { const index = byCell.get(`${point.x + dx},${point.y + dy}`); if (index !== undefined) point.neighbours.push(index); }); });
    };
    const tick = (timestamp: number) => {
      frame = requestAnimationFrame(tick);
      if (document.hidden || timestamp - last < 32) return;
      last = timestamp; if (!start) start = timestamp;
      const time = (timestamp - start) / 1000;
      context.clearRect(0, 0, width, height);
      const reveal = Math.min(1, time / 1.8);
      const sweep = ((time - 2) % 6) / 2.4;
      points.forEach((point, i) => {
        if (point.x > reveal * width) return;
        const pulse = Math.max(0, 1 - Math.abs(point.x / width - sweep) * 14);
        const entrance = Math.max(0, 1 - Math.abs(point.x / width - reveal) * 12) * (reveal < 1 ? 1 : 0);
        const impactAge = (timestamp - impactAt) / 1000;
        const impact = impactAge < 2 ? Math.max(0, 1 - Math.abs(point.x / width - impactAge / 1.4) * 7) : 0;
        const brightness = Math.max(pulse, entrance, impact);
        context.strokeStyle = `rgba(109,223,252,${0.17 + brightness * 0.62})`; context.lineWidth = 0.6;
        point.neighbours.forEach((index) => { const other = points[index]; if (other.x > reveal * width) return; context.beginPath(); context.moveTo(point.x, point.y); context.lineTo(other.x, other.y); context.stroke(); });
        context.fillStyle = `rgba(200,249,255,${0.32 + brightness * 0.65})`;
        context.beginPath(); context.arc(point.x, point.y, 0.6 + brightness * 0.7 + (i % 5 === 0 ? 0.2 : 0), 0, Math.PI * 2); context.fill();
      });
    };
    const setMotion = () => { cancelAnimationFrame(frame); context.clearRect(0, 0, width, height); if (!motion.matches) frame = requestAnimationFrame(tick); };
    const receive = (event: Event) => { if ((event as CustomEvent<NeuralSignal>).detail.kind === "kick") impactAt = performance.now(); };
    window.addEventListener(SIGNAL_EVENT, receive);
    const observer = new ResizeObserver(resize); observer.observe(text); resize(); setMotion(); motion.addEventListener("change", setMotion);
    return () => { observer.disconnect(); cancelAnimationFrame(frame); motion.removeEventListener("change", setMotion); window.removeEventListener(SIGNAL_EVENT, receive); };
  }, []);
  return <h1 className="neural-wordmark" aria-label="xValue"><span ref={textRef} aria-hidden="true">xValue</span><canvas ref={canvasRef} aria-hidden="true" /></h1>;
}
