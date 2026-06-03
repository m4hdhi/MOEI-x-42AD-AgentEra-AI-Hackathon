"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck, LogIn } from "lucide-react";
import { API_URL } from "@/lib/utils";

export default function AdminLoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await fetch(`${API_URL}/admin-auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        throw new Error(j.detail || `HTTP ${r.status}`);
      }
      router.push("/admin/exec");
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-900 px-4">
      <div className="w-full max-w-sm rounded-xl border border-slate-700 bg-slate-800 p-8 shadow-2xl">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-moei-bronze">
            <ShieldCheck className="text-white" size={20} />
          </div>
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-moei-bronze">
              MOEI · Admin Console
            </div>
            <div className="text-base font-bold text-white">Staff sign-in</div>
          </div>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Staff email
            </label>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              required
              placeholder="agent@moei.gov.ae"
              className="w-full rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-moei-bronze"
              autoComplete="email"
            />
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Password
            </label>
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              required
              placeholder="•••••"
              className="w-full rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-moei-bronze"
              autoComplete="current-password"
            />
          </div>

          {error && (
            <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-md bg-moei-bronze px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-moei-bronze-dark disabled:opacity-60"
          >
            <LogIn size={14} />
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="mt-5 rounded-md bg-slate-900/60 px-3 py-2 text-[10px] text-slate-400">
          <span className="font-semibold text-slate-300">Demo access:</span> sign in with any staff email and the password{" "}
          <code className="rounded bg-slate-800 px-1 text-moei-bronze">admin</code>. Live deployments use MOEI federated single sign-on.
        </div>

        <div className="mt-5 text-center">
          <a href="/" className="text-[11px] text-slate-400 hover:text-slate-200">
            ← Back to public site
          </a>
        </div>
      </div>
    </div>
  );
}
