import SVGLogo from "@/components/ui/SVGLogo";
import type { Metadata } from "next";

export const metadata: Metadata = {
  description: "Browse Formula 1 seasons, rounds, and session results.",
};

export default function Home() {

  return (
    <div className="min-h-full p-12 flex flex-col items-center">
      <div className="w-full max-w-lg">
        <SVGLogo />
      </div>
    </div>
  );
}
