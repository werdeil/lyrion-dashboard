import requests
import urllib3
from flask import current_app

urllib3.disable_warnings()


def lyrion_request(payload):
    host = current_app.config["LYRION_HOST"]
    r = requests.post(
        f"{host}/jsonrpc.js",
        json=payload,
        verify=False,
        timeout=5,
    )
    return r.json()


def get_players():
    payload = {
        "id": 1,
        "method": "slim.request",
        "params": ["", ["players", "0", "100"]],
    }
    data = lyrion_request(payload)
    return data["result"].get("players_loop", [])


def play_album(player_id, album_id):
    payload = {
        "id": 1,
        "method": "slim.request",
        "params": [
            player_id,
            ["playlistcontrol", "cmd:load", f"album_id:{album_id}"],
        ],
    }
    lyrion_request(payload)
