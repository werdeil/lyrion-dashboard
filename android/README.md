# Lyrion Dashboard — Android app

A thin Android WebView wrapper around the Lyrion Dashboard app,
following the same principle as
[lms-material-app](https://github.com/CDrummond/lms-material-app): the whole
UI lives in the web page served by the Flask app, the Android app only
provides the native shell.

<img src="../docs/screenshots/dashboard-app.png" alt="Android app" width="240">

## Features

- Full screen WebView loading the dashboard
- Settings screen (server URL, keep screen on)
- Automatic discovery of the Lyrion Music Server on the local network
  (UDP broadcast on port 3483, the standard LMS discovery protocol); the
  suggested URL assumes Lyrion Dashboard runs on the same host on port 1111.
  Note: discovery cannot work while a VPN is active on the phone (UDP
  broadcasts do not cross the tunnel) — disable the VPN during discovery or
  enter the URL manually
- Keeps the screen on while the dashboard is displayed (configurable)
- Works over plain HTTP on the local network (cleartext traffic allowed)
- App menu (Settings / Reload / Quit) opened from the ⋮ button in the
  dashboard header; the back button/gesture behaves as usual (WebView
  history, then leaves the app)

## Requirements

- Android 8.0 (API 26) or newer
- A running Lyrion Dashboard instance reachable from the phone

## Building

With Android Studio: open the `android/` folder and run the `app`
configuration.

From the command line (requires the Android SDK, `ANDROID_HOME` set):

```bash
cd android
./gradlew assembleDebug
# APK in app/build/outputs/apk/debug/app-debug.apk
```

Debug builds use a distinct application ID (`.debug` suffix) and label
("Lyrion Dashboard (debug)"), so they install side by side with the signed
release app instead of refusing to install over it.

## CI builds

The GitHub Actions workflow `.github/workflows/android.yml`:

- builds a debug APK on every push touching `android/**` and uploads it as a
  workflow artifact;
- on a published GitHub release, builds a release APK and attaches it to the
  release. The APK is signed when the `ANDROID_KEYSTORE_BASE64`,
  `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` and `ANDROID_KEY_PASSWORD`
  repository secrets are configured, and unsigned otherwise.

Versioning: bump `versionCode` and `versionName` in `app/build.gradle.kts`
before releasing, then tag the release `vX.Y.Z` with the matching version.
The values are static in the source on purpose — F-Droid builds from the
tag and parses them from the gradle file — and the release workflow fails
if the tag doesn't match `versionName`. `versionCode` packs the semver as
`X*10000 + Y*100 + Z` (e.g. 0.1.0 → 100).

## F-Droid

The repo is F-Droid-ready: MIT license, FOSS dependencies only, static
versions parseable at each tag, and app-store texts under
`fastlane/metadata/android/`. To get listed, submit a packaging request
(https://gitlab.com/fdroid/rfp) or a merge request to
https://gitlab.com/fdroid/fdroiddata with a recipe using
`Repo: https://github.com/werdeil/lyrion-dashboard`, gradle subdir
`android/app`, `UpdateCheckMode: Tags` and `AutoUpdateMode: Version` —
the same setup as lms-material-app. New tags are then picked up and
built by F-Droid automatically.

To create a keystore and export it for CI:

```bash
keytool -genkeypair -v -keystore release.jks -alias lyrion \
        -keyalg RSA -keysize 2048 -validity 10000
base64 -w0 release.jks   # value for ANDROID_KEYSTORE_BASE64
```
