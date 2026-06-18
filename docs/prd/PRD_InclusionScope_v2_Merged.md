# PRD — Inclusion & Accessibility Assurance Agent

*Working name: **InclusionScope** (rename freely)*

| | |
|---|---|
| **Event** | NexHack 2026 (sponsor & host: Xenber Sdn. Bhd.) |
| **Track** | Track 1 — Agentic AI for Internal Enterprise Operations (via **Compliance**) |
| **Status** | **v2.0 — merged.** Strategy from the compliance PRD; engineering folded in from the implementation plan; conflicts resolved. |
| **Supersedes** | PRD draft v1.0 and `implementation.md` (Navigability Auditor). This is the single source of truth. |
| **Team size** | 1–3 |

---

## 0. Read this first — what NexHack actually grades

We are **not** optimizing for the Deriv brief. NexHack's rubric is commercial-heavy. Total **130 marks**:

| Criterion | Marks | Where this product must win |
|---|---|---|
| Problem Relevance & Impact | 20 | Named regulated buyer + measurable inclusion/compliance pain |
| Technical Architecture, Execution & Completeness | 30 | End-to-end agentic flow that actually runs |
| Market Adoption & Commercial Potential | 30 | Clear buyer, pricing, adoption path, compliance fit |
| Innovation & Differentiation | 30 | Agentic persona simulation + audit evidence — not a scanner, not a chatbot |
| Presentation & Demonstration | 20 | The empathy-replay wall + auto-generated evidence pack |

**~90 of 130 marks (Problem + Market + Innovation) cannot be won by a pretty demo.** The brief says solutions "should not merely look impressive." So the **engine, the evidence pack, and the commercial story are first-class**; the wall is polish.

> **Resolved scope discipline (the one rule the build plan must obey):** build effort follows the marks. We **do not** build collectible figurines, a multi-project management CRUD, or a Lighthouse-per-screen pipeline. Those earned zero rubric marks and competed for the time the evidence pack needs. They are cut. See §21, §23.

Requirements are tagged **[MVP]** (no submission without it) or **[STRETCH]** (only if MVP is solid).

---

## 1. One-liner / positioning

> An autonomous agent that runs a consumer app through simulated **vulnerable-user personas** (elderly, OKU/disabled, low-literacy, non-native speaker, low-end device), measures where each is blocked using **real accessibility signals**, and generates **continuous compliance evidence** that the app meets inclusion and accessibility obligations — work compliance teams do today through slow, periodic manual audits.

We are **not** pitching "a UX/QA tester." We're pitching **inclusion assurance as audit evidence**.

---

## 2. Problem statement (compliance framing)

Regulated consumer apps — banking, fintech, government services — are under growing obligation to be usable by vulnerable and underserved populations, not just the median tech-savvy adult. Today, proving that is:

- **Manual** — periodic accessibility audits and recruited user-research panels.
- **Slow & expensive** — quarterly at best; can't keep up with release velocity.
- **Stale** — every release can silently break access for a protected group, and nobody knows until the next audit or a complaint.

The result: apps silently exclude elderly, disabled, low-literacy, and non-native users at specific steps (OTP, document upload, dense forms) — simultaneously a **conversion loss**, a **financial-inclusion gap**, and a **compliance exposure**.

---

## 3. Why now (grounding — keep this real, don't oversell)

- **BNM financial-inclusion expectations.** Bank Negara Malaysia expects digital banks to identify and serve underserved segments — low financial literacy, language barriers, persons with disabilities, hard-to-reach customers. *This is your persona list, defined by the regulator.* It's an active supervisory expectation, not aspirational law — the strongest lever.
- **PWD Act 2008 (Malaysia), Article 28 / Section 30** — right to access ICT and digital platforms; essential services including digital platforms should be accessible to persons with disabilities.
- **WCAG 2.1 / 2.2 AA** — the de-facto standard banks and regulators reference.
- **Global regulatory wave** — ADA Title II (public-sector apps → WCAG 2.2 AA), EU EAA, etc., expose any firm with overseas users.

> ⚠️ **Honest caveat to carry into the pitch:** Malaysian digital-accessibility law is **weakly enforced today** — do *not* pitch "you'll be fined." The credible why-now is BNM supervisory expectation (real) + reputational/ESG risk + global exposure + "10x cheaper than a manual audit." The stick is soft; the pull is regulator expectation, cost, and reputation.

---

