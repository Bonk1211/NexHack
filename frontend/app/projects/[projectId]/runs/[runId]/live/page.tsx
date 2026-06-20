"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getApp, getLinkedPersonas, getPersonas } from "@/lib/api";
import { streamRun, type Pack, type UsageSummary } from "@/lib/live";
import { LiveView, Results, reduce, type LiveState } from "@/components/AssessmentRunner";

export default function LiveRunPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  const [live, setLive] = useState<LiveState | null>(null);
  const [pack, setPack] = useState<Pack | null>(null);
  const [liveRunId, setLiveRunId] = useState<string | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [appName, setAppName] = useState("");
  const [personaInfoMap, setPersonaInfoMap] = useState<Record<string, { name: string; figurineUrl?: string }>>({});
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"live" | "results">("live");
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const [app, linkedSlugs, allPersonas] = await Promise.all([
          getApp(projectId),
          getLinkedPersonas(projectId),
          getPersonas(),
        ]);
        if (cancelled) return;

        if (!app.stagingUrl) {
          setError("No staging URL configured for this project.");
          return;
        }
        if (linkedSlugs.length === 0) {
          setError("No personas linked to this project.");
          return;
        }

        setAppName(app.name);

        // Build slug → display info map from the full persona library
        const infoMap: Record<string, { name: string; figurineUrl?: string }> = {};
        for (const p of allPersonas) {
          // Backend returns slug as `id`; identity.name is the display name
          const stem = (p as any).stem ?? p.id;
          infoMap[stem] = {
            name: p.identity?.name ?? stem,
            figurineUrl: p.figurineUrl,
          };
        }
        setPersonaInfoMap(infoMap);

        setLive({ runNodes: [], log: [], frames: {}, n: 1 });
        esRef.current?.close();
        esRef.current = streamRun(
          { appName: app.name, targetUrl: app.stagingUrl, personaNames: linkedSlugs },
          (e) => {
            if (e.type === "usage") {
              setUsage(e.summary);
              return;
            }
            if (e.type === "final") {
              setPack(e.pack);
              setLiveRunId(e.run_id);
              if (e.usage) setUsage(e.usage);
              setView("results");
              esRef.current?.close();
              return;
            }
            if (e.type === "error") {
              setError(e.message);
              esRef.current?.close();
              return;
            }
            setLive((s) => (s ? reduce(s, e) : s));
          },
        );
      } catch (err) {
        if (!cancelled) setError(String(err));
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
      esRef.current?.close();
    };
  }, [projectId]);

  const done = pack !== null;

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
        {done && liveRunId && (
          <Link
            href={`/projects/${projectId}/runs/${liveRunId}`}
            className="rounded-xl bg-brand px-5 py-2.5 text-[14px] font-medium text-white no-underline transition-opacity hover:opacity-90"
          >
            View report
          </Link>
        )}
      </div>

      <div className="px-10 py-8">
        <div className="rise mb-6">
          <h1 className="font-display text-[28px] text-primary">
            {appName ? `Live — ${appName}` : "Live run"}
          </h1>
          <p className="mt-1 text-[14px] text-secondary">
            {error
              ? "Error"
              : done
                ? "Run complete"
                : live
                  ? "Agents running…"
                  : "Starting up…"}
          </p>
        </div>

        {error && (
          <div className="rounded-xl bg-tint-blocked p-4 text-[14px] text-blocked">{error}</div>
        )}

        {live && !error && (
          <>
            {done && (
              <div className="mb-6 inline-flex items-center gap-1 rounded-lg bg-field p-1">
                {(["live", "results"] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => setView(v)}
                    className={`rounded-md px-3 py-1 text-[12px] font-medium capitalize transition-colors ${
                      view === v ? "bg-card text-primary shadow-sm" : "text-secondary hover:text-primary"
                    }`}
                  >
                    {v === "live" ? "Live preview" : "Results"}
                  </button>
                ))}
              </div>
            )}

            {(!done || view === "live") && (
              <LiveView live={live} personaInfoMap={personaInfoMap} />
            )}
            {done && view === "results" && pack && (
              <Results pack={pack} runId={liveRunId} usage={usage} />
            )}
          </>
        )}
      </div>
    </div>
  );
}
