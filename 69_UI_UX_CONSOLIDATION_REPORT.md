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
