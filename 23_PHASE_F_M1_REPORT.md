# Phase F — M1 Local Implementation Report (Ops Backend)

Date: 2026-06-10 · Status: **M1 IMPLEMENTED LOCALLY — commit `1a13fe9` on `alerts-phase-f` (off `2f2f593` = origin/main with list-hardening PR #12). NOT pushed/deployed. M2 frontend NOT started (per F-4: this report is the M1 gate).**

## 1. Files changed (15 files, +1188/−8, all in `alerts/`)

Add: `doctype/ec_alert_rule/{__init__,json,py}` · `services/rule_overlay.py` (116 ln) · `services/policy_csv.py` · `api_policies.py` · `api_rules.py` · `api_dashboard.py` · `tests/test_phase_f.py` (151 ln). Change: 2 DocType JSONs (policy/action extends), `services/alert_engine.py` (+12/−3 overlay wiring), `services/action_queue.py` (+1: Pending Review stamp), `permissions.py` (+18: 3 capability fns), `api_actions.py` (+64: list_actions + review_action). **hooks.py 0 diff (blob-verified) · 0 pm/ · client untouched (GET-only frozen, blob-verified).**

## 2. Schema impact (additive only, FC migrate applies)

- `EC Price Policy`: +`product_name`, +`target_price` (display-only — engine does NOT read it), +`owner_user`, +`import_batch` (RO); `status` options now `Draft/Active/Paused/Expired/Inactive` — **inert by construction** (engine's `find_policy` filters `status=Active`; existing rows unaffected).
- NEW `EC Alert Rule` (20 fields, track_changes, SM-only DocPerm like all siblings; controller blocks `recommend_stock_lock` on non-lockable rule_codes and bad date windows).
- `EC Alert Action`: +review section (`review_status` Select `Pending Review/Approved/Rejected`, `reviewed_by/at` RO, `review_note`); new lock actions are stamped `Pending Review` at creation.
- No DocPerm/role changes anywhere.

## 3. Endpoint contracts (all: scope check first line; writes POST-only; brand filtered server-side)

**api_policies**: `list_policies(filters,start,page_len)` · `save_policy(policy,name?)` (create=Draft default, owner defaults to creator; brand-change also scope-checked) · `set_policy_status(name,status)` · `csv_template()` (→ Download-button contract, req #1) · `preview_policy_csv(content)` — **writes nothing**, per-row verdicts (shape + DB + scope) · `import_policy_csv(content)` — re-validates, commits valid rows only, upsert key brand+platform+shop+sku+item, `import_batch` stamped, returns {batch, created, updated, failed[]}.
**api_rules**: `list_rules` · `save_rule` (KAM tier; **editing an Active rule demotes it to Draft for re-approval** unless editor can activate) · `set_rule_status` (Activate/Pause = approval step, stamps approved_by/at) · `check_rule_overlap(rule)` (req #2: returns new rule's tier + which Active rules it overrides / is overridden by, priority `SKU > Shop > Platform > Brand`).
**api_dashboard** (default window **last 14 days**, req #4): `kpis` · `by_dimension(brand|platform|shop|rule_code)` · `top_skus(limit≤25)` · `aging` (unresolved buckets <4h/4–24h/1–3d/>3d, scans beyond 14d) · `trend(days≤31)` (daily new/resolved/ignored).
**api_actions**: +`list_actions(filters)` (locks page source incl. review + DS1 audit fields) · +`review_action(name, Approve|Reject, note)` — Approve keeps status `Dry Run` + stamps audit; Reject **requires note** → status `Cancelled`; only dry-run-era statuses reviewable; docstring + return wording never implies a real lock happened (req #3 backend side).

## 4. Permission matrix (additions — service-layer, no new roles)

| Capability | kam | manager | leader | System Manager |
|---|---|---|---|---|
| manage policy (create/edit/status, CSV import per-row) | ✅ | ✅ | ❌ (read) | ✅ |
| save rule (Draft) | ✅ | ✅ | ❌ | ✅ |
| activate/pause rule (approval, F-2) | ❌ | ✅ | ✅ | ✅ |
| review dry-run lock (approve/reject) | ✅ | ✅ | ✅ | ✅ |
| real execution / credentials | ❌ | ❌ | ❌ | SM only (unchanged, DS1) |

Mock-tested for all 5 role tiers (incl. None → all False).

## 5. Rule overlay behavior

`find_rules` → best-match per rule_code (score SKU 8 > shop 4 > platform 2 > brand 1; Active + enabled + in-window; **fail-safe `{}` on any lookup error**). `overlay_params` may replace `severe_drop_percent`/`high_alert_percent`; `overlay_hit` may override severity, with the approved below_min escalation (gap ≥ X% ⇒ Critical, else override-or-Warning); `lock_narrowing` can only **disable** the lock recommendation for the two severe rules — below_min/above_high stay never-lockable in code, and a lock still requires `policy.enable_stock_safety_lock` downstream. **Req #5 golden guarantee: with zero Active rules the overlay is a mathematical identity — tested across all 6 engine scenarios (params dict equal, hit dict equal, lock decisions equal).**

## 6. Regression test results

**Full sandbox suite 51/51 PASS** = every prior class (NoWrite, Normalizer, Chunker, NoSqlFunctionStrings, PullSafety, DisabledFlagParser, Observability, SchedulerGates, ServerErrorRetry) + 14 new Phase F tests (golden identity, overlay behavior ×4, CSV ×3 incl. the `5.000.000`→5,000,000 footgun and the 500-row cap, capability tiers, source guards ×2). Bonus catch: **our own lint test flagged `api_dashboard` using `fields=["count(*) …"]`** (the exact class of the PR-#7 production bug) — rewritten to parameterized SQL with column whitelists before commit. Bench-pending: endpoint scope/state-machine integration tests run on a site (same caveat as every phase).

## 7. No-write confirmation

Client diff vs origin/main = 0 lines; `ALLOWED_METHODS={GET}` in blob; `review_action` source-guard test proves no client/requests/buffer/adjust references; no archive/delete; DS1 untouched; **FES-VN scheduler logic untouched** (api_omisell/tasks/hooks all 0 diff — live pulls continue unaffected by this branch).

## 8. Deploy/rollback notes (for the eventual Phase F deploy — NOT now; M2–M4 continue on this branch)

Deploy (after M4, per plan): single PR, FC migrate applies §2 (1 new DocType + 9 added fields + status options). Migrate-safety: status-option extension is additive (existing values preserved); new fields nullable. Post-deploy backend probes: policy-inertness (Draft policy invisible to engine), 403 matrix on the 4 new modules, golden regression re-run. Rollback: revert PR — overlay disappears (engine returns to literal current code), schema stays harmlessly (Draft/Paused values would render as plain strings on old code — acceptable; nothing writes them until F UI ships). Instant config-level off-switch is inherent: deactivate all EC Alert Rules ⇒ overlay = identity.

---
**Gate:** M1 review. On your approval, M2 starts (Dashboard v2 in-place upgrade of `/alerts` + `/alerts/policies` page incl. CSV upload + Download-Template button) — frontend-only, same branch.
