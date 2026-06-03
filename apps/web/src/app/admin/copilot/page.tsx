"use client";

import { useEffect, useState } from "react";
import {
  RefreshCw, Headphones, MessageSquare, Globe, ChevronRight, AlertCircle,
  AlertTriangle, Bell, FileText,
} from "lucide-react";
import { API_URL } from "@/lib/utils";

type Turn = { role: "user" | "assistant"; text: string; channel: string };
type Case = {
  case_number: string;
  user_name: string | null;
  channel: string;
  intent: string;
  service: string;
  status: string;
  priority: string;
  sentiment: number | null;
  created_at: string;
};
type RiskUser = {
  user_id: string;
  user_name: string;
  open_cases: number;
  high_priority: number;
  avg_sentiment: number | null;
  risk_score: number;
};

const CHANNEL_META: Record<string, { color: string; icon: typeof MessageSquare; label: string }> = {
  whatsapp: { color: "bg-green-100 text-green-800 border-green-200", icon: MessageSquare, label: "WhatsApp" },
  voice: { color: "bg-purple-100 text-purple-800 border-purple-200", icon: Headphones, label: "Voice" },
  web: { color: "bg-amber-100 text-amber-800 border-amber-200", icon: Globe, label: "Web" },
  mobile: { color: "bg-slate-100 text-slate-800 border-slate-200", icon: Globe, label: "Mobile" },
};

const PRIORITY_COLOR: Record<string, string> = {
  critical: "bg-red-100 text-red-800 border-red-200",
  high: "bg-orange-100 text-orange-800 border-orange-200",
  medium: "bg-amber-100 text-amber-800 border-amber-200",
  low: "bg-slate-100 text-slate-700 border-slate-200",
};
const STATUS_COLOR: Record<string, string> = {
  open: "bg-blue-100 text-blue-800",
  in_progress: "bg-amber-100 text-amber-800",
  escalated: "bg-red-100 text-red-800",
  resolved: "bg-green-100 text-green-800",
  closed: "bg-slate-100 text-slate-700",
};

