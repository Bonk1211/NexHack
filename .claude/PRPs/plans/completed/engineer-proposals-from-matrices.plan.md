# Plan: Aggregate friction + confusion matrices into engineer proposals

## Summary
Today the evidence pack routes remediation **only** from trusted axe/WCAG failures (`build_remediation`). Steps that block or confuse personas with *no* axe violation (ambiguous labels, give-up dwell, high LLM confusion) produce **no** engineering guidance. This adds a per-step **proposals** aggregator: it reads the friction signals (status + dwell + dead-ends per persona×step) and the confusion stream (`llm_confusion` per persona×step), clusters them by step, and emits a prioritized, owner-routed **proposed fix for engineers** — even when there is no WCAG failure.

## User Story
As an engineer triaging an assessment, I want each problematic step rolled up into one concrete proposed fix (root cause + what to change + who owns it + severity), so that I can act on behavioral friction and confusion, not just axe failures.

## Problem → Solution
`build_remediation` is WCAG-criterion-only; the friction matrix and the confusion signal are shown to humans but never turned into actionable fixes. → A new PURE `build_proposals(runs)` aggregates friction status + dwell + confusion (+ any WCAG) per step into ranked engineer proposals, attached to the pack as `pack["proposals"]`, rendered in Results and the PDF/JSON export.

## Metadata
- **Complexity**: Medium
- **Source PRD**: N/A (free-form feature)
- **PRD Phase**: N/A
- **Estimated Files**: 5 (3 backend, 2 frontend) + 1 test file updated

---

## UX Design

### Before
```
Results
 ├─ Inclusion score + synthesis
 ├─ Persona verdicts
 ├─ Friction matrix  (status cells)
 └─ Empathy replay
(Remediation = WCAG-only, shown only in the exported PDF)
```

### After
```
Results
 ├─ Inclusion score + synthesis
 ├─ Proposed fixes for engineering   ← NEW
 │    P0 · "otp"  · @content
 │       2 personas blocked, confusion 1.0, WCAG 4.1.2
 │       → Add a programmatic <label> to the OTP field; show inline error text.
 │    P2 · "address" · @content
 │       Elderly dwelled 41s, confusion 0.7
 │       → Simplify copy / add helper text; reading grade too high.
 ├─ Persona verdicts
 ├─ Friction matrix
 └─ Empathy replay
```

### Interaction Changes
| Touchpoint | Before | After | Notes |
|---|---|---|---|
| Results page | no engineer fixes inline | ranked "Proposed fixes" section | reads `pack.proposals` |
| Behavioral-only blocks | invisible to remediation | become proposals | the core gap this closes |
| PDF/JSON export | remediation (WCAG) only | + proposals section | mirrors remediation rendering |

---

## Mandatory Reading

| Priority | File | Lines | Why |
|---|---|---|---|
| P0 | `backend/app/evidence/pack.py` | 27-115, 206-248 | `build_remediation`/`build_friction_matrix` (the PURE aggregators to mirror) + `build_pack` (where to attach) |
| P0 | `backend/app/scoring/engine.py` | 30-128 | `StepSignals`, `step_status`, `_step_blocks`, `_has_friction`, `PersonaThresholds` — the signals to aggregate |
| P0 | `backend/tests/test_evidence.py` | 17-32, 92-126 | test helpers (`_run`, `_otp_blocked`) + remediation/empty-pack assertions to mirror |
| P1 | `backend/app/routes/runs.py` | 533-552 | how the pack is assembled in the SSE path (build_pack already attaches proposals → free here) |
| P1 | `backend/app/evidence/export.py` | 158-171 | remediation table render to mirror for proposals |
| P1 | `frontend/lib/live.ts` | 64-73 | `Pack` interface — add `proposals` |
| P1 | `frontend/components/AssessmentRunner.tsx` | 564-666 | `Results` component — add the proposals section |
| P2 | `backend/app/agents/llm.py` | 575-643 | OPTIONAL LLM narration pattern (`synthesize`) if enriching fix prose later |

## External Documentation
No external research needed — feature uses established internal PURE-aggregator + two-stream patterns.

---

## Patterns to Mirror

