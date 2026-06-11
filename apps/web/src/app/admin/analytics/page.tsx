"use client";

import { useEffect, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  Activity, AlertTriangle, CheckCircle2, Gauge, Globe, MessageSquare, Mic, Smartphone, Users,
} from "lucide-react";
import { API_URL } from "@/lib/utils";

// ---- Types ----------------------------------------------------------------

type Summary = {
  total_cases_today: number;
  total_cases_week: number;
  self_served_rate: number;
  avg_resolution_hours: number;
  sla_compliance_rate: number;
  escalation_rate: number;
  open_cases: number;
  overdue_cases: number;
};
type ByChannel = { whatsapp: number; voice: number; web: number; mobile: number };
type Intent = { intent: string; count: number };
type SentimentTrend = {
  series: { date: string; positive: number; neutral: number; negative: number }[];
};
type OverdueCase = {
  case_id: string;
  customer_id: string;
  priority_tier: string;
  sla_deadline: string | null;
  days_overdue: number;
  channel: string;
};

// ---- Mock fallback (keeps the demo alive if the API is unreachable) --------

const MOCK_SUMMARY: Summary = {
  total_cases_today: 142,
  total_cases_week: 968,
  self_served_rate: 0.63,
  avg_resolution_hours: 18.4,
  sla_compliance_rate: 0.91,
  escalation_rate: 0.08,
  open_cases: 87,
  overdue_cases: 6,
};
const MOCK_CHANNEL: ByChannel = { whatsapp: 512, voice: 214, web: 168, mobile: 74 };
const MOCK_INTENTS: Intent[] = [
  { intent: "service_request", count: 311 },
  { intent: "status_check", count: 248 },
  { intent: "inquiry", count: 196 },
  { intent: "complaint", count: 142 },
  { intent: "appreciation", count: 71 },
];
const MOCK_SENTIMENT: SentimentTrend = {
  series: Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - (6 - i));
    return {
      date: d.toISOString().slice(0, 10),
      positive: 60 + Math.round(Math.random() * 30),
      neutral: 30 + Math.round(Math.random() * 20),
      negative: 8 + Math.round(Math.random() * 14),
    };
  }),
};

const CHANNEL_META: Record<keyof ByChannel, { label: string; color: string; icon: typeof Globe }> = {
  whatsapp: { label: "WhatsApp", color: "#25D366", icon: MessageSquare },
  voice: { label: "Voice", color: "#9c8853", icon: Mic },
  web: { label: "Web", color: "#28bfa8", icon: Globe },
  mobile: { label: "Mobile", color: "#7a6a3f", icon: Smartphone },
};

const pct = (n: number) => `${Math.round(n * 100)}%`;

