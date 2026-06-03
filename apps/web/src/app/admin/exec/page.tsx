"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  Activity, AlertTriangle, BellRing, Briefcase, Calendar, MessageSquare,
  Mic, Smartphone, Globe, Sparkles, TrendingUp, Users, Phone, Gauge, CheckCircle2,
} from "lucide-react";
import Link from "next/link";
import { API_URL } from "@/lib/utils";

// ---- Types ----------------------------------------------------------------

type CrmStats = {
  totals: Record<string, number | null>;
  by_service: { service: string; n: number }[];
  by_channel: { channel: string; n: number }[];
  by_intent: { intent: string; n: number }[];
};
type Forecast = {
  as_of: string;
  method: string;
  history: { day: string; value: number; kind: string }[];
  forecast: { day: string; value: number; kind: string }[];
};
type Sentiment = {
  days: number;
  series: { day: string; avg: number | null; negative_count: number; total: number }[];
};
type Heatmap = {
  cells: { day: string; dow: number; hour: number; avg_cases: number; recommended_agents: number }[];
  peak: { day: string; hour: number; avg_cases: number; recommended_agents: number } | null;
};
type Risk = {
  items: {
    user_id: string; user_name: string; open_cases: number;
    high_priority: number; avg_sentiment: number | null; risk_score: number;
  }[];
};
type Notifs = {
  totals: { upcoming: number; sent_today: number; sent_week: number; failed: number };
  by_template: { template: string; n: number }[];
};
type OpKpis = {
  first_contact_resolution_pct: number;
  channel_deflection_pct: number;
  avg_handle_time_seconds: number;
  avg_handle_time_minutes: number;
  cross_channel_continuity_pct: number;
  window: string;
};
type Feedback = {
  totals: {
    responses_30d: number;
    responses_today: number;
    avg_csat_5: number | null;
    avg_ces_5: number | null;
    effortless_pct: number;
    nps_proxy: number;
  };
};
type ActivityEvent = {
  id: number; user_name: string | null; channel: string | null;
  event_type: string; summary: string; at: string;
};
type VoiceStats = {
  total: number; today: number; avg_qa: number; avg_duration: number;
  resolution_rate: number; avg_sentiment: number;
};

// ---- Constants ------------------------------------------------------------

const CHANNEL_ICON: Record<string, typeof Globe> = {
  whatsapp: MessageSquare, voice: Mic, web: Globe, mobile: Smartphone,
};
const EVENT_COLOR: Record<string, string> = {
  case_created: "bg-blue-100 text-blue-800",
  escalation: "bg-red-100 text-red-800",
  channel_switch: "bg-purple-100 text-purple-800",
  sentiment_change: "bg-orange-100 text-orange-800",
  nba_offered: "bg-moei-cream text-moei-bronze",
  turn: "bg-slate-100 text-slate-700",
};

// ---- Page ----------------------------------------------------------------

