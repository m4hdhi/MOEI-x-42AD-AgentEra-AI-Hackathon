import type { Metadata } from "next";
import { IBM_Plex_Sans, Noto_Sans_Arabic } from "next/font/google";
import "./globals.css";
import { MoeiHeader } from "@/components/MoeiHeader";
import { MoeiFooter } from "@/components/MoeiFooter";

// MOEI uses a custom clean sans on moei.gov.ae; IBM Plex Sans is the closest free
// match (geometric, slightly humanist, with a strong bold weight).
const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
});
const arabic = Noto_Sans_Arabic({
  subsets: ["arabic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-arabic",
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
