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

## 16. Visual-polish pass (2026-06-15) - donut + Price Setup actions

Focused visual polish from owner review. Only `frontend/build_alert_pages.py`
changed; backend untouched (no schema / rule / scope / API / permission change);
DS1 stays closed; generated HTML git-ignored. Pages NOT in scope (Alerts, Rules
structure, Stock Safety, Integration Health) are unchanged except for the shared
info-icon spacing. NOT merged, NOT deployed.

### 16.1 Concentric-donut Alert Distribution (Overview)

The three horizontal bar columns (`al-dist3`: Brand / Platform / Rule) are
replaced by one concentric-donut SVG in the same full-width card, drawn with the
existing inline-SVG approach (no external chart library).

Implementation details:

- Structure: a 200x200 `<svg id="ov-donut">` with three rings - outer = Brand,
  middle = Platform, inner = Rule - plus a centre `<circle>` + `<text
  id="ov-donut-total">` showing the total alert count, and an HTML legend
  (`#ov-donut-legend`) on the right grouped by dimension with category name,
  count and percentage.
- Data: one `api_dashboard.by_dimension` read per dimension (brand / platform /
  rule_code), fetched together via `Promise.all`. The denominator for ALL three
  rings is the SAME total = sum of the brand-dimension counts (= total alerts in
  the window), so every ring's percentages are comparable. Each ring shows the
  Top 3 categories by count plus an aggregated "Other" segment
  (`Other = total - sum(top3)`), so a ring is never more than four segments.
- Labels: Rule segments use the business label (`A.ruleLabel`) with the raw code
  only in the tooltip - no raw snake_case. "(none)" is shown for empty keys.
- Geometry: annular sectors via a small `donutArc(cx,cy,rOuter,rInner,a0,a1)`
  path generator (two arcs + two radial lines), starting at 12 o'clock, clockwise.
- Colour: a single 4-step navy ramp (`#27406a / #4f6f9f / #86a0c4 / #c8d2e0`,
  Other = lightest) - four colours total across the whole chart, deliberately not
  matching the reference image, readable contrast.
- Interaction: every segment AND every legend row is `tabindex="0"`
  `role="button"` with an `aria-label` and an SVG `<title>` carrying "dimension,
  category, count, percentage". Click (or Enter/Space) on a clickable segment
  applies the matching dashboard filter (`f-brand` / `f-platform` /
  `f-rule_code`, raw value) and calls `reload()` so the whole Overview refilters;
  "Other"/"(none)" segments are inert (`data-noclick`). Handlers are delegated on
  the SVG and the legend (`donutDelegate` / `donutKey` -> `donutClick`).
- Layout: donut + legend in a flex wrap; the card stays full-width above Top SKU
  and Aging, compact (210px donut) and centres the donut below 1100px so it stays
  readable at 1366px.
- Builder asserts added: `id="ov-donut"`, `id="ov-donut-legend"`,
  `id="ov-donut-total"`, the three ring defs (`dim:"brand"/"platform"/"rule"`),
  `loadDonut` / `renderDonut` / `donutClick` / `donutArc`, and `data-dim="`; the
  obsolete `al-dist3` / `dash-brand` / `dash-platform` / `dash-rule` ids were
  removed from the page-1 assert list.

### 16.2 Info-icon spacing (Price Setup + Rules, shared)

The shared `.al-help-i` rule was tuned: `margin-left:7px` (was 4px), `font-size:12px`
(slightly smaller/subtler), default `color:var(--gray-400)` (muted neutral),
`display:inline-flex; align-items:center; line-height:1` (vertically centred with
the label), `transition:color .15s`, and a clearer hover/focus state (navy +
focus ring). Because the class is shared, spacing is now consistent across every
Price Setup and Rules label. Tooltip behaviour and the EC Field Description
adapter are unchanged.

### 16.3 Price Setup contextual lifecycle footer + status badge

The footer no longer shows Save + Active + Paused + Draft at once. It now shows at
most two lifecycle buttons chosen by the record's current status, plus a status
badge next to the drawer title (`#pl-d-status`, `A.polBadge`). `refreshFooter()`
(invoked from `openDrawer` and on brand change via `applyCaps`) sets the labels,
visibility and permission-driven `disabled` state; after a successful transition
the drawer closes and the list reloads, so reopening reflects the new status.

Exact behaviour by status:

| Status | Primary (id `pl-save`) | Secondary (id `pl-life`) | More menu (id `pl-st-draft`) |
|---|---|---|---|
| New / Draft | "Save" | "Activate" -> Active (needs can_activate) | hidden |
| Active | "Save Changes" | "Pause" -> Paused (needs can_manage) | "Set to Draft" -> Draft |
| Paused | "Save Changes" | "Resume" -> Active (needs can_activate) | "Set to Draft" -> Draft |

