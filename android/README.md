# Lyrion Custom Data — Android app

A thin Android WebView wrapper around the Lyrion Custom Data dashboard,
following the same principle as
[lms-material-app](https://github.com/CDrummond/lms-material-app): the whole
UI lives in the web page served by the Flask app, the Android app only
provides the native shell.

## Features

- Full screen WebView loading the dashboard
- Settings screen (server URL, keep screen on)
- Automatic discovery of the Lyrion Music Server on the local network
  (UDP broadcast on port 3483, the standard LMS discovery protocol); the
  suggested URL assumes Lyrion Custom Data runs on the same host on port 1111
- Keeps the screen on while the dashboard is displayed (configurable)
- Works over plain HTTP on the local network (cleartext traffic allowed)
- Back button navigates the WebView history; on the start page it opens a
  small menu (Settings / Reload / Quit)

## Requirements

- Android 8.0 (API 26) or newer
- A running Lyrion Custom Data instance reachable from the phone

## Building

With Android Studio: open the `android/` folder and run the `app`
configuration.

From the command line (requires the Android SDK, `ANDROID_HOME` set):

```bash
cd android
./gradlew assembleDebug
# APK in app/build/outputs/apk/debug/app-debug.apk
```

## CI builds

The GitHub Actions workflow `.github/workflows/android.yml`:

- builds a debug APK on every push touching `android/**` and uploads it as a
  workflow artifact;
- on a published GitHub release, builds a release APK and attaches it to the
  release. The APK is signed when the `ANDROID_KEYSTORE_BASE64`,
  `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` and `ANDROID_KEY_PASSWORD`
  repository secrets are configured, and unsigned otherwise.

To create a keystore and export it for CI:

```bash
keytool -genkeypair -v -keystore release.jks -alias lyrion \
        -keyalg RSA -keysize 2048 -validity 10000
base64 -w0 release.jks   # value for ANDROID_KEYSTORE_BASE64
```
