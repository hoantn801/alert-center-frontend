# 56 — search_skus fix: q aliases + exact-first ranking

Date: 2026-06-12 · Status: BUILT, 123/123 tests pass (full suite, 1 bench-only skip), awaiting deploy.
Incident: `search_skus(brand=LOF-VN, q=GBS_LOF_8936025777042-48)` trả rows không liên quan dù SKU tồn tại chính xác trong DB (EC-SKU-003741).

## Root cause — cùng bug class với doc 55 (lần 3)

Signature cũ chỉ nhận `keyword`; caller gửi `q=` bị Frappe **lặng lẽ bỏ qua** → keyword rỗng → endpoint trả top-20 rows mới nhất của brand (không filter) = "unrelated rows".

## Fix (`api_sku_catalog.py` + tests, code-only, NO migration)

1. **Aliases**: `resolve_search_query(q, query, search, keyword)` PURE — first non-empty wins.
2. **Filter khi có q**: `seller_sku LIKE %q% OR product_name LIKE %q%` (giữ nguyên semantics, fetch headroom limit×3 ≤150 để ranking promote).
3. **Ranking** `rank_sku_match()` PURE: 0 = exact seller_sku (case-insensitive) → 1 = SKU chứa q → 2 = product_name chứa q → 3 = loại bỏ. Sort stable nên trong cùng rank vẫn theo last_seen desc.
4. **Literal re-check**: q thường chứa `_` (SQL LIKE wildcard = 1 ký tự bất kỳ) → row khớp LIKE nhưng không chứa literal q (vd `GBSxLOFx...`) bị **drop** thay vì trả về.
5. **No match → `rows: []`** — không bao giờ trả rows brand không liên quan.
6. **Brand scope giữ nguyên**: `require_brand_access` + filter `brand =` không đổi; platform/shop filter không đổi.

Không đụng: catalogue sync, scheduler, ingest, pull_recent, Omisell write, stock, PM/hooks/tasks, migration.

## Tests (`tests/test_sku_search.py` MỚI — 9 tests, chạy mọi nơi)

Fake `frappe.get_all` mô phỏng **đúng SQL LIKE wildcards** (`%`/`_`) + stub perms: exact q → đúng SKU đứng đầu; partial q → chỉ rows match, SKU-partial trước name-match; aliases `query`/`search`/`keyword` đều hoạt động; no-match → `[]`; brand scope assert cả perms call lẫn filter; wildcard false-hit bị drop; + pure rank/alias tables. Full suite **123/123**.

Sự cố phụ trong lúc build: bản đầu test file dính NUL bytes (sentinel chars lọt vào Edit) — đã ghi đè sạch, verify 0 NUL + ASCII clean cả 2 file.

## Deploy (owner — gộp branch feat/g2-2-catalogue-sync hoặc branch riêng)

```powershell
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/api_sku_catalog.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/tests/test_sku_search.py
git -C C:\dev\ecentric_workspace commit -m "fix(alerts): search_skus honors q aliases + exact-first ranking + no-match empty"
# push -> PR -> merge -> FC deploy (code-only, no migrate)
```

## Verify sau deploy

```powershell
# exact -> dong dau tien phai la GBS_LOF_8936025777042-48
Body: {"brand":"LOF-VN","q":"GBS_LOF_8936025777042-48"}
# partial -> chi cac SKU/ten chua chuoi nay
Body: {"brand":"LOF-VN","q":"8936025777042"}
# rac -> rows = []
Body: {"brand":"LOF-VN","q":"NO-SUCH-SKU"}
```

UI: /alerts/policies → SKU search modal gõ đúng SKU → kết quả đầu tiên là SKU đó (modal dùng cùng endpoint).
