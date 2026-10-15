# PyreVixen update runbook

How to ship a new PyreVixen release when Mozilla ships a new Firefox. The
goal: **a signed PyreVixen release within days of Mozilla's release.**

## 1. Bump VERSION

Edit the [VERSION](VERSION) file to the new Firefox release number
(e.g. `158.0` → `159.0`). One line, no whitespace. Commit to `main` —
`build.yml` triggers on VERSION changes automatically.

## 2. Run the rebase check, fix failing patches

Check the latest
[rebase-check](../../actions/workflows/rebase-check.yml) run (or trigger it
manually with workflow_dispatch). It dry-runs every patch against the new
source and reports PASS/FAIL per patch.

Fix failures in this order — these two drift the most:

1. **Branding** (`patches/010-branding.patch`) — resource paths and
   `AndroidManifest.xml` churn almost every release.
2. **Privacy defaults** (`patches/050-privacy-defaults.patch`) — Mozilla
   adds new prefs and telemetry hooks regularly; every new one needs a
   default-off (or removal) decision.

Then work through the rest numerically (020 → 080). Re-run the rebase check
until every patch applies cleanly.

## 3. Re-run the full TESTING.md gate — no gate, no release

Build the APKs (`build.yml` on `main`, or `scripts/build.sh` locally), then
check **every** box in [TESTING.md](TESTING.md) on those exact APKs.
Anything waived goes into the release notes under "Known issues" with its
reason. A release that skips the gate does not ship. Period.

## 4. Ship the signed release

Merge to `main` (if not already there) — `build.yml` signs with the CI key
and publishes the GitHub Release with APKs, `SHA256SUMS`, and rendered
release notes.

**If the release is delayed** (patches need work, the gate found problems),
say so in the release notes of the shipped version instead of quietly
shipping an old base — e.g. "Note: this release trails Firefox N by X
days while patch 050 was rebased." Users deserve to know what base they're
on.

---

## ⚠️ SIGNING-KEY BACKUP WARNING

**The release signing key is stored in CI secrets AND in two offline
backups (e.g. two encrypted USB drives in different locations). Losing the
key forces a FRESH REINSTALL for every user — Android will not install an
update signed with a different key, and there is no recovery path.**

- Never commit the key or its passwords to the repo (release.sh refuses to
  work any other way — env/CI secrets only).
- After generating a new key, verify BOTH offline backups restore correctly
  before deleting the original.
- If a backup is ever suspected compromised, rotate the key and announce a
  manual reinstall — do not quietly keep signing.
