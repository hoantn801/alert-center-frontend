# 49 — Case grouping fix: platform + shop vào Case scope

Date: 2026-06-11 · Status: BUILT, 73/73 tests pass (1 bench-only skip), awaiting deploy.
Bug thật (không phải UI): Lazada P02056 occurrences (EC-AOCC-001219/001223) gắn vào case Shopee EC-AL-000708 vì `_find_or_create_case` lookup + case key chỉ gộp theo **brand+sku+rule**.

## Changes (3 files sửa + 1 file mới, code-only, NO migrate)

| File | Change |
|---|---|
| `services/dedupe_keys.py` | NEW `case_key(brand, platform, shop, sku, rule, order, line)` → `case\|brand\|platform\|shop\|sku\|rule\|order\|line` (pure, _fit 140). |
| `services/alert_engine.py` | `_find_or_create_case`: open-case lookup thêm `platform` + `shop`; key dùng `dedupe_keys.case_key`. Occurrence dedupe / `_bump_case` / missing_* path **không đổi**. |
| `api_repair.py` | NEW SM-only POST `repair_case_grouping(brand=None, dry_run=1)`. Quét case price-rule đang Open/In Review có occurrence lệch platform/shop → tách về case đúng scope (tìm case mở cùng scope hoặc tạo mới với key mới), repoint `occurrence.case`, **recalc rollups từ occurrences** (occurrence_count, first/last_seen_at, worst_gap_percent, effective_check_price/actual/gap = occurrence mới nhất), Comment audit trên mọi case chạm vào. dry_run=1 mặc định; không delete, không đổi status; case rỗng sau repair được liệt kê để xử lý tay. |
| `tests/test_case_grouping.py` | NEW 15 tests: key tách theo platform/shop (đúng kịch bản EC-AL-000708), cùng scope reuse case, occurrence key stable khi re-pull, engine wiring (lookup 5 trường, dedupe trước create), repair safety (SM-only, dry-run default, no delete/status, recalc đủ field, chỉ price rules). +1 bench test (skip ngoài bench): 2 platform → 2 case, cùng scope → reuse. |

Constraints giữ nguyên: no Omisell write, no stock write, no scheduler/hooks/tasks/PM, alert-engine chỉ sửa đúng hàm grouping.

## Verify đã chạy (sandbox)

py_compile 4 files OK, ASCII clean, full suite **73/73 pass** (test_tz_epoch 14 + test_case_grouping 15 + test_phase_g1_1 19 + test_phase_g2 9 + test_rules_pure 16, 1 bench-skip) — không regression.

## Deploy (owner, Windows)

```powershell
git -C C:\dev\ecentric_workspace rev-parse --abbrev-ref HEAD   # verify FIRST
git -C C:\dev\ecentric_workspace checkout -b fix/case-grouping-platform-shop
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/services/dedupe_keys.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/services/alert_engine.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/api_repair.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/tests/test_case_grouping.py
git -C C:\dev\ecentric_workspace commit -m "fix(alerts): case grouping by brand+platform+shop+sku+rule + repair endpoint"
# push -> PR -> merge -> FC deploy (code-only, no migrate)
```

## Repair runbook (sau deploy)

```powershell
# 1. DRY RUN - xem plan, không ghi gì
Invoke-FrappeMethod "ecentric_workspace.alerts.api_repair.repair_case_grouping" @{ brand = "FES-VN"; dry_run = 1 }
# expect: mixed_cases chứa EC-AL-000708 với groups Shopee|FES-VN-SHOPEE + Lazada|FES-VN-LAZADA

# 2. Chạy thật (cần confirm trong cùng turn theo quy tắc production-write)
Invoke-FrappeMethod "ecentric_workspace.alerts.api_repair.repair_case_grouping" @{ brand = "FES-VN"; dry_run = 0 }
```

## Verify sau repair (/alerts, Ctrl+Shift+R)

1. 2 case rows riêng: `Shopee / FES-VN-SHOPEE / P02056 / below_min` và `Lazada / FES-VN-LAZADA / P02056 / below_min` (case Lazada mới có occurrence_count=2, chứa EC-AOCC-001219+001223).
2. EC-AL-000708 occurrence_count giảm tương ứng, rollups recalc đúng; Comment audit trên cả 2 case.
3. Đơn Lazada P02056 mới tiếp theo → vào case Lazada (không vào 000708).
4. Re-pull 2 đơn cũ → không tạo occurrence mới (dedupe giữ).
5. Bench (tuỳ chọn): `bench --site <site> run-tests --module ecentric_workspace.alerts.tests.test_case_grouping` (chạy thêm bench test).
