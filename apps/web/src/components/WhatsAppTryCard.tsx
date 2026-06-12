"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Copy, Check } from "lucide-react";
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

  const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=176x176&data=${encodeURIComponent(info.wa_link)}`;

  function copyJoin() {
    if (!info) return;
    navigator.clipboard.writeText(info.join_code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div className="moei-card overflow-hidden border-emerald-200 bg-gradient-to-br from-emerald-50 via-white to-white p-6">
      <div className="flex items-center gap-4">
        <WhatsAppLogo />
        <div>
          <div className="text-[13px] font-bold uppercase tracking-[0.28em] text-emerald-700">
            Try on WhatsApp
          </div>
          <h3 className="mt-2 text-2xl font-bold leading-tight text-moei-ink">
            Chat with MOEI on WhatsApp
          </h3>
        </div>
      </div>

      <div className="mt-5 grid items-start gap-5 sm:grid-cols-[176px_1fr]">
        <div className="rounded-[20px] border border-moei-line bg-white p-2.5">
          <img src={qrUrl} alt="Scan to open WhatsApp" className="h-40 w-40" />
        </div>

        <ol className="space-y-3 pt-1 text-lg leading-relaxed text-moei-body">
          <li>
            <span className="font-bold text-moei-ink">1.</span>{" "}
            <a
              href={info.wa_link}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 font-bold text-emerald-700 hover:underline"
            >
              Open WhatsApp <ExternalLink size={16} />
            </a>{" "}
            to <code className="rounded-lg bg-emerald-50 px-3 py-1 text-base text-emerald-800">{info.number}</code>
          </li>
          {info.join_code ? (
            <li>
              <span className="font-bold text-moei-ink">2.</span> Send the code:{" "}
              <button
                type="button"
                onClick={copyJoin}
                className="inline-flex items-center gap-1 rounded-lg bg-emerald-50 px-3 py-1 font-mono text-base text-emerald-800 hover:bg-emerald-100"
              >
                {info.join_code}
                {copied ? <Check size={14} /> : <Copy size={14} />}
              </button>
            </li>
          ) : null}
          <li>
            <span className="font-bold text-moei-ink">{info.join_code ? "3." : "2."}</span> Ask any question about your ministry services.
          </li>
        </ol>
      </div>

      <div className="mt-4 border-t border-emerald-100 pt-2.5 text-[10px] text-moei-muted">
        {info.note}
      </div>
    </div>
  );
}

function WhatsAppLogo() {
  return (
    <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-[14px] bg-gradient-to-br from-[#57f879] to-[#18b91f] text-white shadow-sm">
      <svg viewBox="0 0 448 512" aria-hidden="true" className="h-11 w-11 fill-white">
        <path d="M380.9 97.1C339 55.1 283.2 32 223.9 32 101.5 32 1.9 131.6 1.9 254c0 39.1 10.2 77.3 29.6 111L0 480l117.7-30.9c32.4 17.7 68.9 27 106.1 27h.1c122.3 0 224.1-99.6 224.1-222 0-59.3-25.2-115-67.1-157ZM223.9 438.7c-33.2 0-65.7-8.9-94-25.7l-6.7-4-69.8 18.3 18.6-68.1-4.4-7C49.1 322.8 39.4 288.9 39.4 254c0-101.7 82.8-184.5 184.6-184.5 49.3 0 95.6 19.2 130.4 54.1 34.8 34.9 56.2 81.2 56.1 130.5 0 101.8-84.9 184.6-186.6 184.6Zm101.2-138.2c-5.5-2.8-32.8-16.2-37.9-18-5.1-1.9-8.8-2.8-12.5 2.8-3.7 5.6-14.3 18-17.6 21.8-3.2 3.7-6.5 4.2-12 1.4-32.6-16.3-54-29.1-75.5-66-5.7-9.8 5.7-9.1 16.3-30.3 1.8-3.7.9-6.9-.5-9.7-1.4-2.8-12.5-30.1-17.1-41.2-4.5-10.8-9.1-9.3-12.5-9.5-3.2-.2-6.9-.2-10.6-.2-3.7 0-9.7 1.4-14.8 6.9-5.1 5.6-19.4 19-19.4 46.3 0 27.3 19.9 53.7 22.6 57.4 2.8 3.7 39.1 59.7 94.8 83.8 35.2 15.2 49 16.5 66.6 13.9 10.7-1.6 32.8-13.4 37.4-26.4 4.6-13 4.6-24.1 3.2-26.4-1.3-2.5-5-3.9-10.5-6.6Z" />
      </svg>
    </div>
  );
}
