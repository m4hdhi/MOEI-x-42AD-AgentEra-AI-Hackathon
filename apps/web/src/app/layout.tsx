import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { MoeiHeader } from "@/components/MoeiHeader";
import { MoeiFooter } from "@/components/MoeiFooter";

// Fonts are self-hosted (vendored under ./fonts) instead of fetched from Google at build time,
// so the app builds and runs fully offline — critical for the demo machine / fresh devices, and
// it removes the ~6s-per-compile Google Fonts round-trip. Both are variable woff2 files (one file
// covers every weight). MOEI uses a custom clean sans on moei.gov.ae; IBM Plex Sans is the closest
// free match (geometric, slightly humanist, with a strong bold weight).
const sans = localFont({
  src: "./fonts/IBMPlexSans-Variable.woff2",
  weight: "100 700",
  variable: "--font-sans",
  display: "swap",
});
const arabic = localFont({
  src: "./fonts/NotoSansArabic-Variable.woff2",
  weight: "100 900",
  variable: "--font-arabic",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Ministry of Energy and Infrastructure | Smart Services",
  description:
    "The official smart services portal of the UAE Ministry of Energy and Infrastructure. Get help with housing, energy, transport, maritime, and infrastructure services in Arabic and English, 24 hours a day.",
  icons: {
    icon: "/moei.png",
    shortcut: "/moei.png",
    apple: "/moei.png",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${sans.variable} ${arabic.variable}`}>
      <body className="min-h-screen bg-white antialiased">
        {/* Citizen chrome — hidden by globals.css on /admin/* via body[data-surface="admin"] */}
        <div data-citizen-chrome>
          <MoeiHeader />
        </div>
        <main>{children}</main>
        <div data-citizen-chrome>
          <MoeiFooter />
        </div>
      </body>
    </html>
  );
}
