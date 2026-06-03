"use client";

import { useEffect, useState } from "react";
import { API_URL } from "./utils";

export type UaePassSession = {
  authenticated: boolean;
  sub?: string;
  user_type?: string;             // SOP1 / SOP2 / SOP3
  emirates_id?: string;
  full_name_en?: string;
  full_name_ar?: string;
  first_name_en?: string;
  gender?: string;
  nationality_en?: string;
  mobile?: string;
  email?: string;
};

/** Hook that returns the current UAE PASS session (or null while loading / unauthenticated). */
export function useUaePassSession(): { session: UaePassSession | null; loading: boolean } {
  const [session, setSession] = useState<UaePassSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/auth/me`, { credentials: "include" })
      .then(async (r) => {
        const data = (await r.json()) as UaePassSession;
        if (!cancelled) {
          setSession(data.authenticated ? data : null);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSession(null);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { session, loading };
}

export function loginUrl(locale: "en" | "ar" = "en"): string {
  return `${API_URL}/auth/uaepass/login?locale=${locale}`;
}

export function logoutAndRedirect(): void {
  // POST to /auth/logout, then UAE PASS handles the rest of the redirect chain.
  // We use a form submit so cookies are sent and the browser follows redirects.
  const form = document.createElement("form");
  form.method = "POST";
  form.action = `${API_URL}/auth/logout`;
  document.body.appendChild(form);
  form.submit();
}
