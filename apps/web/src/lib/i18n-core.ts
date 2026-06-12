export type Lang = "en" | "ar";
export const LOCALE_COOKIE = "NEXT_LOCALE";

export function dirFor(lang: Lang): "ltr" | "rtl" {
  return lang === "ar" ? "rtl" : "ltr";
}

export function normalizeLang(value: string | undefined | null): Lang {
  return value === "ar" ? "ar" : "en";
}