## 4. Target market & buyer

| Tier | Buyer | Why they pay |
|---|---|---|
| **Beachhead** | Software agencies (e.g., **Xenber**) shipping consumer apps to regulated clients | Certify inclusion before client handover; differentiate delivery; fastest sales cycle |
| **Primary** | Compliance / risk + digital-banking ops at fintechs & digital banks | Continuous evidence for BNM inclusion expectations; cheaper than manual audits |
| **Tertiary** | Government digital-services teams | PWD Act / public-sector accessibility obligations |

Compliance buyers are slow; agencies are not. Land via agencies, expand into their banking clients.

---

## 5. Goals & success metrics

| Goal | Metric | Baseline (manual) | Target (agent) |
|---|---|---|---|
| Continuous coverage | Inclusion checks per release | ~1/quarter (audit) | every release / on-demand |
| Cut audit cost | Cost per inclusion assessment | manual audit $$$ | fraction, automated |
| Catch exclusion early | Time from "release breaks a group" → flagged | until next audit/complaint | minutes |
| Evidence on demand | Auditable evidence pack generated | days of consultant work | auto-generated |
| Coverage breadth | Protected segments tested per run | 1–2 (whoever was recruited) | full persona library |

> Where you can't cite real audit costs, state the assumption explicitly ("a manual audit runs RM X over Y weeks; we run continuously at near-zero marginal cost"). A stated assumption beats hand-waving.

---

## 6. Non-goals

- ❌ Not a replacement for formal audits or **real disabled-user testing** — we augment and generate continuous evidence *between* audits. (Critical for credibility — see §23.)
- ❌ Not a general QA/bug tool — scope is inclusion/accessibility, done deeply.
- ❌ Not production testing — staging/UAT or a provided build only.
- ❌ Not auto-fixing — we detect, evidence, and route remediation. We don't patch.
- ❌ Not desktop-first — mobile (web view / emulation) is the priority.
- ❌ **Not a gimmick layer** — no collectible figurines, no decorative avatars, no multi-tenant project-management console. The empathy replay carries the emotional weight, not character art.

---

## 7. Personas — protected-access segments

Configurable per app; this is the **compliance-relevant default library**. Each persona = a **behavior model** + a **different pass/fail threshold** on the same screen. Without both, it's the same test in a costume (see §23).

| Persona | Behavior model | Failure threshold lens |
|---|---|---|
| Elderly / low-digital-literacy | Slow, cautious, needs large tap targets, abandons on ambiguity | High dwell + no clear next action = fail |
| OKU — visual (low-vision/blind) | Depends on contrast, labels, screen-reader semantics, focus order | Contrast < WCAG AA, missing labels, broken focus = fail |
| OKU — motor | Needs large targets, tolerant timing, no precision gestures | Small/overlapping targets, tight timeouts = fail |
| OKU — hearing | Needs captions/text alternatives for audio cues | Audio-only critical info = fail |
| Low-literacy | Struggles with dense text, jargon, unlabeled fields | Reading load / ambiguity high = fail |
| Non-native speaker (BM/EN/中文/தமிழ்) | Hits untranslated keys, truncated strings, broken layout | Localisation breakage = fail |
| Low-end device + slow network | Slow render, timeouts, layout breakage | Step latency / layout failure = fail |
| *Median adult (control) — optional* | Baseline competent user, no impairment | Used only to show "passes for baseline, blocks protected group." **Not** a tech-savvy power user. |

> **Resolved:** the "techie vs auntie" contrast from the build plan is dropped. A power user is not a protected group, and that contrast tells a conversion story, not an exclusion story. If a passing reference is wanted, use the labeled **control** persona above.

---

## 8. System architecture

