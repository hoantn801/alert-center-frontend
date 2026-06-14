# Alert Center — Policy Conflict Guard (Local Report)

Date: 2026-06-08 · Status: **IMPLEMENTED — backend `C:\dev\ecentric_workspace`, frontend built `C:\dev\ALERT_CENTER`. Ready to deploy.** No Omisell/stock write; scheduler/hooks/tasks/PM untouched; G1.1 + G2.1 intact.

## 1. Files changed
- `doctype/ec_price_policy/ec_price_policy.py` — `validate()` now calls `_guard_exact_scope_conflict()` (+ pure helpers `_scope_key`, `_windows_overlap`).
- `api_policies.py` — new read endpoint `policy_conflicts(brand)` for the UI badges.
- `frontend/build_alert_pages.py` — `/alerts/policies`: fallback helper note in the scope section + conflict badges in the policy list. Rebuilt 5 HTML.

No schema/migrate change. No new DocType.

## 2. Backend guard (block on save/activate)
`EC Price Policy.validate()` fires on **both** Desk and the `api_policies.save_policy`/`set_policy_status` paths (both call `doc.save()`). When the policy is **Active**, it scans other Active policies of the **exact same scope** and **blocks** if validity overlaps:
- scope key = `(platform-normalized, shop-normalized, target)` where `target` = seller_sku → else item → else `__fallback__` (when `is_brand_fallback`).
- `platform` blank is normalized to `All`; `shop` blank normalized to `""`.
- validity overlap = inclusive window overlap (open ends allowed).
- excludes self; throws a clear `Duplicate Active Policy` error naming the conflicting policy.

So you can never **save/activate** a 2nd Active policy for e.g. `FES-VN / Shopee / FES-VN-SHOPEE / P02056` while another with overlapping dates is Active.

## 3. Platform=All behavior (preserved hierarchy)
`Platform=All` is a **different scope** from a specific platform, so it is **never blocked** by a specific-platform policy — the priority **Shop+Platform+SKU > Platform+SKU > All+SKU** holds. The guard only blocks *exact* same-scope duplicates (e.g. two `All+SKU`, or two `Shopee+shop+SKU`). The UI marks `All`/no-shop policies that are superseded by a more specific Active policy as **fallback** (see §4).

## 4. UI
- **Scope helper note** (near Platform/Shop): "Platform=All thường nên để Shop trống. Policy theo platform/shop cụ thể sẽ OVERRIDE policy All. Hệ thống chặn 2 Active policy trùng y hệt scope."
- **List badges** via `policy_conflicts(brand)`: a red **TRÙNG** badge on rows that have another exact-scope Active policy with overlapping validity (existing duplicates that pre-date the guard), and a yellow **fallback** badge on Active policies overridden by a more specific one. Tooltips explain each.

## 5. Data cleanup
No auto-delete. Existing duplicates remain and are **flagged** (TRÙNG badge) so KAM can manually set the wrong one to Inactive/Paused. The guard only prevents *new* exact-scope duplicates.

## 6. No-write confirmation
No Omisell call; no stock/buffer/inventory write; DS1 locked; scheduler/hooks/tasks/PM untouched. The guard is read-then-throw (it queries existing policies and either allows the save or raises — it writes nothing extra). G1.1 Case/Occurrence and G2.1 SKU Catalog code paths unchanged.

## 7. Build / test
- Guard pure logic verified standalone **7/7** (scope-key equality incl. All≠Shopee, shop distinctness; window overlap incl. disjoint/touching/open-end). `ec_price_policy.py` + `api_policies.py` `py_compile` clean. Full `doc.validate()` block is bench-pending.
- Frontend: all 5 pages build, **every assert passes** incl. new conflict markers (`al-conf-badge`, `api_policies.policy_conflicts`, `loadConflicts`); ASCII-clean, no unresolved placeholders.

## 8. Deploy / rollback
- **Backend** (owner, `C:\dev\ecentric_workspace`): branch, stage `doctype/ec_price_policy/ec_price_policy.py` + `api_policies.py`, PR → merge → **FC deploy (no migrate — code only)**.
- **Frontend**: `cd C:\dev\ALERT_CENTER\deploy; .\deploy_alert_pages.ps1`.
- **Rollback**: revert PR → FC deploy (guard removed; no data change). Frontend redeploy prior HTML. No data unwind.

## 9. Verify after deploy
1. Try to add/activate a 2nd Active policy with the same brand/platform/shop/SKU + overlapping dates → blocked with the duplicate error.
2. Add an `All`+SKU and a `Shopee`+SKU policy for the same SKU → both allowed; `/alerts/policies` shows the All one with a **fallback** badge.
3. An existing exact-duplicate pair shows red **TRÙNG** on both rows; inactivate one → badge clears on reload.
