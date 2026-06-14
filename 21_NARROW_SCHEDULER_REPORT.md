# Alert Center — Narrow Scheduler Implementation Report (FES-VN gate design)

Date: 2026-06-10 · Status: **IMPLEMENTED LOCALLY — branch `alerts-scheduler-narrow`, commits `44310d2` + `e9801ea` (off `8a4c9f6` = origin/main with PR #10). NOT pushed/deployed. Scheduler will register at deploy but pulls NOTHING until staged enablement.**

## 1. Files changed (4 files, +152/−3)

`alerts/tasks.py` (+72: `scheduled_omisell_pull` + `_scheduled_brands` + safe parser on `_disabled`), `hooks.py` (+6, see §2), `alerts/tests/test_phase_d1.py` (+62: TestSchedulerGates), `alerts/services/omisell_normalizer.py` (+11/−2 — **carried-over Q-D2 terminology docs**: local commit `d841400` had missed PR #10 because the branch was pushed before it landed; identical comment-only content, now in `e9801ea`).

## 2. Exact hooks.py diff (the ONLY hooks change)

```diff
         "*/10 * * * *": [
             "ecentric_workspace.alerts.tasks.process_action_queue_job",
         ],
+        # Narrow Omisell pull scheduler (approved 2026-06-10): quadruple-gated
+        # in tasks.scheduled_omisell_pull - runs nothing until site_config
+        # ec_alerts_scheduled_pull_brands lists at least one brand.
+        "*/15 * * * *": [
+            "ecentric_workspace.alerts.tasks.scheduled_omisell_pull",
+        ],
```

## 3. Scheduler gate behavior (fail-safe at every layer)

`scheduled_omisell_pull()` per run: (1) `ec_alerts_scheduler_disabled` via the **safe parser** (the `bool("0")` trap is now fixed for this switch too) → `{"skipped": "scheduler_disabled"}` · (2) `ec_alerts_pull_disabled` (safe parser) → skipped · (3) `ec_alerts_scheduled_pull_brands` missing/empty/non-list → `{"skipped": "no_brands_configured"}` (strings stripped; non-list = fail-safe []) · (4) per brand: BIS missing/disabled → skip; `credential_status≠Active` → skip; breaker ≥3 → skip; running-lock present → skip; per-brand try/except → `error_logged`, never kills the batch. Survivors get the running lock + `frappe.enqueue(pull_recent_job, queue long, timeout 3600)` — **the exact job verified on FES-VN**, with all its chunking/checkpoint/timebox/diagnostics. Every run's result is logged (`frappe.logger("alerts")`).

## 4. Tests

Sandbox **34/34 PASS** (full regression: NoWrite 7, Normalizer 6, Chunker 5, NoSqlFunctionStrings 1, PullSafety 5, DisabledFlagParser 2, Observability 3, **+SchedulerGates 5**). SchedulerGates covers: allowlist parser table (8 cases incl. non-list/empty/whitespace fail-safes), gate order + all 7 no-op/skip paths present, **verified-job reuse + zero pull logic in tasks.py** (asserts no `OmisellClient(`/`get_orders(`/`get_order_detail`/`ingest_orders` anywhere in the module), safe parser wired on the scheduler switch, hooks cron entry present.

## 5. No-write confirmation

Client blob untouched and `ALLOWED_METHODS={GET}` verified at commit; tasks.py contains no API/pull logic (test-enforced); no stock/buffer/inventory path; no archive/delete; no nightly reconciliation; no PM files (0 pm/ in branch diff). DS1 locked.

## 6. Deploy checklist (owner machine, per-turn confirm)

1. Pre-push: `git fetch` → `git diff --name-status origin/main..alerts-scheduler-narrow` = exactly 4 files (hooks.py **expected** this time), 0 pm/. 2. Push → PR #11 → Files-changed gate → merge → FC Deploy (code-only; migrate harmless). 3. Scheduler registers **but**: `ec_alerts_scheduler_disabled=1` still ON + allowlist absent ⇒ double-dormant.

## 7. Staged enablement checklist (your approved sequence — each step its own confirmation)

1. **Deploy with `ec_alerts_scheduled_pull_brands` ABSENT.** ✔ gate 3 no-ops even after switch removal.
2. **Remove `ec_alerts_scheduler_disabled`** (option (a) approved): wakes pause-expiry + dry-run queue worker + pull scheduler. Sanity right after: EC Automation Pause expired rows flip within the hour; queue worker drains nothing (0 Pending); no Error Log entries.
3. **Verify one no-op pull cycle** (≤15 min wait): FC scheduler log / `frappe.logger("alerts")` shows `{"skipped": "no_brands_configured"}`; `pull_status FES-VN` unchanged.
4. **Set `ec_alerts_scheduled_pull_brands: ["FES-VN"]`** → first real cycle within 15 min.
5. **24h monitoring:** `pull_status FES-VN` — `last_sync_at` ≈ now−(15..30min), breaker=0, `running_since` null between cycles, `last_run.state=done`, failed=0; `/alerts` healthy + new real alerts only; no `ingestion_api_failed`; `capacity_stats` growth sane vs Log=54/Item=106 baseline; FC: no worker timeout/502; BIS Comments show run summaries.

## FINAL PRE-PUSH OUTPUT (verified read-only 2026-06-10, after fresh fetch — for your review before push)

| # | Check | Result |
|---|---|---|
| 1 | Branch `alerts-scheduler-narrow`, tips `e9801ea` ← `44310d2` | ✅ |
| 2 | Diff vs fresh origin/main (`8a4c9f6` = PR #10 merge) | ✅ +152/−3 |
| 3 | Exactly 4 files (tasks.py, hooks.py, test_phase_d1.py, omisell_normalizer.py) | ✅ |
| 4 | hooks.py diff = ONLY the approved cron block (+6 lines: 3 comments + `"*/15 * * * *"` + 1 target + closing) — full diff re-printed and matched §2 byte-for-byte | ✅ |
| 5 | 0 `pm/**` | ✅ |
| 6 | No Omisell write path: client diff vs origin/main = **0 lines**; `frozenset({"GET"})` present in blob; tasks.py test-enforced free of client/pull calls | ✅ |
| 7 | No stock/buffer write: branch diff greps 0 for adjust/buffer-write patterns; DS1 locked | ✅ |
| 8 | No archive/delete: branch diff greps 0 for delete_doc/truncate/drop | ✅ |
| 9 | Allowlist missing/empty ⇒ no-op: blob shows non-list→`[]` + `no_brands_configured` skip path; TestSchedulerGates table covers 8 fail-safe cases | ✅ |
| 10 | Deploy + staged enablement checklist = §6–§7 (deploy with allowlist ABSENT → remove scheduler_disabled → verify no-op cycle → set `["FES-VN"]` → 24h monitoring) — matches your 5-step rule exactly | ✅ |
| 11 | Rollback plan = §8 below (5 instant controls + revert PR #11) | ✅ |

## 8. Rollback plan (all instant, no deploy)

`ec_alerts_scheduled_pull_brands: []` → stops scheduled pull only · `ec_alerts_pull_disabled: 1` → stops manual+scheduled pulls · `ec_alerts_scheduler_disabled: 1` → stops all three jobs · BIS `enabled=0` → FES-VN only · breaker self-stops after 3 failures. Code rollback: revert PR #11 (cron entry + function disappear; nothing else to unwind).
