-- Storage bucket for evidence artifacts (§14/§17): per-step screenshots and the
-- rendered evidence pack (PDF + JSON). Public read so dashboard/export links resolve
-- without signing; writes go through the service-role key from the backend only.

insert into storage.buckets (id, name, public)
values ('evidence', 'evidence', true)
on conflict (id) do nothing;

-- Public read of evidence objects (screenshots + packs are non-sensitive artifacts).
-- CREATE POLICY has no IF NOT EXISTS, so guard for idempotent re-runs.
drop policy if exists "evidence public read" on storage.objects;
create policy "evidence public read"
  on storage.objects for select
  using (bucket_id = 'evidence');
