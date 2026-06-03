"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Star, ThumbsUp } from "lucide-react";
import { API_URL } from "@/lib/utils";

function CsatInner() {
  const params = useSearchParams();
  const caseNumber = params.get("case") || "";
  const [csat, setCsat] = useState<number | null>(null);
  const [ces, setCes] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (csat === null && ces === null) {
      setError("Please rate at least one of the questions.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const r = await fetch(`${API_URL}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ case_number: caseNumber, csat, ces, comment }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setDone(true);
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="bg-moei-cream/30">
        <section className="mx-auto max-w-2xl px-6 py-20 text-center">
          <div className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-moei-bronze">
            <ThumbsUp className="text-white" size={28} />
          </div>
          <h1 className="mt-6 moei-h-section">Thank you</h1>
          <p className="mt-3 text-moei-body">
            Your feedback has been recorded{caseNumber && <> against case <code className="rounded bg-moei-cream px-1.5 py-0.5 text-moei-bronze">{caseNumber}</code></>}.
            We use it to improve every channel.
          </p>
          <a href="/" className="moei-btn-primary mt-8 inline-flex">Back to MOEI</a>
        </section>
      </div>
    );
  }

  return (
    <div className="bg-moei-cream/30">
      <section className="mx-auto max-w-2xl px-6 py-12">
        <span className="moei-kicker">Customer Happiness · Service Feedback</span>
        <h1 className="mt-2 moei-h-section">How was your experience?</h1>
        {caseNumber && (
          <p className="mt-2 text-sm text-moei-body">
            About case <code className="rounded bg-moei-cream px-1.5 py-0.5 font-mono text-moei-bronze">{caseNumber}</code>
          </p>
        )}

        <div className="mt-8 space-y-8 rounded-2xl border border-moei-line bg-white p-6">
          <Question
            title="Overall satisfaction (CSAT)"
            hint="1 = Very dissatisfied · 5 = Very satisfied"
            value={csat}
            onChange={setCsat}
            labels={["😡", "😞", "😐", "🙂", "😍"]}
          />
          <Question
            title="Effort score (CES)"
            hint="1 = Very easy · 5 = Very hard to resolve"
            value={ces}
            onChange={setCes}
            labels={["🚀", "✨", "🤔", "😅", "🧱"]}
          />
          <div>
            <label className="mb-2 block text-sm font-semibold text-moei-ink">
              Anything else (optional)
            </label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={3}
              placeholder="What worked, what could be better?"
              className="w-full rounded-xl border border-moei-line px-3 py-2 text-sm outline-none focus:border-moei-bronze"
            />
          </div>

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              {error}
            </div>
          )}

          <button
            onClick={submit}
            disabled={busy}
            className="moei-btn-primary w-full justify-center"
          >
            {busy ? "Submitting…" : "Submit feedback"}
          </button>
        </div>

        <p className="mt-6 text-center text-[11px] text-moei-muted">
          PDPL Art. 5 — your responses are stored against your case only, never used for marketing.
        </p>
      </section>
    </div>
  );
}

function Question({
  title, hint, value, onChange, labels,
}: { title: string; hint: string; value: number | null; onChange: (v: number) => void; labels: string[] }) {
  return (
    <div>
      <div className="mb-1 text-sm font-semibold text-moei-ink">{title}</div>
      <div className="mb-3 text-xs text-moei-muted">{hint}</div>
      <div className="grid grid-cols-5 gap-2">
        {labels.map((label, i) => {
          const num = i + 1;
          const active = value === num;
          return (
            <button
              key={num}
              type="button"
              onClick={() => onChange(num)}
              className={
                "flex flex-col items-center gap-1 rounded-xl border p-3 transition " +
                (active
                  ? "border-moei-bronze bg-moei-cream shadow-md"
                  : "border-moei-line bg-white hover:border-moei-bronze/50")
              }
            >
              <span className="text-2xl">{label}</span>
              <span className={"text-xs font-semibold " + (active ? "text-moei-bronze" : "text-moei-muted")}>
                {num}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function CsatPage() {
  return (
    <Suspense fallback={null}>
      <CsatInner />
    </Suspense>
  );
}