### PURE_AGGREGATOR (per-criterion rollup, severity-ranked, routed)
```python
# SOURCE: backend/app/evidence/pack.py:98-115
def build_remediation(runs: list[PersonaRunResult]) -> list[dict]:
    worst: dict[str, dict] = {}
    for r in runs:
        sev = r.result.persona_verdict.severity
        for crit, verdict in r.result.wcag_conformance.items():
            if verdict != "fail":
                continue
            rank = _SEVERITY_RANK.get(sev, 4)
            if crit not in worst or rank < _SEVERITY_RANK.get(worst[crit]["severity"], 4):
                worst[crit] = {"criterion": crit, "issue": ..., "owner": route_owner([crit]), "severity": sev}
    return sorted(worst.values(), key=lambda x: _SEVERITY_RANK.get(x["severity"], 4))
```

### STEP_KEY_UNION + PER-CELL STATUS (how steps & cells are derived)
```python
# SOURCE: backend/app/evidence/pack.py:69-95
step_keys: list[str] = []
for r in runs:
    for s in r.steps:
        if s.step_key not in step_keys:
            step_keys.append(s.step_key)
# ...
"status": step_status(by_key[key], r.thresholds),  # red|amber|green
"dwell_s": by_key[key].dwell_s,
```

### SIGNAL HELPERS (reuse, don't re-derive thresholds)
```python
# SOURCE: backend/app/scoring/engine.py:90-128
def _step_blocks(step, t) -> bool: ...       # dead_end / not completed / dwell≥giveup / retries>limit
def step_status(step, t) -> str: ...          # "red" | "amber" | "green"
# StepSignals.llm_confusion is the confusion stream (engine.py:41)
```

### ATTACH IN build_pack (single attach → /runs, /runs/stream, persistence all get it)
```python
# SOURCE: backend/app/evidence/pack.py:237-248
return {
    "app": app, "run_at": run_at, "inclusion_score": inclusion_score,
    "wcag_conformance": conformance, "matrix": build_friction_matrix(runs),
    "personas": personas, "remediation": build_remediation(runs),
}
```

### EXPORT TABLE (mirror for the proposals section)
```python
# SOURCE: backend/app/evidence/export.py:158-171
story.append(Paragraph("Remediation — prioritized & routed", h2))
rem_rows = [["Severity", "Issue", "Owner"]]
for r in pack.get("remediation", []):
    rem_rows.append([r.get("severity") or "—", r.get("issue", ""), r.get("owner", "")])
if len(rem_rows) == 1:
    rem_rows.append(["—", "no remediation items", "—"])
story.append(_table(rem_rows, colors.HexColor("#37474f")))
```

### FRONTEND RESULTS SECTION (where & how to render)
```tsx
// SOURCE: frontend/components/AssessmentRunner.tsx:588-608 (persona verdict cards)
<div className="grid gap-3 sm:grid-cols-3">
  {pack.personas.map((p) => ( ... ))}
</div>
```

### TEST HELPERS (mirror exactly)
```python
# SOURCE: backend/tests/test_evidence.py:17-32
T = PersonaThresholds(max_dwell_s=30, giveup_threshold_s=60, retry_limit=3, max_reading_grade=12)
def _run(persona, steps): return PersonaRunResult(persona, tuple(steps), T, score(steps, T))
def _otp_blocked():
    return StepSignals(1, "otp", critical=True, wcag=(WcagSignal("4.1.2", False),),
                       dead_end=True, completed=False)
```

---

## Files to Change

| File | Action | Justification |
|---|---|---|
| `backend/app/evidence/pack.py` | UPDATE | Add `build_proposals(runs)` (PURE) + attach as `pack["proposals"]` in `build_pack`; add a confusion/dwell owner heuristic |
| `backend/app/evidence/export.py` | UPDATE | Render a "Proposed fixes" table (mirror remediation) |
| `backend/tests/test_evidence.py` | UPDATE | Tests for the aggregator (blocked-no-WCAG, confusion-only, severity rank, empty) |
| `frontend/lib/live.ts` | UPDATE | Add `proposals` to the `Pack` interface |
| `frontend/components/AssessmentRunner.tsx` | UPDATE | Render the "Proposed fixes for engineering" section in `Results` |

