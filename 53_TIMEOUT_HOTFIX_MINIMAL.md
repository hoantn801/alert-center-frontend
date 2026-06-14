# 53 — Minimal Omisell timeout hotfix (no adaptive, no planner)

Date: 2026-06-12 · Status: BUILT trên đúng nền post-revert (HEAD sau PR #27 revert #25/#26), 86/86 tests pass, awaiting deploy.
Incident: LOF-VN lặp lại `Read timed out (read timeout=30)`; lock sạch (`running_since=null`), 3/7 chunks xong, 232 orders đã ingest — network/API chậm, không phải lock/logic.

## Scope — đúng yêu cầu, KHÔNG tái-nhiễm #25/#26

Có: GET retry + timeout 60s configurable + lock guard + error visibility.
KHÔNG: adaptive chunking, pull_planner, done_partial, chunk_seconds — test có guard cấm các symbol này quay lại. 1h chunk planning giữ nguyên (span_chunks/MAX_OVERLAP_CHUNKS như cũ).

## Changes (2 files sửa + 1 test, code-only, NO migrate)

**`services/omisell_client.py`**

1. `BACKOFFS_TIMEOUT = (2, 5)` — bắt `requests.Timeout`/`ConnectionError`, retry tối đa 2 lần sau lần fail đầu, **GET-only** (non-GET/auth POST không bao giờ retry — có thể đã thành công server-side). Hết retry → `OmisellError("TIMEOUT on GET <path> (after 2 retries, read_timeout=Ns): ...")`.
2. `read_timeout()`: mặc định **60s** (`DEFAULT_READ_TIMEOUT`), override qua site_config `ec_alerts_omisell_read_timeout` (clamp 10..180, fail-safe 60). `requests.request(..., timeout=read_timeout())`.

**`api_omisell.py`**

3. `pull_recent`: enqueue fail → xoá running lock ngay (job finally vẫn xoá như cũ — REQ 3).
4. Chunk loop: bắt exception → ghi vào run (`pull_status.last_run`): `failed_chunk_window`, `failed_stage` (list/auth/detail/other), `timeout` bool, `stopped`; re-raise → state=error, finally xoá lock, run kế resume từ `last_sync_at − overlap` (checkpoint per-chunk không đổi).

**`tests/test_pull_resilience.py`** (viết lại minimal, 14 tests): retry thành công attempt 2 (REQ 6a); exhaust → OmisellError có "TIMEOUT" + "read_timeout=" (6b); non-GET không retry, 1 call duy nhất (6d); lock finally + enqueue guard (6c); `read_timeout()` default 60 / override 90/120 / clamp 10·180 / fail-safe + được truyền vào requests; **guard chống tái-nhiễm**: cấm `_chunk_seconds`/`pull_planner`/`MAX_CATCHUP`/`ADAPTIVE_`/`done_partial`, bắt buộc `span_chunks`+`chunk_windows(start, end, max_chunks=eff_chunks)` y nguyên; monotonic guard intact.

Verify: py_compile + ASCII, full suite **86/86** (resilience 14 + tz 14 + case-grouping 15 + g1_1 19 + g2 9 + rules 16; 1 bench skip) chạy trên git-show HEAD + patch (tránh mount staleness). Repo chỉ 3 file intended có marker mới.

## Deploy (owner)

```powershell
git -C C:\dev\ecentric_workspace checkout main && git pull
git -C C:\dev\ecentric_workspace checkout -b fix/omisell-timeout-minimal
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/services/omisell_client.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/api_omisell.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/tests/test_pull_resilience.py
git -C C:\dev\ecentric_workspace commit -m "fix(alerts): GET timeout retry + 60s configurable read timeout + lock guard + failed-chunk visibility (minimal, no adaptive)"
# push -> PR -> merge -> FC deploy (code-only, no migrate)
```

Lưu ý: em sửa trên working tree branch hiện tại (`g2.2-omisell-product-probe`) — anh có thể `git stash` / cherry-pick sang branch mới từ main; diff thực chỉ nằm trong 3 file trên (các " M" khác là CRLF noise từ mount).

## Verify sau deploy (LOF-VN)

1. `pull_recent(LOF-VN)` → kỳ vọng đa số timeout 30s cũ biến mất (60s + 2 retry hấp thụ spike).
2. Nếu vẫn lỗi: `last_run` có `failed_stage`/`failed_chunk_window`/`timeout=true`, error message chứa `read_timeout=60s`; `running_since=null`.
3. Run kế tiếp resume, `chunks_done` tăng dần tới `caught_up=true`; không dup Order Log/Occurrence.
4. Tuỳ chọn nếu LOF vẫn chậm: `ec_alerts_omisell_read_timeout=90` trong site_config (không cần deploy).
