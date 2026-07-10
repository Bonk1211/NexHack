# InclusionScope — Inclusion & Accessibility Assurance, from Persona to Proof

![Next.js](https://img.shields.io/badge/Next.js-000000?logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React_19-61DAFB?logo=react&logoColor=black)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS_v4-06B6D4?logo=tailwindcss&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.10+-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?logo=langchain&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?logo=playwright&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3FCF8E?logo=supabase&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![DeepSeek](https://img.shields.io/badge/DeepSeek_V4-4D6BFE?logo=deepseek&logoColor=white)

## 🚩 Project Overview

### Problem Statement

- **Accessibility failures are invisible until a real user is blocked** — scanners
  check markup, not whether a person can actually finish the task.
- **Compliance is claimed, not proven** — teams have no continuous, audit-grade
  evidence that vulnerable users can use their product.
- *Example:* An elderly user hits an OTP login where the code field has no label and
  the timer resets faster than they can type. A markup scan passes. The user is stuck.

### Solution

**Onboard:**

- Register an app and its target flow
- Import user demographics
- LLM suggests matching vulnerable-user personas

**Assure:**

- Drive the flow through the **accessibility tree** as each persona
- Capture a **dual signal** every step: axe-core WCAG results + a screenshot
- Score with a pure, seeded engine — two streams kept strictly separate

**Prove:**

- Export an audit-style **PDF evidence pack** + friction matrix
- Fire a live **Slack alert** to the flow owner on any P0 block
- Track quota, cost, and a per-project compliance dashboard

## 🎯 Mission

Turn inclusion from an untested claim into **continuous compliance evidence** — measuring
where real vulnerable users get blocked, and generating proof an auditor can trust.

> Inclusion assurance as audit evidence — not a scanner, not a chatbot.
> NexHack 2026 · Track 1 (Compliance). Single source of truth:
> [`docs/prd/PRD_InclusionScope_v2_Merged.md`](docs/prd/PRD_InclusionScope_v2_Merged.md).

## ⚙️ Tech Stack

**Frontend:**
Next.js 15 · React 19 · TailwindCSS v4 · Geist

**Backend:**
FastAPI · Python 3.10+ · LangGraph (persona subgraph + run map-reduce, SQLite crash-resume)

**Agent & Signals:**
Playwright (mobile emulation + CDP throttling) · axe-core (`axe-playwright-python`) · ReportLab (PDF)

**Cloud & Data:**
Supabase (Postgres + Storage) · Pydantic v2

**AI:**
DeepSeek V4 (LOCKED, §25) — two-tier `flash` per step / `pro` per run · DashScope (figurine images)

## ✨ Key Features

### 🧭 Persona-Driven Assurance

- **Accessibility-tree navigation:** the agent drives the real app the way assistive tech does
- **Dual-signal capture:** trusted axe-core WCAG results + empathy-replay screenshot per step
- **Vulnerable-user personas:** elderly, OKU/disabled, low-literacy, non-native, low-end device
- **Crash-resume:** per-persona SQLite checkpoints — a run survives a mid-flow failure

### 📊 Two-Stream Scoring (the credibility spine)

The scorer emits three results and **never collapses the trusted stream into the composite**:

1. **WCAG conformance** — TRUSTED (axe-core). A compliance officer can rely on it without trusting the sim.
2. **Persona verdict** — INDICATIVE (completion + severity P0–P3).
3. **Composite inclusion score** — OPTIONAL, DERIVED roll-up with visible, tunable weights.

Pure and seeded — the defensible IP, and the hardest-tested layer.

### 📈 Evidence & Alerting

- **Audit-grade PDF evidence pack** — the primary output
- **Friction matrix** — persona × step, where each got blocked
- **Live P0 alerts** — Slack routing to the flow owner on a hard block
- **Compliance dashboard** — per-project, with quota and cost tracking

### 🧑‍💼 Operator Experience

- **Persona wall + empathy replay** — watch each persona's run frame by frame
- **Flow editor & demographics import** with LLM persona suggestion
- **Deterministic offline fallback** — leave `LLM_API_KEY` empty to run reproducibly, no network

## 🚀 Getting Started

### Prerequisites

- Node.js 18+
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)

