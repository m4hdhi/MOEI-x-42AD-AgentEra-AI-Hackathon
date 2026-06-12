"use client";

/**
 * Strategic Country Intelligence — a digital advisor for MOEI leadership.
 *
 * Pick a country → see a decision-ready profile (economy, energy, infrastructure, UAE
 * bilateral cooperation) → "Prepare me for a meeting" generates an executive briefing in
 * seconds (talking points, opportunities, risks, recommended actions, smart questions),
 * grounded only in trusted country data. Plus side-by-side comparison and strategic Q&A.
 */

import { useCallback, useEffect, useState } from "react";
import {
  Globe, Sparkles, Scale, MessageSquare, FileText, TrendingUp, Zap, Ship, Leaf, Building2,
  Handshake, AlertTriangle, Lightbulb, ArrowRight, Loader2, Send, BookOpen,
} from "lucide-react";
import { API_URL } from "@/lib/utils";

type Card = {
  code: string; flag: string; name: string; name_ar: string; region: string;
  gdp_usd_b: number; gdp_per_capita_usd: number; gdp_growth_pct: number; uae_trade_usd_b: number | null;
};
type Tab = "profile" | "brief" | "compare" | "ask";

const num = (n: number | null | undefined, d = 0) =>
  n == null ? "—" : n.toLocaleString(undefined, { maximumFractionDigits: d });

