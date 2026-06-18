// Small shared display helpers for the dashboard (labels, severity colors).
import type { MatrixStatus, Severity } from "./api";

// Turn persona ids ("oku_visual") into readable labels ("OKU — Visual").
export function personaLabel(id: string): string {
  const map: Record<string, string> = {
    control: "Control (baseline)",
    oku_visual: "OKU — Visual",
    oku_motor: "OKU — Motor",
    oku_hearing: "OKU — Hearing",
    elderly_low_literacy: "Elderly · Low literacy",
    low_literacy: "Low literacy",
    non_native: "Non-native speaker",
    low_end_device: "Low-end device",
  };
  return map[id] ?? id.replace(/_/g, " ");
}

// Severity chip colors: P0 hottest, descending to grey.
export function severityColor(sev: Severity): { bg: string; fg: string } {
  switch (sev) {
    case "P0":
      return { bg: "#7f1d1d", fg: "#fecaca" };
    case "P1":
      return { bg: "#7c2d12", fg: "#fed7aa" };
    case "P2":
      return { bg: "#713f12", fg: "#fde68a" };
    case "P3":
      return { bg: "#334155", fg: "#cbd5e1" };
    default:
      return { bg: "#1e293b", fg: "#94a3b8" };
  }
}

// Matrix cell fill by status. na is rendered hatched (see component).
export function statusFill(status: MatrixStatus): string {
  switch (status) {
    case "green":
      return "#16a34a";
    case "amber":
      return "#d97706";
    case "red":
      return "#dc2626";
    case "na":
      return "#1e2434";
  }
}
