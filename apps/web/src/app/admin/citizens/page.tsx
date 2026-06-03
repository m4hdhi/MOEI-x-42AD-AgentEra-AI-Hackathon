"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Users, Search, ChevronRight, ShieldCheck, AlertTriangle, MessageSquare,
  Mic, Globe, Smartphone, RefreshCw,
} from "lucide-react";
import { API_URL } from "@/lib/utils";

type Citizen = {
  user_id: string;
  name: string | null;
  user_type: string | null;
  mobile: string | null;
  email: string | null;
  verified: boolean | null;
  total_cases: number;
  open_cases: number;
  escalated_cases: number;
  avg_sentiment: number | null;
  last_case_at: string | null;
  channels: string[];
};

const CH_ICON: Record<string, typeof Globe> = {
  whatsapp: MessageSquare, voice: Mic, web: Globe, mobile: Smartphone,
};

function sentimentTone(s: number | null) {
  if (s === null) return "text-slate-400";
  if (s >= 0.6) return "text-emerald-600";
  if (s >= 0.4) return "text-amber-600";
  return "text-red-600";
}

export default function CitizensPage() {
  const [items, setItems] = useState<Citizen[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const r = await fetch(`${API_URL}/crm/citizens?limit=200`).then((x) => x.json());
      setItems(r.citizens || []);
    } catch { /* ignore */ } finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  const filtered = items.filter(
    (c) => !q || (`${c.name ?? ""} ${c.user_id}`.toLowerCase().includes(q.toLowerCase())),
  );

  return (
    <div className="bg-moei-cream/30 min-h-screen">
      <section className="border-b border-moei-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-10">
          <div className="flex items-end justify-between">
            <div>
              <span className="moei-kicker">Customer Relationship Management</span>
              <h1 className="mt-2 moei-h-section">Citizens</h1>
              <p className="mt-2 text-sm text-moei-body">
                Every citizen who has contacted the ministry on any channel. Open a profile to see
                their full history and take the next action.
              </p>
            </div>
            <button onClick={load} className="moei-btn-ghost text-xs">
              <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
            </button>
          </div>

          <div className="mt-6 flex items-center gap-2 rounded-lg border border-moei-line bg-white px-3 py-2 lg:w-96">
            <Search size={16} className="text-moei-muted" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search by name or Emirates ID"
              className="w-full bg-transparent text-sm outline-none"
            />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-8">
        <div className="overflow-hidden rounded-xl border border-moei-line bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-moei-line bg-moei-cream/40 text-left text-[11px] uppercase tracking-wider text-moei-muted">
                <th className="px-4 py-3 font-semibold">Citizen</th>
                <th className="px-4 py-3 font-semibold">Channels</th>
                <th className="px-4 py-3 text-center font-semibold">Cases</th>
                <th className="px-4 py-3 text-center font-semibold">Open</th>
                <th className="px-4 py-3 text-center font-semibold">Escalated</th>
                <th className="px-4 py-3 text-center font-semibold">Sentiment</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr
                  key={c.user_id}
                  className="border-b border-moei-line/60 transition hover:bg-moei-cream/30"
                >
                  <td className="px-4 py-3">
                    <Link href={`/admin/citizens/${encodeURIComponent(c.user_id)}`} className="flex items-center gap-3">
                      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-moei-cream text-xs font-bold text-moei-bronze">
                        {(c.name || "?").slice(0, 1).toUpperCase()}
                      </span>
                      <span>
                        <span className="flex items-center gap-1.5 font-semibold text-moei-ink">
                          {c.name || "Unknown"}
                          {c.verified ? (
                            <span title="UAE PASS verified"><ShieldCheck size={13} className="text-emerald-600" /></span>
                          ) : null}
                        </span>
                        <span className="font-mono text-[11px] text-moei-muted">{c.user_id}</span>
                      </span>
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1.5">
                      {(c.channels || []).map((ch) => {
                        const Icon = CH_ICON[ch] ?? Globe;
                        return (
                          <span key={ch} title={ch} className="flex h-6 w-6 items-center justify-center rounded bg-moei-cream/60">
                            <Icon size={12} className="text-moei-bronze" />
                          </span>
                        );
                      })}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center font-semibold text-moei-ink">{c.total_cases}</td>
                  <td className="px-4 py-3 text-center">
                    {c.open_cases > 0 ? (
                      <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-700">{c.open_cases}</span>
                    ) : <span className="text-moei-muted">—</span>}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {c.escalated_cases > 0 ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-700">
                        <AlertTriangle size={10} /> {c.escalated_cases}
                      </span>
                    ) : <span className="text-moei-muted">—</span>}
                  </td>
                  <td className={"px-4 py-3 text-center font-semibold " + sentimentTone(c.avg_sentiment)}>
                    {c.avg_sentiment === null ? "—" : `${Math.round(c.avg_sentiment * 100)}%`}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link href={`/admin/citizens/${encodeURIComponent(c.user_id)}`} className="inline-flex items-center text-moei-bronze hover:text-moei-bronze-dark">
                      <ChevronRight size={16} />
                    </Link>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-sm text-moei-muted">
                    <Users className="mx-auto mb-2 text-moei-bronze" size={22} />
                    No citizens found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
