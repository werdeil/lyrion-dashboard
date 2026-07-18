---
name: release
description: >-
  Cut a release of the Lyrion Dashboard. Use this whenever a task is about
  shipping a new version — bumping the version, tagging, the Release workflow,
  or how the Android APK gets built and attached. Covers the single source of
  truth for the version, the manual `Release` → publish → `android.yml` chain,
  the versionCode packing, and the F-Droid constraint that keeps versions
  static in source. Reach for it before touching `VERSION`, `release.yml`, or
  the Android `versionName`/`versionCode`.
---

# Cutting a release

Releases are **cut manually** from the GitHub UI, not on every merge. The flow
is deliberately two-step: a workflow prepares a *draft*, a human publishes it,
and publishing triggers the APK build.

## The version, and its two mirrors

The semantic version lives in **three** places that must agree, and the release
workflow is what keeps them in sync:

1. `VERSION` (repo root) — the **single source of truth** for the web app.
   `config.py` reads it at import and exposes it on `/health`.
2. `android/app/build.gradle.kts` — `versionName` (the semver) and
   `versionCode` (an integer). These are **static literals on purpose**: F-Droid
   builds from the source at the tag and parses them from this file, so they
   must be committed, not computed at build time.
3. The git tag `vX.Y.Z`.

`versionCode` packs the semver as **`X*10000 + Y*100 + Z`** (e.g. `0.2.1` →
`201`, `1.0.0` → `10000`). Keep that formula — the Release workflow and the
gradle comment both rely on it.

## The Release workflow (`.github/workflows/release.yml`)

Triggered by `workflow_dispatch` with inputs `version` (X.Y.Z, no leading `v`)
and `prerelease`. It:

1. Validates the version is semver and the tag doesn't already exist.
2. Bumps `versionCode`/`versionName` in `build.gradle.kts` (via `sed`, failing
   loudly if nothing changed) and writes `VERSION`.
3. Commits `chore(release): vX.Y.Z`, tags `vX.Y.Z`, pushes both.
4. Opens a **draft** GitHub release with auto-generated notes (`--generate-notes`).

It stops there. Nothing is published automatically.

## Publishing → the APK (`.github/workflows/android.yml`)

Publishing the draft fires `android.yml` on `release: published`, which:

- Re-checks the tag matches `versionName` in `build.gradle.kts` (F-Droid
  coherence guard) — a mismatch fails the job.
- Builds the **release APK**. It is **signed** only when the repo secrets
  `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`,
  `ANDROID_KEY_PASSWORD` are configured; otherwise it builds unsigned.
- Attaches `lyrion-custom-data-vX.Y.Z.apk` to the release.

`android.yml` also builds a **debug** APK on every push touching `android/**`
(uploaded as a workflow artifact, not attached to a release).

## Doing a release

1. Decide the new `X.Y.Z`.
2. Run the **Release** workflow (Actions → Release → Run workflow) with that
   version; tick prerelease if applicable.
3. Review the auto-generated notes on the resulting **draft** release, edit if
   needed, then **Publish**.
4. Confirm `android.yml` ran and the signed APK is attached.

Prefer this path over hand-editing versions: doing it manually risks the three
mirrors drifting, which the F-Droid coherence guard will reject at release time.
If you must bump by hand (e.g. prepping a PR), change **all three** consistently
and keep the `versionCode` packing formula.

## Checklist

- [ ] Version bumped in `VERSION` **and** `versionName`/`versionCode` in
      `android/app/build.gradle.kts`, with `versionCode = X*10000 + Y*100 + Z`.
- [ ] Tag `vX.Y.Z` matches `versionName` (else `android.yml` fails).
- [ ] Release cut via the workflow, reviewed as a draft, then published.
- [ ] Signed APK attached (signing secrets present) — verify on the release.
