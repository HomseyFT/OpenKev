import json
import subprocess
from websockets.sync.client import connect

REMOTE_HOST = "100.77.169.69"  
REMOTE_PORT = 8260


def _get_tailscale_ip() -> str:
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True, text=True, timeout=3
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def sendMessage(text, ip) -> bool | Exception:
    """Send a message through the relay server.

    Returns True on success (delivered or queued), or the Exception on failure.
    """
    try:
        if not ip:
            raise Exception("Recipient IP is required")
        payload = {
            "headers": {"to_ip": ip, "from_ip": _get_tailscale_ip()},
            "body": text,
        }
        with connect(f"ws://{REMOTE_HOST}:{REMOTE_PORT}") as websocket:
            websocket.send(json.dumps(payload))
            raw = websocket.recv()
            response = json.loads(raw)
            if response == payload or response.get("status") == "queued":
                return True
            return False
    except Exception as ex:
        return ex
