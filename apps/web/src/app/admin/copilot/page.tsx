"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  Bell,
  CheckCircle2,
  ChevronRight,
  Clock,
  ExternalLink,
  FileText,
  Globe,
  Headphones,
  MessageSquare,
  Radio,
  RefreshCw,
  ShieldAlert,
  UserRound,
} from "lucide-react";
import { API_URL } from "@/lib/utils";

type Turn = { role: "user" | "assistant"; text: string; channel: string };
type ActiveUser = {
  user_id: string;
  name: string;
  mobile?: string | null;
  verified?: boolean;
  preferred_language?: string | null;
  last_seen?: string | null;
  total_cases: number;
  open_cases: number;
  escalated_cases: number;
  avg_sentiment?: number | null;
  channels: string[];
};
type Case = {
  case_number: string;
  user_name: string | null;
  channel: string;
  intent: string;
  service: string;
  title?: string;
  status: string;
  priority: string;
  sentiment: number | null;
  assigned_to?: string | null;
  correlation_id?: string | null;
  updated_at?: string;
  created_at: string;
};
type Activity = {
  id: number;
  channel?: string | null;
  event_type: string;
  summary: string;
  created_at: string;
};
type CustomerDocument = {
  id: string;
  document_type: string;
  status: string;
  original_name?: string | null;
  confidence?: number | null;
  case_number?: string | null;
  created_at: string;
};
type Recording = {
  id: string;
  call_id: string;
  language?: string | null;
  duration_seconds?: number | null;
  summary?: string | null;
  service?: string | null;
  resolved?: boolean;
  qa_score?: number | null;
  sentiment_avg?: number | null;
  escalated?: boolean;
  created_at: string;
};
type FollowUp = {
  id: string;
  channel: string;
  template: string;
  status: string;
  payload?: Record<string, any> | null;
  scheduled_at: string;
  sent_at?: string | null;
  created_at: string;
  case_number?: string | null;
};
type CopilotContext = {
  user_id: string;
  name: string;
  profile: Record<string, any> | null;
  turns: Turn[];
  cases: Case[];
  activity: Activity[];
  documents: CustomerDocument[];
  recordings: Recording[];
  notifications: FollowUp[];
  summary: {
    total_cases: number;
    open_cases: number;
    escalated_cases: number;
    high_priority: number;
    resolved_cases: number;
    avg_sentiment: number | null;
    sentiment_label: string;
    channels: string[];
    last_case_at?: string | null;
  };
  risk: {
    score: number;
    band: string;
    drivers: {
      open_cases: number;
      escalated_cases: number;
      high_priority: number;
      missing_documents: string[];
      avg_sentiment: number | null;
    };
  };
  next_best_action: { type: string; label: string; detail: string };
  data_sources: Record<string, boolean | number>;
  fetched_at: string;
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
const RISK_COLOR: Record<string, string> = {
  critical: "border-red-300 bg-red-50 text-red-800",
  high: "border-orange-300 bg-orange-50 text-orange-800",
  watch: "border-amber-300 bg-amber-50 text-amber-800",
  normal: "border-emerald-300 bg-emerald-50 text-emerald-800",
};

function formatDate(value?: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("en-AE", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "short",
  }).format(new Date(value));
}

function secondsToText(value?: number | null) {
  if (!value) return "0s";
  const minutes = Math.floor(value / 60);
  const seconds = value % 60;
  return minutes ? `${minutes}m ${seconds}s` : `${seconds}s`;
}

