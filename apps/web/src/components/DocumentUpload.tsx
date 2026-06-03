"use client";

import { useRef, useState } from "react";
import { Upload, FileCheck, Loader2 } from "lucide-react";
import { API_URL } from "@/lib/utils";

/**
 * Citizen document upload with AI vision extraction (computer vision).
 * Uploads an Emirates ID / salary slip photo; GPT-4o-mini vision reads it and returns
 * structured fields, removing manual data entry.
 */
export function DocumentUpload() {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy(true); setError(null); setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const r = await fetch(`${API_URL}/documents/extract`, { method: "POST", body: fd, credentials: "include" });
      const data = await r.json();
      if (!data.ok) { setError(data.reason || "Could not read the document."); }
      else setResult(data);
    } catch (err: any) {
      setError(err?.message || "Upload failed.");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  const fields = result?.fields || {};
  const shown = ["document_type", "full_name", "id_number", "employer", "monthly_salary_aed", "expiry_date"]
    .filter((k) => fields[k]);

  return (
    <div className="rounded-2xl border border-moei-line bg-white p-5">
      <div className="flex items-center gap-2 text-sm font-semibold text-moei-ink">
        <Upload size={15} className="text-moei-bronze" /> Upload a document
      </div>
      <p className="mt-1 text-xs text-moei-body">
        Photograph your Emirates ID or salary certificate — we read it automatically, no typing.
      </p>

      <input ref={inputRef} type="file" accept="image/*" onChange={onPick} className="hidden" />
      <button
        onClick={() => inputRef.current?.click()}
        disabled={busy}
        className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-moei-bronze/50 bg-moei-cream/30 px-3 py-3 text-sm font-medium text-moei-bronze transition hover:bg-moei-cream/60 disabled:opacity-60"
      >
        {busy ? <><Loader2 size={15} className="animate-spin" /> Reading…</> : <><Upload size={15} /> Choose image</>}
      </button>

      {error && <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-800">{error}</div>}

      {result && (
        <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50/50 p-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-700">
            <FileCheck size={13} /> Extracted automatically
          </div>
          <dl className="mt-2 space-y-1 text-[11px]">
            {shown.map((k) => (
              <div key={k} className="flex justify-between gap-2">
                <dt className="capitalize text-moei-muted">{k.replace(/_/g, " ")}</dt>
                <dd className="text-right font-medium text-moei-ink">{String(fields[k])}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-2 text-[10px] text-moei-muted">{result.note}</p>
        </div>
      )}
    </div>
  );
}
