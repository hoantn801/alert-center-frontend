# Alert Center — G1.1 Price-Basis Mapping Inspection (pre-commit gate)

Date: 2026-06-08 · Status: **G1.1 NOT committed. Mapping inspected from code + golden file; one item needs a REAL capture to fully confirm.** Read-only; no Omisell write; DS1 locked.

Sources inspected: `services/omisell_normalizer.py` (the live mapping) and `tests/golden/omisell_order_detail.json` (a **sanitized placeholder**, shaped from developers.omisell.com docs — explicitly "replace with a real T2 capture").

---

## What the raw Omisell order-detail item actually carries

Per `catalogue_items[]` the payload (docs/placeholder) has these price fields:
`original_price`, `discounted_price`, `discount_seller`, `discount_platform`, `voucher_seller`, `voucher_platform`. Order-level: `payment_information[].transaction_amount`.

Placeholder arithmetic (SKU-A): `original 120000 − discount_seller 10000 − discount_platform 5000 − voucher_seller 6000 − voucher_platform 0 = 99000 = discounted_price`; and `discounted_price × qty` summed = `transaction_amount 207900`. So in the documented shape, **`discounted_price` is the final per-unit customer price net of all four seller/platform discount+voucher layers.**

The current normalizer (`normalize_order_detail`) reads all four but **collapses** them:
```
seller_discount   = discount_seller + voucher_seller        # product seller disc + seller/shop voucher, SUMMED
platform_discount = discount_platform + voucher_platform     # platform disc + platform voucher, SUMMED
unit_check_price  = discounted_price                         # carried as payload fallback
customer_paid_price = None                                   # (transaction_amount is order-level)
```

---

## Answers

**Q1 — Does `seller_discount` include seller/shop voucher, or only product-level seller discount?** It includes **both** — `seller_discount = discount_seller + voucher_seller`. So seller/shop voucher IS already inside it, but summed together with the product-level seller discount.

**Q2 — Are seller/shop vouchers stored separately anywhere?** **No.** `voucher_seller` is available in the raw payload but the normalizer adds it into `seller_discount`; the individual `discount_seller` vs `voucher_seller` split is **not persisted** (lost after summation). Same for `discount_platform` vs `voucher_platform`.

**Q3 — Does `platform_discount` include all platform-funded discounts incl. platform voucher?** It includes `discount_platform + voucher_platform` only. The order-detail item payload (docs/placeholder) has **no separate fields** for platform campaign subsidy, coins/points, or shipping voucher — so those layers are **not captured** today (they may be folded into `discounted_price`, or live elsewhere in the payload we don't read, or not exist per item). **Cannot confirm without a real capture.**

**Q4 — Does Omisell provide a reliable final customer-paid item price?** Per the documented shape, **`discounted_price` IS the final net unit price** (original − all four layers, and × qty = transaction_amount). BUT today `customer_paid_price` is set to `None` and `discounted_price` is only used as a last-resort fallback, and its semantics are **Q-D5 PROVISIONAL** because the golden file is a placeholder, not a real order. **So: probably yes via `discounted_price`, but UNCONFIRMED until a real T2 capture.**

---

## Proposed amendment (Q5/Q6) — ready to implement, pending confirmation

Stop collapsing; carry every layer through normalizer → ingestion → Order Item + Occurrence so each brand can choose its basis and the audit shows exactly what was netted.

**Audit fields (Order Item + Occurrence):** `product_discount` (=discount_seller), `seller_voucher_discount` (=voucher_seller), `seller_funded_total_discount` (=product_discount+seller_voucher_discount), `platform_discount` (=discount_platform, product-level platform), `platform_voucher_discount` (=voucher_platform), plus the existing `effective_check_price`, `price_basis_used`, `list_price`, `seller_funded_price`, `platform_included_price`, `customer_paid_price`. (Keep the legacy summed `seller_discount`/`platform_discount` columns for back-compat.)

**Per-unit candidates:**
- `product_discount_only` = list − product_discount  (excludes seller voucher)
- `seller_funded_all`     = list − product_discount − seller_voucher_discount  (= today's seller_funded)
- `seller_plus_platform`  = list − all seller − all platform discount+voucher
- `customer_paid`         = `discounted_price` (the documented final net price) — once confirmed reliable
- `strictest`             = lowest available candidate

**`EC Brand Alert Config.price_eval_basis` options become:** `product_discount_only` / `seller_funded_all` / `seller_plus_platform` / `customer_paid` / `strictest` (default `seller_funded_all` = legacy behavior). This directly supports "some brands check only seller-funded; others check final customer-checkout incl. shop/platform vouchers."

---

## Confirmation gate (why not commit yet)

The golden file is a **placeholder**, so before finalizing we must confirm against ONE real order:
1. Run (read-only) `pull_one_order(brand="FES-VN", omisell_order_number="<a real order>", capture_golden=1)` → it returns the **sanitized** raw payload. Save it over `tests/golden/omisell_order_detail.json`.
2. Confirm on the real payload: (a) the exact field names (`discount_seller`/`voucher_seller`/`discount_platform`/`voucher_platform`), (b) whether `original − the four = discounted_price` actually holds, (c) whether **extra layers** exist (platform campaign subsidy, coins/points, shipping voucher) as separate fields — if so we add candidates for them, (d) whether `discounted_price` is truly the customer-checkout price (so `customer_paid` is reliable).
3. If the real payload matches the documented shape → implement the amendment above as-is. If it reveals extra layers → extend the candidate set first.

**Recommendation:** capture one real FES-VN order now (read-only), confirm the four findings, then I implement the granular split + basis options and we commit G1.1 together. Holding the commit as you directed.

(Independent of this, the rest of G1.1 backend — Case/Occurrence model, bulk actions, Policy/Rule cleanup — is implemented and unaffected by the basis-granularity decision; it will simply carry whichever audit fields we finalize here.)
