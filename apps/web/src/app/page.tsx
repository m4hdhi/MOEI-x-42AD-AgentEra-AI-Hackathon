"use client";

import Link from "next/link";
import {
  ArrowRight,
  Bookmark,
  Phone,
  Smartphone,
  Search,
  Mic,
  Clock,
  Languages,
  ShieldCheck,
} from "lucide-react";
import { SmartSearch } from "@/components/SmartSearch";
import { WhatsAppTryCard } from "@/components/WhatsAppTryCard";
import { useLang } from "@/lib/i18n";

export default function HomePage() {
  const { t } = useLang();

  const SERVICES = [
    {
      title: t("Sheikh Zayed Housing Programme", "برنامج الشيخ زايد للإسكان"),
      desc: t(
        "Check loan eligibility, request rescheduling, or submit hardship documents.",
        "تحقّق من أهلية القرض، اطلب إعادة الجدولة، أو قدّم مستندات الحالة الإنسانية.",
      ),
      href: "/chat",
      category: t("Housing", "الإسكان"),
    },
    {
      title: t("Application Status", "حالة الطلب"),
      desc: t(
        "Track any active request across housing, transport, maritime, and infrastructure.",
        "تابع أي طلب نشِط في خدمات الإسكان والنقل والبحرية والبنية التحتية.",
      ),
      href: "/chat",
      category: t("All sectors", "كل القطاعات"),
    },
    {
      title: t("Document Submission", "تقديم المستندات"),
      desc: t(
        "Upload salary slips, bank statements, or Emirates ID securely from any device.",
        "ارفع قسائم الراتب أو كشوف الحساب أو الهوية الإماراتية بأمان من أي جهاز.",
      ),
      href: "/chat",
      category: t("All sectors", "كل القطاعات"),
    },
    {
      title: t("Call Centre", "مركز الاتصال"),
      desc: t(
        "Talk to the MOEI Smart Assistant in Arabic or English. No queue, no wait.",
        "تحدّث إلى المساعد الذكي للوزارة بالعربية أو الإنجليزية. دون طابور ودون انتظار.",
      ),
      href: "/call",
      category: t("Contact", "تواصل"),
    },
    {
      title: t("Energy Services", "خدمات الطاقة"),
      desc: t(
        "Tariff information, billing questions, and outage reporting across the federation.",
        "معلومات التعرفة، استفسارات الفواتير، والإبلاغ عن الانقطاعات على مستوى الاتحاد.",
      ),
      href: "/chat",
      category: t("Energy", "الطاقة"),
    },
    {
      title: t("Maritime Permits", "التصاريح البحرية"),
      desc: t(
        "Vessel registration, port enquiries, and seafarer certificates.",
        "تسجيل السفن، استفسارات الموانئ، وشهادات البحّارة.",
      ),
      href: "/chat",
      category: t("Maritime", "البحرية"),
    },
    {
      title: t("Transport Permits", "تصاريح النقل"),
      desc: t(
        "Federal driver and vehicle services, and national transportation enquiries.",
        "خدمات السائقين والمركبات الاتحادية، واستفسارات النقل الوطني.",
      ),
      href: "/chat",
      category: t("Transport", "النقل"),
    },
    {
      title: t("Infrastructure Enquiries", "استفسارات البنية التحتية"),
      desc: t(
        "Roads, public works, and federal construction information.",
        "الطرق والأشغال العامة ومعلومات البناء الاتحادي.",
      ),
      href: "/chat",
      category: t("Infrastructure", "البنية التحتية"),
    },
  ];

  const PROMISE = [
    {
      icon: Clock,
      label: t("Available 24/7", "متاح على مدار الساعة"),
      note: t("Every day, including weekends.", "كل يوم، بما في ذلك عطلة نهاية الأسبوع."),
    },
    {
      icon: Languages,
      label: t("Arabic & English", "العربية والإنجليزية"),
      note: t(
        "Reply in the language you write or speak.",
        "نردّ بنفس اللغة التي تكتب أو تتحدث بها.",
      ),
    },
    {
      icon: Smartphone,
      label: t("No app to install", "لا حاجة لتثبيت تطبيق"),
      note: t("Works in your browser and on WhatsApp.", "يعمل في متصفحك وعلى واتساب."),
    },
    {
      icon: ShieldCheck,
      label: t("Secure & official", "آمن ورسمي"),
      note: t(
        "Sign in with UAE PASS for personalised help.",
        "سجّل الدخول عبر الهوية الرقمية للحصول على مساعدة مخصصة.",
      ),
    },
  ];

  const NEWS = [
    {
      date: t("23 May 2026", "٢٣ مايو ٢٠٢٦"),
      tag: t("Customer Happiness", "سعادة المتعاملين"),
      title: t(
        "MOEI Smart Assistant now answers in Arabic and English on every channel",
        "المساعد الذكي للوزارة يجيب الآن بالعربية والإنجليزية على كل القنوات",
      ),
      body: t(
        "Citizens can start a conversation on WhatsApp and continue on the website or call centre without repeating themselves.",
        "يمكن للمتعاملين بدء محادثة على واتساب ومتابعتها على الموقع أو مركز الاتصال دون تكرار ما قالوه.",
      ),
    },
    {
      date: t("13 May 2026", "١٣ مايو ٢٠٢٦"),
      tag: t("Sheikh Zayed Housing Programme", "برنامج الشيخ زايد للإسكان"),
      title: t(
        "Sheikh Zayed Housing Programme completes handover of Al Suyoh phase 16",
        "برنامج الشيخ زايد للإسكان يكمل تسليم المرحلة 16 من مشروع السيوح",
      ),
      body: t(
        "Eligible families receive their keys ahead of schedule, with on-site customer happiness officers available throughout.",
        "تتسلّم الأسر المستحقة مفاتيحها قبل الموعد، مع توفّر موظفي سعادة المتعاملين في الموقع طوال الوقت.",
      ),
    },
    {
      date: t("11 May 2026", "١١ مايو ٢٠٢٦"),
      tag: t("Ministry News", "أخبار الوزارة"),
      title: t(
        "MOEI hosts national forum on the future of federal customer service",
        "الوزارة تستضيف منتدى وطنيًا حول مستقبل خدمة المتعاملين الاتحادية",
      ),
      body: t(
        "Government leaders discussed how the ministry continues to raise standards of service quality and accessibility.",
        "ناقش قادة الحكومة كيف تواصل الوزارة رفع معايير جودة الخدمة وسهولة الوصول إليها.",
      ),
    },
  ];

  const SERVICE_TABS = [
    t("Most used services", "الخدمات الأكثر استخدامًا"),
    t("All Services", "جميع الخدمات"),
    t("My Favourites", "المفضلة"),
    t("Sheikh Zayed Housing Programme", "برنامج الشيخ زايد للإسكان"),
    t("Land Transport", "النقل البري"),
    t("Maritime Transport", "النقل البحري"),
    t("Infrastructure", "البنية التحتية"),
    t("Geological", "المسح الجيولوجي"),
  ];

  const INITIATIVES = [
    t("171 TAWASUL", "تواصل 171"),
    t("UAE LEGISLATION", "التشريعات الإماراتية"),
    t("ESAAD", "إسعاد"),
    t("UAE PASS", "الهوية الرقمية"),
  ];

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
              {t("Ministry of Energy and Infrastructure", "وزارة الطاقة والبنية التحتية")}
            </span>
            <h1 className="mt-4 moei-h-display">
              {t("Your ministry,", "وزارتك،")}
              <br />
              <span className="text-moei-bronze">{t("always answering.", "مُجيبة دائمًا.")}</span>
            </h1>
            <p className="mt-6 max-w-xl text-base leading-relaxed text-moei-body md:text-lg">
              {t(
                "Ask about housing, energy, transport, maritime, or infrastructure services any time of day. Get clear answers in Arabic or English, file a request, or speak to a person when you need one.",
                "اسأل عن خدمات الإسكان أو الطاقة أو النقل أو البحرية أو البنية التحتية في أي وقت من اليوم. احصل على إجابات واضحة بالعربية أو الإنجليزية، قدّم طلبًا، أو تحدّث إلى موظف عند الحاجة.",
              )}
            </p>
            <div className="mt-8">
              <SmartSearch />
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/chat" className="moei-btn-primary">
                {t("Start a conversation", "ابدأ محادثة")} <ArrowRight size={16} />
              </Link>
              <Link href="/call" className="moei-btn-ghost">
                {t("Call us instead", "اتصل بنا بدلاً من ذلك")} <Phone size={14} />
              </Link>
            </div>
          </div>

          <div className="lg:col-span-5">
            <div className="moei-card p-6">
              <div className="moei-kicker">{t("Our promise", "وعدنا")}</div>
              <h3 className="mt-2 text-2xl font-bold text-moei-ink">
                {t("Service that meets you where you are", "خدمة تصل إليك أينما كنت")}
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
                {t(
                  "Call centre 800 6634 · WhatsApp · moei.gov.ae · MOEI mobile app",
                  "مركز الاتصال 800 6634 · واتساب · moei.gov.ae · تطبيق الوزارة",
                )}
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
              <span className="moei-kicker">{t("How can we help today", "كيف يمكننا مساعدتك اليوم")}</span>
              <h2 className="mt-2 moei-h-section">{t("Services", "الخدمات")}</h2>
            </div>
            <Link href="/chat" className="moei-btn-primary hidden sm:inline-flex">
              {t("Check application status", "تابع حالة الطلب")} <ArrowRight size={16} />
            </Link>
          </div>

          <div className="mb-8 flex flex-wrap items-center gap-x-10 gap-y-3 border-b border-moei-line">
            {SERVICE_TABS.map((tab, i) => (
              <span
                key={tab}
                className={
                  "cursor-pointer border-b-2 pb-3 text-sm font-medium transition-colors " +
                  (i === 0
                    ? "border-moei-bronze text-moei-bronze"
                    : "border-transparent text-moei-muted hover:text-moei-ink")
                }
              >
                {tab}
              </span>
            ))}
          </div>

          <div className="mb-8 max-w-md">
            <div className="moei-search">
              <input placeholder={t("Search by a service keyword", "ابحث بكلمة مفتاحية للخدمة")} />
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
                  {t("Start Service", "ابدأ الخدمة")} <ArrowRight size={14} />
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
              <span className="moei-kicker">{t("Stay in touch", "ابقَ على تواصل")}</span>
              <h2 className="mt-2 moei-h-section">{t("News", "الأخبار")}</h2>
            </div>
            <Link href="#" className="moei-btn-ghost">
              {t("View all", "عرض الكل")} <ArrowRight size={14} />
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
                    {t("View Details", "عرض التفاصيل")} <ArrowRight size={12} />
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
            {t(
              "Supportive initiatives of the United Arab Emirates",
              "مبادرات داعمة لدولة الإمارات العربية المتحدة",
            )}
          </h2>
          <div className="mt-8 grid grid-cols-2 items-center gap-10 opacity-70 md:grid-cols-4">
            {INITIATIVES.map((n) => (
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