The standalone Draft button is removed from the footer; because returning to
Draft is a real backend transition (`set_policy_status('Draft')`), it lives under
a small "More" menu for Active/Paused records only. No arrow glyphs remain on any
lifecycle button. Backend APIs (`api_policies.save_policy`,
`api_policies.set_policy_status`), the Active-threshold validation warning, and
the `can_manage` / `can_activate` permission checks are all preserved; no new
status was invented. Builder asserts added: `#pl-d-status`, `#pl-life`,
`#pl-more`, `#pl-st-draft`, `refreshFooter`, `curStatus`, `set_policy_status`,
`function save()`; negatives for `#pl-st-active` / `#pl-st-paused` and for the
three `&#8594;` arrow labels.

### 16.4 Validation output

Run against a faithful reconstruction (the sandbox mount truncates the now ~185 KB
builder; the host file is complete - every edit applied to the host and the
tail-assert edits replayed deterministically via unique anchors, then the REAL
assert block executed):

```
py_compile OK
[OK] built out/alert_center.html (100977 bytes)
[OK] built out/alert_policies.html (100198 bytes)
[OK] built out/alert_rules.html (82180 bytes)
[OK] built out/alert_locks.html (78355 bytes)
[OK] built out/alert_health.html (71332 bytes)
[OK] M2c policy-drawer asserts pass
[OK] M2/M2b dashboard asserts pass        (+ donut: ov-donut, 3 ring defs, total, legend, handlers)
[OK] M2d Price Setup contextual-footer asserts pass   (badge, pl-life, no arrows, no Active/Paused btns)
[OK] M3 asserts pass
[OK] M4 asserts pass
[OK] G1 integration-health asserts pass
[OK] module-shell asserts pass
[OK] UI/UX consolidation nav + terminology asserts pass
```

Other checks: `node --check` OK on all five pages' inline JS; duplicate-id audit
NONE on all five; dead-button audit NONE unbound (overview + policies, donut and
contextual-footer handlers verified); selector/action audit - donut click +
keyboard delegated (`donutDelegate`/`donutKey`), footer `pl-life`/`pl-more`/
`pl-st-draft` wired; non-ASCII bytes 0 on all five; style/script tag balance OK;
Price Setup table header/row alignment unchanged; no merge-conflict markers;
secret scan clean; no trailing whitespace in edited ranges; all five
`frontend/alert_*.html` confirmed git-ignored.

### 16.5 Preview guidance

The generated pages need Frappe + live data to show real distributions, so the
truest preview is on the bench site after rebuild. To eyeball layout/markup at
1366px and 1920px locally (artifacts are git-ignored):

```powershell
cd C:\dev\ALERT_CENTER
python -m py_compile frontend\build_alert_pages.py
python frontend\build_alert_pages.py deploy\backups\home_20260608_154510\main_section_html.bak.html frontend
start frontend\alert_center.html     # donut (needs the page served by Frappe for live data)
start frontend\alert_policies.html   # open a policy -> contextual footer + status badge
```

On the bench site: open `/alerts` (Overview) - the Alert Distribution card shows
the concentric donut; hover a segment for the dimension/category/count/percent
tooltip; click a segment to filter. Open `/alerts/policies`, edit a Draft vs an
Active vs a Paused policy to see the footer change (Save+Activate / Save
Changes+Pause / Save Changes+Resume) and the status badge by the title.

### 16.6 Commit + push (owner runs on Windows)

The sandbox git working tree reads a truncated copy of the large builder, so a
commit/stage from the sandbox would corrupt the file. As with the prior passes
(committed on Windows as `dfcd32e`, `f38c52a`), the owner runs:

```powershell
cd C:\dev\ALERT_CENTER
python -m py_compile frontend\build_alert_pages.py
git add frontend\build_alert_pages.py 69_UI_UX_CONSOLIDATION_REPORT.md
git status   # confirm NO generated frontend\*.html staged, no secrets
git commit -m "Alert UI: polish distribution chart and Price Setup actions"
git push     # same branch: feat/alert-ui-ux-consolidation
```

Commit hash: assigned by the owner's Windows commit (the prior pass is HEAD
`f38c52a`; this pass commits on top of it). NOT merged, NOT deployed.

### 16.7 Status

- committed: NO (staged in working tree; command in 16.6) · pushed: NO · merged: NO · deployed: NO

## 17. Adopt Apache ECharts for the charts (2026-06-15)

UAT rejected the hand-made SVG charts. This pass replaces them with Apache
ECharts: three independent mini-donuts + an interactive combo trend. No API,
permission, schema or scheduler change. NOT merged, NOT deployed.

### 17.1 ECharts version + asset source

- **Apache ECharts 5.5.1** (Apache-2.0), obtained from the npm registry
  (`npm pack echarts@5.5.1`, file `package/dist/echarts.min.js`, 1,030,855 bytes,
  md5 `ef12c5c63df2acdf59f8a86cf0317711`). The Apache license header is retained
  in the file. NOT a runtime CDN.

