# Alert Center — Phase D.1 Capacity Hardening Implementation Report

Date: 2026-06-09 · Status: **DEPLOYED + MANUAL VERIFICATION PASSED 2026-06-10** after a 4-hotfix chain: PR #7 COUNT fix → PR #8 pull_recent→background job + timeboxes (bench-502 incident, see `19_PULL_RECENT_INCIDENT_HOTFIX.md`) → PR #9 disabled-flag parser → PR #10 observability + Q-D2-FINAL price-risk allowlist. Verified on FES-VN: 4/4 chunks, caught_up=true through 2026-06-07 21:00, failed=0, skipped=0, breaker=0, no 502, no orphan lock. Capacity baseline: Log=54 / Item=106 / Alert=33 / log_plus_item=160. Scheduler OFF; read-only; DS1 locked. Next gate: `20_NARROW_SCHEDULER_PROPOSAL.md` (prepare-only).

Original implementation report below.

## 1. Files changed (10 files, +285/−39, all in `alerts/` + `patches.txt`)

Add: `alerts/patches/{__init__,p001_capacity_indexes}.py`, `alerts/tests/test_phase_d1.py`. Change: `api_alerts.py` (COUNT refactor), `api_omisell.py` (+105: hardening), 4 DocType JSONs (search_index + 1 field), `patches.txt` (+1 line).

## 2. Indexes added

- **search_index (single-column, via migrate):** Order Log — brand, order_datetime, sync_status, omisell_shop_id, external_order_id, platform · Order Item — seller_sku, item, external_line_id · EC Alert — detected_at, owner_user.
- **Composite (patch `p001_capacity_indexes`, idempotent — SHOW INDEX guard, never blocks migrate):** Order Log `(brand, order_datetime)` [the baseline-median scan key] · EC Alert `(brand, status, detected_at)` [/alerts list + cards].

## 3. Schema changes

One additive field: `EC Brand Integration Settings.consecutive_failures` (Int, read-only, default 0 — circuit-breaker state). Nothing else; no DocPerm/role change.

## 4. Behavior changes

- `get_cards` + `list_alerts` total → **COUNT(*)-based** (constant memory at any table size; same results — bench test asserts equivalence vs old method).
- `pull_orders`: pull kill switch `ec_alerts_pull_disabled` (fail-safe: config error ⇒ disabled) → circuit-breaker check → per-run detail cap **300** (`ec_alerts_pull_max_details` tunable) — capped runs do NOT advance `last_sync_at`; breaker increments on failure, resets on full success.
- New `pull_recent(brand, max_chunks?)` — **MANUAL SM-only catch-up**: ≤1h chunks (pure `chunk_windows`, max 4/run), chunk-level checkpointing (advance per fully-successful chunk; a failed/capped chunk holds the checkpoint and stops), reports `caught_up`. This is the future scheduler body — **deliberately NOT scheduled**; note: the scheduler kill switch gates jobs, not this manual endpoint (documented in-code).
- New `capacity_stats()` — SM-only row counts for Log/Item/Alert/Action/Pause + `log_plus_item` vs the **2M archive-review trigger** (your decision: measure first; no archive/delete code exists).

## 5. Tests

- **Sandbox-executed: 18/18 PASS** (TestNoWrite 7 + TestNormalizer 6 + new TestChunker 5) with stubbed frappe and network-refusing `requests`. TestChunker covers: 4-chunk cap, ≤1h bound, contiguity (no gaps/overlap), partial last chunk, empty window, D.1 constants, **and a read-only-surface regression** (ALLOWED_METHODS={GET} + client public surface unchanged).
- Bench-pending (`TestSchemaD1`): search_index in meta, composite indexes via SHOW INDEX, consecutive_failures field, get_cards equivalence.
- Blob-level verification: all committed modules compile from `git show`; patches.txt tail correct; client blob confirmed untouched.

## 6. Performance/capacity verification plan (post-deploy)

(1) Migrate log shows p001 creating 2 indexes (or "already present" on re-deploys). (2) Bench-run `TestSchemaD1`. (3) `capacity_stats` baseline reading (expect tiny counts now — this is the measurement going forward). (4) Optional timing: `/alerts` get_cards latency before/after is already sub-second at current size — the win shows up at volume; EXPLAIN via bench console if you want hard numbers.

## 7. Rollback plan

Revert PR → FC deploy (COUNT refactor and endpoints revert; **indexes stay — harmless and beneficial**, drop only via explicit patch if ever desired; `consecutive_failures` field stays harmlessly). Instant stops without deploy: `ec_alerts_pull_disabled: 1` (all pulls), BIS `enabled=0` (per brand), breaker auto-opens on repeated failure. No data migration to unwind.

## 8. Confirmations

**No write path:** client untouched, `ALLOWED_METHODS={GET}` blob-verified, no mutation function added, regression test guards it. **No scheduler activation:** hooks.py 0 diff; nothing registered; kill switch ON; `pull_recent` is manual-only. **No PM changes:** 0 pm/ paths in commit (user WIP in working tree left untouched). **No archive/delete execution** (measurement only). **No nightly reconciliation** (deferred to D.2 per decision). **DS1 stays locked.**

## 9. Deploy checklist (when approved — owner machine)

1. Pre-push: housekeeping → `git fetch` → `git diff --name-status origin/main..alerts-phase-d1` = exactly 10 files, 0 pm/, 0 hooks.
2. Push → PR #6 (Files-changed gate) → merge → FC Deploy. **Migrate matters this time**: applies search_index columns + runs p001 (watch log for the 2 index lines) + adds consecutive_failures.
3. Post-deploy: `capacity_stats` probe (200 + counts); `/alerts` cards still correct (compare to pre-deploy numbers); non-SM 403 on the 2 new endpoints; optional `pull_recent` single run on FES-VN (manual, read-only) to see chunk checkpointing live.
4. Then the separate gate you defined: decide narrow scheduler enablement (single pilot brand, */15, both kill switches honored) — needs its own approval + small hooks.py change at that time.
