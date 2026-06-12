"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { User, Globe, ChevronDown, LogIn, LogOut } from "lucide-react";
import { loginUrl, logoutAndRedirect, useUaePassSession } from "@/lib/auth";
import { AccessibilityToggle } from "@/components/AccessibilityToggle";
import { SmartSearch } from "@/components/SmartSearch";
import { useLang } from "@/lib/i18n";

export function MoeiHeader() {
  const pathname = usePathname();
  const { session, loading } = useUaePassSession();
  const { t, lang, setLang } = useLang();

  // Primary nav — mirrors moei.gov.ae's Home · Services · Media Center · …
  const NAV: { href: string; label: string; hasDropdown?: boolean }[] = [
    { href: "/", label: t("Home", "الرئيسية") },
    { href: "/chat", label: t("Services", "الخدمات"), hasDropdown: true },
    { href: "#", label: t("Media Center", "المركز الإعلامي") },
    { href: "#", label: t("Knowledge Center", "مركز المعرفة") },
    { href: "#", label: t("Digital Participation", "المشاركة الرقمية") },
    { href: "#", label: t("Open Data", "البيانات المفتوحة") },
    { href: "#", label: t("About Ministry", "عن الوزارة") },
    { href: "/chat", label: t("Ask MOEI", "اسأل الوزارة") },
  ];

  // Secondary nav for our app — small pills under the main nav. Citizen-facing; admin pages live
  // under /admin/* and are only reachable via the "Staff sign-in" link in the footer.
  const APP_NAV: { href: string; label: string; external?: boolean }[] = [
    { href: "/chat", label: t("Chat", "الدردشة") },
    { href: "/mobile", label: t("Mobile App", "تطبيق الهاتف") },
    { href: "/call", label: t("Call Centre", "مركز الاتصال") },
    { href: "/sign", label: t("Sign Language", "لغة الإشارة") },
    { href: "/automation", label: t("Task Automation", "أتمتة المهام") },
  ];

  return (
    <>
      <div className="moei-top-rule" />
      <header className="w-full border-b border-moei-line bg-white">
        {/* Top row: logo lockup + Agent42 badge + search */}
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-6 py-4">
          <Link href="/" className="flex items-center gap-4">
            <Image
              src="/moei-logo.png"
              alt={t(
                "UAE Ministry of Energy and Infrastructure",
                "وزارة الطاقة والبنية التحتية - الإمارات",
              )}
              width={140}
              height={64}
              priority
              className="h-14 w-auto"
            />
            <div className="ml-1 hidden items-center gap-2 rounded-full border border-moei-bronze/40 bg-moei-cream px-3 py-1.5 sm:flex">
              <span className="h-1.5 w-1.5 rounded-full bg-moei-bronze" />
              <span className="text-[11px] font-semibold uppercase tracking-wider text-moei-bronze">
                {t("Smart Assistant", "المساعد الذكي")}
              </span>
            </div>
          </Link>

          {/* Right side: search + UAE PASS auth */}
          <div className="flex items-center gap-3">
            {/* Search — bronze border, MOEI style */}
            <div className="hidden lg:block lg:w-80">
              <SmartSearch compact placeholder={t("Search in website", "ابحث في الموقع")} />
            </div>

            {/* UAE PASS auth state */}
            {!loading && session?.authenticated ? (
              <div className="flex items-center gap-2">
                <div className="hidden text-right md:block">
                  <div className="text-xs font-semibold text-moei-ink">
                    {session.full_name_en || t("Citizen", "مواطن")}
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-moei-muted">
                    {session.user_type || "UAE PASS"}
                    {session.emirates_id ? ` · ${session.emirates_id}` : ""}
                  </div>
                </div>
                <button
                  onClick={logoutAndRedirect}
                  title={t("Sign out", "تسجيل الخروج")}
                  className="moei-btn-icon"
                  aria-label={t("Sign out", "تسجيل الخروج")}
                >
                  <LogOut size={16} />
                </button>
              </div>
            ) : (
              <a
                href={loginUrl(lang)}
                className="moei-btn-primary"
                title={t("Sign in with UAE PASS", "الدخول عبر الهوية الرقمية")}
              >
                <LogIn size={14} />{" "}
                {t("Login with UAE PASS", "الدخول عبر الهوية الرقمية")}
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
              <Link
                href="/account"
                className="transition-colors hover:text-moei-bronze"
                aria-label={t("Citizen account", "حساب المتعامل")}
                title={t("Citizen account", "حساب المتعامل")}
              >
                <User size={18} />
              </Link>
              <AccessibilityToggle />
              {/* Language switch — toggles the whole app between English and Arabic (RTL). */}
              <button
                onClick={() => setLang(lang === "ar" ? "en" : "ar")}
                className="flex items-center gap-1.5 transition-colors hover:text-moei-bronze"
                aria-label={t("Switch to Arabic", "التبديل إلى الإنجليزية")}
                title={t("Switch to Arabic", "التبديل إلى الإنجليزية")}
              >
                <Globe size={18} />
                <span className="text-xs font-semibold">
                  {t("العربية", "English")}
                </span>
              </button>
            </div>
          </div>
        </nav>

        {/* Secondary nav */}
        <div className="border-t border-moei-line bg-moei-sand">
          <div className="mx-auto flex max-w-7xl items-center gap-2 overflow-x-auto px-6 py-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-moei-muted">
              {t("Quick access:", "وصول سريع:")}
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
