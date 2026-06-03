"use client";

import { useEffect, useState } from "react";
import {
  Home, Zap, Car, Anchor, Construction, AlertTriangle, Cpu, Network,
  BookOpen, Phone, TrendingUp, ArrowDown,
} from "lucide-react";
import { API_URL } from "@/lib/utils";

type Agent = { id: string; name: string; desc: string; icon: string; handled: number };
type Net = {
  master: { name: string; desc: string; pipeline: string[]; total_handled: number };
  agents: Agent[];
  support_agents: { name: string; desc: string }[];
};

const ICONS: Record<string, typeof Home> = {
  home: Home, zap: Zap, car: Car, anchor: Anchor, construction: Construction, alert: AlertTriangle,
};

export default function AgentNetworkPage() {
  const [net, setNet] = useState<Net | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/crm/agent-network`).then((r) => r.json()).then(setNet).catch(() => {});
  }, []);

  return (
    <div className="bg-moei-cream/30 min-h-screen">
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-10">
          <span className="moei-kicker">Architecture</span>
          <h1 className="mt-2 moei-h-section">Multi-Agent Network</h1>
          <p className="mt-2 max-w-2xl text-sm text-moei-body">
            Not a single chatbot — a master supervisor agent that understands every request,
            holds cross-channel memory, and coordinates a team of specialist agents. New services
            are added by plugging in a new agent, with no change to the rest of the system.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-8">
        {!net ? (
          <div className="py-16 text-center text-sm text-moei-muted">Loading…</div>
        ) : (
          <>
            {/* Master agent */}
            <div className="rounded-2xl border-2 border-moei-bronze bg-white p-6 shadow-moei-card">
              <div className="flex items-start gap-4">
                <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-moei-bronze text-white">
                  <Cpu size={24} />
                </span>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-moei-ink">{net.master.name}</h2>
                    <span className="rounded-full bg-moei-cream px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-moei-bronze">
                      {net.master.total_handled} requests routed
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-moei-body">{net.master.desc}</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {net.master.pipeline.map((p, i) => (
                      <span key={p} className="inline-flex items-center gap-1">
                        <span className="rounded-md bg-moei-cream/70 px-2 py-0.5 text-[11px] font-medium text-moei-ink">{p}</span>
                        {i < net.master.pipeline.length - 1 && <span className="text-moei-muted">→</span>}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="my-4 flex justify-center text-moei-muted"><ArrowDown size={20} /></div>
            <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-moei-muted">
              <Network size={13} /> Specialist agents
            </div>

            {/* Specialist agents */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {net.agents.map((a) => {
                const Icon = ICONS[a.icon] ?? Home;
                return (
                  <div key={a.id} className="rounded-xl border border-moei-line bg-white p-5 transition hover:border-moei-bronze hover:shadow-moei-card">
                    <div className="flex items-center justify-between">
                      <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-moei-cream">
                        <Icon size={18} className="text-moei-bronze" />
                      </span>
                      <span className="text-right">
                        <span className="block text-xl font-bold text-moei-ink">{a.handled}</span>
                        <span className="text-[10px] uppercase tracking-wider text-moei-muted">cases handled</span>
                      </span>
                    </div>
                    <h3 className="mt-3 font-semibold text-moei-ink">{a.name}</h3>
                    <p className="mt-1 text-xs text-moei-body">{a.desc}</p>
                  </div>
                );
              })}
            </div>

            {/* Support agents */}
            <div className="mt-8 mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-moei-muted">
              <Cpu size={13} /> Cross-cutting intelligence
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              {net.support_agents.map((s, i) => {
                const Icon = [BookOpen, Phone, TrendingUp][i] ?? Cpu;
                return (
                  <div key={s.name} className="rounded-xl border border-dashed border-moei-line bg-white/60 p-4">
                    <div className="flex items-center gap-2">
                      <Icon size={15} className="text-moei-bronze" />
                      <h3 className="text-sm font-semibold text-moei-ink">{s.name}</h3>
                    </div>
                    <p className="mt-1 text-xs text-moei-body">{s.desc}</p>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
