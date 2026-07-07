import Link from "next/link";
import { ScoreRing } from "@/components/ScoreRing";
import { FrictionMatrix } from "@/components/FrictionMatrix";
import { Reveal } from "@/components/Reveal";
import type { FrictionMatrix as FrictionMatrixData } from "@/lib/types";

export default function Home() {
  return (
    <div>
      <div
        className="px-10 pt-16 pb-14"
        style={{ background: "linear-gradient(135deg, var(--color-anchor) 0%, var(--color-workshop) 100%)" }}
      >
        <div className="grid gap-10 sm:grid-cols-[1.1fr_0.9fr] sm:items-center">
          <div className="rise">
            <span className="section-label text-on-dark-dim">InclusionScope</span>
            <h1 className="mt-3 font-display text-[40px] leading-tight text-on-dark">
              Accessibility audits that show exactly who gets blocked — and why.
            </h1>
            <div className="signage-rail mt-4 h-[2px] w-16 bg-accent" />
            <p className="mt-4 max-w-md text-[15px] leading-relaxed text-on-dark-dim">
              Real personas run your live app end-to-end, cross-checked against
              axe-core&apos;s WCAG engine — every finding is either machine-verified or
              clearly labeled as a signal, never guessed.
            </p>
            <Link
              href="/projects"
              className="mt-7 inline-block rounded-xl bg-accent px-5 py-2.5 text-[14px] font-medium text-white no-underline transition-opacity hover:opacity-90"
            >
              Show me who&apos;s blocked
            </Link>
          </div>

          <div className="pegboard flex h-[280px] items-center justify-center sm:h-[320px]">
            <div className="mascot-float h-[220px] w-[220px] overflow-hidden rounded-full shadow-2xl sm:h-[260px] sm:w-[260px]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/mascot-hero.png"
                alt="InclusionScope mascot holding a glowing accessibility check"
                className="h-full w-full object-cover"
              />
            </div>
          </div>
        </div>
      </div>

      <PainInsight />
      <ProductProof />
      <ValueStrip />
      <HowItWorks />
      <ClosingCTA />
      <SiteFooter />
    </div>
  );
}

// Pain → stakes: the user's blocked moment, paired with what it costs the SaaS
// owner who can't see it in their own analytics. Numbers are the actual persona
// thresholds this product runs with (personas/elderly_low_literacy.json,
// personas/oku_visual.json) — not invented stats.
function PainInsight() {
  return (
    <div className="border-b border-hairline bg-card px-5 py-12 sm:px-10">
      <span className="section-label">Who gets left behind</span>
      <div className="mt-5 grid gap-8 sm:grid-cols-2">
        <Reveal className="border-l-2 border-blocked pl-5">
          <h2 className="font-display text-[22px] leading-snug text-primary">
            She&apos;s 68. The OTP timer runs out before she finishes reading it.
          </h2>
          <p className="mt-2 text-[14px] leading-relaxed text-secondary">
            Our elderly persona reads at 120 words a minute and gives up after 30
            seconds of ambiguity. Our low-vision persona can&apos;t move past a field
            without AA contrast and a real focus order. These aren&apos;t edge cases —
            they&apos;re two of the users your app already has.
          </p>
          <p className="mt-3 text-[12px] text-tertiary">
            elderly_low_literacy · oku_visual — real persona thresholds, not guesses
          </p>
        </Reveal>
        <Reveal delayMs={40} className="border-l-2 border-accent pl-5">
          <h2 className="font-display text-[22px] leading-snug text-primary">
            Your funnel shows a drop-off. It doesn&apos;t show why.
          </h2>
          <p className="mt-2 text-[14px] leading-relaxed text-secondary">
            A blocked OKU or senior user doesn&apos;t file a ticket — they close the
            tab. Standard analytics can&apos;t tell you if that was a contrast
            failure, a missing label, or a timer that was never built for them. As
            accessibility expectations tighten for consumer and government-facing
            apps, &quot;we didn&apos;t know&quot; stops being a defense.
          </p>
        </Reveal>
      </div>
    </div>
  );
}

