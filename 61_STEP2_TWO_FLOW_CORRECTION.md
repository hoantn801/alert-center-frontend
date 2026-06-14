# 61 — Step 2 correction: two-flow ToDo (Incident per-case + Setup per-brand)

Date: 2026-06-13 · Status: DESIGN / ARCHITECTURE REVIEW. **No code rewritten, nothing committed.** Supersedes the single-flow Step 2 (doc 60) which created one ToDo per case incl. missing_policy — that conflicts with the locked UX (Cần xử lý / Thiếu thiết lập / Đã xử lý). Step 2 single-flow `case_todo.py` is **on hold**, not committed.

## 1. Rule classification (which flow)

| rule_code | Flow | ToDo |
|---|---|---|
| `possible_missing_zero` (missing_zero) | **A Incident** | per-case |
| `severe_price_drop` (severe_drop) | A Incident | per-case |
| `below_min` | A Incident | per-case |
| `above_high` | A Incident | per-case |
| `missing_brand_mapping` | A Incident (data incident needing KAM) — but usually brand-less → no owner → no ToDo + diagnostic | per-case if owner |
| `missing_policy` | **B Setup** | aggregated per brand |
| `missing_integration_credential`, `ingestion_api_failed`, `stock_lock_api_failed` | **None** (System Manager concerns, not KAM) | no ToDo |

`INCIDENT_RULES = {possible_missing_zero, severe_price_drop, below_min, above_high, missing_brand_mapping}` · `SETUP_RULES = {missing_policy}` · others → no ToDo.

## 2. Flow A — Incident ToDo (per Alert Case)

One open ToDo per active incident case (unchanged from the locked ToDo audit, just gated to `INCIDENT_RULES`):
- reference_type = `EC Alert`, reference_name = case, allocated_to = case.owner_user.
- Open/In Review → exactly one open ToDo (idempotent). Closed/Ignored/Cancelled → close assignment. New violation after terminal → new case → new ToDo, old never reopened. Owner change while active → reassign (close old + add new).
- No owner → no ToDo + diagnostic; case still visible to Admin/Manager.
→ feeds UI **"Cần xử lý"**; closed → **"Đã xử lý"**.

## 3. Flow B — Setup ToDo (aggregated per brand) — REFERENCE MODEL PROPOSAL

**Problem:** an aggregated brand-level setup ToDo is NOT tied to one EC Alert. Using an arbitrary missing_policy case as the reference is wrong (that case can be closed independently).

**Proposed reference model (recommended): `reference_type = "Brand Approver"`, `reference_name = <brand>`.**
- Brand Approver is the brand source-of-truth record (already holds `kam_owner`; `brand_resolver` resolves owners from it). It is a real, stable, Frappe-native doctype on the site (defined in the approval app; EC Alert already Links to it).
- One setup ToDo per brand points at the brand's own config record — stable across individual cases/SKUs.
- Discriminator (since a Brand Approver could host other assignments): a stable marker in `description`, e.g. prefix `[price_setup_missing]`, plus filter `reference_type="Brand Approver"` + `reference_name=brand` + `allocated_to=brand_kam` + `status="Open"` + description LIKE the marker. Identity = that one ToDo.
- allocated_to = brand KAM (`resolve_owner(None, brand)`).

**Alternatives considered:**
- (B2) Dedicated `EC Brand Setup Task` DocType → cleanest semantics but **needs a migration** + new DocType; rejected for Step 2 (zero-migration goal). Revisit if Setup needs its own fields/state.
- (B3) Reference a synthetic key on EC Brand Integration Settings or EC Brand Alert Config → those are integration/price-config records, less semantically "the brand"; Brand Approver is the canonical brand record. Rejected.

→ **Decision needed (Q-S2-B): use Brand Approver as the setup-ToDo reference?** (recommended) — see question below.

### Flow B behavior