```
            ┌────────────────────────────────────────────────────┐
            │            Orchestrator (per-app run)              │
            │   selects persona library + flow + device/lang     │
            └───────────────┬────────────────────────────────────┘
                            │ launches one agent per persona
            ┌───────────────▼────────────────────┐
            │  PERSONA NAVIGATION AGENT (xN)      │
            │  - Playwright mobile emulation      │
            │  - a11y-tree drives navigation      │
            │  - Vision LLM: per-screen comprehension judgment + nav fallback │
            │  - persona behavior + thresholds (seeded RNG) │
            │  - screenshot every step            │
            └───────────────┬────────────────────┘
                            │ per step, TWO signal streams ▼
        ┌───────────────────┴───────────────────┐
        │                                        │
┌───────▼─────────────┐              ┌───────────▼──────────────┐
│ A) ACCESSIBILITY     │              │ B) BEHAVIORAL SIGNALS    │
│    SIGNALS (TRUSTED) │              │    (INDICATIVE)          │
│ - contrast ratio     │              │ - completion / blocked   │
│ - label presence     │              │ - dwell, retries         │
│ - tap-target size    │              │ - dead-ends, backtrack   │
│ - focus order        │              │ - LLM "I don't know what │
│ - WCAG 2.x (axe-core)│              │   this field wants"      │
└───────┬──────────────┘              └───────────┬──────────────┘
        └───────────────────┬────────────────────┘
                            ▼
            ┌───────────────────────────────────┐
            │  SCORING ENGINE (§16)              │
            │  emits A and B SEPARATELY +        │
            │  optional composite; severity P0–P3│
            └───────────────┬───────────────────┘
                            ▼
   ┌────────────────────────┼───────────────────────────┐
   ▼                        ▼                           ▼
┌─────────────────┐  ┌──────────────────┐   ┌──────────────────────┐
│ EVIDENCE PACK   │  │ DASHBOARD WALL    │   │ ALERTS + ROUTING      │
│ (compliance     │  │ + empathy replay  │   │ persona blocked →     │
│  output, §13)   │  │ + friction matrix │   │ tag owning area (§9.4)│
└─────────────────┘  └──────────────────┘   └──────────────────────┘
```

The two-stream design is the spine: **stream A is machine-verifiable and trustworthy** (the credible core a compliance officer relies on); **stream B is the persona-simulation differentiator** (labeled indicative). Keeping them distinct is what protects the product from the "it's just a costume" critique — see §16 for how the scorer enforces this.

**Navigation method (resolved):** the accessibility tree drives navigation (robust, cheap, and it *is* the trusted signal source). The vision LLM is used for per-screen comprehension judgment (the indicative "I don't know what this field wants" signal) and as a navigation fallback when the a11y tree is insufficient. Screenshots are captured every step regardless, which is what powers empathy replay — so the differentiator does not depend on vision-driven navigation.

---

## 9. Functional requirements

### 9.1 Persona navigation
- **FR-1.1 [MVP]** Load the target app in a **mobile-emulated viewport** (Playwright device descriptor).
- **FR-1.2 [MVP]** Agent navigates the flow via the **accessibility tree**, parameterized by the persona behavior model; **vision LLM** provides per-screen comprehension judgment and is the navigation fallback.
- **FR-1.3 [MVP]** Capture a **screenshot every step** (feeds empathy replay + evidence).
- **FR-1.4 [MVP]** Run **≥3 personas** over the same flow (MVP); full library is stretch.
- **FR-1.5 [STRETCH]** Throttled network (CDP) for the low-end/slow-network persona.
- **FR-1.6 [STRETCH]** Second-language run for the non-native persona (localisation breakage).

### 9.2 Dual-signal capture
- **FR-2.1 [MVP]** Per step, extract **accessibility signals** (trusted): contrast, label presence, tap-target size, focus order (§10).
- **FR-2.2 [MVP]** Per step, capture **behavioral signals** (indicative): completion/blocked, dwell, retries, dead-ends, first-person confusion note.
- **FR-2.3 [MVP]** Behavior driven by a **seeded RNG** so runs are reproducible.

### 9.3 Scoring
- **FR-3.1 [MVP]** WCAG 2.x conformance per step (pass/fail per criterion tested) — reported **as its own trusted result**.
- **FR-3.2 [MVP]** Per-persona **completion verdict** + severity P0–P3 (§12), labeled **indicative**.
- **FR-3.3 [MVP]** Produce the **persona × step friction matrix** (the hero artifact).
- **FR-3.4 [MVP]** Scoring is a **pure, seeded, unit-tested function** with **visible tunable weights** (§16).

### 9.4 Evidence & routing
- **FR-4.1 [MVP]** Generate a **compliance evidence pack** (§13) — structured, exportable (PDF/JSON), not a log file.
- **FR-4.2 [MVP]** Live **dashboard wall** with per-persona panels + **empathy replay** (§14) + friction matrix.
- **FR-4.3 [MVP]** Live **alert** (Slack or in-dashboard) when a persona is **blocked**, with evidence + **owning area routed** (frontend / content / i18n / backend).
- **FR-4.4 [STRETCH]** Trend over releases ("this release broke low-vision access at OTP").

