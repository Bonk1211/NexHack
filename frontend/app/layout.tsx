import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "InclusionScope",
  description: "Inclusion & accessibility assurance — persona wall + empathy replay",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
