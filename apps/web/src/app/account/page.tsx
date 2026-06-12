"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileText,
  FolderOpen,
  History,
  MessageCircle,
  Phone,
  ShieldCheck,
  User,
} from "lucide-react";
import { API_URL } from "@/lib/utils";
import { LoginGate } from "@/components/LoginGate";
import type { UaePassSession } from "@/lib/auth";

type CaseItem = {
  case_number: string;
  service?: string;
  intent?: string;
  status?: string;
  priority?: string;
  summary?: string;
  description?: string;
  created_at?: string;
  updated_at?: string;
};
type ActivityItem = { id: string; event_type?: string; summary?: string; channel?: string; created_at?: string };
type ChatTurn = { role: "user" | "assistant"; text: string; channel?: string };
type DocumentItem = {
  id: string;
  document_type?: string;
  original_name?: string;
  status?: string;
  confidence?: number;
  created_at?: string;
};

export default function AccountPage() {
  return (
    <LoginGate
      title="Sign in to view your account"
      subtitle="Your profile, service requests, complaints, documents, and conversation history are linked to UAE PASS."
    >
      {(session) => <AccountExperience session={session} />}
    </LoginGate>
  );
}

function AccountExperience({ session }: { session: UaePassSession }) {
  const userId = session.emirates_id || "";
  const [profile, setProfile] = useState<any>(null);
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      const [profileRes, historyRes, docsRes] = await Promise.allSettled([
        fetch(`${API_URL}/crm/citizens/${encodeURIComponent(userId)}`, { credentials: "include" }).then((r) => r.ok ? r.json() : null),
        fetch(`${API_URL}/chat/history?n=30`, { credentials: "include" }).then((r) => r.ok ? r.json() : { turns: [] }),
        fetch(`${API_URL}/documents?limit=20`, { credentials: "include" }).then((r) => r.ok ? r.json() : { documents: [] }),
      ]);
      if (cancelled) return;
      setProfile(profileRes.status === "fulfilled" ? profileRes.value : null);
      setHistory(historyRes.status === "fulfilled" ? historyRes.value?.turns || [] : []);
      setDocuments(docsRes.status === "fulfilled" ? docsRes.value?.documents || [] : []);
      setLoading(false);
    }
    if (userId) load();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const cases: CaseItem[] = profile?.cases || [];
  const activity: ActivityItem[] = profile?.activity || [];
  const summary = profile?.summary || {};
  const complaints = useMemo(
    () => cases.filter((c) => c.intent === "complaint" || /complaint|شكوى/i.test(`${c.summary || ""} ${c.description || ""}`)),
    [cases],
  );
  const pending = cases.filter((c) => !["resolved", "closed", "approved", "rejected"].includes(String(c.status || "").toLowerCase()));
  const completed = cases.filter((c) => ["resolved", "closed", "approved"].includes(String(c.status || "").toLowerCase()));

  return (
    <div className="min-h-screen bg-moei-cream/30">
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-8">
          <span className="moei-kicker">Citizen Account</span>
          <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="moei-h-section">{session.full_name_en || "Your account"}</h1>
              <p className="mt-2 text-sm text-moei-body">
                Track your requests, complaints, uploaded documents, and cross-channel history.
              </p>
            </div>
            <div className="flex gap-2">
              <Link href="/chat" className="moei-btn-secondary">
                <MessageCircle size={14} /> Ask MOEI
              </Link>
              <Link href="/call" className="moei-btn-primary">
                <Phone size={14} /> Call 800 6634
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-6 py-8 lg:grid-cols-12">
        <aside className="space-y-4 lg:col-span-4">
          <Panel title="Your Details" icon={<User size={15} />}>
            <div className="space-y-2 text-sm">
              <Info label="Emirates ID" value={session.emirates_id || "—"} />
              <Info label="Mobile" value={session.mobile || "—"} />
              <Info label="Email" value={session.email || "—"} />
              <Info label="Nationality" value={session.nationality_en || "—"} />
              <Info label="UAE PASS" value={session.user_type || "Verified"} />
            </div>
            <div className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
              <ShieldCheck size={13} /> Verified with UAE PASS
            </div>
          </Panel>

          <Panel title="Saved Documents" icon={<FolderOpen size={15} />} count={documents.length}>
            {documents.length === 0 ? (
              <Empty text="No saved documents yet." />
            ) : (
              <div className="space-y-2">
                {documents.map((doc) => (
                  <div key={doc.id} className="rounded-lg border border-moei-line bg-white px-3 py-2 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-moei-ink">{clean(doc.document_type || "document")}</span>
                      <span className="text-moei-muted">{fmtDate(doc.created_at)}</span>
                    </div>
                    <div className="mt-0.5 truncate text-moei-muted">{doc.original_name || doc.id}</div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </aside>

        <main className="space-y-4 lg:col-span-8">
          <div className="grid gap-3 sm:grid-cols-4">
            <Kpi icon={<FileText size={15} />} label="Total requests" value={summary.total_cases ?? cases.length} />
            <Kpi icon={<Clock size={15} />} label="Pending" value={pending.length || summary.open_cases || 0} tone="warn" />
            <Kpi icon={<CheckCircle2 size={15} />} label="Completed" value={completed.length || summary.resolved_cases || 0} tone="good" />
            <Kpi icon={<AlertTriangle size={15} />} label="Complaints" value={complaints.length} tone={complaints.length ? "warn" : "good"} />
          </div>

          <Panel title="Requests & Complaints" icon={<FileText size={15} />} count={cases.length}>
            {loading ? (
              <Empty text="Loading your requests..." />
            ) : cases.length === 0 ? (
              <Empty text="No service requests or complaints yet." />
            ) : (
              <div className="space-y-2">
                {cases.slice(0, 12).map((c) => (
                  <div key={c.case_number} className="rounded-lg border border-moei-line bg-white p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <div className="font-mono text-[11px] text-moei-bronze">{c.case_number}</div>
                        <div className="text-sm font-semibold text-moei-ink">{clean(c.service || c.intent || "Service request")}</div>
                      </div>
                      <Status status={c.status || "open"} />
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-moei-body">
                      {c.summary || c.description || "Request created from your conversation."}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-moei-muted">
                      <span>{fmtDate(c.created_at)}</span>
                      {c.priority && <span>Priority: {c.priority}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Conversation History" icon={<History size={15} />} count={history.length}>
              {history.length === 0 ? (
                <Empty text="No recent conversation history." />
              ) : (
                <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
                  {history.slice(-12).map((turn, i) => (
                    <div key={i} className="rounded-lg border border-moei-line bg-white px-3 py-2 text-xs">
                      <div className="mb-1 flex justify-between gap-2">
                        <span className="font-semibold text-moei-ink">{turn.role === "user" ? "You" : "Assistant"}</span>
                        <span className="uppercase text-moei-muted">{turn.channel || "web"}</span>
                      </div>
                      <p className="line-clamp-3 text-moei-body">{turn.text}</p>
                    </div>
                  ))}
                </div>
              )}
            </Panel>

            <Panel title="Recent Activity" icon={<Activity size={15} />} count={activity.length}>
              {activity.length === 0 ? (
                <Empty text="No recent activity yet." />
              ) : (
                <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
                  {activity.slice(0, 12).map((item) => (
                    <div key={item.id} className="rounded-lg border border-moei-line bg-white px-3 py-2 text-xs">
                      <div className="flex justify-between gap-2">
                        <span className="font-semibold text-moei-ink">{clean(item.event_type || "activity")}</span>
                        <span className="text-moei-muted">{fmtDate(item.created_at)}</span>
                      </div>
                      <p className="mt-1 text-moei-body">{item.summary || "Activity recorded."}</p>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          </div>
        </main>
      </section>
    </div>
  );
}

function Panel({ title, icon, count, children }: { title: string; icon: React.ReactNode; count?: number; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-moei-line bg-white p-5">
      <div className="mb-4 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-semibold text-moei-ink">
          <span className="text-moei-bronze">{icon}</span>
          {title}
        </div>
        {count !== undefined && <span className="rounded-full bg-moei-cream px-2 py-0.5 text-xs text-moei-bronze">{count}</span>}
      </div>
      {children}
    </section>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-moei-line/60 pb-1.5">
      <span className="text-moei-muted">{label}</span>
      <span className="text-right font-medium text-moei-ink">{value}</span>
    </div>
  );
}

function Kpi({ icon, label, value, tone }: { icon: React.ReactNode; label: string; value: number | string; tone?: "good" | "warn" }) {
  const cls = tone === "good" ? "text-emerald-700 bg-emerald-50" : tone === "warn" ? "text-amber-700 bg-amber-50" : "text-moei-bronze bg-moei-cream";
  return (
    <div className="rounded-2xl border border-moei-line bg-white p-4">
      <div className={`inline-flex rounded-lg p-2 ${cls}`}>{icon}</div>
      <div className="mt-3 text-2xl font-bold text-moei-ink">{value}</div>
      <div className="text-xs text-moei-muted">{label}</div>
    </div>
  );
}

function Status({ status }: { status: string }) {
  const s = status.toLowerCase();
  const cls = ["resolved", "closed", "approved"].includes(s)
    ? "bg-emerald-50 text-emerald-700"
    : ["rejected", "escalated"].includes(s)
    ? "bg-red-50 text-red-700"
    : "bg-amber-50 text-amber-700";
  return <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${cls}`}>{clean(status)}</span>;
}

function Empty({ text }: { text: string }) {
  return <p className="rounded-lg border border-dashed border-moei-line bg-moei-cream/20 px-3 py-6 text-center text-sm text-moei-muted">{text}</p>;
}

function clean(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function fmtDate(value?: string) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString();
  } catch {
    return value;
  }
}
