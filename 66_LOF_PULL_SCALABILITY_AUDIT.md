# 66 — LOF Omisell order-pull scalability: incident audit

Date: 2026-06-13 · AUDIT ONLY. No code. Read from real source (`api_omisell.py`, `services/omisell_client.py`, `services/ingestion.py`).

## Answers to the 10 questions

### 1. How often is `/api/v2/auth/token/get/` called?
**Designed: only when the cached token is missing or within 2 min of expiry** (`_ensure_token`, omisell_client L137-142). **In practice for LOF: almost certainly PER REQUEST** — see Q4/Q5. The auth POST timing out mid-run on one specific order proves `_ensure_token` is re-authenticating during the order-detail loop, not once at run start.

### 2. Exact call path
`tasks.scheduled_omisell_pull` → `frappe.enqueue(pull_recent_job)` → `pull_recent_job(brand)` splits `[last_sync_at − overlap, now]` into ≤1h chunks → for each chunk `pull_orders(brand, cf, ct)` → `client = OmisellClient(bis.name)` (one client per chunk) → list phase `client.get_orders()` (paged) then detail phase `client.get_order_detail(number)` per order → each call → `_request(auth=True)` → `_headers()` → **`_ensure_token()`** → reuse cached `bis.token` OR `_authenticate()` → `_request("POST", "/api/v2/auth/token/get/", auth=False)`.

### 3. Where is the token cached?
**In the DB** — on `EC Brand Integration Settings`: `bis.token` (Password field) + `bis.token_expired_at` (Datetime), persisted via `bis.save()` (L159-162). Shared across workers/runs via the DB row. NOT process-local, NOT Redis. (`self.bis` is loaded once per `OmisellClient`; `_ensure_token` reads the in-memory copy.)

### 4. Real expiry / refresh policy
`token_expired_at = datetime.fromtimestamp(int(data["expired_time"]))` — set **only if Omisell returns `expired_time`** (L160-161). Refresh = `_ensure_token` re-auths when `not (token and exp and exp > now+2min)`. **PRIME SUSPECT:** if Omisell's token response has **no `expired_time`** (or it isn't persisting), `token_expired_at` stays NULL → the guard `token and exp and …` is False on every call → **`_authenticate()` runs on EVERY request** = one auth POST per order + per list page. This doubles API calls (auth POST + data call per order) and is the most likely cause of 692-793s for 249-303 orders (~2.8 s/order = two paced calls each). Also no clock-skew/margin handling beyond 2 min.

### 5. Why zero retries on token acquisition?
The timeout retry in `_request` is **GET-only** by explicit design (omisell_client L192: `if method == "GET" and attempt_timeout < len(BACKOFFS_TIMEOUT)`). The auth call is a **POST**, so it falls straight through to `raise OmisellError("TIMEOUT on POST … after 0 retries")`. Rationale in the code: "a timed-out POST may have succeeded server-side." That rationale is wrong for the auth token exchange — it is effectively a read (credentials → token), idempotent and safe to retry; re-POSTing just returns a (new) valid token. So the GET-only guard accidentally left the most critical call (auth) with zero resilience.

### 6. Does one order failure make the whole chunk incomplete and hold the checkpoint?
**YES.** `pull_orders` advances `last_sync_at` ONLY when `summary["failed"] == 0 AND not capped_at AND not timeboxed` (L415). Any of: ≥1 failed order (detail/auth/ingest), `capped_at` (listed > 300), or `timeboxed` → `last_sync_at_advanced=False` → **checkpoint held**. Next scheduled cycle re-scans `[held_last_sync − overlap, now]`. Because `now` keeps advancing while `last_sync_at` is frozen, **the window GROWS every cycle** → more orders → guaranteed to hit cap/timeout again → permanent replay (death spiral). High-volume brands (LOF lists 249-303/window, cap 300) can essentially never advance.

### 7. How does dedupe protect repeated orders during a held checkpoint?
**Fully idempotent at the data layer** (`ingestion.ingest_orders`): upsert by `order_key = source|external_order_id` (UNIQUE); a re-listed order is `unchanged`/`updated`, never duplicated. `EC Alert Occurrence` dedupe key is per order/line. So the replay **wastes time + Omisell rate quota** but does not corrupt data. The cost is purely runtime + quota, not duplicates.

### 8. Why 692-793 s for only 249-303 orders?
Per-order cost ≈ 2.8 s. Contributors: `MIN_INTERVAL = 1.0 s` minimum between calls; `THROTTLE_AT = 70` of the 100-call/min bucket → a hard `time.sleep(5)` whenever the rate header exceeds 70 (frequent at sustained ~1/s); the single **60 s auth timeout** (zero-retry); and — the multiplier — **a re-auth POST per order** when `token_expired_at` is NULL (Q4), i.e. ~2 paced calls per order instead of 1. 249 orders × ~2 paced calls × (1 s + throttle) + one 60 s stall ≈ 692 s.

