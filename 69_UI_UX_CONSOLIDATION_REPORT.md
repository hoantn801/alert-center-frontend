# 69 - Alert Center UI/UX Consolidation - Implementation Plan & Report

Branch: `feat/alert-ui-ux-consolidation` (frontend). Backend support (if any):
`feat/alert-ui-support`. **Not deployed. Not merged.**

## 0. Inspection findings (done first, per working method)

- **Builder** `frontend/build_alert_pages.py` is the single source; 5 pages are
  generated artifacts (git-ignored). Structure: `SHELL` (homepage shell) +
  `_AC_NAV`/`ac_aside` (sidebar) + `subnav` (top tabs) + `SHARED_CSS` +
  `SHARED_JS` (the `window.AL` helper namespace) + `PAGE1..5` (content + JS) +
  assembly asserts.
- **`EC Field Description` DocType does NOT exist** in `ecentric_workspace`
  (no doctype JSON, no code references). Per spec section 17 this is a gate:
  creating a DocType is a schema change requiring owner approval, and it cannot
  be "read" because there is nothing to read. **Decision:** implement the
  business-terminology layer as a self-contained frontend label/definition map
  now (spec section 4 minimum), structured with a single lookup so it can later
  be backed by `EC Field Description` via a small read-only API. The DocType +
  its read endpoint are **deferred** (owner decision; see section 8 below).
- **Rule codes are rendered raw** at: alerts table, alert detail (subtitle +
  KV), occurrence table, rules table. These are the points to map to business
  labels (raw code retained in tooltip/technical detail).
- **Navigation today**: sidebar `Dashboard, Alerts(#al-alert-list), Price Setup,
  Rules, Locks | Automation Pauses(->locks), Integration Health | Back to
  Workspace`; top subnav `Dashboard & Alerts, Policies, Rules, Locks,
  Integration Health`. Routes: `/alerts`, `/alerts/policies`, `/alerts/rules`,
  `/alerts/locks`, `/alerts/integration-health` (5 Web Pages - fixed).
- **Overview already** (prior batch) has: 6 clickable KPI cards incl. Setup
  Issues, simplified default filters + Advanced + active chips + date preset,
  hourly chart + 14-day trend, brand/platform/rule bars, top-SKU, aging, and the
  full alerts table at the bottom (`#al-alert-list`, hash-nav toggles sidebar).

## 1. Canonical business-label map (spec section 4)

| Code | Vietnamese label |
| --- | --- |
| below_min | Thap hon gia toi thieu |
| above_high | Cao hon nguong canh bao |
| severe_price_drop | Giam gia nghiem trong |
| possible_missing_zero | Nghi thieu so 0 |
| missing_brand_mapping | Thieu cau hinh brand |
| missing_policy | Thieu Price Policy |
| ingestion_api_failed | Loi dong bo du lieu |
| missing_integration_credential | Thieu thong tin ket noi |
| stock_lock_api_failed | Loi xu ly Stock Safety |

(Stored ASCII-escaped in the builder; raw code shown only in tooltip / technical
detail. Unknown codes fall back to the raw code.)

## 2. Navigation target (spec sections 2 + 11)

Alert Center: **Overview, Alerts, Price Setup, Rules, Stock Safety** ;
Operations: **Integration Health** ; Workspace: **Back to Workspace**. Remove
the standalone **Automation Pauses** (it lives inside Stock Safety). Routes are
unchanged (`/alerts/locks` is now labelled "Stock Safety"); Overview vs Alerts
share `/alerts` with the existing hash subview (`#al-alert-list`).

## 3. Implemented + validated THIS session (commit group 1)

- **Terminology layer**: `RULE_LABELS` map + `ruleLabel(code)` added to
  `window.AL`; applied at all rule-code render points (alerts table, alert
  detail subtitle + KV, occurrence table, rules table) with the raw code kept in
  a `title` tooltip / Technical section.
- **Navigation restructure**: `_AC_NAV` -> Overview / Alerts / Price Setup /
  Rules / Stock Safety | Integration Health | Back to Workspace; Automation
  Pauses standalone removed; nav-active gate + `subnav` updated to match.
