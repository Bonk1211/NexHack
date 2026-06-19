"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { subscribeToRun, FLOW_STEPS } from "@/lib/sse";
import { getPersonas } from "@/lib/api";
import type { Persona, RunEvent, Severity } from "@/lib/types";
import { scorePct } from "@/lib/format";

interface LaneState {
  personaId: string;
  steps: { stepName: string; status: Severity | "pending"; dwellMs: number | null }[];
  activeStep: number;
  confusionScore: number;
  confusionLevel: number;
  innerMonologue: string;
  done: boolean;
  blocked: boolean;
  blockedAt?: string;
  completed: boolean;
}

function laneAccentColor(confusionLevel: number): string {
  if (confusionLevel >= 0.7) return "#c8362f";
  if (confusionLevel >= 0.35) return "#b25e00";
  return "#1d8a4e";
}

function laneBgClass(confusionLevel: number, blocked: boolean): string {
  if (blocked) return "bg-tint-blocked";
  if (confusionLevel >= 0.5) return "bg-[#fef9f5]";
  return "bg-card";
}

export default function LiveRunPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const runId = params.runId as string;

  const [personas, setPersonas] = useState<Persona[]>([]);
  const [lanes, setLanes] = useState<LaneState[]>([]);
  const [overallScore, setOverallScore] = useState<number | null>(null);
  const [done, setDone] = useState(false);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    getPersonas().then((p) => {
      setPersonas(p);
      const initial: LaneState[] = p.map((persona) => ({
        personaId: persona.id,
        steps: FLOW_STEPS.map((stepName) => ({ stepName, status: "pending" as const, dwellMs: null })),
        activeStep: -1,
        confusionScore: 0,
        confusionLevel: 0,
        innerMonologue: "",
        done: false,
        blocked: false,
        completed: false,
      }));
      setLanes(initial);
    });
  }, []);

  const handleEvent = useCallback((event: RunEvent) => {
    if (event.type === "persona_step") {
      setLanes((prev) =>
        prev.map((lane) => {
          if (lane.personaId !== event.personaId) return lane;
          const steps = [...lane.steps];
          steps[event.stepIdx] = {
            stepName: event.stepName,
            status: event.status,
            dwellMs: event.dwellMs,
          };
          return {
            ...lane,
            steps,
            activeStep: event.stepIdx,
            confusionScore: event.confusionScore,
            confusionLevel: event.confusionLevel,
            innerMonologue: event.innerMonologue,
          };
        }),
      );
    } else if (event.type === "persona_done") {
      setLanes((prev) =>
        prev.map((lane) => {
          if (lane.personaId !== event.personaId) return lane;
          return {
            ...lane,
            done: true,
            completed: event.completed,
            blocked: !event.completed,
            blockedAt: event.blockedAt,
            confusionScore: event.confusionScore,
          };
        }),
      );
    } else if (event.type === "run_done") {
      setOverallScore(event.overallScore);
      setDone(true);
    }
  }, []);

  useEffect(() => {
    if (lanes.length === 0 || started) return;
    setStarted(true);
    const unsubscribe = subscribeToRun(runId, handleEvent, () => {});
    return unsubscribe;
  }, [lanes.length, started, runId, handleEvent]);

  const personaMap: Record<string, Persona> = {};
  personas.forEach((p) => {
    personaMap[p.id] = p;
  });

  const activePersonas = lanes.filter(
    (lane) => lane.steps.some((s) => s.status !== "pending") || lane.done,
  );

  return (
    <div className="min-h-screen bg-field">
      <div className="flex items-center justify-between border-b border-hairline px-10 py-4">
        <div className="flex items-center gap-2 text-[13px] text-secondary">
          <Link href="/" className="text-brand no-underline hover:underline">Home</Link>
          <span>/</span>
          <Link href={`/projects/${projectId}`} className="text-brand no-underline hover:underline">Project</Link>
          <span>/</span>
          <span className="text-primary">Live run</span>
        </div>
        {done && overallScore != null && (
          <Link
            href={`/projects/${projectId}/runs/${runId}`}
            className="rounded-xl bg-brand px-5 py-2.5 text-[14px] font-medium text-white no-underline transition-opacity hover:opacity-90"
          >
            View report
          </Link>
        )}
      </div>

      <div className="px-10 py-8">
        <div className="rise mb-8 flex items-center justify-between">
          <div>
            <h1 className="font-display text-[28px] text-primary">Live acceptance test</h1>
            <p className="mt-1 text-[14px] text-secondary">{done ? "Run complete" : "Running..."}</p>
          </div>
          <div className="text-right">
            <div className="font-display text-[48px] leading-none tabular-nums text-primary">
              {overallScore != null ? scorePct(overallScore) : "—"}
            </div>
            <div className="mt-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-tertiary">Score</div>
          </div>
        </div>

        <div className="space-y-3">
          {activePersonas.map((lane, i) => {
            const persona = personaMap[lane.personaId];
            if (!persona) return null;
            return (
              <div
                key={lane.personaId}
                className={`rise rounded-[16px] transition-colors ${laneBgClass(lane.confusionLevel, lane.blocked)} shadow-[0_1px_2px_rgba(0,0,0,0.04),0_8px_24px_rgba(0,0,0,0.04)]`}
                style={{
                  animationDelay: `${i * 30}ms`,
                  borderLeft: lane.confusionLevel > 0.05
                    ? `3px solid ${laneAccentColor(lane.confusionLevel)}`
                    : undefined,
                }}
              >
                <div className="flex items-start gap-5 p-5">
                  <div className="flex w-[160px] shrink-0 items-center gap-3">
                    <div className="h-10 w-10 shrink-0 overflow-hidden rounded-full bg-field">
                      {persona.figurineUrl && (
                        <img src={persona.figurineUrl} alt={persona.identity.name} className="h-10 w-10 rounded-full object-cover" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <div className="truncate text-[14px] font-medium text-primary">{persona.identity.name}</div>
                      <div className="text-[11px] tabular-nums text-tertiary">
                        {lane.done
                          ? lane.blocked
                            ? `Blocked at ${lane.blockedAt}`
                            : "Completed"
                          : `Confusion: ${(lane.confusionScore * 100).toFixed(0)}%`}
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-1 flex-col gap-3">
                    <div className="flex items-center gap-2">
                      {lane.steps.map((step, si) => (
                        <StepCell
                          key={step.stepName}
                          step={step}
                          isActive={si === lane.activeStep && !lane.done}
                          isBlocked={lane.blocked && lane.blockedAt === step.stepName}
                        />
                      ))}
                    </div>

                    {lane.innerMonologue && (
                      <div className="min-w-0">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-tertiary">
                          Simulated reasoning
                        </div>
                        <ThoughtLine
                          text={lane.innerMonologue}
                          blocked={lane.blocked && lane.done}
                        />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {done && (
          <div className="rise mt-8 text-center">
            <p className="text-[15px] text-secondary">
              Run complete. Overall score:{" "}
              <span className="font-semibold text-primary">{scorePct(overallScore!)}%</span>
            </p>
            <Link
              href={`/projects/${projectId}/runs/${runId}`}
              className="mt-4 inline-block rounded-xl bg-brand px-6 py-3 text-[14px] font-medium text-white no-underline transition-opacity hover:opacity-90"
            >
              View full report
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

function ThoughtLine({ text, blocked }: { text: string; blocked: boolean }) {
  return (
    <p
      className={`mt-1 text-[13px] leading-relaxed transition-opacity duration-300 motion-reduce:transition-none ${
        blocked ? "font-medium text-blocked" : "italic text-secondary"
      }`}
    >
      &ldquo;{text}&rdquo;
    </p>
  );
}

function StepCell({
  step,
  isActive,
  isBlocked,
}: {
  step: { stepName: string; status: Severity | "pending"; dwellMs: number | null };
  isActive: boolean;
  isBlocked: boolean;
}) {
  const statusColor: Record<string, string> = {
    ok: "#1d8a4e",
    friction: "#b25e00",
    blocked: "#c8362f",
    pending: "#e5e5ea",
  };

  return (
    <div className="flex flex-1 flex-col items-center gap-1">
      <div
        className={`flex h-8 w-full items-center justify-center rounded-lg text-[11px] font-medium transition-colors ${
          isActive ? "pulse-soft" : ""
        }`}
        style={{
          background:
            step.status === "pending"
              ? "#f5f5f7"
              : step.status === "blocked"
                ? "#fdf3f2"
                : step.status === "friction"
                  ? "#fbf6ef"
                  : "#f1f7f3",
          color: statusColor[step.status],
        }}
      >
        {step.status === "pending" ? (
          <span className="text-tertiary">—</span>
        ) : step.status === "blocked" ? (
          <span className="font-semibold text-blocked">blocked</span>
        ) : step.dwellMs != null ? (
          <span className="tabular-nums">{(step.dwellMs / 1000).toFixed(1)}s</span>
        ) : (
          <span>✓</span>
        )}
      </div>
      <span className="text-[10px] text-tertiary">{step.stepName}</span>
    </div>
  );
}
