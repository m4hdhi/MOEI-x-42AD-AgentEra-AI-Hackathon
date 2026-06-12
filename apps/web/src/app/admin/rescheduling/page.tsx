"use client";

/**
 * Officer review console — Housing Loan Arrears Rescheduling.
 *
 * The AI agent has already done the officer's work for every request: retrieved the loan,
 * analysed income/family/capacity, applied the policy rules, and produced an explainable
 * recommendation with a confidence score. The human officer reviews, and approves, overrides,
 * or takes ownership of the exceptional cases. Every step is audited.
 */

import { useCallback, useEffect, useState } from "react";
import {
  Home, CheckCircle2, AlertTriangle, Clock, FileText, ShieldCheck, Gauge, Scale,
  ListChecks, User, ArrowRight,
} from "lucide-react";
import { API_URL } from "@/lib/utils";

type Item = {
  reference: string; applicant: string; recommendation: string; approved_request_type: string | null;
  confidence: number; status: string; current_salary: number; arrears: number;
  proposed_emi: number | null; deduction_ratio: number | null; rule_20_pass: boolean;
  rule_period_pass: boolean; created_at: string; officer_action?: string | null;
};
type Stats = { total: number; approved: number; review: number; rejected: number; avg_confidence: number; auto_rate: number };

const STATUS: Record<string, { cls: string; Icon: typeof CheckCircle2 }> = {
  approved: { cls: "text-emerald-700 bg-emerald-50", Icon: CheckCircle2 },
  rejected: { cls: "text-red-700 bg-red-50", Icon: AlertTriangle },
  request_documents: { cls: "text-amber-700 bg-amber-50", Icon: FileText },
  human_review: { cls: "text-violet-700 bg-violet-50", Icon: Clock },
};
const AED = (n?: number | null) => (n == null ? "—" : `AED ${Math.round(n).toLocaleString()}`);