export default function ExecPage() {
  const [stats, setStats] = useState<CrmStats | null>(null);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [sentiment, setSentiment] = useState<Sentiment | null>(null);
  const [heatmap, setHeatmap] = useState<Heatmap | null>(null);
  const [risks, setRisks] = useState<Risk | null>(null);
  const [notifs, setNotifs] = useState<Notifs | null>(null);
  const [opKpis, setOpKpis] = useState<OpKpis | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [voice, setVoice] = useState<VoiceStats | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const sseRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const fetchAll = () => {
      fetch(`${API_URL}/crm/stats`).then(r => r.json()).then(setStats).catch(() => {});
      fetch(`${API_URL}/analytics/volume-forecast?days=7`).then(r => r.json()).then(setForecast).catch(() => {});
      fetch(`${API_URL}/analytics/sentiment-trend?days=14`).then(r => r.json()).then(setSentiment).catch(() => {});
      fetch(`${API_URL}/analytics/heatmap`).then(r => r.json()).then(setHeatmap).catch(() => {});
      fetch(`${API_URL}/analytics/escalation-risk?limit=6`).then(r => r.json()).then(setRisks).catch(() => {});
      fetch(`${API_URL}/notifications/stats`).then(r => r.json()).then(setNotifs).catch(() => {});
      fetch(`${API_URL}/crm/kpis`).then(r => r.json()).then(setOpKpis).catch(() => {});
      fetch(`${API_URL}/feedback/stats`).then(r => r.json()).then(setFeedback).catch(() => {});
      fetch(`${API_URL}/recordings/stats`).then(r => r.json()).then(setVoice).catch(() => {});
    };
    fetchAll();
    const t = setInterval(fetchAll, 8000);

    // SSE — live activity stream
    try {
      const es = new EventSource(`${API_URL}/activity/stream`);
      es.addEventListener("activity", (ev: MessageEvent) => {
        try {
          const e: ActivityEvent = JSON.parse(ev.data);
          setActivity(prev => [e, ...prev.filter(x => x.id !== e.id)].slice(0, 60));
        } catch {}
      });
      es.onerror = () => { /* let it retry */ };
      sseRef.current = es;
    } catch {}

    return () => {
      clearInterval(t);
      sseRef.current?.close();
    };
  }, []);

  return (
    <div className="bg-moei-cream/30">
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-10">
          <div className="flex items-end justify-between">
            <div>
              <span className="moei-kicker">
                MOEI Customer Happiness Centre · {new Date().toLocaleDateString("en-GB")}
              </span>
              <h1 className="mt-2 moei-h-section">Executive Dashboard</h1>
              <p className="mt-2 text-sm text-moei-body">
                Real-time omnichannel KPIs · predictive analytics · workforce planning · live citizen activity
              </p>
            </div>
            <div className="flex items-center gap-2 rounded-sm border border-moei-bronze/40 bg-moei-cream px-3 py-1.5">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-moei-bronze" />
              <span className="text-xs font-semibold uppercase tracking-wider text-moei-bronze">
                Live · SSE connected
              </span>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-8">
        {/* ===== AI Leadership Advisor ===== */}
        <AdvisorBox />

        {/* ===== Brief-mandated operational KPIs ===== */}
        <OperationalKpiRow op={opKpis} feedback={feedback} />

        {/* ===== KPI row ===== */}
        <div className="mt-3">
          <KpiRow stats={stats} notifs={notifs} />
        </div>

        {/* ===== Voice contact centre ===== */}
        <VoiceCentreCard voice={voice} />

        {/* ===== Live ticker (full width) ===== */}
        <Card title="Live Omnichannel Activity" icon={<Activity size={14} />} className="mt-6">
          <ActivityTicker events={activity} />
        </Card>

        {/* ===== Charts row 1: forecast + sentiment ===== */}
        <div className="mt-6 grid gap-4 lg:grid-cols-3">
          <Card title="7-day demand forecast" icon={<TrendingUp size={14} />} span={2}>
            <ForecastChart data={forecast} />
            {forecast && (
              <p className="mt-2 text-[10px] text-moei-muted">{forecast.method}</p>
            )}
          </Card>
          <Card title="Sentiment trend (14 days)" icon={<Sparkles size={14} />}>
            <SentimentChart data={sentiment} />
          </Card>
        </div>

        {/* ===== Cases + channels ===== */}
        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <Card title="Cases by service (7d)" icon={<Briefcase size={14} />}>
            <SimpleBar items={stats?.by_service ?? []} labelKey="service" />
          </Card>
          <Card title="Cases by channel (7d)" icon={<Globe size={14} />}>
            <ChannelBars items={stats?.by_channel ?? []} />
          </Card>
        </div>

        {/* ===== Heatmap + Risk ===== */}
        <div className="mt-6 grid gap-4 lg:grid-cols-3">
          <Card title="Workforce heatmap · day × hour" icon={<Calendar size={14} />} span={2}>
            <WorkforceHeatmap data={heatmap} />
          </Card>
          <Card title="Top escalation risk" icon={<AlertTriangle size={14} />}>
            <RiskList items={risks?.items ?? []} />
          </Card>
        </div>

        {/* ===== Notifications + Intents ===== */}
        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <Card title="Outbound engagement" icon={<BellRing size={14} />}>
            <NotificationsPanel notifs={notifs} />
          </Card>
          <Card title="Top intents (7d)" icon={<Users size={14} />}>
            <SimpleBar items={stats?.by_intent ?? []} labelKey="intent" />
          </Card>
        </div>
      </section>
    </div>
  );
}

