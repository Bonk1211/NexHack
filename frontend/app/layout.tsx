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
        <div className="relative z-10 flex min-h-screen">
          <Sidebar />
          <main className="ml-[240px] flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
