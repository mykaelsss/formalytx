import type { Metadata } from "next";
import "./globals.css";
import { cn } from "@/lib/utils";
import { Exo_2, Roboto_Mono } from "next/font/google";
import { Toaster } from "@/components/ui/sonner"
import Providers from './providers'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { TooltipProvider } from "@/components/ui/tooltip"
import Footer from "@/components/Footer"

  const exo2 = Exo_2({
    subsets: ['latin'],
    variable: '--font-exo2',
  });

  const robotoMono = Roboto_Mono({
    subsets: ['latin'],
    variable: '--font-roboto-mono',
  });

export const metadata: Metadata = {
  title: {
    default: "Formalytx",
    template: "%s · Formalytx",
  },
  description: "Explore Formula 1 session results, lap times, and car telemetry.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={cn("h-full", "antialiased", exo2.variable, robotoMono.variable)}
    >
      <body className="bg-background min-h-full flex flex-col">
        <Providers>
          <TooltipProvider>
            {children}
          </TooltipProvider>
          <Toaster 
          position="bottom-right" 
          toastOptions={{
          classNames: {
              toast: "bg-surface-card! text-text-primary! border-accent-green-dark!",
              closeButton: "hover:bg-[var(--gray1)]! hover:border-[var(--gray4)]!"
            },
          }} 
          />
          <Footer />
          <ReactQueryDevtools />
        </Providers>
      </body>
    </html>
  );
}