// ---- Components ----------------------------------------------------------

function Card({
  title, icon, span, className = "", children,
}: { title: string; icon?: React.ReactNode; span?: number; className?: string; children: React.ReactNode }) {
  return (
    <div className={"rounded-sm border border-moei-line bg-white p-5 " + (span === 2 ? "lg:col-span-2 " : "") + className}>
      <h3 className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-moei-ink">
        {icon}{title}
      </h3>
      {children}
    </div>
  );
}

function Kpi({
  label, value, sub, accent, icon: Icon,
}: { label: string; value: string; sub?: string; accent?: boolean; icon?: typeof Activity }) {
  return (
    <div className={"rounded-sm border bg-white p-4 " + (accent ? "border-moei-bronze/40" : "border-moei-line")}>
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-moei-muted">
        {Icon && <Icon size={11} />} {label}
      </div>
      <div className={"mt-1.5 text-2xl font-bold " + (accent ? "text-moei-bronze" : "text-moei-ink")}>
        {value}
      </div>
      {sub && <div className="mt-1 text-[10px] text-moei-muted">{sub}</div>}
    </div>
  );
}

function OperationalKpiRow({ op, feedback }: { op: OpKpis | null; feedback: Feedback | null }) {
  // The brief-mandated success metrics: FCR, deflection, AHT, cross-channel continuity, CSAT, CES
  const aht = op?.avg_handle_time_minutes ?? 0;
  const ahtDisplay = aht < 1 ? `${(op?.avg_handle_time_seconds ?? 0).toFixed(0)}s`
                    : aht < 60 ? `${aht.toFixed(1)} min`
                    : `${(aht / 60).toFixed(1)} h`;
  const csat = feedback?.totals.avg_csat_5;
  const ces = feedback?.totals.avg_ces_5;
  return (
    <div className="rounded-sm border border-moei-bronze/40 bg-moei-cream/40 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="moei-kicker">Brief success metrics · last 7 days</div>
        <span className="text-[10px] text-moei-muted">{op?.window || "loading…"}</span>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <KpiInline
          label="First-Contact Resolution"
          value={op ? `${op.first_contact_resolution_pct}%` : "…"}
          hint="Resolved < 1h, single channel"
          tone="accent"
        />
        <KpiInline
          label="Channel Deflection"
          value={op ? `${op.channel_deflection_pct}%` : "…"}
          hint="Cases handled without human escalation"
          tone={op && op.channel_deflection_pct >= 60 ? "accent" : "neutral"}
        />
        <KpiInline
          label="Avg Handle Time"
          value={ahtDisplay}
          hint="Creation → resolution"
          tone="neutral"
        />
        <KpiInline
          label="Cross-Channel Continuity"
          value={op ? `${op.cross_channel_continuity_pct}%` : "…"}
          hint="Users active on >1 channel"
          tone="accent"
        />
        <KpiInline
          label="CSAT"
          value={csat !== null && csat !== undefined ? `${csat.toFixed(1)} / 5` : "—"}
          hint={`${feedback?.totals.responses_30d ?? 0} responses 30d`}
          tone="accent"
        />
        <KpiInline
          label="Customer Effort"
          value={ces !== null && ces !== undefined ? `${ces.toFixed(1)} / 5` : "—"}
          hint={`${feedback?.totals.effortless_pct ?? 0}% rated 'easy'`}
          tone="neutral"
        />
      </div>
    </div>
  );
}

function KpiInline({ label, value, hint, tone }: { label: string; value: string; hint: string; tone: "accent" | "neutral" }) {
  return (
    <div className="rounded-sm bg-white p-3">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-moei-muted">{label}</div>
      <div className={"mt-1 text-2xl font-bold " + (tone === "accent" ? "text-moei-bronze" : "text-moei-ink")}>
        {value}
      </div>
      <div className="mt-1 text-[10px] text-moei-muted">{hint}</div>
    </div>
  );
}

