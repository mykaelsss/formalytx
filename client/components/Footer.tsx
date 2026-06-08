import Link from "next/link";

export default function Footer() {
  return (
    <footer className="mt-auto border-t border-surface-border bg-surface-card">
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <p className="text-center text-xs leading-relaxed text-text-muted">
          This is an unofficial fan project and is not affiliated with, endorsed by, sponsored by,
          or connected to Formula 1, the FIA, or any Formula 1 team, driver, or official entity.
          All data is sourced from publicly available APIs for informational and educational purposes
          only. Formula 1, F1, the F1 logo, Formula One, and all related names, marks, emblems, and
          images are proprietary trademarks of Formula One Licensing B.V. and/or the FIA. Use of
          these marks is not intended to imply any affiliation or endorsement. No commercial
          relationship is claimed or implied.
        </p>
        <p className="mt-4 text-center text-xs text-text-muted">
          <Link
            href="/privacy"
            className="underline underline-offset-4 hover:text-text-secondary transition-colors"
          >
            Privacy Policy
          </Link>
        </p>
      </div>
    </footer>
  );
}
