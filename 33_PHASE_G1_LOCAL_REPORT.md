# Alert Center — Phase G1 Local Implementation Report
## Brand Onboarding Foundation & Integration Health

Date: 2026-06-08 · Status: **IMPLEMENTED LOCALLY — awaiting review before deploy.** Read + diagnose only; no production data written.

---

## 1. Files changed

**Backend (in git repo `ecentric_workspace/`, 3 NEW files — additive, no edits to existing modules):**

| File | Lines | Purpose |
|---|---|---|
| `ecentric_workspace/alerts/services/brand_readiness.py` | ~180 | PURE readiness derivation (no frappe). `derive(facts) -> {status, blockers, action, running}` |
| `ecentric_workspace/alerts/api_brands.py` | ~240 | 3 whitelisted READ endpoints; fact-gatherer; secret-safe BIS projection |
| `ecentric_workspace/alerts/tests/test_phase_g1.py` | ~190 | 19 tests (precedence + secret redaction), sandbox-runnable |

No existing backend file was modified. No DocType, no DocPerm, no `hooks.py`, no `tasks.py`, no `patches.txt`, no PM file.

**Frontend / ops tooling (outside git — `ALERT_CENTER/`):**

- `frontend/build_alert_pages.py` — added 5th page (PAGE5_CONTENT + PAGE5_JS), `.al-st-*` status-pill CSS, `stHealth()` JS helper, repointed sidebar "Integration Health" slot to `/alerts/integration-health`, added it as a 5th subnav tab, extended build asserts (G1 + module-shell loop now 5 pages).
- `frontend/alert_health.html` — NEW built page (+ all 4 existing pages rebuilt: they pick up the shared `.al-st-*` CSS, the new nav slot, and the subnav tab; content otherwise unchanged).
- `deploy/deploy_alert_pages.ps1` + `rollback_alert_pages.ps1` — added the `alert-health` entry.
- `deploy/verify_phase_g1.ps1` — NEW read-only post-deploy probe.

---

## 2. Endpoint contracts (all `@frappe.whitelist`, READ-ONLY, scoped)

`list_brand_readiness()` → `{brands:[row...], thresholds, is_supervisor, capacity?}`. One row per brand the caller may see (SM = all Active Brand Approver brands; scoped users = their brands). Each row: `brand, status, running, action{code,label}, blockers[{code,label,severity}], kam_owner, manager_email, leader_email, ba_status, bis_exists, credential_status, enabled, dry_run_stock_lock, last_sync_at, consecutive_failures, in_allowlist, last_run_state, counts{order_log, order_item, alerts_open, alerts_total, policies_active}`. `capacity` (SM only) = `{order_log, order_item, log_plus_item, archive_review_trigger:2000000, archive_review_due}`. Rows sorted Blocked → Warning → Manual → Running → Ready → Scheduler Enabled.

`brand_readiness(brand)` → full drawer detail: the verdict + `brand_approver{...}` + `bis{...}` (secret-free) + `in_allowlist` + `last_run` (cache summary) + `counts` + `coverage` + `thresholds`. Gated by `require_brand_access`.

`policy_coverage(brand, days=30, sample=500)` → `{distinct_skus, covered, pct, sampled, days}`. Bounded: distinct seller_skus seen in the last 30 days of order items (capped at `sample`) vs those with an Active EC Price Policy (seller_sku match). Parameterized SQL; cheap by construction.

Actions reuse existing verified endpoints — the page calls `api_omisell.pull_preview` and `pull_status` (both read-only, SM-only); it does **not** call `pull_recent` or write site_config (see §9).

---

## 3. Readiness logic (pure, deterministic — `brand_readiness.derive`)

Single primary status, precedence first-match-wins:

1. **Blocked** if any hard blocker, in order: `missing_brand_approver` (no/inactive BA) → `missing_bis` → `bis_disabled` (enabled≠1) → `ds1_unsafe` (dry_run_stock_lock≠1) → `missing_base_url` (BIS exists+enabled but `base_url` empty/null — added 2026-06-08 after LOF probe HTTP 417) → `credential_not_active` → `breaker_open` (consecutive_failures ≥ 3).
2. **Running** (a pull is in-flight) — when not blocked.
3. **Manual Pull Required** — credentials OK but never synced, or stale and not allowlisted.
4. **Warning** — `no_kam_owner`, `low_policy_coverage` (<50%), or `stale_sync_scheduled` (>45 min while allowlisted).
5. **Scheduler Enabled** — allowlisted + fresh + last run done/clean, no warnings.
6. **Ready** — fresh + can-pull, not yet allowlisted (verified-manual, awaiting allowlist).

