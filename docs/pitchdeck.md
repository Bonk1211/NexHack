# InclusionScope — Pitch Deck

18 slides, full content, ready to feed into a slide-generation tool. No cross-references, no "see other doc" pointers — every slide is self-contained. Supporting notes, open questions, and full source citations live in `extra_info_slide.md`, not here.

---

## SLIDE 1 — COVER / HOOK

**Title:** Who is your app excluding right now?

**Subtitle:** InclusionScope — continuous, AI-driven accessibility auditing that blocks bad code before it ships.

**Visual:** Split screen. Left: a confident professional using a sleek banking app. Right: an elderly Malaysian woman squinting at the same app, unable to read the OTP field. No caption needed — let the contrast speak.

**Footer tag:** NexHack 2026 → Xenber Accelerator Track

---

## SLIDE 2 — THE PROBLEM

**Title:** Meet Makcik Salmah

**Visual:** Portrait — the same elderly Malaysian woman from the cover slide, now named. She's seated with her phone, warm but tired expression, mid-squint at the screen.

**Two headline pain points (bold, large type):**
- Text Too Small to Read. Buttons Too Small to Tap.
- One Confusing Screen From Giving Up — Could Be Your Own Parents

**Grounding line:**
She's 68, low-vision, and just wants to order food on her own — but at checkout, the "Pay Now" button fades into the background, and she gives up two taps from finishing.

**Footer stat:**
Makcik Salmah represents 805,509 registered Malaysians with disabilities [1] — and every elderly, low-vision, or low-literacy user your app was never tested against.

---

## SLIDE 3 — WHY NOW

**Title:** The pressure is real, specific, and starting now — not hypothetical

**Four pressure points:**

1. **Scale is bigger than assumed, and growing fast.** Malaysia's registered disability population grew 674,548 (2022) → 736,607 (2023) → 805,509 (2024) [1] — a 19.4% increase in two years. This is a fast-growing customer segment enterprise apps are systematically failing, not a shrinking niche.

2. **The web is failing accessibility at a shocking baseline rate.** The WebAIM Million 2026 audit of the top 1M home pages found 95.9% had detectable WCAG failures — 83.9% had low-contrast text failures alone, 53.1% had images missing alt text, 51% had unlabeled form fields [4]. This is the default state of software everywhere, including the fintech and gov-adjacent products this deck targets.

3. **Export exposure just became real for Malaysian companies selling into Europe.** The EU Accessibility Act (EAA) took effect 28 June 2025 and is explicitly extraterritorial — it applies to non-EU companies selling e-commerce, banking, or digital-media products to EU consumers, not just EU-based ones [3]. Penalties are already codified: Germany, up to €100,000 per violation (BFSG §37); France, €5,000–€250,000 plus daily penalties up to €1,000 [3]. Enforcement has already started — three French disability advocacy groups sent formal legal notices to major retailers in July 2025 [3].

4. **This is retention and revenue, not just compliance risk.** The UK's Click-Away Pound Survey found businesses lose £17.1 billion a year because disabled users hit an accessibility barrier and buy from a competitor instead — 71% click away from an inaccessible site, and 83% deliberately limit their shopping to sites they already know are accessible [15]. A 2024 Acquia survey of 1,265 disabled adults found 62% would consider switching to a competitor with better accessibility, and 42% would stop using a brand entirely after a bad accessibility experience [16]. This is Makcik Salmah (Slide 2) at scale — an app that fails her once doesn't just risk a fine, it loses her for good.

**Honest caveat, stated on the slide:** there is no confirmed official Malaysian government mandate codifying WCAG 2.0/2.1 AA as a binding technical standard for commercial products — only the general ICT-access right under Act 685. That's the opportunity: the legal right to accessible ICT already exists in Malaysian law; the technical enforcement mechanism doesn't yet. The company that becomes the default way Malaysian teams meet that standard, before a formal mandate forces it, defines what "compliant" means in practice. Separately: the retention/revenue figures above are UK/US survey self-report data, not a peer-reviewed study isolating disabled-user retention before and after an accessibility fix — that rigorous evidence doesn't exist yet anywhere in the field. That gap is part of why the validation study (Slide 13) matters — it's a step toward exactly the kind of hard evidence this space is still missing.