- **Stock Safety rename**: page title "Stock Safety Actions", nav + subnav
  "Stock Safety", simulation banner retained; Automation Pauses remains as a
  panel on that page.
- Builder self-asserts updated (Overview / Stock Safety / ruleLabel / no
  Automation-Pauses-standalone) and the full build re-validated.

## 3b. Implemented + validated - increment 2 (Overview/Alerts + EC FD adapter)

- **EC Field Description adapter** (`SHARED_JS`): `FIELD_HELP` cache +
  `loadFieldHelp()` does ONE defensive `frappe.client.get_list` of the custom
  DocType (called once per page in `initScope`); records keyed
  **`alert.rule.<code>`** with `label`/`description` OVERRIDE the built-in rule
  labels, else the static fallback is used. Read failures (missing DocType /
  fields / permission) are silent. **Metadata contract to maintain in the ERP:**
  DocType `EC Field Description`, one record per key; fieldnames used =
  `name` (the key, e.g. `alert.rule.below_min`), `label`, `description`. Confirm
  these fieldnames on the live site and I will widen the adapter to drive form
  tooltips for Price Setup / Rules.
- **Overview vs Alerts subviews on `/alerts`** (no 6th route): the full work
  queue (`#al-alert-list`) is **hidden on Overview** and shown only in the
  Alerts subview (deep-link `#al-alert-list`, browser refresh stable). Overview
  shows the insight grid + a new **Recent Critical Alerts** panel (5 rows,
  business labels) + **"View all alerts"**; sidebar + subnav active states sync;
  clicking a KPI drills into the Alerts subview with the filter applied.
- **Business labels in the rule distribution** bars (via `ruleLabel`).

Validated: builder `py_compile` + 5-page build + asserts PASS; per page no
duplicate IDs, ASCII-clean, `node --check` clean; Overview/Alerts elements all
present in generated output.

## 3c. Implemented + validated - increment 3 (Overview redesign + Integration Health)

**Overview (P1):** KPI strip reordered to Open / Critical / Warning / Pending
Stock Safety / Setup Issues with **Resolved demoted to a smaller secondary**
card (`kpi-sec`); default filter bar now shows Period / Brand / Platform /
Severity / Search (+ Apply / More / Clear), Status moved to Advanced; the
standalone **hourly chart panel removed** and replaced by **one full-width main
Alert Trend card** (New/Resolved/Ignored, period basis labelled); the three
dimension charts consolidated into **one "Alert Distribution" card** (Brand /
Platform / Rule side-by-side, rule business labels) plus Top SKUs + Aging; the
new trend toggles with the Overview subview. All JS render IDs preserved (no JS
behaviour change; `renderHourly` already no-ops when its element is absent).

**Integration Health (P6):** frontend **"Not Configured"** classification
(`ihStatus`: a brand with no integration settings reads Not Configured, not
Blocked) applied to the status cell AND the KPI counts (Ready / Not Configured /
Warning-Delayed / Blocked); cryptic headers **BA/BIS/CRED/ON/DS1/Sched relabelled
to Brand Setup / Integration / Credential / Enabled / Stock Safety / Scheduler**
with the abbreviations kept in `title` tooltips. No backend change (payload
already exposes `bis_exists`/`status`). No secret leakage.

Validated: `py_compile` + 5-page build + asserts PASS; per page no duplicate IDs,
ASCII-clean, `node --check` clean; Overview distribution/main-trend/secondary-KPI
and IH Not-Configured/friendly-headers confirmed in generated output.

## 3d. Increment 4 - four operational pages (bounded changes, validated)

Each remaining page received a real, validated change (some simplified per the
"continue even if simplified" rule); deeper reworks still listed in section 4.

- **Alerts (P2):** Operational / Setup **mode switch** in the work-queue header
  (segmented control), reusing the existing setup-only API path; switching
  updates table + KPI/chip state; business rule labels already applied. *Deferred:
  full column re-order and the sectioned detail drawer.*
- **Price Setup (P3):** `polScope()` helper derives and shows a **scope-source
  badge** (SKU-specific / Shop Policy / Platform Policy / Brand fallback) with a
  priority tooltip, in the policy table. Documented metadata keys for EC Field
  Description (price_setup.*). *Deferred: drawer Advanced-collapse + live scope
  preview.*
