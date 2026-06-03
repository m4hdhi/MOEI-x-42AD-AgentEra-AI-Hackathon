"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Search, ShieldCheck, ChevronRight } from "lucide-react";
import { API_URL } from "@/lib/utils";

type Event = { node: string; payload: unknown; at: string };

function AuditInner() {
  const params = useSearchParams();
  const [cid, setCid] = useState(params.get("cid") ?? "");
  const [events, setEvents] = useState<Event[] | null>(null);
  const [error, setError] = useState("");

  async function load(theCid?: string) {
    const c = (theCid ?? cid).trim();
    if (!c) return;
    setError("");
    setEvents(null);
    try {
      const r = await fetch(`${API_URL}/copilot/audit/${encodeURIComponent(c)}`);
      if (!r.ok) {
        setError(`No audit record found for ${c} (HTTP ${r.status}). The full technical trace may still be available.`);
        return;
      }
      const data = await r.json();
      setEvents(data.events || []);
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    const fromUrl = params.get("cid");
    if (fromUrl) {
      setCid(fromUrl);
      load(fromUrl);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="bg-moei-cream/30">
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-10">
          <div className="flex items-center gap-2 text-moei-bronze">
            <ShieldCheck size={18} />
            <span className="moei-kicker">UAE PDPL · Article 7</span>
          </div>
          <h1 className="mt-3 moei-h-section">Audit Trail · Right to Explanation</h1>
          <p className="mt-2 max-w-2xl text-sm text-moei-body">
            Every decision made on a citizen's behalf is recorded with the inputs, the rule or service that produced the answer, and the final reply. Paste a conversation reference to walk through the full record.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-6 py-10">
        <div className="rounded-sm border border-moei-line bg-white p-5">
          <label className="moei-kicker">Case number or conversation reference</label>
          <div className="mt-2 flex gap-2">
            <input
              value={cid}
              onChange={(e) => setCid(e.target.value)}
              placeholder="e.g. MOEI-CASE-20260530-0001"
              className="flex-1 rounded-sm border border-moei-line bg-white px-3 py-2 text-sm outline-none focus:border-moei-bronze"
            />
            <button onClick={() => load()} disabled={!cid} className="moei-btn-primary">
              <Search size={14} /> Look up
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-5 rounded-sm border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
            {error}
          </div>
        )}

        {events && events.length === 0 && (
          <p className="mt-5 text-sm text-moei-muted">
            No events recorded under that reference yet. The full technical trace may still be available — see the link below.
          </p>
        )}

        {events && events.length > 0 && (
          <ol className="mt-6 relative space-y-4 border-l-2 border-moei-line pl-6">
            {events.map((e, i) => (
              <li key={i} className="relative">
                <span className="absolute -left-[31px] top-1 flex h-5 w-5 items-center justify-center rounded-full bg-moei-bronze text-[10px] font-bold text-white">
                  {i + 1}
                </span>
                <div className="rounded-lg border border-moei-line bg-white p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-moei-ink">{nodeLabel(e.node)}</span>
                    <span className="text-[11px] text-moei-muted">{nodeStep(e.node)}</span>
                  </div>
                  <p className="mt-1 text-sm text-moei-body">{summarise(e.node, e.payload as any)}</p>
                  <details className="mt-2">
                    <summary className="cursor-pointer text-[11px] text-moei-muted hover:text-moei-bronze">Technical detail</summary>
                    <pre className="mt-2 max-h-60 overflow-auto rounded-sm bg-moei-cream/50 p-3 text-[11px] text-moei-ink">
                      {JSON.stringify(cleanPayload(e.payload as any), null, 2)}
                    </pre>
                  </details>
                </div>
              </li>
            ))}
          </ol>
        )}

        <div className="mt-8 rounded-sm border border-moei-bronze/40 bg-moei-cream/40 p-5">
          <div className="text-xs font-semibold uppercase tracking-wider text-moei-bronze">For engineers</div>
          <div className="mt-1 font-semibold text-moei-ink">Full technical trace</div>
          <p className="mt-1 text-xs text-moei-body">
            The complete step-by-step trace — including the routing decision, knowledge lookup, response generation, and timing — is available for compliance review and incident investigation.
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
      </section>
    </div>
  );
}

// ---- Friendly rendering of each decision step --------------------------------
const NODE_META: Record<string, { label: string; step: string }> = {
  Request: { label: "Citizen request received", step: "Step 1 · Intake" },
  Router: { label: "Understood the request", step: "Step 2 · Classification" },
  Sentiment: { label: "Read the citizen's tone", step: "Step 3 · Sentiment" },
  Guardrails: { label: "Privacy & policy checks", step: "Step 4 · Guardrails" },
  Knowledge: { label: "Looked up official sources", step: "Step 5 · Knowledge" },
  Worker: { label: "Applied the service rules", step: "Step 6 · Processing" },
  Critic: { label: "Quality self-check", step: "Step 7 · Review" },
  Escalation: { label: "Escalation decision", step: "Step 8 · Routing" },
  Reply: { label: "Reply sent to citizen", step: "Final · Response" },
};
function nodeLabel(n: string) { return NODE_META[n]?.label ?? n; }
function nodeStep(n: string) { return NODE_META[n]?.step ?? ""; }

function summarise(node: string, p: Record<string, any>): string {
  switch (node) {
    case "Request": return `“${p.message ?? ""}” · channel: ${p.channel ?? "—"}${p.case_number ? ` · case ${p.case_number}` : ""}`;
    case "Router": return `Service: ${p.service ?? "—"} · intent: ${p.intent ?? "—"} · confidence ${Math.round((p.confidence ?? 0) * 100)}%`;
    case "Sentiment": return p.score == null ? "Not scored" : `Sentiment ${Math.round(p.score * 100)}% ${p.score < 0.4 ? "(negative — handled with care)" : p.score >= 0.7 ? "(positive)" : "(neutral)"}`;
    case "Guardrails": return `${p.pii_redacted ? "Personal data redacted. " : "No personal data exposed. "}${p.policy_blocked ? `Blocked: ${p.block_reason}` : "Passed policy checks."}`;
    case "Knowledge": {
      const s = p.sources ?? [];
      return s.length ? `Cited ${s.length} official source(s): ${s.map((x: any) => x.title).filter(Boolean).join(", ")}` : "No external sources needed.";
    }
    case "Worker": {
      const tools = p.tool_calls ?? [];
      return tools.length ? `Used: ${tools.map((t: any) => t.tool).join(", ")}` : "Answered from the service catalogue.";
    }
    case "Critic": return p.score == null ? "—" : `Quality score ${Math.round(p.score * 100)}%${p.notes ? ` · ${p.notes}` : ""}`;
    case "Escalation": return p.escalated ? `Escalated to a human officer${p.reason ? ` — ${p.reason}` : ""}` : "Resolved by the assistant — no escalation needed.";
    case "Reply": return `“${(p.text ?? "").slice(0, 160)}${(p.text ?? "").length > 160 ? "…" : ""}”`;
    default: return "";
  }
}
function cleanPayload(p: Record<string, any>) {
  const { _step, ...rest } = p || {};
  return rest;
}

export default function AuditPage() {
  return (
    <Suspense fallback={null}>
      <AuditInner />
    </Suspense>
  );
}
