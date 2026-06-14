# Alert Center — Narrow Scheduler Proposal (FES-VN only)

Date: 2026-06-10 · Status: **PROPOSAL — prepare-only, NOT implemented, NOT enabled.** Gate: your explicit approval → small local build → deploy → staged enablement below. Everything stays read-only; DS1 locked; no stock/buffer write.

## 1. What would be scheduled

One cron entry in `hooks.py` (the ONLY hooks change since Phase E):
```python
"cron": { ...existing */10 queue worker...,
  "*/15 * * * *": ["ecentric_workspace.alerts.tasks.scheduled_omisell_pull"],
}
```
New `tasks.scheduled_omisell_pull()` — thin, boring, and quadruple-gated:
1. `ec_alerts_scheduler_disabled` (existing global kill switch — parsed with the SAFE parser) → no-op.
2. `ec_alerts_pull_disabled` (pull-specific switch) → no-op.
3. **Brand allowlist**: `ec_alerts_scheduled_pull_brands` (site_config list, proposal: `["FES-VN"]`) — only listed brands run; empty/missing list = no-op (fail-safe). Multi-brand later = config change, not code.
4. Per-brand: BIS `enabled=1` + `credential_status=Active` + circuit breaker (`consecutive_failures < 3`) + per-brand running-lock (reuses `_running_key`).
Then it simply enqueues the **same `pull_recent_job`** that manual verification just proved (4 chunks ≤1h, detail cap 300, chunk checkpointing, timeboxes, diagnostics, breaker). No new pull logic — the scheduler is just a timer in front of verified code.

## 2. Sizing (FES-VN, from verified data)

Observed ≈0–7 orders/hour → a */15 run typically processes 1 chunk with 0–2 orders in seconds; catch-up after downtime is bounded (4 chunks/run → worst case 4h recovered per 15 min, backlog drains automatically). Rate budget trivially safe (≤10 calls/run vs 100/min leak).

## 3. Enable/disable controls (all instant, no deploy)

| Control | Effect |
|---|---|
| `ec_alerts_scheduled_pull_brands: []` or remove key | scheduler runs but pulls nothing (fail-safe default) |
| `ec_alerts_pull_disabled: 1` | stops scheduled AND manual pulls |
| `ec_alerts_scheduler_disabled: 1` | stops ALL alert-center jobs (incl. pause-expiry/queue worker — note: those are currently OFF anyway under this same switch; see §6) |
| BIS FES-VN `enabled=0` | stops this brand only |
| Circuit breaker ≥3 | self-stops the brand until you reset `consecutive_failures` |

## 4. Staged enablement runbook (after build+deploy approval)

1. Deploy with `ec_alerts_scheduled_pull_brands` ABSENT → scheduler entry registers but every run no-ops (prove the no-op in logs for one cycle).
2. Set `ec_alerts_scheduled_pull_brands: ["FES-VN"]` AND remove `ec_alerts_scheduler_disabled` (decision needed — §6) → first real cycle.
3. Watch 24h (checklist §5). 4. Review → widen brands or adjust cadence (separate decisions).

## 5. Monitoring checklist (daily for the first week — all read-only)

- `pull_status FES-VN`: `last_sync_at` advancing ≈ now−15..30 min; `consecutive_failures = 0`; `running_since` null between cycles; `last_run.state = done`, `caught_up = true`, failed=0.
- `/alerts`: new price alerts appearing for real violations; `ingestion_api_failed` alert ABSENT (its appearance = actionable diagnostics now, per observability hotfix).
- `capacity_stats` weekly: row growth vs the 160 baseline (~real volume check vs 100K/month assumption); 2M archive-review trigger.
- FC dashboard: no worker timeouts, scheduler job duration seconds-not-minutes, Error Log free of `alerts.omisell.*` entries.
- BIS FES-VN Comments: one summary per non-trivial run (audit trail).

## 6. Decision needed alongside approval

`ec_alerts_scheduler_disabled=1` currently also keeps the **pause-expiry + dry-run queue worker** (shipped in Phase E) dormant. Enabling the pull scheduler requires removing that key — which would also wake those two (both dry-run-safe, were approved in D2-E, just never enabled). Options: **(a)** remove the key — all three jobs go live (recommended: pause-expiry is needed for KAM usability anyway); **(b)** keep the key and give the pull job its own inverse switch (more config sprawl). Recommend (a) — say which.

## 7. Build scope when approved (small)

`tasks.py` +~40 lines (`scheduled_omisell_pull` with the 4 gates), `hooks.py` +1 cron line, tests (+gate matrix in sandbox style), pre-push checks, deploy via standard flow. Rollback = any §3 switch (instant) or revert PR.

## Unchanged

Omisell client read-only (`ALLOWED_METHODS={GET}`), no stock/buffer write (DS1 locked), no archive/delete, no nightly reconciliation (D.2), no PM files.
