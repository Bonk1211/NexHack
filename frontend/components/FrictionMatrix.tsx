import type { FrictionMatrix as MatrixType, Severity } from "@/lib/types";

const CELL_TINT: Record<Severity, string> = {
  ok: "#f1f7f3",
  friction: "#fbf6ef",
  blocked: "#fdf3f2",
};
const CELL_TEXT: Record<Severity, string> = {
  ok: "#1d8a4e",
  friction: "#b25e00",
  blocked: "#c8362f",
};

export function FrictionMatrix({
  matrix,
  personaNames,
}: {
  matrix: MatrixType;
  personaNames: Record<string, string>;
}) {
  return (
    <section className="mt-14">
      <h2 className="section-label">Friction matrix</h2>

      <div className="mt-5 overflow-x-auto rounded-[18px] bg-card p-2 shadow-[0_1px_2px_rgba(0,0,0,0.04),0_8px_24px_rgba(0,0,0,0.04)]">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-card px-3 py-2.5 text-left text-[12px] font-semibold uppercase tracking-[0.08em] text-tertiary">
                Persona
              </th>
              {matrix.steps.map((s) => (
                <th
                  key={s}
                  className="px-3 py-2.5 text-right text-[12px] font-semibold uppercase tracking-[0.08em] text-tertiary"
                >
                  {s}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.rows.map((row, ri) => (
              <tr
                key={row.personaId}
                className="rise border-t border-hairline"
                style={{ animationDelay: `${ri * 30}ms` }}
              >
                <td className="sticky left-0 z-10 bg-card px-3 py-1.5 text-[14px] font-medium text-primary">
                  {personaNames[row.personaId] ?? row.personaId}
                </td>
                {row.cells.map((cell) => {
                  const reached = cell.dwellMs != null;
                  return (
                    <td key={cell.stepName} className="p-1">
                      <div
                        className="flex h-10 w-full min-w-[68px] items-center justify-end rounded-lg px-3 text-[15px] font-medium tabular-nums"
                        style={{ background: CELL_TINT[cell.status], color: CELL_TEXT[cell.status] }}
                      >
                        {cell.status === "blocked" && !reached ? (
                          <span className="text-[13px] font-medium">blocked</span>
                        ) : reached ? (
                          `${(cell.dwellMs! / 1000).toFixed(1)}s`
                        ) : (
                          <span className="text-[13px]">—</span>
                        )}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex items-center gap-5 text-[12px] text-secondary">
        <Legend color="#1d8a4e" label="Pass" />
        <Legend color="#b25e00" label="Friction" />
        <Legend color="#c8362f" label="Blocked" />
      </div>
    </section>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-2 w-2 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}
