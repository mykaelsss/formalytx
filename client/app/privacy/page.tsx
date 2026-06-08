import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "How Formalytx collects and uses anonymized usage analytics.",
};

const LAST_UPDATED = "June 7, 2026";

export default function PrivacyPage() {
  return (
    <main className="mx-auto w-full max-w-3xl px-5 py-16">
      <h1 className="text-3xl font-bold tracking-tight text-text-primary">
        Privacy Policy
      </h1>
      <p className="mt-2 text-xs font-mono uppercase tracking-[0.2em] text-text-muted">
        Last updated {LAST_UPDATED}
      </p>

      <div className="mt-10 flex flex-col gap-8 text-sm leading-relaxed text-text-secondary">
        <section className="flex flex-col gap-3">
          <p>
            Formalytx is an unofficial, non-commercial fan project. This policy
            explains what limited data is collected when you visit the site and
            how it is used.
          </p>
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold text-text-primary">
            What we collect
          </h2>
          <p>
            We use{" "}
            <span className="text-text-primary">Vercel Web Analytics</span> and{" "}
            <span className="text-text-primary">Vercel Speed Insights</span> to
            understand aggregate usage and performance. This collects anonymized
            information such as the pages visited, referring site, approximate
            location (country/region), device type, and browser. It is used only
            to understand how the site is used and to improve performance.
          </p>
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold text-text-primary">
            What we don&apos;t do
          </h2>
          <ul className="flex list-disc flex-col gap-2 pl-5">
            <li>
              We do not set tracking or advertising{" "}
              <span className="text-text-primary">cookies</span>, and there is no
              cookie consent banner because none are used.
            </li>
            <li>
              We do not build personal profiles or track you across other
              websites.
            </li>
            <li>
              We do not store your IP address. Vercel derives a temporary,
              anonymized identifier and discards the raw IP.
            </li>
            <li>We do not sell, rent, or share your data with advertisers.</li>
          </ul>
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold text-text-primary">
            Data processing
          </h2>
          <p>
            Analytics data is processed on our behalf by Vercel Inc. as a data
            processor. You can read more in{" "}
            <a
              href="https://vercel.com/docs/analytics/privacy-policy"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-green underline underline-offset-4"
            >
              Vercel&apos;s analytics privacy documentation
            </a>
            .
          </p>
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold text-text-primary">
            Your rights
          </h2>
          <p>
            Depending on where you live (for example under GDPR or CCPA), you may
            have rights to access, correct, or request deletion of personal data.
            Because the analytics described here are anonymized and not tied to
            an identifiable person, we typically hold no data that can be linked
            back to you. If you have questions, contact us below.
          </p>
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold text-text-primary">Contact</h2>
          <p>
            Questions about this policy can be sent to{" "}
            <a
              href="mailto:formalytx.privacy@gmail.com"
              className="text-accent-green underline underline-offset-4"
            >
              formalytx.privacy@gmail.com
            </a>
            .
          </p>
        </section>
      </div>
    </main>
  );
}
