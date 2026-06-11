"use client";

/**
 * Sheikh Zayed Housing Programme — Loan Arrears Rescheduling (citizen journey).
 *
 * Sign in with UAE PASS → the Programme retrieves your loan & arrears automatically → upload a
 * salary certificate and confirm authenticity → the assistant assesses your case against the
 * Programme's rules and returns a decision in seconds (instead of ~5 working days). The
 * beneficiary sees a clear status and the reason — not the internal calculations.
 */

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Home, Upload, ShieldCheck, CheckCircle2, AlertTriangle, Clock, FileText, Loader2,
  Banknote, CalendarClock, Users, ArrowRight,
} from "lucide-react";
import { API_URL } from "@/lib/utils";
import { LoginGate } from "@/components/LoginGate";
import type { UaePassSession } from "@/lib/auth";

type Loan = {
  found: boolean; applicant?: string; application_id?: string; current_salary?: number;
  arrears?: number; overdue_months?: number; current_emi?: number;
  remaining_term_months?: number; family_size?: number; has_active_request?: boolean;
};
type Result = {
  reference: string;
  citizen: { status: string; status_label: string; headline: string; reason: string; recommendation: string };
  assessment: any;
};
type CertResult = {
  document_id?: string;
  document_type?: string;
  confidence?: number;
  fields?: Record<string, any>;
  signals?: string[];
  original_name?: string;
  note?: string;
};

const AED = (n?: number) => (n == null ? "—" : `AED ${Math.round(n).toLocaleString()}`);
const STATUS_STYLE: Record<string, { bg: string; text: string; Icon: typeof CheckCircle2 }> = {
  approved: { bg: "bg-emerald-50 border-emerald-200", text: "text-emerald-700", Icon: CheckCircle2 },
  rejected: { bg: "bg-red-50 border-red-200", text: "text-red-700", Icon: AlertTriangle },
  request_documents: { bg: "bg-amber-50 border-amber-200", text: "text-amber-700", Icon: FileText },
  human_review: { bg: "bg-violet-50 border-violet-200", text: "text-violet-700", Icon: Clock },
  in_progress: { bg: "bg-blue-50 border-blue-200", text: "text-blue-700", Icon: Loader2 },
};

export default function ReschedulingPage() {
  return (
    <LoginGate
      title="Sheikh Zayed Housing — Loan Rescheduling"
      subtitle="Sign in with UAE PASS to review your housing loan arrears and request a rescheduling plan."
    >
      {(session) => <Experience session={session} />}
    </LoginGate>
  );
}

