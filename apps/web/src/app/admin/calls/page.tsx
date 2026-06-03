"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Phone, ChevronRight, Clock, CheckCircle2, AlertCircle, Gauge, RefreshCw } from "lucide-react";
import { API_URL } from "@/lib/utils";

type Recording = {
  id: string;
  call_id: string;
  user_name: string | null;
  user_id: string | null;
  duration_seconds: number;
  turn_count: number;
  summary: string | null;
  service: string | null;
  resolved: boolean | null;
  qa_score: number | null;
  sentiment_start: number | null;
  sentiment_end: number | null;
  case_number: string | null;
  analysed: boolean | null;
  created_at: string;
};

type Stats = {
  total: number; today: number; avg_qa: number; avg_duration: number;
  resolution_rate: number; avg_sentiment: number;
};

const fmtDur = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;

function qaColor(q: number | null) {
  if (q === null) return "text-slate-400";
  if (q >= 85) return "text-emerald-600";
  if (q >= 65) return "text-amber-600";
  return "text-red-600";
}

export default function CallsPage() {
  const [items, setItems] = useState<Recording[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const [r, s] = await Promise.all([
        fetch(`${API_URL}/recordings?limit=100`).then((x) => x.json()),
        fetch(`${API_URL}/recordings/stats`).then((x) => x.json()),
      ]);
      setItems(r.items || []);
      setStats(s);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 8000); // poll so new calls appear during the demo
    return () => clearInterval(t);
  }, []);

  return (
    <div className="bg-moei-cream/30 min-h-screen">
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-10">
          <div className="flex items-end justify-between">
            <div>
              <span className="moei-kicker">Voice Contact Centre</span>
              <h1 className="mt-2 moei-h-section">Call Recordings & Quality</h1>
              <p className="mt-2 text-sm text-moei-body">
                Every call is recorded, transcribed, summarised, and quality-scored automatically.
              </p>
            </div>
            <button onClick={load} className="moei-btn-ghost text-xs">
              <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
            </button>
          </div>

          {stats && (
            <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-5">
              <Kpi label="Calls handled" value={String(stats.total)} sub={`${stats.today} today`} />
              <Kpi label="Avg quality score" value={`${stats.avg_qa}`} sub="out of 100" tone={stats.avg_qa >= 80 ? "good" : "warn"} />
              <Kpi label="Resolved first call" value={`${stats.resolution_rate}%`} tone={stats.resolution_rate >= 70 ? "good" : "warn"} />
              <Kpi label="Avg call length" value={fmtDur(stats.avg_duration)} />
              <Kpi label="Avg sentiment" value={`${stats.avg_sentiment}%`} tone={stats.avg_sentiment >= 60 ? "good" : "warn"} />
            </div>
          )}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-8">
        {items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-moei-line bg-white py-16 text-center text-sm text-moei-muted">
            <Phone className="mx-auto mb-3 text-moei-bronze" size={24} />
            No calls recorded yet. Place a call from the Call Centre page to see it appear here.
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((r) => (
              <Link
                key={r.id}
                href={`/admin/calls/${r.id}`}
                className="block rounded-xl border border-moei-line bg-white p-4 transition hover:border-moei-bronze hover:shadow-moei-card"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-moei-cream">
                        <Phone size={14} className="text-moei-bronze" />
                      </span>
                      {r.service && (
                        <span className="rounded-full bg-moei-cream px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-moei-bronze">
                          {r.service}
                        </span>
                      )}
                      {r.resolved ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                          <CheckCircle2 size={10} /> Resolved
                        </span>
                      ) : r.analysed ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700">
                          <AlertCircle size={10} /> Follow-up
                        </span>
                      ) : (
                        <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700">Analysing…</span>
                      )}
                      {r.case_number && (
                        <span className="font-mono text-[10px] text-moei-muted">{r.case_number}</span>
                      )}
                    </div>
                    <p className="mt-2 line-clamp-2 text-sm text-moei-ink">
                      {r.summary || "Processing call summary…"}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-moei-muted">
                      <span className="inline-flex items-center gap-1"><Clock size={11} /> {fmtDur(r.duration_seconds)}</span>
                      <span>{r.turn_count} exchanges</span>
                      <span>{new Date(r.created_at).toLocaleString()}</span>
                      {r.user_name && <span>{r.user_name}</span>}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <div className={"flex items-center gap-1 text-lg font-bold " + qaColor(r.qa_score)}>
                      <Gauge size={16} /> {r.qa_score ?? "—"}
                    </div>
                    <span className="text-[10px] text-moei-muted">quality</span>
                    <ChevronRight size={16} className="mt-1 text-moei-muted" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "good" | "warn" }) {
  return (
    <div className="rounded-xl border border-moei-line bg-white p-4">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-moei-muted">{label}</div>
      <div className={"mt-1 text-2xl font-bold " + (tone === "good" ? "text-emerald-600" : tone === "warn" ? "text-amber-600" : "text-moei-ink")}>
        {value}
      </div>
      {sub && <div className="text-[10px] text-moei-muted">{sub}</div>}
    </div>
  );
}
