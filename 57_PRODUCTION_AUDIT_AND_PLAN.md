# 57 — Alert Center production audit + gap analysis + file-level plan

Date: 2026-06-13 · Status: AUDIT ONLY — no code until decisions §D approved. Target build 12–16h sau approval.
Scope: hiện thực hoá binding business flow (Brand Setup / Price Setup / My Alerts) trên codebase thật. Audit dựa trên đọc trực tiếp `C:\dev\ecentric_workspace\ecentric_workspace\alerts`.

---

## A. Ground truth đã đọc (không suy đoán)

**DocTypes hiện có (12):** ec_alert, ec_alert_action, ec_alert_occurrence, ec_alert_rule, ec_automation_pause, ec_brand_alert_config, ec_brand_integration_settings, ec_marketplace_order_item, ec_marketplace_order_log, ec_marketplace_shop, ec_marketplace_sku_catalog, ec_price_policy.

**EC Alert.status hiện tại:** `Open / In Review / Resolved / Ignored`. **KHÔNG có `Closed`, KHÔNG có `Cancelled`.** Controller `ec_alert.py` stamp `resolved_by/at` khi status ∈ (Resolved, Ignored).

**EC Price Policy fields:** brand, platform, shop, item, seller_sku, product_name, is_brand_fallback, **min_price, reference_price, target_price, high_alert_percent, severe_drop_percent**, enable_stock_safety_lock, stock_lock_duration_minutes, effective_from/to, status (Draft/Active/Paused/Expired/Inactive), owner_user, import_batch. `seller_sku` KHÔNG unique.

**EC Marketplace SKU Catalog fields:** brand, platform, shop, omisell_shop_id, seller_sku, product_name, external_product_id, erpnext_item_code, rsp_price, is_active, status (Active/Stale/Retired), source_system, source_level (order_derived/omisell_product), first_seen_at, last_seen_at, raw_payload_hash, catalog_key, **note**. → **stock / sale_price / catalogue_price / product-status / image / is_variant/parent đang nằm trong `note` JSON** (quyết định no-migration doc 54).

**ToDo:** Alert Center **KHÔNG có ToDo nào**. Chỉ PM module dùng `frappe ToDo` (pm/api/tasks.py, recurrence.py). Đây là tham chiếu pattern, không reuse trực tiếp.

**Permissions (service-layer, permissions.py):** role suy từ Brand Approver (kam=3/manager=2/leader=1), `is_global_supervisor` = System Manager. `can_handle_alert` = kam/manager/leader/supervisor; `can_manage_policy` = kam/manager/supervisor; Brand Setup (BIS/API key/shop map) hiện **System Manager only**.

**Scheduler (hooks.py):** order pull `*/15` (quadruple-gated qua `ec_alerts_scheduled_pull_brands`), action queue `*/10`, pause expiry hourly. **Catalogue sync KHÔNG có trong scheduler** — chỉ chạy thủ công qua `api_catalogue_sync.confirm` (đúng yêu cầu "order pull ưu tiên hơn catalogue").

---

## B. Trả lời 11 câu hỏi audit

### 1. Phần nào đã có & reuse được

| Đã có | Reuse cho |
|---|---|
| `api_catalogue_sync` (preview/confirm, page-streaming, caps) + `services/catalogue_sync` (normalize/variant/price-guard) | Brand Setup §"đồng bộ sản phẩm" — gần như đủ backend |
| `services/sku_catalog` (catalog_key, upsert, backfill order-derived) + `api_sku_catalog.search_skus` (vừa fix ranking) | Price Setup grid: nguồn SKU + autofill metadata |
| `EC Price Policy` + `api_policies` (save/list/csv preview+import/conflicts) + `services/policy_csv` | Price Setup: min/benchmark/severe/high — **schema đủ**, thiếu grid UI + bulk-by-brand idempotent |
| `EC Alert` Case + `EC Alert Occurrence` + `alert_engine._find_or_create_case` (platform/shop-scoped) | My Alerts — case model đúng, chỉ thiếu status `Closed/Cancelled` + ToDo |
| `api_alerts.set_status/bulk_set_status` + permission gates | My Alerts KAM actions (In Review/Closed/Ignored) |
| `permissions.py` role model | Permission matrix — mở rộng, không viết lại |
| `EC Brand Integration Settings` + `api_brands` (readiness) + `EC Marketplace Shop` | Brand Setup: API key + shop map (đã có, thiếu UI gom 1 chỗ + KAM-assign field) |

