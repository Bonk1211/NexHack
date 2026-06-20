-- Store the full evidence pack inline so the run-detail page can rehydrate a run
-- without depending on Storage being configured (§13/§17). evidence_packs already
-- keeps summary/matrix/remediation for queries; `pack` is the complete artifact
-- (personas, friction matrix, empathy replay, synthesis) the detail view renders.
alter table evidence_packs add column if not exists pack jsonb;