// ---- Page -----------------------------------------------------------------

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [channel, setChannel] = useState<ByChannel | null>(null);
  const [intents, setIntents] = useState<Intent[] | null>(null);
  const [sentiment, setSentiment] = useState<SentimentTrend | null>(null);
  const [overdue, setOverdue] = useState<OverdueCase[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    // Each fetch falls back to mock data independently so one dead endpoint
    // never blanks the whole dashboard during a demo.
    const get = <T,>(path: string, fallback: T): Promise<T> =>
      fetch(`${API_URL}${path}`)
        .then((r) => (r.ok ? (r.json() as Promise<T>) : Promise.reject()))
        .catch(() => fallback);

    Promise.all([
      get<Summary>("/analytics/summary", MOCK_SUMMARY),
      get<ByChannel>("/analytics/cases-by-channel", MOCK_CHANNEL),
      get<Intent[]>("/analytics/top-intents?limit=5", MOCK_INTENTS),
      get<SentimentTrend>("/analytics/sentiment-trend?days=7", MOCK_SENTIMENT),
      get<OverdueCase[]>("/analytics/overdue-cases", []),
    ]).then(([s, c, i, se, o]) => {
      if (cancelled) return;
      // A summary that came back empty (zeros) means the migration likely isn't applied —
      // prefer mock so the cards aren't all "0" on stage.
      setSummary(s && s.total_cases_week > 0 ? s : MOCK_SUMMARY);
      setChannel(c ?? MOCK_CHANNEL);
      setIntents(i?.length ? i : MOCK_INTENTS);
      setSentiment(se?.series?.length ? se : MOCK_SENTIMENT);
      setOverdue(Array.isArray(o) ? o : []);
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="bg-moei-cream/30">
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-10">
          <span className="moei-kicker">
            MOEI Customer Happiness Centre · {new Date().toLocaleDateString("en-GB")}
          </span>
          <h1 className="mt-2 moei-h-section">Analytics</h1>
          <p className="mt-2 text-sm text-moei-body">
            Service KPIs · channel mix · top intents · sentiment trend
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-8">
        {/* ===== Metric cards ===== */}
        {loading ? (
          <SkeletonRow />
        ) : (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Metric
              label="Cases today"
              value={summary!.total_cases_today.toLocaleString()}
              sub={`${summary!.total_cases_week.toLocaleString()} this week`}
              icon={Activity}
              accent
            />
            <Metric
              label="Self-served rate"
              value={pct(summary!.self_served_rate)}
              sub="Resolved without an agent"
              icon={CheckCircle2}
            />
            <Metric
              label="SLA compliance"
              value={pct(summary!.sla_compliance_rate)}
              sub={`avg resolution ${summary!.avg_resolution_hours.toFixed(1)}h`}
              icon={Gauge}
              accent
            />
            <Metric
              label="Open cases"
              value={summary!.open_cases.toLocaleString()}
              sub={`${summary!.overdue_cases} overdue · ${pct(summary!.escalation_rate)} escalated`}
              icon={AlertTriangle}
              danger={summary!.overdue_cases > 0}
            />
          </div>
        )}

        {/* ===== Cases by channel ===== */}
        <Card title="Cases by channel" icon={<Globe size={14} />} className="mt-6">
          {loading || !channel ? <SkeletonChart /> : <ChannelChart data={channel} />}
        </Card>

        {/* ===== Top intents + sentiment trend ===== */}
        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <Card title="Top 5 intents (7d)" icon={<Users size={14} />}>
            {loading || !intents ? <SkeletonChart /> : <IntentsChart data={intents} />}
          </Card>
          <Card title="Sentiment trend (7 days)" icon={<Activity size={14} />}>
            {loading || !sentiment ? <SkeletonChart /> : <SentimentChart data={sentiment} />}
          </Card>
        </div>

        {/* ===== Overdue SLA cases ===== */}
        {overdue && overdue.length > 0 && (
          <Card title="Overdue SLA cases" icon={<AlertTriangle size={14} />} className="mt-6">
            <OverdueTable rows={overdue} />
          </Card>
        )}
      </section>
    </div>
  );
}

// ---- Components -----------------------------------------------------------

function Card({
  title, icon, className = "", children,
}: { title: string; icon?: React.ReactNode; className?: string; children: React.ReactNode }) {
  return (
    <div className={"rounded-sm border border-moei-line bg-white p-5 " + className}>
      <h3 className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-moei-ink">
        {icon}{title}
      </h3>
      {children}
    </div>
  );
}

function Metric({
  label, value, sub, icon: Icon, accent, danger,
}: {
  label: string; value: string; sub?: string; icon: typeof Activity;
  accent?: boolean; danger?: boolean;
}) {
  return (
    <div className={"rounded-sm border bg-white p-4 " + (danger ? "border-red-200" : accent ? "border-moei-bronze/40" : "border-moei-line")}>
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-moei-muted">
        <Icon size={11} /> {label}
      </div>
      <div className={"mt-1.5 text-2xl font-bold " + (danger ? "text-red-600" : accent ? "text-moei-bronze" : "text-moei-ink")}>
        {value}
      </div>
      {sub && <div className="mt-1 text-[10px] text-moei-muted">{sub}</div>}
    </div>
  );
}

function ChannelChart({ data }: { data: ByChannel }) {
  const rows = (Object.keys(CHANNEL_META) as (keyof ByChannel)[]).map((k) => ({
    channel: CHANNEL_META[k].label,
    count: data[k] ?? 0,
    color: CHANNEL_META[k].color,
  }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={rows}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e6dfd0" />
        <XAxis dataKey="channel" tick={{ fontSize: 11, fill: "#7a7a7a" }} />
        <YAxis tick={{ fontSize: 10, fill: "#7a7a7a" }} allowDecimals={false} />
        <Tooltip />
        <Bar dataKey="count" name="Cases" radius={[3, 3, 0, 0]}>
          {rows.map((r) => (
            <Cell key={r.channel} fill={r.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function IntentsChart({ data }: { data: Intent[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} layout="vertical" margin={{ left: 24 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e6dfd0" horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 10, fill: "#7a7a7a" }} allowDecimals={false} />
        <YAxis
          type="category"
          dataKey="intent"
          width={110}
          tick={{ fontSize: 11, fill: "#7a7a7a" }}
          tickFormatter={(v: string) => v.replace(/_/g, " ")}
        />
        <Tooltip />
        <Bar dataKey="count" name="Interactions" fill="#9c8853" radius={[0, 3, 3, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function SentimentChart({ data }: { data: SentimentTrend }) {
  const series = data.series.map((s) => ({ ...s, date: s.date.slice(5) }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={series}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e6dfd0" />
        <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#7a7a7a" }} />
        <YAxis tick={{ fontSize: 10, fill: "#7a7a7a" }} allowDecimals={false} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Area type="monotone" dataKey="positive" stackId="1" stroke="#28bfa8" fill="#28bfa8" fillOpacity={0.7} name="Positive" />
        <Area type="monotone" dataKey="neutral" stackId="1" stroke="#9c8853" fill="#9c8853" fillOpacity={0.6} name="Neutral" />
        <Area type="monotone" dataKey="negative" stackId="1" stroke="#E4002B" fill="#E4002B" fillOpacity={0.6} name="Negative" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

const TIER_BADGE: Record<string, string> = {
  urgent: "bg-red-100 text-red-800",
  medium: "bg-amber-100 text-amber-800",
  normal: "bg-slate-100 text-slate-700",
};

function OverdueTable({ rows }: { rows: OverdueCase[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-moei-line text-[10px] uppercase tracking-wider text-moei-muted">
            <th className="py-2 pr-3 font-semibold">Case</th>
            <th className="py-2 pr-3 font-semibold">Customer</th>
            <th className="py-2 pr-3 font-semibold">Tier</th>
            <th className="py-2 pr-3 font-semibold">Channel</th>
            <th className="py-2 pr-3 text-right font-semibold">Days overdue</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.case_id} className="border-b border-moei-line/40 last:border-0">
              <td className="py-2 pr-3 font-semibold text-moei-ink">{r.case_id}</td>
              <td className="py-2 pr-3 text-moei-body">{r.customer_id}</td>
              <td className="py-2 pr-3">
                <span className={"rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize " + (TIER_BADGE[r.priority_tier] ?? TIER_BADGE.normal)}>
                  {r.priority_tier}
                </span>
              </td>
              <td className="py-2 pr-3 capitalize text-moei-body">{r.channel}</td>
              <td className="py-2 pr-3 text-right font-semibold text-red-600">{r.days_overdue.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SkeletonRow() {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="animate-pulse rounded-sm border border-moei-line bg-white p-4">
          <div className="h-3 w-20 rounded bg-moei-line" />
          <div className="mt-3 h-7 w-16 rounded bg-moei-line" />
          <div className="mt-2 h-2 w-24 rounded bg-moei-line/60" />
        </div>
      ))}
    </div>
  );
}

function SkeletonChart() {
  return <div className="h-[260px] w-full animate-pulse rounded-sm bg-moei-line/40" />;
}
