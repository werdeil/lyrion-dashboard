# Lyrion Dashboard — Android app

A thin Android WebView wrapper around the Lyrion Dashboard app,
following the same principle as
[lms-material-app](https://github.com/CDrummond/lms-material-app): the whole
UI lives in the web page served by the Flask app, the Android app only
provides the native shell.

<img src="../docs/screenshots/dashboard-app.png" alt="Android app" width="240">

The Gradle project has two modules: `app/` (the phone app described here)
and `wear/` (a Wear OS companion, see [below](#wear-os-companion-wear)).

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
  dashboard header; the back button/gesture simply leaves the app

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
# Phone APK in app/build/outputs/apk/debug/app-debug.apk
# Watch APK in wear/build/outputs/apk/debug/wear-debug.apk
```

## Wear OS companion (`wear/`)

A small native watch app (Compose for Wear OS — a WebView is not available
on watches) that shows only the lyrics of the track currently playing,
karaoke-style when they carry LRC timestamps.

- **Standalone**: the watch polls `/now-playing.json` on the Lyrion
  Dashboard server directly every 5 s and extrapolates the playback
  position locally between polls, exactly like the web page does. No
  phone-side component is involved; when the watch has no Wi-Fi, Wear OS
  transparently proxies the HTTP requests through the paired phone's
  Bluetooth connection.
- **Synced lyrics first**: LRC lyrics from the library are highlighted
  line-by-line and auto-centred. When the library has no synced lyrics,
  the app asks the dashboard's web fallback (`/lyrics.json`) once per
  track; plain lyrics are shown as scrollable text.
- **Settings**: on first launch (or with a long-press on the lyrics
  screen) set the server URL — typed or dictated through the system
  input. A toggle keeps the screen on while music plays (on by default).
- **Requirements**: Wear OS 2.23+ (API 26); the Lyrion Dashboard server
  reachable from the watch (plain HTTP on the LAN is allowed).

### Installing on the watch

The easiest way is the **“Install the watch app” button in the phone
app's settings**. Modern watches (Wear OS 4+, e.g. Pixel Watch) only
expose *wireless debugging*, whose pairing protocol requires the real
`adb` binary — so the phone app delegates the install to the Lyrion
Dashboard server (`POST /wear/install.json`), which runs
`adb pair` / `adb connect` / `adb install` from the LAN. To enable it:

1. Make `adb` available to the server. With Docker, uncomment the
   `command:` override in `docker-compose.override.yml.example` (installs
   the Debian `adb` package at container start); on bare metal, install
   `adb`/`android-tools` and optionally set `ADB_PATH`.
2. Provide the APK: the server looks at `WEAR_APK_PATH` (default
   `<custom data dir>/lyrion-wear.apk`). If the file is missing it
   downloads the wear APK of the latest GitHub release. While testing
   pre-release builds, drop the CI artifact (`lyrion-custom-data-wear-debug`)
   there under that name.
3. On the watch, enable developer options and *Wireless debugging*, tap
   *Pair new device*, and copy the addresses/code into the phone app's
   install screen. Pairing is only needed the first time; later updates
   just need the connection address.

Manual alternative from a computer (works on any watch):

```bash
adb pair <watch-ip>:<pairing-port> <6-digit-code>   # first time only
adb connect <watch-ip>:<connect-port>
adb -s <watch-ip>:<connect-port> install -r wear/build/outputs/apk/debug/wear-debug.apk
```

(Watches still offering the legacy *Debug over Wi-Fi* skip the pair step
and use port 5555.)

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
