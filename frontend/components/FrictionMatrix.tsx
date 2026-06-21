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

      {/* Steps are ROWS (a run can have many — they scroll vertically) and personas are
          COLUMNS (few — they fit the viewport), so the matrix never scrolls horizontally. */}
      <div className="mt-5 rounded-[18px] bg-card p-2 shadow-[0_1px_2px_rgba(0,0,0,0.04),0_8px_24px_rgba(0,0,0,0.04)]">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              <th className="px-3 py-2.5 text-left text-[12px] font-semibold uppercase tracking-[0.08em] text-tertiary">
                Step
              </th>
              {matrix.rows.map((row) => (
                <th
                  key={row.personaId}
                  className="px-3 py-2.5 text-right text-[12px] font-semibold uppercase tracking-[0.08em] text-tertiary"
                >
                  {personaNames[row.personaId] ?? row.personaId}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.steps.map((step, si) => (
              <tr
                key={step}
                className="rise border-t border-hairline"
                style={{ animationDelay: `${si * 20}ms` }}
              >
                <td className="max-w-[240px] break-words px-3 py-1.5 align-middle text-[13px] font-medium text-primary">
                  {step}
                </td>
                {matrix.rows.map((row) => {
                  const cell = row.cells.find((c) => c.stepName === step);
                  const reached = cell?.dwellMs != null;
                  return (
                    <td key={row.personaId} className="p-1">
                      <div
                        className="flex h-10 w-full items-center justify-end rounded-lg px-3 text-[15px] font-medium tabular-nums"
                        style={
                          cell
                            ? { background: CELL_TINT[cell.status], color: CELL_TEXT[cell.status] }
                            : { background: "#f4f4f5", color: "#a1a1aa" }
                        }
                      >
                        {!cell ? (
                          <span className="text-[13px] text-tertiary">—</span>
                        ) : status === "blocked" && !reached ? (
                          <span className="text-[13px] font-medium">blocked</span>
                        ) : reached ? (
                          `${(cell!.dwellMs! / 1000).toFixed(1)}s`
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