export default function IntelConsole() {
  const [cards, setCards] = useState<Card[]>([]);
  const [code, setCode] = useState<string>("");
  const [tab, setTab] = useState<Tab>("profile");

  useEffect(() => {
    fetch(`${API_URL}/intel/countries`, { credentials: "include" })
      .then((r) => r.json()).then((d) => { setCards(d.countries || []); if (d.countries?.[0]) setCode(d.countries[0].code); });
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-7xl">
        <div className="flex items-center gap-2">
          <Globe className="text-moei-bronze" size={20} />
          <h1 className="text-xl font-bold text-slate-800">Strategic Country Intelligence</h1>
        </div>
        <p className="mt-1 text-sm text-slate-500">Decision-ready intelligence for international engagement — not a search engine, a strategic advisor.</p>

        {/* country selector */}
        <div className="mt-5 flex flex-wrap gap-2">
          {cards.map((c) => (
            <button key={c.code} onClick={() => setCode(c.code)}
              className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold transition ${code === c.code ? "border-moei-bronze bg-white shadow-sm" : "border-slate-200 bg-white/60 hover:border-slate-300"}`}>
              <span className="text-lg">{c.flag}</span> {c.name}
            </button>
          ))}
        </div>

        {/* tabs */}
        <div className="mt-5 inline-flex rounded-xl border border-slate-200 bg-white p-1">
          {([
            { k: "profile", icon: BookOpen, label: "Country profile" },
            { k: "brief", icon: Sparkles, label: "Prepare me for a meeting" },
            { k: "compare", icon: Scale, label: "Compare" },
            { k: "ask", icon: MessageSquare, label: "Ask" },
          ] as const).map(({ k, icon: Icon, label }) => (
            <button key={k} onClick={() => setTab(k)}
              className={`flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold transition ${tab === k ? "bg-moei-bronze text-white" : "text-slate-600 hover:text-moei-bronze"}`}>
              <Icon size={15} /> {label}
            </button>
          ))}
        </div>

        <div className="mt-5">
          {tab === "profile" && <Profile code={code} />}
          {tab === "brief" && <Briefing code={code} card={cards.find((c) => c.code === code)} />}
          {tab === "compare" && <Compare cards={cards} />}
          {tab === "ask" && <Ask />}
        </div>
      </div>
    </div>
  );
}

// ── Profile ──────────────────────────────────────────────────────────────────
function Profile({ code }: { code: string }) {
  const [p, setP] = useState<any>(null);
  useEffect(() => {
    if (!code) return;
    setP(null);
    fetch(`${API_URL}/intel/country/${code}`, { credentials: "include" }).then((r) => r.json()).then(setP);
  }, [code]);
  if (!p) return <Loading />;
  const en = p.energy || {}, inf = p.infrastructure || {}, su = p.sustainability || {}, uae = p.uae || {}, comp = p.competitiveness || {};
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-center gap-3">
          <span className="text-4xl">{p.flag}</span>
          <div>
            <div className="text-lg font-bold text-slate-800">{p.name} <span className="text-slate-400 text-sm">{p.name_ar}</span></div>
            <div className="text-xs text-slate-500">{p.region} · Capital {p.capital}</div>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Ind icon={TrendingUp} label="GDP" value={`$${num(p.gdp_usd_b)}bn`} />
          <Ind icon={TrendingUp} label="GDP / capita" value={`$${num(p.gdp_per_capita_usd)}`} />
          <Ind icon={TrendingUp} label="Real growth" value={`${p.gdp_growth_pct}%`} tone={p.gdp_growth_pct < 0 ? "warn" : "good"} />
          <Ind icon={Building2} label="Population" value={`${num(p.population_m, 1)}m`} />
          <Ind icon={Zap} label="Renewable elec." value={`${en.renewable_share_pct ?? "—"}%`} />
          <Ind icon={Zap} label="Elec / capita" value={`${num(en.per_capita_kwh)} kWh`} />
          <Ind icon={Ship} label="Logistics idx" value={`${inf.logistics_index ?? "—"}`} />
          <Ind icon={Handshake} label="UAE non-oil trade" value={`$${num(uae.non_oil_trade_usd_b)}bn`} tone="bronze" />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section icon={Zap} title="Energy">
          <p className="text-sm text-slate-600">{en.notes}</p>
          <Kv k="Renewable target" v={en.renewable_target} />
          <Kv k="CO₂ / capita" v={en.co2_per_capita_t ? `${en.co2_per_capita_t} t` : "—"} />
        </Section>
        <Section icon={Ship} title="Infrastructure">
          <p className="text-sm text-slate-600">{inf.notes}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">{(inf.key_assets || []).map((a: string) => <Chip key={a}>{a}</Chip>)}</div>
        </Section>
        <Section icon={Leaf} title="Sustainability & competitiveness">
          <p className="text-sm text-slate-600">{su.notes}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">{(su.initiatives || []).map((a: string) => <Chip key={a}>{a}</Chip>)}</div>
          <div className="mt-2 flex gap-3 text-xs text-slate-500">
            <span>Competitiveness #{comp.global_competitiveness_rank ?? "—"}</span>
            <span>Innovation #{comp.innovation_rank ?? "—"}</span>
          </div>
        </Section>
        <Section icon={Building2} title="Major projects">
          <ul className="space-y-1 text-sm text-slate-600">{(p.projects || []).map((x: string) => <li key={x} className="flex gap-2"><span className="text-moei-bronze">•</span>{x}</li>)}</ul>
        </Section>
      </div>

      {/* UAE bilateral */}
      <Section icon={Handshake} title="UAE bilateral cooperation" accent>
        <p className="text-sm font-medium text-slate-700">{uae.positioning}</p>
        <p className="mt-0.5 text-xs text-slate-500">{uae.trade_trend} · {uae.companies}</p>
        <div className="mt-3 space-y-2">
          {(uae.agreements || []).map((a: any, i: number) => (
            <div key={i} className="rounded-lg border border-slate-100 bg-slate-50 p-2.5">
              <div className="flex items-center gap-2"><span className="rounded-full bg-moei-cream px-2 py-0.5 text-[10px] font-semibold text-moei-bronze">{a.date}</span><span className="text-sm font-semibold text-slate-800">{a.title}</span></div>
              <p className="mt-0.5 text-xs text-slate-600">{a.detail}</p>
            </div>
          ))}
        </div>
      </Section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section icon={Lightbulb} title="Strategic opportunities for the UAE">
          <div className="space-y-2">{(p.opportunities || []).map((o: any, i: number) => (
            <div key={i} className="text-sm"><span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700">{o.sector}</span> <span className="font-semibold text-slate-800">{o.title}</span><p className="text-xs text-slate-600">{o.detail}</p></div>
          ))}</div>
        </Section>
        <Section icon={AlertTriangle} title="Risks & sensitivities">
          <ul className="space-y-1 text-sm text-slate-600">{(p.risks || []).map((x: string) => <li key={x} className="flex gap-2"><AlertTriangle size={13} className="mt-0.5 shrink-0 text-amber-500" />{x}</li>)}</ul>
        </Section>
      </div>
    </div>
  );
}

// ── Briefing (the hero) ──────────────────────────────────────────────────────
function Briefing({ code, card }: { code: string; card?: Card }) {
  const [ctx, setCtx] = useState("");
  const [lang, setLang] = useState<"en" | "ar">("en");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<any>(null);

  async function gen() {
    if (busy || !code) return;
    setBusy(true); setRes(null);
    try {
      const r = await fetch(`${API_URL}/intel/brief`, {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
        body: JSON.stringify({ code, meeting_context: ctx, language: lang }),
      });
      setRes(await r.json());
    } finally { setBusy(false); }
  }
  const b = res?.brief;
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
          <Sparkles size={16} className="text-moei-bronze" /> Prepare leadership for a meeting with {card?.flag} {card?.name}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <input value={ctx} onChange={(e) => setCtx(e.target.value)}
            placeholder="e.g. Energy Minister meeting on green-hydrogen offtake"
            className="flex-1 min-w-[260px] rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-moei-bronze" />
          <button onClick={() => setLang(lang === "en" ? "ar" : "en")} className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-600">{lang === "en" ? "العربية" : "English"}</button>
          <button onClick={gen} disabled={busy} className="inline-flex items-center gap-1.5 rounded-lg bg-moei-bronze px-4 py-2 text-sm font-semibold text-white hover:bg-moei-bronze-dark disabled:opacity-50">
            {busy ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />} Generate briefing
          </button>
        </div>
        {["Brazil green hydrogen", "Singapore smart cities", "India IMEC corridor"].map(() => null)}
      </div>

      {busy && <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-400"><Loader2 className="mx-auto animate-spin" /> Researching and drafting the briefing…</div>}

      {b && (
        <div className="space-y-4" dir={lang === "ar" ? "rtl" : "ltr"}>
          <div className="flex items-center justify-between rounded-xl border border-moei-bronze/30 bg-moei-cream/30 px-4 py-2 text-xs">
            <span className="font-mono text-moei-bronze">{res.reference}</span>
            <span className="text-slate-500">{res.meeting_context || "Leadership readiness"} · {res.generated_by === "ai" ? "AI-generated" : "data-grounded"}</span>
          </div>
          <BriefCard icon={FileText} title="Executive summary" items={b.summary} accent />
          <div className="grid gap-4 lg:grid-cols-2">
            <BriefCard icon={MessageSquare} title="Talking points" items={b.talking_points} />
            <BriefCard icon={Lightbulb} title="Opportunities for the UAE" items={b.opportunities} tone="emerald" />
            <BriefCard icon={AlertTriangle} title="Risks to manage" items={b.risks} tone="amber" />
            <BriefCard icon={ArrowRight} title="Recommended actions" items={b.recommended_actions} />
          </div>
          <BriefCard icon={MessageSquare} title="Smart questions to ask" items={b.questions} />
        </div>
      )}
    </div>
  );
}

// ── Compare ──────────────────────────────────────────────────────────────────
function Compare({ cards }: { cards: Card[] }) {
  const [sel, setSel] = useState<string[]>([]);
  const [res, setRes] = useState<any>(null);
  const toggle = (c: string) => setSel((s) => s.includes(c) ? s.filter((x) => x !== c) : s.length < 4 ? [...s, c] : s);
  useEffect(() => {
    if (sel.length < 2) { setRes(null); return; }
    fetch(`${API_URL}/intel/compare`, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify({ codes: sel }) })
      .then((r) => r.json()).then(setRes);
  }, [sel]);
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Pick 2–4 countries</div>
        <div className="flex flex-wrap gap-2">
          {cards.map((c) => (
            <button key={c.code} onClick={() => toggle(c.code)}
              className={`rounded-lg border px-3 py-1.5 text-sm font-semibold transition ${sel.includes(c.code) ? "border-moei-bronze bg-moei-cream/40 text-moei-bronze" : "border-slate-200 text-slate-600"}`}>
              {c.flag} {c.name}
            </button>
          ))}
        </div>
      </div>
      {res && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-slate-200 bg-slate-50">
              <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Metric</th>
              {res.countries.map((c: any) => <th key={c.code} className="px-4 py-2.5 text-center font-bold text-slate-700">{c.flag} {c.name}</th>)}
            </tr></thead>
            <tbody>
              {res.rows.map((row: any, i: number) => (
                <tr key={i} className="border-b border-slate-100">
                  <td className="px-4 py-2.5 text-slate-500">{row.metric}</td>
                  {row.values.map((v: any, j: number) => <td key={j} className="px-4 py-2.5 text-center font-semibold text-slate-800">{v == null ? "—" : typeof v === "number" ? v.toLocaleString() : v}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {sel.length < 2 && <p className="text-sm text-slate-400">Select at least two countries to compare.</p>}
    </div>
  );
}

// ── Ask ──────────────────────────────────────────────────────────────────────
function Ask() {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [a, setA] = useState<string | null>(null);
  const ask = useCallback(async () => {
    if (!q.trim() || busy) return;
    setBusy(true); setA(null);
    try {
      const r = await fetch(`${API_URL}/intel/ask`, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify({ question: q }) });
      const d = await r.json(); setA(d.answer);
    } finally { setBusy(false); }
  }, [q, busy]);
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex gap-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask()}
            placeholder="e.g. Which country is our best green-hydrogen offtake partner and why?"
            className="flex-1 rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-moei-bronze" />
          <button onClick={ask} disabled={busy} className="inline-flex items-center gap-1.5 rounded-lg bg-moei-bronze px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />} Ask</button>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {["Compare UAE energy partners by renewable share", "Where should we focus port investment?", "Best partner for green hydrogen?"].map((s) => (
            <button key={s} onClick={() => setQ(s)} className="rounded-full border border-slate-200 px-2.5 py-1 text-[11px] text-slate-500 hover:border-moei-bronze hover:text-moei-bronze">{s}</button>
          ))}
        </div>
      </div>
      {a && <div className="rounded-xl border border-moei-bronze/30 bg-moei-cream/20 p-4 text-sm leading-relaxed text-slate-700 whitespace-pre-line">{a}</div>}
    </div>
  );
}

// ── small components ─────────────────────────────────────────────────────────
function Loading() { return <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-400"><Loader2 className="mx-auto animate-spin" /></div>; }
function Ind({ icon: Icon, label, value, tone }: { icon: any; label: string; value: string; tone?: "good" | "warn" | "bronze" }) {
  const c = tone === "good" ? "text-emerald-600" : tone === "warn" ? "text-red-600" : tone === "bronze" ? "text-moei-bronze" : "text-slate-800";
  return <div className="rounded-lg border border-slate-100 bg-slate-50 p-3"><div className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400"><Icon size={11} /> {label}</div><div className={`mt-1 text-base font-bold ${c}`}>{value}</div></div>;
}
function Section({ icon: Icon, title, children, accent }: { icon: any; title: string; children: React.ReactNode; accent?: boolean }) {
  return <div className={`rounded-xl border p-4 ${accent ? "border-moei-bronze/30 bg-moei-cream/20" : "border-slate-200 bg-white"}`}><div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400"><Icon size={13} /> {title}</div>{children}</div>;
}
function BriefCard({ icon: Icon, title, items, tone, accent }: { icon: any; title: string; items: string[]; tone?: "emerald" | "amber"; accent?: boolean }) {
  const head = tone === "emerald" ? "text-emerald-700" : tone === "amber" ? "text-amber-700" : "text-slate-700";
  return (
    <div className={`rounded-xl border p-4 ${accent ? "border-moei-bronze/40 bg-white" : "border-slate-200 bg-white"}`}>
      <div className={`mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider ${head}`}><Icon size={13} /> {title}</div>
      <ul className="space-y-1.5">{(items || []).map((x, i) => <li key={i} className="flex gap-2 text-sm text-slate-700"><span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-moei-bronze" />{x}</li>)}</ul>
    </div>
  );
}
function Kv({ k, v }: { k: string; v: string }) { return <div className="mt-1.5 flex justify-between text-xs"><span className="text-slate-400">{k}</span><span className="font-medium text-slate-600">{v}</span></div>; }
function Chip({ children }: { children: React.ReactNode }) { return <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">{children}</span>; }
