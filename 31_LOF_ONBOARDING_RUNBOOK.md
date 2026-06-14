# Alert Center — LOF (Brand #2) Onboarding Runbook

Date: 2026-06-08 · Owner runs every step on Windows (PS5). Goal: bring **LOF** online as the 2nd monitored brand (highest price-compliance risk) using only **proven, verified code paths** — no new pull logic. FES-VN keeps running untouched.

**Constraints (enforced throughout):** No Omisell write path · No stock/buffer/inventory write · DS1 remains locked (`dry_run_stock_lock=1`) · Stock Safety Lock stays dry-run only · FES-VN scheduler logic unchanged · custom rules NOT activated.

**Brand code:** convention is `<CODE>-VN` (FES-VN, FCV-VN, BBT-VN, AND-VN) → LOF is almost certainly **`LOF-VN`**. This is **confirmed by Step 1, not assumed** — the `Brand Approver` record name is the source of truth. If the record is named `LOF` (no suffix), pass `-Brand LOF` to every script.

The only **production write** in this runbook is Step 8 (add LOF to the scheduler allowlist in site_config). Everything before it is read-only to Omisell; ingestion in Steps 5–7 writes only Frappe records (Order Log / Item / EC Alert), which is the intended catch-up.

---

## Scripts (all in `ALERT_CENTER/deploy/`)

| Script | What it does | Writes? |
|---|---|---|
| `onboard_lof_preflight.ps1` | Steps 1–4: resolve code, KAM scope, BIS, allowlist reminder | **No** (read-only) |
| `onboard_lof_pull.ps1` | A probe → B preview → (stop unless `-Confirm`) → C pull → D poll → E verify | Probe sets `credential_status`; pull ingests to **Frappe only** |
| `monitor_brands.ps1` | Step 9: 24h health line per brand | **No** (read-only) |

---

## Step 1–4 — Preflight (READ-ONLY)

```powershell
cd "C:\Users\admin\NextCommerce\Data - Documents\General\ERP Website\ALERT_CENTER\deploy"
.\onboard_lof_preflight.ps1            # auto-tries LOF-VN then LOF
# or force: .\onboard_lof_preflight.ps1 -Brand LOF-VN
```

It checks and prints:

1. **Brand code** — finds the `Brand Approver` record (`LOF-VN` or `LOF`); ABORTS if neither exists. The printed `Brand code CONFIRMED = '...'` is the answer to "LOF or LOF-VN".
2. **KAM scope** — `status=Active`; `kam_owner` / `manager_email` / `leader_email`. Empty `kam_owner` is a WARN (alerts get a fallback owner); zero scope users is a blocker for non-SM access.
3. **EC Brand Integration Settings (Omisell)** — record exists; `enabled=1`; `credential_status` (Active or "validate via probe"); `base_url`; `api_key`/`api_secret` configured (Password fields show masked when set); `last_sync_at` (empty is fine for a new brand → first window defaults to now−1h); `consecutive_failures=0`; **`dry_run_stock_lock=1`** (DS1 — blocker if not).
4. **Allowlist reminder** — `ec_alerts_scheduled_pull_brands` is not REST-readable; confirm on the FC dashboard it is still `["FES-VN"]`. Do **not** add LOF here yet.

**Gate:** `PREFLIGHT PASSED` with 0 blockers → continue. Any `[ERR]` → fix in Desk first (BIS is System-Manager-only).

---

## Step 4–7 — Manual pull + verify

First run **without** `-Confirm` (safe: probe + preview only, nothing ingested):

```powershell
.\onboard_lof_pull.ps1 -Brand LOF-VN
```

- **A `omisell_probe`** — auth + 1 shop; proves credentials, sets `credential_status=Active`. Failure → ABORT (fix keys).
- **B `pull_preview`** (Step 4) — read-only count: `would_list = N` for the next ≤1h window. No DB write.
- Then it **STOPS** and tells you to re-run with `-Confirm`.

Review `would_list`. When ready, run the real pull (Step 5):

```powershell
.\onboard_lof_pull.ps1 -Brand LOF-VN -Confirm
```

