# Alert Center — Phase D Implementation Plan (Read-only Omisell Ingestion)

Date: 2026-06-08 · Status: **PLAN — no code until you approve.** Read-only hard constraints in force (no inventory/buffer/stock/delist/product/order writes, no webhook registration; only auth POST; DS1 keeps buffer writes locked).

## 0. Approved decisions (binding, 2026-06-08)

**Q-D1** 1 pilot brand, manual-only Phase D, no scheduler pull; cadence decided after T0–T3; **I will ask you for the pilot brand before T0**. · **Q-D2** provisional real-sale rule = include paid/RTS/processing/shipped/delivered, exclude cancelled/returned/failed/draft/unpaid/invalid; filtering centralized + configurable, no unclear status_id hardcoded before real payloads (T2/T3 confirm). · **Q-D3** add rule_code `ingestion_api_failed`. · **Q-D5** `unit_check_price = discounted_price` provisional; 4-point semantics check at T2 golden file; adjust mapper before T3 if needed. · **Q-D6** add `token_expired_at` (Datetime) to EC Brand Integration Settings. · **Q-D4** sidebar nav DEFERRED. · DS1 audit fields + Dry Run terminology cleanup ride along (additive, already planned).

## 1. Exact files to add / change (branch `alerts-phase-d` off origin/main)

| File | A/C | Content |
|---|---|---|
| `alerts/services/omisell_client.py` | Add | single `_request()` chokepoint with `ALLOWED_METHODS = {"GET"}` + auth-path allowlist; token get/refresh/cache (uses `token_expired_at`); rate-limit reader (`X-Omisell-Api-Call-Limit`, sleep >70/100) + 429 backoff (30/60/120s, max 3); `_sanitize()` strips Authorization/token from anything logged; public methods: `get_shops()`, `get_orders(updated_from, updated_to, page)`, `get_order_detail(omisell_order_number)` — **nothing else exists** |
| `alerts/services/omisell_normalizer.py` | Add | payload → our normalized order dict per pre-code §4 (synthetic line id `{parcel}:{catalogue_sku}`, discount/voucher merges, unix→site-TZ); **status filter centralized here**: provisional keyword rule on status_name + override hook `frappe.conf.ec_alerts_omisell_allowed_status_ids` (list) once T2/T3 confirms — excluded orders are logged in the pull summary, not ingested |
| `alerts/api_omisell.py` | Add | 4 SM-only POST endpoints (§3) |
| `alerts/services/dedupe_keys.py` | Change (+1 fn) | `ingestion_failed_key(brand, yyyymmdd)` = `omisell\|{brand}\|ingestion_api_failed\|{YYYYMMDD}` (daily per brand, mirrors C3) |
| `alerts/doctype/ec_brand_integration_settings/*.json` | Change | + `token_expired_at` (Datetime, read_only) after last_sync_at (Q-D6) |
| `alerts/doctype/ec_alert/ec_alert.json` | Change | + `ingestion_api_failed` in rule_code Select (Q-D3) |
| `alerts/doctype/ec_alert_action/ec_alert_action.json` | Change | + 7 DS1 audit fields (actual/available/buffer_stock_before, buffer_stock_after, locked_quantity, release_required, release_strategy) — schema only, nothing writes them yet |
| `alerts/services/action_queue.py` | Change (text only) | Dry Run api_response → "DRY RUN: would set/increase buffer stock to lock sellable quantity until {lock_until}. No API was called." (DS1 terminology) |
| `alerts/tests/test_phase_d.py` | Add | §5 no-write enforcement + normalizer golden-file + endpoint guard tests |
| `alerts/tests/golden/omisell_order_detail.json` | Add | sanitized sample (doc-schema-shaped placeholder now; replaced by real T2 capture) |
| Workspace `ALERT_CENTER/deploy/run_phase_d_tests.ps1` | Add | T0–T3 driver script (§6) |

Not touched: `api.py`, Phase E endpoints, page, hooks.py (**no scheduler entry**), permissions.py, PM anything.

## 2. Schema changes (all additive, app-owned JSON, idempotent FC migrate)

1 new field on BIS (`token_expired_at`), 1 Select option on EC Alert (`ingestion_api_failed`), 7 DS1 fields on EC Alert Action. No new DocTypes, no fixtures, no patches, no DocPerm change.

## 3. Endpoint contracts (`ecentric_workspace.alerts.api_omisell.*` — all `@frappe.whitelist(methods=["POST"])` + `frappe.only_for("System Manager")` + active BIS check)

