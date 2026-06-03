"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, Search, X } from "lucide-react";
import { API_URL } from "@/lib/utils";

type Hit = {
  id: string;
  title: string;
  title_ar: string;
  summary: string;
  service: string;
  channels: string[];
  fee_aed: number;
  sla_days: number;
  url?: string;
};

export function SmartSearch() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const tRef = useRef<number | null>(null);

  useEffect(() => {
    if (q.trim().length < 2) {
      setHits([]);
      setOpen(false);
      return;
    }
    if (tRef.current) window.clearTimeout(tRef.current);
    tRef.current = window.setTimeout(async () => {
      setBusy(true);
      try {
        const r = await fetch(`${API_URL}/search?q=${encodeURIComponent(q)}&limit=6`);
        const data = await r.json();
        setHits(data.results || []);
        setOpen(true);
      } finally {
        setBusy(false);
      }
    }, 220);
    return () => {
      if (tRef.current) window.clearTimeout(tRef.current);
    };
  }, [q]);

  return (
    <div className="relative w-full max-w-2xl">
      <div className="flex items-center gap-3 rounded-full border-2 border-moei-bronze bg-white px-5 py-3 shadow-sm transition focus-within:shadow-md">
        <Search size={18} className="text-moei-bronze" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search MOEI services — try 'boat', 'housing', 'power outage'…"
          className="flex-1 bg-transparent text-sm font-medium text-moei-ink outline-none placeholder:text-moei-muted"
          onFocus={() => q && setOpen(true)}
        />
        {q && (
          <button
            type="button"
            onClick={() => { setQ(""); setHits([]); setOpen(false); }}
            className="text-moei-muted hover:text-moei-ink"
            aria-label="clear"
          >
            <X size={16} />
          </button>
        )}
        {busy && (
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-moei-bronze" />
        )}
      </div>

      {open && hits.length > 0 && (
        <div className="absolute left-0 right-0 top-full z-20 mt-2 max-h-[420px] overflow-y-auto rounded-2xl border border-moei-line bg-white shadow-xl">
          <ul className="divide-y divide-moei-line/60">
            {hits.map((h) => (
              <li key={h.id}>
                <a
                  href={h.url || "#"}
                  target={h.url ? "_blank" : undefined}
                  rel="noreferrer"
                  className="flex items-start gap-3 px-5 py-3 transition hover:bg-moei-cream"
                >
                  <div className="mt-0.5 rounded-md bg-moei-cream px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-moei-bronze">
                    {h.service}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <div className="truncate text-sm font-semibold text-moei-ink">{h.title}</div>
                      <ArrowUpRight size={14} className="shrink-0 text-moei-muted" />
                    </div>
                    {h.summary && (
                      <div className="mt-0.5 line-clamp-1 text-xs text-moei-body">{h.summary}</div>
                    )}
                    <div className="mt-1 flex flex-wrap gap-3 text-[10px] text-moei-muted">
                      <span>AED {h.fee_aed}</span>
                      <span>{h.sla_days} day{h.sla_days === 1 ? "" : "s"} SLA</span>
                      {h.channels.slice(0, 2).map((c) => (
                        <span key={c} className="truncate">{c}</span>
                      ))}
                    </div>
                  </div>
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
      {open && q.length >= 2 && hits.length === 0 && !busy && (
        <div className="absolute left-0 right-0 top-full z-20 mt-2 rounded-2xl border border-moei-line bg-white p-4 text-xs text-moei-muted shadow-md">
          No services matched <span className="font-semibold text-moei-ink">{q}</span>. Try a broader keyword.
        </div>
      )}
    </div>
  );
}