- **C `pull_recent`** (Step 5) — enqueues the **same background job** FES-VN uses (`pull_recent_job`, queue `long`, ≤4 chunks of ≤1h, chunk-level checkpointing). Returns immediately with a `job_id`.
- **D poll `pull_status`** (Step 6) — every 10s until the run finishes (default timeout 600s; raise with `-MaxPollSeconds`).
- **E verify** (Step 7) — gates:
  - `state = done`
  - `breaker = 0` (`consecutive_failures`)
  - `failed = 0` (summed across chunks)
  - **no stuck running lock** (`running_since` cleared)
  - **alerts appear under LOF** — queries `EC Alert` for `brand=LOF-VN`. (WARN-only if zero: a clean window with no priced violations is legitimate; widen the window or wait for order activity.)

`MANUAL PULL VERIFIED` with 0 blockers → proceed to Step 8. Any blocker → do **not** add LOF to the allowlist; the checkpoint holds, so re-running `-Confirm` is safe.

> Re-runnable & idempotent: dedupe keys (decision C1) make re-pulls no-ops; a failed/capped/timeboxed chunk holds the checkpoint and stops, so nothing is skipped.

---

## Step 8 — Add LOF to the scheduled allowlist (PRODUCTION WRITE — needs explicit go-ahead)

Only after Step 7 passes. Edit site_config on **Frappe Cloud**:

```
ec_alerts_scheduled_pull_brands:  ["FES-VN", "LOF-VN"]
```

(FC dashboard → Site Config; or `bench --site team.ecentric.vn set-config -p ec_alerts_scheduled_pull_brands '["FES-VN","LOF-VN"]'`.)

Why this is safe to add: `scheduled_omisell_pull` re-checks **per brand** every 15 min — BIS `enabled=1` + `credential_status=Active` + breaker `< 3` + no running lock — and skips any brand that fails. It calls the identical `pull_recent_job`; no FES-VN code changes. Do **not** touch `ec_alerts_scheduler_disabled` or `ec_alerts_pull_disabled` (global kill switches stay as they are).

Confirm after the edit: within ~15 min, `monitor_brands.ps1` should show LOF-VN `last_state=done` and `sync_age_min` shrinking.

**Instant rollback:** remove `"LOF-VN"` from the list (back to `["FES-VN"]`) — no deploy. Per-brand stop: set BIS `enabled=0` for LOF.

---

## Step 9 — Monitor both brands for 24h

Run ad hoc through the window:

```powershell
.\monitor_brands.ps1                       # FES-VN + LOF-VN
```

One line per brand: `run` (idle/yes), `sync_age_min`, `breaker`, `last_state`, `failed`, `pull_disabled`. Healthy = `idle`, `sync_age_min` under ~45, `breaker=0`, `last_state=done`, `failed=0`. The script flags ERR on any failure/breaker and WARN on stale sync.

Exit criteria (both brands, 24h): no breaker trips, no stuck locks, no 502/timeout, `last_sync_at` advancing each cycle, alerts landing under each brand. On pass → LOF is a permanent monitored brand.

---

## Abort / escalation quick table

| Symptom | Meaning | Action |
|---|---|---|
| Preflight: no Brand Approver | brand code wrong / record missing | confirm name in Desk; pass `-Brand` |
| Preflight: `dry_run_stock_lock != 1` | DS1 not honored | set it to 1 on BIS before any pull |
| Probe FAILED | bad/expired credentials | fix `api_key`/`api_secret` in BIS; `credential_status` auto-set Expired + alert raised |
| `state=error` | job exception | read `last_run.error` + the `ingestion_api_failed` alert; checkpoint held |
| `failed > 0` | some order details failed | inspect `failed_order_numbers`; transient 5xx auto-retries; persistent → `ec_alerts_pull_skip_orders` poison-pill list |
| breaker `>= 3` | circuit open | investigate, then reset `consecutive_failures=0` on BIS |
| stuck running lock | poll timed out / worker died | re-run `pull_status`; lock TTL clears it; re-run `-Confirm` |

---

## What this runbook deliberately does NOT do

No 2nd-brand price policies are required to start (missing_policy alerts will simply surface where LOF has no policy yet — that is the expected discovery signal). No custom rule activation. No DS1 / stock-write. No Omisell write. No change to FES-VN. Those remain separate, individually-gated steps.
