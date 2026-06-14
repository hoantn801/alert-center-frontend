# Stock Safety Lock — Buffer-Stock Mechanism (Decision DS1)

Date: 2026-06-08 · Status: **BINDING design update from user — supersedes all earlier "set available stock to 0" wording.** Design-only: no code/schema change yet; real execution remains Dry Run-gated.

## 1. The mechanism (corrected)

Omisell has three stock concepts: **actual/physical stock**, **incoming/pending stock**, **buffer (reserved) stock**. Marketplace **available = actual − buffer** (per Omisell's model).

Stock Safety Lock must **only touch buffer stock**:
- ❌ never off/delist listing · ❌ never set actual/physical stock to 0 · ❌ never overwrite real stock.
- ✅ **set/increase buffer stock to lock the sellable quantity** → available drops to 0, physical stock untouched.

Example: actual 50, buffer 0 → available 50. Lock: buffer → 50 → available 0, actual still 50.

Terminology rule: everywhere we said "set available stock to 0", read "**set/increase buffer stock to lock sellable quantity**". Action name stays **Stock Safety Lock**; the implementation target is Omisell buffer stock.

## 2. Audit fields — EC Alert Action (additive schema change, NOT yet applied)

To add via app-owned DocType JSON in the next approved schema window (Phase D or a small pre-D batch):

| Field | Type | Meaning |
|---|---|---|
| `actual_stock_before` | Float | physical stock at lock time (read, never written) |
| `available_stock_before` | Float | sellable qty at lock time (existing `previous_available_stock` keeps backward-compat; new field is the canonical name going forward) |
| `buffer_stock_before` | Float | buffer before lock |
| `buffer_stock_after` | Float | buffer we set/computed |
| `locked_quantity` | Float | sellable qty actually locked (= buffer_after − buffer_before in delta terms) |
| `release_required` | Check | lock must eventually be released |
| `release_strategy` | Select: `Restore Previous Buffer` / `Reduce By Locked Quantity` / `Manual` | depends on Omisell API semantics (gate item 3) |

## 3. Release logic (audited, never blind)

Never blind-set stock. Release = restore `buffer_stock_before` **or** reduce buffer by `locked_quantity` — choice fixed by whether Omisell's buffer update is absolute-set or delta (gate item 3). Every release writes: who/when/strategy/values-before-after into the action (`release_status`, `executed_*`, audit fields) — same dedupe/no-delete rules as locks. Future auto-release still requires price re-check first (existing rule unchanged).

## 4. Phase D gate — buffer-stock API confirmation (replaces old checklist items 10–12)

Before ANY real Stock Safety Lock execution, Omisell must confirm:
1. Read **actual, available, and buffer stock** by SKU / warehouse / pickup_id.
2. Update **buffer stock specifically** (not general stock overwrite).
3. Buffer update semantics: **absolute set or delta adjustment**?
4. Update granularity: per warehouse / pickup_id, per shop, or per SKU?
5. Sample request/response for buffer stock update (incl. error cases).
6. Sandbox or a safe test SKU.

Until all 6 confirmed: lock actions stay **Dry Run only**; real order ingestion may proceed separately (its own gate, checklist §1); real buffer-stock write stays locked (kill switch + dry_run flags + no HTTP code, unchanged).

## 5. Code touchpoints when implemented (inventory for the future Phase D plan — nothing changed today)

- `services/stock_lock executor` (future): read stocks → write audit fields → buffer update → verify available=0.
- `services/action_queue.py`: Dry Run `api_response` text currently says "would set available stock to 0" — **terminology fix to "would set/increase buffer stock to lock sellable quantity (locked_quantity=N)"** — batch with the next app deploy, not worth a solo deploy.
- `EC Alert Action` JSON: +7 fields (§2).
- `release` flow: per §3, still manual-only at first.
- UI drawer (Phase E page): show audit fields once they exist.