export default function CopilotPage() {
  const [users, setUsers] = useState<ActiveUser[]>([]);
  const [userId, setUserId] = useState("");
  const [context, setContext] = useState<CopilotContext | null>(null);
  const [risks, setRisks] = useState<RiskUser[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<string | null>(null);

  const selectedUser = useMemo(
    () => users.find((user) => user.user_id === userId) ?? null,
    [users, userId],
  );

  const loadUsers = useCallback(async () => {
    const response = await fetch(`${API_URL}/copilot/active-users?limit=30`, { cache: "no-store" });
    if (!response.ok) throw new Error(`active users HTTP ${response.status}`);
    const data = await response.json();
    const list = data.users || [];
    setUsers(list);
    if (!userId && list.length) {
      const preferred =
        list.find((user: ActiveUser) => user.verified) ||
        list.find((user: ActiveUser) => user.total_cases > 0 && user.name !== user.user_id) ||
        list[0];
      setUserId(preferred.user_id);
    }
  }, [userId]);

  const loadContext = useCallback(async (id: string) => {
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      const [ctx, risk] = await Promise.all([
        fetch(`${API_URL}/copilot/context/${encodeURIComponent(id)}`, { cache: "no-store" }).then((r) => {
          if (!r.ok) throw new Error(`context HTTP ${r.status}`);
          return r.json();
        }),
        fetch(`${API_URL}/analytics/escalation-risk?limit=6`, { cache: "no-store" }).then((r) => r.json()),
      ]);
      setContext(ctx);
      setRisks(risk.items || []);
      setLastRefresh(new Date().toISOString());
    } catch (err: any) {
      setError(err.message || "Failed to load co-pilot data");
    } finally {
      setBusy(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      await loadUsers();
      if (userId) await loadContext(userId);
    } catch (err: any) {
      setError(err.message || "Failed to refresh co-pilot data");
    }
  }, [loadContext, loadUsers, userId]);

  useEffect(() => {
    loadUsers().catch((err) => setError(err.message || "Failed to load users"));
  }, [loadUsers]);

  useEffect(() => {
    if (!userId) return;
    loadContext(userId);
    const timer = window.setInterval(() => loadContext(userId), 5000);
    return () => window.clearInterval(timer);
  }, [loadContext, userId]);

  async function caseAction(caseNumber: string, action: "assign" | "resolve" | "escalate" | "reopen") {
    const body: Record<string, string> = { action };
    if (action === "assign") body.assigned_to = "MOEI agent";
    const response = await fetch(`${API_URL}/crm/cases/${encodeURIComponent(caseNumber)}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      setError(`Could not ${action} ${caseNumber}`);
      return;
    }
    await loadContext(userId);
    await loadUsers();
  }

  const channelMix = context?.turns.reduce<Record<string, number>>((acc, turn) => {
    acc[turn.channel] = (acc[turn.channel] ?? 0) + 1;
    return acc;
  }, {}) ?? {};

  return (
    <div className="bg-moei-cream/30">
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <span className="moei-kicker">MOEI Customer Happiness Centre</span>
              <h1 className="mt-2 moei-h-section">Agent Co-pilot</h1>
              <p className="mt-2 max-w-3xl text-sm text-moei-body">
                Live operator workspace for citizen context, open cases, documents, call history, risk, and staff actions.
              </p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <select
                value={userId}
                onChange={(event) => setUserId(event.target.value)}
                className="min-w-[280px] rounded-sm border border-moei-line bg-white px-3 py-2 text-xs text-moei-ink"
              >
                {users.length === 0 && <option value="">No live citizens</option>}
                {users.map((user) => (
                  <option key={user.user_id} value={user.user_id}>
                    {user.name} - {user.user_id}
                  </option>
                ))}
              </select>
              <button onClick={refresh} disabled={busy} className="moei-btn-ghost">
                <RefreshCw size={14} className={busy ? "animate-spin" : ""} /> Refresh
              </button>
            </div>
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-4">
            <Metric label="Citizen" value={context?.name || selectedUser?.name || "-"} sub={context?.user_id || userId || "No user selected"} />
            <Metric label="Open cases" value={context?.summary.open_cases ?? selectedUser?.open_cases ?? 0} sub={`${context?.summary.escalated_cases ?? selectedUser?.escalated_cases ?? 0} escalated`} />
            <Metric label="Risk score" value={context?.risk.score ?? 0} sub={context?.risk.band ?? "normal"} tone={context?.risk.band} />
            <Metric label="Last refresh" value={lastRefresh ? formatDate(lastRefresh) : "-"} sub={error ? "Needs attention" : "Polling every 5s"} />
          </div>
          {error && (
            <div className="mt-4 rounded-sm border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-800">
              {error}
            </div>
          )}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-8">
        <LiveCitizens users={users} selectedUserId={userId} onSelect={setUserId} />
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="space-y-6 lg:col-span-8">
            <NextAction context={context} />
            <Transcript turns={context?.turns ?? []} channelMix={channelMix} />
            <CasesTable cases={context?.cases ?? []} onAction={caseAction} />
            <ActivityTimeline activity={context?.activity ?? []} />
          </div>

          <aside className="space-y-4 lg:col-span-4">
            <CitizenCard context={context} selectedUser={selectedUser} />
            <DocumentsCard documents={context?.documents ?? []} />
            <CallsCard recordings={context?.recordings ?? []} />
            <FollowUps followUps={context?.notifications ?? []} />
            <EscalationRisk risks={risks} currentUserId={userId} onSelect={setUserId} />
            <QuickActions userId={userId} latestCase={context?.cases[0]?.case_number ?? null} onDone={() => userId && loadContext(userId)} />
            <SourceStatus sources={context?.data_sources} />
          </aside>
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value, sub, tone }: { label: string; value: string | number; sub: string; tone?: string }) {
  const color = tone ? RISK_COLOR[tone] || RISK_COLOR.normal : "border-moei-line bg-white text-moei-ink";
  return (
    <div className={`rounded-sm border px-4 py-3 ${color}`}>
      <div className="text-[10px] font-semibold uppercase tracking-wider opacity-70">{label}</div>
      <div className="mt-1 truncate text-lg font-semibold">{value}</div>
      <div className="truncate text-[11px] opacity-75">{sub}</div>
    </div>
  );
}

function LiveCitizens({ users, selectedUserId, onSelect }: { users: ActiveUser[]; selectedUserId: string; onSelect: (userId: string) => void }) {
  return (
    <div className="mb-6 rounded-sm border border-moei-line bg-white">
      <div className="flex items-center justify-between border-b border-moei-line bg-moei-cream/50 px-5 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-moei-ink">
          <UserRound size={14} /> Live citizens
        </h2>
        <span className="text-[11px] text-moei-muted">{users.length} visible</span>
      </div>
      <div className="flex gap-3 overflow-x-auto p-4">
        {users.length === 0 && <p className="text-sm text-moei-muted">No citizen activity yet.</p>}
        {users.map((user) => {
          const active = user.user_id === selectedUserId;
          const risky = user.escalated_cases > 0 || (user.avg_sentiment != null && user.avg_sentiment < 0.4);
          return (
            <button
              key={user.user_id}
              onClick={() => onSelect(user.user_id)}
              className={`min-w-[235px] rounded-sm border px-3 py-3 text-left transition ${
                active
                  ? "border-moei-bronze bg-moei-cream text-moei-ink"
                  : "border-moei-line bg-white text-moei-body hover:border-moei-bronze"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold">{user.name}</div>
                  <div className="mt-0.5 truncate font-mono text-[10px] text-moei-muted">{user.user_id}</div>
                </div>
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${risky ? "bg-red-100 text-red-800" : "bg-emerald-50 text-emerald-800"}`}>
                  {risky ? "watch" : "ok"}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-[10px]">
                <span className="rounded-sm bg-white/70 px-2 py-1">
                  <b className="text-moei-ink">{user.open_cases}</b> open
                </span>
                <span className="rounded-sm bg-white/70 px-2 py-1">
                  <b className="text-moei-ink">{user.escalated_cases}</b> esc
                </span>
                <span className="rounded-sm bg-white/70 px-2 py-1">
                  <b className="text-moei-ink">{user.avg_sentiment ?? "-"}</b> sent
                </span>
              </div>
              <div className="mt-2 truncate text-[10px] text-moei-muted">
                {user.verified ? "UAE PASS verified" : "Unverified"} · {formatDate(user.last_seen)}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function NextAction({ context }: { context: CopilotContext | null }) {
  const action = context?.next_best_action;
  return (
    <div className="rounded-sm border border-moei-bronze/40 bg-moei-cream/50 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-moei-bronze">
            <AlertCircle size={16} />
            <span className="text-sm font-semibold">Next best action</span>
          </div>
          <h2 className="mt-2 text-xl font-semibold text-moei-ink">{action?.label ?? "Waiting for live context"}</h2>
          <p className="mt-2 text-sm leading-relaxed text-moei-body">{action?.detail ?? "Select a citizen with activity to generate an operational recommendation."}</p>
        </div>
        <div className={`shrink-0 rounded-sm border px-3 py-2 text-center text-xs font-semibold ${RISK_COLOR[context?.risk.band || "normal"]}`}>
          <div className="text-2xl">{context?.risk.score ?? 0}</div>
          <div className="uppercase tracking-wide">{context?.risk.band ?? "normal"}</div>
        </div>
      </div>
      {context?.risk.drivers.missing_documents?.length ? (
        <div className="mt-4 rounded-sm border border-amber-200 bg-white px-3 py-2 text-xs text-amber-800">
          Missing documents: {context.risk.drivers.missing_documents.map((doc) => doc.replace("_", " ")).join(", ")}
        </div>
      ) : null}
    </div>
  );
}

function Transcript({ turns, channelMix }: { turns: Turn[]; channelMix: Record<string, number> }) {
  return (
    <div className="rounded-sm border border-moei-line bg-white">
      <div className="flex items-center justify-between border-b border-moei-line bg-moei-cream/50 px-5 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-moei-ink">
          <Radio size={14} /> Live transcript
        </h2>
        <div className="flex gap-3 text-[11px] text-moei-muted">
          {Object.entries(channelMix).map(([channel, count]) => (
            <span key={channel}>{channel}: <span className="font-semibold text-moei-ink">{count}</span></span>
          ))}
        </div>
      </div>
      <div className="max-h-[410px] overflow-y-auto p-5">
        {turns.length === 0 && (
          <p className="text-sm text-moei-muted">No live short-term transcript yet. Citizen chat, WhatsApp, or voice turns will appear here when memory is populated.</p>
        )}
        <div className="space-y-3">
          {turns.map((turn, index) => {
            const meta = CHANNEL_META[turn.channel] ?? CHANNEL_META.web;
            const Icon = meta.icon;
            return (
              <div key={`${turn.role}-${index}`} className="flex items-start gap-3 border-b border-moei-line/40 pb-3 last:border-0 last:pb-0">
                <span className={`mt-0.5 inline-flex h-6 items-center gap-1 rounded-sm border px-1.5 text-[10px] font-semibold uppercase ${meta.color}`}>
                  <Icon size={10} /> {meta.label}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-[10px] uppercase tracking-wider text-moei-muted">{turn.role}</div>
                  <div dir={/[\u0600-\u06FF]/.test(turn.text) ? "rtl" : "ltr"} className="whitespace-pre-wrap text-sm text-moei-ink">{turn.text}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function CasesTable({ cases, onAction }: { cases: Case[]; onAction: (caseNumber: string, action: "assign" | "resolve" | "escalate" | "reopen") => void }) {
  return (
    <div className="rounded-sm border border-moei-line bg-white">
      <div className="flex items-center justify-between border-b border-moei-line bg-moei-cream/50 px-5 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-moei-ink">
          <FileText size={14} /> Case history
        </h2>
        <span className="text-[11px] text-moei-muted">{cases.length} cases</span>
      </div>
      <div className="max-h-[330px] overflow-auto">
        {cases.length === 0 && <p className="p-5 text-sm text-moei-muted">No cases on file for this citizen.</p>}
        {cases.length > 0 && (
          <table className="w-full min-w-[860px] text-xs">
            <thead className="sticky top-0 bg-moei-cream/80 text-[10px] uppercase tracking-wider text-moei-muted backdrop-blur">
              <tr>
                <th className="px-4 py-2 text-left">Case</th>
                <th className="px-4 py-2 text-left">Service</th>
                <th className="px-4 py-2 text-left">Priority</th>
                <th className="px-4 py-2 text-left">Status</th>
                <th className="px-4 py-2 text-left">Sentiment</th>
                <th className="px-4 py-2 text-left">Updated</th>
                <th className="px-4 py-2 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((item) => (
                <tr key={item.case_number} className="border-t border-moei-line/40 align-top">
                  <td className="px-4 py-3">
                    <div className="font-mono text-[11px] text-moei-ink">{item.case_number}</div>
                    <div className="mt-1 max-w-[220px] truncate text-[11px] text-moei-muted">{item.title || item.intent}</div>
                    {item.correlation_id && (
                      <Link href={`/admin/audit?cid=${encodeURIComponent(item.case_number)}`} className="mt-1 inline-flex items-center gap-1 text-[10px] font-semibold text-moei-bronze hover:underline">
                        Audit <ExternalLink size={10} />
                      </Link>
                    )}
                  </td>
                  <td className="px-4 py-3 text-moei-body">{item.service}<div className="text-[10px] text-moei-muted">{item.channel}</div></td>
                  <td className="px-4 py-3"><span className={`rounded-full border px-2 py-0.5 text-[10px] ${PRIORITY_COLOR[item.priority] || PRIORITY_COLOR.medium}`}>{item.priority}</span></td>
                  <td className="px-4 py-3"><span className={`rounded-full px-2 py-0.5 text-[10px] ${STATUS_COLOR[item.status] || STATUS_COLOR.open}`}>{item.status}</span></td>
                  <td className="px-4 py-3 text-moei-body">{item.sentiment ?? "-"}</td>
                  <td className="px-4 py-3 text-moei-muted">{formatDate(item.updated_at || item.created_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1.5">
                      <button onClick={() => onAction(item.case_number, "assign")} className="rounded-sm border border-moei-line px-2 py-1 text-[10px] font-semibold text-moei-body hover:border-moei-bronze hover:text-moei-bronze">Assign</button>
                      {item.status !== "resolved" && item.status !== "closed" ? (
                        <button onClick={() => onAction(item.case_number, "resolve")} className="rounded-sm border border-emerald-200 bg-emerald-50 px-2 py-1 text-[10px] font-semibold text-emerald-800">Resolve</button>
                      ) : (
                        <button onClick={() => onAction(item.case_number, "reopen")} className="rounded-sm border border-blue-200 bg-blue-50 px-2 py-1 text-[10px] font-semibold text-blue-800">Reopen</button>
                      )}
                      {item.status !== "escalated" && (
                        <button onClick={() => onAction(item.case_number, "escalate")} className="rounded-sm border border-red-200 bg-red-50 px-2 py-1 text-[10px] font-semibold text-red-800">Escalate</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function ActivityTimeline({ activity }: { activity: Activity[] }) {
  return (
    <div className="rounded-sm border border-moei-line bg-white">
      <div className="flex items-center justify-between border-b border-moei-line bg-moei-cream/50 px-5 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-moei-ink">
          <Clock size={14} /> Recent activity
        </h2>
        <span className="text-[11px] text-moei-muted">{activity.length} events</span>
      </div>
      <div className="max-h-[260px] overflow-y-auto p-5">
        {activity.length === 0 && <p className="text-sm text-moei-muted">No activity events recorded yet.</p>}
        <div className="space-y-3">
          {activity.map((item) => (
            <div key={item.id} className="flex gap-3 border-b border-moei-line/40 pb-3 last:border-0 last:pb-0">
              <span className="mt-1 h-2 w-2 rounded-full bg-moei-bronze" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-moei-muted">{item.event_type}</span>
                  <span className="shrink-0 text-[10px] text-moei-muted">{formatDate(item.created_at)}</span>
                </div>
                <p className="mt-1 text-sm text-moei-ink">{item.summary}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CitizenCard({ context, selectedUser }: { context: CopilotContext | null; selectedUser: ActiveUser | null }) {
  const profile = context?.profile;
  const name = context?.name || selectedUser?.name || "-";
  const userId = context?.user_id || selectedUser?.user_id || "";
  return (
    <div className="rounded-sm border border-moei-line bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="moei-kicker flex items-center gap-1.5"><UserRound size={12} /> Citizen context</div>
          <h2 className="mt-2 text-lg font-semibold text-moei-ink">{name}</h2>
          <p className="font-mono text-[11px] text-moei-muted">{userId || "No citizen selected"}</p>
        </div>
        {userId && (
          <Link href={`/admin/citizens/${encodeURIComponent(userId)}`} className="rounded-sm border border-moei-line p-2 text-moei-body hover:border-moei-bronze hover:text-moei-bronze" title="Open full profile">
            <ExternalLink size={14} />
          </Link>
        )}
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <Field label="Mobile" value={profile?.mobile || selectedUser?.mobile || "-"} />
        <Field label="Language" value={profile?.preferred_language || selectedUser?.preferred_language || "-"} />
        <Field label="Verified" value={profile?.verified || selectedUser?.verified ? "UAE PASS" : "Unverified"} />
        <Field label="Channels" value={(context?.summary.channels || selectedUser?.channels || []).join(", ") || "-"} />
        <Field label="Sentiment" value={context?.summary.sentiment_label || "unknown"} />
        <Field label="Last case" value={formatDate(context?.summary.last_case_at || selectedUser?.last_seen)} />
      </dl>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-moei-muted">{label}</dt>
      <dd className="mt-1 truncate font-medium text-moei-ink">{value}</dd>
    </div>
  );
}

function DocumentsCard({ documents }: { documents: CustomerDocument[] }) {
  return (
    <div className="rounded-sm border border-moei-line bg-white p-5">
      <div className="moei-kicker flex items-center gap-1.5"><FileText size={12} /> Documents</div>
      <div className="mt-3 space-y-2">
        {documents.length === 0 && <p className="text-xs text-moei-muted">No uploaded documents for this citizen.</p>}
        {documents.slice(0, 5).map((doc) => (
          <div key={doc.id} className="rounded-sm border border-moei-line px-3 py-2 text-xs">
            <div className="flex items-center justify-between gap-3">
              <span className="font-semibold text-moei-ink">{doc.document_type.replace("_", " ")}</span>
              <span className="text-[10px] text-moei-muted">{doc.confidence != null ? `${Math.round(doc.confidence * 100)}%` : "-"}</span>
            </div>
            <div className="mt-1 truncate text-[11px] text-moei-muted">{doc.original_name || doc.status} · {formatDate(doc.created_at)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CallsCard({ recordings }: { recordings: Recording[] }) {
  return (
    <div className="rounded-sm border border-moei-line bg-white p-5">
      <div className="moei-kicker flex items-center gap-1.5"><Headphones size={12} /> Voice calls</div>
      <div className="mt-3 space-y-2">
        {recordings.length === 0 && <p className="text-xs text-moei-muted">No recorded calls for this citizen.</p>}
        {recordings.slice(0, 4).map((recording) => (
          <Link key={recording.id} href={`/admin/calls/${recording.id}`} className="block rounded-sm border border-moei-line px-3 py-2 text-xs hover:border-moei-bronze">
            <div className="flex items-center justify-between gap-3">
              <span className="font-semibold text-moei-ink">{recording.service || "Voice session"}</span>
              <span className="text-[10px] text-moei-muted">{secondsToText(recording.duration_seconds)}</span>
            </div>
            <p className="mt-1 line-clamp-2 text-[11px] text-moei-muted">{recording.summary || `QA ${recording.qa_score ?? "-"} · sentiment ${recording.sentiment_avg ?? "-"}`}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}

function FollowUps({ followUps }: { followUps: FollowUp[] }) {
  return (
    <div className="rounded-sm border border-moei-line bg-white p-5">
      <div className="moei-kicker flex items-center gap-1.5"><Bell size={12} /> Follow-up queue</div>
      <div className="mt-3 space-y-2">
        {followUps.length === 0 && <p className="text-xs text-moei-muted">No follow-ups scheduled or sent for this citizen.</p>}
        {followUps.slice(0, 6).map((item) => {
          const sent = item.status === "sent";
          const failed = item.status === "failed";
          return (
            <div key={item.id} className="rounded-sm border border-moei-line px-3 py-2 text-xs">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate font-semibold text-moei-ink">{item.template.replace("_", " ")}</div>
                  <div className="mt-0.5 text-[10px] text-moei-muted">
                    {item.channel} · {item.case_number || "general"} · {sent ? formatDate(item.sent_at) : formatDate(item.scheduled_at)}
                  </div>
                </div>
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                  failed ? "bg-red-100 text-red-800" : sent ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800"
                }`}>
                  {item.status}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function EscalationRisk({ risks, currentUserId, onSelect }: { risks: RiskUser[]; currentUserId: string; onSelect: (userId: string) => void }) {
  return (
    <div className="rounded-sm border border-moei-line bg-white p-5">
      <div className="moei-kicker flex items-center gap-1.5"><AlertTriangle size={12} /> Escalation watchlist</div>
      <ul className="mt-3 space-y-2">
        {risks.slice(0, 5).map((risk) => (
          <li key={risk.user_id} className="border-b border-moei-line/40 pb-2 last:border-0 last:pb-0">
            <button
              onClick={() => onSelect(risk.user_id)}
              className={`flex w-full items-center justify-between text-left transition hover:text-moei-bronze ${risk.user_id === currentUserId ? "text-moei-bronze" : ""}`}
            >
            <div className="min-w-0">
              <div className="truncate text-xs font-semibold">{risk.user_name || risk.user_id}</div>
              <div className="text-[10px] text-moei-muted">{risk.open_cases} open · {risk.high_priority} high · sentiment {risk.avg_sentiment ?? "-"}</div>
            </div>
            <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-800">{risk.risk_score}</span>
            </button>
          </li>
        ))}
        {risks.length === 0 && <li className="text-xs text-moei-muted">No users currently at risk.</li>}
      </ul>
    </div>
  );
}

function QuickActions({ userId, latestCase, onDone }: { userId: string; latestCase: string | null; onDone: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const actions: { label: string; template: string; channel: string; hours: number }[] = [
    { label: "Send document reminder", template: "doc_reminder", channel: "whatsapp", hours: 0 },
    { label: "Schedule CSAT survey", template: "csat_survey", channel: "whatsapp", hours: 24 },
    { label: "Push status update", template: "status_update", channel: "whatsapp", hours: 0 },
    { label: "Send proactive tip", template: "proactive_tip", channel: "sms", hours: 1 },
  ];

  async function fire(label: string, template: string, channel: string, hours: number) {
    if (!userId) return;
    setBusy(label);
    setToast(null);
    try {
      const body: Record<string, string | number> = {
        user_id: userId,
        channel,
        template,
        scheduled_in_hours: hours,
      };
      if (latestCase) body.case_number = latestCase;
      const response = await fetch(`${API_URL}/notifications`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const when = hours === 0 ? "queued now" : `scheduled in ${hours}h`;
      setToast(`${label} ${when} (${String(data.id).slice(0, 8)})`);
      onDone();
    } catch (err: any) {
      setToast(`Failed: ${err.message || err}`);
    } finally {
      setBusy(null);
      window.setTimeout(() => setToast(null), 5000);
    }
  }

  return (
    <div className="rounded-sm border border-moei-line bg-white p-5">
      <div className="moei-kicker flex items-center gap-1.5"><Bell size={12} /> Proactive engagement</div>
      <div className="mt-3 space-y-2">
        {actions.map((action) => (
          <button
            key={action.label}
            onClick={() => fire(action.label, action.template, action.channel, action.hours)}
            disabled={busy !== null || !userId}
            className="flex w-full items-center justify-between rounded-sm border border-moei-line bg-white px-3 py-2 text-left text-xs text-moei-body transition hover:border-moei-bronze hover:text-moei-bronze disabled:opacity-60"
          >
            <span>{busy === action.label ? "Scheduling..." : action.label}</span>
            <ChevronRight size={12} />
          </button>
        ))}
      </div>
      {toast && (
        <div className={`mt-3 rounded-sm border px-3 py-2 text-[11px] ${toast.startsWith("Failed") ? "border-red-200 bg-red-50 text-red-800" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`}>
          {toast}
        </div>
      )}
      <p className="mt-3 text-[10px] text-moei-muted">Writes to the notifications table and attaches the latest case when available.</p>
    </div>
  );
}

function SourceStatus({ sources }: { sources?: Record<string, boolean | number> }) {
  const rows = [
    ["Profile", sources?.citizen_profile],
    ["Memory turns", sources?.short_term_memory_turns],
    ["CRM cases", sources?.crm_cases],
    ["Activity events", sources?.activity_events],
    ["Documents", sources?.customer_documents],
    ["Call recordings", sources?.call_recordings],
    ["Follow-ups", sources?.notifications],
  ];
  return (
    <div className="rounded-sm border border-moei-line bg-white p-5">
      <div className="moei-kicker flex items-center gap-1.5"><ShieldAlert size={12} /> Data source status</div>
      <div className="mt-3 space-y-2">
        {rows.map(([label, value]) => {
          const active = typeof value === "boolean" ? value : Number(value || 0) > 0;
          return (
            <div key={String(label)} className="flex items-center justify-between text-xs">
              <span className="text-moei-body">{label}</span>
              <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${active ? "bg-emerald-50 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>
                <CheckCircle2 size={10} /> {typeof value === "boolean" ? (value ? "linked" : "empty") : value ?? 0}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