### 17.2 Asset path + loading method

- The minified file is vendored into the backend app as a static asset:
  `ecentric_workspace/ecentric_workspace/public/js/echarts.min.js`, which Frappe
  serves at **`/assets/ecentric_workspace/js/echarts.min.js`** after `bench build`.
- The Overview page (`/alerts` only) loads it with a single
  `<script src="/assets/ecentric_workspace/js/echarts.min.js"></script>` near the
  top of the page body, so `window.echarts` is defined before the page JS runs.
  The other four pages do not load it.
- Because this is a backend/app asset, it lives on its own branch
  **`feat/alert-ui-echarts-asset`** (the chart code stays on the frontend branch
  `feat/alert-ui-ux-consolidation`).

### 17.3 Three-donut configuration (Alert Distribution)

The three dimensions are independent, so they are three separate ECharts pie
(donut) instances side by side in one card — `#ec-brand`, `#ec-platform`,
`#ec-rule` — NOT one nested ring chart. Each donut:

- uses **its own dimension total** (sum of that dimension's rows) as denominator,
  drawn in the centre via an ECharts `graphic` text (total + "Total alert");
- shows **Top 3 + Other** (`top3()` aggregates the remainder into "Other");
- uses **business labels** (`A.ruleLabel` for rules; raw code only inside the
  tooltip) — no raw snake_case;
- has tooltip (name + value + percent), hover emphasis (scale + shadow), a compact
  scroll legend below, and renders cleanly when one category is 100%;
- uses a **separate coordinated palette** per dimension: Brand = blue/navy
  (`#1f3a5f…#c3d4e8`), Platform = teal/cyan (`#0f766e…#bfe9e6`), Rule =
  amber/coral (`#b45309…#f6dcb8`) — deliberately not one navy ramp;
- is click-to-filter (see 17.5) and has a per-chart table fallback (17.6).

### 17.4 Trend-series truthfulness

The combo chart (`#ec-trend`) is built ONLY from what `api_dashboard.trend`
truthfully returns per day: **New (bars), Resolved (line), Ignored (dashed
line)**. The backend provides no per-day severity split and no historical
backlog series, so **New Critical / New Warning stacked bars and an Open-Backlog
line are intentionally NOT shown** (they would be fabricated). A 7/14/30-day
preset (`#ov-trend-days`) re-queries `trend(days=…)`; axes are labelled, the
tooltip is axis-triggered, and the legend is clickable (ECharts default). If the
window allowed it, a small read-only aggregate could later add a truthful
severity split — but none was added here, keeping APIs unchanged.

### 17.5 Click / drill-down behaviour

- **Donut segment click** → sets the matching filter control (`f-brand` /
  `f-platform` / `f-rule_code`, raw value) and `reload()`s the whole Overview;
  "Other"/"(none)" segments are inert.
- **Trend point click** → sets `f-from = f-to = that day`, clears the preset,
  `reload()`s and switches to the Alerts subview (`#al-alert-list`) — i.e. opens
  Alerts filtered to that day.
- Legends are clickable to toggle series/segments (built-in).

### 17.6 Fallback behaviour

Every chart degrades gracefully when `window.echarts` is unavailable (asset not
yet deployed or failed to load): `ecOK()` gates rendering and each container has a
sibling `*-fb` element that shows a readable table (donuts: category / count / %;
trend: date / New / Resolved / Ignored) or an empty-state line when there is no
data. So the frontend branch is safe to ship/preview even before the asset branch
lands — the page shows tables until ECharts is served.

Lifecycle helpers (no leaks, no duplicate instances): `ecGet` (reuse-or-init a
single instance per container), `ecDispose`/`ecDisposeAll` (dispose before every
rerender), `ecResizeAll` (wired to `window` resize and re-run when returning to
the Overview subview). Each `renderDonut` / `loadTrend` disposes its instance
before `setOption(…, true)` (notMerge).

### 17.7 Removed obsolete custom-SVG code

Deleted: the concentric-donut path generator (`donutArc`, `donutTop3`,
`renderDonut`-SVG, `donutClick`, `donutDelegate`/`donutKey`), the `#ov-donut`
SVG + HTML legend, the hand-made sparse-bar trend (`#dash-trend`, `.al-trend*`,
`.al-col*`, `.al-dot`) and `renderHourly`, plus their CSS. Page-1 asserts for
those were replaced with asserts for: the ECharts asset `<script src>`, the three
donut containers + trend container, the four fallback containers, the lifecycle
helpers (`ecGet`/`ecDispose`/`ecResizeAll`), `loadCharts`/`loadTrend`,
`DONUT_PAL`, `#ov-trend-days`, `>=2` click handlers, `>=4` fallbacks, the
resize wiring, the trend-truthfulness note, and negative asserts that every
obsolete SVG artifact (`#ov-donut`, `donutArc`, `al-dist3`, `al-trend-day`,
`#dash-trend`, `renderHourly`) is gone.

### 17.8 Validation output

Frontend reconstruction build (sandbox mount truncates the now ~195 KB builder;
host file complete, tail-assert edits replayed via unique anchors):

```
py_compile OK
[OK] built alert_center.html (101102 bytes)
[OK] built alert_policies.html (99289 bytes)
[OK] built alert_rules.html (81271 bytes)
[OK] built alert_locks.html (77446 bytes)
[OK] built alert_health.html (70423 bytes)
[OK] M2c policy-drawer asserts pass
[OK] M2/M2b dashboard asserts pass   (+ ECharts asset, 3 donut + trend containers,
                                       fallbacks, click handlers, resize, no-SVG negatives)
[OK] M2d Price Setup contextual-footer asserts pass
[OK] M3 asserts pass
[OK] M4 asserts pass
[OK] G1 integration-health asserts pass
[OK] module-shell asserts pass
[OK] UI/UX consolidation nav + terminology asserts pass
```

Other checks: `node --check` OK on all five pages' inline JS; duplicate-id NONE
on all five; non-ASCII bytes 0 on all five; style/script tag balance OK;
dead-control audit NONE unbound (Overview); chart-fallback audit (≥4 `*-fb`
containers); click-filter audit (2 `.on("click"` handlers, donut + trend);
resize/dispose audit (`window…resize`→`ecResizeAll`, `ecDispose` before each
rerender); obsolete-SVG audit (0 occurrences of every removed artifact); no
merge-conflict markers; no trailing whitespace (git diff --check equivalent);
secret scan clean; vendored asset md5 verified `ef12c5c6…`; all five
`frontend/alert_*.html` git-ignored.

### 17.9 Branches, commits, and how to land it (owner, on Windows)

Two repos, two branches. The sandbox cannot commit (the `.git/index.lock` is
unremovable here and the large builder reads back truncated), so the owner runs:

```powershell
# 1) Asset repo (backend app) — new branch
cd C:\dev\ecentric_workspace
git checkout -b feat/alert-ui-echarts-asset
git add ecentric_workspace/public/js/echarts.min.js
git commit -m "Alert UI: add pinned ECharts asset"
bench build --app ecentric_workspace   # publishes /assets/ecentric_workspace/js/echarts.min.js
git push -u origin feat/alert-ui-echarts-asset

# 2) Frontend repo — existing branch
cd C:\dev\ALERT_CENTER
python -m py_compile frontend\build_alert_pages.py
git add frontend\build_alert_pages.py 69_UI_UX_CONSOLIDATION_REPORT.md
git commit -m "Alert UI: replace custom charts with interactive ECharts"
git push    # feat/alert-ui-ux-consolidation
python frontend\build_alert_pages.py deploy\backups\home_20260608_154510\main_section_html.bak.html frontend
```

Commit hashes: assigned by the two Windows commits above (the prior frontend HEAD
is `f38c52a`). The disposable preview `frontend\_preview_echarts.html` and the
mock `frontend\_preview_polish.html` are untracked helpers (not staged); delete
anytime.

### 17.10 Status

- ECharts asset vendored: YES (file in place, md5 verified) · committed: NO · pushed: NO
- frontend chart code: implemented + validated · committed: NO · pushed: NO
- merged: NO · deployed: NO

## 18. Chart architecture refactor — shared ERP source of truth (2026-06-15)

Section 17's ECharts behaviour was approved, but the implementation kept palettes,
lifecycle and option construction inside the builder. This pass moves all of that
into shared, namespaced app assets so charts have one ERP-wide source of truth.
No API/permission/schema/scheduler change. NOT merged, NOT deployed.

### 18.1 Verified frontend base commit

`git log` confirms the frontend branch `feat/alert-ui-ux-consolidation` HEAD is
**`22f6315 Alert UI: polish distribution chart and Price Setup actions`** (the
earlier `f38c52a` is its parent — section 17 mislabelled it; corrected here). All
of 22f6315 is preserved (see 18.11).

### 18.2 Exact files created / changed

App repo `ecentric_workspace` (branch `feat/alert-ui-echarts-asset`):

- `ecentric_workspace/public/charts/vendor/echarts.min.js` — moved here from the
  earlier `public/js/` location (md5 unchanged `ef12c5c6…`, never modified).
- `ecentric_workspace/public/charts/chart_theme.js` — new (`window.ECChartTheme`).
- `ecentric_workspace/public/charts/chart_common.js` — new (`window.ECCharts`).
- `ecentric_workspace/public/charts/alert_charts.js` — new (`window.AlertCharts`).
- `public/js/` removed.

Frontend repo `ALERT_CENTER` (branch `feat/alert-ui-ux-consolidation`):

- `frontend/build_alert_pages.py` — PAGE1 now loads the 4 assets in order and only
  renders containers/fallbacks, fetches data, does a minimal transform, calls
  `AlertCharts`, and handles the filter/drill callback; the inline palettes
  (`DONUT_PAL`), generic lifecycle (`ecGet`/`ecDispose`/`ecResizeAll`/`CHARTS`)
  and the long donut/trend `setOption` objects were removed; page-1 asserts
  updated. Other four pages unchanged.
- `69_UI_UX_CONSOLIDATION_REPORT.md` — this section.

### 18.3 ECharts version + license

Apache **ECharts 5.5.1**, Apache-2.0 (license header retained in the file),
vendored from npm, served at `/assets/ecentric_workspace/charts/vendor/echarts.min.js`.
The minified file is byte-for-byte unmodified (md5 `ef12c5c63df2acdf59f8a86cf0317711`).

### 18.4 Theme tokens + palettes (`chart_theme.js` → `window.ECChartTheme`)

- Light + dark token sets (`tokens()` picks by `prefers-color-scheme`): ink,
  muted, faint, grid, axis, border, surface, surfaceAlt.
- `semantic`: critical `#db2777`, warning `#d4a017`, ok `#1a8754`, info `#2f6db0`,
  neutral `#94a3b8`.
- `palettes`: brand `["#1f3a5f","#2f6db0","#5b9bd5","#c3d4e8"]` (blue/navy),
  platform `["#0f766e","#14a8a0","#5fd0c8","#bfe9e6"]` (teal/cyan),
  rule `["#b45309","#ea8b2f","#f4b46b","#f6dcb8"]` (amber/coral), series
  `["#2f6db0","#0f766e","#94a3b8"]` (New/Resolved/Ignored). Index 3 = "Other".
- `typography`, `animation` (450ms cubicOut), `empty`, `loading()`, and reusable
  style fragments `tooltip()/axisLabel()/splitLine()/grid()/legend()/centerText()`.
  No chart page hardcodes ordinary palettes after this.

### 18.5 Shared lifecycle (`chart_common.js` → `window.ECCharts`)

`ok, ensure, get, dispose, disposeAll, resize, resizeAll, attachResize (single,
debounced, idempotent), showLoading, hideLoading, setOption (dispose-safe,
notMerge default), fallback, clearFallback, esc, pct, merge (deep)`. A registry of
live elements drives `resizeAll`; `ensure` reuses `getInstanceByDom` so a
container never gets two instances; `attachResize` guards with a bound-flag so only
one window listener is ever added — preventing duplicate instances, duplicate
listeners and leaks.

### 18.6 Alert render functions (`alert_charts.js` → `window.AlertCharts`)

- `renderDistributionDonut(el, dimension, rows, options)` — Top 3 + Other against
  the dimension's own total, business labels via `options.labelFor`, palette via
  `ECChartTheme.palette(dimension)`, centre total via `ECChartTheme.centerText`,
  tooltip/legend from theme, disposes before rerender, wires `options.onClick(raw)`
  (Other/none inert), and renders a table fallback when ECharts is unavailable.
- `renderTrend(el, rows, options)` — New (bars) / Resolved (line) / Ignored
  (dashed line) using `ECChartTheme.palette("series")`, axis/grid/legend from
  theme, wires `options.onPointClick(day)`, table fallback otherwise.
- It consumes `window.echarts`, `ECChartTheme`, `ECCharts`; it re-implements no
  generic lifecycle and hardcodes no palette.

### 18.7 Asset loading order (Overview page only)

```html
<script src="/assets/ecentric_workspace/charts/vendor/echarts.min.js"></script>
<script src="/assets/ecentric_workspace/charts/chart_theme.js"></script>
<script src="/assets/ecentric_workspace/charts/chart_common.js"></script>
<script src="/assets/ecentric_workspace/charts/alert_charts.js"></script>
```

Pinned local assets, no runtime CDN. Order = vendor → theme → common → alert.

### 18.8 Fallback behaviour (defence in depth)

- If `window.echarts` is missing but the modules loaded: `AlertCharts` renders a
  per-chart table (donut: category/count/%; trend: date/New/Resolved/Ignored).
- If the module bundle itself failed to load (no `window.AlertCharts`): the builder
  renders a minimal page-level table fallback in the same `*-fb` element.
  Either way the Overview stays readable; the page never blanks.

### 18.9 Data truthfulness (unchanged from the approved behaviour)

Three independent donuts (Brand/Platform/Rule), each its own total, Top 3 + Other,
theme palettes, business labels, click-to-filter. Trend uses exactly the API's
New / Resolved / Ignored per day — no fabricated severity-by-day, backlog or
cumulative series.

### 18.10 Validation output

App assets: `node --check` OK on `chart_theme.js`, `chart_common.js`,
`alert_charts.js` and `vendor/echarts.min.js`; only the three approved globals are
assigned (`window.ECChartTheme` / `window.ECCharts` / `window.AlertCharts`); the
minified asset is unmodified (md5 verified); no secrets, no conflict markers, no
trailing whitespace.

Frontend (reconstruction build; host file complete, tail asserts replayed via
unique anchors):

```
py_compile OK
[OK] built alert_center.html (98207 bytes)   # smaller: chart code now external
[OK] built alert_policies.html / alert_rules.html / alert_locks.html / alert_health.html
[OK] M2c / M2/M2b (+ 4 assets in order, AlertCharts/ECCharts/ECChartTheme wiring,
     callbacks, fallbacks, negatives: no DONUT_PAL/ecGet/ecResizeAll/inline options)
[OK] M2d Price Setup contextual-footer asserts pass
[OK] M3 / M4 / G1 / module-shell / consolidation asserts pass
```

Other: `node --check` OK on all five pages; duplicate-id NONE; non-ASCII 0;
tag balance OK; dead-control audit NONE unbound; donut click-to-filter audit
(`onClick:function(raw){applyDimFilter…`) and trend click-to-day audit
(`onPointClick:function(day){…`) present; resize/dispose audit
(`ECCharts.attachResize()` in builder; dispose-before-rerender inside the shared
module); old-custom-SVG audit (0 occurrences of every removed artifact); generated
HTML git-ignored; no conflict markers; no trailing whitespace.

### 18.11 Price Setup RC2 (commit 22f6315) preserved

Verified intact in the built `alert_policies.html`: the contextual lifecycle
footer (`#pl-life`, single secondary button), `refreshFooter`, the status badge
`#pl-d-status`, the "More → Set to Draft" affordance, and the info-icon spacing
(`margin-left:7px`). The refactor touched only PAGE1 chart code; PAGE2 (Price
Setup) was not modified.

### 18.12 Windows commit commands (owner; two repos / two branches)

The sandbox cannot commit (unremovable `.git/index.lock`; the large builder reads
back truncated), so the owner runs:

```powershell
# App assets — branch feat/alert-ui-echarts-asset
cd C:\dev\ecentric_workspace
git checkout -b feat/alert-ui-echarts-asset   # (or: git checkout feat/alert-ui-echarts-asset)
git add ecentric_workspace/public/charts/
node --check ecentric_workspace/public/charts/chart_theme.js
node --check ecentric_workspace/public/charts/chart_common.js
node --check ecentric_workspace/public/charts/alert_charts.js
git commit -m "Alert UI: add shared ECharts assets (theme, common, alert, vendor)"
bench build --app ecentric_workspace
git push -u origin feat/alert-ui-echarts-asset

# Frontend — branch feat/alert-ui-ux-consolidation (already on it)
cd C:\dev\ALERT_CENTER
python -m py_compile frontend\build_alert_pages.py
git add frontend\build_alert_pages.py 69_UI_UX_CONSOLIDATION_REPORT.md
git commit -m "Alert UI: move charts to shared ECharts assets"
git push
python frontend\build_alert_pages.py deploy\backups\home_20260608_154510\main_section_html.bak.html frontend
```

The untracked previews `frontend\_preview_echarts.html` (now loads the 4 shared
assets) and `frontend\_preview_polish.html` are disposable; not staged.

### 18.13 Status

- app assets created + validated · committed: NO · pushed: NO
- builder refactored + validated · committed: NO · pushed: NO
- Price Setup RC2 (22f6315) preserved: YES
- merged: NO · deployed: NO

## 19. RC3 UI/UX + workflow correction (2026-06-15) — Pass 1 + Pass 2

Verified frontend base = **`f87b8e2 Alert UI: use shared interactive ECharts`**.
Two passes, ONE combined validation, ONE final commit. **Frontend-only.**

### 19.1 No backend / schema / API change

Backend inspection (before editing) confirmed nothing was missing, so **no
DocType, schema, API, permission, or scheduler change was made**. The only file
changed is `frontend/build_alert_pages.py` (+ this report). The five generated
`frontend/alert_*.html` stay git-ignored. The shared ECharts assets and the
Price Setup contextual footer are unchanged (verified, no regression).

Reused existing fields/endpoints:
- Per-order components + marketplace id: `EC Alert Occurrence` via
  `api_alerts.alert_occurrences` (`external_order_id`, `rsp_price`,
  `seller_discount_amount`, `seller_voucher_amount`, `platform_discount_amount`,
  `platform_voucher_amount`, `effective_check_price`, `min_price_at_check`,
  `baseline_price_at_check`, `gap_percent`, `price_components_used`). No Omisell/
  warehouse order id exists in the occurrence, so `external_order_id` is the
  primary order id.
- Lifecycle: `api_alerts.set_status` (In Review / Closed / Ignored).
- Rules: `api_rules.list_rules` / `save_rule` / `set_rule_status` (Draft/Active/
  Paused). No delete endpoint exists, so "remove platform override" = set that
  override rule **Paused** (it stops applying → Brand Default takes over).

### 19.2 Pass 1 (UI + workflow corrections)

A1 advanced-filter spacing + subtle card + true zero-height collapse (the
`display:flex` rule was overriding `[hidden]`). A2 SLA bars relative to the max
bucket (zero = no fill, positive = visible min width, progressive blue→amber→
orange→pink), count preserved. A3 Recent Critical rows clickable + Enter/Space →
open drawer. B1 raw `price_components_used` moved to Technical Details/CSV/tooltip;
friendly breakdown remains. B3 contextual lifecycle footer (Claim→In Review,
Resolve→**Closed** [fixes the rejected "Resolved" bug], Ignore in More, terminal =
no primary); Pause Automation + Source Order removed from the alert drawer (F).
B4 evidence shows `external_order_id`. C1 ERP Item hidden; C2 alert thresholds
removed from Price Setup; C3/E4 effective-period UI removed from Price Setup and
Rules — all kept as hidden inputs so values persist and Active validation can't
regress. D one scope-priority line with per-tier tooltips (duplicates removed).
E1 rule-code bug fixed (`relabelRuleOptions` pins the canonical code onto
`o.value`; editor options carry explicit `value="below_min"` …). E3 (partial)
severity override hidden.

### 19.3 Pass 2 — B2 selected-occurrence mapping

The price-calculation panel is sourced from the **selected `EC Alert Occurrence`
row** (`renderCalc(o)`), defaulting to the latest violating occurrence
(`rows[0]`, ordered `detected_at desc`). Clicking or Enter/Space on a row
(`selectOcc(i)`) re-renders the panel from that row and highlights it
(`al-occ-sel`); the heading shows that row's `external_order_id`; the panel is
sticky (`.al-calc`) so it stays visible while the table scrolls. Every value (RSP,
seller/platform discount+voucher, effective price, min, baseline, gap) comes from
the selected row — the alert-summary values are not used once a row is selected,
and nothing is fabricated. CSV export stays based on the full list (`S.occ`);
reopening the drawer resets `S.selOcc=0`.

### 19.4 Pass 2 — E2/E3 Rules business editor + precedence

UI→backend mapping: each brand card shows three behaviours →
`below_min` (Below minimum price), `severe_price_drop` (Severe price drop),
`above_high` (Above benchmark). "All platforms" = the **`platform="All"` Brand
Default** row (no new rule code / scope type). "Customize by platform" lists
Shopee/Lazada/TikTok: a platform with its own rule is **overridden** (badge); else
it **inherits** the brand default (muted "inherits N%"). Each behaviour's threshold
is written to its canonical field — `below_min → threshold_percent`,
`severe_price_drop → severe_drop_percent`, `above_high → high_alert_percent`. Edit/
Configure/Add prefill the (E3-simplified) drawer for `brand~rule_code~platform`;
Remove sets the override Paused (fallback). The Advanced Exceptions table keeps
Shop/SKU rules.

Precedence resolver (`ruleMatchScore`/`resolveRule`/`resolveThreshold`) is a
faithful frontend mirror of the backend `services/rule_overlay._match_score`:
the threshold for a rule_code comes from the **most specific** matching rule
(SKU +8 > Shop +4 > Platform +2 > Brand +1), resolved **independently per rule
code, never merged, never "stricter value"**. A deterministic self-test runs on
load and in CI (node):

```
severe_price_drop: Brand 50 / Shopee 60 / SKU 70
  generic (Lazada)        -> 50
  Shopee                  -> 60
  matching SKU            -> 70
  a 55% drop alerts generic (>=50) but NOT Shopee (<60) or SKU (<70)
verified independently for below_min and above_high
=> precedence self-test: PASS
```

### 19.5 Combined validation output

```
py_compile OK
5-page build OK
[OK] M2c (Price Setup simplified) / M2/M2b (+A1,A2,A3,B1,B3,B4,E1,B2)
[OK] M2d (Price Setup footer preserved) / M3 (+D,E1,E4,E2,E3,precedence)
[OK] M4 / G1 / module-shell / consolidation
node --check OK on all 5 pages
precedence self-test (node): PASS  (50/60/70 + 55% case, all 3 rule codes)
duplicate IDs: NONE (all 5) · non-ASCII: 0 (all 5)
dead-control audit: NONE unbound
ECharts shared assets: present (no regression) · Price Setup pl-life footer: present
no conflict markers · no trailing whitespace · no secrets · generated HTML git-ignored
```

### 19.6 Final commit (owner, Windows — one commit for Pass 1 + Pass 2)

```powershell
cd C:\dev\ALERT_CENTER
python -m py_compile frontend\build_alert_pages.py
python frontend\build_alert_pages.py deploy\backups\home_20260608_154510\main_section_html.bak.html frontend
git add frontend\build_alert_pages.py 69_UI_UX_CONSOLIDATION_REPORT.md
git status   # confirm NO generated frontend\*.html staged, no secrets
git commit -m "Alert UI: RC3 workflow corrections + Rules business editor (Pass 1+2)"
git push     # feat/alert-ui-ux-consolidation
```

## 20. E3 completion — fully simplified KAM rule editor (2026-06-15)

The rule drawer was rebuilt so the KAM-facing editor exposes ONLY business fields.

### 20.1 Visible vs hidden

Visible: Brand · Behaviour (Below minimum price / Severe price drop / Above
benchmark) · ONE "All platforms" threshold · optional "Customize by platform"
(Shopee / Lazada / TikTok, each marked inherited/overridden) · Save / Cancel.

Removed from the UI (verified absent in the built page): the raw rule-code
`<select>` (`r-rule_code`), the raw scope selectors (`r-platform` / `r-shop` /
`r-seller_sku` / `r-item`), the three simultaneous threshold inputs
(`r-severe_drop_percent` / `r-high_alert_percent` / `r-threshold_percent`), the
severity-override `<select>`, the lifecycle transition buttons
(`ru-st-active/paused/draft`), the overlap tool, and the effective-period fields.
Canonical rule codes / scope values stay internal in JS/API payloads only
(behaviour `<select>` carries `value="below_min"` … but shows business labels;
severity_override + effective_from/to remain as hidden inputs so existing values
are not lost).

### 20.2 ONE behaviour threshold input — and the truthful field it writes

The editor shows exactly one threshold input (`r-thr-all`) per behaviour. IMPORTANT
backend reality discovered on inspection: `api_rules` EDITABLE persists ONLY
`threshold_percent` — `severe_drop_percent` / `high_alert_percent` are doctype-/
overlay-read-only fields and are NOT in the rule API. So with **no backend change**
the editor writes `threshold_percent` for every behaviour, and the backend
`rule_overlay` maps it to the right behaviour by `rule_code`
(`severe_drop_percent or threshold_percent`, etc.). Implementing the literal
per-field mapping (`severe_price_drop → severe_drop_percent`) would require adding
those fields to the rule API — a backend change, explicitly out of scope. The
frontend resolver/test still mirror the overlay's read order (per-field with
`threshold_percent` fallback), so the precedence test remains exact.

