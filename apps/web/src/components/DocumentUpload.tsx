"use client";

import { useEffect, useRef, useState } from "react";
import { Upload, FileCheck, Loader2, MessageCircle } from "lucide-react";
import { API_URL } from "@/lib/utils";

/**
 * Citizen document upload with AI vision extraction (computer vision).
 * Uploads an Emirates ID / salary slip photo; GPT-4o-mini vision reads it and returns
 * structured fields, removing manual data entry.
 */
export function DocumentUpload({ onSendToChat }: { onSendToChat?: (text: string) => void }) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [documents, setDocuments] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function loadDocuments() {
    try {
      const r = await fetch(`${API_URL}/documents?limit=5`, { credentials: "include" });
      if (!r.ok) return;
      const data = await r.json();
      setDocuments(data.documents || []);
    } catch {
      // Best-effort only; upload still works if the saved list cannot load.
    }
  }

  useEffect(() => {
    loadDocuments();
  }, []);

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
      else {
        setResult(data);
        loadDocuments();
      }
    } catch (err: any) {
      setError(err?.message || "Upload failed.");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  const fields = result?.fields || {};
  const shown = [
    "document_type",
    "full_name",
    "id_number",
    "nationality",
    "employer",
    "designation",
    "monthly_salary_aed",
    "issue_date",
    "expiry_date",
  ]
    .filter((k) => fields[k]);
  const confidence = typeof result?.confidence === "number" ? Math.round(result.confidence * 100) : null;

  return (
    <div className="rounded-2xl border border-moei-line bg-white p-5">
      <div className="flex items-center gap-2 text-sm font-semibold text-moei-ink">
        <Upload size={15} className="text-moei-bronze" /> Upload a document
      </div>
      <p className="mt-1 text-xs text-moei-body">
        Photograph your Emirates ID or salary certificate — we read it automatically and save it to your profile.
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
            <FileCheck size={13} /> Recognized as {String(result.document_type || "document").replace(/_/g, " ")}
            {confidence != null && <span className="text-emerald-600">({confidence}%)</span>}
          </div>
          <dl className="mt-2 space-y-1 text-[11px]">
            {shown.map((k) => (
              <div key={k} className="flex justify-between gap-2">
                <dt className="capitalize text-moei-muted">{k.replace(/_/g, " ")}</dt>
                <dd className="text-right font-medium text-moei-ink">{String(fields[k])}</dd>
              </div>
            ))}
          </dl>
          {result.signals?.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {result.signals.slice(0, 4).map((signal: string) => (
                <span
                  key={signal}
                  className="rounded-full border border-emerald-200 bg-white px-2 py-0.5 text-[10px] text-emerald-700"
                >
                  {signal.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}
          {onSendToChat && result.chat_summary && (
            <button
              onClick={() => onSendToChat(result.chat_summary)}
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-emerald-300 bg-white px-3 py-2 text-xs font-semibold text-emerald-700 transition hover:bg-emerald-50"
            >
              <MessageCircle size={13} /> Send document details to chat
            </button>
          )}
          <p className="mt-2 text-[10px] text-moei-muted">{result.note}</p>
        </div>
      )}

      {documents.length > 0 && (
        <div className="mt-4 border-t border-moei-line pt-3">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-moei-muted">
            Saved documents
          </div>
          <ul className="mt-2 space-y-1.5">
            {documents.map((doc) => (
              <li
                key={doc.id}
                className="flex items-center justify-between gap-2 rounded-lg border border-moei-line bg-moei-cream/20 px-3 py-2 text-[11px]"
              >
                <span className="min-w-0">
                  <span className="block truncate font-medium text-moei-ink">
                    {String(doc.document_type || "document").replace(/_/g, " ")}
                  </span>
                  <span className="block truncate text-moei-muted">
                    {doc.original_name || doc.id}
                  </span>
                </span>
                <span className="shrink-0 text-moei-muted">
                  {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : "saved"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