### 2. Thiếu backend

- **Status lifecycle `Closed` + `Cancelled`**: chưa tồn tại. `Resolved` đang đóng vai "Closed". Cần thêm option + (nếu đổi tên) data migration + cập nhật `HANDLE_STATUSES`/`NOTE_REQUIRED`/controller/dashboard counts.
- **ToDo lifecycle hoàn toàn thiếu**: tạo/đóng/dedupe 1-ToDo-per-case. Không có code nào.
- **Terminal-guard phòng thủ**: hiện đúng *nhờ* lookup chỉ match Open/In Review (xem §4), nhưng không có assertion tường minh ở `_bump_case`/`_record_price_violation`.
- **Brand Setup orchestration endpoint**: gán KAM cho brand (hiện KAM ở Brand Approver, không có ô set trong luồng Alert Center), "1-nút setup" chưa có.
- **Price Setup bulk-by-brand idempotent save** (grid → upsert nhiều policy 1 lần, key brand+platform+shop+seller_sku): `save_policy` chỉ làm 1 record; CSV import có nhưng không phải grid bulk-apply/paste.
- **Catalogue sync per-brand "last_sync_time" + history**: hiện ephemeral (JSON trả về), không lưu.

### 3. Chỉ thiếu UI (backend đã đủ/gần đủ)

- **Brand Setup page**: gom BIS (API key) + shop map + readiness + nút "đồng bộ sản phẩm" (gọi catalogue preview/confirm) + chọn KAM. Backend ~90% có.
- **Price Setup grid**: inline-edit/bulk-apply/paste-Excel/CSV-XLSX import/validation-preview/bulk-save. Backend: policy save + csv preview có; cần thêm 1 bulk endpoint + grid UI.
- **My Alerts**: list theo KAM + 3 action. `api_alerts` + occurrences drawer đã có; cần trang gọn 3-flow, ẩn Cancelled.

### 4. Terminal case có nhận occurrence mới ở mọi path không?

**Hiện tại AN TOÀN nhưng ngầm định, chưa phủ Cancelled.** Chi tiết:
- `_record_price_violation`: nếu occ_key đã tồn tại → return `existing.case` **không bump** (re-pull cùng order-line, không thêm evidence). ✓
- `_find_or_create_case`: lookup `status in [Open, In Review]` → case terminal (Resolved/Ignored) KHÔNG match → tạo **case mới**. ✓ (đúng spec "vi phạm mới sau terminal → case mới").
- `_bump_case`: chỉ gọi từ path trên (case open hoặc vừa tạo) → không bump terminal. ✓
- **Lỗ hổng cần vá khi thêm Cancelled**: phải đưa `Cancelled`/`Closed` vào danh sách terminal của lookup (lookup hiện hard-code `[Open, In Review]` nên tự động loại — OK), NHƯNG `api_repair.repair_case_grouping` di chuyển occurrence + recalc **không kiểm tra terminal** của case đích/nguồn → có thể tăng count case terminal. Cần guard.
- **Khuyến nghị**: thêm hằng `ACTIVE_CASE_STATUSES = ("Open","In Review")` dùng chung, và 1 assert phòng thủ trong `_bump_case` (nếu case không active → log + bỏ qua, không raise để khỏi vỡ ingest).

### 5. ToDo: có chưa? dedupe/close ra sao?

**Chưa có gì.** Phải xây mới. Quyết định cốt lõi (xem §D-3): dùng **Frappe-native `ToDo`** (reference_type="EC Alert", reference_name=case) vì hiện ra ở Desk awesome-bar/assignment, hay **field `todo_status` trên EC Alert** (đơn giản, không cross-module). Dedupe rule: 1 ToDo mở/case → khi tạo case mở ToDo; khi `set_status` sang terminal → đóng ToDo; vi phạm mới → case mới → ToDo mới; không reopen.

