"use client";

import Image from "next/image";
import { ShieldCheck, Lock } from "lucide-react";
import { loginUrl, useUaePassSession, type UaePassSession } from "@/lib/auth";

/**
 * Gates a citizen action (chat / call) behind UAE PASS sign-in.
 *
 * Real-world rationale: we only create a service request and store a citizen's
 * conversation + activity once they are identified. Until then we show a sign-in
 * prompt. When authenticated, the child render-prop receives the verified session.
 */
export function LoginGate({
  theme = "light",
  title,
  subtitle,
  children,
}: {
  theme?: "light" | "dark";
  title: string;
  subtitle: string;
  children: (session: UaePassSession) => React.ReactNode;
}) {
  const { session, loading } = useUaePassSession();

  if (loading) {
    return (
      <div className={"flex min-h-[60vh] items-center justify-center text-sm " + (theme === "dark" ? "text-slate-400" : "text-moei-muted")}>
        Checking your sign-in…
      </div>
    );
  }

  if (session?.authenticated) {
    return <>{children(session)}</>;
  }

  const dark = theme === "dark";
  return (
    <div className={"flex min-h-[70vh] items-center justify-center px-6 py-16 " + (dark ? "bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900" : "bg-moei-cream/30")}>
      <div className={"w-full max-w-md rounded-2xl border p-8 text-center shadow-xl " + (dark ? "border-slate-700 bg-slate-800/80" : "border-moei-line bg-white")}>
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-moei-cream">
          <Lock size={22} className="text-moei-bronze" />
        </div>
        <h1 className={"mt-5 text-xl font-bold " + (dark ? "text-white" : "text-moei-ink")}>{title}</h1>
        <p className={"mt-2 text-sm " + (dark ? "text-slate-400" : "text-moei-body")}>{subtitle}</p>

        <a
          href={loginUrl()}
          className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-moei-bronze px-4 py-3 text-sm font-semibold text-white transition hover:bg-moei-bronze-dark"
        >
          <ShieldCheck size={16} /> Sign in with UAE PASS
        </a>

        <div className={"mt-4 flex items-center justify-center gap-2 text-[11px] " + (dark ? "text-slate-500" : "text-moei-muted")}>
          <Image src="/uae-pass.png" alt="UAE PASS" width={70} height={20} className="h-4 w-auto opacity-80" />
          <span>Your details stay private and are used only to handle your request.</span>
        </div>
      </div>
    </div>
  );
}
