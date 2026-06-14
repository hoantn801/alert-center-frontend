# Alert Center — Phase D Implementation Report (Read-only Omisell Ingestion)

Date: 2026-06-08 · Status: **DEPLOYED (PR #4) + auth hotfix `66c8d4f` (PR #5) + PILOT PASSED 2026-06-09 — see §10.**

## 10. Pilot results (FES-VN, user-verified 2026-06-09)

- **T0 PASS** — auth probe OK after hotfix (official `POST /api/v2/auth/token/get/` with api_key+api_secret).
- **T1 PASS** — shop directory: total=5, mapped=5, unmapped=0.
- **T3 PASS** — 1-hour window after Site Config status allowlist (`ec_alerts_omisell_allowed_status_ids`) + cache clear: listed=10, ingested=10, skipped_status=0, failed=0, last_sync_advanced=True. **T3 re-run same window PASS → idempotency proven in production** (EC Marketplace Order Log review confirmed no duplicates; real Omisell orders created correctly).
- **T2 OPTIONAL/PENDING** — initial IDs provided were not `omisell_order_number`; T3 already exercised the order list→detail→normalize→ingest flow with correct Omisell IDs, so the single-order golden capture remains optional (worth doing once for the formal Q-D5 4-point record when a known omisell_order_number is handy).
- Confirmed: no Omisell write path used; no stock/buffer update; no scheduler; store/platform untouched.

**Phase D read-only ingestion pilot: PASSED.** Next gate: Phase D.1 capacity hardening (`16_PHASE_D1_CAPACITY_PRECODE.md`) before any scheduler / multi-brand sync.

---

Original implementation report below (pre-deploy state).

## 1. Files added / changed (10 files, +812/−3, all inside `alerts/`)

Add: `services/omisell_client.py` (186 ln), `services/omisell_normalizer.py` (114 ln), `api_omisell.py` (224 ln), `tests/test_phase_d.py` (156 ln), `tests/golden/omisell_order_detail.json` (sanitized docs-shaped placeholder). Change: `services/dedupe_keys.py` (+5: `ingestion_failed_key`), `services/action_queue.py` (3/2: DS1 Dry Run terminology only), 3 DocType JSONs (§2). Workspace: `deploy/run_phase_d_tests.ps1` (T0–T3 driver, ASCII-only).

## 2. Schema changes (all additive, FC migrate applies)

`EC Brand Integration Settings` + `token_expired_at` (Datetime, read-only — Q-D6) · `EC Alert.rule_code` + `ingestion_api_failed` option (Q-D3) · `EC Alert Action` + DS1 audit block (7 fields + section/column break: actual/available/buffer_stock_before, buffer_stock_after, locked_quantity, release_required, release_strategy — schema only, **nothing writes them in Phase D**).

## 3. Endpoint contracts (implemented exactly per plan §3)

All 4 = POST + `frappe.only_for("System Manager")` + enabled BIS for the brand required: `omisell_probe(brand)` (auth + 1-shop sample; success flips credential_status→Active; auth fail → Expired + C3 alert); `sync_shop_directory(brand)` (paged shop list → mapped/unmapped report, **creates nothing**); `pull_one_order(brand, omisell_order_number, capture_golden)` (Q-D2 filter applied; `capture_golden=1` returns sanitized payload for the Q-D5 4-point check); `pull_orders(brand, updated_from, updated_to)` (**hard reject window > 3600s**; per-order failures isolated; `skipped_status_detail` records real status_id/name pairs as Q-D2 evidence; **`last_sync_at` advances only when failed=0**, else daily `ingestion_api_failed` alert).

## 4. Test results

- **Sandbox-executed: 10/10 PASS** (`TestNoWrite` + `TestNormalizer`, run with stubbed frappe AND a stubbed `requests` whose `request()` raises on any call — proving zero network in unit scope). Blob-level compile of all committed modules PASS. JSON field_order consistency PASS.
- Golden-file mapping verified: synthetic line ids (`PKG-1:GOLD-SKU-A`), Q-D5 provisional price (99 000 / 9 900), seller vs platform discount merge, customer_paid_price=None, line-id stability across parses, status keyword filter (Delivered/RTS in; Cancelled/Draft out; **unknown → excluded** with reason).
- Pending bench: `TestEndpointGuards` (non-SM 403 ×4, 3601s window reject) — skips gracefully without a site.

## 5. No-write enforcement proof

(1) `ALLOWED_METHODS = frozenset({"GET"})` — test asserts frozen + GET-only. (2) Chokepoint refuses POST/PATCH/PUT/DELETE incl. POST-to-non-auth-path with auth=False (5 cases tested). (3) Public client surface introspected = exactly `get_shops/get_orders/get_order_detail`; regex sweep finds no mutation-named callables. (4) `sanitize()` strips token/api_key/refresh_token/authorization recursively (tested). (5) Repo-wide test: **no other module under `alerts/` imports requests/HTTP**. (6) Pre-merge grep gate added to §8 checklist. There is no function in the codebase that could write to Omisell.

## 6. Confirmations

**No PM files changed** (0 pm/ paths in commit; your uncommitted PM WIP verified intact across branch switch). **No scheduler** (hooks.py diff = 0; nothing registered). **No Omisell write path** (§5). **No /alerts page change.** Kill switch + dry-run flags untouched. DS1 buffer write remains locked.

## 7. Auth note (the one ⚠️TC from pre-code)

Exact token-exchange path/body key aren't printable from the docs portal — implemented as site_config-tunable (`ec_alerts_omisell_auth_path` default `/api/v2/public/login/`, `ec_alerts_omisell_auth_field` default `api_key`, `ec_alerts_omisell_auth_scheme` default `Omi`, supports `Account` static-key mode). If T0 fails on auth, we fix it with a site-config edit — **no redeploy**.

## 8. Deploy checklist (when approved — owner machine, per-turn confirm)

1. Pre-push: `git diff --name-status origin/main..alerts-phase-d` → exactly 10 files, zero pm/, zero hooks; grep gate: `git grep -lE "import requests|from requests" alerts-phase-d -- ecentric_workspace/alerts` → only `omisell_client.py`.
2. Push `alerts-phase-d` → PR (Files-changed gate) → merge → FC deploy (migrate applies §2; no scheduler registers).
3. Post-deploy probe: 3 schema items present; 4 endpoints → 403 for non-SM; existing Phase C/E probes still green.
4. **You give me: pilot brand (Q-D1) + its Omisell API key goes into that brand's BIS (Desk, SM)** → then T0 → T1 (manual shop mapping) → T2 with **a specific order number you pick** (+`-CaptureGolden` → send me the golden file + 4 Q-D5 answers + real status pairs for Q-D2) → T3 (≤1h window, run twice for idempotency proof).
5. T-results report → separate gates: Q-D5 mapper confirm, Q-D2 status allowlist into site_config, cadence/scheduler decision.

## 9. Rollback plan

Revert PR → FC deploy (endpoints vanish). Per-brand instant stop: BIS `enabled=0`. Read-only → **no Omisell-side state exists to undo**. Schema additions stay harmlessly; ingested orders/alerts kept for audit. Token cache clears by setting BIS.token empty.
