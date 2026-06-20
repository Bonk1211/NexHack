# InclusionScope — Business Analyst Reference

## 1. WCAG Severity Framework (P0–P3)

### The Standard We Reference

WCAG 2.1 is the globally adopted standard. It has three conformance levels:

| Level | What it means | Who mandates it |
|---|---|---|
| A | Minimum baseline — fails = legally risky | EU Web Accessibility Directive, US Section 508 |
| AA | Target for commercial products | EN 301 549 (EU), MCMC Malaysia, most enterprise contracts |
| AAA | Enhanced — rarely mandated, aspirational | Specialist/government portals |

Malaysia's **EGAP (Electronic Government Activities Plan)** and MCMC reference WCAG 2.0 AA as the compliance baseline. Any Malaysian government-facing digital product is legally expected to meet this.

---

### Our P0–P3 Mapping

The industry has no universal P-number standard. Ours is derived from WCAG level + path criticality (whether the user is blocked on a flow they **must** complete).

| Severity | Triggers | Real-world meaning | Examples |
|---|---|---|---|
| **P0** | WCAG Level A violation on a critical path **OR** agent hard-blocked on critical step | User cannot complete the task at all. Legal exposure. | Missing form labels (4.1.2), keyboard trap (2.1.1), no alt text on a functional button (1.1.1), OTP with no timing adjustment (2.2.1) |
| **P1** | WCAG Level AA violation on critical path **OR** agent confused >70% + friction on critical step | Significant friction — user likely gives up or makes errors | Contrast failure on primary content (1.4.3), inaccessible error messages (3.3.1), focus not visible on interactive elements (2.4.7) |
| **P2** | WCAG Level A/AA on secondary path **OR** agent friction on non-critical step | Notable friction, degrades experience but task completable | Contrast on decorative elements, missing page title on non-landing pages (2.4.2), dense reading grade on supplementary copy |
| **P3** | WCAG Level AAA **OR** best practice | Enhancement opportunity — not a compliance risk | Enhanced contrast AAA (1.4.6), sign language (1.2.6), extended audio description |

**Critical path** = any step the user must complete to achieve the primary flow goal (checkout, login, claim reward). Non-critical = supplementary (help text, marketing content, footer links).

---

### Which WCAG Criteria Matter Most for Malaysian Apps

Based on WebAIM's annual screen reader survey and Malaysian OKU demographic data:

| Criterion | Failure rate in wild | Why it matters in MY context |
|---|---|---|
| 1.4.3 Contrast Minimum | 83% of homepages (WebAIM 2024) | OKU visual population: 199,189 registered (DOSM 2023) |
| 4.1.2 Name/Role/Value | 41% | Screen reader users cannot interact with unlabeled controls |
| 1.1.1 Non-text Content | 54% | Images-as-buttons common in Malaysian e-commerce/gov sites |
| 2.4.4 Link Purpose | 38% | "Click here" / "Read more" patterns extremely common locally |
| 3.3.2 Labels/Instructions | 29% | Forms without field-level instructions — common in legacy systems |