---

## SLIDE 4 — THE STATUS QUO IS BROKEN

**Title:** The status quo: broken, slow, and expensive

**Visual:** A WCAG audit report PDF with a large red stamp: "ISSUED 3 MONTHS AFTER LAUNCH"

**Subtext under the visual:** By the time the audit lands, six sprints have already shipped on top of it. Malaysia already grants the legal right to ICT access under the Persons with Disabilities Act 2008 (Act 685, ss.29–32) [2] — the tooling to actually meet it just doesn't exist yet.

**Comparison table:**

| | Human WCAG Audit | OKU User Panel | InclusionScope |
|---|---|---|---|
| Cost per test | RM15,000–50,000 (vendor-quoted estimate [9]) | RM8,000–20,000 | ~RM2–5 (a 5-persona run at ~RM0.8/run compute cost is ≈RM4 before margin) |
| Turnaround | 2–3 weeks | 3–6 weeks | 3 minutes |
| Frequency | Quarterly | Annually | Every PR |
| CI integration | No | No | Yes |
| Personas covered | 1–2 | Real users | 5+ custom types |

**Bottom statement:** A team shipping 20 PRs/week runs 1,000+ audits per year for less than the cost of one human audit.

**Secondary framing:** We don't replace OKU user panels — we make sure nothing embarrassing reaches them.

---

## SLIDE 5 — THE GAP NO TOOL FILLS

**Title:** The gap no tool fills today

**Visual — 2×2 matrix (axes: Fast/Slow vertical, Shallow/Deep horizontal):**

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

**Three bullets:**
- Lighthouse: automated scan only, no persona behavior, no CI blocking
- Human audit: deep but RM15,000+, 3 weeks, no continuous integration
- OKU user panels: gold standard but unaffordable per-PR
- InclusionScope: deep, fast, and continuous — the empty quadrant

---

## SLIDE 6 — THE SOLUTION

**Title:** InclusionScope — Continuous accessibility intelligence

**Visual:** Product hero screenshot — the project dashboard showing the inclusion-score ring, persona dots, and health badge on a project card.

**Three pillars:**
- **Persona agents** — Real Playwright browsers simulating 5+ disabled Malaysian user types
- **Every deployment** — Runs on every PR via GitHub Actions, blocks P0 findings automatically
- **Developer-ready output** — Jira tickets, PR comments, evidence pack with screenshots

**One-liner:** Same WCAG standards as a certified auditor. 3 minutes. ~RM4 per full 5-persona run.

---

## SLIDE 7 — LIVE DEMO

**Title:** Watch it run

**Demo sequence to record (90 seconds):**
1. Open InclusionScope dashboard → show project card (score ring, persona dots, health badge) — 10s
2. Click into project → Run tab → hit "Start scan" → live view activates — 10s
3. Show persona phone-frame columns side by side, live browser screencast streaming for each persona — 20s
4. Agent graph node updating live: load → observe → agent → route_next — 10s
5. One persona gets blocked (red), others show friction (amber) — 15s
6. Run completes → switch to Results tab → inclusion score, friction matrix, synthesis narrative, each persona's closing statement — 15s
7. Cut to GitHub PR → show the failing check ("InclusionScope — 1 P0 · Low-vision users blocked at OTP step") and the PR comment with the persona table — 10s

**Design note:** This slide is mostly full-bleed screen recording. Minimal chrome. Let the product speak.

---

## SLIDE 8 — TECHNICAL ARCHITECTURE

**Title:** Architecture built for trust, not just speed

**Visual — flow diagram, left to right:**

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
   │  load        load
   │  observe     observe
   │  agent       agent      ← autonomous, goal-directed
   │  route_next  route_next    (no manual flow script)
   │    └────┬────┘
   │         ▼
   │      aggregate → score → evidence → alerts
   │
   ├──► axe-core (WCAG scan, per step)
   ├──► DeepSeek (confusion judgment + closing reflection, per persona)
   ├──► Supabase (evidence pack, screenshots)
   │
   ▼