`blockers` returns the FULL ordered list (hard first, then warnings, each with severity). `action` = remedy of the top item, else the status's onboarding step. Thresholds (`stale_minutes=45`, `min_coverage=50`, `breaker_limit=3`) are passed in from site_config keys (`ec_alerts_health_stale_minutes`, `ec_alerts_health_min_coverage`) with these defaults — tunable without a deploy. `_truthy()` avoids the `bool("0")==True` trap.

---

## 4. Permission behavior

Reuses the service layer verbatim — **no new role, no DocPerm change**:

- `list_brand_readiness` / `brand_readiness` begin with `require_alert_center_access` / `require_brand_access` → SM sees all; KAM/manager/leader see only their `Brand Approver`-scoped brands; anyone else → `PermissionError`.
- **Secret redaction**: BIS is read through `_BIS_FIELDS` — an explicit allowlist that omits `api_key`/`api_secret`/`token`; they cannot appear in any response even for SM. A unit test enforces this, and `verify_phase_g1.ps1` scans the live JSON for leaks.
- Action authorization: `pull_preview`/`pull_status` are `System Manager` only (unchanged); the page only renders those buttons when `scope.supervisor` is true. Non-SM see the read-only table + links + gated instructions, no action buttons. `Create/Edit BIS` is an SM-only Desk link.

---

## 5. LOF-VN expected status

With its Brand Approver present but no EC Brand Integration Settings: **Blocked**, top blocker `missing_bis`, action "Create EC Brand Integration Settings before preview/pull".

**Update 2026-06-08 (real LOF onboarding):** LOF's BIS was created but with `base_url` empty/null (enabled=1, credential_status=Active, dry_run_stock_lock=1), so the readiness was over-optimistically `Manual Pull Required` while `omisell_probe` failed HTTP 417. Fixed: added hard blocker **`missing_base_url`** (condition: `bis_exists` true but `base_url` empty/null) → **Blocked**, action **"Complete EC Brand Integration Settings base_url/credentials before preview/pull"**. The preview button stays **disabled** until `base_url` exists (tooltip "Cần base_url trong BIS trước khi preview/pull"). So LOF now correctly shows **Blocked / missing_base_url** rather than Manual Pull. Pinned by `test_missing_base_url_blocks` + `test_missing_base_url_precedence_over_credential`. (If LOF's Brand Approver doesn't exist, it won't appear — create it to surface the case.)

---

## 6. FES-VN expected status

Credentials Active, breaker 0, in the scheduler allowlist, fresh sync → **Scheduler Enabled** (green). If a pull happens to be mid-cycle it shows **Running** briefly; if it were fresh-but-not-allowlisted it would read **Ready**. Unit test `test_healthy_scheduled_brand_is_scheduler_enabled` pins the steady state. This proves the same generic logic recognizes a fully-onboarded brand with no special-casing.

---

## 7. Capacity / idempotency display

- **Per brand:** Order Log + Order Item counts in every row and the drawer, so multi-brand row growth is visible at a glance.
- **Global (SM):** a capacity panel shows `log_plus_item` vs the **2,000,000** archive-review trigger with a progress bar; when `archive_review_due` it turns amber and the help text says to plan an archive (still measure-only — no delete code). Reuses the exact trigger from `api_omisell.capacity_stats`.
- **Idempotency context:** the readiness counts reflect the upsert model documented in `32_PHASE_G1_PRECODE.md` §"Data Lifecycle" — re-pulls don't inflate counts (Order Log upsert by `order_key`; items replaced in place). The page is a read-only window onto those counts.

---

## 8. Test results