export default function OfficerConsole() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [sel, setSel] = useState<string | null>(null);
  const [detail, setDetail] = useState<any>(null);
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    const d = await fetch(`${API_URL}/szhp/queue`, { credentials: "include" }).then((r) => r.json());
    setStats(d.stats); setItems(d.items || []);
    if (!sel && d.items?.length) setSel(d.items[0].reference);
  }, [sel]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!sel) return;
    fetch(`${API_URL}/szhp/assessment/${sel}`, { credentials: "include" }).then((r) => r.json()).then(setDetail);
  }, [sel]);

  async function act(action: string) {
    if (!sel) return;
    await fetch(`${API_URL}/szhp/assessment/${sel}/action`, {
      method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
      body: JSON.stringify({ action }),
    });
    setToast(`${sel} · ${action}`); setTimeout(() => setToast(""), 2500);
    await load();
    fetch(`${API_URL}/szhp/assessment/${sel}`, { credentials: "include" }).then((r) => r.json()).then(setDetail);
  }

  const a = detail?.assessment;
  const payload = a?.payload || {};

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      {toast && <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-full bg-slate-800 px-4 py-2 text-xs font-semibold text-white">{toast}</div>}

      <div className="mx-auto max-w-7xl">
        <div className="flex items-center gap-2">
          <Home className="text-moei-bronze" size={20} />
          <h1 className="text-xl font-bold text-slate-800">Loan Rescheduling — Officer Console</h1>
        </div>
        <p className="mt-1 text-sm text-slate-500">Sheikh Zayed Housing Programme · the agent decides, you review the exceptions.</p>

        {/* Stats */}
        {stats && (
          <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-5">
            <Stat label="Requests" value={String(stats.total)} />
            <Stat label="Auto-decided" value={`${stats.auto_rate ?? 0}%`} tone="good" />
            <Stat label="Avg confidence" value={`${Math.round((stats.avg_confidence || 0) * 100)}%`} />
            <Stat label="Needs officer" value={String(stats.review)} tone={stats.review ? "warn" : undefined} />
            <Stat label="Rejected" value={String(stats.rejected)} />
          </div>
        )}

        <div className="mt-6 grid gap-5 lg:grid-cols-3">
          {/* Queue */}
          <div className="rounded-xl border border-slate-200 bg-white p-3">
            <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-slate-400">Queue</div>
            <div className="space-y-1.5 max-h-[640px] overflow-y-auto">
              {items.map((it) => {
                const st = STATUS[it.status] || STATUS.human_review;
                return (
                  <button key={it.reference} onClick={() => setSel(it.reference)}
                    className={`w-full rounded-lg border p-2.5 text-left transition ${sel === it.reference ? "border-moei-bronze bg-moei-cream/30" : "border-slate-200 hover:border-slate-300"}`}>
                    <div className="flex items-center justify-between">
                      <span className="text-[13px] font-semibold text-slate-800">{it.applicant}</span>
                      <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-semibold ${st.cls}`}><st.Icon size={9} /> {it.status.replace("_", " ")}</span>
                    </div>
                    <div className="mt-1 flex items-center justify-between text-[10px] text-slate-500">
                      <span className="font-mono">{it.reference}</span>
                      <span>{it.approved_request_type || "—"} · {Math.round(it.confidence * 100)}%</span>
                    </div>
                  </button>
                );
              })}
              {items.length === 0 && <p className="py-8 text-center text-xs text-slate-400">No requests yet.</p>}
            </div>
          </div>

          {/* Detail — the officer-grade assessment */}
          <div className="lg:col-span-2 space-y-4">
            {!a ? (
              <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-400">Select a request to review the assessment.</div>
            ) : (
              <>
                <div className="rounded-xl border border-slate-200 bg-white p-5">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-moei-cream text-moei-bronze"><User size={18} /></span>
                      <div>
                        <div className="text-base font-bold text-slate-800">{a.applicant}</div>
                        <div className="font-mono text-[11px] text-slate-400">{a.reference} · {a.application_id}</div>
                      </div>
                    </div>
                    <Confidence value={a.confidence} />
                  </div>
                  <p className="mt-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">{payload.case_summary}</p>
                </div>

                {/* Recommendation + compliance */}
                <div className="grid gap-3 sm:grid-cols-2">
                  <Card title="Recommendation" Icon={ListChecks}>
                    <div className="text-lg font-bold capitalize text-slate-800">{(a.recommendation || "").replace(/_/g, " ")}</div>
                    <div className="text-xs text-slate-500">{a.approved_request_type ? a.approved_request_type.replace("_", " ") : ""}</div>
                    {payload.proposed_repayment_plan && <p className="mt-2 text-sm text-moei-bronze">{payload.proposed_repayment_plan}</p>}
                  </Card>
                  <Card title="Policy compliance" Icon={Scale}>
                    <Rule label="Deduction ≤ 20% of income" pass={payload.rule_20_compliance === "Pass"} detail={payload.proposed_deduction_rate != null ? `${payload.proposed_deduction_rate}%` : ""} />
                    <Rule label="Term ≤ original period" pass={payload.rule_period_compliance === "Pass"} />
                    <Rule label="No active duplicate request" pass={payload.rule_active_request === "Pass"} />
                  </Card>
                </div>

                {/* Analysis grid */}
                <Card title="Income & case analysis" Icon={Gauge}>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Mini label="Salary" value={AED(payload.income_analysis?.monthly_salary)} />
                    <Mini label="Per family member" value={AED(payload.income_analysis?.avg_income_per_member)} tone={payload.income_analysis?.per_member_below_floor ? "warn" : undefined} />
                    <Mini label="Arrears" value={AED(payload.arrears_amount)} tone="warn" />
                    <Mini label="Overdue" value={`${payload.overdue_installments} mo`} />
                    <Mini label="Current instalment" value={AED(a.current_emi)} />
                    <Mini label="Proposed instalment" value={AED(a.proposed_emi)} />
                    <Mini label="Remaining term" value={`${payload.remaining_repayment_period_months} mo`} />
                    <Mini label="Income stable" value={payload.income_analysis?.income_stable ? "Yes" : "No"} />
                  </div>
                  {payload.flags?.length > 0 && (
                    <div className="mt-3 rounded-lg bg-amber-50 p-2.5 text-[12px] text-amber-800">
                      <AlertTriangle size={12} className="mr-1 inline" /> {payload.flags.join(" ")}
                    </div>
                  )}
                </Card>

                {/* Reasoning */}
                <Card title="Reasoning (explainable decision)" Icon={FileText}>
                  <p className="text-sm leading-relaxed text-slate-700">{payload.reasoning}</p>
                </Card>

                {/* Audit trail */}
                {detail?.audit?.length > 0 && (
                  <Card title="Decision audit trail" Icon={ShieldCheck}>
                    <ol className="space-y-1.5">
                      {detail.audit.map((e: any, i: number) => (
                        <li key={i} className="flex items-start gap-2 text-[11px]">
                          <span className="mt-0.5 rounded bg-slate-100 px-1.5 py-0.5 font-mono font-semibold text-slate-600">{e.node}</span>
                          <span className="text-slate-500">{typeof e.payload === "string" ? e.payload : JSON.stringify(e.payload)}</span>
                        </li>
                      ))}
                    </ol>
                  </Card>
                )}

                {/* Officer actions */}
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => act("approve")} className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700"><CheckCircle2 size={15} /> Confirm decision</button>
                  <button onClick={() => act("override")} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"><ArrowRight size={15} /> Override & approve</button>
                  <button onClick={() => act("refer")} className="inline-flex items-center gap-1.5 rounded-lg border border-violet-300 px-4 py-2 text-sm font-semibold text-violet-700 hover:bg-violet-50"><Clock size={15} /> Take for manual review</button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "good" | "warn" }) {
  const c = tone === "good" ? "text-emerald-600" : tone === "warn" ? "text-amber-600" : "text-slate-800";
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${c}`}>{value}</div>
    </div>
  );
}
function Card({ title, Icon, children }: { title: string; Icon: typeof Home; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400"><Icon size={13} /> {title}</div>
      {children}
    </div>
  );
}
function Mini({ label, value, tone }: { label: string; value: string; tone?: "warn" }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 p-2.5">
      <div className="text-[9px] font-semibold uppercase tracking-wider text-slate-400">{label}</div>
      <div className={`mt-0.5 text-sm font-bold ${tone === "warn" ? "text-red-600" : "text-slate-800"}`}>{value}</div>
    </div>
  );
}
function Rule({ label, pass, detail }: { label: string; pass: boolean; detail?: string }) {
  return (
    <div className="flex items-center justify-between py-1 text-sm">
      <span className="text-slate-600">{label}</span>
      <span className={`inline-flex items-center gap-1 font-semibold ${pass ? "text-emerald-600" : "text-red-600"}`}>
        {detail && <span className="text-xs text-slate-400">{detail}</span>}
        {pass ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />} {pass ? "Pass" : "Fail"}
      </span>
    </div>
  );
}
function Confidence({ value }: { value: number }) {
  const pct = Math.round((value || 0) * 100);
  const tone = pct >= 80 ? "text-emerald-600" : pct >= 60 ? "text-amber-600" : "text-red-600";
  return (
    <div className="text-right">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Confidence</div>
      <div className={`text-2xl font-bold ${tone}`}>{pct}%</div>
    </div>
  );
}
