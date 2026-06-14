# ALERT_CENTER — Marketplace Price Compliance / Alert Center MVP

New initiative folder (created 2026-06-06). Scope: central Alert Center (`/alerts`) for the internal ERP on `team.ecentric.vn`, MVP = Price Compliance / Price Anomaly alerts from Omisell order data, with brand-aware Stock Safety Lock action queue.

---

## Build, Deploy & Source Control (MVP handover, 2026-06-15)

This repo holds the **page builder, its visual source snapshot, and deploy/verify
scripts** for the five Alert Center Web Pages. Backend Python lives in the
separate app repo `ecentric_workspace` (module `ecentric_workspace.alerts`).

Routes: `/alerts`, `/alerts/policies`, `/alerts/rules`, `/alerts/locks`,
`/alerts/integration-health`.

### Source of truth

| Concern | File |
| --- | --- |
| Page generator (the ONLY hand-edited frontend file) | `frontend/build_alert_pages.py` |
| Visual source of truth (ERP Homepage shell) | `deploy/backups/home_20260608_154510/main_section_html.bak.html` |
| Deploy (all pages or one route) | `deploy/deploy_alert_pages.ps1` |
| Rollback | `deploy/rollback_alert_pages.ps1` |
| Post-deploy smoke (read-only) | `deploy/verify_alert_center_postdeploy.ps1` |
| 24h brand health monitor (read-only) | `deploy/monitor_brands.ps1` |
| Deploy + rollback runbook | `RUNBOOK_ALERT_CENTER.md` |

### Generated outputs policy

The five `frontend/*.html` files are **deterministic build artifacts, NOT
source**. They are git-ignored and rebuilt from the builder + home snapshot.
Never hand-edit them. A fresh clone MUST run the builder before deploying.

### Build

```powershell
cd C:\dev\ALERT_CENTER
python -m py_compile frontend\build_alert_pages.py
python frontend\build_alert_pages.py `
  deploy\backups\home_20260608_154510\main_section_html.bak.html `
  frontend
```

The builder emits the 5 pages and runs embedded self-assertions (ASCII-safe, no
Jinja leak, balanced `<style>`/`<script>`, required selector markers). Non-zero
exit = failed assertion -> do not deploy.

### Deploy + verify

```powershell
.\deploy\deploy_alert_pages.ps1                       # or  -Only alert-policies
bench --site team.ecentric.vn clear-cache
.\deploy\verify_alert_center_postdeploy.ps1           # expect all [OK]
.\deploy\monitor_brands.ps1 -Brands FES-VN,LOF-VN
```

Smoke credentials come from `EC_API_TOKEN` (`key:secret`) or `-CredCsv` - never
hardcoded, never committed.

### Rollback

`deploy\rollback_alert_pages.ps1` takes the pages offline (content preserved);
to restore previous CONTENT, re-deploy the prior build or the backup
`deploy\backups\<route>_<timestamp>\web_page.json`. Frontend rollback is
content-only; no data/audit history is touched. Backend rollback is a git revert
of the app repo (never a hard delete; patches p004/p005 are forward-only). Full
steps + success signals in `RUNBOOK_ALERT_CENTER.md`.

### Prerequisites

- Windows PowerShell 5+ with network access to the site.
- Python 3.10+ on PATH (builder is stdlib-only).
- Frappe API token for a scoped account, via `EC_API_TOKEN` or an out-of-repo CSV.
- App `ecentric_workspace` deployed + migrated on the target site.

### Putting this folder under Git (owner runs once on Windows)

No remote is assumed. `.gitignore` already excludes secrets, the keys CSV,
`deploy/backups/` (except the home snapshot), runtime probe JSONs, and generated
HTML.

```powershell
cd C:\dev\ALERT_CENTER
git init
git add .gitignore README.md RUNBOOK_ALERT_CENTER.md frontend\build_alert_pages.py deploy\*.ps1
git add deploy\backups\home_20260608_154510\main_section_html.bak.html
git add *.md                              # phase docs (project history)
git status                                # confirm NO secrets / no frontend\*.html / no backups
git commit -m "Alert Center MVP: builder, deploy/verify scripts, docs, snapshot"
# add a remote ONLY when the owner provides one:
# git remote add origin <url>; git branch -M main; git push -u origin main
```

---

## Files

| File | Purpose |
|---|---|
| `00_PRECODE_REPORT.md` | Phase A deliverable — inspection + design. **§17 = binding approved decisions D1–D6** (no new roles, kam_owner field, Frappe Cloud deploy, dry-run only, reuse ERP UI). |
| `01_PHASE_B_PLAN.md` | Phase B implementation plan (schema + permission utils) + UI reference report (§8). Awaiting "go". |
| `OMISELL_API_CHECKLIST.md` | 15-item API requirement checklist to send to Omisell (D3). |
| `02_PHASE_B_REPORT.md` | Phase B implementation report (accepted as local-complete) + §10 git/OneDrive incident. |
| `03_DEPLOY_CHECKLIST.md` | Frappe Cloud push/deploy/verify checklist + git housekeeping commands. Nothing executed yet. |
| `04_PHASE_C_DESIGN.md` | Phase C design note + binding decisions C1/C2 (§0). |
| `05_PHASE_C_REPORT.md` | Phase C implementation report (local-only, commit `08cfdaa`) + Phase B verification gate (§0, residual probes R1/R2). |

## Status

- **Phase A: DONE + APPROVED 2026-06-06 (with corrections → report §17).**
- **Phase B: PRODUCTION-COMPLETE 2026-06-07 (user-verified).** Deployed via Frappe Cloud from commit `b16d30b`. Verified: 8 DocTypes live, `Brand Approver.kam_owner` exists, no Omisell API / stock-lock execution, `/alerts` correctly absent. Docs: `02_PHASE_B_REPORT.md`, `03_DEPLOY_CHECKLIST.md`.
- **Phase C: PRODUCTION-COMPLETE 2026-06-07 (all probes passed — `verify_phase_c_probes.ps1`).** Live: rules engine (C1/C2/C3), idempotent mock ingestion, dry-run action queue, 2 SM-only endpoints. Smoke records SMOKE-C-001 / EC-AL-000568 kept for audit.
- **Phase E: PRODUCTION-COMPLETE 2026-06-08 (user-verified: probes + SM smoke + non-SM 403 matrix + KAM scoped UAT; kam_owner x7 filled).** Scheduler intentionally OFF (`ec_alerts_scheduler_disabled=1`) until separately approved. Docs: `08`–`10`.
- **Phase D: IMPLEMENTED LOCALLY 2026-06-08 — commit `04d4c68` on `alerts-phase-d` (read-only ingestion, manual T0–T3, no scheduler). NOT pushed/deployed; zero real Omisell calls. Docs: `12`–`14`. Stock buffer write stays locked by DS1 (`11_STOCK_LOCK_BUFFER_DESIGN.md`).**

## Ground truth used

- Live snapshot `MSOSOPOREC/phase8/snapshots/20260605_230007/live_state/` (2026-06-05 23:00).
- Approval-module snapshot `20260527_120657_approval_check/` (Brand Approver / Global Role schemas + records).
- Local app repo `ecentric_workspace/` (PM v2 module pattern).
