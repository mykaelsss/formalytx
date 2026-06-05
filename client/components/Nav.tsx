import Link from "next/link";
import SVGLogo from "@/components/ui/SVGLogo";

export default function Nav() {
  return (
    <nav className="border-b border-surface-border bg-surface-card">
      <div className="flex items-center px-4 py-3 sm:px-6 lg:px-8">
        <Link href="/" aria-label="Formalytx home" className="text-text-primary">
          <SVGLogo height={36} width={104} />
        </Link>
      </div>
    </nav>
  );
}