GitHub API
  PR comment + Check run
```

**Three callouts:**
- **Playwright**: real headless Chromium — not a simulator, an actual browser
- **LangGraph**: cyclic agent graph — the agent loops (observe → decide → act) until blocked or goal reached, autonomously, without a hand-authored flow script
- **axe-core**: industry-standard WCAG engine, the same one used by Google Lighthouse and Deque

---

## SLIDE 9 — ACCESSIBILITY AS A MERGE GATE

**Title:** Accessibility as a merge gate, not an afterthought

**Visual:** GitHub PR screenshot mockup showing:
- Status checks section
- A failing, required check: "InclusionScope · Inclusion score 70% · 1 P0 issue"
- PR comment with a formatted table: persona | verdict | blocked at | WCAG failures

**Three bullets:**
- Triggers on every PR against the live preview URL — zero manual steps
- P0 findings block the merge — the same way a failing unit test does
- Evidence pack attached as an artifact — screenshots, WCAG details, LLM synthesis

**One-liner:** Accessibility regressions never ship. They're caught in the same pipeline as code bugs.

---

## SLIDE 10 — TRUST MODEL + SHAP

**Title:** Our scores are defensible, not just impressive

**Left column — two-stream model:**

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

**Right column — SHAP waterfall (example run):**

```
Baseline:          1.00
─ WCAG 1.4.3:    −0.15
─ 2 P0 blocks:   −0.08
─ Dwell excess:  −0.04
─ Label fail:    −0.03
──────────────────────
Inclusion score:  0.70
```

**Bottom callout:** The LLM cannot hallucinate a P0. Compliance verdicts come from axe-core only.

**Automated-coverage claim, stated precisely:** automated tools like axe-core catch roughly half of accessibility issues by volume (Deque's 2021 study, measured across 2,000+ audits and 300,000+ issues) [5] — historically closer to 20–30% of WCAG success criteria specifically. The remainder requires behavioral judgment. That's the gap the persona-simulation layer targets.

**Second half of the slide — every knob has a citable source, not vibes.** The persona behavior model isn't hand-tuned by feel. Map each hyperparameter to its actual value in the codebase and its actual published source:

| Knob | Value in code | Source |
|---|---|---|
| `min_tap_target_px` | 44 baseline, 48 for elderly/motor personas | WCAG 2.5.5 Target Size (Enhanced), Level AAA, WCAG 2.1 — 44×44 CSS px [17]; Apple Human Interface Guidelines — 44×44pt [17]; Material Design 3 — 48×48dp [17]. Deliberately set above the current AA-level minimum, WCAG 2.5.8 (24×24 CSS px, WCAG 2.2) [17] — this targets the stricter AAA/platform bar, not just the legal floor. |
| `max_reading_grade` | 12 baseline, 8 for elderly/non-native, 6 for low-literacy | Measured via Flesch-Kincaid Grade Level (Kincaid et al., 1975) [18]. Threshold informed by Doak, Doak & Root, *Teaching Patients With Low Literacy Skills* (1996) [19] — a peer-reviewed clinical-literacy textbook, cited in AMA's own health-literacy policy report, recommending grade 5-or-below for low-literacy audiences; our low-literacy persona (grade 6) sits just above that as a calibrated target, not a copied number. |
| `reading_speed_wpm` | 200–220 baseline, 100–140 for elderly/low-literacy/OKU-visual personas | Brysbaert (2019), "How many words do we read per minute?", *Journal of Memory and Language* — 238 WPM average adult silent reading, n=18,573 [20]. Our baseline sits ~10% below the measured average (a conservative margin), with impaired-persona multipliers reducing further. Also consistent with Jakob Nielsen's practitioner estimate of 200–250 WPM ("How Little Do Users Read?", NN/g) [21]. |
| `giveup_threshold_s` | 30–60s, varies by persona | Stated honestly: this is a calibrated design parameter, not a number lifted from a single study — we checked, and neither Baymard nor NN/g publish a seconds-based task-abandonment threshold that matches this construct. (NN/g's real, verified 10-second figure measures attention span during *system response delay* [22], a different thing from a persona's patience for an *ambiguous UI flow* — we didn't force that citation to fit.) This is exactly the parameter the quarterly OKU/senior-citizen UAT panel (Slide 11) and the validation study (Slide 13) exist to empirically calibrate over time. |
| disability tags → lens | `low_vision`, `hearing`, `motor`, `cognitive`, `low_literacy` → contrast / labels / tap-target / reading-load flags | WHO's International Classification of Functioning, Disability and Health (ICF), endorsed 2001 across 191 member states [23], for the disability-modeling framework; Malaysia JKM's 7 official OKU registration categories — Pendengaran, Penglihatan, Pertuturan, Fizikal, Pembelajaran, Mental, Pelbagai [24] — for the Malaysia-specific persona mapping. |

**Frame it on the slide as:** "Parameters are evidence-seeded from accessibility standards and HCI literature, each threshold traceable to a source — including the one place we don't have a perfect citation, which is exactly what our real-panel validation loop is for." Naming the one honest gap is what kills "hand-authored assumptions" — a table with zero gaps would look staged; a table with four hard citations and one named, well-reasoned gap looks real.

---

## SLIDE 11 — THE MOAT

**Title:** Why this is hard to copy, not just hard to build

**1. Data moat — the persona library compounds.**
The Malaysian/SEA persona library (disability type, language, reading level, regional UI/UX conventions) isn't a static config file — every run against a real app generates behavioral signal (where personas stall, what confuses them, which WCAG failures correlate with real friction). That signal feeds back into calibrating give-up thresholds, dwell multipliers, and confusion scoring per persona type. A competitor can clone the codebase; they can't clone a calibration history built on real Malaysian and SEA app traffic.

**2. Real-panel moat — an ongoing OKU/senior-citizen ground-truth loop, not a one-time study.**
On a quarterly (or otherwise periodic) cadence, real OKU individuals and senior citizens run UAT sessions against actual client websites — not just a demo target. Each panel session produces two things a generic competitor has no reason to collect: (a) real precision/recall data comparing what the personas predicted would cause friction against what a real disabled or elderly user actually experienced on that specific client's site, and (b) a growing, Malaysia-specific gap-analysis dataset used to keep recalibrating persona behavioral parameters against real human behavior instead of static assumptions. This turns the indicative stream (Slide 10) into something that gets measurably more accurate over time, on our own client base — a compounding, proprietary dataset a codebase clone can't replicate, and a recurring service relationship (panel recruiting, scheduling, client access) that's operationally hard to copy even if the model weights were.

**3. Regulatory-timing moat — being the standard before there is one.**
Malaysia has the legal right to accessible ICT (Act 685) but not yet a codified technical standard. The EU already does (EAA, June 2025) [3], and pressure typically flows in that direction — export-exposed regions adopt standards their trading partners enforce. A tool already positioned as audit-grade output, mapped to WCAG 2.1 AA, with a defensible trusted/indicative split (Slide 10), is positioned to become the reference implementation once a Malaysian standard is codified — the same way axe-core became the reference for Lighthouse and Deque despite not being a government mandate itself.

---

## SLIDE 12 — CATEGORY VALIDATION

**Title:** Investors already back this category — we're the SEA-specific, CI-native wedge into it

**Table — accessibility-tech funding, global:**

| Company | What they do | Funding / outcome |
|---|---|---|
| Evinced | Automated accessibility scanning, enterprise | $112M total raised, incl. $55M Series C (Dec 2024, Insight Partners) [6] |
| Level Access | Accessibility platform + compliance reporting | $111M+ raised, incl. $55M KKR investment (2021) [6] |
| accessiBe | Automated remediation / overlay | $58M total raised (Series A + extension, 2021–22) [6] |
| Fable | Disability-led testing platform | $37M total raised, incl. $25M Series B (Oct 2024, Five Elms Capital) [6] |
| UserWay | Overlay + compliance widget | Bootstrapped, then acquired by Level Access for $98.7M (Dec 2023) [6] |

**Global market size:** digital accessibility software estimated at $878.45M in 2025, growing to $2,330.57M by 2035 (10.25% CAGR) [7].

**The wedge:** every comparable above is a US/EU-first product with generic personas and no CI-native merge-gate mechanic — most are runtime overlays or manual-review platforms, not a check that blocks a PR. None has a Malaysia/SEA-calibrated persona library or the extraterritorial EAA-exposure angle (Slide 3). This is a proven, funded category with a clear regional and product-mechanic gap InclusionScope is first into.

---

## SLIDE 13 — VALIDATION & PATH TO PROOF

**Title:** We don't have paying customers yet. Here's exactly how we get proof.

**Honest framing, stated plainly on the slide:** InclusionScope is pre-traction — no pilots, no LOIs, no signed customers as of this deck. What exists is a working, deployed product (Slides 7–10) and a specific, falsifiable plan to generate real evidence.

**The validation study:**
1. Select 10 Malaysian web apps (5 known-good, 5 known-bad for accessibility).
2. Run InclusionScope on all 10.
3. Run a parallel certified WCAG 2.1 AA audit by a human auditor on the same 10.
4. Measure precision and recall of InclusionScope's P0/P1 findings against the human auditor's findings.
5. Measure correlation between InclusionScope's inclusion score and the auditor's overall rating.

**Target thresholds:** greater than 80% precision on P0 findings, greater than 60% recall against the human auditor's findings — published as a technical brief. This is the artifact that converts "interesting demo" into "defensible enterprise product."

**Pilot pipeline, targeted not signed:** Malaysian fintechs and e-government-adjacent digital service providers — the same segment quantified in Slide 14 — are the first outreach targets, chosen specifically because they carry both Act 685 exposure and, for export-facing fintechs, EAA exposure (Slide 3).

---

## SLIDE 14 — MARKET OPPORTUNITY: TAM / SAM / SOM

**Title:** A funded category, a specific regional wedge

**TAM — Total Addressable Market:**
Global digital accessibility software market: $878.45M (2025) → $2,330.57M by 2035, 10.25% CAGR [7]. A vertical-specific market size, not a generic dev-tools TAM inflation — this is what buyers already spend on this exact problem category.

**SAM — Serviceable Addressable Market (Malaysia + SEA):**
Anchor points: Malaysia has ~6,000 companies holding MDEC "Malaysia Digital" status as of 2025, up from 5,331 in March 2024 [8]; 5 licensed digital banks (BNM, 2025) [8]; 100+ Fintech Association of Malaysia members (2023 figure) [8]. Regionally, the SEA digital economy's gross merchandise value is forecast to surpass $300B in 2025, with revenue forecast at $135B (e-Conomy SEA 2025, Google/Temasek/Bain) [10].

Modeled SAM: if 5,000 Malaysia + SEA digital-first companies in regulated or export-exposed sectors (fintech, e-commerce, gov-adjacent digital services) adopt InclusionScope at the Growth tier (RM799/mo), that's a ~RM48M/year (~US$10.2M/year) SAM — a deliberately conservative anchor given MDEC alone already counts ~6,000 qualifying companies in Malaysia before SEA is added.

**SOM — Serviceable Obtainable Market (18-month target):**
50–150 paying teams in Malaysia within 18 months of public launch, concentrated in fintech and gov-adjacent digital services — the same segment the validation study (Slide 13) targets first. At blended Starter/Growth pricing this is roughly RM1.2M–7.2M ARR at the low and high end of that range — a planning target, not a forecast promise.

**Regional disability-population context:** Philippines 8.46M / 8.7% of population (2020 Census, PSA) [11]; Vietnam ~6.2M (National Survey on People with Disabilities, 2016) [12]; Indonesia ~22.97M (Susenas 2020/BPS 2024) [13]. Malaysia's 805,509 [1] is the smallest of these in absolute terms but the only one with a published four-year growth trend and a codified ICT-access right (Act 685) anchoring the go-to-market story.

---

## SLIDE 15 — BUSINESS MODEL & UNIT ECONOMICS

**Title:** Priced for developer-led adoption, modeled for real margin

**Pricing:**

| Tier | Target | Price | What's included |
|---|---|---|---|
| Starter | Indie / startup | RM199/mo | 5 apps, 100 runs/mo included (RM2.00/run beyond quota), 3 personas |
| Growth | SME product teams | RM799/mo | 20 apps, 400 runs/mo included (RM1.50/run beyond quota), 8 personas, Jira integration |
| Enterprise | Bank / GLC / gov | Custom | On-prem, custom personas, compliance reports, SLA, volume-priced runs |

**Unit economics:** per-run compute cost is ~RM0.8. Pricing is sized so both tiers hold a consistent ~60% gross margin even at full quota utilization (Starter: RM199 revenue vs. RM80 COGS at 100 runs; Growth: RM799 revenue vs. RM320 COGS at 400 runs). Overage pricing (RM2.00/run Starter, RM1.50/run Growth) holds roughly that same margin band above quota, so heavy usage doesn't quietly turn unprofitable.

**Why 60%, not higher:** it's a believable number for a compute/LLM-heavy dev tool, not an inflated one — pure-software SaaS commonly runs 70–80% gross margin, but products with real per-transaction compute cost typically sit lower. 60% is defensible, holds up under a usage audit, and still leaves real room for CAC spend.

**Benchmarked against industry** (no internal actuals exist pre-launch): top-quartile SaaS net revenue retention runs 104–106%, the standard target LTV:CAC ratio is 3:1, and CAC payback commonly runs 20–23 months industry-wide (High Alpha/OpenView 2025 SaaS Benchmarks) [14]. At ~60% gross margin, InclusionScope has real room to hit a healthy LTV:CAC without needing aggressive price increases — the lever that matters most is adoption depth (apps per account, personas per app, runs per app) more than price per seat.

**Churn mitigation — how a CI-gate avoids "tool fatigue":** the product's core adoption mechanic (merge-blocking on P0 findings, Slide 9) is structurally different from a dashboard tool a team can quietly stop checking. Once a repo's CI pipeline depends on InclusionScope's check passing, removing it is an active decision that reintroduces known accessibility risk — not a passive lapse. This is the same retention mechanic that makes CI-native tools (linters, test-coverage gates, dependency scanners) stickier than dashboard-only SaaS: the tool is embedded in the workflow, not layered on top of it.

**Go-to-market:**
1. **Land**: Malaysian fintech and e-government portals — both under active compliance pressure (Slide 3).
2. **Expand**: any team using GitHub/Vercel/CI — developer-led adoption, no procurement cycle needed.

---

## SLIDE 16 — ROADMAP

**Title:** Built to survive beyond the demo

**Timeline:**

**NOW (built):**
- Autonomous LangGraph agent — cyclic load → observe → agent → route_next loop, goal-directed navigation, no manual flow script required
- Live Playwright browser streaming
- WCAG scoring — axe-core plus the two-stream trust model
- GitHub Actions CI integration (merge-gate)
- Evidence pack — screenshots, friction matrix, synthesis, per-persona closing statement
- Dashboard + Malaysian persona set

**Q3 2026:**
- First quarterly OKU/senior-citizen UAT panel (Slide 11 commitment) — real-user ground-truth run #1
- Validation study (Slide 13) — 10-app precision/recall benchmark against a certified human auditor
- Malaysian persona library expansion — broader disability types, language coverage

**Q4 2026:**
- Jira/Linear ticket push integration
- Remediation copilot — suggested code-level fixes, not just findings
- Second UAT panel cycle — first measurement of persona-calibration improvement over time

**2027:**
- On-prem deployment option
- SDK/API for any CI provider, not just GitHub Actions
- Cert-ready compliance reports
- SEA expansion — persona library and regulatory framing for Philippines, Vietnam, Indonesia (Slide 14 TAM)

**Callout box:** The nearest-term unlock isn't a future promise — it's already live. The agent is given a goal ("claim reward"), explores the UI itself, and needs no hand-authored flow script. The last manual-configuration step is already eliminated.

---

## SLIDE 17 — THE ASK & CLOSE

**Title:** Every Malaysian app has a silent exclusion problem. We're asking for the runway to prove we close it.

**The ask — specific, non-monetary:**
1. **Pilot introductions** — warm intros into Malaysian fintech or gov-adjacent digital teams, to run the validation study (Slide 13) against real production apps, not just the demo target.
2. **Mentorship on enterprise/compliance GTM** — the technical build is done; the gap is enterprise sales motion into regulated buyers (banks, GLCs, gov digital services).
3. **Technical resources for the validation study** — access to a certified WCAG auditor for the parallel human-audit comparison in Slide 13, the single highest-leverage artifact this company can produce next.

**Visual:** Full-bleed — the InclusionScope inclusion score ring, large, centered. Score showing 70%. Below it: "5 personas · 3 min · ~RM4 per run"

**Closing lines:**
- 805,509 registered persons with disabilities in Malaysia deserve to use the same apps everyone else does [1].
- Every team shipping code deserves to know who they're excluding before it ships.
- InclusionScope closes that gap — automatically, continuously, affordably. The product works today (Slide 7). What we need next is proof at scale, and that's what this accelerator track is for.

**Bottom right:** GitHub repo URL + deployment link.

---

## SLIDE 18 — SOURCES

**Title:** Sources

Compact appendix — short form only; full URLs and verification notes are in `extra_info_slide.md`.

1. DOSM, Person With Disability Statistics Malaysia 2024
2. Persons with Disabilities Act 2008 (Malaysia, Act 685)
3. EU Accessibility Act (in force 28 June 2025) — Hamlins LLP; German BFSG §37; French EAA enforcement coverage
4. WebAIM Million 2026
5. Deque, "Automated Testing Identifies 57% of Digital Accessibility Issues" (2021)
6. Company funding: Crunchbase, TechCrunch, BusinessWire, Level Access press release
7. Precedence Research, digital accessibility software market (2025)
8. MDEC "Malaysia Digital" status data; Bank Negara Malaysia digital banking licensees; Fintech Association of Malaysia
9. WCAG audit cost — vendor-quoted (Accessible.org, DigitalA11Y), not independently verified
10. e-Conomy SEA 2025 (Google/Temasek/Bain)
11. Philippines Statistics Authority, 2020 Census
12. Vietnam GSO + UNICEF, National Survey on People with Disabilities 2016
13. Indonesia BPS, Susenas 2020 / 2024 report
14. High Alpha (OpenView), 2025 SaaS Benchmarks Report
15. Click-Away Pound Survey 2019 (Freeney Williams / clickawaypound.com)
16. Acquia, "Consumer Perspectives on Digital Accessibility" (2024, fielded by Researchscape International)
17. WCAG 2.5.5 / 2.5.8 (W3C); Apple Human Interface Guidelines; Google Material Design 3
18. Flesch-Kincaid Grade Level (Kincaid et al., 1975)
19. Doak, Doak & Root, "Teaching Patients With Low Literacy Skills" (1996)
20. Brysbaert (2019), "How many words do we read per minute?", Journal of Memory and Language
21. Nielsen, "How Little Do Users Read?" (NN/g)
22. Nielsen, "Response Time Limits" (NN/g)
23. WHO, International Classification of Functioning, Disability and Health (ICF, 2001)
24. Malaysia JKM, OKU registration categories

https://www.thestar.com.my/lifestyle/living/2026/06/24/how-digital-accessibility-is-empowering-malaysians-with-disabilities?fbclid=IwY2xjawS7IV1leHRuA2FlbQIxMQBicmlkETE4T1h2VHZsMGJHMHJzSnZJc3J0YwZhcHBfaWQQMjIyMDM5MTc4ODIwMDg5MgABHlKGOojCLBgW0UR1TCad5ntW0U_fWgfr08bG_LaBxHyJ6dGA2DipxtTOhTDM_aem_FspdCgK1PLX9FKlmsux8ZQ

https://thesun.my/news/malaysia-news/push-for-digital-access-standards-in-malaysia-aj14849449/
