# 55 — G2.2 confirm caps hotfix (Bad Gateway)

Date: 2026-06-12 · Status: BUILT, 114/114 tests pass (full suite, 1 bench-only skip), awaiting deploy. KHÔNG chạy LOF confirm cho tới khi deploy bản này.

## Root cause (xác nhận đúng chẩn đoán của anh)

`confirm_catalogue_sku_sync` (doc 54) có 2 lỗi: (1) default `pages = 40` cho synchronous web request — quá nặng; (2) signature chỉ nhận `pages/page_size/max_rows`, caller gửi `pages_requested`/`row_cap` bị **lặng lẽ bỏ qua** → chạy với default 40 pages/1000 rows → fetch 40 pages (pacing ~1s/call) + upserts vượt gunicorn timeout → Bad Gateway / bench down. Order pull/scheduler vô can (LOF idle/done/caught_up sau đó).

## Fix (3 files, code-only, NO migration)

**`services/catalogue_sync.py`** — `resolve_confirm_params()` PURE: nhận đủ alias (`pages|max_pages|pages_requested`, `max_rows|row_cap|limit`, `page_size`, `start_page`, `allow_heavy`), lấy giá trị non-empty đầu tiên, clamp: pages default **2**, hard **≤5** sync trừ khi `allow_heavy=1` (SM, trần 40); rows default **300**, trần 5000; page_size ≤100; fail-safe mọi input rác.

**`api_catalogue_sync.py`** — viết lại confirm thành **page-streaming**: fetch page → upsert ngay → page kế. `TIME_BUDGET_SECONDS = 50` (cùng lý do SYNC_TIME_BUDGET), check deadline cả fetch-phase lẫn upsert-phase. Dừng vì cap/budget → `timeboxed=true` hoặc `capped_at` + `next_page` + `rows_processed`; resume bằng `start_page=next_page` (upsert hash-gated idempotent nên overlap page dở dang an toàn). Response **echo** `effective_page_size` / `effective_pages_requested` / `effective_row_cap` / `allow_heavy` / `start_page`. Hết data → `complete=true`. Preview giữ zero-write, dùng cùng resolver/caps.

**`tests/test_catalogue_sync.py`** — +13 tests: honor từng alias (`pages_requested`, `max_pages`, `row_cap`, `limit`), precedence first-non-empty, defaults sync-safe (2/300/50), hard cap 5 trừ allow_heavy (trần 40), clamps + fail-safe, start_page, echo effective_*, timebox/next_page/partial wiring, re-run idempotent (hash-gate). Tổng module 28 tests; full suite **114/114**.

## Deploy (owner — gộp vào branch feat/g2-2-catalogue-sync)

```powershell
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/services/catalogue_sync.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/api_catalogue_sync.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/tests/test_catalogue_sync.py
git -C C:\dev\ecentric_workspace commit -m "fix(alerts): G2.2 confirm honors cap aliases + sync-safe defaults + page-streaming timebox"
# push -> PR -> merge -> FC deploy (code-only, no migrate)
```

## Run LOF confirm SAU deploy (an toàn theo từng bước nhỏ)

```powershell
# 1. preview truoc (zero write) - check platform/price report
Body: {"brand":"LOF-VN","pages":2}  -> preview_catalogue_sku_sync
# 2. confirm nho dau tien - mac dinh da an toan (2 pages / 300 rows / 50s)
Body: {"brand":"LOF-VN"}            -> confirm_catalogue_sku_sync
# 3. doc response: effective_pages_requested=2, effective_row_cap=300;
#    neu timeboxed/capped -> chay tiep voi {"brand":"LOF-VN","start_page":<next_page>}
# 4. lap toi khi complete=true; re-run bat ky luc nao cung chi ra unchanged.
# 5. catalogue lon va muon chay nhanh hon: {"pages_requested":5} hoac
#    {"allow_heavy":1,"pages":10} - co y thuc rang heavy co the cham.
```

Verify: counts hợp lý, `EC Marketplace SKU Catalog` không dup (re-run → unchanged), bench không 502, FES/LOF scheduler vẫn idle/done trong lúc chạy.