### 20.3 Remove platform override

The user-facing action is **"Bỏ tùy chỉnh"** with helper **"Sẽ dùng lại giá trị
All platforms"** — never "Pause rule". Under the hood it calls
`set_rule_status(Paused)` on the override (no delete API exists), then re-renders:
the platform shows as inherited with the Brand Default value, and the paused
override no longer applies.

### 20.4 Source-of-truth boundary

The frontend precedence resolver is used ONLY for UI preview + the deterministic
self-test/assert. The backend `rule_overlay` remains the single source of truth for
actual alert evaluation; no backend evaluation logic is duplicated or replaced in
production behaviour.

### 20.5 E3 validation (added to the combined run)

```
Rule drawer: no raw rule-code <select> (r-rule_code absent)         PASS
Rule drawer: no raw scope <select> (r-platform/shop/seller_sku)     PASS
exactly ONE threshold input visible (r-thr-all; 3-field set absent) PASS
severity-override <select> absent                                  PASS
effective-period fields absent (hidden inputs only; no date picker) PASS
"Bỏ tùy chỉnh" + "Sẽ dùng lại giá trị All platforms" present; no "Pause" label  PASS
canonical rule_code + threshold_percent submitted (RULE_SAVE_THR_FIELD) PASS
precedence self-test (node): PASS · 5-page build + all asserts: PASS
node ×5 · dup IDs NONE · dead-control NONE · 0 non-ASCII
ECharts shared assets + Price Setup pl-life footer: unchanged
no conflicts / trailing-ws / secrets · generated HTML git-ignored
```

### 20.6 Status — single final commit ready

Frontend-only; `frontend/build_alert_pages.py` (+263 / −764, a net simplification)
and this report. No backend/schema/API change. Owner runs the one final commit on
Windows:

```powershell
cd C:\dev\ALERT_CENTER
git add frontend\build_alert_pages.py 69_UI_UX_CONSOLIDATION_REPORT.md
git commit -m "Alert UI: RC3 workflow corrections + simplified Rules editor (Pass 1+2, E3 complete)"
git push
```

- Pass 1 + Pass 2 + E3 implemented + combined validation: PASS
- backend/schema/API change: NONE · committed: NO · pushed: NO · merged: NO · deployed: NO
