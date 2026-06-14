# Incident + Hotfix — pull_recent Bench 502 (2026-06-09)

Status: **Hotfix `883520a` on `alerts-phase-d1-hotfix-pull` — local, NOT pushed/deployed. Do not run pull_recent until it ships.**

## 1. What happened (analysis)

First `pull_recent` (max_chunks=1) **completed successfully**: window 11:00→12:00 processed, chunks_done=1 → `last_sync_at` advanced to 12:00 (the "to=22:44" in the response was the overall now-bound, not the processed range — only chunk 1 ran). The PowerShell "truncation" was display-only. The **second** call planned window 12:00→13:00 and died with Bad Gateway.

Root cause (my design flaw in D.1): the Omisell client paces ≥1s/call by design; `pull_recent` ran list + up to 300 detail GETs + DB writes **inside one synchronous web request**. That can take minutes; the gunicorn worker timeout (~120s) kills the worker mid-request → with workers tied up/recycling, FC shows "bench appears to be down". Verify in FC: web error log around the timestamp should show `WORKER TIMEOUT`/SIGKILL (no code exception expected). Recovery: bench self-heals once workers recycle — no data corruption possible (per-chunk transaction; an interrupted chunk does NOT advance `last_sync_at`; idempotent re-pull by design).

## 2. State inspection (run these BEFORE next steps — read-only)

```powershell
# a. bench alive again?
Invoke-RestMethod -Uri "https://team.ecentric.vn/api/method/ping" -Headers $h
# b. checkpoint + breaker state:
Invoke-RestMethod -Headers $h -Uri "https://team.ecentric.vn/api/resource/EC Brand Integration Settings?filters=[[%22brand%22,%22=%22,%22FES-VN%22]]&fields=[%22name%22,%22last_sync_at%22,%22consecutive_failures%22,%22enabled%22]"
# EXPECT: last_sync_at = 2026-06-07 12:00:00 (chunk 1 end). If it shows 13:00 the 2nd chunk
# actually completed before the 502 (also fine). consecutive_failures should be 0.
# c. what was ingested:
Invoke-RestMethod -Method Post -Headers $h -Uri "https://team.ecentric.vn/api/method/ecentric_workspace.alerts.api_omisell.capacity_stats"
# compare counts vs the saved baseline (Log=11/Item=21) -> the delta = chunk-1 (+maybe partial chunk-2) orders
# Partial chunk-2 ingestion (if any) is SAFE: dedupe keys make the re-pull a no-op.
```
**Interim guard until hotfix deploys:** FC Site Config → `"ec_alerts_pull_disabled": 1` (remove after deploy).

## 3. The hotfix (commit `883520a`, 2 files, +188/−27)

1. **`pull_recent` → background job**: enqueues `pull_recent_job` (queue `long`, rq timeout 3600s), returns `{queued, job_id}` instantly. Per-brand cache lock blocks concurrent runs. Job summary → cache (24h) + Comment on the BIS record (audit trail). The job is NOT whitelisted and NOT scheduled.
2. **Timeboxes**: `pull_orders` gains `time_budget` — direct web calls hard-capped at **50s** (safely under worker timeout, even with max_chunks=1 and a dense window); job chunks share `JOB_TIME_BUDGET=3000s`. Timebox checked in both list and detail loops; a timeboxed/capped chunk holds the checkpoint and is NOT a breaker failure.
3. **`pull_preview(brand, hours)`**: order-list COUNT only (1 API call, zero writes) — size the backlog before pulling.
4. **`pull_status(brand)`**: running flag, last run summary, `last_sync_at`, breaker count — solves the PowerShell-truncation problem too (re-readable any time).
5. Latent NameError fixed (module-scope `timedelta`).
6. Tests: **+TestPullSafety ×5** (budgets sane; pull_recent contains enqueue and NO inline pulling; job not whitelisted; timebox present; preview is count-only). Sandbox total **24/24 PASS**. Read-only guarantees re-verified (client untouched).

## 4. Deploy checklist — PRE-PUSH OUTPUT (verified read-only 2026-06-09, after fresh fetch)

| # | Check | Result |
|---|---|---|
| 1 | Branch `alerts-phase-d1-hotfix-pull`, tip `883520a` | ✅ |
| 2 | Diff vs fresh origin/main (`c28cdd1` = PR #7 merge) | ✅ +188/−27 |
| 3 | Exactly 2 files: `api_omisell.py`, `tests/test_phase_d1.py` | ✅ |
| 4 | 0 `pm/**` | ✅ |
| 5 | 0 hooks.py | ✅ |
| 6 | 0 `scheduler_events` refs in alerts/ blobs | ✅ |
| 7 | Client read-only: diff vs origin/main = **0 lines**, `ALLOWED_METHODS = frozenset({"GET"})` present in blob | ✅ |
| 8 | `pull_recent` = whitelisted wrapper containing `frappe.enqueue` + instant `{queued: True, job_id}`; no inline pulling (TestPullSafety asserts) | ✅ |
| 9 | `pull_status` + `pull_preview` both whitelisted (POST, SM-only) | ✅ |
| 10 | Concurrency: `_running_key` cache lock + "already running" refusal (6 refs) | ✅ |
| 11 | No archive/delete (grep NONE) | ✅ |
| 12 | No stock/buffer/inventory write (grep NONE; DS1 locked) | ✅ |

**Deploy:** set Site Config `ec_alerts_pull_disabled = 1` FIRST (operational decision) → push → PR #8 → Files-changed gate (2 files) → merge → FC Deploy (code-only, migrate no-op). **Rollback:** revert PR (returns to pre-hotfix code — keep `ec_alerts_pull_disabled=1` in that case since the old sync path is the hazard); instant stop any time via the same flag or BIS `enabled=0`; no schema/data to unwind; nothing Omisell-side.

## 5. Post-fix probes (in order)

1. `pull_status FES-VN` → 200, `running_since: null`, correct `last_sync_at`, breaker 0.
2. `pull_preview FES-VN` → `would_list` count for the next window (instant, no writes).
3. Remove `ec_alerts_pull_disabled` → `pull_recent FES-VN` → expect **instant** `{queued: true, job_id}`.
4. Poll `pull_status` until `last_run.state = "done"` → review `summaries[]` (each chunk: listed/ingested/elapsed_seconds) + `caught_up`.
5. Immediately re-call `pull_recent` while job runs → expect clean "already running" refusal (lock works).
6. `capacity_stats` delta + spot-check Order Log records; `/alerts` unaffected.
7. Re-run once more after done → near-empty window, idempotent.

## 6. Unchanged guarantees

Omisell client untouched (GET-only frozen), no scheduler entry, kill switches intact (+`ec_alerts_pull_disabled` now doing its job as designed), no stock/buffer path (DS1), no pm/, no archive/delete.
