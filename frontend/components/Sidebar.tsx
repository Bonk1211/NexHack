"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/personas", label: "Personas" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-[240px] flex-col bg-anchor">
      <div className="px-6 pt-7 pb-8">
        <Link href="/" className="font-display text-[22px] text-on-dark no-underline">
          InclusionScope
        </Link>
      </div>

      <nav className="flex-1 px-3">
        {NAV.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`mb-0.5 flex items-center rounded-lg px-3 py-2 text-[14px] no-underline transition-colors duration-200 ${
                active
                  ? "bg-white/[0.08] text-on-dark font-medium"
                  : "text-on-dark-dim hover:text-on-dark hover:bg-white/[0.04]"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="px-6 pb-6">
        <span className="text-[11px] text-tertiary">v0.1.0</span>
      </div>
    </aside>
  );
}
