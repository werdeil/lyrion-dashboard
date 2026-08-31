"""Tests for the /wear/install.json endpoint: validation and adb sequencing."""

import os
import subprocess
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("LYRION_HOST", "http://localhost:9000")
os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

# The config env vars above must be set before anything imports config.py.
# pylint: disable=wrong-import-position
from flask import Flask

from routes.wear import wear_bp


def _proc(output):
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=output, stderr="")


class WearInstallTest(unittest.TestCase):
    def setUp(self):
        fd, self.apk_path = tempfile.mkstemp(suffix=".apk")
        os.close(fd)

        app = Flask(__name__)
        app.config["ADB_PATH"] = "adb"
        app.config["WEAR_APK_PATH"] = self.apk_path
        app.config["GITHUB_REPO"] = "example/repo"
        app.register_blueprint(wear_bp)
        self.client = app.test_client()

    def tearDown(self):
        os.unlink(self.apk_path)

    def _post(self, **body):
        return self.client.post("/wear/install.json", json=body)

    # --- validation -------------------------------------------------------

    def test_rejects_bad_host(self):
        for host in [None, "", "-oops", "a b", "x;rm"]:
            resp = self._post(host=host, connect_port=5555)
            self.assertEqual(resp.status_code, 400, host)
            self.assertEqual(resp.get_json()["step"], "input")

    def test_rejects_bad_ports_and_code(self):
        cases = [
            {"host": "192.168.1.2", "connect_port": "5555"},  # port must be int
            {"host": "192.168.1.2", "connect_port": 0},
            {"host": "192.168.1.2", "connect_port": 5555, "pair_port": 40001},  # code missing
            {"host": "192.168.1.2", "connect_port": 5555, "pair_port": 40001, "pair_code": "12345"},
        ]
        for body in cases:
            resp = self._post(**body)
            self.assertEqual(resp.status_code, 400, body)

    # --- adb availability ---------------------------------------------------

    def test_reports_missing_adb(self):
        with mock.patch("services.wear_install.shutil.which", return_value=None):
            resp = self._post(host="192.168.1.2", connect_port=5555)
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(resp.get_json()["step"], "adb")

        with mock.patch("services.wear_install.shutil.which", return_value=None):
            status = self.client.get("/wear/status.json").get_json()
        self.assertFalse(status["adb"])
        self.assertTrue(status["apk_present"])

    # --- adb sequencing -----------------------------------------------------

    def test_pair_connect_install_success(self):
        outputs = {
            "pair": _proc("Successfully paired to 192.168.1.2:40001"),
            "connect": _proc("connected to 192.168.1.2:5555"),
            "install": _proc("Performing Streamed Install\nSuccess"),
            "disconnect": _proc("disconnected"),
        }
        calls = []

        def fake_run(cmd, **_):
            calls.append(cmd)
            for key, proc in outputs.items():
                if key in cmd:
                    return proc
            raise AssertionError(f"unexpected adb call: {cmd}")

        with mock.patch("services.wear_install.shutil.which", return_value="/usr/bin/adb"), \
                mock.patch("services.wear_install.subprocess.run", side_effect=fake_run):
            resp = self._post(
                host="192.168.1.2",
                connect_port=5555,
                pair_port=40001,
                pair_code="123456",
            )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["ok"])
        self.assertIn("pair", calls[0])
        self.assertIn("connect", calls[1])
        self.assertIn("install", calls[2])
        self.assertIn(self.apk_path, calls[2])
        self.assertIn("disconnect", calls[3])

    def test_connect_failure_is_reported(self):
        def fake_run(cmd, **_):
            if "connect" in cmd:
                return _proc("failed to connect to '192.168.1.2:5555'")
            return _proc("disconnected")

        with mock.patch("services.wear_install.shutil.which", return_value="/usr/bin/adb"), \
                mock.patch("services.wear_install.subprocess.run", side_effect=fake_run):
            resp = self._post(host="192.168.1.2", connect_port=5555)

        self.assertEqual(resp.status_code, 502)
        body = resp.get_json()
        self.assertEqual(body["step"], "connect")
        self.assertIn("failed to connect", body["error"])

    def test_pairing_is_skipped_without_code(self):
        calls = []

        def fake_run(cmd, **_):
            calls.append(cmd)
            if "connect" in cmd:
                return _proc("already connected to 192.168.1.2:5555")
            if "install" in cmd:
                return _proc("Success")
            return _proc("disconnected")

        with mock.patch("services.wear_install.shutil.which", return_value="/usr/bin/adb"), \
                mock.patch("services.wear_install.subprocess.run", side_effect=fake_run):
            resp = self._post(host="192.168.1.2", connect_port=5555)

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("pair", [c[1] for c in calls])

    def test_missing_apk_and_no_release(self):
        os.unlink(self.apk_path)
        try:
            with mock.patch("services.wear_install.shutil.which", return_value="/usr/bin/adb"), \
                    mock.patch("services.wear_install.requests.get", side_effect=OSError("offline")):
                resp = self._post(host="192.168.1.2", connect_port=5555)
        finally:
            # Recreate the file so tearDown's unlink finds it.
            with open(self.apk_path, "w", encoding="utf-8"):
                pass

        self.assertEqual(resp.status_code, 502)
        self.assertEqual(resp.get_json()["step"], "apk")


if __name__ == "__main__":
    unittest.main()