> **Resolved:** alerting/routing (FR-4.3) was missing from the build plan, where "escalation" had been redefined as a vision-model fallback. The human-routing alert is reinstated as MVP; the vision mechanism is called "fallback," not "escalation."

---

## 10. Accessibility signal spec (the trusted core)

Machine-verifiable, mapped to WCAG so it stands up as evidence:

| Signal | Source | WCAG anchor |
|---|---|---|
| Contrast ratio | computed style / pixel sampling | 1.4.3 Contrast (Minimum) |
| Label presence on inputs/controls | a11y tree / `aria-label`, `<label>` | 1.3.1, 4.1.2 Name/Role/Value |
| Tap-target size | bounding box | 2.5.8 Target Size |
| Focus order / keyboard reachability | tab order traversal | 2.4.3 Focus Order |
| Text alternatives for non-text | `alt`, captions | 1.1.1 Non-text Content |
| Untranslated / truncated strings | string + layout diff | (localisation, supports inclusion) |

> Use **axe-core** for the static checks; layer the agentic journey on top. Your novelty is the **persona journey + evidence**, not the contrast checker. **Lighthouse is not used for MVP** (slow, flaky per-screen subprocess; marginal gain) — stretch only.

---

## 11. Persona behavior + threshold spec

Each persona is a config object: a **behavior profile** for the navigation agent + **threshold overrides** for the scorer.

```json
{
  "persona": "elderly_low_literacy",
  "behavior_prompt": "Move slowly, read everything, prefer large clear buttons, give up if the next step is ambiguous after ~30s.",
  "behavior_profile": { "dwell_multiplier": 1.8, "hesitation_prob": 0.4, "reading_speed_wpm": 120, "giveup_threshold_s": 30, "retry_limit": 2 },
  "thresholds": { "max_dwell_s": 30, "min_tap_target_px": 48, "max_reading_grade": 8 },
  "weighting": { "ambiguity": "high", "latency": "medium" }
}
```

The same screen yields different verdicts across personas — that difference *is* the insight. All randomness is injected via a **seeded RNG** so tests and demos are deterministic.

---

## 12. Severity model

| Severity | Definition | Example |
|---|---|---|
| **P0** | Persona fully blocked; cannot complete flow | Low-vision user can't submit because control is unlabeled |
| **P1** | Major exclusion; likely abandonment | Contrast fails AA on primary CTA; tap target too small for motor persona |
| **P2** | Significant friction; high confusion | Dense unlabeled form; ambiguous copy for low-literacy persona |
| **P3** | Minor / cosmetic | Non-blocking untranslated string |

Severity = (protected-group impact × step criticality). A blocker on KYC ≫ a cosmetic issue in a footer.

---

## 13. Evidence pack spec (the compliance output — the "Usefulness" win)

The differentiated output. **This is the highest-priority build item; it has no equivalent in the original build plan and carries the marks a demo can't.** Per app, per run:

- **Executive summary**: pass/fail per persona, headline exclusions, overall inclusion score.
- **Persona × step friction matrix** (green/amber/red, dwell + verdict per cell).
- **WCAG findings** (trusted): each failure mapped to a criterion, with the screenshot.
- **Empathy-replay clips**: short recordings showing the screen *as the persona experiences it* (proof, not assertion).
- **Remediation list**: prioritized by severity, routed to owning area (frontend / content / i18n / backend).
- **Trend** (stretch): conformance over the last N releases.
- **Export**: PDF/JSON evidence artifact suitable for an audit trail.

```json
{
  "app": "...", "run_at": "ISO-8601", "inclusion_score": 0.71,
  "wcag_conformance": { "1.4.3": "fail", "1.3.1": "fail", "2.5.8": "pass" },
  "personas": [
    { "persona": "oku_visual", "verdict": "blocked", "severity": "P0",
      "blocked_at": "otp_step", "wcag_failures": ["1.3.1","4.1.2"],
      "behavioral_note": "indicative — agent could not locate a labeled OTP field",
      "evidence": { "screenshot": "...", "replay": "..." } }
  ],
  "remediation": [ { "issue": "OTP field unlabeled", "owner": "@frontend", "severity": "P0" } ]
}
```

Note the structure keeps `wcag_conformance` (trusted) distinct from `behavioral_note` (indicative) — see §16.

