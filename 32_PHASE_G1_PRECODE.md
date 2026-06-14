# Alert Center — Phase G1 Pre-Code Proposal
## Brand Onboarding Foundation & Integration Health

Date: 2026-06-08 · Status: **PRE-CODE — awaiting approval. No code written yet.**

---

## 0. Motivation & scope

Onboarding LOF-VN exposed the real gap: bringing a brand online today means a human reading scattered Desk records (Brand Approver, EC Brand Integration Settings), running PowerShell probes, and eyeballing `pull_status`. That doesn't scale. G1 turns "is this brand ready, and what's blocking it?" into a **single read-only page driven by computed readiness logic** — so any brand becomes a configuration/onboarding workflow, not a custom script.

**G1 is deliberately a read + diagnose + link-out layer.** It writes nothing new to production data: no new automation, no site_config edits, no Omisell writes, no stock writes, DS1 stays locked, FES-VN scheduler untouched. The mutating actions it surfaces (probe / preview / manual pull) are the **existing, already-verified** SM-only endpoints; the one genuinely new write (scheduler allowlist) is **documented and gated**, never auto-applied.

North-star alignment: maintainability (one readiness function, no per-brand branches), scalability (computed for N brands), permission-awareness (service-layer scope reused), auditability (no silent mutations; actions reuse audited endpoints), reusable components (`.al-*` UI + `permissions.get_allowed_brands`), clean data model (reuse canonical DocTypes), clear boundaries (new `api_brands` module fronts existing services).

---

## 1. DocTypes — reuse everything, add nothing (G1)

**No new DocType in G1.** Readiness is a *computed projection* over records that already exist. Storing it would create a second source of truth that drifts. Sources:

| Concept | Canonical DocType | Fields read |
|---|---|---|
| Brand + scope | `Brand Approver` | `name` (brand code), `status`, `kam_owner`, `manager_email`, `leader_email` |
| Omisell integration | `EC Brand Integration Settings` | `enabled`, `credential_status`, `base_url`, `last_sync_at`, `consecutive_failures`, `dry_run_stock_lock`, `default_platform_scope` (NEVER `api_key`/`api_secret`/`token`) |
| Alerts | `EC Alert` | counts by `brand`, `status`, `rule_code` |
| Orders / lines | `EC Marketplace Order Log` / `EC Marketplace Order Item` | counts by `brand` |
| Policies | `EC Price Policy` | count Active by `brand`; distinct `seller_sku` covered |
| Scheduler allowlist | site_config `ec_alerts_scheduled_pull_brands` | membership (read) |
| Last run | cache `pull_recent_job` summary | via existing `pull_status` |

**Deferred (NOT G1):** an optional `EC Brand Readiness Snapshot` cache DocType for history/trend could come later (G4) if recompute cost matters. G1 computes live with cheap `frappe.db.count` + a few `get_value`s, bounded per brand.

---

## 2. API endpoints (new module `ecentric_workspace/alerts/api_brands.py`)

All `@frappe.whitelist`, all begin with `permissions.require_alert_center_access()`; reads are scoped via `get_allowed_brands`. No new mutation endpoints — actions reuse `api_omisell`.

| Endpoint | Method | Returns | Notes |
|---|---|---|---|
| `list_brand_readiness()` | POST | one readiness row per brand the caller may see | the table feed; SM sees all Active Brand Approver brands, others see their scope |
| `brand_readiness(brand)` | POST | full detail for one brand (all §3 fields + blockers + suggested action) | drawer feed; `require_brand_access` |
| `policy_coverage(brand, sample=500)` | POST | `{covered, distinct_skus, pct, sampled}` | best-effort, bounded; split out because it's the heaviest query |

**Reused (already live, unchanged):** `api_omisell.omisell_probe`, `pull_preview`, `pull_recent`, `pull_status` (all SM-only POST), `api_policies.list_policies`, `api_alerts.list_alerts/get_cards`. G1 adds **zero** new write paths.

Secret safety: `api_brands` selects an explicit field allowlist from BIS — `api_key`/`api_secret`/`token` are never in the `fields=[...]` list, so they can't leak to the frontend even for SM.

---

## 3. UI structure — `/alerts/integration-health` (alias `/alerts/brands`)

Fills the existing sidebar slot "Integration Health" (currently a placeholder pointing at `/alerts`; G1 repoints it to the real route). Same `.ec-sidebar` module shell, same `.al-*` components, same breadcrumb pattern `Workspace / Alert Center / Integration Health`. Built by the existing `build_alert_pages.py` (5th page) and deployed by `deploy_alert_pages.ps1 -Only alert-health`.

