# 59 — Step 2 audit + plan: Frappe ToDo lifecycle cho Alert Case

Date: 2026-06-13 · Status: AUDIT ONLY — no code until plan approved. Không deploy/migrate.

## A. Audit — trả lời 4 câu hỏi

### 1. Frappe ToDo (v15, bench-managed — không vendored trong sandbox)

App pin `frappe~=15.0.0`. PM module đã dùng assignment API thật (`pm/api/tasks.py:15`): `from frappe.desk.form.assign_to import add as _assign_add` → `_assign_add({"doctype":"Task","name":...,"assign_to":[user]})`. Đây là bằng chứng API có sẵn trong version này.

ToDo v15 fields liên quan:
- `allocated_to` (Link User) — người được giao (v15 đổi từ `owner`-as-assignee sang `allocated_to`).
- `assigned_by` (Link User).
- `reference_type` (Link DocType) + `reference_name` (Dynamic Link).
- `status` — `Open` / `Closed` / `Cancelled`.
- `description`, `priority`, `date`.
- (`_assign` là field trên DOC ĐÍCH — EC Alert — không phải trên ToDo.)

**Cách tạo/đóng đúng chuẩn:** dùng assignment API (giống PM), KHÔNG tạo ToDo doc thô:
- Tạo: `frappe.desk.form.assign_to.add({"doctype":"EC Alert","name":case,"assign_to":[owner],"description":...}, ignore_permissions=True)` → tạo ToDo (`allocated_to=owner`, `reference_type="EC Alert"`, `reference_name=case`, `status="Open"`) + set `_assign` trên case (Desk "Assigned to me" hiển thị).
- Đóng: `frappe.desk.form.assign_to.remove("EC Alert", case, owner)` (đóng 1 assignment) hoặc `close_all_assignments("EC Alert", case)` (đóng tất cả) — set ToDo `status` Cancelled/Closed + cập nhật `_assign`. **Đóng = qua API, không xoá** (giữ evidence/audit). Signature chính xác confirm tại code-time trên bench; fallback an toàn = query ToDo theo (reference_type, reference_name, status Open) rồi set status.

### 2. Resolve KAM owner — ĐÃ CÓ helper duy nhất, reuse

`services/brand_resolver.resolve_owner(shop_name, brand)` đã hiện thực **đúng** priority yêu cầu: `shop.kam_owner → brand.kam_owner → brand.manager_email → brand.leader_email → None`. **Không duplicate** — Step 2 reuse trực tiếp.

Quan trọng: EC Alert đã lưu sẵn `owner_user` (set lúc tạo case qua `resolve_owner` trong `_find_or_create_case` + `_create_alert`). → ToDo lấy `case.owner_user`, **không cần re-resolve** (single source). Nếu `owner_user` rỗng (vd brand-less missing_brand_mapping) → không tạo ToDo + ghi diagnostic.

### 3. Chokepoint tạo Alert Case — KHÔNG có 1 hàm chung duy nhất, NHƯNG controller là chokepoint thật

Hai path tạo EC Alert: `_find_or_create_case` (Case/Occurrence price-violation) và `_create_alert` (legacy single-tier: missing_policy/missing_brand_mapping/ingestion_api_failed...). Cả hai `frappe.get_doc(...).insert()`. **Không có 1 service-function chung.** + `api_repair` tạo case split + Desk có thể tạo.

→ **Chokepoint đúng = EC Alert controller** (`after_insert` + `on_update`). Mọi case mới (engine, legacy, repair-split, manual) đều qua controller. Occurrence là doctype KHÁC (`EC Alert Occurrence`) nên controller EC Alert **không** fire cho occurrence → tự thoả "không tạo ToDo theo occurrence". `_bump_case` gọi `case.save()` mỗi occurrence → `on_update` chạy nhưng ensure idempotent → no-op. Đây là nơi gọi `case_todo.sync_todo(case)`.

### 4. Field `todo_name` trên EC Alert — KHÔNG cần (zero-migration)

ToDo là source of truth; lookup nhanh = `frappe.get_all("ToDo", {"reference_type":"EC Alert","reference_name":case,"status":"Open"})` (rẻ, có sẵn index trên reference). **Không thêm `todo_name` ở Step 2 → không migration.** Nếu sau này cần cột audit/report theo ToDo, thêm field (migration nhẹ) ở phase sau. Quyết định: **Step 2 = NO migration.** (Khác với D3 "todo_name acceptable" — chọn không thêm để giữ Step 2 không-migration; nêu rõ để anh duyệt.)

## B. Binding lifecycle → mapping kỹ thuật