axe-core (which we run) detects ~57% of WCAG issues automatically (Deque's published figure). The remaining 43% require judgment — which is where our persona simulation layer adds value above a pure axe scan.

---

## 2. SHAP and LLM Credibility

### The Two-Stream Architecture (Why the LLM Cannot "Hallucinate" a Compliance Result)

This is the most important credibility design decision in InclusionScope.

```
TRUSTED stream  ─── axe-core violations, dwell time, dead_end flag
                         ↓
                    WCAG conformance verdict   ← P0/P1 severity
                    Inclusion score (math)     ← reportable, auditable

INDICATIVE stream ── LLM confusion score (0–1)
                         ↓
                    Behavioral friction flag   ← labeled "indicative"
                    Synthesis narrative        ← labeled "AI-generated"
```

**The LLM never touches the compliance score.** If the LLM API is offline, the WCAG result is identical. The LLM only contributes the "this persona would be confused here" signal — which is subjective, labeled as such, and additive to the objective result, never substitutive.

When presenting to judges or clients: **"Our WCAG verdicts are the same output you'd get from running axe-core, the tool used by Google Lighthouse, Deque, and Microsoft. We just run it on every page, for every persona, on every deployment."**

---

### Where SHAP Applies

SHAP (SHapley Additive exPlanations) is applicable to our **scoring formula** — the deterministic weighted combination that produces the inclusion score. This is the explainability layer we can build.

**Features feeding the score:**

| Feature | Source | Weight justification |
|---|---|---|
| WCAG failure count (trusted) | axe-core | Objective — directly maps to criterion violations |
| Critical block rate | dead_end on critical steps | Highest weight — user literally cannot proceed |
| Avg dwell ratio (persona dwell / threshold) | behavior model × reading load | HCI research: dwell > 2× expected = friction signal |
| Give-up count | dwell >= give_up_threshold_s | Nielsen Norman: 7s rule for unclear UI |
| Label failure rate | a11y tree label check | Proxy for screen-reader navigability |

SHAP waterfall on a run would look like:

```
Baseline score: 1.00
  − 0.15  WCAG 1.4.3 failure (contrast) on 2 pages
  − 0.08  2 of 5 personas hard-blocked at submit step
  − 0.04  p-siti dwell 3.2× expected on OTP screen
  − 0.03  2 unlabeled textboxes in profile form
  ─────────────────────────────────────────────
  = 0.70  Inclusion Score
```

This gives you a **court-defensible breakdown**: every deduction traces to a specific signal, not an LLM opinion.

**For the LLM's indicative output specifically:**

| Credibility mechanism | What it does |
|---|---|
| `temperature=0` | Same a11y tree → same confusion score every time. Reproducible. |
| Seeded RNG | Same run → same persona behavior → same dwell/give-up decisions |
| Graceful degradation | No API key → heuristic fallback. Results remain valid. |
| Labeled as indicative | Every LLM output is flagged in the report. Not conflated with WCAG. |
| Agreement check | When LLM confusion > 0.7 AND dead_end = True → high confidence finding |

**What to say when judges probe "but the AI might be wrong":**

> "The AI contributes only to the behavioral friction signal — whether a persona 'feels confused' at a given screen. That signal is labeled indicative. The compliance verdict — the P0 that determines whether a PR is blocked — comes entirely from axe-core, the same tool Google and Microsoft use. The AI cannot invent a WCAG violation."

---

## 3. Defending the Score: Why This Replaces (or Augments) Human UAT

### The Honest Position

Do not claim full replacement. Claim **augmentation with a clear coverage argument**:

> "InclusionScope replaces the repetitive, mechanical 80% of accessibility UAT. It frees human testers and OKU consultants to focus on the 20% that requires lived experience and judgment."

This is a stronger and more defensible position than "replaces humans entirely" — and it's the position that won't get dismantled in a 30-second cross-examination.

---

### The Five Pillars of Score Defensibility

**Pillar 1 — Reproducibility (we beat humans here)**

Human testers vary by fatigue, interpretation, tool settings, screen reader version. Our system:
- Same seed → identical run, always
- Persona behavior is deterministic (seeded RNG)
- axe-core version pinned

A WCAG auditor running the same test twice may get different results. We don't.

**Pillar 2 — Coverage (we beat humans on scale)**

| Human accessibility tester | InclusionScope |
|---|---|
| 1 persona perspective per test session | 5 personas, parallel, same run |
| Tests when hired (quarterly at best) | Tests every PR |
| RM15,000–50,000 per audit | Cents per run (LLM API costs) |
| 2–3 week turnaround | 3 minutes |
| Report as PDF, no integration | Blocks PR, posts findings in-line |

**Pillar 3 — Behavioral model is calibrated to published HCI research**

| Persona parameter | Research basis |
|---|---|
| `giveup_threshold_s` | Nielsen Norman Group: users abandon tasks after ~7-10s of confusion |
| `dwell_multiplier` | Reading load models: Flesch-Kincaid grade vs. reading speed (200 WPM baseline) |
| `requires_labels` | Screen reader dependency: JAWS/NVDA users navigate by form labels — documented in WebAIM SR Survey |
| OKU disabilities | WHO disability prevalence × Malaysian census → persona demographic weighting |

These are not invented parameters. They can be cited.

**Pillar 4 — The two-stream model mirrors how real audits work**

Professional accessibility audits already have two streams:
1. **Automated scan** (axe, WAVE, Lighthouse) — objective, fast, ~57% coverage
2. **Manual expert review** — subjective judgment on the remaining 43%

We replicate this exactly:
- Stream A (TRUSTED) = our automated axe scan — same as any professional audit
- Stream B (INDICATIVE) = our persona simulation = approximates the manual review layer

A certified WCAG auditor does the same thing. We just do it in 3 minutes instead of 3 weeks.

**Pillar 5 — We quantify what auditors leave qualitative**

A human auditor says: "Low vision users may struggle with this contrast ratio."
We say: "3 of 5 personas were blocked. Inclusion score dropped 15 points. Estimated excluded population: 199,000 registered OKU visual users in Malaysia."

The business impact framing converts a compliance checkbox into a revenue/risk number — which is what product managers and CFOs actually respond to.

---

### Handling the Hard Questions

**"Can your tool pass/fail WCAG AA certification?"**
> "No tool can certify WCAG conformance alone — not ours, not Google Lighthouse, not Deque's axe. Certification requires human judgment on the non-automatable 43%. What we do is run the same automated checks that underpin every professional audit, continuously, on every build — so by the time a certifier sees your product, the automatable issues are already fixed."

**"How do you know your persona simulation reflects real OKU users?"**
> "We don't claim it's a perfect model — we label it indicative. What we claim is that the behavioral parameters map to published research: reading speeds, task abandonment thresholds, screen reader dependency patterns from WebAIM's annual survey of 1,500 real screen reader users. The appropriate validation is a calibration study: run our tool alongside a real OKU user panel, measure recall and precision. That's our next research milestone."

**"Why not just hire OKU users to test?"**
> "You should — for final sign-off. But OKU user recruitment takes 3–6 weeks and costs RM8,000–20,000 per study. You can't run a user study on every PR. InclusionScope runs on every PR so that by the time OKU users see the product, the basic barriers are already gone. We make their time count."

**"The LLM could be biased or wrong."**
> "The LLM output is never the compliance verdict. It's the behavioral color commentary — 'this persona would be confused here.' If the LLM is wrong, the WCAG result is unaffected. If you disable the LLM entirely, P0/P1 verdicts are identical. The LLM makes the report richer and more human-readable. It doesn't determine pass or fail."

---

## 4. Competitive Positioning

| Tool | What it does | What we add |
|---|---|---|
| Google Lighthouse | Automated axe scan, performance | Persona simulation, CI gate, Malaysian demographic framing |
| Deque axe DevTools | Deep WCAG scan, manual testing workflow | Continuous CI integration, behavioral model, LLM synthesis |
| UserTesting.com | Real human panel testing | 100× faster, CI-native, costs cents not thousands |
| Manual WCAG audit | Human expert judgment | Speed, consistency, PR-level granularity |

**Our defensible position:** We are not a WCAG scanner (Lighthouse does that). We are not a human testing panel (UserTesting does that). We are the **continuous accessibility layer** that sits between every code change and every user — making both scanners and human panels 10× more effective by the time they see the product.

---

## 5. Recommended Validation Study (for credibility post-demo)

To move from demo-credible to enterprise-credible, run this study before pitching to paying clients:

1. Select 10 Malaysian web apps (5 known-good, 5 known-bad for accessibility)
2. Run InclusionScope on all 10
3. Run a parallel certified WCAG 2.1 AA audit by a human auditor
4. Measure: precision, recall, false positive rate on P0/P1 findings
5. Measure: correlation between inclusion score and auditor's overall rating

Target: >80% precision on P0 findings (we flag real issues), >60% recall (we catch most of what auditors find). Publish as a technical brief. That converts "interesting demo" into "defensible enterprise product."
