"""Install the Wear OS companion APK on a watch through the server's adb.

Modern watches (Wear OS 4+, e.g. Pixel Watch) only expose "wireless
debugging", whose pairing protocol (SPAKE2 over TLS) is implemented by the
real adb binary but by no permissively-licensed Android library — so the
phone app cannot push the APK to the watch itself. Instead the phone
collects the pairing info displayed on the watch and the server, which sits
on the same LAN, drives `adb pair` / `adb connect` / `adb install`.

The APK comes from WEAR_APK_PATH when the file exists (drop a CI-built
debug APK there while testing), otherwise the wear asset of the latest
GitHub release is downloaded to that path and reused afterwards.
"""

import os
import re
import shutil
import subprocess  # nosec B404 — adb is a fixed binary run without a shell, args allowlisted

import requests
from flask import current_app

# Conservative allowlists: these values end up as adb arguments, so reject
# anything that could be an option (leading '-') or shell-ish garbage even
# though subprocess is invoked without a shell.
_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_CODE_RE = re.compile(r"^\d{6}$")

_PAIR_TIMEOUT = 30
_CONNECT_TIMEOUT = 30
_INSTALL_TIMEOUT = 300


class WearInstallError(Exception):
    """A failed step; `step` tells the client which one (for i18n)."""

    def __init__(self, step, detail):
        super().__init__(detail)
        self.step = step
        self.detail = detail


def validate_request(host, connect_port, pair_port, pair_code):
    if not host or not _HOST_RE.match(host):
        raise WearInstallError("input", "invalid host")
    if not _valid_port(connect_port):
        raise WearInstallError("input", "invalid connect_port")
    # Pairing is optional (only needed once per watch/server couple), but
    # port and code come together.
    if (pair_port is None) != (pair_code is None):
        raise WearInstallError("input", "pair_port and pair_code go together")
    if pair_port is not None and not _valid_port(pair_port):
        raise WearInstallError("input", "invalid pair_port")
    if pair_code is not None and not _CODE_RE.match(str(pair_code)):
        raise WearInstallError("input", "invalid pair_code")


def status():
    """What the phone app needs to warn the user before trying."""
    apk_path = current_app.config["WEAR_APK_PATH"]
    return {
        "adb": shutil.which(current_app.config["ADB_PATH"]) is not None,
        "apk_present": os.path.isfile(apk_path),
        "apk_path": apk_path,
    }


def install(host, connect_port, pair_port=None, pair_code=None):
    """Run the pair/connect/install sequence, returning the adb transcript.

    Raises WearInstallError naming the failed step. The transcript of the
    steps that did run is attached to the error so the phone can show it.
    """
    validate_request(host, connect_port, pair_port, pair_code)

    if shutil.which(current_app.config["ADB_PATH"]) is None:
        raise WearInstallError(
            "adb", f"adb not found on the server (ADB_PATH={current_app.config['ADB_PATH']})"
        )
    apk = _resolve_apk()

    transcript = []
    serial = f"{host}:{connect_port}"
    try:
        if pair_code is not None:
            out = _run_adb(["pair", f"{host}:{pair_port}", str(pair_code)], _PAIR_TIMEOUT)
            transcript.append(out)
            if "successfully paired" not in out.lower():
                raise WearInstallError("pair", _tail(transcript))

        # `adb connect` exits 0 even when it fails; trust the message.
        out = _run_adb(["connect", serial], _CONNECT_TIMEOUT)
        transcript.append(out)
        if "connected to" not in out.lower() or "failed" in out.lower():
            raise WearInstallError("connect", _tail(transcript))

        # -r: reinstall, keeping data, so update installs just work.
        out = _run_adb(["-s", serial, "install", "-r", apk], _INSTALL_TIMEOUT)
        transcript.append(out)
        if "success" not in out.lower():
            raise WearInstallError("install", _tail(transcript))
    finally:
        # Leave no dangling adb connection; ignore the outcome (best-effort
        # cleanup, a failure here must not mask the real result).
        try:
            _run_adb(["disconnect", serial], 10)
        except Exception:  # nosec B110
            pass

    return _tail(transcript)


def _valid_port(port):
    return isinstance(port, int) and 1 <= port <= 65535


def _run_adb(args, timeout):
    cmd = [current_app.config["ADB_PATH"], *args]
    try:
        # Exit codes are unreliable across adb subcommands (`adb connect`
        # exits 0 on failure), so callers check the output, not `check=`.
        proc = subprocess.run(  # nosec B603 — cmd[0] is the configured adb path, args are allowlist-validated, no shell
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise WearInstallError(
            args[0].lstrip("-"), f"adb {args[0]} timed out after {timeout}s"
        ) from exc
    return (proc.stdout + proc.stderr).strip()


def _tail(transcript, limit=2000):
    return "\n".join(transcript)[-limit:]


def _resolve_apk():
    """Local file first; otherwise fetch the latest release's wear APK."""
    path = current_app.config["WEAR_APK_PATH"]
    if os.path.isfile(path):
        return path

    repo = current_app.config["GITHUB_REPO"]
    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo}/releases/latest", timeout=15
        )
        r.raise_for_status()
        assets = r.json().get("assets", [])
    except Exception as e:
        raise WearInstallError("apk", f"no APK at {path} and release lookup failed: {e}") from e

    asset = next(
        (a for a in assets if "wear" in a["name"].lower() and a["name"].endswith(".apk")),
        None,
    )
    if asset is None:
        raise WearInstallError(
            "apk", f"no APK at {path} and the latest release has no wear APK asset"
        )

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with requests.get(asset["browser_download_url"], stream=True, timeout=120) as resp:
            resp.raise_for_status()
            part = path + ".part"
            with open(part, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
            os.replace(part, path)
    except Exception as e:
        raise WearInstallError("apk", f"downloading {asset['name']} failed: {e}") from e
    return path