- **Rules (P4):** scope-tier badges relabelled to **business override semantics**
  (Brand Default / Platform Override / Shop Override / SKU Exception, raw tier in
  tooltip); priority shown in the panel title. *Deferred: Brand-Defaults vs
  Exceptions card grouping.*
- **Stock Safety (P5):** prominent **Simulation Mode** banner + product copy
  ("no real inventory update is sent..."); DRY-RUN marker retained. *Deferred:
  Pending/History/Pauses tabs + compact KPI strip.*
- **Integration Health wording:** ambiguous `Enabled` header renamed to
  **`Pull Enabled`** (the BIS pull flag).

Validated: `py_compile` + 5-page build + asserts PASS; per page 0 duplicate IDs,
ASCII-clean, `node --check` clean, **no dead buttons** (every new control bound).

## 4. Deferred (designed, NOT yet built - honest status)

These are specified, lower-priority-for-tonight, or gated; each is a clean next
commit and is **not** claimed as complete:

- **Overview**: consolidate hourly + 14-day into one period-aware trend (New /
  Resolved / Critical); replace 6 insight blocks with Alert Distribution
  (3 mini-donuts), Top SKUs, Aging, Recent Critical (5 rows); move the full
  alerts table out of Overview into the Alerts subview.
- **Overview/Alerts as distinct subviews** on `/alerts` (build on the existing
  hash mechanism so the full work-queue is not buried under the dashboard).
- **Alerts**: Operational vs Setup view switch in-header; search across
  SKU/product/shop/title (needs backend `list_alerts` search-field support -
  currently SKU-only); column re-prioritisation; detail-drawer restructure.
- **Price Setup**: drawer simplification (Scope / Product / Prices / Thresholds
  + collapsed Advanced); scope-source labels (SKU / Shop / Platform / Brand
  fallback) instead of a bare badge.
- **Rules**: brand-default cards (Below minimum / Severe drop / Above benchmark)
  + Exceptions/overrides + priority/resolution preview. **Inspection needed**:
  thresholds currently live on EC Price Policy AND EC Alert Rule; the
  brand-default/exception model maps onto the existing scope hierarchy but a full
  move would be a schema change - prefer UI framing over moving fields; report
  the architectural gap.
- **Integration Health**: status terminology (Not Configured vs Blocked - needs
  `brand_readiness.derive()` change, backend) + business-friendly column
  relabel (Brand Setup / Integration Settings / Credential / Scheduler / Stock
  Safety / Last Sync / Breaker / Next Action) with abbreviations in tooltips.
- **EC Field Description**: owner to create the DocType; suggested keys =
  `alert.rule.<code>`, `price_setup.<field>`, `rules.<field>`,
  `stock_safety.<field>`, `integration_health.<column>`. Frontend will batch-read
  via a new read-only API (existing permission scope) once available. Until then
  the frontend label/definition map is the source.

## 5. Validation (this session)

Builder `py_compile` **PASS**; build of all 5 pages **PASS**; builder
self-asserts **PASS** (incl. new: `>Overview<`, `>Stock Safety<`,
`>Automation Pauses<` absent, `RULE_LABELS`/`ruleCell` present). Per page:
ASCII-safe (0 non-ASCII), no duplicate IDs, `node --check` clean, only the one
inherited shell logout `onclick`. Generated sizes ~65-88 KB. Confirmed: business
labels render via `ruleCell` (raw code in `title` tooltip); sidebar + subnav show
Overview / Alerts / Price Setup / Rules / Stock Safety / Integration Health;
the Automation-Pauses *panel* remains on the Stock Safety page (its create/cancel
flow untouched) while the standalone sidebar item is gone; page title is
"Stock Safety Actions" with the simulation/DRY-RUN banner retained. Frontend-only;
no backend change; no deploy; DS1 gate untouched.

Note: validation was run against a faithful reconstruction because the sandbox
file mount truncates the ~140 KB builder on read; the host file is complete and
correct (every edit verified) - the owner's Windows build is authoritative.

## 5a. Git (owner runs on Windows - NOT done from sandbox)

