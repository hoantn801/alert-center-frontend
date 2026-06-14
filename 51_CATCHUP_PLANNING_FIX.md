# 51 — Catch-up planning fix: span-based cap + caught_up trung thực

Date: 2026-06-12 · Status: BUILT, 96/96 tests pass (full suite, 1 bench-only skip), awaiting deploy.
Bug (LOF-VN): adaptive 30m chunks + cap cứng 12 chunks → mỗi run phủ tối đa 6h = đúng bằng overlap → checkpoint stale không bao giờ đuổi kịp `now`, nhưng `caught_up=true` (đếm theo count) và monitor stale.

## Root cause

`eff_chunks = min(max(max_chunks, span_chunks), MAX_OVERLAP_CHUNKS=12)` — cap theo SỐ chunk, không theo SPAN. Với cs=1800: 12×30m=6h. Window 14:48→01:17 (~10.5h) cần 21 chunks → plan bị cắt ở 20:48 mà `caught_up = chunks_done == chunks_planned` vẫn true.

## Changes (1 file mới + 1 file sửa + tests, code-only, NO migrate)

**`services/pull_planner.py` (MỚI, PURE — frappe-free):** `plan(start, end, chunk_seconds, min_chunks, span_seconds)` → `required_chunks = ceil(window/cs)`, `span_cap_chunks = span//cs`, chunks contiguous ≤cs, `planned_end`, `truncated = planned_end < end`. Truncation được BÁO, không giấu.

**`api_omisell.py`:**

1. `MAX_CATCHUP_SPAN_SECONDS = MAX_OVERLAP_CHUNKS × MAX_WINDOW_SECONDS` (12h) — cap theo SPAN, đúng nghĩa của cap "12×1h" cũ. cs=1800 → tối đa 24 chunks; cs=3600 → 12 như cũ (FES-VN không đổi hành vi).
2. `pull_recent_job` dùng planner; run summary thêm `required_chunks`, `planned_to`.
3. `caught_up = done_all AND not truncated` — chỉ true khi chunk cuối chạm đúng `to` (REQ 3).
4. Không caught_up → `state = "done_partial"` + `next_from` (end của chunk thành công cuối, = vị trí checkpoint), `remaining_seconds`, `capped_at` (khi bị span-cap) — hiện qua `pull_status.last_run` (REQ 4).
5. `last_sync_at` vẫn advance monotonic theo từng chunk thành công trong `pull_orders` (không đổi, REQ 5); lock vẫn xoá trong finally (không đổi, REQ 6).

`chunk_windows()` giữ nguyên trong api_omisell (test_phase_d1 tham chiếu) — chỉ pull_recent_job chuyển sang planner.

## Tests

**`tests/test_catchup_planner.py` (MỚI, 11 tests):** đúng window incident LOF (14:48:52→01:17:45, cs=1800): required=21, span_cap=24, KHÔNG truncate, chunk cuối == `to` (REQ 7a/7c); mô phỏng cap cũ 6h → truncate tại 20:48 (document bug); backlog 30h → truncate tại 12h và báo đúng; chunks contiguous; FES 1h-chunk behavior không đổi; edge windows. Wiring: caught_up formula mới (formula cũ bị cấm), done_partial + next_from/remaining_seconds/capped_at/planned_to, monotonic guard + `last_end = ct`, lock finally (REQ 7b/7d).
Cập nhật assert cũ ở `test_tz_epoch.py` + `test_pull_resilience.py` (planning chuyển sang planner).

Full suite: **96/96 OK** (catchup 11 + resilience 12 + tz 14 + case-grouping 15 + g1_1 19 + g2 9 + rules_pure 16; 1 bench skip).

## Deploy (owner)

```powershell
git -C C:\dev\ecentric_workspace rev-parse --abbrev-ref HEAD   # verify FIRST
git -C C:\dev\ecentric_workspace checkout -b fix/catchup-span-planning
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/api_omisell.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/services/pull_planner.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/tests/test_catchup_planner.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/tests/test_tz_epoch.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/tests/test_pull_resilience.py
git -C C:\dev\ecentric_workspace commit -m "fix(alerts): span-based catch-up planning + honest caught_up/done_partial"
# push -> PR -> merge -> FC deploy (code-only, no migrate)
```

(Nếu doc 50 chưa deploy: gộp chung 1 PR — cùng các file.)

## Verify sau deploy (LOF-VN)

1. `pull_recent(LOF-VN)` → `pull_status.last_run`: `chunks_planned == required_chunks` (≤ span cap), `planned_to == to`, chunk cuối chạm `to`, `caught_up=true`, `state=done`.
2. Nếu backlog >12h: `state=done_partial`, `caught_up=false`, có `capped_at`/`next_from`/`remaining_seconds`; run kế tiếp tiếp tục từ checkpoint − overlap và `remaining_seconds` giảm dần về 0.
3. `last_sync_at` tiến sau mỗi run (monitor hết stale); `running_since` null sau run.
4. FES-VN: hành vi không đổi (1h chunks, window nhỏ).
