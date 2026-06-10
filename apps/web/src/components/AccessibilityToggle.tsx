"use client";

import { useEffect, useState } from "react";
import { Accessibility, Type, Contrast, X } from "lucide-react";
import { useLang } from "@/lib/i18n";

/**
 * Citizen accessibility controls (Challenge guide: accessibility & inclusion bonus).
 * Toggles high-contrast and large-text ("senior-friendly") modes via body data-attributes,
 * persisted in localStorage. CSS lives in globals.css.
 */
export function AccessibilityToggle() {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const [contrast, setContrast] = useState(false);
  const [largeText, setLargeText] = useState(false);

  useEffect(() => {
    const c = localStorage.getItem("a11y-contrast") === "1";
    const t = localStorage.getItem("a11y-text") === "1";
    setContrast(c); setLargeText(t);
    apply(c, t);
  }, []);

  function apply(c: boolean, t: boolean) {
    if (typeof document === "undefined") return;
    document.body.dataset.contrast = c ? "high" : "normal";
    document.body.dataset.text = t ? "large" : "normal";
  }
  function toggleContrast() {
    const v = !contrast; setContrast(v); localStorage.setItem("a11y-contrast", v ? "1" : "0"); apply(v, largeText);
  }
  function toggleText() {
    const v = !largeText; setLargeText(v); localStorage.setItem("a11y-text", v ? "1" : "0"); apply(contrast, v);
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="transition-colors hover:text-moei-bronze"
        aria-label={t("Accessibility options", "خيارات إمكانية الوصول")}
        aria-expanded={open}
      >
        <Accessibility size={18} />
      </button>
      {open && (
        <div role="dialog" aria-label={t("Accessibility settings", "إعدادات إمكانية الوصول")}
          className="absolute right-0 z-50 mt-2 w-56 rounded-lg border border-moei-line bg-white p-3 shadow-lg">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-moei-muted">{t("Accessibility", "إمكانية الوصول")}</span>
            <button onClick={() => setOpen(false)} aria-label={t("Close", "إغلاق")}><X size={14} className="text-moei-muted" /></button>
          </div>
          <button
            onClick={toggleContrast}
            aria-pressed={contrast}
            className={"mb-1.5 flex w-full items-center gap-2 rounded-md border px-3 py-2 text-sm transition " +
              (contrast ? "border-moei-bronze bg-moei-cream text-moei-bronze" : "border-moei-line text-moei-body hover:border-moei-bronze")}
          >
            <Contrast size={15} /> {t("High contrast", "تباين عالٍ")} {contrast && "✓"}
          </button>
          <button
            onClick={toggleText}
            aria-pressed={largeText}
            className={"flex w-full items-center gap-2 rounded-md border px-3 py-2 text-sm transition " +
              (largeText ? "border-moei-bronze bg-moei-cream text-moei-bronze" : "border-moei-line text-moei-body hover:border-moei-bronze")}
          >
            <Type size={15} /> {t("Larger text", "نص أكبر")} {largeText && "✓"}
          </button>
          <p className="mt-2 text-[10px] text-moei-muted">{t("Voice input is available on the Chat and Call pages.", "الإدخال الصوتي متاح في صفحتي الدردشة والاتصال.")}</p>
        </div>
      )}
    </div>
  );
}
