"use client";

/**
 * Lightweight bilingual (English ⇄ Arabic) layer for the whole app.
 *
 * There is no route-based i18n; instead a single client context carries the active language and a
 * tiny `t(en, ar)` helper so strings stay co-located with the markup that uses them — far easier to
 * apply across a pre-built UI than a key-based catalogue. The choice is persisted in the
 * `NEXT_LOCALE` cookie (so the server layout can render `<html lang/dir>` correctly on first paint,
 * with no flash) and mirrored to `<html>` on every toggle. Arabic flips the document to RTL, which
 * also swaps in the Noto Sans Arabic font via the `[dir="rtl"]` rule in globals.css.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react";

export type Lang = "en" | "ar";
export const LOCALE_COOKIE = "NEXT_LOCALE";

export function dirFor(lang: Lang): "ltr" | "rtl" {
  return lang === "ar" ? "rtl" : "ltr";
}

/** Normalise an arbitrary cookie/string value to a supported language (defaults to English). */
export function normalizeLang(value: string | undefined | null): Lang {
  return value === "ar" ? "ar" : "en";
}

type LangContextValue = {
  lang: Lang;
  dir: "ltr" | "rtl";
  setLang: (lang: Lang) => void;
  toggle: () => void;
  /** Pick the string for the active language. */
  t: (en: string, ar: string) => string;
};

const LangContext = createContext<LangContextValue | null>(null);

function persist(lang: Lang) {
  try {
    document.cookie = `${LOCALE_COOKIE}=${lang};path=/;max-age=31536000;samesite=lax`;
    window.localStorage.setItem(LOCALE_COOKIE, lang);
  } catch {
    /* SSR / privacy mode — non-fatal, the in-memory state still drives the UI this session. */
  }
}

function applyToDocument(lang: Lang) {
  const el = document.documentElement;
  el.lang = lang;
  el.dir = dirFor(lang);
}

export function LanguageProvider({
  initialLang,
  children,
}: {
  initialLang: Lang;
  children: React.ReactNode;
}) {
  const [lang, setLangState] = useState<Lang>(initialLang);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    persist(next);
    applyToDocument(next);
  }, []);

  // Keep <html lang/dir> in sync with state (covers a localStorage value that differs from the
  // cookie used for SSR, and any external state change).
  useEffect(() => {
    applyToDocument(lang);
  }, [lang]);

  const value: LangContextValue = {
    lang,
    dir: dirFor(lang),
    setLang,
    toggle: () => setLang(lang === "ar" ? "en" : "ar"),
    t: (en, ar) => (lang === "ar" ? ar : en),
  };

  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

/**
 * Access the active language and the `t(en, ar)` helper. Safe to call outside the provider (returns
 * an English-only fallback) so isolated component tests / stray renders don't crash.
 */
export function useLang(): LangContextValue {
  const ctx = useContext(LangContext);
  if (ctx) return ctx;
  return {
    lang: "en",
    dir: "ltr",
    setLang: () => {},
    toggle: () => {},
    t: (en) => en,
  };
}
