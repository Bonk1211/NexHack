import type { Metadata } from "next";
import { Instrument_Serif } from "next/font/google";
import { GeistSans } from "geist/font/sans";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

const instrument = Instrument_Serif({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-instrument",
  display: "swap",
});

export const metadata: Metadata = {
  title: "InclusionScope",
  description: "Audit every user. Before they leave.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${instrument.variable}`}>
      <body>
        <div className="grain-overlay" aria-hidden />
        <div className="relative z-10 min-h-screen">
          <Sidebar />
          {/* Sidebar is fixed (240px) and only visible at md+; margin-left clears it
              there. Below md the rail is an off-canvas drawer instead, so margin is 0
              and pt-14 clears the mobile top bar (h-14) rendered by Sidebar. No flex-1 —
              that would make main 100vw wide and the margin would then overflow
              horizontally. */}
          <main className="ml-0 min-w-0 pt-14 md:ml-[240px] md:pt-0">{children}</main>
        </div>
      </body>
    </html>
  );
}