Layout:
- **Header band** — counts: brands Ready / Blocked / Warning / Scheduler-Enabled. One-line legend.
- **Readiness table** (one row per brand) with a colored status pill and these columns:
  brand code · KAM owner · manager/leader · Brand Approver status · BIS status · credential_status · enabled · dry_run_stock_lock · last_sync_at (relative) · breaker (consecutive_failures) · scheduler allowlist (yes/no) · last run state · alert count · order/item count · policy coverage %.
- **Row click → detail drawer** (`.al-drawer-wide`): full field dump, the **ordered blocker list**, the **single recommended next action**, and the action buttons (§4).
- **Status pills** (reuse severity color tokens, no new palette): Ready `--green` · Warning `--yellow` · Blocked `--pink` · Running `--navy` · Scheduler Enabled `--green` outline · Manual Pull Required `--yellow` outline.

ASCII-only source (entities / `\uXXXX`), no external libs, no Jinja — same constraints as the other four pages.

---

## 4. Actions & links (per row / in drawer) + safety gates

| Action | Mechanism | Gate |
|---|---|---|
| Create/Edit BIS | link to Desk `/app/ec-brand-integration-settings/new` (or the record) | SM only (DocPerm already SM-only); KAM sees a "ask an admin" hint instead |
| View policies | link `/alerts/policies?brand=<code>` | scope |
| View alerts | link `/alerts#al-alert-list` (filtered) | scope |
| Run preview | calls `api_omisell.pull_preview` | **SM only**; read-only count, no DB write |
| Run manual pull | calls `api_omisell.pull_recent` | **SM only**; confirm modal; **preview must have been run first** (UI enforces); background job |
| View pull_status | calls `api_omisell.pull_status` | SM only; read-only |
| Add to scheduler | **NO auto-write.** Drawer shows the exact site_config snippet + the FC step + a copy button | documented/gated; requires explicit owner action off-page |

Hard safety gates (UI + server):
- Every Omisell call is read-only (probe/list/detail GETs); ingestion writes Frappe records only. No Omisell write path anywhere in G1.
- No stock/buffer/inventory write. DS1 stays locked (`dry_run_stock_lock` is shown and a brand with it `!=1` is flagged Blocked for any pull action).
- "Add to scheduler" never edits `ec_alerts_scheduled_pull_brands` from the page. It only renders the instruction. (Auto-edit is a future, separately-approved gate — see G4/roadmap.)
- Manual pull button disabled unless the brand is at least Warning-or-better on credentials (BIS enabled + credential_status Active + breaker closed); otherwise it shows the blocker instead.
- All mutating actions reuse `frappe.only_for("System Manager")` already inside the existing endpoints — G1 adds no new privilege.

---

## 5. Permission model

Reuse the service layer verbatim — **no new roles, no DocPerm changes** (decision D2 holds).

- Table/detail visibility: `get_allowed_brands(user)` — SM/Administrator → all Active brands (`*`); KAM/manager/leader → their scoped brands; nobody else → `PermissionError`.
- Field redaction: BIS secret fields never selected. Even SM sees `credential_status`, never the key.
- Action authorization: preview/pull/status are `System Manager` only (unchanged). KAM/manager/leader get a **read-only readiness view** with action buttons replaced by an explanatory hint ("integration actions are System-Manager-only").
- `Create BIS` is an SM-only Desk link; non-SM see guidance text.

---

## 6. Readiness logic (pure, deterministic, precedence-ordered)

Computed per brand from §1 sources. A brand gets an **ordered blocker list** and a **single status** = the highest-precedence condition that applies:

Precedence (first match wins):
1. **Blocked — Missing Brand Approver** (no record / not Active)
2. **Blocked — Missing BIS** (no `EC Brand Integration Settings` Omisell row) ← LOF-VN today
3. **Blocked — BIS disabled** (`enabled != 1`)
4. **Blocked — DS1 unsafe** (`dry_run_stock_lock != 1`) — refuse pull actions
5. **Blocked — credential not Active** (`credential_status != "Active"`) → suggested action: Run probe
6. **Blocked — circuit breaker open** (`consecutive_failures >= 3`) → suggested action: investigate + reset
7. **Running** (a `pull_status.running_since` lock is set) — informational, not a blocker
8. **Warning — no KAM owner** (`kam_owner` empty: alerts have no daily owner)
9. **Warning — stale last_sync_at** (older than a configurable threshold, default 45 min for scheduled brands; "never synced" for new brands shows **Manual Pull Required**)
10. **Warning — policy coverage too low** (Active-policy SKU coverage below a threshold, default <50% of recently-seen SKUs; tunable, best-effort)
11. **Manual Pull Required** — credentials Active but `last_sync_at` empty and brand not in scheduler allowlist
12. **Scheduler Enabled** — in `ec_alerts_scheduled_pull_brands` AND last run `state=done` AND breaker 0 AND sync fresh
13. **Ready** — credentials Active, breaker 0, can pull, but scheduler not yet enabled (the "verified manual, awaiting allowlist" state)

