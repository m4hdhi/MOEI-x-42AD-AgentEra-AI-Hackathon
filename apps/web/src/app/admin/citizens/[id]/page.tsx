"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, ShieldCheck, Phone, Mail, Flag, BadgeCheck, MessageSquare, Mic, Globe,
  Smartphone, CheckCircle2, AlertTriangle, RotateCcw, Send, Clock, Star, FileText,
  Sparkles, TrendingUp, TrendingDown, Minus, Compass,
} from "lucide-react";
import { API_URL } from "@/lib/utils";

type Case = {
  case_number: string; title: string; service: string; intent: string;
  status: string; priority: string; sentiment: number | null; channel: string;
  created_at: string; assigned_to: string | null;
};
type Activity = { id: number; channel: string | null; event_type: string; summary: string; created_at: string };
type Recording = { id: string; duration_seconds: number; summary: string | null; service: string | null; resolved: boolean | null; qa_score: number | null; case_number: string | null; created_at: string };
type Feedback = { csat: number | null; ces: number | null; comment: string | null; case_number: string | null; submitted_at: string };
type Twin = {
  preferred_channel: string | null; frequent_services: string[]; satisfaction_trend: string;
  predicted_next_need: string; life_event_signal: string | null; calls_recorded: number; avg_csat: number | null;
};
type Profile = {
  user_id: string; name: string | null; verified: boolean;
  profile: Record<string, any> | null;
  twin: Twin;
  summary: {
    total_cases: number; open_cases: number; escalated_cases: number; resolved_cases: number;
    avg_sentiment: number | null; first_contact: string | null; last_contact: string | null; channels: string[];
  };
  cases: Case[]; activity: Activity[]; recordings: Recording[]; feedback: Feedback[];
};

const CH_ICON: Record<string, typeof Globe> = { whatsapp: MessageSquare, voice: Mic, web: Globe, mobile: Smartphone };
const STATUS_COLOR: Record<string, string> = {
  open: "bg-blue-50 text-blue-700", escalated: "bg-red-50 text-red-700",
  resolved: "bg-emerald-50 text-emerald-700",
};
const fmtDur = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;

