# Alert Center — Handover Package (for new Claude chat)

> Date: 2026-06-10 · Purpose: continue ERP Website / Alert Center dev in a fresh chat without re-reading the prior conversation. **This is a handover doc only — nothing new was implemented in this step.**

---

## 1. Current project status

**Phase summary:** Phase F (dashboard/policies UI) live. G1 (Integration Health) deployed. G1.1 (Case+Occurrence + component price basis) deployed+verified. G2.1 / Conflict Guard / Hourly Chart / Scheduler-overlap hotfix = **built, NOT yet deployed**.

**Deployed + verified**
- G1 Integration Health / brand readiness (PR #15).
- G1.1: two-tier `EC Alert` (Case) + `EC Alert Occurrence` (per-line evidence); component-based price basis; rule-overlay thresholds; bulk actions; occurrence CSV export. Backend commit `21f6c43`, deployed + verified (Case `EC-AL-000662`, Occurrence `EC-AOCC-000675`).
- Alert engine confirmed working end-to-end when an order reaches ERP.

**Partially done (built locally, awaiting owner deploy)**
- **Scheduler overlap hotfix** — `api_omisell.py` (backend-only). Compile OK + sim 7/7. Report `44_SCHEDULER_OVERLAP_HOTFIX_REPORT.md`.
- **G2.1** order-derived SKU Catalog + policy search/autofill + missing-policy coverage panel (backend + frontend).
- **Policy Conflict Guard** (backend `ec_price_policy.py` + `api_policies.py` + frontend badges/note).
- **Dashboard hourly chart** (backend `api_dashboard.hourly_trend` + frontend SVG).

**Pending (owner action)**
- Deploy the 4 built items above (deploy PM and Alert Center separately; backend explicit-path staged; frontend via `deploy_alert_pages.ps1`).
- Then the **Omisell list/timezone diagnostic** (section 7) — top priority before any further scheduler change.

**FES-VN / LOF-VN production state**
- Both on the live scheduled pull. Engine + detail API healthy.
- **Open issue:** scheduled order/list pull intermittently misses orders the detail API can read (see section 7). Overlap hotfix widens the window structurally but does **not** yet fully fix the miss → diagnostic needed.
- LOF-VN G2.1 SKU Catalog may be empty if no order-derived data yet (expected, not a bug).

---

## 2. Repositories and paths

- **Backend repo:** `C:\dev\ecentric_workspace` (Frappe app `ecentric_workspace`; prod `team.ecentric.vn`, Frappe Cloud).
- **Frontend / deploy:** `C:\dev\ALERT_CENTER` (builder, reports, deploy scripts).
  - Builder: `C:\dev\ALERT_CENTER\frontend\build_alert_pages.py`
  - Deploy scripts / Web Page records: `C:\dev\ALERT_CENTER\deploy\` (`deploy_alert_pages.ps1`).
- **Old OneDrive folders = BACKUP ONLY. Do NOT code/commit/deploy from them** (caused lock/truncate/revert).
- **Branch naming:** feature branches off `main`, one feature per branch (e.g. `fix/scheduler-overlap`, `feat/g2-1-sku-catalog`). PR → merge → FC deploy.
- **Current main commit:** last verified backend commit = `21f6c43` (G1.1). Confirm with `git -C C:\dev\ecentric_workspace rev-parse HEAD` before staging.
- **Active/unmerged work:** scheduler overlap hotfix + G2.1 + Conflict Guard + hourly chart all sit as **local edits not yet committed/branched** — owner to branch + stage explicit paths.

---

## 3. Production constraints / non-negotiables

- **No Omisell write** — client `ALLOWED_METHODS={GET}` frozen; only `get_shops`/`get_orders`/`get_order_detail`.
- **No stock / buffer / inventory write.**
- **DS1 remains locked.**
- **Do not touch scheduler / hooks / tasks / PM** unless explicitly requested.
- **Deploy PM and Alert Center separately** (never mixed).
- **Always verify current Git branch before commit/deploy.**
- **Do not mix feature commits across branches.**
- **Backend changes = explicit-path staged** (`git add ecentric_workspace/alerts/<file>`, never `git add .`).
- **Frontend deploy = Web Page records** via `C:\dev\ALERT_CENTER\deploy` (`deploy_alert_pages.ps1`, resolves Web Page by ROUTE).
- ASCII-clean builds; credentials never pasted/committed (stay in `secrets/`).
- Production write (PUT/POST to live, deploy, Server Script/DocType change) needs explicit same-turn user confirmation.

---

## 4. Completed phases and key decisions

- **Phase F Drop 1/2** — Dashboard v2 (KPIs, by-dimension, top SKUs, aging, daily trend; default 14d window, server-scoped). Policies/rules/locks/health UI pages. 5 single-file Web Pages built from home-shell snapshot.
- **G1 Integration Health / brand readiness** — per-brand integration/config readiness surface; deployed PR #15.
- **G1.1 component-based price basis** — `effective_check_price = RSP − [seller_discount] − [seller_voucher] − [platform_discount] − [platform_voucher]`, each included only if its `include_*` flag is on (`EC Brand Alert Config`). Default flags `1/1/0/0/0` (seller-funded legacy). **FES-VN + LOF-VN = all four on** (customer-checkout), `use_customer_paid=0`. Components are **per-unit**; only `customer_paid_price` is line-total ÷ qty.
- **Case + Occurrence model** — `EC Alert` = Case (one open Case per brand+sku+rule); `EC Alert Occurrence` = per-order-line evidence. Occurrence key `omisell|{order}|{line}|occ|{rule}`; Case key `case|{brand}|{sku}|{rule}|{first_order}|{first_line}`.
- **Evidence export** — occurrence CSV export; bulk set-status.
- **Policy Conflict Guard** — block a 2nd **Active** policy with EXACT same scope (brand+platform+shop+sku/item) + overlapping validity (`_guard_exact_scope_conflict` in `validate()`). `Platform=All` is a **different scope = fallback**, not blocked. `api_policies.policy_conflicts(brand)` returns per-policy flags `duplicate`/`overridden` for badges. Does NOT auto-delete existing policies.
- **G2.1 order-derived SKU Catalog + Policy Autofill** — `EC Marketplace SKU Catalog` (key `source|omisell_shop_id|seller_sku`, `rsp_price` = latest list_price, hash-gated idempotent upsert from order lines, fail-open in engine). `api_sku_catalog`: list/search/sync-preview/sync-confirm/`policy_missing_skus` (brand-scoped, **no Omisell call** — order-derived only). Frontend: SKU search modal + autofill + coverage panel.
- **Dashboard hourly chart** — `api_dashboard.hourly_trend(filters)` → per hour-of-day total + critical, honors dashboard filters; frontend combined column(total)+line(critical) SVG. Filter panel moved below KPI+chart row.
- **Scheduler overlap hotfix** — `_overlap_minutes()` (site_config `ec_alerts_pull_overlap_minutes`, default 360); `effective_from = last_sync_at − overlap`; full-span ≤1h chunks (`MAX_OVERLAP_CHUNKS=12`); **monotonic checkpoint** `last_sync_at = max(prev, window_end)`; run-level `listed_order_numbers`/`listed_total`; `pull_status` exposes `overlap_minutes`. No dup records (Order Log upsert + Occurrence dedupe). `pull_one_order` unchanged.

---

## 5. Important verified facts (exact)

**Golden order `ODVN26060894414148` — discount mapping (per-unit):**
- `original_price` = RSP / listed price
- `discount_seller` = seller discount
- `voucher_seller` = seller / shop voucher
- `discount_platform` = platform discount
- `voucher_platform` = platform voucher
- `discounted_price = original_price − (all four components)`
- **All values per-unit.**

**P02056 example:** `282000 − 46000 − 0 − 0 − 44600 = 191400`.

**G1.1 verified:** Case `EC-AL-000662` + Occurrence `EC-AOCC-000675`.

**Manual pull verified — order `ODVN260609D6414F3F`:**
- `EC-MOL-000707` created; P02056 `effective_check_price = 209985`, `min_price_at_check = 250500`, `check_result = Below Min`.
- `EC-AL-000708` created.

**Alert Engine works once the order reaches ERP.**

**Current unresolved issue:** scheduled order/list API does **not** return known order `ODVN260609D6414F3F` even though the detail API reads it fine.

---

## 6. Current unresolved issue to continue next

**Title:** Omisell scheduled list / timezone diagnostic

**Evidence**
- `pull_one_order(ODVN260609D6414F3F)` succeeds.
- Scheduled pull with 360-min overlap covered `2026-06-09 19:16 → 2026-06-10 01:18`.
- `listed_total = 0`, `listed_order_numbers = []`.
- Target order `order_datetime = 2026-06-09 21:37:39`.
- → Overlap works **structurally**, but Omisell order/list still misses the order.
- Likely causes: list endpoint timestamp semantics, timezone, status/shop filter, or list↔detail API inconsistency.

**Next recommended task:** add a **read-only** diagnostic probe for Omisell order/list windows **before** changing the scheduler again.

**Probe target**
- brand = `FES-VN`, target order = `ODVN260609D6414F3F`, shop_id = `21611`, known ERP `order_datetime = 2026-06-09 21:37:39`.

**Probe windows**
1. VN local around order time: `2026-06-09 20:00 → 2026-06-09 23:00`
2. UTC-shifted (−7h): `2026-06-09 13:00 → 2026-06-09 16:00`
3. Wider same-day VN: `2026-06-09 00:00 → 2026-06-10 02:00`
4. Wider UTC-shifted: `2026-06-08 17:00 → 2026-06-09 19:00`
5. Current scheduler window: `2026-06-09 19:16 → 2026-06-10 01:18`

**For each probe, log:** `requested_from`, `requested_to`, raw params sent to Omisell, listed count, listed order numbers, whether target appears, status/order time returned if it appears.

---

## 7. Deploy / verification commands (PowerShell)

> Run against prod via the documented authenticated path. Adjust brand as needed. `api` base = `ecentric_workspace.alerts.api_omisell` / `api_sku_catalog` etc.

```powershell
# --- scheduler / pull (api_omisell) ---
# pull_status: overlap_minutes + last_run summary fields
Invoke-FrappeMethod "ecentric_workspace.alerts.api_omisell.pull_status" @{ brand = "FES-VN" }

# pull_recent: trigger one scheduled-style recent pull (uses overlap)
Invoke-FrappeMethod "ecentric_workspace.alerts.api_omisell.pull_recent" @{ brand = "FES-VN" }

# pull_one_order: manual single-order (UNCHANGED by hotfix)
Invoke-FrappeMethod "ecentric_workspace.alerts.api_omisell.pull_one_order" @{ brand = "FES-VN"; order_number = "ODVN260609D6414F3F" }

# --- G2.1 SKU catalog (api_sku_catalog) ---
Invoke-FrappeMethod "ecentric_workspace.alerts.api_sku_catalog.search_skus" @{ brand = "FES-VN"; q = "P02056" }
Invoke-FrappeMethod "ecentric_workspace.alerts.api_sku_catalog.sync_sku_catalog_confirm" @{ brand = "FES-VN" }

# --- brand monitor / readiness (G1) ---
Invoke-FrappeMethod "ecentric_workspace.alerts.api_brands.monitor_brands" @{}

# --- frontend deploy (Web Page records, run from C:\dev\ALERT_CENTER\deploy) ---
powershell -File C:\dev\ALERT_CENTER\deploy\deploy_alert_pages.ps1
```

> NOTE: `Invoke-FrappeMethod` is a placeholder for the project's documented authenticated call wrapper — use the existing helper in the deploy scripts. Method names/args are the canonical ones; confirm the wrapper name in `deploy/` before running.

**Backend deploy (Windows, `C:\dev\ecentric_workspace`):**
```powershell
git -C C:\dev\ecentric_workspace rev-parse --abbrev-ref HEAD   # verify branch FIRST
git -C C:\dev\ecentric_workspace checkout -b fix/scheduler-overlap
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/api_omisell.py   # explicit path
git -C C:\dev\ecentric_workspace commit -m "fix(alerts): scheduled-pull overlap + monotonic checkpoint"
# push -> PR -> merge -> FC deploy (no migrate, code-only)
```

---

## 8. Files changed by recent features

**Backend** (`C:\dev\ecentric_workspace\ecentric_workspace\alerts\`)
- `api_omisell.py` — scheduler overlap hotfix (`_overlap_minutes`, `MAX_OVERLAP_CHUNKS=12`, re-scan, monotonic checkpoint, run rollup, `pull_status.overlap_minutes`).
- `api_dashboard.py` — `+hourly_trend(filters)`.
- `api_policies.py` — `+policy_conflicts(brand)`.
- `api_sku_catalog.py` — NEW (list/search/sync-preview/sync-confirm/`policy_missing_skus`).
- `services/alert_engine.py` — `+import sku_catalog`; fail-open `upsert_from_order_line` at top of line loop.
- `services/sku_catalog.py` — NEW (`catalog_key`, `_row_hash`, `upsert`, `upsert_from_order_line`, `backfill`).
- `doctype/ec_price_policy/ec_price_policy.py` — `_guard_exact_scope_conflict()` + `_scope_key` + `_windows_overlap`.
- `doctype/ec_alert_occurrence/` — NEW DocType (per-line evidence).
- `doctype/ec_brand_alert_config/` — NEW DocType (component include flags).
- `doctype/ec_marketplace_sku_catalog/` — NEW DocType (catalog_key UNIQUE, rsp_price, first/last_seen, is_active, source_level).
- Tests: `tests/test_phase_g1_1.py`, `tests/test_phase_g2.py` (9/9 pass).

**Frontend** (`C:\dev\ALERT_CENTER\`)
- `frontend/build_alert_pages.py` — G1.1 Drop2/polish, G2.1 (SKU modal `pl-sku-modal`, autofill, coverage `pl-coverage`/`pl-cov-modal`, `exportCovTemplate`), Conflict Guard (`al-conf-badge`, `loadConflicts`, `h_all_fallback`), hourly chart (`al-top-row`, `al-hour-panel`, `dash-hourly`, `renderHourly` SVG).
- Deployed HTML pages: 5 single-file Web Pages (alert_center / policies / rules / locks / health) rebuilt — deploy via `deploy/deploy_alert_pages.ps1` (unchanged script).

---

## 9. Known risks / gotchas

- **Old OneDrive repo** caused lock / truncate / revert — do NOT use it.
- **Bash/sandbox mount lags/truncates large builder files** — freshly-Edited big files read truncated in bash (false "unterminated string" / "( never closed"). Read/Grep read host-truth correctly. Prefer Windows host for commits/deploys; use /tmp reassembly (mount head + host-truth tail) for sandbox compile checks.
- **`EC Marketplace Order Item` child row names churn** on order update — do NOT rely on child row names as stable IDs.
- **Use `external_order_id` + `external_line_id`** for evidence identity.
- **Alert rows are snapshots/Cases; Occurrences hold per-order evidence** — don't conflate.
- **`Platform=All` is fallback**; exact-duplicate Active policy (same scope, overlapping validity) is **blocked**.
- **G2.1 LOF-VN catalog may be empty** if no order-derived data exists yet (expected).
- Frappe RestrictedPython sandbox quirks still apply (no `import`, no dunder, no `.append` on raw lists, `doc` not `self` in DocType events, child-array PUT needs `name`, vi-VN number thousand-sep, PS5 ASCII-only `.ps1`).

---

## 10. Next suggested plan

1. **First:** finish the Omisell list/timezone diagnostic (section 6) — read-only probe, 5 windows, log target-appearance.
2. **Then:** fix scheduled-pull list semantics based on the diagnostic (timestamp field / timezone / filter).
3. **Then:** monitor FES-VN / LOF-VN for 24h.
4. **Then (optional):** G2.2 — Omisell product/catalogue GET sync (probe-gated; endpoints exist: Get Product List api-6492412, Get Catalogue List api-5741887, Get Product Detail by SKU api-10762720; not yet in client).

**Deploy order reminder:** deploy the 4 built-but-pending items (scheduler hotfix, G2.1, Conflict Guard, hourly chart) before/around the diagnostic, PM and Alert Center separately, branch verified each time.
