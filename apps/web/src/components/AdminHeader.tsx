"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Headphones, LayoutDashboard, ShieldCheck, ScrollText, ExternalLink, LogOut, ArrowLeft, PhoneCall, Users, Network, Home } from "lucide-react";

const ADMIN_NAV = [
  { href: "/admin/exec", label: "Executive Dashboard", icon: LayoutDashboard },
  { href: "/admin/citizens", label: "Citizens", icon: Users },
  { href: "/admin/rescheduling", label: "Loan Rescheduling", icon: Home },
  { href: "/admin/copilot", label: "Agent Co-pilot", icon: Headphones },
  { href: "/admin/calls", label: "Call Recordings", icon: PhoneCall },
  { href: "/admin/agents", label: "Agent Network", icon: Network },
  { href: "/admin/audit", label: "Audit Trail", icon: ShieldCheck },
  { href: "http://localhost:3001", label: "AI Traces", icon: ScrollText, external: true },
];

export function AdminHeader({ user }: { user?: { email?: string; role?: string } }) {
  const pathname = usePathname();
  const router = useRouter();

  function logout() {
    document.cookie = "hassan_admin=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT";
    router.push("/admin/login");
  }

  return (
    <>
      <div className="h-[3px] w-full bg-slate-900" />
      <header className="w-full border-b border-slate-700 bg-slate-900 text-slate-100">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <Link href="/admin/exec" className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded bg-moei-bronze text-[10px] font-bold uppercase tracking-wider text-white">
                MOEI
              </div>
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-moei-bronze">
                  Admin Console
                </div>
                <div className="text-[13px] font-semibold text-white">
                  Customer Happiness Centre
                </div>
              </div>
            </Link>
            <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-red-300">
              Staff only
            </span>
          </div>

          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="flex items-center gap-1.5 text-xs text-slate-300 transition hover:text-white"
              title="Back to citizen site"
            >
              <ArrowLeft size={12} /> Citizen view
            </Link>
            {user?.email && (
              <div className="hidden md:block text-right">
                <div className="text-xs font-semibold text-white">{user.email}</div>
                <div className="text-[10px] uppercase tracking-wider text-slate-400">{user.role || "agent"}</div>
              </div>
            )}
            <button
              onClick={logout}
              className="flex items-center gap-1 rounded-full border border-slate-600 px-3 py-1 text-xs text-slate-200 transition hover:border-red-400 hover:text-red-300"
              title="Sign out"
            >
              <LogOut size={12} /> Sign out
            </button>
          </div>
        </div>

        <nav className="border-t border-slate-700 bg-slate-800">
          <div className="mx-auto flex max-w-7xl items-center gap-1 px-6">
            {ADMIN_NAV.map((item) => {
              const active = item.href === pathname || (item.href !== "/admin" && pathname.startsWith(item.href));
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  target={item.external ? "_blank" : undefined}
                  rel={item.external ? "noreferrer" : undefined}
                  className={
                    "flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium transition " +
                    (active
                      ? "border-b-2 border-moei-bronze text-white"
                      : "border-b-2 border-transparent text-slate-300 hover:text-white")
                  }
                >
                  <Icon size={12} />
                  {item.label}
                  {item.external && <ExternalLink size={9} className="opacity-60" />}
                </Link>
              );
            })}
          </div>
        </nav>
      </header>
    </>
  );
}