### 6. Bulk price setup reuse EC Price Policy thế nào

- Mỗi dòng grid = 1 `EC Price Policy` (brand+platform+shop+seller_sku, `is_brand_fallback=0`). KAM nhập `reference_price`(benchmark)/`target_price` + `min_price` + `severe_drop_percent` + `high_alert_percent` (optional). Các field còn lại (product_name, platform, shop) **autofill từ SKU Catalog** — không bắt KAM nhập.
- Cần **bulk upsert endpoint**: lookup theo scope-key (brand+platform+shop+seller_sku, status Active/Draft), update nếu có / insert nếu chưa — idempotent, validation-preview trước. Conflict-guard hiện có (`_guard_exact_scope_conflict`) phải được tôn trọng.
- `severe_drop_percent`/`high_alert_percent` theo decision G1.1 thuộc về **Rules** không phải Policy — nhưng business flow muốn KAM nhập tại Price Setup. **Quyết định D-5**: cho phép 2 field này sống ở Policy (engine fallback Rule→Policy đã hỗ trợ) HAY tạo rule kèm. Khuyến nghị: nhập tại Policy (đơn giản cho KAM), engine đã đọc được.

### 7. Cần DocType mới cho catalogue sync job/history?

**Không bắt buộc cho MVP, NÊN có cái nhẹ.** Hiện "last sync time" suy được từ `last_seen_at` max per brand. Đề xuất tuỳ chọn `EC Catalogue Sync Run` (brand, started/finished, pages, created/enriched/unchanged, status, error) để Brand Setup hiện "Đồng bộ lần cuối / kết quả" và audit. Nếu muốn zero-migration: lưu run summary vào `note`/Comment trên BIS như pull_recent_job đang làm. **Quyết định D-4.**

### 8. Migration nào THỰC SỰ cần

| Migration | Bắt buộc? | Lý do |
|---|---|---|
| EC Alert.status += `Closed`, `Cancelled` (Select option) | **CÓ** (nếu chốt model mới) | Lifecycle spec. Kèm data fix `Resolved`→`Closed` nếu đổi tên |
| SKU Catalog += stock, sale_price, catalogue_price, image_url, product_status_raw, last_sync_at, is_variant, parent_sku | **CÓ nếu** Brand Setup cần filter/hiển thị cột (khuyến nghị) | Hiện trong `note` JSON, không query được |
| EC Alert += `todo_*` (nếu chọn field-based ToDo) | Tuỳ D-3 | |
| `EC Catalogue Sync Run` DocType | Tuỳ D-4 | |
| EC Price Policy: thêm index/unique scope | Không bắt buộc | bulk upsert có thể lookup không cần unique |

→ **Tối thiểu 1 migration (status). Khuyến nghị 2 (status + SKU Catalog fields).** Tất cả additive, không xoá field, không đụng PM.

### 9. Permission matrix (đề xuất)

| Hành động | Admin (System Manager) | Manager (brand) | KAM (brand) |
|---|---|---|---|
| Brand Setup: API key / BIS | ✅ | ❌ | ❌ |
| Map shop → brand | ✅ | ❌ | ❌ |
| Gán KAM cho brand | ✅ | ✅ (brand mình) | ❌ |
| Chạy catalogue sync | ✅ | ✅ | ❌ (hoặc ✅ read-only preview) |
| Price Setup (nhập/sửa giá) | ✅ | ✅ | ✅ (brand mình) |
| My Alerts: In Review / Closed / Ignored | ✅ | ✅ | ✅ (brand mình) |
| Cancelled | ✅ | ❌ | ❌ (ẩn khỏi KAM) |
| Xem KPI xử lý | ✅ | ✅ | ✅ (của mình) |

Khớp `permissions.py` hiện có; chỉ cần thêm `can_setup_brand` (System Manager), `can_cancel_case` (supervisor), `can_run_catalogue_sync`.

### 10. File-level implementation plan (theo phase)