- **Remaining-count source:** distinct `seller_sku` among ACTIVE (`Open`/`In Review`) `missing_policy` EC Alert cases for the brand: `SELECT COUNT(DISTINCT seller_sku) FROM tabEC Alert WHERE brand=%s AND rule_code='missing_policy' AND status IN ('Open','In Review')`.
- missing_policy case insert (active) → recompute remaining; ensure ONE open setup ToDo for the brand; update its description to "Thiếu thiết lập giá: N SKU — mở Price Setup" (+ link/route to Price Setup).
- missing_policy case → terminal → recompute remaining; if 0 → **close** the setup ToDo; else update description (new N).
- Reuse: repeated missing_policy cases update the SAME open brand ToDo (no per-case/per-SKU ToDo).
- After closed, if missing setup reappears → **new** setup ToDo (never reopen the closed one — find only `status="Open"`; a closed/cancelled one is ignored).
- Keep historical ToDo records (close, never delete).
→ feeds UI **"Thiếu thiết lập"** (one row per brand with a count).

## 4. Frappe v15 signature gate (BLOCKER — owner must run on bench/staging)

Sandbox has **no frappe installed** (verified: `import frappe` fails, no `assign_to.py`, no pip) → I cannot `inspect.signature` the live API here. Per your gate, run this READ-ONLY inspection on the bench/staging and return output:

```python
import inspect
from frappe.desk.form import assign_to
print("add:", inspect.signature(assign_to.add))
print("remove:", inspect.signature(assign_to.remove))
print("close_all_assignments:", inspect.signature(assign_to.close_all_assignments))
```
(or: `bench --site <site> console` then paste; or `bench --site <site> execute frappe.desk.form.assign_to.add` won't show sig — use console.)

**Working assumption (v15, to be CONFIRMED — calls will be adjusted to the returned signatures, not wrapped in try/except as a contract substitute):**
- `add(args=None, *, ignore_permissions=False)` — `args` dict keys: `doctype, name, assign_to(list), description, date, priority, notify, ...`. Returns assignment list.
- `remove(doctype, name, assign_to, ignore_permissions=False)`.
- `close_all_assignments(doctype, name, ignore_permissions=False)` (the `ignore_permissions` kwarg was added in v15; older = `(doctype, name)`).

Once you return the three signatures, I lock the exact call sites (drop the defensive try/except fallback that was standing in for the contract).

## 5. Test plan (10 required)

Incident: (1) new incident case → 1 ToDo; (2) extra occurrences → no dup; (3) reassign on owner change; (4) terminal closes; (5) new case after terminal → new ToDo.
Setup: (6) 20 missing_policy cases / one brand → ONE setup ToDo; (7) remaining count updates, no dup; (8) zero remaining → close setup ToDo; (9) future missing setup → new ToDo, not reopen old; (10) different brands → separate setup ToDos.
Plus retained: recursion guard, fail-open, controller-syncs-only-on-change. In-memory fakes for assign_to + a count stub (no DB); bench-gated class for the real round-trip.

## 6. Recursion guard + fail-open — RETAINED

Both flows go through one `sync_todo(case)` with the thread-flag recursion guard (`frappe.flags._ec_alert_todo_syncing`) + full try/except fail-open + diagnostic (brand/case/owner/error). The setup flow's description-update is a ToDo write (not an EC Alert save) so it won't re-enter the EC Alert controller; the guard still wraps it.

## 7. What I will build after approval

1. Rewrite `services/case_todo.py`: dispatch by rule → `_sync_incident(case)` (Flow A) / `_sync_brand_setup(brand, owner)` (Flow B) / none. Setup helpers: `_remaining_missing_skus(brand)`, `_find_open_setup_todo(brand)`, `_ensure_setup_todo`, `_close_setup_todo`. Calls adjusted to the CONFIRMED signatures.
2. `ec_alert.py` controller hooks unchanged in shape; `sync_todo` dispatch updated. missing_policy case terminal must still trigger a recompute → on_update already fires on status change. ✓
3. `tests/test_case_todo.py`: replace with the 10-case two-flow suite.
4. Still **zero migration** (Brand Approver reference + description marker; no new field). If you prefer the dedicated DocType (B2), that adds a migration — your call.

## Gates before coding
- **Q-S2-B**: approve Brand Approver as the setup-ToDo reference (vs dedicated DocType).
- **Signatures**: return the 3 `inspect.signature` outputs from bench.

No commit / deploy / migrate / Step 3 until both are resolved.