The generated builder is too large for the sandbox mount to read intact, so
staging/committing here would risk committing a TRUNCATED `build_alert_pages.py`.
Therefore git was NOT run in the sandbox. Exact commands (run on the Windows host
where files are intact; remote already configured per repo):

```powershell
cd C:\dev\ALERT_CENTER
git checkout main && git pull
git checkout -b feat/alert-ui-ux-consolidation
git add frontend\build_alert_pages.py 69_UI_UX_CONSOLIDATION_REPORT.md README.md RUNBOOK_ALERT_CENTER.md
git status            # confirm NO generated frontend\*.html staged, no secrets
git commit -m "Alert UI/UX: business-label terminology layer + nav restructure + Stock Safety rename"
git push -u origin feat/alert-ui-ux-consolidation
# rebuild generated pages locally (artifacts, git-ignored):
python frontend\build_alert_pages.py deploy\backups\home_20260608_154510\main_section_html.bak.html frontend
# DO NOT merge, DO NOT deploy.
```

## 6. Status

Local implemented (commit group 1), branch + commit commands prepared for the
owner (sandbox cannot authenticate a push). Deeper redesign deferred per above.

## 14. Stock Safety pass (2026-06-15) - locks page restructure

Scope: `/alerts/locks` (generated `alert_locks.html`) only. Backend untouched:
no schema, rule-evaluation, scope-priority, API or permission change; DS1 gate
stays closed; no real Omisell write / unlock / restore / reconciliation enabled.
Everything on the page remains DRY-RUN / simulation.

What changed (all in `frontend/build_alert_pages.py`, PAGE4 only):

- Page title is now **Stock Safety Actions**. A prominent **Simulation Mode**
  banner states no lock/buffer command is sent to Omisell (DS1 gate closed).
- Three internal tabs replace the old flat layout: **Pending Actions**,
  **Action History**, **Automation Pauses** - a segmented `al-modesw` tablist
  (`#ss-tabs` -> `#ss-tab-pending|history|pauses`) with `role="tablist"/"tab"`,
  `aria-selected`, and Enter/Space keyboard activation. Hash state
  `#stock-pending` / `#stock-history` / `#stock-pauses` is restored on load and
  on `hashchange` (`setStockTab` / `restoreTab`). Pending is the default.
  - Pending Actions: review queue filtered to `Pending Review`.
  - Action History: same table, terminal records (review filter cleared, title
    swaps to history).
  - Automation Pauses: the pauses panel (`#ss-pauses`) moved fully inside this
    subview - Scheduled/Active/Expired/Cancelled states with status badges and a
    Cancel action only on Active pauses. It is NOT a global sidebar item (the
    module-shell assert enforces no `Automation Pauses</a>` nav anchor on any
    page; the in-page tab is a `<button>`, allowed).
- Compact, clickable KPI strip (`#ss-kpis`, `role="button"`, `tabindex="0"`,
  Enter/Space): Pending / Approved / Rejected / Skipped-Failed. Clicking a card
  jumps to the right tab and sets the review filter (`data-ss="tab|review"`).
- Sectioned detail drawer (`#lk-d-kv`, built via `kvdl()`): **Trigger & Evidence**
  / **Requested Action** / a prominent **Simulation State** box (`al-action-box`)
  / **Review Decision** / **Technical Details** collapsed in `<details class=
  "al-tech">`. Approve/Reject enable logic and required-note validation preserved.
- Loading / empty / error states kept on both tables; business labels via the
  existing terminology layer; ASCII-safe embedding; generated HTML git-ignored.