**Phase H1 — Lifecycle nền (backend, ~3h)**
- `doctype/ec_alert/ec_alert.json` (+status Closed,Cancelled) + `ec_alert.py` (terminal stamp + freeze guard).
- `services/alert_engine.py`: hằng `ACTIVE_CASE_STATUSES`, guard ở `_bump_case`.
- `api_alerts.py`: `HANDLE_STATUSES`/`NOTE_REQUIRED`/labels → Closed; thêm `cancel_case` (supervisor); dashboard counts.
- `api_repair.py`: tôn trọng terminal khi recalc.
- migration patch: `Resolved`→`Closed` (data) — `patches.txt`.
- tests: terminal-guard mọi path, cancel chỉ supervisor.

**Phase H2 — ToDo lifecycle (backend, ~2h)** (sau D-3)
- `services/case_todo.py` (open/close/dedupe 1-per-case).
- hook vào `_find_or_create_case` (mở) + `api_alerts.set_status`/`cancel_case` (đóng).
- tests: 1 ToDo/case, terminal→đóng, new case→new ToDo, no reopen.

**Phase H3 — SKU Catalog fields + Brand Setup backend (~2.5h)** (sau D-2)
- SKU Catalog json (+fields) + `catalogue_sync.upsert_catalogue_row` ghi field thật thay note JSON (giữ note fallback).
- `api_brand_setup.py`: gom readiness + assign-KAM + trigger sync (reuse api_catalogue_sync/api_brands).
- (tuỳ D-4) `EC Catalogue Sync Run`.

**Phase H4 — Price Setup bulk (backend, ~2h)**
- `api_price_setup.py`: `grid_rows(brand)` (join SKU Catalog + policy hiện có), `preview_bulk(rows)`, `save_bulk(rows)` idempotent + conflict-guard, `export_template`, `import_xlsx/csv`.
- reuse `policy_csv` + conflict-guard.

**Phase H5 — UI 3 flows (frontend, ~4h)**
- `build_alert_pages.py`: trang Brand Setup, Price Setup (grid Excel-like), My Alerts (3 action, ẩn Cancelled). Reuse shell/CSS.
- deploy qua `deploy_alert_pages.ps1`.

**Phase H6 — verify + deploy (~1.5h)**: full suite, bench run-tests, staged deploy, UAT script.

### 11. Test & deploy plan

- **Unit/pure**: lifecycle guard, todo dedupe, bulk upsert idempotency, price-field autofill, permission matrix — chạy sandbox như hiện tại (git-show base + /tmp).
- **Bench**: migration patch (Resolved→Closed), DocType JSON parse, todo cross-check.
- **Deploy**: backend code-only branches per phase; **migration phases (H1, H3) chạy `bench migrate`** — tách PR riêng, confirm từng turn. Frontend qua deploy_alert_pages.ps1. Order pull/scheduler KHÔNG đụng. Mỗi phase: branch verify → PR → merge → FC deploy → verify live.

---

## C. Constraints tuân thủ

PM module: không đụng (chỉ đọc ToDo làm tham chiếu). Core price calc (`pricing.evaluate_components`): không sửa. Omisell/stock write: không. Order pull: không đụng path; catalogue sync vẫn manual/thấp ưu tiên hơn pull. UI: che thuật ngữ kỹ thuật (case_key, occurrence, rule_code → nhãn tiếng Việt thân thiện).

## D. Quyết định cần APPROVAL trước khi code

1. **Status model**: đổi `Resolved`→`Closed` (data migration) HAY giữ `Resolved` nội bộ + chỉ relabel UI thành "Đã xử lý"? (Khuyến nghị: relabel UI, giữ value `Resolved` để khỏi migrate data — nhưng spec ghi rõ "Closed". Cần anh chốt.)
2. **SKU Catalog**: promote stock/sale_price/image/... thành field thật (migration, khuyến nghị) HAY giữ trong note JSON (zero-migration nhưng không filter được)?
3. **ToDo**: Frappe-native `ToDo` (hiện ở Desk) HAY field `todo_status` trên EC Alert (đơn giản, self-contained)? Khuyến nghị field-based để không phụ thuộc Desk + dễ test.
4. **Catalogue Sync Run history**: DocType mới (audit đẹp) HAY Comment/note trên BIS (zero-migration)?
5. **severe_drop/high % nhập ở đâu**: tại Price Setup (Policy, đơn giản cho KAM, engine đã fallback) HAY bắt buộc qua Rules (cần approval F-2)? Khuyến nghị Policy.
6. **Cancelled quyền**: chỉ System Manager, hay Manager cũng được? (Spec: Admin/System only — khuyến nghị giữ vậy.)
7. **Catalogue sync ai chạy**: chỉ Admin, hay Manager cũng được trigger cho brand mình?

