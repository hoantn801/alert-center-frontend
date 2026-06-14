# Phase F — UAT Notes & Findings

Date: 2026-06-08 · Companion to `29_PHASE_F_UAT_SCRIPT.md`. Records behavior confirmed during UAT so future sessions/users don't re-investigate.

---

## Finding 1 — EC Alert records are immutable snapshots (EXPECTED)

**Question:** I created an Active EC Price Policy (FES-VN / All / P02056 / min 250,000 / ref 270,000 / RSP 320,000) but the existing alert row for P02056 still shows `rule=missing_policy`, `min=0`, `baseline=0`. Bug?

**Answer: No — this is correct, expected behavior. EC Alert rows are point-in-time snapshots.**

Code evidence (`alerts/services/alert_engine.py::_create_alert`): the engine does **dedupe-then-insert**. If a `dedupe_key` already exists (any status), it returns the existing row untouched and creates nothing. There is **no update path** that rewrites an existing alert's `rule_code`, `min_price`, or `baseline_price` when a policy is later added/changed. Every alert captures the rule verdict, min, and baseline **as they were at detection time**.

Why by design:
- **Auditability** (north-star #4): an alert is the record of "what we detected and what the policy was at that moment." Retro-rewriting it would destroy the audit trail.
- **Dedupe integrity** (decision C1): `missing_policy` uses a daily SKU-level key (`omisell|{brand}|{platform}|{shop}|{sku}|missing_policy|{YYYYMMDD}`). The existing alert keeps that key; it is not reopened or mutated by later activity.

**Consequence for the policy you just created:** it takes effect on the **next evaluation** of a matching order line — i.e. the next scheduled/manual pull that re-checks an order with SKU P02056. It does **not** retroactively fix the old `missing_policy` alert. The old row stays as a historical snapshot; a fresh, correct alert (e.g. `below_min`) appears when the order is re-evaluated.

---

## Finding 2 — `Platform = All` ALREADY matches Shopee/Lazada/TikTok (NO hotfix needed)

**Question:** Does `Platform = All` in EC Price Policy match marketplace-specific orders (Shopee/Lazada/TikTok), with priority Shop+Platform+SKU > Platform+SKU > All+SKU?

**Answer: Yes — the wildcard and the exact priority you described are already implemented.** No backend change required.

Code evidence (`alerts/services/policy_lookup.py::find_policy`) — lookup walks priority levels and returns the first Active, in-window match:

| Level | Match | Your requirement |
|---|---|---|
| 1 | brand + platform + **shop** + item | Shop-specific (highest) |
| 2 | brand + platform + **shop** + seller_sku | Shop-specific |
| 3 | brand + platform + item (policy has no shop) | Platform-specific |
| 4 | brand + platform + seller_sku (policy has no shop) | Platform-specific |
| 5 | brand + **platform="All"** + item / seller_sku | All-platform fallback (lowest before brand fallback) |
| 6 | brand-level fallback, only if `is_brand_fallback=1` | explicit opt-in |

Trace for your data — order `brand=FES-VN, platform=Shopee, shop=FES-VN-SHOPEE, seller_sku=P02056` vs policy `brand=FES-VN, platform=All, shop=(blank), seller_sku=P02056`:
- L2 (shop+sku): policy has platform=All & no shop → **no match**
- L4 (platform=Shopee+sku, no shop): policy platform=All ≠ Shopee → **no match**
- **L5 (platform="All"+sku, no shop): MATCH** ✓

So a `Platform=All` policy applies to Shopee/Lazada/TikTok when no more specific policy exists; a Shopee-specific policy (L3/L4) overrides it; a shop-specific policy (L1/L2) overrides the platform one. Priority is exactly: **Shop+Platform+SKU > Platform+SKU > All+SKU**.

Note on stored value: `save_policy` writes the field verbatim, so selecting "All" in the +Policy form stores `platform="All"`, which is what L5 queries. (If a policy were saved with platform blank/empty instead of the literal "All", L5 would not match — so keep using the "All" option, not an empty platform.)

**Reason the old alert still says `missing_policy`:** purely Finding 1 (snapshot), not a matching gap. The lookup would have matched at L5 — but only on a *new* evaluation, which hasn't run for that already-ingested order.

---

## How to test the policy actually takes effect

Pick one:

1. **Re-evaluate the existing order (cleanest):** as System Manager, call the read-only single-order re-pull:
   `POST /api/method/ecentric_workspace.alerts.api_omisell.pull_one_order` with `{brand:"FES-VN", order_number:"<the P02056 order>"}`.
   This re-ingests (idempotent) and re-runs the engine on that order. Expected: the old `missing_policy` row is untouched; if unit price < 250,000 a **new `below_min`** alert appears with `min=250000` and a real `baseline`. If price ≥ 250,000 and < high threshold → `check_result=OK`, no new alert.
2. **Wait for a new order line** for P02056 to arrive via the FES-VN scheduled pull — same result on first matching line.

Either way, confirm:
- old `missing_policy` alert = unchanged (snapshot),
- new alert (if price breaches) carries the policy's `min_price`/`baseline`,
- only ONE winning rule per line (decision C2).

---

## Finding 3 (UI improvement — DONE, approved & built 2026-06-08)

Added a subtle **neutral info banner** (not warning/error style) **above the Alerts list** on `/alerts`:

> Alerts là snapshot tại thời điểm phát hiện. Tạo/sửa policy chỉ áp dụng cho lần đánh giá / pull tiếp theo, không cập nhật lại alert cũ.

Implementation (frontend only — backend untouched, scheduler untouched, no Omisell/stock write, DS1 locked):
- New CSS class `.al-note` (border `--gray-200`, bg `--gray-50`, text `--gray-600`, `ⓘ` icon `--gray-400`) — neutral, matches existing Alert Center style.
- Banner `<div class="al-note" id="al-snapshot-note">` inserted in `build_alert_pages.py` immediately before `<div class="panel" id="al-alert-list">`. Vietnamese stored as HTML entities (ASCII source rule).
- Build asserts extended: page1 must contain `id="al-snapshot-note"` and `"snapshot t"` (unescaped).
- Rebuilt all 4 pages (ASCII-clean; note appears **only** on alert_center, line 524, directly above the list at 525). Other 3 pages get only the harmless shared `.al-note` CSS, no banner.

**Deploy (owner):** `deploy_alert_pages.ps1 -Only alert-center` → Ctrl+Shift+R on `/alerts`, confirm the grey info line sits above the Alerts table.

---

## Summary for the report

- **Is this expected snapshot behavior?** Yes — EC Alert rows are immutable; the engine dedupe-then-inserts and never rewrites an existing alert when a policy is added/changed.
- **Does `Platform=All` currently match Shopee?** Yes — already implemented (policy_lookup L5), with the exact priority Shop+Platform+SKU > Platform+SKU > All+SKU.
- **Is a backend hotfix needed?** No. The reported symptom is the snapshot, not a matching gap.
- **How to test after "fix":** no fix to deploy — re-run `pull_one_order` for that order (or wait for a new P02056 order) and confirm a fresh `below_min` alert appears while the old `missing_policy` row stays as a snapshot.
- **UI note:** optional snapshot disclaimer on the alert list — proposed, pending approval.
