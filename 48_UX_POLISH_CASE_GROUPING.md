# 48 — UX polish: Case grouping clarity (pre-G2.2)

Date: 2026-06-11 · Status: BUILT, all 5 pages rebuilt + asserts pass, awaiting deploy.
Context: P02056 Lazada "issue" confirmed UI/UX, not engine (EC-AOCC-001219/001223 → Case EC-AL-000708 correct). This drop makes Case grouping legible.

## Changes

**Frontend (`frontend/build_alert_pages.py`, /alerts page only):**

1. Cột occurrence_count đổi label **"Số đơn vi phạm"**; badge phóng to + nền hồng (`.al-occ-n.multi`) khi case gộp >1 đơn.
2. Cột "Phát hiện" → **"Lần gần nhất"**, giá trị = `last_seen_at` (fallback `detected_at`). Drawer hiển thị cả "Phát hiện đầu" (`first_seen_at`) và "Lần gần nhất".
3. Drawer: pill hồng "**N đơn vi phạm**" ngay cạnh title khi N>1; khung Occurrences viền hồng (`.al-occ-wrap.hl`) khi nhiều đơn — bảng evidence không thể bị bỏ sót.
4. `missing_policy` / `missing_brand_mapping`: Giá check / Min / Baseline / Gap hiển thị **"-"** thay vì 0 (cả list lẫn drawer; helpers `pmoney`/`pgap`, map `NOPRICE`).
5. SKU search **khớp chính xác mặc định**: gõ `P02056` không còn lẫn `P02056X2`; muốn mở rộng dùng `*` (vd `P020*`). Placeholder + tooltip giải thích.
6. "View by Occurrence" toggle: KHÔNG làm (đúng yêu cầu — để sau).

**Backend (`api_alerts.py` — 1 thay đổi nhỏ, CẦN THIẾT):**

`_scoped_filters` trước giờ **bỏ qua hoàn toàn** key `seller_sku` (không nằm trong tuple xử lý) — ô filter SKU là no-op từ đầu, đây chính là gốc của confusion "P02056 lẫn P02056X2". Fix: exact `=` mặc định, `*`→`like`. `last_seen_at`/`first_seen_at` đã có sẵn trong LIST_FIELDS → không cần thay đổi nào khác. Không đụng engine/scheduler/Omisell/stock/PM.

## Verify đã chạy

Builder: 5 pages build OK, toàn bộ asserts pass (gồm asserts mới: `al-occ-n.multi`, `occBadge`, `NOPRICE`, `pmoney(`, `pgap(`, `last_seen_at`, `first_seen_at`, `al-case-pill`, placeholder cũ bị cấm). 5 HTML ASCII-clean, copy về `frontend/` parity đúng byte. `api_alerts.py` py_compile OK, ASCII clean.

## Deploy (owner)

```powershell
# backend (1 file, code-only, no migrate) - branch riêng hoặc gộp fix/scheduler-overlap PR
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/api_alerts.py
# frontend (sau khi backend live, hoặc cùng lúc - filter cũ vốn no-op nên không gãy)
powershell -File C:\dev\ALERT_CENTER\deploy\deploy_alert_pages.ps1 -Only alert-center
```

Lưu ý thứ tự: trang mới gửi `seller_sku` y như cũ — backend cũ ignore, backend mới filter. Deploy lệch pha không gây lỗi, chỉ là filter chưa hoạt động cho tới khi backend live.

## Test sau deploy (Ctrl+Shift+R /alerts)

1. Cột "Số đơn vi phạm": case P02056 (EC-AL-000708) badge hồng với số ≥2.
2. Cột "Lần gần nhất" đổi theo đơn mới nhất (không phải ngày tạo case).
3. Mở drawer EC-AL-000708: pill "N đơn vi phạm" cạnh title, bảng evidence viền hồng, đủ 2 đơn ODVN26061079FEA963 + ODVN260610A8C002C0.
4. Filter SKU `P02056` → chỉ case P02056; `P02056X2` không xuất hiện. `P020*` → cả hai.
5. Case missing_policy bất kỳ: các cột giá hiển thị "-" không phải 0.
