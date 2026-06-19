"use client";

import { useState } from "react";
import type { PersonaResult, Severity } from "@/lib/types";

const STATUS_DOT: Record<Severity, string> = {
  ok: "#1d8a4e",
  friction: "#b25e00",
  blocked: "#c8362f",
};

const STATUS_LABEL: Record<Severity, string> = {
  ok: "Pass",
  friction: "Friction",
  blocked: "Blocked",
};

export function RunLog({ results }: { results: PersonaResult[] }) {
  const totalSteps = results.reduce((sum, r) => sum + r.steps.length, 0);
  const blockedCount = results.filter((r) => r.status === "blocked").length;

  return (
    <section className="mt-14">
      <div className="flex items-baseline justify-between">
        <h2 className="section-label">Run log</h2>
        <span className="text-[13px] text-secondary">
          {results.length} personas · {blockedCount} blocked · {totalSteps} steps recorded
        </span>
      </div>

      <div className="mt-5 space-y-3">
        {results.map((r, i) => (
          <PersonaGroup key={r.personaId} result={r} defaultOpen={i < 3} />
        ))}
      </div>
    </section>
  );
}

function PersonaGroup({ result, defaultOpen }: { result: PersonaResult; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-4 p-4 text-left transition-colors hover:bg-field"
      >
        <div className="h-9 w-9 shrink-0 overflow-hidden rounded-full bg-field">
          {result.persona.figurineUrl && (
            <img src={result.persona.figurineUrl} alt={result.persona.identity.name} className="h-9 w-9 rounded-full object-cover" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-display text-[16px] text-primary">{result.persona.identity.name}</span>
            <span
              className="inline-block h-[6px] w-[6px] rounded-full"
              style={{ background: STATUS_DOT[result.status] }}
            />
          </div>
          <div className="text-[12px] text-tertiary">{result.persona.identity.label}</div>
        </div>
        <div className="flex items-center gap-4 text-[12px]">
          <span className="text-secondary">
            Confusion: <span className="font-medium tabular-nums text-primary">{(result.confusionScore * 100).toFixed(0)}%</span>
          </span>
          <span className="text-tertiary">{result.steps.length} steps</span>
          <span className={`text-[16px] transition-transform duration-200 ${open ? "rotate-180" : ""}`}>
            ↓
          </span>
        </div>
      </button>

      {open && (
        <div className="border-t border-hairline">
          {result.steps.map((step, si) => (
            <StepRow key={step.stepName} step={step} isLast={si === result.steps.length - 1} />
          ))}
        </div>
      )}
    </div>
  );
}

function StepRow({
  step,
  isLast,
}: {
  step: { stepName: string; status: Severity; dwellMs: number; innerMonologue: string; confusionLevel: number; understandability: number };
  isLast: boolean;
}) {
  const isBlocked = step.status === "blocked";

  return (
    <div
      className={`px-5 py-3.5 ${!isLast ? "border-b border-hairline" : ""} ${
        isBlocked ? "bg-tint-blocked border-l-[3px] border-l-blocked" : ""
      }`}
    >
      <div className="flex items-center gap-4">
        <span className="w-[100px] shrink-0 text-[14px] font-medium text-primary">{step.stepName}</span>

        <span className="inline-flex items-center gap-1.5 text-[12px]">
          <span className="h-[6px] w-[6px] rounded-full" style={{ background: STATUS_DOT[step.status] }} />
          <span style={{ color: STATUS_DOT[step.status] }}>{STATUS_LABEL[step.status]}</span>
        </span>

        <span className="text-[12px] tabular-nums text-tertiary">
          {(step.dwellMs / 1000).toFixed(1)}s
        </span>

        <span className="text-[11px] tabular-nums text-tertiary" title="Understandability">
          U: {step.understandability.toFixed(2)}
        </span>

        <span className="text-[11px] tabular-nums text-tertiary" title="Confusion level">
          C: {step.confusionLevel.toFixed(2)}
        </span>

        <span className="text-[12px] text-tertiary">—</span>
      </div>

      {step.innerMonologue && (
        <p className={`mt-1.5 text-[13px] leading-relaxed ${isBlocked ? "font-medium text-blocked" : "italic text-secondary"}`}>
          &ldquo;{step.innerMonologue}&rdquo;
        </p>
      )}
    </div>
  );
}
