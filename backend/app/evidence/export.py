"""Evidence pack export (§13) — JSON and audit-style PDF.

The evidence pack (app.evidence.pack.build_pack) is the differentiated output;
this module makes it *exportable* as a compliance artifact rather than a log file
(FR-4.1). JSON is the machine-readable canonical form; the PDF is the human/audit
deliverable.

Two-stream discipline (§16) is carried into the PDF layout: the TRUSTED WCAG
conformance table is visually separated from the INDICATIVE persona-verdict table
(distinct section headers + an explicit label), so a reader never mistakes the
persona-simulation signal for machine-verified conformance.

Rendering is headless — reportlab.platypus needs no browser.
"""
from __future__ import annotations

import io
import json

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def pack_to_json_bytes(pack: dict) -> bytes:
    """Serialize the evidence pack as pretty UTF-8 JSON bytes (HTTP download)."""
    return json.dumps(pack, indent=2, ensure_ascii=False).encode("utf-8")


def pack_to_json(pack: dict, path: str) -> str:
    """Write the evidence pack as pretty JSON to `path`; return `path`."""
    with open(path, "wb") as f:
        f.write(pack_to_json_bytes(pack))
    return path


def _table(rows: list[list], header_bg: colors.Color) -> Table:
    """A simple bordered table with a colored header row."""
    t = Table(rows, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), header_bg),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.96, 0.96, 0.96)]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _render_pdf(pack: dict, target) -> None:
    """Render the evidence pack as an audit-style PDF into `target`.

    `target` may be a filesystem path (str) or a binary file-like buffer —
    `SimpleDocTemplate` accepts either, which lets us serve the PDF over HTTP
    without touching disk.
    """
    styles = getSampleStyleSheet()
    h1, h2, body = styles["Title"], styles["Heading2"], styles["BodyText"]
    note = styles["Italic"]

    doc = SimpleDocTemplate(
        target,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="InclusionScope Evidence Pack",
    )

    app = pack.get("app", "")
    run_at = pack.get("run_at", "")
    score = pack.get("inclusion_score", "")

    story: list = []

    # Title block.
    story.append(Paragraph("InclusionScope — Inclusion Assurance Evidence Pack", h1))
    story.append(
        Paragraph(
            f"<b>App:</b> {app} &nbsp;&nbsp; <b>Run:</b> {run_at} "
            f"&nbsp;&nbsp; <b>Inclusion score:</b> {score}",
            body,
        )
    )
    story.append(Spacer(1, 6 * mm))

    # Executive summary.
    personas = pack.get("personas", [])
    blocked = [p for p in personas if p.get("verdict") == "blocked"]
    wcag = pack.get("wcag_conformance", {})
    failed_crit = [c for c, v in wcag.items() if v == "fail"]
    story.append(Paragraph("Executive summary", h2))
    story.append(
        Paragraph(
            f"{len(blocked)} of {len(personas)} personas were blocked; "
            f"{len(failed_crit)} WCAG criteria failed conformance.",
            body,
        )
    )
    story.append(Spacer(1, 6 * mm))

    # TRUSTED stream — WCAG conformance (machine-verifiable, §16).
    story.append(Paragraph("WCAG conformance — TRUSTED (machine-verifiable)", h2))
    story.append(
        Paragraph(
            "Machine-verifiable conformance results, reportable on their own.",
            note,
        )
    )
    wcag_rows = [["Criterion", "Result"]]
    for crit in sorted(wcag):
        wcag_rows.append([crit, wcag[crit].upper()])
    if len(wcag_rows) == 1:
        wcag_rows.append(["—", "no criteria tested"])
    story.append(_table(wcag_rows, colors.HexColor("#1b5e20")))  # green = trusted
    story.append(Spacer(1, 8 * mm))

    # INDICATIVE stream — per-persona verdicts (persona simulation, §16).
    story.append(Paragraph("Persona verdicts — INDICATIVE (persona simulation)", h2))
    story.append(
        Paragraph(
            "Indicative persona-simulation signal — NOT machine-verified conformance.",
            note,
        )
    )
    persona_rows = [["Persona", "Verdict", "Severity", "Blocked at"]]
    for p in personas:
        persona_rows.append(
            [
                p.get("persona", ""),
                p.get("verdict", ""),
                p.get("severity") or "—",
                p.get("blocked_at") or "—",
            ]
        )
    if len(persona_rows) == 1:
        persona_rows.append(["—", "—", "—", "—"])
    story.append(_table(persona_rows, colors.HexColor("#e65100")))  # amber = indicative
    story.append(Spacer(1, 8 * mm))

    # Prioritized remediation, routed to owning area (FR-4.3).
    story.append(Paragraph("Remediation — prioritized & routed", h2))
    rem_rows = [["Severity", "Issue", "Owner"]]
    for r in pack.get("remediation", []):
        rem_rows.append(
            [
                r.get("severity") or "—",
                r.get("issue", ""),
                r.get("owner", ""),
            ]
        )
    if len(rem_rows) == 1:
        rem_rows.append(["—", "no remediation items", "—"])
    story.append(_table(rem_rows, colors.HexColor("#37474f")))
    story.append(Spacer(1, 8 * mm))

    # Proposed fixes — engineering: the behavioral + confusion rollup (derived, below the
    # trusted remediation table above).
    story.append(Paragraph("Proposed fixes — engineering", h2))
    prop_rows = [["Severity", "Step", "Owner", "Proposed fix"]]
    for p in pack.get("proposals", []):
        prop_rows.append(
            [
                p.get("severity") or "—",
                p.get("step_key", ""),
                p.get("owner", ""),
                p.get("fix", ""),
            ]
        )
    if len(prop_rows) == 1:
        prop_rows.append(["—", "—", "—", "no proposed fixes"])
    story.append(_table(prop_rows, colors.HexColor("#37474f")))

    doc.build(story)


def pack_to_pdf(pack: dict, path: str) -> str:
    """Render the evidence pack as an audit-style PDF to `path`; return `path`."""
    _render_pdf(pack, path)
    return path


def pack_to_pdf_bytes(pack: dict) -> bytes:
    """Render the evidence pack as audit-style PDF bytes (HTTP download)."""
    buf = io.BytesIO()
    _render_pdf(pack, buf)
    return buf.getvalue()
