# InclusionScope — Slide Agent Brief
## NexHack 2026 · Track 1: Agentic AI for Internal Enterprise Operations

---

## PRODUCT CONTEXT (read before designing)

**Product name:** InclusionScope  
**One-line:** An autonomous AI agent that simulates how disabled Malaysian users experience your app — on every code deployment.

**What it does:**  
InclusionScope runs a LangGraph agent workflow that launches real Playwright browsers, simulates 3–5 persona types (elderly, OKU visual, low-tech, non-native speaker), navigates the target app, and produces a WCAG-grounded accessibility audit — automatically, on every PR via GitHub Actions.

**Why it matters:**  
- 608,523 registered OKU in Malaysia (DOSM 2023). Most enterprise apps exclude them silently.
- A certified human accessibility audit costs RM15,000–50,000 and takes 2–3 weeks.
- InclusionScope does the same in 3 minutes for cents.
- Findings land as developer tickets in Jira/GitHub, not a PDF no one reads.

**Technical stack:**  
- Backend: FastAPI + LangGraph (cyclic agent graph) + Playwright (real browser)
- AI: DeepSeek V4 Flash (per-step confusion judgment) + axe-core (WCAG conformance)
- DB: Supabase (runs, evidence packs, personas)
- Frontend: Next.js 14, live CDP screencast stream of each persona's browser
- CI: GitHub Actions → POST to backend → results posted back to PR as check + comment

**Two-stream trust model (critical to communicate):**  
- TRUSTED stream: axe-core violations + dwell time + dead_end flag → P0/P1 severity. Deterministic. Court-admissible.  
- INDICATIVE stream: LLM confusion score → behavioral friction signal. Labeled, never substitutes for WCAG verdict.  
- The LLM cannot hallucinate a compliance result. P0/P1 comes from axe-core only.

**Track alignment:** Track 1 — Agentic AI for Enterprise Operations (QA, compliance, product engineering teams)

---

## PRESENTATION CONSTRAINTS

- **Total time: 7 minutes** (strict — 2 marks deducted per 30s over)
- Format: demo video covering both app demo + slides
- Judges reward: depth over breadth, paying-customer logic, real technical execution

**Suggested time split:**
```
Slides 1–3  Problem + Market      ~1:00
Slide  4    Solution overview      ~0:30
Slide  5    Live demo              ~1:30   ← longest, most visual
Slide  6    Technical architecture ~0:45
Slide  7    Trust model + SHAP     ~0:30
Slide  8    CI/CD integration      ~0:30
Slide  9    Business case          ~0:30
Slide  10   Pricing + GTM          ~0:30
Slide  11   Roadmap                ~0:30
Slide  12   Close                  ~0:15
             Total                  ~7:00
```

---

## SLIDES — CONTENT & VISUAL DIRECTION

---

### SLIDE 1 — HOOK
**Title:** "Who is your app excluding right now?"  
**Visual:** Split screen. Left: a confident professional using a sleek banking app. Right: an elderly Malaysian woman squinting at the same app, unable to read the OTP field. No caption needed — let the contrast speak.  
**Speaker note:** Open with the uncomfortable question. No agenda slide. No "hi my name is." Drop them straight into the tension.

---

### SLIDE 2 — THE PROBLEM
**Title:** "Accessibility is a compliance deadline, not a design preference"

**Three columns:**
| The cost of ignoring it | The current solution | Why it breaks down |
|---|---|---|
| 608,523 registered OKU in Malaysia | Manual WCAG audit | RM15K–50K per audit |
| EU & MCMC compliance pressure | Hire OKU user testers | 3–6 week turnaround |
| Silent exclusion = lost users | Quarterly spot checks | Never on every PR |

**Visual:** A WCAG audit report PDF with a large red stamp: "ISSUED 3 MONTHS AFTER LAUNCH"  
**Subtext:** "By the time the audit lands, 6 sprints have shipped on top of it."

---

### SLIDE 3 — MARKET REALITY
**Title:** "The gap no tool fills today"

**Visual:** 2×2 matrix
```
                    FAST
                      │
     InclusionScope ──┼── (empty — this is us)
                      │
SHALLOW ──────────────┼────────────── DEEP
  Lighthouse/axe ─────┤
                      │
     Human audit ─────┼── OKU user panel
                      │
                    SLOW
```

**Three bullet points:**
- Lighthouse: automated scan only, no persona behavior, no CI blocking
- Human audit: deep but RM15K+, 3 weeks, no continuous integration
- OKU user panels: gold standard but unaffordable per-PR
- **InclusionScope: deep + fast + continuous**