| Endpoint | Params | Returns (sanitized — no token/header material ever) | Omisell calls |
|---|---|---|---|
| `omisell_probe` | `brand` | `{ok, token_refreshed, shop_sample_count, rate_limit_header}` | auth + 1× shop list (page_size=1) |
| `sync_shop_directory` | `brand` | `{omisell_shops: [{shop_id, shop_name, platform}], mapped: [...], unmapped: [...]}` — **report only, creates nothing**; you map manually in EC Marketplace Shop | auth + shop list (paged) |
| `pull_one_order` | `brand, omisell_order_number, capture_golden=0` | ingest result + alert/action summary; `capture_golden=1` additionally returns the **sanitized** raw payload for saving as golden file | auth + 1× order detail |
| `pull_orders` | `brand, updated_from, updated_to` (datetime strings) | `{window, listed, ingested, skipped_status, failed, alerts, queue}` — **hard guard: window ≤ 3600s, reject otherwise (MVP)**; `last_sync_at`/`token_expired_at` updated on success | auth + order list pages + N order details |

Failure behavior (all 4): auth-class → BIS `credential_status=Expired` + daily `missing_integration_credential` alert; other API failure → daily `ingestion_api_failed` Warning alert (new key) + `frappe.log_error`; `last_sync_at` advances only on full window success.

## 4. Permission gates

System Manager only on all 4 endpoints (same `frappe.only_for` pattern as mock ingestion — production-proven). Internally: BIS must exist + `enabled=1` + integration_type=Omisell for the named brand, else clean refusal (no alert spam from misconfig probing). No KAM-facing surface; nothing added to `/alerts` page; credentials decrypted only inside `omisell_client._auth()`; responses sanitized at the chokepoint before any return/log.

## 5. No-write enforcement tests (test_phase_d.py)

1. `_request("POST", "/api/v2/public/order/list")` → raises (only auth path may POST).
2. `_request("PATCH"/"PUT"/"DELETE", anything)` → raises.
3. Introspection: `omisell_client` module exposes no attribute matching `(adjust|update|cancel|delete|delist|stock|webhook)` (regex on dir()).
4. `ALLOWED_METHODS == {"GET"}` frozen constant assertion.
5. Normalizer is pure: importable without network; golden-file test asserts full mapping (incl. synthetic line ids stable across two parses, Q-D5 price fields, status filter include/exclude lists).
6. Endpoint guards: non-SM → PermissionError on all 4; `pull_orders` window 3601s → ValidationError.
7. Regression: pure rules suite + grep gate (zero write verbs to api.omisell.com) re-run at commit; pre-merge checklist repeats the grep on blobs (like Phase C/E §0).

## 6. T0–T3 manual test scripts (`run_phase_d_tests.ps1` — parameterized, ASCII-only, token from CSV, never printed)

```
.\run_phase_d_tests.ps1 -Step T0 -Brand <PILOT>                         # auth probe: expect ok=true + rate header
.\run_phase_d_tests.ps1 -Step T1 -Brand <PILOT>                         # shop directory report -> you map shops manually in Desk, rerun until unmapped=0
.\run_phase_d_tests.ps1 -Step T2 -Brand <PILOT> -OrderNumber <OMI-...>  # single order you choose; prints alert summary + sanitized golden payload to file for the Q-D5 4-point check
.\run_phase_d_tests.ps1 -Step T3 -Brand <PILOT> -From "yyyy-MM-dd HH:mm" -To "+1h"   # 1-hour window; prints counts to compare vs Omisell UI; rerun = idempotency proof (0 new docs)
```
Each step prints `[OK]/[WARN]/[ERR]` + a verification checklist; T2 output is the gate for confirming Q-D5 and the Q-D2 status list (we record actual status_id/status_name pairs seen). **I will ask for the pilot brand before T0.**

## 7. Deploy / rollback

Deploy: local build + tests (golden/no-write/pure regression, blob-verified commit) → implementation report → your approval → push from Windows → PR gate (files-changed = this plan §1 only, zero pm/) → FC deploy (migrate applies the 3 schema edits; **no scheduler registered**) → post-deploy probe (fields + rule_code option present, 4 endpoints 403 for non-SM) → you give pilot brand + credential into BIS (SM, Desk) → T0–T3 → results report → separate decisions: cadence/scheduler, status list final, Q-D5 mapper confirmation.
Rollback: revert PR → FC deploy (endpoints vanish); per-brand instant stop = BIS `enabled=0`; schema additions stay harmlessly; **no Omisell-side state exists to undo (read-only)**; ingested orders/alerts kept for audit.

Risk: LOW-MEDIUM — first real external calls, but manual-only, SM-only, GET-only, 1-hour-window-capped, single pilot brand, and every failure path ends in an alert + log rather than a retry storm.
