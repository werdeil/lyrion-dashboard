from flask import Blueprint, jsonify, request

from services.wear_install import WearInstallError, install, status

wear_bp = Blueprint("wear", __name__)


@wear_bp.route("/wear/status.json")
def wear_status():
    """Pre-flight info for the phone app's install screen."""
    return jsonify(status())


@wear_bp.route("/wear/install.json", methods=["POST"])
def wear_install():
    """Install the Wear OS companion APK on a watch via the server's adb.

    The phone app posts the wireless-debugging pairing info shown on the
    watch; pairing fields are optional once the watch already trusts this
    server. See services/wear_install.py for why this runs server-side.
    """
    data = request.get_json(silent=True) or {}
    try:
        detail = install(
            host=data.get("host"),
            connect_port=data.get("connect_port"),
            pair_port=data.get("pair_port"),
            pair_code=data.get("pair_code"),
        )
    except WearInstallError as e:
        code = 400 if e.step == "input" else 502
        return jsonify({"ok": False, "step": e.step, "error": e.detail}), code
    return jsonify({"ok": True, "detail": detail})