---

### SLIDE 4 — SOLUTION
**Title:** "InclusionScope — Continuous accessibility intelligence"

**Visual:** Clean product hero screenshot (the project dashboard showing ScoreRing, persona dots, health badge on a project card)

**Three pillars (icon + headline + one line each):**
- 🤖 **Persona agents** — Real Playwright browsers simulating 5 disabled Malaysian user types
- ⚡ **Every deployment** — Runs on every PR via GitHub Actions, blocks P0s automatically
- 📋 **Developer-ready output** — Jira tickets, PR comments, evidence pack with screenshots

**One-liner at bottom:**  
*"Same WCAG standards as a certified auditor. 3 minutes. Cents per run."*

---

### SLIDE 5 — LIVE DEMO (longest slide / screen record)
**Title:** "Watch it run"

**Demo sequence to record (90 seconds):**
1. Open InclusionScope dashboard → show BrewPoints project card (score ring, persona dots, health badge) — 10s
2. Click into project → Run tab → hit "Run assessment" → live view activates — 10s
3. Show 3 PersonaColumn phone frames side by side, CDP screencast streaming — each persona's live browser visible — 20s
4. Graph node bar updating: observe → comprehend → decide → act — 10s
5. One persona gets blocked (red), two show friction (amber) — 15s
6. Run completes → switch to Results tab → inclusion score 70%, friction matrix, synthesis narrative — 15s
7. Cut to GitHub PR → show ❌ check "InclusionScope — 1 P0 · Low-vision users blocked at OTP step" + PR comment with persona table — 10s

**Design note:** This slide is mostly full-bleed screen recording. Minimal chrome. Let the product speak.

---

### SLIDE 6 — TECHNICAL ARCHITECTURE
**Title:** "Architecture built for trust, not just speed"

**Visual:** Clean flow diagram (horizontal, left to right)

```
GitHub PR
   │
   ▼
[GH Actions]
  curl POST
   │
   ▼
[FastAPI Backend]
  _resolve_flow()
   │
   ├──► [LangGraph Run Graph]
   │      init → fan_out
   │         │
   │    ┌────┴────┐
   │    ▼         ▼
   │  [Persona   [Persona
   │   Subgraph]  Subgraph]
   │  observe     observe
   │  comprehend  comprehend
   │  decide      decide
   │  act         act
   │    └────┬────┘
   │         ▼
   │      aggregate → score → evidence → alerts
   │
   ├──► axe-core (WCAG scan, per step)
   ├──► DeepSeek Flash (confusion judgment, per step)
   ├──► Supabase (evidence pack, screenshots)
   │
   ▼
GitHub API
  PR comment + Check run
```

**Three callouts:**
- **Playwright**: real headless Chromium — not a simulator, actual browser
- **LangGraph**: cyclic graph — agent loops until blocked or goal reached
- **axe-core**: industry-standard WCAG engine used by Google Lighthouse & Deque

---

### SLIDE 7 — TRUST MODEL + SHAP
**Title:** "Our scores are defensible, not just impressive"

**Visual:** Two-column layout

**Left column — Two-stream model:**
```
TRUSTED STREAM
axe-core violations
+ dwell time
+ dead_end flag
       ↓
  P0 / P1 severity    ← deterministic
  Inclusion score     ← auditable

INDICATIVE STREAM
LLM confusion 0–1
       ↓
  Behavioral friction ← labeled
  Synthesis narrative ← labeled AI
```

**Right column — SHAP waterfall (example):**
```
Baseline:          1.00
─ WCAG 1.4.3:    −0.15
─ 2 P0 blocks:   −0.08
─ Dwell excess:  −0.04
─ Label fail:    −0.03
──────────────────────
Inclusion score:  0.70
```

**Bottom callout:**  
*"The LLM cannot hallucinate a P0. Compliance verdicts come from axe-core only."*

---

### SLIDE 8 — CI/CD INTEGRATION
**Title:** "Accessibility as a merge gate, not an afterthought"

**Visual:** GitHub PR screenshot mockup showing:
- Status checks section
- ❌ `InclusionScope · Inclusion score 70% · 1 P0 issue` — Required — Failing
- PR comment with formatted table: persona | verdict | blocked at | WCAG failures

**Three bullets:**
- Triggers on every PR against the Vercel preview URL — zero manual steps
- P0 findings block the merge — the same way a failing unit test does
- Evidence pack attached as artifact — screenshots, WCAG details, LLM synthesis

