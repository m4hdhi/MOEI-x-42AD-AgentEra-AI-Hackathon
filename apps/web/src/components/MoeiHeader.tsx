"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search, User, Globe, Accessibility, ChevronDown, LogIn, LogOut } from "lucide-react";
import { loginUrl, logoutAndRedirect, useUaePassSession } from "@/lib/auth";
import { AccessibilityToggle } from "@/components/AccessibilityToggle";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/chat", label: "Services", hasDropdown: true },
  { href: "#", label: "Media Center" },
  { href: "#", label: "Knowledge Center" },
  { href: "#", label: "Digital Participation" },
  { href: "#", label: "Open Data" },
  { href: "#", label: "About Ministry" },
  { href: "/chat", label: "Ask MOEI" },
];

// Secondary nav for our app — small bronze pills under the main nav
// Citizen-facing nav. Admin pages live under /admin/* and are only reachable via the
// "Staff sign-in" link in the footer.
const APP_NAV: { href: string; label: string; external?: boolean }[] = [
  { href: "/chat", label: "Chat" },
  { href: "/mobile", label: "Mobile App" },
  { href: "/call", label: "Call Centre" },
];

export function MoeiHeader() {
  const pathname = usePathname();
  const { session, loading } = useUaePassSession();
  return (
    <>
      <div className="moei-top-rule" />
      <header className="w-full border-b border-moei-line bg-white">
        {/* Top row: logo lockup + Hassan badge + search */}
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-6 py-4">
          <Link href="/" className="flex items-center gap-4">
            <Image
              src="/moei-logo.png"
              alt="UAE Ministry of Energy and Infrastructure"
              width={140}
              height={64}
              priority
              className="h-14 w-auto"
            />
            <div className="ml-1 hidden items-center gap-2 rounded-full border border-moei-bronze/40 bg-moei-cream px-3 py-1.5 sm:flex">
              <span className="h-1.5 w-1.5 rounded-full bg-moei-bronze" />
              <span className="text-[11px] font-semibold uppercase tracking-wider text-moei-bronze">
                Smart Assistant
              </span>
            </div>
          </Link>

          {/* Right side: search + UAE PASS auth */}
          <div className="flex items-center gap-3">
            {/* Search — bronze border, MOEI style */}
            <div className="hidden items-center gap-2 rounded-lg border-2 border-moei-bronze bg-white px-4 py-2 lg:flex lg:w-72">
              <input
                placeholder="Search in website"
                className="w-full bg-transparent text-sm outline-none placeholder:text-moei-muted"
              />
              <Search size={18} className="text-moei-bronze" />
            </div>

            {/* UAE PASS auth state */}
            {!loading && session?.authenticated ? (
              <div className="flex items-center gap-2">
                <div className="hidden text-right md:block">
                  <div className="text-xs font-semibold text-moei-ink">
                    {session.full_name_en || "Citizen"}
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-moei-muted">
                    {session.user_type || "UAE PASS"}
                    {session.emirates_id ? ` · ${session.emirates_id}` : ""}
                  </div>
                </div>
                <button
                  onClick={logoutAndRedirect}
                  title="Sign out"
                  className="moei-btn-icon"
                  aria-label="Sign out"
                >
                  <LogOut size={16} />
                </button>
              </div>
            ) : (
              <a
                href={loginUrl()}
                className="moei-btn-primary"
                title="Sign in with UAE PASS"
              >
                <LogIn size={14} /> Login with UAE PASS
              </a>
            )}
          </div>
        </div>

        {/* Primary nav — mirrors moei.gov.ae's Home · Services · Media Center · ... */}
        <nav className="border-t border-moei-line bg-white">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6">
            <ul className="flex items-center gap-8 py-3 overflow-x-auto">
              {NAV.map((item) => {
                const active = item.href === pathname;
                return (
                  <li key={item.label}>
                    <Link
                      href={item.href}
                      className={
                        "moei-nav-link flex items-center gap-1 whitespace-nowrap " +
                        (active ? "text-moei-bronze" : "")
                      }
                    >
                      {item.label}
                      {item.hasDropdown && <ChevronDown size={12} />}
                    </Link>
                  </li>
                );
              })}
            </ul>

            <div className="hidden items-center gap-4 text-moei-muted md:flex">
              <button className="transition-colors hover:text-moei-bronze" aria-label="Citizen account">
                <User size={18} />
              </button>
              <AccessibilityToggle />
              <button className="transition-colors hover:text-moei-bronze" aria-label="Language">
                <Globe size={18} />
              </button>
            </div>
          </div>
        </nav>

        {/* Secondary nav */}
        <div className="border-t border-moei-line bg-moei-sand">
          <div className="mx-auto flex max-w-7xl items-center gap-2 overflow-x-auto px-6 py-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-moei-muted">
              Quick access:
            </span>
            {APP_NAV.map((item) => {
              const active = item.href === pathname;
              return (
                <Link
                  key={item.href + item.label}
                  href={item.href}
                  target={item.external ? "_blank" : undefined}
                  rel={item.external ? "noreferrer" : undefined}
                  className={
                    "whitespace-nowrap rounded-full border px-3 py-1 text-xs font-medium transition-all " +
                    (active
                      ? "border-moei-bronze bg-moei-bronze text-white"
                      : "border-moei-line bg-white text-moei-body hover:border-moei-bronze hover:text-moei-bronze")
                  }
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      </header>
    </>
  );
}
