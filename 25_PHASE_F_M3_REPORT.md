# Phase F — M3 Local Report (Rules Configuration Page)

Date: 2026-06-10 · Status: **M3 BUILT LOCALLY (workspace-side; app repo unchanged at `1a13fe9`). M4 not started.**

## 1. Files changed

`frontend/build_alert_pages.py` (+PAGE3 content/JS + M3 acceptance asserts) · `frontend/alert_rules.html` (50.8 KB, built) · `deploy/deploy_alert_pages.ps1` + `rollback_alert_pages.ps1` (+alert-rules entry, still ASCII-only). Zero app-repo changes (branch tip verified unchanged).

## 2. UI layout summary

```
[shell + subnav (Rules active)]
[al-banner — VN]: "Rule chỉ ảnh hưởng việc ĐÁNH GIÁ ALERT và ĐỀ XUẤT DRY-RUN
  stock lock. Không có thao tác khoá kho thật — DS1 đang khoá. Không rule nào
  thì engine giữ nguyên hành vi mặc định."           <- required explanation
[panel header]: "Cấu hình rule cảnh báo · Ưu tiên scope: SKU > Shop > Platform > Brand"
[filters: brand / rule / status]
[12-col table: Rule · Tầng scope (tier BADGE per row) · brand/platform/shop/SKU ·
 severity override · ngưỡng % · đề xuất lock (dry-run badge) · status ·
 duyệt bởi · hiệu lực]
[drawer-form]: rule_code · brand · scope fields → LIVE tier line ("Tầng scope
 hiện tại: [SKU]") recomputed on every keystroke · severity override ·
 threshold % (+ per-rule meaning hint) · recommend-lock checkbox — DISABLED
 unless severe_price_drop/possible_missing_zero, with the hard-matrix hint
 ("chỉ THU HẸP — vẫn cần policy bật lock; below_min/above_high không bao giờ
 lock — cứng trong code") · effective dates · status line (shows "Activate/
 Pause cần Lead/System Manager" for KAM) · [Kiểm tra trùng/override] button →
 overlap result block · actions: Lưu (Draft) / →Active / →Paused / →Draft
```

## 3. Endpoint usage

`api_alerts.my_scope` (bootstrap) · `api_rules.list_rules / save_rule / set_rule_status / check_rule_overlap`. All M1 endpoints, brand-scoped server-side; page does no client-side authority decisions (hints only).

## 4. Permission behavior (F-2 — server is the enforcer, UI only hints)

KAM: create/edit → server saves as Draft (and demotes edited Active rules to Draft for re-approval); →Active/→Paused buttons return a clean 403 toast; drawer shows the "cần Lead/System Manager" hint based on scope role. Manager/Leader/SM: same form + working Activate/Pause (stamps approved_by/at, shown in table). Out-of-scope brand: not in dropdowns + server 403.

## 5. Overlap / priority behavior

Tier badge per row + live tier preview while editing (pure client mirror of the server's scoring). [Kiểm tra trùng/override] calls `check_rule_overlap` with the current form values and renders each related Active rule of the same brand+rule_code as: "sẽ BỊ rule mới override (rule mới cụ thể hơn)" / "sẽ OVERRIDE rule mới (rule kia cụ thể hơn)" / "cùng tầng — rule sửa gần nhất thắng", plus the priority legend. No overlap → "Không trùng rule Active nào."

## 6. States

Same patterns: loading row, empty "Không có dữ liệu...", 403 → `al-noaccess`, Guest → login redirect, error toasts with `_server_messages`. Lock checkbox disabled-state doubles as an inline "not applicable" state for non-severe rules.

## 7. Build/test results

Build-time M3 asserts (just executed, PASS): page ASCII-only/no-Jinja/balanced tags/marker; `ru-overlap`, `ru-tier-line`, banner, subnav, `check_rule_overlap` + `set_rule_status` wiring, literal "SKU &gt; Shop &gt; Platform &gt; Brand", **banner mentions DS1** (unescape check). One build bug caught by the ASCII assert itself (an escape level collapsed to a literal `→` — fixed, asserts green). M1/M2 asserts re-ran green; backend suite untouched (51/51 standing).

## 8. No-write confirmation

Workspace-only changes; app repo at `1a13fe9` (0 staged); page calls only M1 scoped endpoints; banner + hints state dry-run-only everywhere; no Omisell write, no stock/buffer, DS1 locked, FES-VN scheduler logic untouched.

---
**Gate:** M3 review → M4 (`/alerts/locks`: review queue with DRY-RUN banner + approve/reject modals + DS1 audit placeholders + pause manager; then integrated UAT script + the two deploy drops).
