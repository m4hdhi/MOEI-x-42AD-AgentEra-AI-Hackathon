import Link from "next/link";

export function MoeiFooter() {
  return (
    <footer className="mt-20 border-t border-moei-line bg-white">
      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-5">
          <Column
            title="About the Ministry"
            links={[
              ["Vision and mission", "https://www.moei.gov.ae/en/about-ministry"],
              ["Leadership", "https://www.moei.gov.ae/en/about-ministry"],
              ["Strategic plan", "https://www.moei.gov.ae/en/about-ministry"],
              ["Annual reports", "https://www.moei.gov.ae/en/about-ministry"],
            ]}
          />
          <Column
            title="Information and support"
            links={[
              ["Frequently asked questions", "#"],
              ["Sheikh Zayed Housing Programme", "https://www.moei.gov.ae"],
              ["Customer Happiness Centre", "#"],
              ["171 Tawasul", "#"],
            ]}
          />
          <Column
            title="For citizens"
            links={[
              ["Chat", "/chat"],
              ["Mobile app", "/mobile"],
              ["Call centre", "/call"],
              ["UAE PASS", "#"],
            ]}
          />
          <Column
            title="For MOEI staff"
            links={[
              ["Staff sign-in", "/admin/login"],
            ]}
          />
          <div>
            <h4 className="mb-3 text-sm font-semibold uppercase tracking-wider text-moei-ink">
              Toll free
            </h4>
            <p className="text-xl font-bold text-moei-bronze">800 6634</p>
            <p className="mt-1 text-xs text-moei-muted">+971 (0) 9 718 0066 34</p>
            <p className="mt-4 text-[11px] text-moei-muted">
              Customer Happiness Centre, available 24 hours a day, 7 days a week.
            </p>
          </div>
        </div>

        <div className="mt-10 flex flex-col gap-3 border-t border-moei-line pt-6 text-xs text-moei-muted sm:flex-row sm:items-center sm:justify-between">
          <p>
            © {new Date().getFullYear()} Ministry of Energy and Infrastructure, United Arab Emirates.
          </p>
          <p>
            خدمة حكومة الإمارات بذكاء يستحقه المواطن
          </p>
        </div>
      </div>
    </footer>
  );
}

function Column({ title, links }: { title: string; links: [string, string][] }) {
  return (
    <div>
      <h4 className="mb-3 text-sm font-semibold uppercase tracking-wider text-moei-ink">
        {title}
      </h4>
      <ul className="space-y-2 text-sm">
        {links.map(([label, href]) => (
          <li key={label}>
            <Link href={href} className="text-moei-body transition hover:text-moei-bronze">
              {label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