### 9. Current cap / page / budget — can high-volume brands progress?
- `MAX_DETAILS_PER_RUN = 300` (per-run detail cap), `MAX_LIST_PAGES = 20`, `MAX_WINDOW_SECONDS = 3600` (1h chunks), `JOB_TIME_BUDGET = 3000 s`, per-chunk budget = `3000 / len(chunks)`. `MAX_OVERLAP_CHUNKS = 12`. `CIRCUIT_BREAKER_LIMIT = 3`.
- **No, high-volume brands cannot reliably progress.** The cap is all-or-nothing: when a window has > 300 orders, `capped_at` holds the checkpoint, so the next window (now larger) caps again. There is **no sub-window / partial-progress checkpoint**. Worse: a **capped-only** cycle (failed=0) does **not** increment the circuit breaker (breaker only counts cycles with `summary["failed"]`), so the cap-replay loop has **no auto-stop** and burns quota indefinitely. A failed cycle (like the current one, failed=1) does increment → breaker opens after 3 and refuses LOF (a stop, but the wrong kind — it halts LOF entirely until manual reset).

### 10. Smallest safe production hotfix (proposal — code later)
Three minimal, independent changes (no scheduler semantics rewrite, no catalogue/ToDo/case/PM/stock touch):

**A. Make the auth token resilient + truly per-run (fixes Q4/Q5/Q8).**
- Allow **bounded retry/backoff for the auth POST** on timeout/5xx (it is an idempotent read of credentials; retrying is safe). e.g. reuse `BACKOFFS_TIMEOUT`/`BACKOFFS_5XX` for the auth path.
- When Omisell returns **no `expired_time`, set a conservative TTL** (e.g. `now + ec_alerts_omisell_token_ttl_minutes`, default ~30 min, with the existing 2-min safety margin) so `_ensure_token` reuses the token instead of re-authing every call. → one token per brand/run, ~half the API calls.

**B. Stop one transient failure from holding the entire completed window (fixes Q6 death-spiral).**
- A small number of **transient detail/auth failures must not freeze the checkpoint forever.** Minimal option: when the list window was fully fetched and only ≤N orders failed, **record the failed order numbers into the existing poison-pill list** (`ec_alerts_pull_skip_orders`) / a targeted-retry list + the existing `ingestion_api_failed` alert, then **advance the checkpoint** (the failed orders are preserved for `pull_one_order` targeted re-pull, not lost). Keeps idempotent dedupe.

**C. Let high-volume brands make forward progress under the cap (fixes Q9).**
- When `capped_at` trips, advance the checkpoint **only through the provably-completed boundary** — process the window in **time-ordered sub-windows** and advance per fully-completed sub-window (so the next cycle starts after the processed portion instead of replaying it). Smallest variant: raise the detail cap with a strict runtime bound, OR shrink the scheduled chunk so each completed chunk advances. Also make **capped/timeboxed cycles count toward a progress watchdog** so an endless cap-replay is detectable/stoppable.

Recommended first PR = **A + B** (smallest, directly kills the current incident: removes the per-order re-auth + the zero-retry auth timeout, and stops a single transient failure from replaying 243 orders). **C** as a fast follow for sustained LOF volume.

## Operational: finish vs pause (no force-unlock, no deploy)

- **Let the current run finish.** It is idempotent (dedupe), performs **no Omisell/stock writes**, and `running_since` is a real run — force-unlocking risks a concurrent run and a half-written checkpoint. Boxme 404s are unrelated.
- **To stop the replay loop safely before the hotfix**, the clean pause is a **config change, not a force-unlock**: remove `LOF-VN` from site_config `ec_alerts_scheduled_pull_brands` (e.g. leave `["FES-VN"]`). This cleanly halts LOF scheduled pulls (the per-brand gate in `tasks.scheduled_omisell_pull`) while FES-VN keeps running. Re-add LOF after deploying A+B. No code, no lock surgery.
- **Check the breaker:** read `consecutive_failures` on the LOF `EC Brand Integration Settings`. If it has reached 3, the breaker is already refusing LOF (auto-stop) and will need a manual reset to 0 **after** the hotfix — not before.
- **Do not** raise the detail cap or read_timeout as a "fix" — that lengthens each doomed replay.

## Constraints honored
Audit only. Proposal does not touch catalogue sync, Alert Case lifecycle, ToDo, PM, Omisell stock, or any remote write. Await review before coding.