---

## 14. Dashboard & empathy replay (the demo surface — Presentation 20)

- **Persona wall**: one panel per persona, status + live/replayed run.
- **Empathy replay** (the centerpiece): render the screen *through the persona's lens* — low-vision contrast/blur filter, colorblind filter, enlarged-tap-target overlay, slowed interaction. A judge watching a button disappear under a low-vision filter understands the exclusion in one second. Runs on the per-step screenshots; no figurines, no character art.
- **The diff is the hero**: the friction matrix showing the *same screen* passing for the control and blocking a protected group.
- **"Who are we excluding" rollup**: one business line — "This app silently blocks low-vision and elderly users at OTP."

---

## 15. Tech stack (resolved)

| Layer | Choice | Note |
|---|---|---|
| Backend | **Python / FastAPI** | one language for the AI glue |
| Frontend | **Next.js** | persona wall + empathy-replay surface + matrix |
| Store | **Supabase (Postgres + Storage)** | entities/results + screenshots/replays; trend (stretch) |
| Browser + mobile | **Playwright** (device descriptors + CDP throttling) | mobile **emulation**, not a real emulator |
| Static a11y | **axe-core** | trusted WCAG signals; don't rebuild contrast/label math |
| Navigation | **a11y-tree primary** | robust + cheap; is also the trusted signal source |
| Per-screen comprehension + nav fallback | **Vision LLM** | the indicative confusion judgment; fallback when a11y tree insufficient |
| Reasoning / scoring synthesis + evidence JSON | **LLM + structured outputs** | once-per-run heavier reasoning |
| Alerts | Slack API or in-dashboard | live "persona blocked" + owner routing |
| Reproducibility | **seeded RNG** | deterministic runs/tests |

> **Open decision — model family.** Two candidates carried from the source docs: the **GPT-5.x line** (mini/nano for per-step, larger for reasoning) or **DeepSeek V4** (Flash for per-step, Pro for synthesis). Pick one on available credits + structured-output reliability, then **lock it** — don't run both. **Verify current model availability and pricing before locking** (model lineups move fast). Two-tier (cheap for per-step vision, larger once per run) saves cost either way.

> Cost note: vision is one image+LLM call per step × personas × runs. Downscale screenshots; reserve the larger model for once-per-run reasoning; cache the stable system-prompt prefix.

---

## 16. Scoring engine spec (the resolved core)

The original PRD demanded two separated streams; the build plan fused them into one `confusion_score`. **Resolution: keep the build plan's pure, seeded, testable scorer, but it must never collapse the trusted stream into the composite.** The engine emits three things:

1. **WCAG conformance result (TRUSTED)** — per-criterion pass/fail, straight from axe-core + the a11y signals. Reported on its own. A compliance officer can rely on this without trusting the simulation.
2. **Per-persona behavioral/completion verdict (INDICATIVE)** — blocked/completed + dwell/retries/confusion, explicitly labeled indicative.
3. **Composite inclusion score (OPTIONAL, derived)** — a convenience roll-up `w1·behavioral + w2·wcag + w3·llm`, normalized 0–1, with **visible tunable weights**. Never shown without the two underlying streams available.

```
score(signals) -> { wcag_conformance, persona_verdict, composite }   # pure, no I/O
```

Properties (non-negotiable):
- **Pure function**, zero I/O — exhaustively unit-testable.
- **Seeded RNG** for any persona hesitation, so outputs are deterministic.
- **Weights live in config and are surfaced in the UI** (defensibility).
- The composite is **derived from**, never a **substitute for**, the separated streams.

Why this matters: a single fused number is exactly what a compliance buyer cannot trust — you can no longer point to the machine-verifiable part. Keeping stream A reportable on its own is the credibility defense.

---

## 17. Data model

```sql
apps          (id, name, staging_url, viewport, created_at)
personas      (id, name, age_band, tech_savviness, patience, language,
               disabilities jsonb, behavior_profile jsonb, thresholds jsonb,
               created_at)                              -- global library
app_personas  (app_id, persona_id)                     -- many-to-many
runs          (id, app_id, mode, status, started_at, finished_at,
               inclusion_score)
run_personas  (id, run_id, persona_id, verdict, severity, completed bool, status)
screen_events (id, run_personas_id, step_idx, url, action, dwell_ms,
               backtracked bool, axe_violations jsonb, wcag_conformance jsonb,
               llm_judgment jsonb, severity, screenshot_url, created_at)
evidence_packs(id, run_id, summary jsonb, matrix jsonb, remediation jsonb,
               pdf_url, json_url, created_at)
```

