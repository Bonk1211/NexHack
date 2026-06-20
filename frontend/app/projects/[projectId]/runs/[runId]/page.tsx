"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getRun, getPersonas } from "@/lib/api";
import { getRunPack, type Pack, type UsageSummary } from "@/lib/live";
import type { RunDetail } from "@/lib/types";
import { ScoreRing } from "@/components/ScoreRing";
import { PersonaWall } from "@/components/PersonaWall";
import { FrictionMatrix } from "@/components/FrictionMatrix";
import { RunLog } from "@/components/RunLog";
import { Results } from "@/components/AssessmentRunner";

type LivePack = { pack: Pack; usage: UsageSummary | null };

export default function RunDetailPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const runId = params.runId as string;

  // A run can be served two ways: the live/Supabase evidence pack (real runs) or
  // the fixture mock (demo runs). Prefer the live pack; fall back to the mock.
  const [livePack, setLivePack] = useState<LivePack | null>(null);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [personaNames, setPersonaNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const live = await getRunPack(runId);
        if (!cancelled) setLivePack(live);
      } catch {
        // Not a live/persisted run — try the fixture store instead.
        try {
          const [r, personas] = await Promise.all([getRun(runId), getPersonas()]);
          if (cancelled) return;
          setRun(r);
          const names: Record<string, string> = {};
          personas.forEach((p) => {
            names[p.id] = p.identity.name;
          });
          setPersonaNames(names);
        } catch {
          if (!cancelled) setRun(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [runId]);

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
        {loading ? (
          <>
            <div className="h-8 w-48 shimmer rounded-lg" />
            <div className="mt-6 h-[400px] card shimmer" />
          </>
        ) : livePack ? (
          <Results pack={livePack.pack} runId={runId} usage={livePack.usage} />
        ) : run ? (
          <MockRunView run={run} personaNames={personaNames} runId={runId} />
        ) : (
          <p className="text-secondary">Run not found.</p>
        )}
      </div>
    </div>
  );
}

// Fixture-backed run view (demo runs from lib/api). Real runs render via <Results />.
function MockRunView({
  run,
  personaNames,
  runId,
}: {
  run: RunDetail;
  personaNames: Record<string, string>;
  runId: string;
}) {
  const blockedPersonas = run.personaResults.filter((p) => p.status === "blocked");
  const atRiskNames = blockedPersonas.map((p) => p.persona.identity.name).join(", ");

  return (
    <>
      <div className="rise rounded-[20px] bg-anchor p-10">
        <div className="flex items-start justify-between">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-on-dark-dim">
              InclusionScope
            </div>
            <h2 className="mt-2 font-display text-[28px] text-on-dark">Run {runId}</h2>
            <p className="mt-1 text-[14px] text-on-dark-dim">
              {run.personaResults.length} personas · {run.mode}
            </p>
            {atRiskNames && (
              <p className="mt-3 text-[14px] text-on-dark-dim">
                At risk: <span className="font-medium text-[#ff6b60]">{atRiskNames}</span>
              </p>
            )}
          </div>
          <ScoreRing value={run.overallScore} size={132} />
        </div>
      </div>

      <PersonaWall results={run.personaResults} />
      <FrictionMatrix matrix={run.frictionMatrix} personaNames={personaNames} />
      <RunLog results={run.personaResults} />
    </>
  );
}