function KpiRow({ stats, notifs }: { stats: CrmStats | null; notifs: Notifs | null }) {
  const t = stats?.totals ?? {};
  const totalCases = (t.today as number) ?? 0;
  const weekCases = (t.week as number) ?? 0;
  const openCases = (t.open as number) ?? 0;
  const escalated = (t.escalated as number) ?? 0;
  const resolved = (t.resolved as number) ?? 0;
  const high = (t.high_priority as number) ?? 0;
  const avgSentiment = t.avg_sentiment as number | null;
  const resolutionRate = weekCases > 0 ? Math.round((resolved / weekCases) * 100) : 0;
  const csat = avgSentiment !== null && avgSentiment !== undefined ? (avgSentiment * 5).toFixed(1) : "—";

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
      <Kpi label="Cases today" value={totalCases.toString()} icon={Activity} accent />
      <Kpi label="Cases (7d)" value={weekCases.toString()} icon={Briefcase} />
      <Kpi label="Open" value={openCases.toString()} sub={`${high} high/critical`} icon={AlertTriangle} />
      <Kpi label="Resolved" value={resolved.toString()} sub={`${resolutionRate}% resolution`} icon={TrendingUp} accent />
      <Kpi label="Escalated" value={escalated.toString()} icon={AlertTriangle} />
      <Kpi label="CSAT proxy" value={`${csat} / 5`} sub="Sentiment-derived" icon={Sparkles} accent />
      <Kpi label="Outbound queued" value={(notifs?.totals?.upcoming ?? 0).toString()} sub={`${notifs?.totals?.sent_week ?? 0} sent (7d)`} icon={BellRing} />
    </div>
  );
}

function ActivityTicker({ events }: { events: ActivityEvent[] }) {
  if (!events.length) {
    return <p className="text-xs text-moei-muted">Waiting for live events…</p>;
  }
  return (
    <ul className="max-h-[260px] divide-y divide-moei-line/50 overflow-y-auto pr-2">
      {events.map((e) => {
        const Icon = CHANNEL_ICON[e.channel ?? "web"] ?? Globe;
        return (
          <li key={e.id} className="flex items-start gap-3 py-2">
            <span className={"inline-flex h-5 items-center gap-1 rounded-sm border-0 px-1.5 text-[10px] font-semibold uppercase " + (EVENT_COLOR[e.event_type] ?? "bg-slate-100 text-slate-700")}>
              {e.event_type}
            </span>
            <Icon size={12} className="mt-0.5 text-moei-muted" />
            <span className="flex-1 truncate text-xs text-moei-ink">
              <span className="font-semibold">{e.user_name ?? "—"}</span>
              <span className="mx-1.5 text-moei-muted">·</span>
              {e.summary}
            </span>
            <span className="text-[10px] text-moei-muted">{new Date(e.at).toLocaleTimeString("en-GB")}</span>
          </li>
        );
      })}
    </ul>
  );
}

