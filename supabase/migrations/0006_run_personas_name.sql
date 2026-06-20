-- Align run_personas with the live persistence path (§17). The streaming/agent flow
-- identifies personas by their stem NAME (e.g. "oku_visual") and does not seed the
-- personas library table, so the original persona_id FK can't be satisfied per run.
-- Store the name directly and relax persona_id to optional, so every persona verdict
-- (and its screen_events / evidence pack) actually persists.
alter table run_personas add column if not exists persona_name text;
alter table run_personas alter column persona_id drop not null;