export default function CopilotPage() {
  const [userId, setUserId] = useState("784-2004-6541442-1");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [cases, setCases] = useState<Case[]>([]);
  const [risks, setRisks] = useState<RiskUser[]>([]);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    try {
      const [t, c, r] = await Promise.all([
        fetch(`${API_URL}/copilot/sessions/${encodeURIComponent(userId)}/transcript`).then(r => r.json()),
        fetch(`${API_URL}/crm/cases?user_id=${encodeURIComponent(userId)}&limit=10`).then(r => r.json()),
        fetch(`${API_URL}/analytics/escalation-risk?limit=6`).then(r => r.json()),
      ]);
      setTurns(t.turns || []);
      setCases(c.cases || []);
      setRisks(r.items || []);
    } catch {
      // ignore
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  const lastUser = [...turns].reverse().find((t) => t.role === "user");
  const sentiment = (() => {
    if (!lastUser) return null;
    const s = lastUser.text;
    if (/sorry|please|help|behind|lost|stress|قلق|أرجو|تأجيل/i.test(s)) return { label: "stressed", score: 0.28 };
    return { label: "neutral", score: 0.6 };
  })();

  const channelMix = turns.reduce<Record<string, number>>((acc, t) => {
    acc[t.channel] = (acc[t.channel] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="bg-moei-cream/30">
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-10">
          <div className="flex items-end justify-between">
            <div>
              <span className="moei-kicker">MOEI Customer Happiness Centre</span>
              <h1 className="mt-2 moei-h-section">Agent Co-pilot</h1>
              <p className="mt-2 text-sm text-moei-body">
                Real-time view of the citizen conversation with the next recommended action, open cases, and citizen sentiment — to help you reply faster.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <input
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                className="rounded-sm border border-moei-line bg-white px-3 py-2 text-xs"
                placeholder="Emirates ID"
              />
              <button onClick={load} disabled={busy} className="moei-btn-ghost">
                <RefreshCw size={14} /> Refresh
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-10">
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="lg:col-span-8 space-y-6">
            <div className="rounded-sm border border-moei-line bg-white">
              <div className="flex items-center justify-between border-b border-moei-line bg-moei-cream/50 px-5 py-3">
                <h2 className="text-sm font-semibold text-moei-ink">Live transcript · cross-channel</h2>
                <div className="flex gap-3 text-[11px] text-moei-muted">
                  {Object.entries(channelMix).map(([ch, n]) => (
                    <span key={ch}>{ch}: <span className="font-semibold text-moei-ink">{n}</span></span>
                  ))}
                </div>
              </div>
              <div className="max-h-[420px] overflow-y-auto p-5">
                {turns.length === 0 && (
                  <p className="text-sm text-moei-muted">No active session for this user yet. Open <code>/chat</code> as the citizen to populate.</p>
                )}
                <div className="space-y-3">
                  {turns.map((t, i) => {
                    const meta = CHANNEL_META[t.channel] ?? CHANNEL_META.web;
                    const Icon = meta.icon;
                    return (
                      <div key={i} className="flex items-start gap-3 border-b border-moei-line/40 pb-3 last:border-0 last:pb-0">
                        <span className={"mt-0.5 inline-flex h-6 items-center gap-1 rounded-sm border px-1.5 text-[10px] font-semibold uppercase " + meta.color}>
                          <Icon size={10} /> {meta.label}
                        </span>
                        <div className="flex-1">
                          <div className="text-[10px] uppercase tracking-wider text-moei-muted">{t.role}</div>
                          <div dir={/[؀-ۿ]/.test(t.text) ? "rtl" : "ltr"} className="text-sm text-moei-ink">{t.text}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="rounded-sm border border-moei-line bg-white">
              <div className="flex items-center justify-between border-b border-moei-line bg-moei-cream/50 px-5 py-3">
                <h2 className="flex items-center gap-2 text-sm font-semibold text-moei-ink">
                  <FileText size={14} /> Case history · {userId}
                </h2>
                <span className="text-[11px] text-moei-muted">{cases.length} cases</span>
              </div>
              <div className="max-h-[280px] overflow-y-auto">
                {cases.length === 0 && <p className="p-5 text-sm text-moei-muted">No cases on file.</p>}
                {cases.length > 0 && (
                  <table className="w-full text-xs">
                    <thead className="bg-moei-cream/30 text-[10px] uppercase tracking-wider text-moei-muted">
                      <tr>
                        <th className="px-4 py-2 text-left">Case #</th>
                        <th className="px-4 py-2 text-left">Service</th>
                        <th className="px-4 py-2 text-left">Intent</th>
                        <th className="px-4 py-2 text-left">Channel</th>
                        <th className="px-4 py-2 text-left">Priority</th>
                        <th className="px-4 py-2 text-left">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cases.map((c) => (
                        <tr key={c.case_number} className="border-t border-moei-line/40">
                          <td className="px-4 py-2 font-mono text-[11px] text-moei-ink">{c.case_number}</td>
                          <td className="px-4 py-2 text-moei-body">{c.service}</td>
                          <td className="px-4 py-2 text-moei-body">{c.intent}</td>
                          <td className="px-4 py-2 text-moei-body">{c.channel}</td>
                          <td className="px-4 py-2"><span className={"rounded-full border px-2 py-0.5 text-[10px] " + (PRIORITY_COLOR[c.priority] || PRIORITY_COLOR.medium)}>{c.priority}</span></td>
                          <td className="px-4 py-2"><span className={"rounded-full px-2 py-0.5 text-[10px] " + (STATUS_COLOR[c.status] || STATUS_COLOR.open)}>{c.status}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>

          <aside className="space-y-4 lg:col-span-4">
            <div className="rounded-sm border border-moei-line bg-white p-5">
              <div className="moei-kicker">Sentiment overlay</div>
              <div className="mt-3 flex items-center gap-3">
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-moei-line">
                  <div className={"h-2 transition-all " + (sentiment?.label === "stressed" ? "bg-red-500" : "bg-moei-bronze")} style={{ width: `${(sentiment?.score ?? 0.5) * 100}%` }} />
                </div>
                <span className="text-xs font-medium text-moei-ink">{sentiment?.label ?? "—"}</span>
              </div>
              <p className="mt-3 text-[11px] text-moei-muted">Lexical proxy on text; SenseVoice / wav2vec2 on voice (production).</p>
            </div>

            <div className="rounded-sm border border-moei-bronze/40 bg-moei-cream/50 p-5">
              <div className="flex items-center gap-2 text-moei-bronze">
                <AlertCircle size={16} />
                <span className="text-sm font-semibold">Next best action</span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-moei-ink">
                {sentiment?.label === "stressed"
                  ? "Acknowledge stress, offer hardship pathway (24-month plan), schedule callback within 24h."
                  : "Confirm citizen need; route to most-relevant MOEI service line; offer document upload if needed."}
              </p>
            </div>

            <div className="rounded-sm border border-moei-line bg-white p-5">
              <div className="moei-kicker flex items-center gap-1.5"><AlertTriangle size={12} /> Escalation risk</div>
              <ul className="mt-3 space-y-2">
                {risks.slice(0, 5).map((r) => (
                  <li key={r.user_id} className="flex items-center justify-between border-b border-moei-line/40 pb-2 last:border-0 last:pb-0">
                    <div className="min-w-0">
                      <div className="truncate text-xs font-semibold text-moei-ink">{r.user_name}</div>
                      <div className="text-[10px] text-moei-muted">
                        {r.open_cases} open · {r.high_priority} high · sentiment {r.avg_sentiment ?? "—"}
                      </div>
                    </div>
                    <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-800">{r.risk_score}</span>
                  </li>
                ))}
                {risks.length === 0 && <li className="text-xs text-moei-muted">No users currently at risk.</li>}
              </ul>
            </div>

            <QuickActions userId={userId} latestCase={cases[0]?.case_number ?? null} />

            <div className="rounded-sm border border-moei-bronze/40 bg-moei-cream/30 p-5">
              <div className="text-xs font-semibold uppercase tracking-wider text-moei-bronze">For engineers</div>
              <p className="mt-1 text-xs text-moei-body">
                Every decision made by the assistant is recorded with a full trace for compliance review and incident investigation (UAE PDPL, Article 7).
              </p>
              <a href="http://localhost:3001" target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-moei-bronze hover:underline">
                Open AI traces <ChevronRight size={12} />
              </a>
            </div>
          </aside>
        </div>
      </section>
    </div>
  );
}

function QuickActions({ userId, latestCase }: { userId: string; latestCase: string | null }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const actions: { label: string; template: string; channel: string; hours: number }[] = [
    { label: "Send doc reminder via WhatsApp", template: "doc_reminder", channel: "whatsapp", hours: 0 },
    { label: "Schedule CSAT survey in 24h", template: "csat_survey", channel: "whatsapp", hours: 24 },
    { label: "Push status update now", template: "status_update", channel: "whatsapp", hours: 0 },
    { label: "Send proactive tip via SMS", template: "proactive_tip", channel: "sms", hours: 1 },
  ];

  async function fire(label: string, template: string, channel: string, hours: number) {
    setBusy(label);
    setToast(null);
    try {
      const body: any = {
        user_id: userId,
        channel,
        template,
        scheduled_in_hours: hours,
      };
      if (latestCase) body.case_number = latestCase;
      const r = await fetch(`${API_URL}/notifications`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      const when = hours === 0 ? "queued for the next tick" : `scheduled in ${hours}h`;
      setToast(`✓ ${label} — ${when} (id ${data.id.slice(0, 8)})`);
    } catch (e: any) {
      setToast(`✗ Failed: ${e.message || e}`);
    } finally {
      setBusy(null);
      setTimeout(() => setToast(null), 5000);
    }
  }

  return (
    <div className="rounded-sm border border-moei-line bg-white p-5">
      <div className="moei-kicker flex items-center gap-1.5"><Bell size={12} /> Proactive engagement</div>
      <div className="mt-3 space-y-2">
        {actions.map((a) => (
          <button
            key={a.label}
            onClick={() => fire(a.label, a.template, a.channel, a.hours)}
            disabled={busy !== null}
            className="flex w-full items-center justify-between rounded-sm border border-moei-line bg-white px-3 py-2 text-left text-xs text-moei-body transition hover:border-moei-bronze hover:text-moei-bronze disabled:opacity-60"
          >
            <span>{busy === a.label ? "Scheduling…" : a.label}</span>
            <ChevronRight size={12} />
          </button>
        ))}
      </div>
      {toast && (
        <div className={"mt-3 rounded-sm border px-3 py-2 text-[11px] " + (toast.startsWith("✓") ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-red-200 bg-red-50 text-red-800")}>
          {toast}
        </div>
      )}
      <p className="mt-3 text-[10px] text-moei-muted">
        Writes to <code>notifications</code> table; the background dispatcher sends due rows every 30s via Twilio.
      </p>
    </div>
  );
}