| Sự kiện | Controller hook | Hành động |
|---|---|---|
| Case mới active (Open) | `after_insert` | `sync_todo`: active + có owner → tạo 1 ToDo cho owner |
| Open → In Review | `on_update` | `sync_todo`: vẫn active, owner không đổi → **idempotent no-op** (giữ ToDo) |
| Occurrence mới (case.save trong _bump_case) | `on_update` | `sync_todo`: no-op (đã có ToDo mở) |
| Closed / Ignored / Cancelled | `on_update` | `sync_todo`: terminal → đóng mọi ToDo mở của case |
| Vi phạm mới sau terminal | `after_insert` (case MỚI) | case mới = ToDo mới; ToDo cũ của case terminal đã đóng, **không reopen** |
| Owner đổi khi đang active | `on_update` | **reassign**: ToDo mở allocated_to ≠ owner_user → đóng cũ + tạo mới cho owner mới (xem quyết định D-S2-1) |

`sync_todo(case)` idempotent:
- `cl.is_terminal(status)` → `close_open_todos(case)`.
- `cl.is_active(status)` + `owner_user` → `ensure_one_open_todo(case, owner_user)` (có sẵn ToDo mở đúng owner → no-op; sai owner → reassign; chưa có → tạo).
- active + owner rỗng → no ToDo + `frappe.logger("alerts").warning({"todo_skipped_no_owner": case})` (test 9).

## C. Gap analysis

| Hạng mục | Trạng thái |
|---|---|
| KAM owner helper | ✅ ĐÃ CÓ (`resolve_owner`), reuse |
| owner_user lưu trên case | ✅ ĐÃ CÓ |
| Lifecycle status/terminal helper | ✅ ĐÃ CÓ (`case_lifecycle`, Step 1) |
| Chokepoint controller | ✅ EC Alert controller (Step 1 đã có `validate`; thêm `after_insert`/`on_update`) |
| ToDo create/close service | ❌ THIẾU → `services/case_todo.py` (mới) |
| ToDo lookup field | ➖ không cần (query trực tiếp) |
| Migration | ➖ KHÔNG cần |
| Tests | ❌ THIẾU → `tests/test_case_todo.py` |

## D. File-level plan (NO migration)

1. **`services/case_todo.py`** (MỚI): `sync_todo(case)`, `ensure_one_open_todo(case, owner)`, `close_open_todos(case)`, `_open_todos(case)`. Dùng `frappe.desk.form.assign_to` (như PM) + fallback query. Reuse `case_lifecycle` + `brand_resolver`. FAIL-OPEN: bọc try/except + log để ToDo hiccup không bao giờ vỡ ingest/save (giống sku_catalog fail-open).
2. **`doctype/ec_alert/ec_alert.py`**: thêm `after_insert(self)` → `case_todo.sync_todo(self)`; `on_update(self)` → `case_todo.sync_todo(self)`. Reuse owner_user trên doc.
3. **`tests/test_case_todo.py`** (MỚI): 10 test bắt buộc. Pure/stub cho logic quyết định (sync_todo phân nhánh) + bench-gated cho assign_to thật. Stub `frappe.desk.form.assign_to` + ToDo query để test idempotency/branching không cần DB.
4. (KHÔNG đụng) order pull / scheduler / catalogue / PM / Omisell / stock.

Deploy sau approval: code-only branch (no migrate). Step 2 không có migration nên deploy nhẹ hơn Step 1.

## E. Quyết định cần APPROVAL

- **D-S2-1 — Reassign khi owner đổi lúc active?** Khuyến nghị **CÓ reassign** (đóng ToDo cũ, mở cho owner mới) — ToDo theo đúng người chịu trách nhiệm. Phương án khác: giữ ToDo gốc tới khi terminal (đơn giản hơn, nhưng ToDo sai người). → cần anh chốt.
- **D-S2-2 — Phạm vi ToDo:** tạo ToDo cho MỌI EC Alert active có owner (gồm cả missing_policy), hay CHỈ price-violation Case (below_min/above_high/severe/possible_zero)? Khuyến nghị **mọi case active có owner** (đồng nhất, missing_policy cũng là việc KAM; brand-less tự rơi vào nhánh no-owner). → cần anh chốt.
- **D-S2-3 — Đóng ToDo = status `Closed` hay `Cancelled`?** Frappe `remove`/`close_all_assignments` thường set `Cancelled`. Khuyến nghị theo chuẩn Frappe (Cancelled = un-assigned), không tự ý ép Closed. → xác nhận.

Sau khi chốt D-S2-1/2/3, em khoá plan và code Step 2.
