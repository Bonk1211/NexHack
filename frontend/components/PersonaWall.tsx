import type { PersonaResult } from "@/lib/types";
import { PersonaCard } from "./PersonaCard";

const STATE_RANK: Record<string, number> = { blocked: 0, friction: 1, ok: 2 };

export function PersonaWall({
  results,
  onOpen,
}: {
  results: PersonaResult[];
  onOpen?: (personaId: string, step?: string) => void;
}) {
  const blockedCount = results.filter((p) => p.status === "blocked").length;
  const ordered = [...results].sort(
    (a, b) => (STATE_RANK[a.status] ?? 2) - (STATE_RANK[b.status] ?? 2),
  );

  return (
    <section className="mt-14">
      <div className="flex items-baseline justify-between">
        <h2 className="section-label">Persona wall</h2>
        <span className="text-[13px] text-secondary">
          {blockedCount}/{results.length} blocked
        </span>
      </div>

      <div className="mt-5 grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4">
        {ordered.map((p, i) => (
          <div key={p.personaId} className="rise h-full" style={{ animationDelay: `${i * 30}ms` }}>
            <PersonaCard result={p} onOpen={onOpen} />
          </div>
        ))}
      </div>
    </section>
  );
}
