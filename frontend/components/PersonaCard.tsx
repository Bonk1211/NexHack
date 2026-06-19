import type { PersonaResult } from "@/lib/types";
import { StatusDot } from "./StatusDot";

const CARD_STATE: Record<string, string> = {
  ok: "bg-card",
  friction: "bg-card border-l-[3px] border-friction",
  blocked: "bg-tint-blocked border-l-[3px] border-blocked",
};

export function PersonaCard({
  result,
  onOpen,
}: {
  result: PersonaResult;
  onOpen?: (personaId: string, step?: string) => void;
}) {
  const status = result.status;
  const blocked = status === "blocked";

  const line = blocked && result.blockedAt
    ? `Blocked at ${result.blockedAt}`
    : status === "friction"
      ? "Some friction"
      : "Completed";

  return (
    <button
      type="button"
      onClick={() => onOpen?.(result.personaId, result.blockedAt ?? undefined)}
      className={`group flex h-full min-h-[112px] w-full flex-col justify-between rounded-[18px] p-5 text-left shadow-[0_1px_2px_rgba(0,0,0,0.04),0_8px_24px_rgba(0,0,0,0.04)] transition-all duration-200 ease-out hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand motion-reduce:transition-none motion-reduce:hover:translate-y-0 ${CARD_STATE[status]}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate font-display text-[17px] text-primary">{result.persona.name}</div>
          <div className="mt-0.5 truncate text-[13px] text-tertiary">{result.persona.label}</div>
        </div>
        <StatusDot status={status} size={7} />
      </div>

      <div
        className={`text-[13px] ${blocked ? "font-medium text-blocked" : "text-secondary"}`}
      >
        {line}
      </div>
    </button>
  );
}