**One-liner:**  
*"Accessibility regressions never ship. They're caught in the same pipeline as code bugs."*

---

### SLIDE 9 — BUSINESS CASE
**Title:** "The economics are obvious"

**Visual:** Three-column cost comparison

| | Human WCAG Audit | OKU User Panel | InclusionScope |
|---|---|---|---|
| Cost per test | RM15,000–50,000 | RM8,000–20,000 | ~RM2–5 |
| Turnaround | 2–3 weeks | 3–6 weeks | 3 minutes |
| Frequency | Quarterly | Annually | Every PR |
| CI integration | ❌ | ❌ | ✅ |
| Personas covered | 1–2 | Real users | 5 custom types |

**Bottom statement:**  
*"A team shipping 20 PRs/week runs 1,000+ audits per year for less than the cost of one human audit."*

**Secondary framing:**  
*"We don't replace OKU user panels — we make sure nothing embarrassing reaches them."*

---

### SLIDE 10 — PRICING + GTM
**Title:** "Priced for adoption, built for enterprise"

**Three tiers:**

| Tier | Target | Price | What's included |
|---|---|---|---|
| **Starter** | Indie / startup | RM199/mo | 5 apps, 500 runs/mo, 3 personas |
| **Growth** | SME product teams | RM799/mo | 20 apps, unlimited runs, 8 personas, Jira integration |
| **Enterprise** | Bank / GLC / gov | Custom | On-prem, custom personas, compliance reports, SLA |

**Go-to-market:**
1. **Land**: Malaysian fintech and e-government portals — both under active WCAG/MCMC compliance pressure
2. **Expand**: Any team using GitHub/Vercel/CI — developer-led adoption (no procurement)
3. **Moat**: Custom Malaysian persona library (language, OKU types, demographic weighting) — harder to replicate than the technical stack

---

### SLIDE 11 — ROADMAP
**Title:** "Built to survive beyond the demo"

**Timeline: 4 phases**

```
NOW (built)               Q3 2026               Q4 2026               2027
──────────────────────────────────────────────────────────────────────────
✅ LangGraph agent        Autonomous flow       Jira/Linear           On-prem
✅ Playwright stream        (no script needed)    ticket push           deployment
✅ WCAG scoring           Goal-directed nav     Remediation           SDK / API
✅ GitHub Actions CI        + page exploration    copilot               for any CI
✅ Evidence pack          Malaysian persona     Validation study      Cert-ready
✅ Dashboard + personas     library expansion     with OKU panel        reports
```

**One callout box:**  
*"Nearest term unlock: autonomous flow navigation. Agent is given a goal ('claim reward'), explores the UI itself, no flow script needed. Eliminates the last manual configuration step."*

---

### SLIDE 12 — CLOSE
**Title:** "Every Malaysian app has a silent exclusion problem. We make it visible."

**Visual:** Full-bleed — the InclusionScope inclusion score ring, large, centered. Score showing 70%. Below it: "BrewPoints · 5 personas · 3 min · RM0.04"

**Three lines only:**
- 608,523 OKU users in Malaysia deserve to use the same apps everyone else does.
- Every team shipping code deserves to know who they're excluding before it ships.
- InclusionScope closes that gap — automatically, continuously, affordably.

**Bottom right:** GitHub repo URL + deployment link

---

## DESIGN DIRECTION FOR SLIDE AGENT

**Visual language:**
- Dark background preferred (#0a0a0f or similar deep navy/black) — feels enterprise + technical
- Accent: orange (#d97a2b) for key numbers, CTA elements, score rings
- Secondary: blue (#0066cc) for trusted/WCAG elements
- Typography: clean sans-serif, large numbers for impact (score percentages, cost figures)
- No clip art. No stock photos of hands shaking.

**Tone:** Confident, technical, commercially serious. Not academic. Not startup-hype.  
Speak to judges who are enterprise builders and fintech operators — not students showing a side project.

**Diagram style:** Clean node-and-edge architecture diagrams. Monospace labels. Not PowerPoint SmartArt.

**Screenshots to embed:**
- Project dashboard (card view with score rings)
- Live run view (phone frames with CDP stream)
- GitHub PR check (❌ failing with findings)
- Evidence pack / results tab (friction matrix + persona verdicts)

**What to avoid:**
- Buzzword soup ("leveraging cutting-edge AI synergies")
- Placeholder lorem ipsum — every word counts in 7 minutes
- Slide transitions that eat time
- More than 6 bullet points on any slide