Validation (real full assert set, run against a faithful reconstruction because
the sandbox mount truncates the ~165 KB builder; host file is complete):
`py_compile` OK; 5-page build OK; **all M2c/M2/M2b/M3/M4/G1/module-shell asserts
pass** (M4 extended with: Simulation Mode banner, `#ss-tabs`/`#ss-tab-*`,
`#ss-queue`/`#ss-pauses`/`#ss-kpis`, `setStockTab`/`restoreTab`, hash tokens,
grouped drawer sections + collapsed `al-tech`, and a refined "no standalone
Automation Pauses nav" check). `node --check` OK on the combined page JS;
duplicate-id audit NONE; locks page non-ASCII bytes 0; style/script tag balance
OK; action table header/row cells 12/12 and pauses table 10/10 aligned; no
merge-conflict markers; secret scan clean; `frontend/alert_locks.html` confirmed
git-ignored; only `build_alert_pages.py` shows as modified.

Commit (owner runs on Windows; do NOT merge, do NOT deploy):

```powershell
cd C:\dev\ALERT_CENTER
git add frontend\build_alert_pages.py 69_UI_UX_CONSOLIDATION_REPORT.md
git status            # confirm NO generated frontend\*.html staged, no secrets
git commit -m "Alert UI: restructure Stock Safety actions and pauses"
git push
# rebuild generated pages locally (artifacts, git-ignored):
python -m py_compile frontend\build_alert_pages.py
python frontend\build_alert_pages.py deploy\backups\home_20260608_154510\main_section_html.bak.html frontend
# DO NOT merge, DO NOT deploy.
```

## 15. Release-candidate polish pass (2026-06-15) - final report

This pass is the final polish + release-candidate validation. No backend schema,
rule-evaluation, scope-priority, API, or permission change; DS1 gate stays closed;
no real Omisell write / unlock / restore / reconciliation enabled. All edits are
in the single builder `frontend/build_alert_pages.py`; generated HTML stays
git-ignored. NOT merged, NOT deployed.

### 15.1 Final page-by-page feature summary

Overview (`/alerts`, `alert_center.html`): compact KPI strip with interactive
drill-down, one consolidated trend card (`ov-trend`), Alert Distribution card,
Recent Critical list, Overview/Alerts subview split via hash, Operational/Setup
mode switch. The obsolete standalone hourly panel stays removed (negative assert).
Rule filter options now show business labels (raw `rule_code` kept as the option
value and in a tooltip).

Alerts work queue (subview of `/alerts`): 14-column table, bulk actions,
occurrence column + occurrences drawer with CSV export, sectioned detail drawer,
business rule labels via `ruleCell`/`RULE_LABELS`.

Price Setup (`/alerts/policies`, `alert_policies.html`): grouped policy drawer
(Scope / Product / Prices / Alert Behavior + collapsed Advanced), live scope
preview, EC Field Description help icons. NEW this pass: a compact coverage
summary (Covered SKUs / Missing SKUs / Coverage %) consistent with the Overview
KPI cards, basis labelled "distinct ordered SKUs, last 30 days", an info tooltip
with the full definition, and a clickable Missing card that opens the existing
missing-policy view. The per-brand missing chips remain as a collapsed drill-down
(`pl-cov-bybrand`) so they no longer dominate the page.

Rules (`/alerts/rules`, `alert_rules.html`): Brand Defaults grouped by brand +
Advanced Exceptions (`<details>`). NEW this pass: the rule editor keeps Scope /
Trigger / Action visible and moves effective dates, status line and the
overlap-check tool into an Advanced `<details>` that is collapsed by default
(`ru-adv-sec`, re-collapsed every time the drawer opens). Nine EC Field
Description help icons (static fallback, live override when the doctype is
present) for rule type, threshold, action, recommend Stock Safety, scope
priority, Brand Default, Platform Override, Shop Override, SKU Exception. Rule
dropdowns relabelled to business labels (values unchanged).

Stock Safety (`/alerts/locks`, `alert_locks.html`): three internal tabs (Pending
Actions / Action History / Automation Pauses) with hash state, compact clickable
KPI strip, sectioned detail drawer. NEW this pass: truthful outcome labelling -
every record reads as a simulation (see 15.5); the page never presents "Live".

Integration Health (`/alerts/integration-health`, `alert_health.html`): friendly
column headers, read-only diagnostics, no `set-config` write, no `pull_recent`
trigger.

### 15.2 Exact files changed

This pass: `frontend/build_alert_pages.py` (builder) and this report
`69_UI_UX_CONSOLIDATION_REPORT.md`. Nothing else. The five generated
`frontend/alert_*.html` are build artifacts and remain git-ignored (not staged).
No backend file under `ecentric_workspace/` was modified.

### 15.3 Commit hashes in branch order

Base / merge-base with `main`: `d603febcb47c`. Branch `feat/alert-ui-ux-consolidation`,
oldest -> newest:

1. `802c1a0` Alert UI: redesign overview and clarify operational pages
2. `569bc70` Alert UI: align builder assertions with consolidated overview
3. `7cf745f` Alert UI: reorder alerts queue and structure detail drawer
4. `fb7ff32` Alert UI: simplify Price Setup policy workflow
5. `cf928f4` Alert UI: simplify Rules defaults and exceptions
6. `dfcd32e` Alert UI: restructure Stock Safety actions and pauses  (current HEAD)
7. *(pending - this pass)* proposed `Alert UI: release-candidate polish (coverage, rules help, truthful stock labels)` - NOT yet committed; the sandbox cannot stage the large builder safely, so the owner commits it on Windows (see 15.8).

### 15.4 Full validation output (real full assert set)

Run against a faithful reconstruction of the builder (the sandbox file mount
truncates the ~175 KB builder on read; the host file is complete - every edit was
applied to the host and replayed deterministically via unique anchors, then the
REAL assert block was executed):

```
py_compile OK
[OK] built out/alert_center.html (94777 bytes)
[OK] built out/alert_policies.html (96999 bytes)
[OK] built out/alert_rules.html (80528 bytes)
[OK] built out/alert_locks.html (76703 bytes)
[OK] built out/alert_health.html (69680 bytes)
[OK] M2c policy-drawer asserts pass
[OK] M2/M2b dashboard asserts pass     (+ RULE_LABELS / ruleCell / relabelRuleOptions)
[OK] M3 asserts pass                   (+ ru-adv-sec collapsed, >=9 rules.* help icons, tier legend)
[OK] M4 asserts pass                   (+ ssStatusBadge/RV_LABEL/SS_LABEL, no >Live<, simulation labels)
[OK] G1 integration-health asserts pass
[OK] module-shell asserts pass         (no standalone Automation Pauses nav anchor)
[OK] UI/UX consolidation nav + terminology asserts pass
```

Added assertions this pass: Price Setup coverage metrics (`pl-cov-kpis`,
`pl-cov-covered/missing/pct`, `data-cov="missing"`, `loadCoverageSummary`,
`data-help="price_setup.coverage"`, 30-day ordered-SKU basis text,
`pl-cov-bybrand` drill-down); Rules Advanced collapsed-by-default + the nine
help-icon topics + business-label markers; Stock Safety truthful-label helpers +
negative `">Live<" not in p4`; Overview business-terminology markers; (kept)
negative asserts for the stale hourly panel and the standalone Automation Pauses
nav.

Other checks: `node --check` OK on all five pages' inline JS; duplicate-id audit
NONE on all five; dead-button audit NONE unbound (policies/rules/locks); delegated
selector/action handlers verified (e.g. `data-cov="missing"`); table header/row
alignment locks 12/12 and pauses 10/10; non-ASCII bytes 0 on all five; style/script
tag balance OK; no merge-conflict markers; secret scan clean; all five
`frontend/alert_*.html` confirmed git-ignored; `git status` shows only the builder
and this report modified.

### 15.5 Exact Stock Safety status mapping (truthfulness)

Source of truth: `EC Alert Action` (`action_type = "Stock Safety Lock"`),
`api_actions.list_actions` / `review_action`. `review_action` performs NO Omisell
call (DS1 gate closed) - Approve only stamps the audit, Reject cancels.

Tab derivation (frontend filter on the existing `review_status` field):

| Tab | Filter applied | Records shown |
|---|---|---|
| Pending Actions | `review_status = "Pending Review"` | awaiting review |
| Action History | review filter cleared | terminal: Approved / Rejected |
| Automation Pauses | (separate `EC Automation Pause` list) | Scheduled/Active/Expired/Cancelled |

Lifecycle (DS1-disabled, current):

| Event | `status` | `review_status` |
|---|---|---|
| Created | Dry Run / Pending / Skipped | Pending Review |
| Approve | unchanged (stays Dry Run) - NO Omisell write | Approved |
| Reject (note required) | Cancelled | Rejected |

Truthful visible labels (raw enum kept in the `title` tooltip):

| Raw `review_status` | Shown as |
|---|---|
| Pending Review | "Cho duyet" (Pending review) |
| Approved | "Duyet cho mo phong" (Approved for simulation) |
| Rejected | "Tu choi" (Rejected) |

| Raw `status` | Shown as (outcome) |
|---|---|
| Dry Run | "Mo phong" (Simulation) |
| Success | "Mo phong hoan tat" (Simulation completed) |
| Pending | "Cho xu ly" (Pending) |
| Processing | "Dang xu ly" (Processing) |
| Skipped | "Bo qua" (Skipped) |
| Failed | "Loi (mo phong)" (Failed - simulation) |
| Cancelled | "Da huy" (Cancelled) |

"Live" is never shown. It is reserved for a future real executor and only when
backend data explicitly proves a live write occurred - no such field/proof exists
today, so every current record reads as Simulation. A negative assert
(`">Live<" not in p4`) guards this.

### 15.6 Genuine remaining limitations

- The Price Setup coverage summary is an aggregate across the user's scoped
  brands computed by calling the canonical per-brand `coverage_report`
  (`api_sku_catalog.policy_missing_skus`) once per brand in parallel. For a
  global supervisor with many brands this is N small reads on page load. It is
  correct and uses no new backend, but a single aggregate endpoint would be more
  efficient if brand counts grow large.
- Coverage % shows `n/a` when a brand has no orders in the 30-day window (no
  fabricated denominator). This is intentional but can read as "missing data" to
  a first-time user; the info tooltip explains it.
- EC Field Description help text is dynamic only if the (DB-only) doctype is
  present and readable; otherwise the static fallback copy is shown. This is by
  design but means help text can differ between environments.
- Main data tables scroll horizontally inside their wrapper but do not have a
  sticky header (only the occurrences table does); adding sticky headers would
  need a max-height scroll container and was judged out of scope for a low-risk
  polish pass.
- Validation is run against a reconstruction because the sandbox mount truncates
  the builder; the owner's Windows build remains authoritative.

### 15.7 Local preview (owner, Windows - artifacts are git-ignored)

```powershell
cd C:\dev\ALERT_CENTER
python -m py_compile frontend\build_alert_pages.py
python frontend\build_alert_pages.py deploy\backups\home_20260608_154510\main_section_html.bak.html frontend
# open the generated files in a browser to eyeball at 1366px and 1920px:
start frontend\alert_policies.html
start frontend\alert_rules.html
start frontend\alert_locks.html
# (live data requires the pages served by Frappe on the bench site)
```

### 15.8 Proposed commit + push (owner runs on Windows; do NOT merge/deploy)

```powershell
cd C:\dev\ALERT_CENTER
git add frontend\build_alert_pages.py 69_UI_UX_CONSOLIDATION_REPORT.md
git status   # confirm NO generated frontend\*.html staged, no secrets
git commit -m "Alert UI: release-candidate polish (coverage, rules help, truthful stock labels)"
git push
```

### 15.9 Proposed deploy (LATER, only after explicit approval - not now)

```powershell
# On the bench host, after PR review + approval (NOT part of this pass):
cd C:\dev\ALERT_CENTER
python frontend\build_alert_pages.py deploy\backups\home_20260608_154510\main_section_html.bak.html frontend
# then publish the 5 Web Pages via the project's existing deploy script:
#   deploy\deploy_alert_center.ps1   (or the documented Web Page import step)
# verify:  deploy\verify_alert_center_postdeploy.ps1
```

### 15.10 Rollback

```powershell
# Source rollback (un-commit this pass, keep history):
cd C:\dev\ALERT_CENTER
git revert <new-commit-hash>            # creates an inverse commit
# or hard reset the branch to the prior HEAD if not yet pushed/shared:
git reset --hard dfcd32e
python frontend\build_alert_pages.py deploy\backups\home_20260608_154510\main_section_html.bak.html frontend
# Deployed-page rollback (only if ever deployed): restore the previous Web Page
# HTML from deploy\backups\ per RUNBOOK_ALERT_CENTER.md.
```

### 15.11 Status

- committed: NO (this pass is staged in the working tree only; commands in 15.8)
- pushed: NO
- merged: NO
- deployed: NO

Prior passes (commits 1-6 in 15.3) are committed and pushed on the branch; they
are NOT merged and NOT deployed.