Each brand row therefore answers: *what is the single most important thing to do next?* — exactly the onboarding sequence (fix Brand Approver → create/enable BIS → probe → preview → manual pull → enable scheduler → runs).

Thresholds (`stale_minutes`, `coverage_pct`) live in site_config keys (e.g. `ec_alerts_health_stale_minutes`, `ec_alerts_health_min_coverage`) with safe defaults, so tuning needs no deploy.

---

## 7. LOF-VN expected status (first real test case)

With Brand Approver present but BIS missing, the page must show:

- **Status pill: Blocked** (precedence #2, "Missing BIS").
- Blocker list: `Missing EC Brand Integration Settings (Omisell)`.
- Recommended action: **"Create BIS before preview/pull"** with the SM-only Desk link to create the record.
- Preview / Manual-pull buttons **disabled** with tooltip "BIS required".
- Scheduler allowlist column: `no`. KAM owner / manager / leader: shown from Brand Approver. Counts (alerts/orders): 0. Policy coverage: n/a.

Once an SM creates + enables BIS and runs probe, LOF-VN should move Blocked → (credential probe) → **Manual Pull Required** → after a verified manual pull → **Ready** → after allowlist edit → **Scheduler Enabled**. That progression is the visible onboarding workflow.

FES-VN, in the same table, should show **Scheduler Enabled** (green) — proving the logic recognizes a fully-onboarded brand without special-casing.

---

## 8. Deploy plan

Two drops, mirroring Phase F:
- **Drop 1 (backend):** new `api_brands.py` (3 read endpoints) + repoint the sidebar "Integration Health" nav entry + 2 optional site_config threshold keys (no migrate needed — no schema change, no new DocType). PR with files-changed gate: only `alerts/api_brands.py` + `frontend/build_alert_pages.py`. FC deploy, **no migrate**.
- **Drop 2 (frontend):** build the 5th page (`alert_health.html`) via `build_alert_pages.py`; deploy `deploy_alert_pages.ps1 -Only alert-health`. Verify live marker + Ctrl+Shift+R.

Constraints reaffirmed in the PR description: no new DocType, no DocPerm/role change, no hooks.py change, no scheduler change, no Omisell/stock write, DS1 locked.

---

## 9. Rollback plan

- Frontend: `rollback_alert_pages.ps1 -Only alert-health` unpublishes the page (content preserved); the sidebar item reverts to placeholder by redeploying the prior builder output.
- Backend: revert the PR → FC deploy. `api_brands.py` is additive and read-only; removing it affects nothing else (no migrations to unwind, no data written).
- Zero data risk: G1 writes no production data; there is nothing to clean up.

---

## 10. Test plan

- **Unit (sandbox, stubbed frappe):** readiness precedence table — feed synthetic brand states (missing BA, missing BIS, disabled, DS1-unsafe, expired cred, breaker open, running, no-KAM, stale, low-coverage, ready, scheduler-enabled) and assert the resolved status + ordered blocker list. Secret-redaction test: assert `api_key`/`api_secret`/`token` never appear in any `api_brands` response.
- **Permission tests:** SM sees all brands; a KAM token sees only scoped brands; an unrelated token → PermissionError; non-SM action endpoints → 403 (reuse the Phase E 403-matrix harness).
- **Live verification (read-only probe script `verify_phase_g1.ps1`):** call `list_brand_readiness` as SM → assert FES-VN = Scheduler Enabled and **LOF-VN = Blocked: Missing BIS**; `brand_readiness("LOF-VN")` returns the Create-BIS action; confirm no secret fields present.
- **UAT:** open `/alerts/integration-health`, confirm pills/columns, drawer blocker list, action gating (LOF-VN buttons disabled), links resolve; confirm FES-VN unaffected and its scheduler keeps running during the test.

---

## Roadmap — phases after G1 (pre-code stubs, each separately gated)

- **G2 — Omisell Shop + SKU Catalog Sync.** Read-only pull of shop list + catalogue SKUs per brand into a browsable catalog (reuse `sync_shop_directory` + a new read endpoint), so policy authoring can autofill real SKUs/shops instead of free-text. Still read-only to Omisell. Feeds the policy-coverage metric in G1.
- **G3 — Policy Coverage + Mass Update.** Turn coverage % into action: highlight uncovered high-volume SKUs, bulk-create Draft policies from the catalog (G2), CSV mass-update (reuse `policy_csv`), brand-scoped. No engine change — policies stay the canonical input.
- **G4 — Generic Brand Onboarding Wizard.** A guided multi-step flow that orchestrates G1 readiness → create BIS → probe → preview → manual pull → (gated) allowlist add. This is where a **gated, audited site_config write for the scheduler allowlist** would finally be introduced behind explicit confirmation — replacing the manual FC step. Optional `EC Brand Readiness Snapshot` cache lands here if needed.
- **G5 — Stock Read Only.** Behind DS1: read available/buffer stock from Omisell to populate the currently-placeholder lock fields (`-(DS1)`), display-only. No writes. Gated on Omisell checklist items 10–12d.
- **G6 — Real Stock Lock Execution Gate.** The eventual, heavily-gated transition from dry-run to real buffer-stock writes (DS1 design `11_STOCK_LOCK_BUFFER_DESIGN.md`). Requires its own approval, executor changes, and audit; explicitly out of scope until G1–G5 are stable.

---

## Data Lifecycle & Idempotency (verified from code, origin/main — `services/ingestion.py`, `services/omisell_normalizer.py`, `services/alert_engine.py`, Order Log DocType)

This is the foundation that makes multi-brand safe. All claims below are read from the deployed code, not assumed. No probe needed — the logic is unambiguous; the FES-VN P02056 re-pull during UAT already demonstrated it live.

### Answers to the 7 questions

**Q1 — Re-pull of a status-changed order: upsert or new record?** **Upsert in place.** `ingestion._ingest_one` looks up `EC Marketplace Order Log` by `order_key` (a UNIQUE field = `"{source_system}|{external_order_id}"`, e.g. `Omisell|ORD-1`). If found, it loads that doc and updates it; only if absent does it create. Note the key is **source + external_order_id**, not brand + external_order_id — so the same Omisell order number is one row regardless of later brand re-resolution (correct: an order is one order).

**Q2 — Order-item idempotency key?** There is **no per-line upsert key**; on any changed re-pull the code does `doc.items = []` then re-appends every line (full child-table replace). So physically the child rows are deleted and re-inserted (their Frappe child `name`s churn). The **logical** line identity is `external_line_id` — that is what alert dedupe uses (`price_alert_key = omisell|{external_order_id}|{external_line_id}|price|{rule_code}`). Important consequence: alerts reference the **parent** (`reference_name` = Order Log) plus the stored `external_line_id`, **never** the child row name — so the alert↔line linkage survives the child-row churn. (On an *unchanged* re-pull — payload hash match — items are not touched at all.)

**Q3 — Created → Cancelled: updated in place?** **Yes.** A changed payload (different `raw_payload_hash`) takes the `status="updated"` branch and overwrites `order_status` in place. `order_status` is stored as `"{status_id} - {status_name}"` (e.g. `702 - Huy boi doi tac`).

**Q4 — Are old statuses kept?** **Only the latest snapshot is stored canonically** — `order_status` is a single field; `raw_payload_hash` holds only the most recent payload fingerprint. There is **no status-history child table**. However, the DocType has `track_changes=1`, so Frappe's native **Version** log records each field change (including `order_status`) as an audit trail. That is an audit history, **not** a queryable event store — fine for "who/what changed when", not for analytics over status transitions.

**Q5 — Does re-pulling increase counts?** **Order Log: no** (upsert by unique `order_key`). **Order Item: no net growth** — a changed re-pull replaces the same number of lines (delete + re-insert), so the count tracks *current* lines; an unchanged re-pull touches nothing. Counts are stable under re-pull; only child-row identities churn on changes.

**Q6 — Does alert dedupe prevent duplicates on re-pull?** **Yes.** Every re-pull re-runs `alert_engine.check_order_log`, but `_create_alert` is dedupe-then-insert against the UNIQUE `EC Alert.dedupe_key`; C1 keys (order-line for price rules, daily SKU-level for `missing_*`) make re-runs no-ops. (This is also why the old `missing_policy` snapshot persists unchanged — see §"Finding 1" in `30_PHASE_F_UAT_NOTES.md`.)

**Q7 — Cancelled orders & price compliance allowlist.** **Confirmed: cancelled-at-violating-price orders ARE considered.** `omisell_normalizer.is_real_sale` reads site_config `ec_alerts_omisell_allowed_status_ids = [250, 300, 400, 460, 500, 600, 702, 900]` (Q-D2 FINAL, framed as "price-risk / customer-checkout statuses": if a customer *could place* the order at that price, the exposure already happened — **702 = Huy boi doi tac / cancelled-by-partner is included**). If the allowlist is absent, a conservative keyword rule applies (excluded keywords win) and **unknown statuses are EXCLUDED and reported, never silently ingested**.

### Current snapshot model

One row per order (`EC Marketplace Order Log`, keyed `order_key` UNIQUE) holding the **latest** state, with its lines in the `items` child table (`EC Marketplace Order Item`). Alerts (`EC Alert`) are separate, immutable, dedupe-keyed records. The order table is a **mutable latest-snapshot**; the alert table is an **append-only event log of detections**. These two roles are intentionally split.

| Data | Idempotency / write behavior | Mutable or immutable |
|---|---|---|
| `EC Marketplace Order Log` | upsert by `order_key` (`source\|external_order_id`); `raw_payload_hash` short-circuits unchanged re-syncs | **Mutable** — latest snapshot, updated in place |
| `EC Marketplace Order Item` | full child-table replace on change; no per-line key; logical id = `external_line_id` | **Mutable** — replaced wholesale on change |
| `order_status` | overwritten in place; history only in Frappe Version log (audit) | **Mutable** (audit trail aside) |
| `EC Alert` | dedupe-then-insert on UNIQUE `dedupe_key`; never rewritten | **Immutable snapshot** (detection-time) |
| `EC Alert Action` | dedupe-keyed dry-run actions | **Immutable** + reviewed status |

What is **upserted**: Order Log + its items.
What is **immutable snapshot**: EC Alert + EC Alert Action (detection records).

### Expected monthly row growth

Planning assumption (from D.1): ~**100K orders/brand/month** ceiling; ~2 lines/order ⇒ ~100K Log + ~200K Item ≈ **~300K rows/brand/month**. Re-pulls do **not** add rows (upsert). Multi-brand scales **linearly**: e.g. FES-VN + LOF-VN at half-ceiling ≈ ~300K rows/month combined; all 7 brands at ceiling ≈ ~2.1M rows/month worst case. Alerts grow far slower (only on violations + daily `missing_*` keys), bounded by SKU count × active days, not order volume.

### Risks if order history / event-sourcing is added later

- **Child-row churn breaks naive history.** The current full-replace of `items` means you cannot retrofit per-line history by watching child rows — their `name`s are not stable. Any event-sourcing must key on `(external_order_id, external_line_id)`, not child row name. (Alerts already do this, so they're safe.)
- **Status-transition store would be a new write surface.** Moving from latest-snapshot to an append-only `EC Order Status Event` child/table is additive but changes growth math (every status change = a new row; cancelled orders often transition several times) and needs its own archive policy. Keep it **opt-in and separate** from the order row; do not convert the order table itself to event-sourced.
- **Idempotency must stay hash-gated.** Today `raw_payload_hash` makes unchanged re-syncs free. An event store must preserve that (only append on real change) or re-pulls will flood it.
- **Dedupe semantics are the contract.** Any history feature must not change `_create_alert` keys, or it will silently reopen/duplicate alerts. Treat C1/C2 keys as a frozen interface.

### Archive threshold / capacity monitoring

- **Measure-first, no archive code exists** (decision: capacity is monitored, not auto-pruned). `api_omisell.capacity_stats()` (SM-only) returns Log/Item/Alert/Action/Pause counts + `log_plus_item` vs a **2M-row archive REVIEW trigger** — a *review* prompt, not a delete.
- D.1 added composite indexes (`(brand, order_datetime)`, `(brand, status, detected_at)`) + search_index so per-brand reads stay fast at volume.
- **G1 surfaces this per brand**: the readiness table's order/item counts come from the same counts; the page can show the global `log_plus_item` vs the 2M trigger so capacity is visible during multi-brand rollout. Crossing 2M = schedule an archive-design decision (hot window + cold storage), still gated and separate.
- Hot-data assumption: ~6 months retained hot; archive design (when triggered) defines cold storage. No deletion without an explicit, separately-approved archive phase.

---

## Open questions for approval

1. Route name: `/alerts/integration-health` (proposed) vs `/alerts/brands` — pick one (the other can 301/alias).
2. Policy-coverage definition: "% of distinct SKUs seen in the last N days of orders that have an Active policy" — confirm N (default 30) and the warning threshold (default 50%). It's the only non-trivial query; I'll bound the sample (default 500 SKUs) to keep it cheap.
3. Stale-sync threshold default (45 min) — OK, or per-brand?
4. Confirm G1 stays **read + diagnose only** (no scheduler auto-write until G4). I recommend yes.
