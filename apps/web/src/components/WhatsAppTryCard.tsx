"use client";

import { useEffect, useState } from "react";
import { MessageSquare, ExternalLink, Copy, Check } from "lucide-react";
import { API_URL } from "@/lib/utils";

type SandboxInfo = {
  number: string;
  join_code: string;
  wa_link: string;
  note: string;
};

export function WhatsAppTryCard() {
  const [info, setInfo] = useState<SandboxInfo | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/whatsapp/sandbox-info`)
      .then((r) => r.json())
      .then(setInfo)
      .catch(() => setInfo(null));
  }, []);

  if (!info) return null;

  const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(info.wa_link)}`;

  function copyJoin() {
    if (!info) return;
    navigator.clipboard.writeText(info.join_code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div className="moei-card overflow-hidden border-emerald-200 bg-gradient-to-br from-emerald-50 via-white to-white p-6">
      <div className="flex items-center gap-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500 text-white">
          <MessageSquare size={16} />
        </span>
        <div>
          <div className="moei-kicker text-emerald-700">Try on WhatsApp</div>
          <h3 className="mt-0.5 text-lg font-bold text-moei-ink">Chat with MOEI on WhatsApp</h3>
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-[180px_1fr]">
        <div className="rounded-xl border border-moei-line bg-white p-2">
          <img src={qrUrl} alt="Scan to open WhatsApp" className="h-full w-full" />
          <div className="mt-1 text-center text-[10px] text-moei-muted">Scan to open</div>
        </div>

        <ol className="space-y-2 text-sm text-moei-body">
          <li>
            <span className="font-semibold text-moei-ink">1.</span>{" "}
            <a
              href={info.wa_link}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 font-semibold text-emerald-700 hover:underline"
            >
              Open WhatsApp <ExternalLink size={12} />
            </a>{" "}
            to <code className="rounded bg-emerald-50 px-1.5 py-0.5 text-xs text-emerald-800">{info.number}</code>
          </li>
          {info.join_code ? (
            <li>
              <span className="font-semibold text-moei-ink">2.</span> Send the code:{" "}
              <button
                type="button"
                onClick={copyJoin}
                className="inline-flex items-center gap-1 rounded bg-emerald-50 px-1.5 py-0.5 font-mono text-xs text-emerald-800 hover:bg-emerald-100"
              >
                {info.join_code}
                {copied ? <Check size={11} /> : <Copy size={11} />}
              </button>
            </li>
          ) : null}
          <li>
            <span className="font-semibold text-moei-ink">{info.join_code ? "3." : "2."}</span> Ask any question about your ministry services.
          </li>
        </ol>
      </div>

      <div className="mt-4 border-t border-emerald-100 pt-3 text-[10px] text-moei-muted">
        {info.note}
      </div>
    </div>
  );
}
