"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Phone, ArrowLeft, CheckCircle2, AlertCircle, Gauge, Clock,
  ListChecks, Tag, TrendingUp, TrendingDown, FileText, User,
} from "lucide-react";
import { API_URL } from "@/lib/utils";

type Turn = { role: "agent" | "citizen"; text: string; t?: number };
type Recording = {
  id: string; call_id: string; user_name: string | null; user_id: string | null;
  language: string; duration_seconds: number; turn_count: number; has_audio: boolean;
  transcript: Turn[]; summary: string | null; topics: string[]; action_items: string[];
  intent: string | null; service: string | null;
  sentiment_start: number | null; sentiment_end: number | null; sentiment_avg: number | null;
  resolved: boolean | null; qa_score: number | null; escalated: boolean | null;
  case_number: string | null; analysed: boolean | null; created_at: string;
};

const fmtDur = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;
const pct = (v: number | null) => (v === null ? "—" : `${Math.round(v * 100)}%`);

export default function CallDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [rec, setRec] = useState<Recording | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let stop = false;
    async function load() {
      try {
        const r = await fetch(`${API_URL}/recordings/${id}`);
        if (!r.ok) { setErr(`Recording not found (HTTP ${r.status})`); return; }
        const data = await r.json();
        if (!stop) setRec(data);
        // Keep polling until analysis lands.
        if (!data.analysed && !stop) setTimeout(load, 2500);
      } catch (e) { setErr(String(e)); }
    }
    load();
    return () => { stop = true; };
  }, [id]);

  if (err) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16 text-center text-sm text-moei-muted">
        {err}
        <div className="mt-4"><Link href="/admin/calls" className="moei-btn-ghost">← Back to recordings</Link></div>
      </div>
    );
  }
  if (!rec) {
    return <div className="mx-auto max-w-3xl px-6 py-16 text-center text-sm text-moei-muted">Loading…</div>;
  }

  const sStart = rec.sentiment_start;
  const sEnd = rec.sentiment_end;
  const improved = sStart !== null && sEnd !== null && sEnd >= sStart;

  return (
    <div className="bg-moei-cream/30 min-h-screen">
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-5xl px-6 py-8">
          <Link href="/admin/calls" className="inline-flex items-center gap-1 text-xs text-moei-muted hover:text-moei-bronze">
            <ArrowLeft size={12} /> All recordings
          </Link>
          <div className="mt-3 flex items-start justify-between gap-6">
            <div>
              <div className="flex items-center gap-2">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-moei-cream">
                  <Phone size={16} className="text-moei-bronze" />
                </span>
                <div>
                  <h1 className="text-xl font-bold text-moei-ink">Call record</h1>
                  <div className="text-[11px] text-moei-muted">
                    {new Date(rec.created_at).toLocaleString()} · {fmtDur(rec.duration_seconds)} · {rec.turn_count} exchanges
                  </div>
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className={"flex items-center justify-end gap-1 text-3xl font-bold " +
                (rec.qa_score === null ? "text-slate-300" : rec.qa_score >= 85 ? "text-emerald-600" : rec.qa_score >= 65 ? "text-amber-600" : "text-red-600")}>
                <Gauge size={22} /> {rec.qa_score ?? "—"}
              </div>
              <div className="text-[10px] uppercase tracking-wider text-moei-muted">Quality score</div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            {rec.service && <Badge icon={<Tag size={11} />}>{rec.service}</Badge>}
            {rec.resolved ? (
              <Badge tone="good" icon={<CheckCircle2 size={11} />}>Resolved first call</Badge>
            ) : rec.analysed ? (
              <Badge tone="warn" icon={<AlertCircle size={11} />}>Needs follow-up</Badge>
            ) : (
              <Badge tone="info">Analysing…</Badge>
            )}
            {rec.escalated && <Badge tone="warn">Escalated</Badge>}
            {rec.case_number && (
              <Link href={`/admin/audit?cid=call:${rec.id}`} className="font-mono text-[11px] text-moei-bronze hover:underline">
                {rec.case_number}
              </Link>
            )}
          </div>

          {/* Audio player */}
          {rec.has_audio ? (
            <audio controls className="mt-5 w-full" src={`${API_URL}/recordings/${rec.id}/audio`} />
          ) : (
            <div className="mt-5 rounded-lg border border-dashed border-moei-line bg-white px-4 py-3 text-[11px] text-moei-muted">
              Audio not available for this call (microphone was not captured). Transcript is shown below.
            </div>
          )}
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-8">
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Left: AI summary + analytics */}
          <div className="space-y-5 lg:col-span-1">
            <Card title="AI summary" icon={<FileText size={14} />}>
              <p className="text-sm leading-relaxed text-moei-body">{rec.summary || "Generating…"}</p>
            </Card>

            <Card title="Sentiment trajectory" icon={improved ? <TrendingUp size={14} /> : <TrendingDown size={14} />}>
              <div className="flex items-center justify-between text-sm">
                <div className="text-center">
                  <div className="text-[10px] uppercase tracking-wider text-moei-muted">Start</div>
                  <div className="text-lg font-bold text-moei-ink">{pct(sStart)}</div>
                </div>
                <div className={"text-2xl " + (improved ? "text-emerald-500" : "text-red-500")}>→</div>
                <div className="text-center">
                  <div className="text-[10px] uppercase tracking-wider text-moei-muted">End</div>
                  <div className={"text-lg font-bold " + (improved ? "text-emerald-600" : "text-red-600")}>{pct(sEnd)}</div>
                </div>
              </div>
              <p className="mt-2 text-[11px] text-moei-muted">
                {improved ? "Citizen sentiment improved during the call." : "Citizen sentiment declined — review recommended."}
              </p>
            </Card>

            {rec.topics.length > 0 && (
              <Card title="Topics" icon={<Tag size={14} />}>
                <div className="flex flex-wrap gap-1.5">
                  {rec.topics.map((t) => (
                    <span key={t} className="rounded-full border border-moei-line bg-moei-cream/40 px-2 py-0.5 text-[11px] text-moei-body">{t}</span>
                  ))}
                </div>
              </Card>
            )}

            {rec.action_items.length > 0 && (
              <Card title="Action items" icon={<ListChecks size={14} />}>
                <ul className="space-y-2 text-sm text-moei-body">
                  {rec.action_items.map((a, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-moei-bronze" />
                      {a}
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </div>

          {/* Right: transcript */}
          <div className="lg:col-span-2">
            <Card title="Transcript" icon={<User size={14} />}>
              <ul className="space-y-3">
                {rec.transcript.map((turn, i) => {
                  const isAgent = turn.role === "agent";
                  return (
                    <li key={i} className={"flex gap-3 " + (isAgent ? "" : "flex-row-reverse")}>
                      <span className={"mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase " +
                        (isAgent ? "bg-moei-bronze text-white" : "bg-slate-200 text-slate-700")}>
                        {isAgent ? "MOEI" : "Citizen"}
                      </span>
                      <div className={"max-w-[80%] rounded-2xl px-3 py-2 text-sm " +
                        (isAgent ? "rounded-tl-sm bg-moei-cream/60 text-moei-ink" : "rounded-tr-sm bg-slate-100 text-moei-ink")}>
                        {turn.text}
                        {turn.t !== undefined && (
                          <span className="ml-2 align-middle text-[9px] text-moei-muted">{fmtDur(turn.t)}</span>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </Card>
          </div>
        </div>
      </section>
    </div>
  );
}

function Card({ title, icon, children }: { title: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-moei-line bg-white p-5">
      <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-moei-bronze">
        {icon} {title}
      </div>
      {children}
    </div>
  );
}

function Badge({ children, tone, icon }: { children: React.ReactNode; tone?: "good" | "warn" | "info"; icon?: React.ReactNode }) {
  const cls = tone === "good" ? "bg-emerald-50 text-emerald-700"
    : tone === "warn" ? "bg-amber-50 text-amber-700"
    : tone === "info" ? "bg-blue-50 text-blue-700"
    : "bg-moei-cream text-moei-bronze";
  return (
    <span className={"inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider " + cls}>
      {icon} {children}
    </span>
  );
}
