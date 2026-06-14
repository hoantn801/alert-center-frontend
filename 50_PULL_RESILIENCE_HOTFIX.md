# 50 — Omisell pull resilience hotfix (LOF read-timeout)

Date: 2026-06-11 · Status: BUILT, 85/85 tests pass (full suite, 1 bench-only skip), awaiting deploy.
Incident: LOF-VN run lỗi `HTTPSConnectionPool... Read timed out (read timeout=30)` giữa chừng dù logic đúng (chunks 33/33, 35/35, 73/73...; breaker 0, failed 0). Network/API timeout, không phải data bug.

## Changes (2 files sửa + 1 test mới, code-only, NO migrate)

**`services/omisell_client.py`**

1. Retry read/connect timeout: `BACKOFFS_TIMEOUT = (2, 5)` — bắt `requests.Timeout` + `requests.ConnectionError` quanh `requests.request`, retry tối đa 2 lần, **GET-only** (GET là read-only nên replay luôn an toàn; auth POST KHÔNG retry — POST timeout có thể đã thành công server-side). Hết retry → `OmisellError("TIMEOUT on GET <path> ...")` để pipeline hiện hữu xử lý (breaker/alert) và classifier nhận diện.

**`api_omisell.py`**

2. Lock safety: `pull_recent` bọc `frappe.enqueue` trong try/except — enqueue fail thì xoá running lock ngay (trước đây brand bị khoá RUNNING_FLAG_TTL=3900s). `pull_recent_job` finally vẫn xoá lock như cũ (mọi exception đều qua finally).
3. Resumability (đã đúng sẵn, nay bảo toàn + ghi rõ): checkpoint advance theo TỪNG chunk thành công bên trong `pull_orders`; chunk fail không rollback (monotonic guard giữ nguyên); run kế tiếp tự resume từ `last_sync_at − overlap`.
4. Adaptive chunking `_chunk_seconds(brand)`: mặc định 1h; site_config `ec_alerts_pull_chunk_seconds` override (clamp 300..3600, không schema); tự động: nếu run TRƯỚC có chunk nặng (listed ≥ 60 hoặc elapsed ≥ 240s) → run này dùng chunk 30m (ít detail-GET hơn mỗi chunk → timeout mất ít công hơn, checkpoint nhích thường xuyên hơn). Fail-safe 1h. Run summary ghi `chunk_seconds`.
5. Error visibility: chunk loop bắt exception, ghi vào run (hiện qua `pull_status.last_run`): `failed_chunk_window` [from,to], `failed_stage` (list/auth/detail/other), `timeout` (bool), `stopped`; rồi re-raise để outer handler set state=error + finally xoá lock.

Constraints giữ: no Omisell write (client vẫn GET-only chokepoint), no stock write, scheduler semantics không đổi (chỉ resilience), no PM/hooks/tasks.

## Tests (`tests/test_pull_resilience.py` — 12 tests)

REQ 7b: fake transport timeout 1 lần → `_request` thành công attempt 2 (calls==2); hết retry → OmisellError "TIMEOUT" (calls==3); auth POST không retry (calls==1). REQ 7a: source asserts lock xoá trong finally + enqueue guard. REQ 7c: monotonic guard + model test. REQ 7d: dedupe keys deterministic (occurrence/price/lock) — GET replay được Order Log upsert + Occurrence dedupe hấp thụ (ingestion không đổi). + adaptive wiring + GET-only guard asserts.

Full suite sau thay đổi: **85/85 OK** (resilience 12 + tz 14 + case-grouping 15 + g1_1 19 + g2 9 + rules_pure 16; 1 bench skip) — test_tz_epoch cập nhật 1 assert theo signature `chunk_windows(..., chunk_seconds=cs, ...)`.

## Deploy (owner)

Cùng repo-files với 2 fix đang chờ — gộp PR hợp lý nhất theo thứ tự: tz/overlap đã deploy rồi → branch mới `fix/pull-resilience`:

```powershell
git -C C:\dev\ecentric_workspace rev-parse --abbrev-ref HEAD   # verify FIRST
git -C C:\dev\ecentric_workspace checkout -b fix/pull-resilience
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/services/omisell_client.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/api_omisell.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/tests/test_pull_resilience.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/tests/test_tz_epoch.py   # 1 assert update
git -C C:\dev\ecentric_workspace commit -m "fix(alerts): GET timeout retry + lock safety + adaptive chunks + failed-chunk visibility"
# push -> PR -> merge -> FC deploy (code-only, no migrate)
```

## Verify sau deploy (LOF-VN)

1. `pull_recent(LOF-VN)` → `pull_status`: run hoàn tất hoặc nếu fail có `failed_chunk_window`/`failed_stage`/`timeout` rõ ràng; `running_since` null sau khi job xong/lỗi (lock sạch).
2. Nếu run trước nặng → run sau `chunk_seconds = 1800` trong last_run.
3. Re-run sau timeout: resume từ checkpoint, **không** Order Log/Occurrence dup (đếm trước/sau).
4. FES-VN không đổi hành vi (chunk 1h khi volume thấp).
5. Tuỳ chọn: set `ec_alerts_pull_chunk_seconds=1800` cứng cho LOF nếu volume luôn cao.