// ── Sample data for the "See the report" section ──────────────────────────
// Illustrative only — this is what a run's output looks like, not a claim
// about the visitor's own app (hence the "Sample output" tag below). Persona
// names and disability labels match the real fixtures this product ships
// with (lib/fixtures.ts: p-siti = elderly/first-time digital, p-mei = OKU
// low-vision, p-david = power user) so the shape is representative of an
// actual run, just condensed to a 4-step flow for the page.
const SAMPLE_STEPS = ["landing", "otp", "submit", "success"];
const SAMPLE_PERSONA_NAMES: Record<string, string> = {
  "p-siti": "Siti Nurhaliza",
  "p-mei": "Aunty Mei",
  "p-david": "David Lim",
};
const SAMPLE_SCORE = 0.61;
const SAMPLE_MATRIX: FrictionMatrixData = {
  steps: SAMPLE_STEPS,
  rows: [
    {
      personaId: "p-siti",
      cells: [
        { stepName: "landing", status: "ok", dwellMs: 3200 },
        { stepName: "otp", status: "blocked", dwellMs: null },
        { stepName: "submit", status: "blocked", dwellMs: null },
        { stepName: "success", status: "blocked", dwellMs: null },
      ],
    },
    {
      personaId: "p-mei",
      cells: [
        { stepName: "landing", status: "ok", dwellMs: 4100 },
        { stepName: "otp", status: "friction", dwellMs: 15200 },
        { stepName: "submit", status: "friction", dwellMs: 21800 },
        { stepName: "success", status: "ok", dwellMs: 3600 },
      ],
    },
    {
      personaId: "p-david",
      cells: [
        { stepName: "landing", status: "ok", dwellMs: 1800 },
        { stepName: "otp", status: "ok", dwellMs: 2600 },
        { stepName: "submit", status: "ok", dwellMs: 2200 },
        { stepName: "success", status: "ok", dwellMs: 1500 },
      ],
    },
  ],
};

function ProductProof() {
  return (
    <div className="border-b border-hairline bg-field px-5 py-14 sm:px-10">
      <div className="flex flex-wrap items-center gap-3">
        <span className="section-label">See the report</span>
        <span className="rounded-full bg-card px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-secondary shadow-sm">
          Sample output
        </span>
      </div>
      <h2 className="mt-4 max-w-xl font-display text-[26px] leading-snug text-primary">
        Every run ends here: a score, and a map of exactly who got stuck.
      </h2>
      <p className="mt-2 max-w-xl text-[14px] leading-relaxed text-secondary">
        Below is a sample run, not your data — three personas through a
        four-step sign-up flow. Your first real run will look like this,
        built from your own staging URL.
      </p>

      <Reveal className="card mt-8 flex flex-col items-center gap-5 p-6 text-center sm:flex-row sm:justify-between sm:p-8 sm:text-left">
        <div>
          <span className="section-label">Inclusion score</span>
          <p className="mt-2 max-w-sm text-[13px] leading-relaxed text-secondary">
            1 of 3 sample personas blocked outright — a first-time digital
            user stuck at the OTP step before she can even reach the form.
          </p>
        </div>
        <ScoreRing value={SAMPLE_SCORE} size={128} />
      </Reveal>

      <Reveal delayMs={80}>
        <FrictionMatrix matrix={SAMPLE_MATRIX} personaNames={SAMPLE_PERSONA_NAMES} />
      </Reveal>

      <p className="mt-6 text-[12px] text-tertiary">
        Real personas · axe-core WCAG 2.2 · zero manual scripting
      </p>
    </div>
  );
}