export default function CitizenProfilePage() {
  const { id } = useParams<{ id: string }>();
  const userId = decodeURIComponent(id);
  const [data, setData] = useState<Profile | null>(null);
  const [err, setErr] = useState("");
  const [toast, setToast] = useState<{ msg: string; tone: "ok" | "info" } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [done, setDone] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API_URL}/crm/citizens/${encodeURIComponent(userId)}`);
      if (!r.ok) { setErr(`No record found (HTTP ${r.status})`); return; }
      setData(await r.json());
    } catch (e) { setErr(String(e)); }
  }, [userId]);

  useEffect(() => { load(); }, [load]);

  function flash(msg: string, tone: "ok" | "info" = "ok") {
    setToast({ msg, tone });
    setTimeout(() => setToast(null), 3200);
  }
  function markDone(key: string) {
    setDone((d) => ({ ...d, [key]: true }));
    setTimeout(() => setDone((d) => { const n = { ...d }; delete n[key]; return n; }), 2600);
  }

  async function caseAction(caseNumber: string, action: string) {
    const key = caseNumber + action;
    setBusy(key);
    try {
      await fetch(`${API_URL}/crm/cases/${encodeURIComponent(caseNumber)}/action`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      markDone(key);
      const verb = action === "resolve" ? "resolved" : action === "escalate" ? "escalated" : "reopened";
      flash(`${caseNumber} ${verb}`);
      await load();
    } catch { flash("Action failed", "info"); } finally { setBusy(null); }
  }

  async function sendNotification(template: string, label: string) {
    setBusy(template);
    const openCase = data?.cases.find((c) => c.status !== "resolved");
    try {
      const r = await fetch(`${API_URL}/notifications`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId, channel: "whatsapp", template,
          case_number: openCase?.case_number, scheduled_in_hours: 0,
        }),
      });
      const res = await r.json().catch(() => ({}));
      const d = res.delivery || {};
      markDone(template);
      if (d.reachable && d.mode === "live") {
        flash(`${label} sent to WhatsApp ${d.to}`, "ok");
      } else if (d.reachable) {
        flash(`${label} prepared for WhatsApp ${d.to} (simulated — no live credentials)`, "info");
      } else {
        flash(`${label} queued — citizen has no WhatsApp on file yet`, "info");
      }
      setTimeout(load, 1500);
    } catch { flash("Could not send message", "info"); } finally { setBusy(null); }
  }

  if (err) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16 text-center text-sm text-moei-muted">
        {err}
        <div className="mt-4"><Link href="/admin/citizens" className="moei-btn-ghost">← Back to citizens</Link></div>
      </div>
    );
  }
  if (!data) return <div className="mx-auto max-w-3xl px-6 py-16 text-center text-sm text-moei-muted">Loading…</div>;

  const p = data.profile || {};
  const s = data.summary;

  return (
    <div className="bg-moei-cream/30 min-h-screen pb-16">
      {toast && (
        <div className={"fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold text-white shadow-lg " +
          (toast.tone === "ok" ? "bg-emerald-600" : "bg-slate-700")}>
          <CheckCircle2 size={14} /> {toast.msg}
        </div>
      )}

      {/* Header */}
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-8">
          <Link href="/admin/citizens" className="inline-flex items-center gap-1 text-xs text-moei-muted hover:text-moei-bronze">
            <ArrowLeft size={12} /> All citizens
          </Link>
          <div className="mt-4 flex flex-wrap items-start justify-between gap-6">
            <div className="flex items-center gap-4">
              <span className="flex h-16 w-16 items-center justify-center rounded-full bg-moei-cream text-2xl font-bold text-moei-bronze">
                {(data.name || "?").slice(0, 1).toUpperCase()}
              </span>
              <div>
                <h1 className="flex items-center gap-2 text-2xl font-bold text-moei-ink">
                  {data.name || "Unknown citizen"}
                  {data.verified && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                      <ShieldCheck size={11} /> UAE PASS verified
                    </span>
                  )}
                </h1>
                <div className="mt-1 font-mono text-xs text-moei-muted">{data.user_id}</div>
                <div className="mt-2 flex flex-wrap gap-4 text-xs text-moei-body">
                  {p.mobile && <span className="inline-flex items-center gap-1"><Phone size={12} /> {p.mobile}</span>}
                  {p.email && <span className="inline-flex items-center gap-1"><Mail size={12} /> {p.email}</span>}
                  {p.nationality_en && <span className="inline-flex items-center gap-1"><Flag size={12} /> {p.nationality_en}</span>}
                  {p.user_type && <span className="inline-flex items-center gap-1"><BadgeCheck size={12} /> {p.user_type}</span>}
                </div>
              </div>
            </div>

            {/* Next actions */}
            <div className="flex flex-col items-end gap-2">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-moei-muted">Next actions</div>
              <div className="flex flex-wrap justify-end gap-2">
                <ActionBtn onClick={() => sendNotification("status_update", "Status update")} busy={busy === "status_update"} done={done["status_update"]} icon={<Send size={12} />}>
                  Send status update
                </ActionBtn>
                <ActionBtn onClick={() => sendNotification("doc_reminder", "Document reminder")} busy={busy === "doc_reminder"} done={done["doc_reminder"]} icon={<FileText size={12} />}>
                  Request documents
                </ActionBtn>
                <ActionBtn onClick={() => sendNotification("csat_survey", "Satisfaction survey")} busy={busy === "csat_survey"} done={done["csat_survey"]} icon={<Star size={12} />}>
                  Send survey
                </ActionBtn>
              </div>
            </div>
          </div>

          {/* Summary KPIs */}
          <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-6">
            <Kpi label="Total cases" value={String(s.total_cases)} />
            <Kpi label="Open" value={String(s.open_cases)} tone={s.open_cases > 0 ? "info" : undefined} />
            <Kpi label="Escalated" value={String(s.escalated_cases)} tone={s.escalated_cases > 0 ? "warn" : undefined} />
            <Kpi label="Resolved" value={String(s.resolved_cases)} tone="good" />
            <Kpi label="Avg sentiment" value={s.avg_sentiment === null ? "—" : `${Math.round(s.avg_sentiment * 100)}%`}
              tone={s.avg_sentiment !== null && s.avg_sentiment < 0.4 ? "warn" : "good"} />
            <Kpi label="Channels" value={String(s.channels.length)} sub={s.channels.join(", ")} />
          </div>

          {/* Digital Twin */}
          {data.twin && <DigitalTwin twin={data.twin} />}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-8">
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Cases (with actions) */}
          <div className="lg:col-span-2">
            <Panel title="Cases & complaints" count={data.cases.length}>
              <div className="space-y-2">
                {data.cases.map((c) => (
                  <div key={c.case_number} className="rounded-lg border border-moei-line bg-white p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-[11px] text-moei-bronze">{c.case_number}</span>
                          <span className={"rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase " + (STATUS_COLOR[c.status] || "bg-slate-100 text-slate-700")}>
                            {c.status}
                          </span>
                          <span className="rounded-full bg-moei-cream px-2 py-0.5 text-[10px] text-moei-bronze">{c.service}</span>
                          {c.priority && ["high", "critical"].includes(c.priority) && (
                            <span className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-semibold text-red-700">{c.priority}</span>
                          )}
                        </div>
                        <p className="mt-1 truncate text-sm text-moei-ink">{c.title}</p>
                        <div className="mt-1 flex items-center gap-3 text-[10px] text-moei-muted">
                          <span className="inline-flex items-center gap-1"><Clock size={10} /> {new Date(c.created_at).toLocaleString()}</span>
                          <span className="inline-flex items-center gap-1">{(CH_ICON[c.channel] ? "" : "")}{c.channel}</span>
                          {c.assigned_to && <span>→ {c.assigned_to}</span>}
                        </div>
                      </div>
                      <div className="flex shrink-0 flex-col gap-1">
                        {c.status !== "resolved" && (
                          <MiniBtn onClick={() => caseAction(c.case_number, "resolve")} busy={busy === c.case_number + "resolve"} done={done[c.case_number + "resolve"]} tone="good" icon={<CheckCircle2 size={11} />}>Resolve</MiniBtn>
                        )}
                        {c.status !== "escalated" && c.status !== "resolved" && (
                          <MiniBtn onClick={() => caseAction(c.case_number, "escalate")} busy={busy === c.case_number + "escalate"} done={done[c.case_number + "escalate"]} tone="warn" icon={<AlertTriangle size={11} />}>Escalate</MiniBtn>
                        )}
                        {c.status === "resolved" && (
                          <MiniBtn onClick={() => caseAction(c.case_number, "reopen")} busy={busy === c.case_number + "reopen"} done={done[c.case_number + "reopen"]} icon={<RotateCcw size={11} />}>Reopen</MiniBtn>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                {data.cases.length === 0 && <Empty>No cases yet.</Empty>}
              </div>
            </Panel>

            {/* Call recordings */}
            {data.recordings.length > 0 && (
              <div className="mt-6">
                <Panel title="Call recordings" count={data.recordings.length}>
                  <div className="space-y-2">
                    {data.recordings.map((r) => (
                      <Link key={r.id} href={`/admin/calls/${r.id}`} className="block rounded-lg border border-moei-line bg-white p-3 transition hover:border-moei-bronze">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Phone size={13} className="text-moei-bronze" />
                            <span className="text-xs text-moei-ink">{r.summary || "Call"}</span>
                          </div>
                          <div className="flex items-center gap-3 text-[10px] text-moei-muted">
                            <span>{fmtDur(r.duration_seconds)}</span>
                            {r.qa_score !== null && <span className="font-semibold text-moei-bronze">QA {r.qa_score}</span>}
                            {r.resolved ? <CheckCircle2 size={12} className="text-emerald-600" /> : <AlertTriangle size={12} className="text-amber-600" />}
                          </div>
                        </div>
                      </Link>
                    ))}
                  </div>
                </Panel>
              </div>
            )}
          </div>

          {/* Activity timeline + feedback */}
          <div className="space-y-6">
            <Panel title="Activity timeline" count={data.activity.length}>
              <ol className="relative space-y-3 border-l border-moei-line pl-4">
                {data.activity.map((a) => (
                  <li key={a.id} className="relative">
                    <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full border-2 border-white bg-moei-bronze" />
                    <div className="text-xs text-moei-ink">{a.summary}</div>
                    <div className="text-[10px] text-moei-muted">
                      {a.channel ? a.channel + " · " : ""}{new Date(a.created_at).toLocaleString()}
                    </div>
                  </li>
                ))}
                {data.activity.length === 0 && <Empty>No activity recorded.</Empty>}
              </ol>
            </Panel>

            {data.feedback.length > 0 && (
              <Panel title="Feedback" count={data.feedback.length}>
                <div className="space-y-2">
                  {data.feedback.map((f, i) => (
                    <div key={i} className="rounded-lg border border-moei-line bg-white p-3 text-xs">
                      <div className="flex gap-3">
                        {f.csat !== null && <span>CSAT <b className="text-moei-bronze">{f.csat}/5</b></span>}
                        {f.ces !== null && <span>Effort <b className="text-moei-bronze">{f.ces}/5</b></span>}
                      </div>
                      {f.comment && <p className="mt-1 text-moei-body">“{f.comment}”</p>}
                    </div>
                  ))}
                </div>
              </Panel>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

function DigitalTwin({ twin }: { twin: Twin }) {
  const TrendIcon = twin.satisfaction_trend === "improving" ? TrendingUp
    : twin.satisfaction_trend === "declining" ? TrendingDown : Minus;
  const trendColor = twin.satisfaction_trend === "improving" ? "text-emerald-600"
    : twin.satisfaction_trend === "declining" ? "text-red-600" : "text-moei-muted";
  return (
    <div className="mt-4 rounded-xl border border-moei-bronze/40 bg-gradient-to-br from-moei-cream/50 to-white p-5">
      <div className="flex items-center gap-2">
        <Sparkles size={15} className="text-moei-bronze" />
        <h3 className="text-sm font-bold text-moei-ink">Digital Twin</h3>
        <span className="text-[11px] text-moei-muted">— a learning model of this citizen</span>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <TwinCell label="Preferred channel" value={twin.preferred_channel || "—"} />
        <TwinCell label="Frequent services" value={twin.frequent_services.length ? twin.frequent_services.join(", ") : "—"} />
        <div className="rounded-lg border border-moei-line bg-white p-3">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-moei-muted">Satisfaction trend</div>
          <div className={"mt-1 flex items-center gap-1 text-sm font-semibold capitalize " + trendColor}>
            <TrendIcon size={14} /> {twin.satisfaction_trend}
          </div>
        </div>
        <TwinCell label="Avg CSAT" value={twin.avg_csat !== null ? `${twin.avg_csat}/5` : "—"} />
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-moei-bronze/30 bg-white p-3">
          <div className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-moei-bronze">
            <Compass size={11} /> Predicted next need
          </div>
          <p className="mt-1 text-sm text-moei-ink">{twin.predicted_next_need}</p>
        </div>
        {twin.life_event_signal && (
          <div className="rounded-lg border border-moei-line bg-white p-3">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-moei-muted">Life-event signal</div>
            <p className="mt-1 text-sm text-moei-ink">{twin.life_event_signal}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function TwinCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-moei-line bg-white p-3">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-moei-muted">{label}</div>
      <div className="mt-1 text-sm font-semibold capitalize text-moei-ink">{value}</div>
    </div>
  );
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "good" | "warn" | "info" }) {
  const c = tone === "good" ? "text-emerald-600" : tone === "warn" ? "text-red-600" : tone === "info" ? "text-blue-600" : "text-moei-ink";
  return (
    <div className="rounded-lg border border-moei-line bg-white p-3">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-moei-muted">{label}</div>
      <div className={"mt-1 text-xl font-bold " + c}>{value}</div>
      {sub && <div className="truncate text-[10px] text-moei-muted">{sub}</div>}
    </div>
  );
}

function Panel({ title, count, children }: { title: string; count?: number; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-moei-line bg-white p-5">
      <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-moei-bronze">
        {title} {count !== undefined && <span className="rounded-full bg-moei-cream px-1.5 text-[10px] text-moei-bronze">{count}</span>}
      </h3>
      {children}
    </div>
  );
}

function ActionBtn({ children, onClick, busy, done, icon }: { children: React.ReactNode; onClick: () => void; busy?: boolean; done?: boolean; icon?: React.ReactNode }) {
  return (
    <button onClick={onClick} disabled={busy || done}
      className={"inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold text-white transition disabled:opacity-90 " +
        (done ? "border-emerald-600 bg-emerald-600" : "border-moei-bronze bg-moei-bronze hover:bg-moei-bronze-dark")}>
      {done ? <CheckCircle2 size={12} /> : icon} {busy ? "Sending…" : done ? "Sent" : children}
    </button>
  );
}

function MiniBtn({ children, onClick, busy, done, tone, icon }: { children: React.ReactNode; onClick: () => void; busy?: boolean; done?: boolean; tone?: "good" | "warn"; icon?: React.ReactNode }) {
  const base = tone === "good" ? "border-emerald-300 text-emerald-700 hover:bg-emerald-50"
    : tone === "warn" ? "border-red-300 text-red-700 hover:bg-red-50"
    : "border-moei-line text-moei-body hover:bg-moei-cream/40";
  const doneCls = "border-emerald-600 bg-emerald-600 text-white";
  return (
    <button onClick={onClick} disabled={busy || done}
      className={"inline-flex items-center gap-1 rounded border px-2 py-1 text-[10px] font-semibold transition disabled:opacity-90 " + (done ? doneCls : base)}>
      {done ? <CheckCircle2 size={11} /> : icon} {busy ? "…" : done ? "Done" : children}
    </button>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-6 text-center text-xs text-moei-muted">{children}</p>;
}
