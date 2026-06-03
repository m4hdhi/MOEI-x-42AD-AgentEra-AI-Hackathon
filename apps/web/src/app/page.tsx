import Link from "next/link";
import {
  ArrowRight,
  Bookmark,
  MessageSquare,
  Phone,
  Smartphone,
  Globe,
  Search,
  Mic,
  Clock,
  Languages,
  ShieldCheck,
} from "lucide-react";
import { SmartSearch } from "@/components/SmartSearch";
import { WhatsAppTryCard } from "@/components/WhatsAppTryCard";

const SERVICES = [
  {
    title: "Sheikh Zayed Housing Programme",
    desc: "Check loan eligibility, request rescheduling, or submit hardship documents.",
    href: "/chat",
    category: "Housing",
  },
  {
    title: "Application Status",
    desc: "Track any active request across housing, transport, maritime, and infrastructure.",
    href: "/chat",
    category: "All sectors",
  },
  {
    title: "Document Submission",
    desc: "Upload salary slips, bank statements, or Emirates ID securely from any device.",
    href: "/chat",
    category: "All sectors",
  },
  {
    title: "Call Centre",
    desc: "Talk to the MOEI Smart Assistant in Arabic or English. No queue, no wait.",
    href: "/call",
    category: "Contact",
  },
  {
    title: "Energy Services",
    desc: "Tariff information, billing questions, and outage reporting across the federation.",
    href: "/chat",
    category: "Energy",
  },
  {
    title: "Maritime Permits",
    desc: "Vessel registration, port enquiries, and seafarer certificates.",
    href: "/chat",
    category: "Maritime",
  },
  {
    title: "Transport Permits",
    desc: "Federal driver and vehicle services, and national transportation enquiries.",
    href: "/chat",
    category: "Transport",
  },
  {
    title: "Infrastructure Enquiries",
    desc: "Roads, public works, and federal construction information.",
    href: "/chat",
    category: "Infrastructure",
  },
];

const PROMISE = [
  { icon: Clock, label: "Available 24/7", note: "Every day, including weekends." },
  { icon: Languages, label: "Arabic & English", note: "Reply in the language you write or speak." },
  { icon: Smartphone, label: "No app to install", note: "Works in your browser and on WhatsApp." },
  { icon: ShieldCheck, label: "Secure & official", note: "Sign in with UAE PASS for personalised help." },
];

const NEWS = [
  {
    date: "23 May 2026",
    tag: "Customer Happiness",
    title: "MOEI Smart Assistant now answers in Arabic and English on every channel",
    body: "Citizens can start a conversation on WhatsApp and continue on the website or call centre without repeating themselves.",
  },
  {
    date: "13 May 2026",
    tag: "Sheikh Zayed Housing Programme",
    title: "Sheikh Zayed Housing Programme completes handover of Al Suyoh phase 16",
    body: "Eligible families receive their keys ahead of schedule, with on-site customer happiness officers available throughout.",
  },
  {
    date: "11 May 2026",
    tag: "Ministry News",
    title: "MOEI hosts national forum on the future of federal customer service",
    body: "Government leaders discussed how the ministry continues to raise standards of service quality and accessibility.",
  },
];