// Slim value strip below the hero — one line each addressing the top three
// buying objections (skepticism about live-run coverage, AI-judged
// compliance, and per-site setup effort).
function ValueStrip() {
  const items: { icon: React.ReactNode; text: string }[] = [
    {
      icon: (
        <>
          <circle cx="12" cy="12" r="9" strokeWidth={2} />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9l5 3-5 3V9z" />
        </>
      ),
      text: "Not a checklist — live personas run your real flow end to end.",
    },
    {
      icon: (
        <>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z"
          />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4" />
        </>
      ),
      text: "axe-core WCAG checks stay separate from AI judgment — never guessed.",
    },
    {
      icon: (
        <>
          <circle cx="12" cy="12" r="9" strokeWidth={2} />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M3 12h18M12 3c2.5 2.5 2.5 15.5 0 18M12 3c-2.5 2.5-2.5 15.5 0 18"
          />
        </>
      ),
      text: "Point at any staging URL — the agent adapts itself, no scripting.",
    },
  ];

  return (
    <div className="border-b border-hairline bg-card px-5 py-14 sm:px-10">
      <span className="section-label">Why it holds up</span>
      <div className="mt-6 grid gap-6 sm:grid-cols-3">
        {items.map((item, i) => (
          <Reveal key={i} delayMs={i * 40} className="card relative overflow-hidden p-6">
            <div className="absolute inset-x-0 top-0 h-[3px] bg-signal" />
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-signal/10 text-signal">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {item.icon}
              </svg>
            </span>
            <p className="mt-4 text-[14px] leading-relaxed text-secondary">{item.text}</p>
          </Reveal>
        ))}
      </div>
    </div>
  );
}

function HowItWorks() {
  const steps = [
    {
      n: "01",
      title: "Point at any staging URL.",
      body: "No scripting, no test IDs to wire up first. Give it a URL and a goal — the agent figures out the rest.",
    },
    {
      n: "02",
      title: "Real personas run the flow, live.",
      body: "Each persona moves through your app at its own pace, cross-checked against axe-core's WCAG engine as it goes.",
    },
    {
      n: "03",
      title: "Get the friction map.",
      body: "An inclusion score, plus a step-by-step breakdown of exactly who got blocked — and why.",
    },
  ];

  return (
    <div className="border-b border-hairline bg-field px-5 py-14 sm:px-10">
      <span className="section-label">How it works</span>
      <div className="mt-6 grid gap-6 sm:grid-cols-3">
        {steps.map((s, i) => (
          <Reveal key={s.n} delayMs={i * 60} className="card p-6">
            <div className="font-display text-[34px] leading-none text-accent">{s.n}</div>
            <h3 className="mt-3 font-display text-[19px] leading-snug text-primary">{s.title}</h3>
            <p className="mt-2 text-[14px] leading-relaxed text-secondary">{s.body}</p>
          </Reveal>
        ))}
      </div>
    </div>
  );
}

// Closing CTA — deliberately mirrors the hero's headline and button copy so
// the page reads as one closed loop, not three unrelated pitches.
function ClosingCTA() {
  return (
    <div
      className="px-5 py-16 text-center sm:px-10"
      style={{ background: "linear-gradient(135deg, var(--color-anchor) 0%, var(--color-workshop) 100%)" }}
    >
      <Reveal className="mx-auto max-w-2xl">
        <span className="section-label text-on-dark-dim">InclusionScope</span>
        <h2 className="mt-3 font-display text-[32px] leading-tight text-on-dark">
          Accessibility audits that show exactly who gets blocked — and why.
        </h2>
        <div className="signage-rail mx-auto mt-4 h-[2px] w-16 bg-accent" />
        <Link
          href="/projects"
          className="mt-7 inline-block rounded-xl bg-accent px-5 py-2.5 text-[14px] font-medium text-white no-underline transition-opacity hover:opacity-90"
        >
          Show me who&apos;s blocked
        </Link>
      </Reveal>
    </div>
  );
}

function SiteFooter() {
  return (
    <footer className="bg-field px-5 py-8 sm:px-10">
      <div className="flex flex-col items-center gap-4 text-center sm:flex-row sm:justify-between sm:text-left">
        <nav className="flex gap-5 text-[13px] text-secondary">
          <Link href="/" className="hover:text-primary">
            Home
          </Link>
          <Link href="/projects" className="hover:text-primary">
            Projects
          </Link>
          <Link href="/personas" className="hover:text-primary">
            Personas
          </Link>
        </nav>
        <p className="text-[12px] text-tertiary">InclusionScope — NexHack 2026</p>
      </div>
    </footer>
  );
}
