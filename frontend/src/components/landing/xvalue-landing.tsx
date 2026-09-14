"use client";

import { useLayoutEffect, useRef } from "react";
import gsap from "gsap";
import { formatInteger } from "@/lib/format";
import type { Player, PlayerPresentation } from "@/types/player";
import { ActionRow } from "./action-row";
import { BrandMark } from "./brand-mark";
import { HeroPlayerAvatar } from "./hero-player-avatar";
import { MetricBar } from "./metric-bar";
import { PlayerValueGrid } from "./player-value-grid";

interface XValueLandingProps {
  player: Player;
  presentation: PlayerPresentation;
}

export function XValueLanding({
  player,
  presentation,
}: XValueLandingProps) {
  const landingRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (!landingRef.current) return;

    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    const context = gsap.context(() => {
      if (reducedMotion) {
        gsap.set(".metric-fill", { scaleX: 1 });
        return;
      }

      const timeline = gsap.timeline({
        defaults: { duration: 0.5, ease: "power3.out" },
      });

      timeline
        .from(".brand-reveal", { autoAlpha: 0, y: -12, duration: 0.42 })
        .from(
          ".avatar-reveal",
          { autoAlpha: 0, scale: 0.9, x: -24, duration: 0.68 },
          0.14,
        )
        .from(
          ".identity-reveal > *",
          { autoAlpha: 0, y: 18, stagger: 0.07 },
          0.34,
        )
        .from(
          ".value-card",
          { autoAlpha: 0, y: 14, stagger: 0.08 },
          0.62,
        )
        .from(
          ".gap-card",
          { autoAlpha: 0, scale: 0.96, duration: 0.58 },
          0.78,
        )
        .from(
          ".metric-item",
          { autoAlpha: 0, y: 12, stagger: 0.08 },
          0.96,
        )
        .to(
          ".metric-fill",
          { scaleX: 1, duration: 0.7, stagger: 0.08, ease: "power2.out" },
          1.04,
        )
        .from(
          ".action-button",
          { autoAlpha: 0, y: 10, stagger: 0.06, duration: 0.4 },
          1.2,
        );
    }, landingRef);

    return () => context.revert();
  }, []);

  return (
    <div ref={landingRef} className="relative min-h-screen overflow-hidden">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.045]"
        aria-hidden="true"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,.32) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.32) 1px, transparent 1px)",
          backgroundSize: "80px 80px",
          maskImage:
            "linear-gradient(to bottom, black, transparent 78%), linear-gradient(to right, black, transparent 90%)",
        }}
      />

      <header className="relative z-10 mx-auto flex h-20 max-w-[1540px] items-center justify-between border-b border-white/[0.08] px-5 sm:px-8 lg:h-[5.25rem] xl:px-10">
        <BrandMark className="brand-reveal text-xl sm:text-2xl" />

        <nav
          className="hidden items-center gap-7 text-sm font-medium text-white/48 md:flex"
          aria-label="Preview navigation"
        >
          <span>Players</span>
          <span>Compare</span>
          <span>Method</span>
        </nav>

        <div className="brand-reveal flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.025] px-3 py-1.5 text-xs text-white/50">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
          Demo · Synthetic data
        </div>
      </header>

      <main className="relative z-10 mx-auto grid min-h-[calc(100svh-5rem)] max-w-[1540px] items-center gap-8 px-5 py-8 sm:px-8 sm:py-10 lg:min-h-[calc(100svh-5.25rem)] lg:grid-cols-[0.78fr_1.22fr] lg:gap-10 lg:py-6 xl:gap-14 xl:px-10 xl:py-8">
        <section
          className="avatar-reveal flex min-w-0 flex-col justify-center"
          aria-label="Featured player portrait"
        >
          <div className="mb-1 flex items-center gap-3 text-xs font-semibold tracking-[0.18em] text-white/38 uppercase lg:mb-0">
            <span className="h-px w-8 bg-accent/60" />
            Featured profile
          </div>
          <HeroPlayerAvatar
            initials={presentation.initials}
            playerName={player.name}
          />
        </section>

        <section className="min-w-0">
          <div className="identity-reveal">
            <p className="font-mono text-xs font-medium tracking-[0.16em] text-accent uppercase">
              {player.isU23 ? "U23 prospect" : "Player intelligence"} · {player.season}
            </p>
            <h1 className="mt-2 max-w-4xl text-[clamp(3rem,5.4vw,6.1rem)] leading-[0.9] font-semibold tracking-[-0.068em] text-balance">
              {player.name}
            </h1>
            <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-white/62 sm:text-base">
              <span className="font-semibold text-white">{player.position}</span>
              <span className="h-1 w-1 rounded-full bg-white/25" aria-hidden="true" />
              <span>{player.age} years</span>
              <span className="h-1 w-1 rounded-full bg-white/25" aria-hidden="true" />
              <span>{player.club}</span>
              <span className="h-1 w-1 rounded-full bg-white/25" aria-hidden="true" />
              <span>{player.league}</span>
            </div>
          </div>

          <div className="mt-6">
            <PlayerValueGrid player={player} presentation={presentation} />
          </div>

          <div className="mt-5 grid gap-6 rounded-2xl border border-white/[0.08] bg-[#091411]/70 p-4 backdrop-blur-sm sm:grid-cols-3 sm:p-5">
            <MetricBar
              label="Performance"
              value={player.inputs.performanceIndex}
              displayValue={player.inputs.performanceIndex.toFixed(1)}
            />
            <MetricBar
              label="Playing Time"
              value={presentation.playingTimeDisplayPct}
              displayValue={`${formatInteger(player.inputs.minutes)} min`}
            />
            <MetricBar
              label="Availability"
              value={player.inputs.availabilityPct}
              displayValue={`${player.inputs.availabilityPct.toFixed(
                Number.isInteger(player.inputs.availabilityPct) ? 0 : 1,
              )}%`}
            />
          </div>

          <div className="mt-5">
            <ActionRow />
          </div>

          <p className="mt-4 max-w-2xl text-xs leading-5 text-white/40">
            Gap shows the difference between the model estimate and a market-value
            reference. It is not proof that a player is undervalued.
          </p>
        </section>
      </main>
    </div>
  );
}
