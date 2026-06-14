# Phase F — UAT Script (FES-VN pilot)

Date: 2026-06-10 · Status: Drop 1 + Drop 2 + nav hotfix deployed & verified. This is the hands-on UAT checklist. Constraints throughout: no 2nd brand, FES-VN scheduler monitored, rules stay Draft (no custom activation without approval), DS1 locked, no real stock write.

Precondition: log in as a user who is `kam_owner`/`manager`/`leader` on FES-VN (or System Manager). Confirm `Brand Approver` FES-VN has kam_owner filled.

## 1. `/alerts` — Dashboard & Alerts
- Open `/alerts` (Ctrl+Shift+R). Sidebar = Alert Center module menu, **Dashboard** active, breadcrumb `Workspace / Alert Center / Dashboard`.
- 6 KPI cards show numbers (Open / Critical / Warning / Missing policy / Lock pending review / Resolved). Default date range = last 14 days; widen the range → numbers/panels refresh.
- Panels render: by brand / by platform / by rule bars · Top violating SKUs · SLA aging buckets · 14-day trend.
- Scroll to the **Alerts** list (15 cols). Click a row → drawer opens with detail + actions. Mark one alert **In Review** (no note needed) → toast + list refresh. **Resolve** another with a note (note required) → status flips. **Ignore** flow w/ note.
- Click sidebar **Alerts** → page jumps/scrolls to the list section (active toggles to Alerts). Click **Dashboard** → back to top (active = Dashboard).
- ✅ Pass = page is Alert-Center content, list usable, drawer/status actions work, anchor jump works.

## 2. `/alerts/policies` — create one small FES-VN policy
- Open Policies (breadcrumb `… / Policies`). Click **+ Policy**.
- Fill: brand FES-VN, platform (e.g. Shopee or All), seller_sku = a real FES-VN SKU you know, product name, min_price (a sensible floor), optionally reference/target price. Save → created as **Draft**.
- Set status **→ Active**. Verify it appears Active in the list. (This Active policy will be consulted by the engine on the next scheduled pull / next matching order.)
- Edit it once (e.g. tweak min_price) → save → still works.
- ✅ Pass = single create/edit + status transitions work, brand-scoped.

## 3. CSV template → download → preview → import (small sample)
- Click **Tải CSV Template** → a CSV with the header row downloads.
- Fill 3 rows: (a) one valid FES-VN row; (b) one row with a deliberately bad number e.g. `min_price = abc`; (c) one valid row with `min_price = 5.000.000` (vi-VN dotted) to confirm it parses as 5,000,000.
- **Upload CSV** → **Kiểm tra (preview)**: table shows per-row OK/✕ with reasons; row (b) flagged; the error textarea fills → **Copy lỗi** works.
- **Import dòng hợp lệ** → report: created/updated counts + the bad row listed as failed. Verify row (c) min_price = 5000000 in the list (not 5).
- ✅ Pass = preview-before-commit, vi-VN number safe, only valid rows imported, errors copyable.

## 4. `/alerts/rules` — Draft only (do NOT activate custom rules yet)
- Open Rules (breadcrumb `… / Rules`). Banner explains rules affect evaluation + dry-run recommendation only; DS1 locked.
- Header shows priority **SKU > Shop > Platform > Brand**.
- Click **+ Rule**: pick rule_code, FES-VN, set scope (e.g. seller_sku) → live "Tầng scope" preview updates. Note the recommend-lock checkbox is disabled for below_min/above_high.
- Click **Kiểm tra trùng/override** → overlap result (likely "Không trùng rule Active nào" since none active).
- Save → stays **Draft**. **Do NOT click → Active** (per your instruction). As KAM, the Activate button should 403/hint anyway.
- ✅ Pass = create Draft + scope preview + overlap check work; activation correctly gated; nothing activated.

## 5. `/alerts/locks` — dry-run wording + pause manager
- Open Locks (breadcrumb `… / Locks`). Top banner = **"⚠️ DRY-RUN ONLY …"** (no stock/buffer sent to Omisell, DS1 locked).
- Review queue table: if a Dry Run action exists, open drawer → DS1 audit fields show **—(DS1)** placeholders. Open **Approve** modal → it states: chỉ duyệt DRY-RUN review · không gửi stock/buffer sang Omisell · real stock write khoá bởi DS1. (You may Approve to confirm wording; it keeps status Dry Run.) **Reject** requires a note.
- Pause manager: **+ Pause** for FES-VN (a SKU or All), short window → appears in active pauses; **Huỷ pause** cancels it.
- ✅ Pass = DRY-RUN wording correct everywhere, no "real lock happened" language, DS1 placeholders honest, pause create/cancel work.

## 6. FES-VN scheduler monitoring (during UAT)
- Periodically `pull_status FES-VN`: `last_sync_at` advancing ≈ now−15-30 min, `state=done`, breaker=0, running null, failed=0. (Latest confirmed: 2026-06-08 15:32:02.)
- `/alerts` cards/list keep working while pulls run. No 502, no worker timeout.

## 7. After UAT
Report per-section pass/fail + any UI nit. On full pass → Phase F production-complete sign-off, then the KAM pilot week (checklist in `26_PHASE_F_FINAL_REPORT.md` §11). Still deferred: 2nd brand, D.2 reconciliation, DS1 stock-read/real-execution.

Out of scope during UAT: activating custom rules (Draft only), adding brands, any real Omisell write.
