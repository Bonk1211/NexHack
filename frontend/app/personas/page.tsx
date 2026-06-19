"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getPersonas } from "@/lib/api";
import type { Persona } from "@/lib/types";
import { behaviorChips } from "@/lib/format";

export default function PersonasPage() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPersonas().then((p) => {
      setPersonas(p);
      setLoading(false);
    });
  }, []);

  return (
    <div className="px-10 py-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-[32px] text-primary">Personas</h1>
          <p className="mt-1 text-[14px] text-secondary">
            Your library of test personas for accessibility audits.
          </p>
        </div>
        <Link
          href="/personas/new"
          className="rounded-xl bg-brand px-5 py-2.5 text-[14px] font-medium text-white no-underline transition-opacity hover:opacity-90"
        >
          New persona
        </Link>
      </div>

      {loading ? (
        <div className="mt-8 grid grid-cols-4 gap-5">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="card h-[160px] shimmer" />
          ))}
        </div>
      ) : (
        <div className="mt-8 grid grid-cols-4 gap-5">
          {personas.map((p, i) => (
            <div key={p.id} className="rise" style={{ animationDelay: `${i * 30}ms` }}>
              <PersonaLibraryCard persona={p} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PersonaLibraryCard({ persona }: { persona: Persona }) {
  const chips = behaviorChips(persona);
  const isLoading = persona.figurineStatus !== "ready";

  return (
    <Link
      href={`/personas/${persona.id}`}
      className="card group block p-5 no-underline transition-all duration-200 ease-out hover:-translate-y-0.5"
    >
      <div className="flex items-start gap-3">
        <div className="h-12 w-12 shrink-0 overflow-hidden rounded-full">
          {isLoading ? (
            <div className="h-12 w-12 shimmer rounded-full" />
          ) : (
            <img
              src={persona.figurineUrl}
              alt={persona.name}
              className="h-12 w-12 rounded-full object-cover"
            />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-display text-[17px] text-primary">{persona.name}</h3>
          <p className="mt-0.5 truncate text-[12px] text-tertiary">{persona.label}</p>
        </div>
      </div>

      {chips.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {chips.map((chip) => (
            <span
              key={chip}
              className="rounded-full bg-field px-2.5 py-0.5 text-[11px] font-medium text-secondary"
            >
              {chip}
            </span>
          ))}
        </div>
      )}
    </Link>
  );
}