function ForecastChart({ data }: { data: Forecast | null }) {
  if (!data) return <Loading h={180} />;
  const series = [
    ...data.history.map(d => ({ day: d.day.slice(5), actual: d.value })),
    ...data.forecast.map(d => ({ day: d.day.slice(5), forecast: d.value })),
  ];
  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={series}>
        <defs>
          <linearGradient id="actualGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#9c8853" stopOpacity={0.5} />
            <stop offset="100%" stopColor="#9c8853" stopOpacity={0.05} />
          </linearGradient>
          <linearGradient id="forecastGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#28bfa8" stopOpacity={0.55} />
            <stop offset="100%" stopColor="#28bfa8" stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#e6dfd0" />
        <XAxis dataKey="day" tick={{ fontSize: 10, fill: "#7a7a7a" }} />
        <YAxis tick={{ fontSize: 10, fill: "#7a7a7a" }} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Area type="monotone" dataKey="actual" stroke="#9c8853" fill="url(#actualGrad)" name="Actual (last 14d)" />
        <Area type="monotone" dataKey="forecast" stroke="#28bfa8" fill="url(#forecastGrad)" strokeDasharray="5 4" name="Forecast (next 7d)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function SentimentChart({ data }: { data: Sentiment | null }) {
  if (!data) return <Loading h={180} />;
  const series = data.series.map(s => ({
    day: s.day.slice(5),
    avg: s.avg ?? 0,
    neg: s.negative_count,
  }));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={series}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e6dfd0" />
        <XAxis dataKey="day" tick={{ fontSize: 10, fill: "#7a7a7a" }} />
        <YAxis tick={{ fontSize: 10, fill: "#7a7a7a" }} yAxisId="L" domain={[0, 1]} />
        <YAxis tick={{ fontSize: 10, fill: "#7a7a7a" }} yAxisId="R" orientation="right" />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Line yAxisId="L" type="monotone" dataKey="avg" stroke="#28bfa8" strokeWidth={2} name="Avg sentiment" dot={false} />
        <Line yAxisId="R" type="monotone" dataKey="neg" stroke="#E4002B" strokeWidth={2} name="Negative count" dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function SimpleBar({ items, labelKey }: { items: any[]; labelKey: string }) {
  if (!items.length) return <Loading h={180} />;
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={items}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e6dfd0" />
        <XAxis dataKey={labelKey} tick={{ fontSize: 10, fill: "#7a7a7a" }} />
        <YAxis tick={{ fontSize: 10, fill: "#7a7a7a" }} />
        <Tooltip />
        <Bar dataKey="n" fill="#9c8853" name="Count" />
      </BarChart>
    </ResponsiveContainer>
  );
}