`behavior_profile jsonb` = `{ dwell_multiplier, hesitation_prob, reading_speed_wpm, giveup_threshold_s, retry_limit }`; `thresholds jsonb` = the per-persona pass/fail overrides. Together they turn "70-year-old auntie" from a label into measurably different agent behavior **and** a different verdict on the same screen.

> **Resolved:** the build plan's `figurine_url / figurine_prompt / figurine_status` fields and the entire image-generation pipeline are **removed**. The `evidence_packs` table is **added** — it didn't exist before and is the primary output.

---

## 18. Innovation & differentiation (30 marks)

Win this axis by occupying the **middle** incumbents don't:

| Existing approach | What it does | Gap you fill |
|---|---|---|
| Static a11y scanners (axe/Deque) | Check code-level WCAG on a page | Don't *complete journeys* as a vulnerable user; no persona context |
| Human research panels (UserTesting) | Real users run real journeys | Slow, expensive, periodic; can't run every release |
| Digital-adoption platforms (Pendo/WalkMe) | Measure friction *after* launch from real traffic | Retroactive; not demographic/compliance-framed |

**Your one-liner:** *agentic, persona-simulated, end-to-end flow completion that outputs continuous compliance evidence.* Agentic + explainable + proactive + domain-specific — what NexHack rewards over "just a chatbot."

---

## 19. Commercial (30 marks)

**Pricing**
- One-off **onboarding audit** per app (setup + first evidence pack).
- Recurring **per-release / continuous monitoring** subscription.
- **Evidence-pack generation** (per audit artifact) for compliance/reporting cycles.

**Go-to-market / adoption path**
1. **Agencies first** (Xenber as design partner / first customer) — inclusion gate before client handover. Fast cycle, warm sponsor relationship.
2. **Expand to their regulated clients** (digital banks, fintechs) — compliance monitoring tied to BNM inclusion expectations.
3. **Government digital services** — PWD Act / public-sector obligations.

**Roadmap (capability, not calendar)**
Agency inclusion gate → fintech continuous compliance monitoring → multi-language/region expansion → trend analytics & audit-ready reporting → integrations (CI, ticketing).

> This section is a **prelim deliverable**, not just a build note. 30 marks live here and they cannot be coded.

---

## 20. Demo plan (prelim 7-min video + final live)

1. Launch the persona wall against a target app (a deliberately exclusion-flawed build, so failures are reproducible).
2. Watch ≥3 personas run; one hits a **P0 block** (e.g., low-vision blocked at an unlabeled OTP).
3. **Empathy replay** shows the screen through that persona's eyes — the exclusion is visible, not asserted.
4. The **evidence pack** auto-generates (WCAG findings + matrix + remediation) and a **live alert** fires with the owning area tagged.
5. Close on the business line + commercial slide (buyer, pricing, roadmap) — because ~60 marks live there.

> Don't stake the demo on emergent live navigation. Plant a reproducible flaw; keep 2–3 panels truly live, the rest replayed, plus a recorded fallback. Run **sequential** mode for clean narration. Pre-seed personas. No figurines.

---

## 21. Build priority (marks-ordered)

Ordered by rubric payoff, not calendar. Ship top-down; stop adding when prelim is met.

1. Schema (minimal, §17) + **scoring function** (pure, seeded, unit-tested — §16).
2. A11y-tree nav loop over a **planted-flaw fixture site** + axe-core signals + screenshot every step.
3. Persona behavior models + **per-persona thresholds** (one shared threshold defeats the whole thesis).
4. Dual-stream capture → **friction matrix** → **evidence pack export** (PDF/JSON).
5. **Empathy replay** on the captured frames + the persona wall.
6. Live **alert + owner routing** on a P0 block.
7. **Commercial one-pager** + 7-min video.

**Explicitly cut (do not build):** collectible figurines + image pipeline; full project/repo management CRUD; Lighthouse-per-screen; design-token lint gate; parallel-mode polish.

**Stretch, only if 1–7 are solid:** network throttling (low-end persona); second-language run; trend-over-releases; one real OKU user sanity-checking one persona's findings (massively strengthens the validity story — §23).

