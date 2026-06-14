# Alert Center Phase B — Frappe Cloud Deploy + Verify Checklist

Date: 2026-06-07 · Status: **CHECKLIST ONLY — nothing pushed, nothing deployed.** Every push/deploy step below waits for your explicit go in the same turn (A33).

## 0. Current state (verified 2026-06-07 00:1x)

- `main` (local) = `584041d` "PM v2 G3" — **your own commit; G3 is already separated onto main by you.** Verified byte-identical to the G3 content I had recovered. → **Item 5/6 of your request is already done**: no cherry-pick needed anymore.
- `alerts-phase-b` = **`b16d30b`** = exactly **one commit on top of main**, containing only the 32 Phase B files (+1870). Re-created via `git commit-tree` (no working-tree touch) so the branch no longer carries a duplicate G3 commit. Content is byte-identical to the approved `5e4d6c1` (diff = 0); **the sha you approved now lives on as `b16d30b`** — same tree, parent rebased onto your G3. Old shas `4ab1cd3`, `cf0f5ba`, `5e4d6c1`, `e13aaaa` are dangling (harmless, recoverable, will be pruned by future gc).
- Working copy: on `main`. Two more OneDrive corruptions were found and fixed this session: zero-byte stale ref in `refs/heads/` and NUL-padded `.git/HEAD`.
- `origin/main` = `993bf1a` — your local `main` (with G3) is 1 commit ahead and **not pushed yet** either.

## 1. Git housekeeping (run on Windows, PowerShell — sandbox cannot unlink these)

```powershell
cd "C:\Users\admin\NextCommerce\Data - Documents\General\ERP Website\ecentric_workspace"
# 1. stale lock + corrupt-index leftovers
Get-ChildItem .git -Recurse -Force -File | Where-Object { $_.Name -like "*stale*" -or $_.Name -like "index.corrupt.*" -or $_.Name -eq "stale_trash_ref" } | Remove-Item -Force
# 2. health check (expect: clean output, no "broken"/"corrupt")
git fsck --connectivity-only 2>&1 | Select-String -NotMatch "dangling"
git status
git log --oneline -3 main; git log --oneline -2 alerts-phase-b
# expected: main=584041d (G3), alerts-phase-b=b16d30b (Phase B) -> 584041d
```
Dangling objects from the untangle are normal; do NOT run `git gc --prune=now` until after push (keeps recovery options).

## 2. Pre-push checks (Windows, OneDrive quiet — pause sync or close editors during git ops)

```powershell
# a. right branch + exactly the expected delta
git diff main alerts-phase-b --stat          # must be 32 files, +1870, all alerts/* + 3 known files
git show b16d30b --stat | Select-Object -First 8
# b. syntax check from the canonical blobs (not the working tree)
git stash -u 2>$null                          # only if dirty
git checkout alerts-phase-b
python -m py_compile ecentric_workspace/hooks.py ecentric_workspace/alerts/permissions.py
git checkout main                             # return; git stash pop if stashed
# c. no secrets: confirm no *.csv / api key material in the commit
git show b16d30b --name-only | Select-String -Pattern "csv|secret|key" # expect only api_key FIELD definitions in doctype json
```

## 3. Branch / merge recommendation

Push **from your Windows machine** (sandbox git is OneDrive-fragile):
```powershell
git push origin main                # ships PM G3 first (independent)
git push origin alerts-phase-b      # then the Phase B branch
```
Open GitHub PR `alerts-phase-b → main` (1 commit, easy review), **merge commit** (not squash — keeps the audited sha `b16d30b` in history). Alternatively fast-forward merge locally and push main — PR preferred for the review trail.

## 4. Frappe Cloud deploy steps

1. FC dashboard → your bench/site (`team.ecentric.vn`) → Apps → `ecentric_workspace` should show the new commit on its tracked branch (confirm the app tracks `main`; if it tracks another branch, adjust the PR target — report back before merging).
2. Click **Deploy/Update**. FC builds a new bench image and runs `migrate` during the update.
3. PM G3 note: if main is pushed before the PR merge, that FC deploy ships G3 alone first — fine and even preferable (isolates variables).

## 5. Migration verification (in FC deploy log)

- Build succeeds; migrate step shows no traceback.
- Look for fixture sync (`Custom Field` updated) and DocType creation; absence of `Module Alerts not found` (would mean modules.txt didn't ship — abort and report).
- Site stays up; open any existing page (`/home`, `/pm`) → unchanged (Phase B must be invisible).

## 6. Post-deploy DocType verification (read-only)

As Administrator in Desk:
- Search "EC Alert" → 8 DocTypes exist, module **Alerts**, all `track_changes` on (DocType → Track Changes checkbox).
- `Brand Approver` form shows **KAM Owner** field right after Manager Email; list view shows the column.
- New DocType list views open empty, no errors.

⚠️ Snapshot script caveat: `snapshot_live_state.ps1` lists `custom=1` DocTypes only — the 8 app-owned DocTypes will NOT appear in `custom_doctypes_list.json`. Verify via API instead (read-only):
```powershell
# expect 200 + "module":"Alerts"
GET /api/resource/DocType/EC Alert?fields=["name","module","track_changes"]
```
(Phase F backlog: extend snapshot script with an `app_doctypes_list` section for module=Alerts.)

## 7. Permission verification (read-only probes)

With a **non-System-Manager** test user's token/session:
- `GET /api/resource/EC Alert` → expect **403 PermissionError** (Desk lockdown works).
- `GET /api/resource/EC Brand Integration Settings` → **403** (credential isolation).
- Desk search as that user: "EC Alert" not accessible.
With Administrator: both return 200/empty list. Confirm no existing DocType's permissions changed: spot-check `MSO Request` / `GBS Sales Order` behavior unchanged for a normal user.

## 8. `/alerts` access verification

**No page exists in Phase B** (frontend is Phase E). Verify `https://team.ecentric.vn/alerts` returns 404/not-found — anything else would mean a route collision (report it). Service-layer `permissions.py` has no whitelisted endpoints yet, so there is no API surface to probe beyond §7.

## 9. Post-deploy data step (needs your input)

Fill `kam_owner` on the 7 Brand Approver records (Desk, 2 minutes) — or send me the brand→KAM list and I seed it (production write → per-turn confirmation). Until filled, owner resolution falls back to manager_email/leader_email, which works but mislabels daily ownership.

## 10. Rollback plan

All additive; no destructive path exists.
1. **App code:** revert the PR merge commit on `main` (GitHub "Revert") → FC Deploy again. PM G3 unaffected (separate commit).
2. **Schema:** the 8 DocTypes + kam_owner field may stay harmlessly (invisible to non-SM, no jobs, no UI, no data). Physical removal only with explicit approval (`bench remove-doctype` equivalent is destructive — not proposed).
3. **Nothing else to disable:** no scheduler entries, no endpoints, no page, no credentials stored yet, dry-run flags default 1 by schema.
4. Keep any created records for audit (none expected in Phase B).

## 11. Process guardrails (your directive 2026-06-07, now standing rules)

Logged to project memory: confirm current branch before every commit; never two writers on the same working tree at once (you commit ↔ I work: coordinate in chat first); one active branch/task at a time; sandbox treats all git state as suspect after OneDrive sync (verify blobs with `git show`, mv stale locks, never trust mount reads of files you just edited).
