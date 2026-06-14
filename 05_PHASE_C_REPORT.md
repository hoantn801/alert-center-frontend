# Alert Center — Phase C Implementation Report

Date: 2026-06-07 · Status: **IMPLEMENTED LOCALLY on branch `alerts-phase-c`, commit `08cfdaa` — NOT pushed, NOT merged, NOT deployed.** Awaiting your review/approval per gate process.

---

## 0. Phase B production verification gate (prerequisite — checklist vs your reported results)

| # | Requirement | Status |
|---|---|---|
| 1 | 8 DocTypes exist in production | ✅ **PASS** — you confirmed explicitly (2026-06-07) |
| 2 | `Brand Approver.kam_owner` exists | ✅ existence confirmed by you. **Residual probe R1 (10s):** open the field in Desk → confirm Type=Link, Options=User (shipped that way in the fixture; just needs eyes) |
| 3 | New DocTypes not broadly accessible via Desk | ⚠️ **Residual probe R2 (30s):** as any non-System-Manager user, `GET /api/resource/EC Alert` (or Desk search "EC Alert") → expect 403/not visible. Shipped as System-Manager-only DocPerm in code; needs one production probe |
| 4 | No `/alerts` UI expected | ✅ PASS — by design (Phase E) |
| 5 | No real Omisell API / stock lock active | ✅ PASS — no integration code existed in Phase B at all |

Gate decision: **proceeded with Phase C LOCAL implementation** (zero production risk). R1+R2 results are required before the **Phase C deploy** approval, not before local coding.

## 1. Files added / changed (commit `08cfdaa` — 13 files, +1253, **zero deletions, no Phase B file touched**)

All new, under `ecentric_workspace/alerts/`:
`api.py` · `services/{__init__,pricing,rules,dedupe_keys,brand_resolver,policy_lookup,baseline,alert_engine,action_queue,ingestion}.py` · `tests/{test_rules_pure,test_phase_c}.py`. No hooks.py change (no scheduler in Phase C), no fixtures, no DocType change, no patches.

## 2. Functions implemented (by module)

- **pricing** (pure): `compute_unit_check_price(line)` — rule A priority: customer_paid_price/qty → payload unit price → list_price − per-unit seller_discount (platform_discount deliberately not subtracted); unresolvable → line skipped+counted.
- **rules** (pure): `evaluate(unit_price, policy, baseline)` — **single winning hit (C2)**: possible_missing_zero (×10 within 15% band, constant `MISSING_ZERO_TOLERANCE`) → severe_price_drop → below_min → above_high → None=OK; float-boundary EPSILON guard; lock recommendation only for the two severe rules.
- **dedupe_keys** (pure): C1 dual-tier builders exactly per your approved formats (incl. external_product_id-preferred variants); >140-char keys compacted deterministically (sha1 tail); `missing_credential_key` = `omisell|{brand}|missing_integration_credential|{YYYYMMDD}` (**proposed format** — not in your C1 list, flag if you want it changed).
- **brand_resolver**: `resolve_shop` (Active EC Marketplace Shop by omisell_shop_id), `resolve_brand` (shop→brand first; payload brand accepted only if it names an Active Brand Approver; else None), `resolve_owner` (D1 chain: shop.kam_owner → brand.kam_owner → manager_email → leader_email → None).
- **policy_lookup**: `find_policy` — 6-level brand-mandatory priority; levels 3–5 require policy.shop unset; level 6 only `is_brand_fallback=1`; effective window inclusive both ends, empty=open; Active only.
- **baseline**: `get_baseline` — 30-day median (same brand+platform[+shop], item OR seller_sku, **excluding the order being checked**), n≥5→High; reference_price→Medium; min_price→Low.
- **alert_engine**: `check_order_log(name, raw_shop_id)` — flow per design §3: missing-brand path (Warning, C1 daily key, no policy check, no lock), missing-policy path (Warning, C1 daily key), price path (snapshots `unit_check_price`/`min_price_at_check`/`baseline_price_at_check`/`check_result` on each line, C2 winner alert, then lock decision). `_create_alert` = dedupe-then-insert (existing key in ANY status blocks recreation — unique index forces this; same-line re-sync never reopens a Resolved incident).
- **action_queue**: `maybe_create_lock_action` (guards: lockable rule + policy.enable_stock_safety_lock + High/Medium confidence + action dedupe; active pause → row created with status=**Skipped** for audit); `find_active_pause` (brand-scoped, expired-Active treated inactive); `process_pending_actions` / `_process_one` (final guard chain: pause re-check → per-brand credential [missing/disabled/inactive → Skipped + `missing_integration_credential` daily alert, **no cross-brand reuse**] → `dry_run_stock_lock=1` → **status=Dry Run** with simulated api_response; `dry_run=0` → Skipped "not implemented" — **a real call is structurally impossible**); per-action try/except + `frappe.log_error`.
- **ingestion**: `ingest_orders` / `_ingest_one` — idempotent by `order_key` + sha256 payload hash (unchanged re-sync → re-run checks, dedupe makes it no-op; changed → items rewritten + re-check); Item link set only when the code exists in Item; per-order failure isolated.
- **api**: `ingest_mock_orders(payload)` and `process_action_queue()` — **POST-only + `frappe.only_for("System Manager")`**. Nothing else is whitelisted; no KAM-facing endpoints until Phase E.