function Experience({ session }: { session: UaePassSession }) {
  const searchParams = useSearchParams();
  const handoffSource = searchParams.get("from");
  const fromAutomation = handoffSource === "automation" || handoffSource === "voice";
  const handoffUtterance = searchParams.get("utterance") || "";
  const userId = session.emirates_id || "anonymous";
  const certInputRef = useRef<HTMLInputElement | null>(null);
  const [loan, setLoan] = useState<Loan | null>(null);
  const [cert, setCert] = useState<CertResult | null>(null);
  const [certBusy, setCertBusy] = useState(false);
  const [certErr, setCertErr] = useState("");
  const [declaredSalary, setDeclaredSalary] = useState("");
  const [incomeStable, setIncomeStable] = useState(true);
  const [hardship, setHardship] = useState(false);
  const [declared, setDeclared] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/szhp/loan?user_id=${encodeURIComponent(userId)}`, { credentials: "include" })
      .then((r) => r.json()).then(setLoan).catch(() => setLoan({ found: false }));
  }, [userId]);

  async function uploadSalaryCertificate(file: File | undefined) {
    if (!file || certBusy) return;
    setCertBusy(true);
    setCertErr("");
    setCert(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("doc_hint", "salary_certificate");
      const r = await fetch(`${API_URL}/documents/extract`, {
        method: "POST",
        body: fd,
        credentials: "include",
      });
      const data = await r.json();
      if (!r.ok || !data.ok) {
        setCertErr(data.reason || data.detail || "Could not read the salary certificate.");
        return;
      }
      const next: CertResult = {
        document_id: data.document_id,
        document_type: data.document_type,
        confidence: data.confidence,
        fields: data.fields || {},
        signals: data.signals || [],
        original_name: file.name,
        note: data.note,
      };
      setCert(next);
      const extractedSalary = data.fields?.monthly_salary_aed;
      if (extractedSalary) {
        setDeclaredSalary(String(extractedSalary).replace(/,/g, ""));
      }
      if (data.document_type !== "salary_certificate") {
        setCertErr("This file was not recognized as a salary certificate. Please upload a valid salary certificate.");
      }
    } catch (e: any) {
      setCertErr(e?.message || "Upload failed.");
    } finally {
      setCertBusy(false);
      if (certInputRef.current) certInputRef.current.value = "";
    }
  }

  async function submit() {
    if (!declared || busy) return;
    setBusy(true); setErr(""); setResult(null);
    try {
      const salaryCertOk = cert?.document_type === "salary_certificate" && !!cert.document_id;
      if (!salaryCertOk) {
        setErr("Please upload a valid salary certificate before submitting.");
        return;
      }
      const r = await fetch(`${API_URL}/szhp/assess`, {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
        body: JSON.stringify({
          user_id: userId, declaration_accepted: declared, salary_cert_provided: !!cert,
          salary_document_id: cert.document_id,
          declared_salary: declaredSalary ? Number(declaredSalary) : null,
          income_stable: incomeStable, temporary_hardship: hardship,
        }),
      });
      if (!r.ok) { const e = await r.json().catch(() => ({})); setErr(e.detail || "Could not assess your request."); return; }
      setResult(await r.json());
    } catch { setErr("Connection error. Please try again."); }
    finally { setBusy(false); }
  }

  return (
    <div className="bg-moei-cream/30 min-h-screen pb-16">
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-4xl px-6 py-8">
          <span className="moei-kicker">Sheikh Zayed Housing Programme</span>
          <h1 className="mt-2 moei-h-section flex items-center gap-2"><Home size={22} className="text-moei-bronze" /> Loan Arrears Rescheduling</h1>
          <p className="mt-2 max-w-2xl text-sm text-moei-body">
            We review your loan against the Programme rules and give you a decision in seconds — fairly,
            transparently, and consistently. A specialist reviews only the exceptional cases.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-6 py-8 space-y-6">
        {fromAutomation && (
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-4">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white">
                <ShieldCheck size={16} />
              </div>
              <div>
                <div className="text-sm font-bold text-emerald-800">
                  {handoffSource === "voice" ? "Voice assistant opened this request" : "Task automation opened this request"}
                </div>
                <p className="mt-1 text-sm leading-relaxed text-emerald-900/80">
                  I understood your request for loan rescheduling and brought you to the correct service.
                  Your UAE PASS identity and loan details are loaded automatically. To finish, upload your
                  salary certificate, confirm the declaration, and submit.
                </p>
                {handoffUtterance && (
                  <p className="mt-2 rounded-lg bg-white/70 px-3 py-2 text-xs text-emerald-800">
                    Request: “{handoffUtterance}”
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Loan retrieved automatically */}
        <div className="rounded-2xl border border-moei-line bg-white p-5">
          <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-moei-muted">
            <ShieldCheck size={14} className="text-emerald-600" /> Your loan — retrieved automatically
          </div>
          {!loan ? (
            <p className="text-sm text-moei-muted">Loading your loan…</p>
          ) : !loan.found ? (
            <p className="text-sm text-moei-muted">No housing loan with arrears was found on your account.</p>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Fact icon={Banknote} label="Monthly salary" value={AED(loan.current_salary)} />
              <Fact icon={AlertTriangle} label="Arrears" value={AED(loan.arrears)} tone="warn" />
              <Fact icon={Banknote} label="Current instalment" value={AED(loan.current_emi)} />
              <Fact icon={CalendarClock} label="Overdue months" value={String(loan.overdue_months ?? "—")} />
              <Fact icon={CalendarClock} label="Remaining term" value={`${loan.remaining_term_months ?? "—"} mo`} />
              <Fact icon={Users} label="Family size" value={String(loan.family_size ?? "—")} />
              <Fact icon={FileText} label="Application" value={loan.application_id || "—"} />
              <Fact icon={ShieldCheck} label="Active request" value={loan.has_active_request ? "Yes" : "No"} />
            </div>
          )}
        </div>

        {/* Submit form */}
        {loan?.found && !result && (
          <div className="rounded-2xl border border-moei-line bg-white p-5 space-y-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-moei-muted">Submit your rescheduling request</div>

            <label className="block">
              <span className="text-sm font-medium text-moei-ink">Salary certificate</span>
              <div className="mt-1 flex flex-wrap items-center gap-3">
                <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-moei-bronze/50 bg-moei-cream/30 px-4 py-2.5 text-sm text-moei-bronze hover:bg-moei-cream/60">
                  {certBusy ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />}
                  {cert ? "Replace certificate" : "Upload certificate"}
                  <input
                    ref={certInputRef}
                    type="file"
                    className="hidden"
                    accept=".png,.jpg,.jpeg,.webp,image/*"
                    onChange={(e) => uploadSalaryCertificate(e.target.files?.[0])}
                  />
                </label>
                {cert && (
                  <span className="inline-flex items-center gap-1 text-xs text-emerald-700">
                    <CheckCircle2 size={13} /> {cert.original_name}
                  </span>
                )}
              </div>
              {cert && (
                <div className="mt-2 rounded-xl border border-emerald-200 bg-emerald-50/60 p-3 text-[11px]">
                  <div className="flex flex-wrap items-center gap-2 font-semibold text-emerald-700">
                    <span>Recognized as {String(cert.document_type || "document").replace(/_/g, " ")}</span>
                    {cert.confidence != null && <span>· {Math.round(cert.confidence * 100)}%</span>}
                    {cert.document_id && <span className="font-mono text-[10px] text-emerald-600">· {cert.document_id.slice(0, 8)}</span>}
                  </div>
                  <div className="mt-2 grid gap-1 sm:grid-cols-2">
                    {cert.fields?.employer && <MiniField label="Employer" value={cert.fields.employer} />}
                    {cert.fields?.designation && <MiniField label="Designation" value={cert.fields.designation} />}
                    {cert.fields?.monthly_salary_aed && <MiniField label="Monthly salary" value={AED(Number(cert.fields.monthly_salary_aed))} />}
                    {cert.fields?.issue_date && <MiniField label="Issue date" value={cert.fields.issue_date} />}
                  </div>
                  {cert.signals && cert.signals.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {cert.signals.slice(0, 4).map((signal) => (
                        <span key={signal} className="rounded-full border border-emerald-200 bg-white px-2 py-0.5 text-[10px] text-emerald-700">
                          {signal.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {certErr && <p className="mt-2 text-xs text-red-600">{certErr}</p>}
              <p className="mt-1 text-[11px] text-moei-muted">
                Upload a photo or image scan. The certificate is classified, saved to your profile, and the salary is extracted live.
              </p>
            </label>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block">
                <span className="text-sm font-medium text-moei-ink">Salary on certificate <span className="text-moei-muted">(optional)</span></span>
                <input value={declaredSalary} onChange={(e) => setDeclaredSalary(e.target.value)} inputMode="numeric"
                  placeholder="e.g. 26861"
                  className="mt-1 w-full rounded-lg border border-moei-line px-3 py-2 text-sm outline-none focus:border-moei-bronze" />
              </label>
              <div className="space-y-2 pt-1">
                <label className="flex items-center gap-2 text-sm text-moei-body">
                  <input type="checkbox" checked={!incomeStable} onChange={(e) => setIncomeStable(!e.target.checked)} className="accent-moei-bronze" />
                  My income has dropped / is not stable
                </label>
                <label className="flex items-center gap-2 text-sm text-moei-body">
                  <input type="checkbox" checked={hardship} onChange={(e) => setHardship(e.target.checked)} className="accent-moei-bronze" />
                  I have a temporary hardship (e.g. medical)
                </label>
              </div>
            </div>

            <label className="flex items-start gap-2 rounded-lg bg-moei-cream/40 p-3 text-[12px] text-moei-body">
              <input type="checkbox" checked={declared} onChange={(e) => setDeclared(e.target.checked)} className="mt-0.5 accent-moei-bronze" />
              <span>I confirm that all uploaded documents are authentic and have not been altered or fabricated.</span>
            </label>

            {err && <p className="text-sm text-red-600">{err}</p>}
            <button onClick={submit} disabled={!declared || busy || certBusy}
              className="moei-btn-primary w-full justify-center disabled:opacity-50">
              {busy ? (<><Loader2 size={15} className="animate-spin" /> Assessing your case…</>) : (<>Submit for instant assessment <ArrowRight size={15} /></>)}
            </button>
            <p className="text-center text-[11px] text-moei-muted">Decision in seconds · 20% deduction cap and repayment-period rules applied automatically.</p>
          </div>
        )}

        {/* Decision */}
        {result && <Decision result={result} onReset={() => setResult(null)} />}

        {/* Status legend */}
        <div className="rounded-2xl border border-moei-line bg-white p-4">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-moei-muted">What you may see</div>
          <div className="flex flex-wrap gap-2 text-[11px]">
            <Legend label="In progress" cls="bg-blue-50 text-blue-700" />
            <Legend label="Approved" cls="bg-emerald-50 text-emerald-700" />
            <Legend label="Additional information required" cls="bg-amber-50 text-amber-700" />
            <Legend label="Rejected" cls="bg-red-50 text-red-700" />
            <Legend label="Under officer review" cls="bg-violet-50 text-violet-700" />
          </div>
        </div>
      </section>
    </div>
  );
}

function Decision({ result, onReset }: { result: Result; onReset: () => void }) {
  const s = STATUS_STYLE[result.citizen.status] || STATUS_STYLE.in_progress;
  const a = result.assessment;
  return (
    <div className={`rounded-2xl border p-6 ${s.bg}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <s.Icon size={22} className={s.text} />
          <div>
            <div className={`text-lg font-bold ${s.text}`}>{result.citizen.status_label}</div>
            <div className="font-mono text-[11px] text-moei-muted">{result.reference}</div>
          </div>
        </div>
        <button onClick={onReset} className="text-[11px] text-moei-muted hover:text-moei-bronze">New request</button>
      </div>

      <p className="mt-3 text-sm font-medium text-moei-ink">{result.citizen.headline}</p>
      <p className="mt-2 text-sm text-moei-body leading-relaxed">{result.citizen.reason}</p>

      {/* Plan + compliance (transparent, but simple) */}
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {a.proposed_repayment_plan && (
          <div className="rounded-lg border border-white bg-white/70 p-3 sm:col-span-3">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-moei-muted">Proposed plan</div>
            <div className="mt-0.5 text-sm font-semibold text-moei-ink">{a.proposed_repayment_plan}</div>
          </div>
        )}
        <Pill label="Deduction of income" value={a.proposed_deduction_rate != null ? `${a.proposed_deduction_rate}%` : "—"} />
        <Pill label="20% rule" value={a.rule_20_compliance} good={a.rule_20_compliance === "Pass"} />
        <Pill label="Period rule" value={a.rule_period_compliance} good={a.rule_period_compliance === "Pass"} />
      </div>
    </div>
  );
}

function Fact({ icon: Icon, label, value, tone }: { icon: typeof Home; label: string; value: string; tone?: "warn" }) {
  return (
    <div className="rounded-lg border border-moei-line bg-moei-cream/20 p-3">
      <div className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-moei-muted"><Icon size={11} /> {label}</div>
      <div className={`mt-1 text-sm font-bold ${tone === "warn" ? "text-red-600" : "text-moei-ink"}`}>{value}</div>
    </div>
  );
}
function MiniField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-white/70 px-2 py-1">
      <span className="text-moei-muted">{label}: </span>
      <span className="font-medium text-moei-ink">{value}</span>
    </div>
  );
}
function Pill({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className="rounded-lg border border-white bg-white/70 p-3">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-moei-muted">{label}</div>
      <div className={`mt-0.5 text-sm font-bold ${good === undefined ? "text-moei-ink" : good ? "text-emerald-700" : "text-red-600"}`}>{value}</div>
    </div>
  );
}
function Legend({ label, cls }: { label: string; cls: string }) {
  return <span className={`rounded-full px-2.5 py-1 font-medium ${cls}`}>{label}</span>;
}