Sau khi anh chốt D1–D7, em khoá phase plan + bắt đầu H1.

---

## E. LOCKED DECISIONS (2026-06-13)

- **D1 — Status = `Closed` canonical.** Thêm `Closed` + `Cancelled`. Patch migrate `Resolved`→`Closed` (giá trị lưu cuối cùng phải là Closed). Trong rollout, compat-read có thể tạm coi `Resolved` là terminal, nhưng stored value cuối = Closed. **Terminal = {Closed, Ignored, Cancelled}.** Guard tường minh MỌI path append/bump/recalc chống case terminal.
- **D2 — Promote SKU Catalog fields** (additive): `image_url, catalogue_price, sale_price, stock, catalogue_id, external_product_id, parent_sku, is_variant, product_status, price_confidence, catalogue_synced_at`. `note` JSON chỉ giữ raw metadata phụ, KHÔNG giữ field mà UI/query cần.
- **D3 — ToDo = Frappe-native.** ≤1 ToDo mở/case; `reference_type="EC Alert"`, `reference_name=case`; allocate cho KAM của brand. Open/In Review → ToDo mở; Closed/Ignored/Cancelled → đóng. Vi phạm mới sau terminal → case mới + ToDo mới; không reopen/append case+ToDo cũ. Link field `todo_name` trên EC Alert OK để lookup, nhưng Frappe ToDo là source of truth.
- **D5 — Threshold ownership.** KAM nhập benchmark/min/severe-drop%/high% (optional) trực tiếp ở Price Setup, lưu vào `EC Price Policy` per SKU. Rules page = trang Admin/advanced defaults, KHÔNG nằm trong luồng KAM thường.

### Revised file-level plan (theo implementation order đã chốt — 8 bước)

**Step 1 — Status model + terminal guards (migration, ~3h)**
`doctype/ec_alert/ec_alert.json` (+`Closed`,`Cancelled`); `ec_alert.py` (stamp resolved_* cho {Closed,Ignored,Cancelled}; freeze khi terminal); `services/alert_engine.py` (`ACTIVE_CASE_STATUSES=("Open","In Review")`, guard ở `_record_price_violation` + `_bump_case`); `api_alerts.py` (`HANDLE_STATUSES`/`NOTE_REQUIRED`/dashboard counts → Closed; `+cancel_case` supervisor-only; compat-read coi Resolved như Closed); `api_repair.py` (recalc bỏ qua/không bump case terminal); `patches.txt` + patch `migrate_resolved_to_closed`. Tests: terminal guard mọi path, compat-read, cancel quyền.

**Step 2 — ToDo lifecycle (~2h)**
`services/case_todo.py` (open/close/dedupe native ToDo, allocate KAM qua `brand_resolver`); hook mở ở `_find_or_create_case`, đóng ở `set_status`/`cancel_case`; `+todo_name` link trên EC Alert (additive, gộp vào migration Step 1 hoặc tự migration nhẹ). Tests: 1-ToDo/case, terminal→đóng, new-case→new-ToDo, no-reopen.

**Step 3 — Promoted SKU fields + backfill (migration, ~2.5h)**
SKU Catalog json (+11 field D2); `services/catalogue_sync.upsert_catalogue_row` ghi field thật (note giữ raw phụ); patch backfill từ `note` JSON hiện có sang field mới (idempotent). Tests: normalize→field, backfill, hash-gate vẫn idempotent.

