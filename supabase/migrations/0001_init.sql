-- InclusionScope — initial schema
-- Source of truth: PRD §17 (data model). Figurine fields removed; evidence_packs added.
-- Two-stream discipline (§16): screen_events keeps wcag_conformance (trusted)
-- distinct from llm_judgment (indicative).

create extension if not exists "pgcrypto";

-- Target apps under assessment
create table if not exists apps (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  staging_url text not null,
  viewport    text not null default 'iphone-13',   -- Playwright device descriptor
  created_at  timestamptz not null default now()
);

-- Global persona library (§7, §11). behavior_profile + thresholds make a
-- persona a measurable behavior model, not just a label.
create table if not exists personas (
  id               uuid primary key default gen_random_uuid(),
  name             text not null unique,
  age_band         text,
  tech_savviness   text,
  patience         text,
  language         text not null default 'en',
  disabilities     jsonb not null default '[]'::jsonb,
  behavior_profile jsonb not null,   -- {dwell_multiplier,hesitation_prob,reading_speed_wpm,giveup_threshold_s,retry_limit}
  thresholds       jsonb not null,   -- {max_dwell_s,min_tap_target_px,max_reading_grade}
  created_at       timestamptz not null default now()
);

-- Which personas run against which app (many-to-many)
create table if not exists app_personas (
  app_id     uuid not null references apps(id) on delete cascade,
  persona_id uuid not null references personas(id) on delete cascade,
  primary key (app_id, persona_id)
);

-- A single assessment run over an app
create table if not exists runs (
  id              uuid primary key default gen_random_uuid(),
  app_id          uuid not null references apps(id) on delete cascade,
  mode            text not null default 'sequential',   -- sequential|parallel (§20: sequential for demo)
  status          text not null default 'pending',      -- pending|running|done|failed
  seed            bigint not null default 0,            -- §16 deterministic runs
  started_at      timestamptz,
  finished_at     timestamptz,
  inclusion_score numeric,                              -- composite (§16), optional/derived
  created_at      timestamptz not null default now()
);

-- One persona's journey within a run
create table if not exists run_personas (
  id         uuid primary key default gen_random_uuid(),
  run_id     uuid not null references runs(id) on delete cascade,
  persona_id uuid not null references personas(id),
  verdict    text,            -- completed|blocked (INDICATIVE)
  severity   text,            -- P0|P1|P2|P3 (§12)
  completed  boolean not null default false,
  status     text not null default 'pending',
  blocked_at text             -- step key where blocked, if any
);

-- Per-step capture. Trusted (wcag_conformance) vs indicative (llm_judgment) kept distinct.
create table if not exists screen_events (
  id               uuid primary key default gen_random_uuid(),
  run_personas_id  uuid not null references run_personas(id) on delete cascade,
  step_idx         int not null,
  url              text,
  action           text,
  dwell_ms         int,
  backtracked      boolean not null default false,
  axe_violations   jsonb not null default '[]'::jsonb,   -- raw axe-core output
  wcag_conformance jsonb not null default '{}'::jsonb,   -- TRUSTED: {criterion: pass|fail}
  llm_judgment     jsonb not null default '{}'::jsonb,   -- INDICATIVE: confusion note + score
  severity         text,
  screenshot_url   text,
  created_at       timestamptz not null default now()
);

-- The primary output (§13). Did not exist in the old build plan.
create table if not exists evidence_packs (
  id          uuid primary key default gen_random_uuid(),
  run_id      uuid not null references runs(id) on delete cascade,
  summary     jsonb not null default '{}'::jsonb,   -- exec summary + inclusion_score + wcag_conformance
  matrix      jsonb not null default '{}'::jsonb,   -- persona × step friction matrix (hero artifact)
  remediation jsonb not null default '[]'::jsonb,   -- prioritized, routed to owning area
  pdf_url     text,
  json_url    text,
  created_at  timestamptz not null default now()
);

create index if not exists idx_run_personas_run on run_personas(run_id);
create index if not exists idx_screen_events_rp on screen_events(run_personas_id);
create index if not exists idx_runs_app on runs(app_id);
