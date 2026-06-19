"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getRun, getPersonas } from "@/lib/api";
import type { RunDetail, Persona } from "@/lib/types";
import { scorePct } from "@/lib/format";
import { ScoreRing } from "@/components/ScoreRing";
import { PersonaWall } from "@/components/PersonaWall";
import { FrictionMatrix } from "@/components/FrictionMatrix";

export default function RunDetailPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const runId = params.runId as string;

  const [run, setRun] = useState<RunDetail | null>(null);
  const [personaNames, setPersonaNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getRun(runId), getPersonas()]).then(([r, personas]) => {
      setRun(r);
      const names: Record<string, string> = {};
      personas.forEach((p) => {
        names[p.id] = p.name;
      });
      setPersonaNames(names);
      setLoading(false);
    });
  }, [runId]);

  if (loading) {
    return (
      <div className="px-10 py-10">
        <div className="h-8 w-48 shimmer rounded-lg" />
        <div className="mt-6 h-[400px] card shimmer" />
      </div>
    );
  }

  if (!run) {
    return (
      <div className="px-10 py-10">
        <p className="text-secondary">Run not found.</p>
      </div>
    );
  }

  const blockedPersonas = run.personaResults.filter((p) => p.status === "blocked");
  const atRiskNames = blockedPersonas.map((p) => p.persona.name).join(", ");

  return (
    <div>
      <div className="flex items-center justify-between border-b border-hairline px-10 py-4">
        <div className="flex items-center gap-2 text-[13px] text-secondary">
          <Link href="/" className="text-brand no-underline hover:underline">
            Home
          </Link>
          <span>/</span>
          <Link href={`/projects/${projectId}`} className="text-brand no-underline hover:underline">
            Project
          </Link>
          <span>/</span>
          <span className="text-primary">{runId}</span>
        </div>
      </div>

      <div className="px-10 py-8">
        <div className="rise rounded-[20px] bg-anchor p-10">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-on-dark-dim">
                InclusionScope
              </div>
              <h2 className="mt-2 font-display text-[28px] text-on-dark">
                Run {runId}
              </h2>
              <p className="mt-1 text-[14px] text-on-dark-dim">
                {run.personaResults.length} personas · {run.mode}
              </p>
              {atRiskNames && (
                <p className="mt-3 text-[14px] text-on-dark-dim">
                  At risk:{" "}
                  <span className="font-medium text-[#ff6b60]">{atRiskNames}</span>
                </p>
              )}
            </div>
            <ScoreRing value={run.overallScore} size={132} />
          </div>
        </div>

        <PersonaWall results={run.personaResults} />
        <FrictionMatrix matrix={run.frictionMatrix} personaNames={personaNames} />
      </div>
    </div>
  );
}
