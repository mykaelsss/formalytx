import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description:
    "How Formalytx uses anonymized analytics and Google AdSense advertising, and how to control ad personalization.",
};

const LAST_UPDATED = "October 12, 2026";

function ExternalLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-accent-green underline underline-offset-4"
    >
      {children}
    </a>
  );
}

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
            Formalytx is an unofficial fan project supported by advertising.
            This policy explains what data is collected when you visit the site,
            who collects it, and how you can control it.
          </p>
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold text-text-primary">Analytics</h2>
          <p>
            We use{" "}
            <span className="text-text-primary">Vercel Web Analytics</span> and{" "}
            <span className="text-text-primary">Vercel Speed Insights</span> to
            understand aggregate usage and performance. This collects anonymized
            information such as the pages visited, referring site, approximate
            location (country/region), device type, and browser. Analytics do
            not use cookies, are not used for advertising, and are used only to
            understand how the site is used and to improve performance.
          </p>
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold text-text-primary">Advertising</h2>
          <p>
            We show ads served by{" "}
            <span className="text-text-primary">Google AdSense</span>. Third-party
            vendors, including Google, use cookies to serve ads based on your
            prior visits to this website or other websites. Google&apos;s use of
            advertising cookies enables it and its partners to serve ads to you
            based on your visits to this site and/or other sites on the
            Internet.
          </p>
          <p>
            Google and its partners may also use cookies, device identifiers,
            and your IP address to measure ad performance, limit how often you
            see an ad, and detect fraud and abuse. This data is collected by
            Google directly from your browser and is not shared with us in a
            form that identifies you. You can learn more in{" "}
            <ExternalLink href="https://policies.google.com/technologies/partner-sites">
              How Google uses information from sites or apps that use its
              services
            </ExternalLink>
            .
          </p>
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold text-text-primary">
            Your choices
          </h2>
          <ul className="flex list-disc flex-col gap-2 pl-5">
            <li>
              If you are in the European Economic Area, the United Kingdom, or
              Switzerland, you will be asked for consent before personalized
              ads are shown. You can decline and still use the site, and you
              can change your choice at any time through the privacy settings
              link provided by the consent message.
            </li>
            <li>
              You can opt out of personalized advertising from Google in{" "}
              <ExternalLink href="https://adssettings.google.com">
                Google Ads Settings
              </ExternalLink>
              .
            </li>
            <li>
              You can opt out of personalized advertising from other
              participating vendors at{" "}
              <ExternalLink href="https://optout.aboutads.info">
                aboutads.info
              </ExternalLink>{" "}
              or, in Europe,{" "}
              <ExternalLink href="https://www.youronlinechoices.eu">
                youronlinechoices.eu
              </ExternalLink>
              .
            </li>
            <li>
              You can block or delete cookies in your browser settings. Ads may
              still appear, but they will not be personalized.
            </li>
          </ul>
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold text-text-primary">
            What we don&apos;t do
          </h2>
          <ul className="flex list-disc flex-col gap-2 pl-5">
            <li>
              Formalytx itself does not set cookies or require an account. The
              only cookies are set by Google for advertising, as described
              above.
            </li>
            <li>
              We do not store your IP address. Vercel derives a temporary,
              anonymized identifier for analytics and discards the raw IP.
            </li>
            <li>
              We do not sell or rent any data we collect, and we do not share
              our analytics data with advertisers.
            </li>
          </ul>
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold text-text-primary">
            Data processing
          </h2>
          <p>
            Analytics data is processed on our behalf by Vercel Inc. as a data
            processor. You can read more in{" "}
            <ExternalLink href="https://vercel.com/docs/analytics/privacy-policy">
              Vercel&apos;s analytics privacy documentation
            </ExternalLink>
            .
          </p>
          <p>
            Advertising data is collected and processed by Google under its own
            responsibility, as described in the{" "}
            <ExternalLink href="https://policies.google.com/privacy">
              Google Privacy Policy
            </ExternalLink>
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
            Our analytics are anonymized and not tied to an identifiable person,
            so we typically hold no data that can be linked back to you.
            Advertising data is held by Google, and you can manage or delete it
            through your Google account and the options listed above. If you
            have questions, contact us below.
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