export default function HomePage() {
  return (
    <div className="bg-white">
      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-moei-sand via-moei-cream/60 to-white">
        <div className="absolute inset-0 opacity-[0.04]">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_50%,_#9c8853_0%,_transparent_50%)]" />
        </div>
        <div className="relative mx-auto grid max-w-7xl gap-10 px-6 py-20 lg:grid-cols-12">
          <div className="lg:col-span-7">
            <span className="moei-kicker">
              Ministry of Energy and Infrastructure
            </span>
            <h1 className="mt-4 moei-h-display">
              Your ministry,
              <br />
              <span className="text-moei-bronze">always answering.</span>
            </h1>
            <p className="mt-6 max-w-xl text-base leading-relaxed text-moei-body md:text-lg">
              Ask about housing, energy, transport, maritime, or infrastructure
              services any time of day. Get clear answers in Arabic or English,
              file a request, or speak to a person when you need one.
            </p>
            <div className="mt-8">
              <SmartSearch />
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/chat" className="moei-btn-primary">
                Start a conversation <ArrowRight size={16} />
              </Link>
              <Link href="/call" className="moei-btn-ghost">
                Call us instead <Phone size={14} />
              </Link>
            </div>
          </div>

          <div className="lg:col-span-5">
            <div className="moei-card p-6">
              <div className="moei-kicker">Our promise</div>
              <h3 className="mt-2 text-2xl font-bold text-moei-ink">
                Service that meets you where you are
              </h3>
              <ul className="mt-4 space-y-3">
                {PROMISE.map((c) => (
                  <li key={c.label} className="flex items-start gap-3">
                    <span className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-lg border border-moei-bronze/30 bg-moei-cream">
                      <c.icon size={16} className="text-moei-bronze" />
                    </span>
                    <div>
                      <div className="text-sm font-semibold text-moei-ink">{c.label}</div>
                      <div className="text-xs text-moei-muted">{c.note}</div>
                    </div>
                  </li>
                ))}
              </ul>
              <div className="mt-5 border-t border-moei-line pt-4 text-xs text-moei-muted">
                Call centre 800 6634 · WhatsApp · moei.gov.ae · MOEI mobile app
              </div>
            </div>
            <div className="mt-4">
              <WhatsAppTryCard />
            </div>
          </div>
        </div>
        <div className="h-1 bg-moei-bronze/80" />
      </section>

      {/* Services */}
      <section className="bg-white">
        <div className="mx-auto max-w-7xl px-6 py-16">
          <div className="mb-10 flex flex-wrap items-end justify-between gap-4">
            <div>
              <span className="moei-kicker">How can we help today</span>
              <h2 className="mt-2 moei-h-section">Services</h2>
            </div>
            <Link href="/chat" className="moei-btn-primary hidden sm:inline-flex">
              Check application status <ArrowRight size={16} />
            </Link>
          </div>

          <div className="mb-8 flex flex-wrap items-center gap-x-10 gap-y-3 border-b border-moei-line">
            {[
              "Most used services",
              "All Services",
              "My Favourites",
              "Sheikh Zayed Housing Programme",
              "Land Transport",
              "Maritime Transport",
              "Infrastructure",
              "Geological",
            ].map((t, i) => (
              <span
                key={t}
                className={
                  "cursor-pointer border-b-2 pb-3 text-sm font-medium transition-colors " +
                  (i === 0
                    ? "border-moei-bronze text-moei-bronze"
                    : "border-transparent text-moei-muted hover:text-moei-ink")
                }
              >
                {t}
              </span>
            ))}
          </div>

          <div className="mb-8 max-w-md">
            <div className="moei-search">
              <input placeholder="Search by a service keyword" />
              <Search size={18} className="text-moei-bronze" />
              <Mic size={18} className="text-moei-bronze" />
            </div>
          </div>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {SERVICES.map((s) => (
              <Link href={s.href} key={s.title} className="moei-service-card group">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-moei-bronze">
                    {s.category}
                  </span>
                  <Bookmark size={16} className="text-moei-muted group-hover:text-moei-bronze" />
                </div>
                <h3 className="moei-service-title">{s.title}</h3>
                <p className="mt-3 flex-1 text-sm leading-relaxed text-moei-body">{s.desc}</p>
                <span className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-moei-bronze group-hover:text-moei-bronze-dark">
                  Start Service <ArrowRight size={14} />
                </span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* News */}
      <section className="bg-moei-sand">
        <div className="mx-auto max-w-7xl px-6 py-16">
          <div className="mb-8 flex items-end justify-between">
            <div>
              <span className="moei-kicker">Stay in touch</span>
              <h2 className="mt-2 moei-h-section">News</h2>
            </div>
            <Link href="#" className="moei-btn-ghost">
              View all <ArrowRight size={14} />
            </Link>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            {NEWS.map((n) => (
              <article
                key={n.title}
                className="overflow-hidden rounded-xl border border-moei-line bg-white shadow-moei-card transition-all hover:shadow-moei-card-hover"
              >
                <div className="h-44 w-full bg-gradient-to-br from-moei-bronze/20 via-moei-cream to-moei-sand" />
                <div className="p-5">
                  <div className="flex gap-3 text-[11px] uppercase tracking-wider">
                    <span className="text-moei-muted">{n.date}</span>
                    <span className="text-moei-bronze">| {n.tag}</span>
                  </div>
                  <h3 className="mt-2 text-lg font-bold leading-snug text-moei-ink">
                    {n.title}
                  </h3>
                  <p className="mt-2 line-clamp-2 text-sm text-moei-body">{n.body}</p>
                  <Link
                    href="#"
                    className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-moei-bronze hover:underline"
                  >
                    View Details <ArrowRight size={12} />
                  </Link>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* Initiatives */}
      <section className="bg-white">
        <div className="mx-auto max-w-7xl px-6 py-14 text-center">
          <h2 className="text-2xl font-bold text-moei-ink">
            Supportive initiatives of the United Arab Emirates
          </h2>
          <div className="mt-8 grid grid-cols-2 items-center gap-10 opacity-70 md:grid-cols-4">
            {["171 TAWASUL", "UAE LEGISLATION", "ESAAD", "UAE PASS"].map((n) => (
              <div
                key={n}
                className="text-sm font-semibold uppercase tracking-wider text-moei-muted transition-colors hover:text-moei-bronze"
              >
                {n}
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
