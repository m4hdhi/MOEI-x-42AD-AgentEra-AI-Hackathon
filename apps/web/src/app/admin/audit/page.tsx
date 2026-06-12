"use client";

import { useEffect, useMemo, useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Database,
  FileSearch,
  RefreshCw,
  Search,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { API_URL, cn } from "@/lib/utils";

type AuditPayload = Record<string, any>;
type AuditEvent = { node: string; payload: AuditPayload; at: string; synthetic?: boolean };
type AuditResult = {
  reference: string;
  correlation_id?: string;
  case_number?: string;
  user_id?: string;
  user_name?: string;
  title?: string;
  source?: string;
  source_status?: string;
  event_count?: number;
  events: AuditEvent[];
  fetched_at?: string;
};
type RecentAudit = {
  reference: string;
  correlation_id?: string;
  case_number?: string;
  user_id?: string;
  user_name?: string;
  title?: string;
  service?: string;
  intent?: string;
  status?: string;
  priority?: string;
  updated_at?: string;
  audit_events?: number;
  kind?: string;
};

function AuditInner() {
  const params = useSearchParams();
  const [cid, setCid] = useState(params.get("cid") ?? "");
  const [result, setResult] = useState<AuditResult | null>(null);
  const [recent, setRecent] = useState<RecentAudit[]>([]);
  const [loading, setLoading] = useState(false);
  const [recentLoading, setRecentLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadRecent() {
    setRecentLoading(true);
    try {
      const r = await fetch(`${API_URL}/copilot/audit/recent?limit=30`, { cache: "no-store" });
      if (!r.ok) throw new Error(`Recent audit feed failed: HTTP ${r.status}`);
      const data = await r.json();
      setRecent(data.items || []);
    } catch (e) {
      setError(String(e));
    } finally {
      setRecentLoading(false);
    }
  }

  async function load(theCid?: string) {
    const c = (theCid ?? cid).trim();
    if (!c) return;
    setCid(c);
    setError("");
    setLoading(true);
    try {
      const r = await fetch(`${API_URL}/copilot/audit/${encodeURIComponent(c)}`, { cache: "no-store" });
      if (!r.ok) {
        setResult(null);
        setError(`No audit record found for ${c} (HTTP ${r.status}). Try a case number, call id, SZHP reference, or correlation id.`);
        return;
      }
      const data = await r.json();
      setResult(data);
    } catch (e) {
      setResult(null);
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadRecent();
    const fromUrl = params.get("cid");
    if (fromUrl) load(fromUrl);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const events = result?.events || [];
  const liveRows = useMemo(() => events.filter((event) => !event.synthetic).length, [events]);
  const reconstructedRows = events.length - liveRows;

  return (
    <div className="min-h-screen bg-moei-cream/30">
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-moei-bronze">
                <ShieldCheck size={18} />
                <span className="moei-kicker">UAE PDPL · Article 7</span>
              </div>
              <h1 className="mt-3 moei-h-section">Audit Trail · Right to Explanation</h1>
              <p className="mt-2 max-w-3xl text-sm text-moei-body">
                Inspect what happened behind a citizen request: exact agent audit rows when available, with a live CRM reconstruction when the low-level trace was not written for that flow.
              </p>
            </div>
            <button onClick={loadRecent} className="moei-btn-secondary" disabled={recentLoading}>
              <RefreshCw size={15} className={cn(recentLoading && "animate-spin")} />
              Refresh
            </button>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-6 py-8 lg:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <div className="rounded-sm border border-moei-line bg-white p-4">
            <label className="moei-kicker">Case, call, SZHP reference, or correlation id</label>
            <div className="mt-3 flex gap-2">
              <input
                value={cid}
                onChange={(e) => setCid(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") load();
                }}
                placeholder="MOEI-CASE-20260611-0001"
                className="min-w-0 flex-1 rounded-sm border border-moei-line bg-white px-3 py-2 text-sm outline-none focus:border-moei-bronze"
              />
              <button onClick={() => load()} disabled={!cid || loading} className="moei-btn-primary">
                <Search size={14} /> Look up
              </button>
            </div>
          </div>

          <div className="rounded-sm border border-moei-line bg-white">
            <div className="flex items-center justify-between border-b border-moei-line px-4 py-3">
              <div>
                <div className="font-semibold text-moei-ink">Recent audit records</div>
                <div className="text-xs text-moei-muted">{recentLoading ? "Loading live records..." : `${recent.length} live references`}</div>
              </div>
              <Database size={18} className="text-moei-bronze" />
            </div>
            <div className="max-h-[620px] overflow-auto p-2">
              {recent.length === 0 && !recentLoading && (
                <div className="rounded-sm bg-moei-cream/50 p-4 text-sm text-moei-muted">
                  No recent records found. Create a case, call, or loan assessment and it will appear here.
                </div>
              )}
              {recent.map((item) => {
                const active = result?.reference === item.reference || result?.case_number === item.case_number;
                return (
                  <button
                    key={`${item.kind}-${item.reference}-${item.updated_at}`}
                    onClick={() => load(item.reference || item.correlation_id)}
                    className={cn(
                      "mb-2 w-full rounded-sm border p-3 text-left transition hover:border-moei-bronze/70 hover:bg-moei-cream/40",
                      active ? "border-moei-bronze bg-moei-cream/50" : "border-moei-line bg-white"
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-moei-ink">{item.title || item.reference}</div>
                        <div className="mt-1 truncate font-mono text-[11px] text-moei-muted">{item.reference}</div>
                      </div>
                      <span className="rounded-full bg-moei-cream px-2 py-1 text-[10px] font-semibold uppercase text-moei-bronze">
                        {item.kind || "record"}
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                      {item.status && <Pill>{item.status}</Pill>}
                      {item.service && <Pill>{item.service}</Pill>}
                      <Pill>{item.audit_events ? `${item.audit_events} trace rows` : "CRM timeline"}</Pill>
                    </div>
                    <div className="mt-2 flex items-center gap-1 text-[11px] text-moei-muted">
                      <Clock3 size={12} />
                      {formatDate(item.updated_at)}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </aside>

        <main className="space-y-5">
          {error && (
            <div className="flex items-start gap-3 rounded-sm border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
              <AlertCircle size={18} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {!result && !loading && (
            <div className="rounded-sm border border-moei-line bg-white p-10 text-center">
              <FileSearch className="mx-auto text-moei-bronze" size={34} />
              <h2 className="mt-4 text-xl font-semibold text-moei-ink">Select a record to inspect</h2>
              <p className="mx-auto mt-2 max-w-md text-sm text-moei-body">
                Pick a recent item or paste a reference. The page reads from the live API and links the timeline back to citizen, case, call, and service data.
              </p>
            </div>
          )}

          {loading && (
            <div className="rounded-sm border border-moei-line bg-white p-8 text-sm text-moei-body">
              Loading audit timeline...
            </div>
          )}

          {result && !loading && (
            <>
              <div className="rounded-sm border border-moei-line bg-white p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="moei-kicker">{result.source || "audit"} record</div>
                    <h2 className="mt-2 text-2xl font-semibold text-moei-ink">{result.title || result.reference}</h2>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      {result.case_number && <Pill>Case {result.case_number}</Pill>}
                      {result.source_status && <Pill>{result.source_status}</Pill>}
                      <Pill>{events.length} events</Pill>
                      <Pill>{liveRows ? `${liveRows} trace rows` : "CRM reconstruction"}</Pill>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {result.user_id && (
                      <Link href={`/admin/copilot?user=${encodeURIComponent(result.user_id)}`} className="moei-btn-secondary">
                        <UserRound size={14} /> Citizen
                      </Link>
                    )}
                    {result.case_number && (
                      <Link href={`/admin/copilot?case=${encodeURIComponent(result.case_number)}`} className="moei-btn-secondary">
                        <Activity size={14} /> Case
                      </Link>
                    )}
                  </div>
                </div>
                <div className="mt-5 grid gap-3 md:grid-cols-3">
                  <SummaryCard label="Reference" value={result.reference || result.correlation_id || "-"} />
                  <SummaryCard label="Citizen" value={result.user_name || result.user_id || "-"} />
                  <SummaryCard label="Correlation" value={result.correlation_id || "-"} mono />
                </div>
                {reconstructedRows > 0 && (
                  <div className="mt-4 rounded-sm border border-moei-bronze/30 bg-moei-cream/50 p-3 text-xs text-moei-body">
                    Some rows are reconstructed from live CRM tables because this flow did not write a low-level `audit_log` trace. They are marked in the timeline as reconstructed.
                  </div>
                )}
              </div>

              {events.length === 0 ? (
                <div className="rounded-sm border border-moei-line bg-white p-5 text-sm text-moei-muted">
                  The record exists, but no audit events were available yet.
                </div>
              ) : (
                <ol className="relative space-y-4 border-l-2 border-moei-line pl-6">
                  {events.map((event, index) => (
                    <li key={`${event.node}-${event.at}-${index}`} className="relative">
                      <span className="absolute -left-[31px] top-1 flex h-5 w-5 items-center justify-center rounded-full bg-moei-bronze text-[10px] font-bold text-white">
                        {index + 1}
                      </span>
                      <div className="rounded-sm border border-moei-line bg-white p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <CheckCircle2 size={16} className={event.synthetic ? "text-moei-bronze" : "text-emerald-600"} />
                            <span className="text-sm font-semibold text-moei-ink">{nodeLabel(event.node)}</span>
                            {event.synthetic && (
                              <span className="rounded-full bg-moei-cream px-2 py-0.5 text-[10px] font-semibold uppercase text-moei-bronze">
                                reconstructed
                              </span>
                            )}
                          </div>
                          <span className="text-[11px] text-moei-muted">{formatDate(event.at)}</span>
                        </div>
                        <p className="mt-2 text-sm leading-6 text-moei-body">{summarise(event.node, event.payload)}</p>
                        <details className="mt-3">
                          <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-wide text-moei-muted hover:text-moei-bronze">
                            Technical detail
                          </summary>
                          <pre className="mt-2 max-h-72 overflow-auto rounded-sm bg-moei-cream/50 p-3 text-[11px] text-moei-ink">
                            {JSON.stringify(cleanPayload(event.payload), null, 2)}
                          </pre>
                        </details>
                      </div>
                    </li>
                  ))}
                </ol>
              )}

              <div className="rounded-sm border border-moei-bronze/40 bg-moei-cream/40 p-5">
                <div className="text-xs font-semibold uppercase tracking-wider text-moei-bronze">For engineers</div>
                <div className="mt-1 font-semibold text-moei-ink">Full technical traces</div>
                <p className="mt-1 text-xs text-moei-body">
                  If Langfuse is running locally, use it for token timing, routing spans, model calls, and latency analysis. This page stays connected to the operational CRM records used by support staff.
                </p>
                <a
                  href="http://localhost:3001"
                  target="_blank"
                  rel="noreferrer"
                  className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-moei-bronze hover:underline"
                >
                  Open AI traces <ChevronRight size={14} />
                </a>
              </div>
            </>
          )}
        </main>
      </section>
    </div>
  );
}

function Pill({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full bg-emerald-50 px-2.5 py-1 font-semibold text-emerald-800">{children}</span>;
}

function SummaryCard({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-sm border border-moei-line bg-moei-cream/30 p-3">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-moei-muted">{label}</div>
      <div className={cn("mt-1 truncate text-sm font-semibold text-moei-ink", mono && "font-mono text-xs")}>{value}</div>
    </div>
  );
}

const NODE_META: Record<string, { label: string }> = {
  Request: { label: "Citizen request received" },
  Router: { label: "Understood the request" },
  Sentiment: { label: "Read the citizen's tone" },
  Guardrails: { label: "Privacy & policy checks" },
  Knowledge: { label: "Looked up official sources" },
  Worker: { label: "Applied the service rules" },
  Critic: { label: "Quality self-check" },
  Escalation: { label: "Escalation decision" },
  Reply: { label: "Reply sent to citizen" },
  CaseRecord: { label: "CRM case record" },
  Activity: { label: "Citizen activity" },
  Notification: { label: "Outbound notification" },
  OfficerAssignment: { label: "Officer assignment" },
  Resolution: { label: "Case resolution" },
  CallRecording: { label: "Voice call analysis" },
  Assessment: { label: "Loan rescheduling assessment" },
  OfficerDecision: { label: "Officer decision" },
};

function nodeLabel(node: string) {
  return NODE_META[node]?.label ?? node;
}

function summarise(node: string, p: AuditPayload): string {
  switch (node) {
    case "Request":
      return `“${p.message ?? ""}” · channel: ${p.channel ?? "-"}${p.case_number ? ` · case ${p.case_number}` : ""}`;
    case "Router":
      return `Service: ${p.service ?? "-"} · intent: ${p.intent ?? "-"} · confidence ${Math.round((p.confidence ?? 0) * 100)}%`;
    case "Sentiment":
      return p.score == null ? "Not scored" : `Sentiment ${Math.round(p.score * 100)}% ${p.score < 0.4 ? "(negative - handled with care)" : p.score >= 0.7 ? "(positive)" : "(neutral)"}`;
    case "Guardrails":
      return `${p.pii_redacted ? "Personal data redacted. " : "No personal data exposed. "}${p.policy_blocked ? `Blocked: ${p.block_reason}` : "Passed policy checks."}`;
    case "Knowledge": {
      const sources = p.sources ?? [];
      return sources.length ? `Cited ${sources.length} official source(s): ${sources.map((x: any) => x.title).filter(Boolean).join(", ")}` : "No external sources needed.";
    }
    case "Worker": {
      const tools = p.tool_calls ?? [];
      return tools.length ? `Used: ${tools.map((t: any) => t.tool).join(", ")}` : "Answered from the service catalogue.";
    }
    case "Critic":
      return p.score == null ? "Quality score was not recorded." : `Quality score ${Math.round(p.score * 100)}%${p.notes ? ` · ${p.notes}` : ""}`;
    case "Escalation":
      return p.escalated ? `Escalated to a human officer${p.reason ? ` - ${p.reason}` : ""}` : "Resolved by the assistant; no escalation needed.";
    case "Reply":
      return `“${(p.text ?? "").slice(0, 180)}${(p.text ?? "").length > 180 ? "..." : ""}”`;
    case "CaseRecord":
      return `${p.title || p.description || "Case opened"} · ${p.service || "general"} / ${p.intent || "request"} · ${p.status || "open"} priority ${p.priority || "medium"}.`;
    case "Activity":
      return `${p.summary || "Activity event"}${p.channel ? ` · ${p.channel}` : ""}${p.event_type ? ` · ${p.event_type}` : ""}`;
    case "Notification":
      return `${p.template || "Notification"} via ${p.channel || "channel"} is ${p.status || "scheduled"}.`;
    case "OfficerAssignment":
      return `Assigned to ${p.assigned_to || "an officer"} with ${p.priority || "medium"} priority.`;
    case "Resolution":
      return `Case ${p.case_number || ""} moved to ${p.status || "resolved"}.`;
    case "CallRecording":
      return `${p.summary || "Call analysed"} · ${p.language || "unknown language"} · ${p.duration_seconds || 0}s · ${p.resolved ? "resolved" : "follow-up needed"}.`;
    case "Assessment":
      return `${p.recommendation || p.status || "Assessment"} with ${Math.round((p.confidence ?? 0) * 100)}% confidence. Proposed EMI ${money(p.proposed_emi)} over ${p.proposed_term_months || "-"} months.`;
    default:
      return Object.keys(p || {}).length ? "Technical event recorded for this request." : "Event recorded.";
  }
}

function cleanPayload(p: AuditPayload) {
  const { _step, ...rest } = p || {};
  return rest;
}

function formatDate(value?: string) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(undefined, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function money(value: unknown) {
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return "-";
  return new Intl.NumberFormat("en-AE", { style: "currency", currency: "AED", maximumFractionDigits: 0 }).format(n);
}

export default function AuditPage() {
  return (
    <Suspense fallback={null}>
      <AuditInner />
    </Suspense>
  );
}