## NOT Building
- **No LLM call in the core aggregator.** Proposals are deterministic from signals (§16 — LLM never bears marks). An optional LLM-narration enrichment can wrap the deterministic `fix` text later (mirror `synthesize`); it is OUT of this scope and the deterministic text always stands alone.
- **No new "confusion matrix" UI artifact.** Confusion already travels per-step (`llm_judgment.confusion`); we aggregate it, we don't add a second matrix table.
- **No change to scoring/severity math** (`engine.py`). Proposals consume existing severity/status; they don't redefine it.
- **No DB schema change.** `proposals` rides inside the existing pack JSON (the pack is persisted whole; `repository.py` stores `matrix`/`remediation` as JSON columns — proposals travels in the pack blob, no new column required for this scope).
- **No per-control granularity.** Proposals are per step_key (the matrix's unit), not per individual a11y node.

---

## Step-by-Step Tasks

### Task 1: Owner heuristic for non-WCAG signals
- **ACTION**: Add a routing helper for proposals whose driver is behavioral, not axe.
- **IMPLEMENT**: In `pack.py`, add
  ```python
  def _proposal_owner(wcag_failures: list[str], *, confusion_driven: bool) -> str:
      """WCAG failure routes via the criterion map; otherwise confusion/copy → @content,
      pure dwell/flow → @frontend."""
      if wcag_failures:
          return route_owner(wcag_failures)
      return "@content" if confusion_driven else "@frontend"
  ```
- **MIRROR**: PURE_AGGREGATOR (`route_owner`, pack.py:60-66).
- **GOTCHA**: keep using the existing `route_owner` for the WCAG case so owner mapping stays single-sourced.
- **VALIDATE**: `python -c "from app.evidence.pack import _proposal_owner; print(_proposal_owner([], confusion_driven=True), _proposal_owner(['1.4.3'], confusion_driven=False))"` → `@content @frontend`.

### Task 2: build_proposals aggregator
- **ACTION**: Aggregate friction + confusion per step into ranked engineer proposals.
- **IMPLEMENT**: In `pack.py` add `build_proposals(runs)`:
  - Build the union of `step_keys` in order (STEP_KEY_UNION).
  - For each step_key, iterate runs; for each run that HAS the step (`by_key`), compute `status = step_status(s, r.thresholds)`, `blocked = _step_blocks(s, r.thresholds)`, collect `s.dwell_s`, `s.llm_confusion`, WCAG fails (`[sig.criterion for sig in s.wcag if not sig.passed]`), and track the run's `r.result.persona_verdict.severity`.
  - A step becomes a proposal when **any** persona is `red`/`amber` OR `max_confusion >= 0.5`.
  - Aggregate: `affected_personas` (status in red/amber or confusion≥0.5), `blocked_personas`, `max_dwell_s`, `max_confusion = round(max,2)`, `wcag_failures` (sorted unique), `severity` = worst (lowest rank via `_SEVERITY_RANK`) among personas touching the step.
  - `confusion_driven = max_confusion >= 0.5 and not wcag_failures`.
  - `owner = _proposal_owner(wcag_failures, confusion_driven=confusion_driven)`.
  - `issue` + `fix` from `_propose_fix(...)` (Task 3).
  - Return `sorted(proposals, key=lambda p: (_SEVERITY_RANK.get(p["severity"],4), -len(p["affected_personas"])))`.
- **MIRROR**: PURE_AGGREGATOR + STEP_KEY_UNION.
- **GOTCHA**: `max()` over confusion needs a default — guard empty (`max(vals, default=0.0)`); a step present for no run can't happen here but keep the default. Reuse `step_status`/`_step_blocks` from engine (import them) — do NOT re-implement thresholds.
- **IMPORTS**: extend the existing `from app.scoring.engine import (...)` with `_step_blocks` (already imports `step_status`, `StepSignals`).
- **VALIDATE**: covered by Task 6 tests.

### Task 3: Deterministic fix templates
- **ACTION**: Turn the dominant signal into a concrete engineer instruction.
- **IMPLEMENT**: In `pack.py` add `_propose_fix(*, wcag_failures, blocked_personas, max_confusion, max_dwell_s, any_high_grade)` returning `(issue, fix)`. Priority order:
  1. `wcag_failures` → `issue = _ISSUE_TEXT[crit]`, `fix = f"Fix WCAG {crit}: {_ISSUE_TEXT[crit].lower()}."` (use first/worst crit).
  2. `blocked_personas` → `issue = f"{n} persona(s) could not get past this step"`, `fix = "Add inline validation/error text and ensure the primary control is reachable and labelled so the step can be completed."`
  3. `max_confusion >= 0.5` → `issue = f"Step unclear (confusion {max_confusion})"`, `fix = "Clarify the field label and instructions; add helper text so the expected input is obvious."`
  4. `max_dwell_s` over a nominal bar → `issue = f"Slow step (up to {max_dwell_s:.0f}s)"`, `fix = "Reduce reading load: shorten copy, simplify the layout, split the screen."`
- **MIRROR**: `_ISSUE_TEXT` table (pack.py:40-48).
- **GOTCHA**: templates are demo-readable, generic across apps (no app-specific wording) — same discipline as `_frame_caption` (pack.py:164-175).
- **VALIDATE**: Task 6 asserts the fix text per signal type.

### Task 4: Attach in build_pack
- **ACTION**: Expose proposals on the pack.
- **IMPLEMENT**: In `build_pack` return dict (pack.py:237-248) add `"proposals": build_proposals(runs),` next to `"remediation"`.
- **MIRROR**: ATTACH IN build_pack.
- **GOTCHA**: build_pack is the single assembly point — `/runs`, `/runs/stream`, and persistence all serialize the same pack, so no route change is needed.
- **VALIDATE**: `python -c "from app.evidence.pack import build_pack; print('proposals' in build_pack('X','t',[]))"` → `True`.

### Task 5: PDF/JSON export section
- **ACTION**: Add proposals to the audit export.
- **IMPLEMENT**: In `export.py` after the remediation table (export.py:171) add a "Proposed fixes — engineering" table: columns `["Severity","Step","Owner","Proposed fix"]`, rows from `pack.get("proposals", [])` (`p["severity"] or "—"`, `p["step_key"]`, `p["owner"]`, `p["fix"]`); empty-guard row like remediation. JSON export is automatic (it serializes the whole pack).
- **MIRROR**: EXPORT TABLE.
- **GOTCHA**: keep the trusted remediation table FIRST (it's the reportable stream); proposals are the derived/behavioral add-on below it.
- **VALIDATE**: `cd backend && .venv/bin/python -m pytest tests/test_export.py tests/test_export_route.py -q`.

### Task 6: Tests
- **ACTION**: Cover the aggregator's distinguishing behavior.
- **IMPLEMENT**: In `test_evidence.py` add:
  - `test_proposals_flag_behavioral_block_without_wcag`: a step with `dead_end=True, completed=False` and NO wcag → a proposal exists for it with severity P0/P1 and a non-empty `fix`. (This is the gap remediation misses.)
  - `test_proposals_flag_confusion_only`: a completed step with `llm_confusion=0.8`, no wcag, dwell small → proposal present, `owner == "@content"`, fix mentions clarity.
  - `test_proposals_prefer_wcag_owner`: step with `WcagSignal("1.4.3", False)` → owner `@frontend`, fix references WCAG.
  - `test_proposals_rank_by_severity`: P0 step ranks before a P2 step.
  - `test_proposals_empty_when_clean`: all-green run → `pack["proposals"] == []`.
- **MIRROR**: TEST HELPERS (`_run`, `_otp_blocked`, `T`).
- **VALIDATE**: `cd backend && .venv/bin/python -m pytest tests/test_evidence.py -q`.

### Task 7: Frontend type
- **ACTION**: Type the new pack field.
- **IMPLEMENT**: In `live.ts` `Pack` (64-73) add
  `proposals: { step_key: string; severity: string | null; owner: string; issue: string; fix: string; affected_personas: string[]; blocked_personas: string[]; max_confusion: number; max_dwell_s: number | null; wcag_failures: string[] }[];`
- **MIRROR**: existing `remediation` field type (live.ts:70).
- **VALIDATE**: `cd frontend && npx tsc --noEmit`.

### Task 8: Render proposals in Results
- **ACTION**: Show the ranked engineer fixes.
- **IMPLEMENT**: In `AssessmentRunner.tsx` `Results` (after the synthesis block, ~line 580, before persona verdicts) add a section "Proposed fixes for engineering" mapping `pack.proposals`. Each card: severity chip + `step_key` + `owner`, a one-line signal summary (`{n} blocked · confusion {max_confusion} · {wcag_failures.join(", ")}`), and the `fix` text. Reuse the blocked tint convention (`bg-tint-blocked border-l-[3px] border-blocked` when severity is P0/P1). Guard `pack.proposals?.length`.
- **MIRROR**: FRONTEND RESULTS SECTION (persona cards, AssessmentRunner.tsx:588-608); STATUS_COLOR/severity styling already in file.
- **GOTCHA**: historical packs (pre-feature, from Supabase) won't have `proposals` → optional-chain and render nothing when absent.
- **VALIDATE**: `cd frontend && npx tsc --noEmit`; manual run shows the section.

---

## Testing Strategy

### Unit Tests
| Test | Input | Expected | Edge? |
|---|---|---|---|
| behavioral block no WCAG | dead_end step, no wcag | proposal present, fix non-empty | yes (the core gap) |
| confusion only | completed, confusion 0.8 | proposal, owner `@content` | yes |
| WCAG owner wins | step w/ 1.4.3 fail | owner `@frontend`, fix cites WCAG | no |
| severity ranking | P0 + P2 steps | P0 first | no |
| clean run | all green | `proposals == []` | yes (empty) |

### Edge Cases Checklist
- [ ] Empty runs → `build_proposals([]) == []`
- [ ] Step present for some personas, `na` for others → aggregates only personas that reached it
- [ ] All-green run → no proposals
- [ ] Confusion exactly 0.5 → included (`>=`)
- [ ] Historical pack without `proposals` → frontend renders nothing (no crash)

---

## Validation Commands

### Static Analysis
```bash
cd backend && .venv/bin/python -c "import app.evidence.pack, app.evidence.export"
cd frontend && npx tsc --noEmit
```
EXPECT: no errors.

### Unit Tests
```bash
cd backend && .venv/bin/python -m pytest tests/test_evidence.py tests/test_export.py tests/test_export_route.py -q
```
EXPECT: all pass (existing + new).

### Full Test Suite
```bash
cd backend && .venv/bin/python -m pytest -q
```
EXPECT: no new failures (pre-existing `test_repository.py` DB-cred failures unrelated).

### Manual Validation
- [ ] Run an assessment with a persona that blocks on a non-axe step (e.g. unlabeled OTP / dwell give-up).
- [ ] Results shows "Proposed fixes for engineering" with that step, ranked, with a concrete fix + owner.
- [ ] Export PDF (`/runs/{id}/export?format=pdf`) includes the proposals table; `format=json` includes `proposals`.

---

## Acceptance Criteria
- [ ] `build_proposals` aggregates friction status + dwell + confusion (+ WCAG) per step
- [ ] Behavioral-only blocks/confusion (no axe) produce proposals — the gap is closed
- [ ] Proposals ranked by severity then # affected, owner-routed, with a concrete fix
- [ ] Attached to the pack; rendered in Results + export
- [ ] Deterministic (no LLM); existing tests unaffected; new tests pass

## Completion Checklist
- [ ] Reuses `step_status`/`_step_blocks`/`route_owner`/`_ISSUE_TEXT` (no re-derivation)
- [ ] PURE (no I/O) — unit-testable like the rest of `pack.py`
- [ ] Two-stream discipline kept (proposals are derived/behavioral, below trusted remediation)
- [ ] tsc + pytest green
- [ ] Frontend optional-chains the new field for historical packs

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Proposals overlap remediation (same WCAG step) | Med | duplicate-feeling output | Proposals are per-step & action-oriented; remediation stays per-criterion/trusted — different axes, both kept |
| Over-flagging (every amber → proposal) | Med | noise | Inclusion gate = red/amber OR confusion≥0.5; ranked so worst surface first |
| Historical packs lack `proposals` | High | frontend crash | Optional-chain in `Results` (Task 8 GOTCHA) |
| `max()` on empty confusion list | Low | ValueError | `max(..., default=0.0)` (Task 2 GOTCHA) |

## Notes
- The aggregator deliberately consumes `PersonaRunResult` objects (not the built pack dict) so it reuses `step_status`/`_step_blocks` directly on `StepSignals` with each persona's own thresholds — same input contract as `build_friction_matrix`/`build_remediation`.
- "Confusion matrix" in the request = the per-step `llm_confusion` stream (engine.py:41), already carried per persona×step; this feature is its first *actionable* consumer.
- Optional future enrichment: wrap each proposal's `fix` with an LLM narration call mirroring `synthesize` (llm.py:608-643) — gated on API key, falling back to the deterministic template. Explicitly out of scope here to keep the core deterministic and testable.