> **Scheduling note (resolved from the build plan's conflict):** the prelim deadline is earlier than the final. Treat **items 1–7 as the prelim target** (working core + evidence pack + video + commercial); reserve stretch + hardening + live polish for the final. The original 11-phase plan overshot the prelim — this ordering fits inside it by cutting the non-scoring work above.

---

## 22. Testing approach (folded, trimmed)

TDD is kept **where it earns marks and prevents demo failure**, not everywhere:

- **Scoring function** — full branch coverage, hand-crafted signal inputs, deterministic under a fixed seed. This is the defensible IP; test it hardest.
- **Contract tests** — Playwright loop against a committed **local fixture site with planted violations**, asserting known issues are caught and a clean control screen returns none.
- **Integration** — FastAPI routes against a test Postgres; LLM mocked.
- **E2E smoke** — one full run, one persona, fixture site, asserting a run + evidence pack persist.

> **Resolved:** the build plan's strict red-green-refactor across all 11 phases is relaxed. Full TDD on every CRUD route is time the evidence pack needs. Keep it on the scorer and the contract layer.

---

## 23. Risks & mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **Validity / "it's just a costume"** — does a simulated persona predict real vulnerable-user experience? | **High** | Lead with stream A (machine-verifiable WCAG) as the trusted core; label stream B as *indicative*; **never collapse A into the composite** (§16). Position as augmenting + generating evidence **between** audits — never "replaces real disabled testers." Overclaiming kills credibility with the exact buyer. A single real OKU sanity-check (stretch) hardens this. |
| Weak MY enforcement undercuts "you must buy" | Medium | Anchor on BNM inclusion *expectations* + cost-vs-audit + reputational/global exposure, not legal threat |
| Compliance buyers are slow | Medium | Agency beachhead (fast cycle); "evidence generation" is concrete, not aspirational |
| Scope creep / nothing finished | High | Strict MVP/STRETCH + the §21 cut list; one flow + 3 personas + evidence pack end-to-end before any stretch |
| Multi-persona cost & demo flakiness | Medium | 2–3 live + rest replayed; recorded fallback; downscale screenshots; sequential narration |
| Reads as QA tool, not compliance | Medium | Every artifact framed as audit evidence; buyer = compliance, not QA |
| **Effort misallocated to polish** (the build plan's original failure mode) | **High** | The §21 cut list is binding: no figurines, no CRUD console, no Lighthouse. Build the engine + evidence + commercial first. |

---

## 24. Rubric mapping (how each piece earns the 130)

| Feature | Problem (20) | Tech (30) | Market (30) | Innovation (30) | Presentation (20) |
|---|---|---|---|---|---|
| Compliance framing + BNM/PWD grounding | ●●● | | ●● | | |
| Dual-stream agentic engine (separated A/B) | | ●●● | | ●●● | |
| WCAG evidence pack (PDF/JSON) | ● | ●● | ●●● | ●● | ● |
| Persona × step friction matrix | ● | ● | | ●● | ●● |
| Empathy-replay wall | | | | ● | ●●● |
| Alert + owner routing | | ● | ● | ● | ● |
| Pricing + agency GTM + roadmap | ●● | | ●●● | | |

Balance check: the **engine + evidence pack + commercial story** carry ~90; the wall is presentation polish. The build order in §21 follows this. Don't invert it.

---

## 25. Open decisions

- **Model family** — GPT-5.x line vs DeepSeek V4. Decide on credits + structured-output reliability; verify current availability; **lock one** (§15).
- **Navigation wow-factor** — resolved to a11y-tree-primary + vision judgment. If the team wants the literal "agent navigates by looking," that's vision-first: more flaky/expensive, and the differentiator survives either way because empathy replay runs on screenshots.
- **Target demo app** — which app to run against? Ideally one with real, reproducible exclusion flaws, or plant them in a sample build.
- **WCAG version** — target 2.1 AA (broadly referenced) or 2.2 AA (newer, stricter)?
- **CAPTCHA/OTP** — run against a staging/sample build with these mocked/disabled.
- **Xenber as design partner** — frame Xenber as the beachhead customer in the pitch (it's their hackathon; leaning into their portfolio is a strength).

---

*Honest through-line: this product only wins if the **evidence is trusted and the buyer is real**. The empathy-replay wall gets you the room; the WCAG-grounded evidence pack and the compliance buyer get you the ~60 marks a demo can't. Build the engine and the evidence, not the wall — and definitely not the figurines.*