### Backend

```bash
cd backend
uv venv && uv pip install -e '.[dev]'   # or: uv pip install -e . then add dev group
cp .env.example .env                     # leave LLM_API_KEY empty for offline fallback
PYTHONPATH=. .venv/bin/pytest            # scorer tests (no external deps needed)
uv run uvicorn app.main:app --reload     # API on http://localhost:8000
```

### Frontend

```bash
cd frontend && npm install && npm run dev   # wall on http://localhost:3000
```

### Fixture Site (demo target)

Served by the backend at `http://localhost:8000/fixture/index.html` — a planted-flaw
OTP flow so a run has a target out of the box.

> Or run everything from the repo root: `make install && make run`.

## 🔌 API Surface (backend on :8000)

| Group | Endpoints |
|-------|-----------|
| Runs | `POST /runs` · `GET /runs` · `GET /runs/{id}` · `GET /runs/stream` (SSE) · `GET /runs/quota` |
| Evidence | `GET /runs/{id}/export` (PDF) · `GET /runs/{project_id}/dashboard` |
| Apps | `GET\|POST /runs/apps` · `GET\|PATCH /runs/apps/{id}` |
| Demographics | `GET\|POST /runs/apps/{id}/demographics` · `DELETE .../{demo_id}` |
| Personas | `POST /runs/apps/{id}/suggest-personas` (LLM) · app persona `GET\|POST\|DELETE` |
| Flow | `GET\|PUT /runs/apps/{id}/flow` |
| Library | `GET\|POST\|PUT\|DELETE /personas/...` · `POST /personas/{slug}/figurine` |
| Health | `GET /health` |

## 🎯 Target Audience

- **Primary:** product & compliance teams shipping consumer apps under WCAG 2.2 AA obligations
- **Focus:** vulnerable users — elderly, disabled (OKU), low-literacy, non-native, low-end device —
  routinely overlooked by markup-only accessibility scans

## 🌟 Core Value Propositions

- **Proof, not claims:** continuous, audit-grade compliance evidence
- **Trusted stream preserved:** WCAG conformance never diluted by simulation
- **Real blocks, real severity:** persona completion + P0–P3, not lint warnings
- **Reproducible:** pure seeded scoring + deterministic offline mode
- **Actionable:** friction matrix + live P0 owner routing
- **One platform:** onboard → assure → prove

## 📁 Layout

```
backend/          FastAPI + AI glue
  app/scoring/    Scoring engine — PURE, seeded, unit-tested. The defensible IP.
  app/agents/     Persona subgraph + run map-reduce (LangGraph), a11y-tree nav,
                  dual-signal capture, DeepSeek LLM nodes
  app/evidence/   Evidence pack builder + export — the primary output
  app/routes/     Projects/apps CRUD, personas, flow editor, run orchestrator,
                  SSE stream, dashboard, export
  app/            orchestrator, alerts (Slack), figurine (DashScope), storage,
                  repository, db, cost tracking
  tests/          Scorer tests — the hardest-tested layer
frontend/         Next.js — landing, projects, assess runner, persona wall +
                  empathy replay, friction matrix, dashboard
personas/         Persona library — behavior_profile + thresholds
supabase/         Postgres schema + migrations
fixture-site/     Planted-flaw demo target — the OTP flow
docs/             PRD, business one-pager, hackathon deck/slide guides
```

## 📈 Future Roadmap

**Now:**

- Persona-driven assurance over any target flow
- Two-stream scoring + audit PDF evidence pack
- Persona wall, empathy replay, compliance dashboard, P0 alerts

**Next:**

- Real WCAG 2.2 AA scan breadth beyond seeded fixtures
- Scheduled continuous runs + regression tracking over time
- Broader persona library and per-market threshold tuning

**Later:**

- Recognized, exportable compliance report as audit-acceptable evidence
- Integrations for banks, insurers, and public accessibility programs

## 📄 License

MIT — see the `LICENSE` file for details.

---

**InclusionScope** — proving vulnerable users can actually finish the task, one persona at a time.