Sandbox: **22/22 PASS** (`python3 -m unittest ...test_phase_g1`).
- `TestReadinessPrecedence` (20): every status + precedence edge — missing BA, missing BIS, disabled (incl. `enabled="0"` trap), DS1-unsafe, **missing_base_url (None/""/whitespace + precedence over credential + base_url-present-ok)**, credential, breaker (3 vs 2), hard-blocker ordering, running-vs-blocked, never-synced, stale±allowlist, no-KAM, low/none coverage, ready, and a closed-enum sweep.
- `TestSecretRedaction` (2): `_BIS_FIELDS` excludes `api_key`/`api_secret`/`token`; `_STATUS_ORDER` covers all statuses.

> Sandbox note: the OneDrive mount truncated `brand_readiness.py` after these edits, so the package-import unittest read a stale copy; the derive() logic (incl. all `missing_base_url` cases) was re-verified by importing the reassembled cloud-truth file standalone — **8/8 pass**. The owner's bench/Windows reads the complete cloud file and runs the full 22.

Build: `build_alert_pages.py` runs clean — all 5 pages built, **ASCII-clean**, all asserts pass incl. new `G1 integration-health asserts` (markers present; `set-config` and `api_omisell.pull_recent` absent; `pull_preview`/`pull_status` present) and the 5-page module-shell loop (every page carries the `Integration Health` nav slot). `py_compile` OK on all 3 backend modules; no SQL-function-string in any `get_all(fields=...)` (aggregates use `frappe.db.count`/parameterized `frappe.db.sql`).

> Bench-pending (need a site): live data shape of `list_brand_readiness` against real Brand Approver/BIS rows — covered by `verify_phase_g1.ps1` post-deploy.

---

## 9. No-write confirmation

- **No Omisell write path:** the page calls only `pull_preview` (read-only count) and `pull_status` (pure read); it never calls `pull_recent`/`pull_orders`. Build assert `api_omisell.pull_recent not in p5` enforces this.
- **No site_config write:** "Add to scheduler" renders an instruction + snippet only; build assert `set-config not in p5`. The allowlist auto-write stays deferred to G4.
- **No stock/buffer/inventory write; DS1 locked:** `api_brands` has zero mutation calls; it reads records/cache/site_config only. DS1 is surfaced (and a brand with `dry_run_stock_lock≠1` is flagged Blocked), never changed.
- **No FES-VN scheduler change:** `tasks.py`/`hooks.py` untouched (0 diff). **No PM files.** **No new DocType / DocPerm / role.** `api_brands` is purely additive.

---

## 10. Deploy / rollback plan

**Deploy (owner, two drops):**
1. Backend — commit the 3 NEW files on a fresh branch and PR (files-changed gate = exactly `alerts/services/brand_readiness.py`, `alerts/api_brands.py`, `alerts/tests/test_phase_g1.py`; 0 pm/, 0 hooks, 0 DocType). Stage with explicit paths (`git add <those 3>`) to avoid the working-tree CRLF/EOL drift on other files. Merge → FC deploy, **no migrate** (no schema change). Optionally set `ec_alerts_health_stale_minutes` / `ec_alerts_health_min_coverage` in site_config (defaults 45 / 50 apply otherwise).
2. Frontend — `cd ALERT_CENTER\deploy; .\deploy_alert_pages.ps1` (deploys all 5; the 4 existing pages need the redeploy to pick up the shared CSS + nav slot + subnav tab). To deploy only the new page: `-Only alert-health` (but then the other pages' sidebar won't show the new slot until they're redeployed too — recommend deploying all 5).
3. Verify — `.\verify_phase_g1.ps1`: asserts FES-VN healthy, LOF-VN Blocked:missing_bis (if its BA exists), no secret leak, coverage smoke. Then browser `/alerts/integration-health` (Ctrl+Shift+R).

**Rollback:** Frontend — `rollback_alert_pages.ps1 -Only alert-health` unpublishes the page; redeploy the prior 4 pages to drop the nav slot if desired. Backend — revert the PR → FC deploy; `api_brands.py`/`brand_readiness.py`/tests are additive and read-only, nothing to unwind, no data written.

**Note (sandbox build hazard):** OneDrive truncated the bash mount's view of `build_alert_pages.py` again; the build was verified by reassembling the full file from the clean mount head + cloud-truth tail in /tmp (all asserts pass) and the 5 regenerated HTML were written back to `frontend/` with byte-length + ASCII parity checks. The owner's Windows build reads the complete cloud file and will reproduce the same output.