## 3. Data flow

`POST api.ingest_mock_orders` (SM only) → `ingestion` (normalize → EC Marketplace Order Log + items, idempotent) → `alert_engine.check_order_log` (brand guard → policy → baseline+confidence → C2 winner → EC Alert + line snapshots → `action_queue.maybe_create_lock_action` [Pending/Skipped]) → `action_queue.process_pending_actions` (pause → credential → **Dry Run** stamp). Alert creation and action processing are separate steps; no external call exists anywhere in the chain.

## 4. Permission gates

Ingestion/queue endpoints: System Manager only (`frappe.only_for`, POST-only). Engine writes use `ignore_permissions=True` internally — safe because every entry point is SM-gated and DocTypes are Desk-locked to SM (Phase B). Brand-scoped read/handle APIs for KAM/manager/leader arrive in Phase E on top of `alerts/permissions.py` (unchanged this phase; test 13 exercises `get_allowed_brands` + `require_brand_access` + only_for denial). No new roles, no DocPerm change, no Role Permission Manager touch.

## 5. Test results

- **Executed here (sandbox, no bench):** `test_rules_pure` — **16/16 PASS**, re-run from the committed git blobs (not the working tree) per OneDrive safety rule. Covers cases 4–8 logic, band/threshold boundaries (incl. the 29,700 exact-threshold float fix), pricing fallbacks, C1 key formats, 140-char compaction. Import-smoke of all 10 runtime modules with stub frappe: PASS. `grep` confirms **zero `requests/urllib/http` imports** under `alerts/`.
- **Pending on a bench site:** `test_phase_c` — the 13 approved integration cases (compiled + blob-verified, not yet executed; needs `bench --site <dev-site> run-tests --module ecentric_workspace.alerts.tests.test_phase_c`). This is the same honest limitation as Phase B §6: no Frappe site exists in this workspace. Options: your local bench, or run on production after deploy (test data is ALERTC-prefixed and self-cleaning — but I recommend a dev/staging site first).

## 6. Limitations / notes for review

1. Bench integration suite not yet executed (above) — the deploy gate should include running it.
2. `external_product_id` is accepted in payloads and used in C1 keys at ingestion time, but is **not persisted** on EC Marketplace Order Item (Phase B schema is frozen); re-runs from a saved order rebuild missing_* keys without it. Fix = 1-field schema addition in a later phase if you want it stored.
3. Same for the raw `omisell_shop_id` on unmapped orders: used in the missing_brand_mapping key when passed, `''` when re-checking from a saved doc.
4. ~~`missing_credential_key` format~~ — **APPROVED 2026-06-07 as decision C3** (brand-scoped, one alert/brand/day; extend with platform if credentials become platform-scoped). Implementation already matches — no code change needed.
5. list_price fallback assumes list_price is per-unit and seller_discount is per-line — mock payloads should prefer customer_paid_price (the primary path).
6. `{YYYYMMDD}` uses `frappe.utils.nowdate()` = site timezone; site must be (and is) Asia/Ho_Chi_Minh.
7. Dedupe vs unique-index semantics: an alert/action with the same key in ANY status blocks recreation (DB constraint). Spec's "Open/In Review" rule is therefore strictly tighter in practice; Failed lock actions are retried by updating the row, not inserting a new one (retry endpoint = Phase E, SM-only).

## 7. Deploy requirement (when approved — separate confirmation)

Code-only change: push `alerts-phase-c` (from your Windows machine) → PR → merge `main` → FC Deploy. **No migrate-relevant change** (no DocType/fixture/patch) — FC's standard deploy+migrate is harmless. Post-deploy: run `test_phase_c` OR one manual SM-only mock ingestion (sample payload in module docstring) and check Alert/Action records; verify both endpoints 403 for non-SM (R2 doubles as this check).

## 8. Rollback plan

Revert the merge commit → FC re-deploy. Nothing else: no scheduler entries were added, endpoints disappear with the code, no schema to unwind, alert/action/log records created during testing stay for audit (ALERTC-prefixed test data is self-cleaning via the suite's teardown).

## 9. Confirmations

- **No real Omisell API call exists**: zero HTTP imports under `alerts/` (grep-verified at commit); `_process_one` has no execution branch — only Skipped/Dry Run outcomes.
- **No real stock update exists**: no code path writes stock anywhere; `previous_available_stock` is only ever read-only schema.
- No listing off/deactivation, no price update, no scheduler, no frontend, no schema change, no new roles, no DocPerm change.

## 10. Incident note (process)

First commit attempt (`def79e0`, now dangling) accidentally swept OneDrive-stale copies of the Phase B files (one file truncated mid-line by a stale mount read). Caught by a deletions-check before reporting; recreated as **`08cfdaa`** staging only the 13 new files (verified: 0 deletions, all blobs compile, pure tests pass from blobs). One more `.git/index` corruption was repaired along the way (same OneDrive pattern, same fix). The Phase B files in git history remain exactly as merged in `4d9f2b0`. Standing recommendation unchanged: push from your Windows git, and avoid concurrent commits while I operate.
