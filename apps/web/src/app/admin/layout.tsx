"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AdminHeader } from "@/components/AdminHeader";
import { API_URL } from "@/lib/utils";

type AdminUser = { email?: string; role?: string };

/**
 * Admin layout: renders an AdminHeader (dark/slate) on every /admin/* route
 * except /admin/login. Also enforces "must be signed in" by redirecting
 * unauthenticated users from any /admin/* page to /admin/login.
 *
 * IMPORTANT: this overrides the parent (root) layout's MoeiHeader/Footer because
 * Next.js nested layouts wrap the page but the root layout still renders. To
 * actually replace the header/footer we set a `data-admin` attribute on the body
 * and use CSS to hide the citizen header — see globals.css.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AdminUser | null>(null);
  const [checked, setChecked] = useState(false);
  const isLoginPage = pathname === "/admin/login";

  useEffect(() => {
    if (isLoginPage) {
      setChecked(true);
      return;
    }
    fetch(`${API_URL}/admin-auth/me`, { credentials: "include" })
      .then(async (r) => {
        if (!r.ok) {
          router.replace("/admin/login");
          return;
        }
        const data = await r.json();
        if (!data.authenticated) {
          router.replace("/admin/login");
          return;
        }
        setUser(data);
      })
      .catch(() => router.replace("/admin/login"))
      .finally(() => setChecked(true));
  }, [pathname, isLoginPage, router]);

  // Hide citizen header / footer on admin routes
  useEffect(() => {
    document.body.dataset.surface = "admin";
    return () => {
      delete document.body.dataset.surface;
    };
  }, []);

  if (isLoginPage) {
    // Login is full-screen on its own; no admin header
    return <>{children}</>;
  }

  if (!checked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-900 text-slate-400">
        Loading admin console…
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <AdminHeader user={user ?? undefined} />
      <main>{children}</main>
    </div>
  );
}