**Step 4 — Persistent background catalogue sync (~2h)**
Chuyển catalogue confirm sang background job pattern (giống `pull_recent_job`): enqueue + lock + page-stream + `catalogue_synced_at` + run summary. **Gating: order pull ưu tiên** — catalogue job queue thấp hơn / skip nếu pull đang chạy. KHÔNG vào scheduler trừ khi approve riêng. (Liên quan D4.)

**Step 5 — Brand Setup backend+UI (~2.5h)**
`api_brand_setup.py` (gom BIS/API key + shop map + assign-KAM + trigger sync, reuse api_brands/api_catalogue_sync); trang Brand Setup. (Liên quan D6/D7.)

**Step 6 — Price Setup bulk (~3h)** — **DEPENDENCY (Gate 2, locked 2026-06-13):** the brand Setup-ToDo remaining count (Step 2) is driven by ACTIVE `missing_policy` CASES, not by EC Price Policy row existence. After a successful policy `save_bulk`, Step 6 MUST auto-close the matching active `missing_policy` case(s) for that brand+SKU and re-trigger the brand setup-ToDo recompute (a `case_todo`-visible status change). Without this, creating a policy does NOT reduce the count / close the Setup ToDo. Do not claim auto-close on policy creation until this integration ships.
`api_price_setup.py` (`grid_rows` join SKU Catalog+policy, `preview_bulk`, `save_bulk` idempotent + conflict-guard, export template, import csv/xlsx); grid UI inline-edit/bulk-apply/paste/import/preview. Reuse `policy_csv`.

**Step 7 — My Alerts UI (~2h)**
Trang 3-action (In Review/Closed/Ignored), ẩn Cancelled khỏi KAM; reuse occurrences drawer.

**Step 8 — Guides + deploy + soak (~1.5h)**
Full suite + bench run-tests; staged deploy per phase (migration phases = PR riêng + `bench migrate`, confirm từng turn); UAT + soak. Order pull/scheduler không đụng.

Tổng ~18h — sẽ siết lại sau khi chốt D4/D6/D7.

### D4, D6, D7 — LOCKED (2026-06-13)

- **D4 — Catalogue sync history = DocType `EC Catalogue Sync Run`** (additive migration). Fields: brand, started_at, finished_at, pages_fetched, created, enriched, unchanged, skipped, errors, status (Running/Done/Done Partial/Error), error_summary, triggered_by, next_page. Brand Setup đọc run mới nhất để hiện "đồng bộ lần cuối + kết quả". `catalogue_synced_at` (D2) vẫn set per-SKU.
- **D6 — Cancelled = chỉ System Manager/Admin.** KAM + Manager không thấy nút Cancel. Giữ KPI sạch. `permissions.can_cancel_case` = `is_global_supervisor` only.
- **D7 — Trigger catalogue sync = Admin + Manager + KAM, NHƯNG**: KAM chỉ sync brand mình; **background-only** (không sync đồng bộ trong web request); **lock per-brand** (1 job/brand, reuse pattern running-flag); **cooldown** (chặn re-trigger trong N phút, site_config `ec_alerts_catalogue_cooldown_minutes`, mặc định vd 30). Preview vẫn read-only mọi role có brand access. `permissions.can_run_catalogue_sync(user, brand)` = supervisor | manager(brand) | kam(brand). Order pull luôn ưu tiên: catalogue job ở queue thấp hơn / skip khi pull của brand đang chạy.

→ **D7 ảnh hưởng Step 4 + Step 5**: thêm cooldown gate + per-brand lock + ưu-tiên-pull vào catalogue background job; `EC Catalogue Sync Run` ghi `triggered_by` để audit ai chạy.

### TẤT CẢ D1–D7 đã chốt. Plan khoá. Chờ lệnh bắt đầu Step 1.

Lưu ý deploy: Step 1, 2, 3, 4 đều có migration (status options + todo_name + 11 SKU fields + EC Catalogue Sync Run). Mỗi migration = PR riêng + `bench migrate`, **cần anh confirm trong cùng turn** trước mỗi lần chạy production (theo CLAUDE.md A33). Order pull/scheduler không đụng ở bất kỳ phase nào.
