-- InclusionScope — LLM token/cost persistence (dashboard spec §3)
-- Token usage was only ever held in-memory (routes/runs.py _STORE) and streamed
-- over SSE; nothing was durable, so there was nothing to aggregate per project.
-- This adds a per-run rollup (on runs) and a per-model breakdown, mirroring the
-- shape emitted by LLMUsageTracker.serialized() so the write path is a near-copy.
-- Cost is operational metadata only (§16): it never feeds the inclusion score.

-- Per-run token/cost rollup (one row per run)
alter table runs
  add column if not exists prompt_tokens     bigint  not null default 0,
  add column if not exists completion_tokens bigint  not null default 0,
  add column if not exists total_tokens      bigint  not null default 0,
  add column if not exists llm_cost          numeric not null default 0,
  add column if not exists llm_currency      text    not null default 'USD',
  add column if not exists pricing_applied   boolean not null default false;

-- Per-model breakdown within a run (DeepSeek today; keep model-keyed for the
-- §25 "model family is open" decision)
create table if not exists run_model_usage (
  id                uuid primary key default gen_random_uuid(),
  run_id            uuid not null references runs(id) on delete cascade,
  model             text not null,
  prompt_tokens     bigint  not null default 0,
  completion_tokens bigint  not null default 0,
  total_tokens      bigint  not null default 0,
  cost              numeric not null default 0,
  pricing_applied   boolean not null default false,
  created_at        timestamptz not null default now(),
  unique (run_id, model)
);

create index if not exists idx_run_model_usage_run on run_model_usage(run_id);