function ChannelBars({ items }: { items: { channel: string; n: number }[] }) {
  if (!items.length) return <Loading h={180} />;
  const max = Math.max(...items.map(i => i.n));
  return (
    <div className="space-y-3">
      {items.map(i => {
        const pct = Math.round((i.n / max) * 100);
        const Icon = CHANNEL_ICON[i.channel] ?? Globe;
        return (
          <div key={i.channel}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="flex items-center gap-1.5 text-moei-body">
                <Icon size={12} className="text-moei-bronze" /> {i.channel}
              </span>
              <span className="font-semibold text-moei-ink">{i.n}</span>
            </div>
            <div className="h-2 rounded-full bg-moei-line">
              <div className="h-2 rounded-full bg-moei-bronze" style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function WorkforceHeatmap({ data }: { data: Heatmap | null }) {
  if (!data) return <Loading h={220} />;
  const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  // Group cells into a [dow][hour] grid
  const grid: number[][] = days.map(() => Array(24).fill(0));
  const agentGrid: number[][] = days.map(() => Array(24).fill(0));
  let maxCases = 0;
  for (const c of data.cells) {
    grid[c.dow][c.hour] = c.avg_cases;
    agentGrid[c.dow][c.hour] = c.recommended_agents;
    if (c.avg_cases > maxCases) maxCases = c.avg_cases;
  }
  const hours = Array.from({ length: 24 }, (_, i) => i);
  return (
    <div className="overflow-x-auto">
      <table className="w-full table-fixed border-collapse text-[9px]">
        <thead>
          <tr>
            <th className="w-10 text-right pr-2 font-normal text-moei-muted"></th>
            {hours.map(h => (
              <th key={h} className="w-7 text-center font-normal text-moei-muted">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {days.map((d, dow) => (
            <tr key={d}>
              <td className="pr-2 text-right text-[10px] font-semibold text-moei-ink">{d}</td>
              {hours.map(h => {
                const v = grid[dow][h];
                const intensity = maxCases > 0 ? v / maxCases : 0;
                const bg = intensity === 0
                  ? "#f6f3ec"
                  : intensity < 0.2 ? "#f0e9d7"
                  : intensity < 0.4 ? "#e3d6a6"
                  : intensity < 0.6 ? "#d4be75"
                  : intensity < 0.8 ? "#b59c52" : "#7a6a3f";
                return (
                  <td key={h} className="border border-white" style={{ background: bg }} title={`${d} ${h}:00 — ${v.toFixed(1)} cases · ${agentGrid[dow][h]} agents`}>
                    <div className="aspect-square" />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {data.peak && (
        <p className="mt-3 text-[11px] text-moei-muted">
          Peak demand: <span className="font-semibold text-moei-ink">{data.peak.day} {data.peak.hour}:00</span>
          {" "}— {data.peak.avg_cases.toFixed(1)} cases/hr → recommend{" "}
          <span className="font-semibold text-moei-bronze">{data.peak.recommended_agents} agents</span>
        </p>
      )}
    </div>
  );
}

function RiskList({ items }: { items: Risk["items"] }) {
  if (!items.length) return <p className="text-xs text-moei-muted">No users at risk.</p>;
  return (
    <ul className="space-y-2">
      {items.map(r => (
        <li key={r.user_id} className="flex items-center justify-between border-b border-moei-line/40 pb-2 last:border-0 last:pb-0">
          <div className="min-w-0">
            <div className="truncate text-xs font-semibold text-moei-ink">{r.user_name}</div>
            <div className="text-[10px] text-moei-muted">
              {r.open_cases} open · {r.high_priority} high · sentiment {r.avg_sentiment ?? "—"}
            </div>
          </div>
          <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-800">
            {r.risk_score}
          </span>
        </li>
      ))}
    </ul>
  );
}

function NotificationsPanel({ notifs }: { notifs: Notifs | null }) {
  if (!notifs) return <Loading h={180} />;
  const total = notifs.by_template.reduce((s, t) => s + t.n, 0) || 1;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        <Mini label="Upcoming" value={notifs.totals.upcoming} accent />
        <Mini label="Sent today" value={notifs.totals.sent_today} />
        <Mini label="Sent (7d)" value={notifs.totals.sent_week} />
        <Mini label="Failed" value={notifs.totals.failed} danger={notifs.totals.failed > 0} />
      </div>
      <div className="border-t border-moei-line pt-3">
        <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-moei-muted">By template</div>
        {notifs.by_template.map(t => {
          const pct = Math.round((t.n / total) * 100);
          return (
            <div key={t.template} className="mb-2">
              <div className="mb-0.5 flex justify-between text-[11px]">
                <span className="capitalize text-moei-body">{t.template.replace(/_/g, " ")}</span>
                <span className="text-moei-muted">{t.n}</span>
              </div>
              <div className="h-1.5 rounded-full bg-moei-line">
                <div className="h-1.5 rounded-full bg-moei-bronze" style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Mini({ label, value, accent, danger }: { label: string; value: number; accent?: boolean; danger?: boolean }) {
  return (
    <div className={"rounded-sm border bg-white p-3 " + (accent ? "border-moei-bronze/40" : danger ? "border-red-200" : "border-moei-line")}>
      <div className="text-[10px] font-semibold uppercase tracking-wider text-moei-muted">{label}</div>
      <div className={"mt-1 text-xl font-bold " + (accent ? "text-moei-bronze" : danger ? "text-red-600" : "text-moei-ink")}>
        {value}
      </div>
    </div>
  );
}

function Loading({ h }: { h: number }) {
  return (
    <div className="flex items-center justify-center text-xs text-moei-muted" style={{ height: h }}>
      Loading…
    </div>
  );
}

const fmtCallDur = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;

type Advice = { answer: string; root_causes: string[]; recommended_actions: string[]; degraded?: boolean };
const ADVISOR_SUGGESTIONS = [
  "Why might satisfaction be at risk this week?",
  "Which service needs the most attention right now?",
  "Where are we likely to see escalations?",
];

function AdvisorBox() {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [advice, setAdvice] = useState<Advice | null>(null);

  async function ask(question?: string) {
    const text = (question ?? q).trim();
    if (!text || busy) return;
    setQ(text);
    setBusy(true);
    setAdvice(null);
    try {
      const r = await fetch(`${API_URL}/analytics/advisor`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text }),
      });
      setAdvice(await r.json());
    } catch {
      setAdvice({ answer: "Could not reach the advisor.", root_causes: [], recommended_actions: [] });
    } finally { setBusy(false); }
  }

  return (
    <div className="rounded-sm border border-moei-bronze/50 bg-gradient-to-br from-moei-cream/60 to-white p-5">
      <div className="flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-moei-bronze text-white">
          <Sparkles size={16} />
        </span>
        <div>
          <div className="text-sm font-bold text-moei-ink">AI Leadership Advisor</div>
          <div className="text-[11px] text-moei-muted">Ask about performance in plain language — grounded in live data.</div>
        </div>
      </div>

      <div className="mt-3 flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask()}
          placeholder="e.g. Why did customer satisfaction drop this week?"
          className="flex-1 rounded-md border border-moei-line bg-white px-3 py-2 text-sm outline-none focus:border-moei-bronze"
        />
        <button onClick={() => ask()} disabled={busy} className="moei-btn-primary disabled:opacity-60">
          {busy ? "Analysing…" : "Ask"}
        </button>
      </div>

      {!advice && !busy && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {ADVISOR_SUGGESTIONS.map((s) => (
            <button key={s} onClick={() => ask(s)}
              className="rounded-full border border-moei-line bg-white px-2.5 py-1 text-[11px] text-moei-body hover:border-moei-bronze hover:text-moei-bronze">
              {s}
            </button>
          ))}
        </div>
      )}

      {advice && (
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <div className="md:col-span-3 rounded-md bg-white border border-moei-line p-3">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-moei-bronze">Answer</div>
            <p className="mt-1 text-sm text-moei-ink">{advice.answer}</p>
          </div>
          {advice.root_causes?.length > 0 && (
            <div className="rounded-md bg-white border border-moei-line p-3 md:col-span-1">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-moei-muted">Likely root causes</div>
              <ul className="mt-1 space-y-1 text-xs text-moei-body">
                {advice.root_causes.map((c, i) => <li key={i} className="flex gap-1.5"><span className="text-moei-bronze">•</span>{c}</li>)}
              </ul>
            </div>
          )}
          {advice.recommended_actions?.length > 0 && (
            <div className="rounded-md bg-white border border-moei-line p-3 md:col-span-2">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-moei-muted">Recommended actions</div>
              <ul className="mt-1 space-y-1 text-xs text-moei-body">
                {advice.recommended_actions.map((a, i) => <li key={i} className="flex gap-1.5"><span className="text-emerald-600">✓</span>{a}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function VoiceCentreCard({ voice }: { voice: VoiceStats | null }) {
  return (
    <Card title="Voice Contact Centre — automated call analytics" icon={<Phone size={14} />} className="mt-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-moei-muted">
          Every call is recorded, transcribed, summarised, and quality-scored automatically.
        </p>
        <Link href="/admin/calls" className="text-xs font-semibold text-moei-bronze hover:underline">
          View all recordings →
        </Link>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-5">
        <VoiceKpi icon={<Phone size={14} />} label="Calls handled" value={voice ? String(voice.total) : "…"} sub={voice ? `${voice.today} today` : ""} />
        <VoiceKpi icon={<Gauge size={14} />} label="Avg quality" value={voice ? String(voice.avg_qa) : "…"} sub="of 100" tone={voice && voice.avg_qa >= 80 ? "good" : "warn"} />
        <VoiceKpi icon={<CheckCircle2 size={14} />} label="Resolved 1st call" value={voice ? `${voice.resolution_rate}%` : "…"} tone={voice && voice.resolution_rate >= 70 ? "good" : "warn"} />
        <VoiceKpi icon={<Activity size={14} />} label="Avg sentiment" value={voice ? `${voice.avg_sentiment}%` : "…"} tone={voice && voice.avg_sentiment >= 60 ? "good" : "warn"} />
        <VoiceKpi icon={<Mic size={14} />} label="Avg length" value={voice ? fmtCallDur(voice.avg_duration) : "…"} />
      </div>
    </Card>
  );
}

function VoiceKpi({ icon, label, value, sub, tone }: { icon: React.ReactNode; label: string; value: string; sub?: string; tone?: "good" | "warn" }) {
  return (
    <div className="rounded-sm border border-moei-line bg-white p-3">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-moei-muted">
        <span className="text-moei-bronze">{icon}</span> {label}
      </div>
      <div className={"mt-1 text-xl font-bold " + (tone === "good" ? "text-emerald-600" : tone === "warn" ? "text-amber-600" : "text-moei-ink")}>
        {value}
      </div>
      {sub && <div className="text-[10px] text-moei-muted">{sub}</div>}
    </div>
  );
}
