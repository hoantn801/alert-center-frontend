# Phase F — Final Integrated Report (M1–M4) · Alert Center Ops UI Full Build

Date: 2026-06-10 · Status: **ALL FOUR MILESTONES BUILT LOCALLY. NOT pushed/merged/deployed.** App branch `alerts-phase-f` @ `1a13fe9` (M1 only — M2–M4 are workspace-side pages). Awaiting your review → Drop 1 → Drop 2 → KAM pilot.

## 1. Files changed across M1–M4

**App repo (1 commit `1a13fe9`, 15 files +1188/−8):** new `EC Alert Rule` doctype · policy/action JSON extends · `services/{rule_overlay,policy_csv}.py` · `alert_engine`/`action_queue` wiring · `permissions.py` +3 capabilities · `api_policies/api_rules/api_dashboard.py` new, `api_actions.py` extended · `tests/test_phase_f.py`. **hooks.py 0 diff · pm/ 0 · omisell client/scheduler 0 diff.**
**Workspace:** `frontend/build_alert_pages.py` (multi-page builder, 4 pages + per-milestone acceptance asserts) · built pages `alert_center.html` 56.7KB / `alert_policies.html` 52.2KB / `alert_rules.html` 50.8KB / `alert_locks.html` 53.9KB · `deploy/deploy_alert_pages.ps1` + `rollback_alert_pages.ps1` (4 pages, `-Only` selector, per-page backups).

## 2. Schema impact (additive, FC migrate)

EC Price Policy: +product_name, +target_price (display-only), +owner_user, +import_batch; status += Draft/Paused/Expired (inert — engine filters Active). NEW EC Alert Rule (20 fields, SM-only DocPerm, track_changes). EC Alert Action: +review section (review_status/reviewed_by/at/note). No DocPerm/role changes; no index changes.

## 3. Routes/pages

`/alerts` = Dashboard v2 + alert list (in place, list kept) · `/alerts/policies` = Policy Master + CSV import · `/alerts/rules` = Rule config + overlap checker · `/alerts/locks` = Dry-run lock review + pause manager. All share: home shell verbatim, `al-subnav` tabs, `window.AL` helpers, no external libs, no sidebar change. Locks page: **"⚠️ DRY-RUN ONLY"** banner; table per your spec (alert ref, brand/platform/shop/SKU, proposed qty, lock_until, release strategy, review status, reviewed by/at, action status); **DS1 audit fields render "—(DS1)" when empty** (actual/available/buffer before, buffer after, locked qty); Approve modal states verbatim: *chỉ duyệt DRY-RUN review · KHÔNG có cập nhật stock/buffer nào gửi sang Omisell · real stock write khoá bởi DS1*; Reject requires note; pause manager lists active pauses + cancel + create (existing endpoints only).

## 4. Endpoint usage (complete map — all scoped server-side, writes POST-only)

`my_scope` (every page) · dashboard: `kpis/by_dimension/top_skus/aging/trend` (default 14d) · alerts: `list_alerts/set_status`, `list_for_alert`, `create_pause` · policies: `list/save/set_status/csv_template/preview_csv/import_csv` · rules: `list/save/set_rule_status/check_rule_overlap` · locks: `list_actions/review_action`, `list_pauses/create_pause/cancel_pause`. Zero `/api/resource` calls from pages; zero client-side authority decisions.

## 5. Permission model (server-authoritative; final matrix)

kam: handle alerts, manage policies, draft rules, review dry-run locks, create pauses — own brands only · manager: + activate/pause rules, cancel pauses · leader: handle/review/activate/cancel (no policy/pause-create) · System Manager: everything + credentials + (future) real execution. No new roles; DocPerm stays SM-only; UI shows hints, server throws 403.

## 6. No-write confirmation

Omisell client untouched since list-hardening (GET-only frozen, blob-verified at M1 commit); review_action source-guard test proves no client/stock references; no archive/delete; **DS1 locked — no stock/buffer/inventory write exists anywhere**; FES-VN scheduler logic untouched (0 diff on api_omisell/tasks/hooks). Tests: **51/51 full sandbox suite** (M1) + per-page build asserts M2/M3/M4 (just re-run, all green).

## 7. UAT script (post-Drop-2, with the KAM pilot — FES-VN)

1. KAM login → `/alerts`: sees own brand only; cards/sections populate; default range = 14 ngày; widen range works; resolve an alert with note; drawer shows actions.
2. `/alerts/policies`: create 1 policy (Draft) → set Active; download template → fill 3 rows (1 sai brand người khác, 1 sai số) → Upload → preview shows 1 OK + 2 lỗi (copy-errors works) → import → 1 created; verify next scheduled pull evaluates with the new Active policy (alert appears if violated).
3. `/alerts/rules`: create Draft rule (below_min escalation 20%) → overlap check → KAM thấy Activate bị 403/hint → Lead activates → next pull: severity per rule; deactivate-all check: pause rule → behavior returns to default.
4. `/alerts/locks`: find a Dry Run action (or trigger via mock ingestion on a test brand) → DS1 placeholders visible → Approve (modal text present) → review stamped, status remains Dry Run → Reject another with note → Cancelled; create + cancel a pause; verify a paused SKU yields Skipped action on next violation.
5. Cross-checks: non-scoped user → no-access screens ×4 pages; Phase C/E probe scripts still green; FES-VN `pull_status` unaffected throughout.

## 8. Deploy plan — Drop 1 (app PR + migrate)

Pre-push: `git diff --name-status origin/main..alerts-phase-f` = exactly 15 M1 files, 0 pm/, 0 hooks; full suite re-run. Push → PR #13 → Files-changed gate → merge → FC Deploy (migrate: 1 new DocType + 9 fields + status options). Post-Drop-1 probes: policy-inertness (create Draft policy via API → engine ignores it), 403 matrix on 4 new modules (non-SM + unscoped), golden regression (existing FES-VN flow produces identical alerts — compare a re-pulled window), `/alerts` v1 page still functional against new backend (it only uses endpoints that kept signatures).

## 9. Deploy plan — Drop 2 (web pages)

`deploy_alert_pages.ps1` (4 pages, backups taken; `-Only` for selective redeploy). Verify each route 200 + marker; hard-reload check; then UAT §7. Pages can ship one-by-one if preferred (`-Only alert-center` first).

## 10. Rollback plan

Drop 2: `rollback_alert_pages.ps1` (unpublish any/all — old alert-center backup restorable from `deploy/backups/`). Drop 1: revert PR → FC deploy (overlay/API gone; engine literal-identical default path; schema stays harmlessly — nothing writes Draft/Paused until UI exists). Config-level: deactivate all EC Alert Rules ⇒ overlay = identity. No Omisell-side state ever.

## 11. KAM pilot checklist (FES-VN, after UAT)

☐ kam_owner verified on FES-VN Brand Approver ☐ KAM browser-tests all 4 routes ☐ KAM enters real min-price list (UI or CSV) and sets Active ☐ Rules: agree starter set with Lead (suggest: none initially — defaults are sane; add escalation rules after a week of data) ☐ Watch 1 week: alerts match KAM expectations (Q-D5 sanity on real prices), false-positive rate, lock recommendations sensible ☐ Daily: locks queue reviewed (approve/reject discipline builds the audit trail the future real executor will require) ☐ Weekly: capacity_stats + pull_status check ☐ Exit criteria for "Phase F production-complete": 1 week pilot, no sev-1 issues, KAM sign-off — then discuss next gates (2nd brand, D.2 reconciliation, DS1 stock-read).
