"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { QuotaBadge } from "@/components/QuotaBadge";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/projects", label: "Projects" },
  { href: "/personas", label: "Personas" },
];

/* Brand mark — scan ring + checkmark, same geometry as frontend/app/icon.svg and
   the icon half of public/inclusionscope-logo.svg. Fixed brand colors, not
   currentColor, since it's designed against the sidebar's dark background. */
function ScopeMark() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 180 180"
      fill="none"
      aria-hidden="true"
      className="shrink-0"
    >
      <circle cx="90" cy="90" r="64" fill="none" stroke="#d97a2b" strokeWidth="16"
        strokeLinecap="round" strokeDasharray="330 72.2" transform="rotate(-38 90 90)" />
      <circle cx="90" cy="90" r="64" fill="none" stroke="#2f8fe0" strokeWidth="16"
        strokeLinecap="round" strokeDasharray="26 376.2" transform="rotate(242 90 90)" />
      <path d="M 66 92 L 82 108 L 116 72" fill="none" stroke="#f5f5f7" strokeWidth="10"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function HamburgerIcon({ open }: { open: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      {open ? (
        <path
          d="M5 5L15 15M15 5L5 15"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
      ) : (
        <path
          d="M3 6H17M3 10H17M3 14H17"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
      )}
    </svg>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  return (
    <>
      {/* Mobile top bar — only below md, since the rail itself is hidden there. */}
      <div className="fixed left-0 top-0 z-40 flex h-14 w-full items-center gap-3 bg-anchor px-4 md:hidden">
        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="-ml-1.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-on-dark transition-colors hover:bg-white/[0.08]"
        >
          <HamburgerIcon open={open} />
        </button>
        <Link href="/" onClick={close} className="flex items-center gap-2 no-underline">
          <ScopeMark />
          <span className="font-display text-[18px] text-on-dark">InclusionScope</span>
        </Link>
      </div>

      {/* Backdrop — closes the drawer on click/tap, mobile only. */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/30 backdrop-blur-sm md:hidden"
          onClick={close}
          aria-hidden="true"
        />
      )}

      {/* Rail on md+, off-canvas drawer below md. */}
      <aside
        className={`fixed left-0 top-0 z-40 flex h-screen w-[240px] flex-col bg-anchor transition-transform duration-300 ease-out md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center gap-2 px-6 pt-7 pb-8">
          <ScopeMark />
          <Link href="/" onClick={close} className="font-display text-[22px] text-on-dark no-underline">
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
                onClick={close}
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

        <div className="px-3 pb-3">
          <Link
            href="/projects"
            onClick={close}
            className="flex items-center justify-center gap-1.5 rounded-lg bg-accent px-3 py-2 text-[13px] font-medium text-white no-underline transition-opacity hover:opacity-90"
          >
            <span aria-hidden="true">+</span> New project
          </Link>
        </div>

        <div className="px-6 pb-6">
          <QuotaBadge compact />
        </div>
      </aside>
    </>
  );
}
