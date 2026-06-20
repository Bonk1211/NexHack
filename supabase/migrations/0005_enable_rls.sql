-- Lock down the public tables. The backend talks to Supabase with the SERVICE-ROLE
-- key (which bypasses RLS), and the frontend never queries these tables directly —
-- it goes through the FastAPI backend. So enabling RLS with NO policies denies the
-- anon/authenticated roles entirely, closing the anon-key read/write hole flagged by
-- the security advisor, without affecting the backend.
alter table apps            enable row level security;
alter table personas        enable row level security;
alter table app_personas    enable row level security;
alter table runs            enable row level security;
alter table run_personas    enable row level security;
alter table screen_events   enable row level security;
alter table evidence_packs  enable row level security;
