// Scroll-triggered version of the `.rise` entrance used across this app.
// `.rise` (globals.css) only ever fired once, on mount — fine for
// above-the-fold content, but anything further down the page had already
// "animated in" before a visitor scrolled to it. This wraps a block in an
// IntersectionObserver and applies the exact same `.rise` class (so it's
// still neutralized by the prefers-reduced-motion block in globals.css)
// only once the element actually enters the viewport.
"use client";

import { useEffect, useRef, useState } from "react";

export function Reveal({
  children,
  className = "",
  delayMs = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delayMs?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.15, rootMargin: "0px 0px -60px 0px" }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={`${visible ? "rise" : "opacity-0"} ${className}`}
      style={visible ? { animationDelay: `${delayMs}ms` } : undefined}
    >
      {children}
    </div>
  );
}
