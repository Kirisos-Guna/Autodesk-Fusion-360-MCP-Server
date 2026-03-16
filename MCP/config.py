# Fusion 360 Add-In HTTP server configuration.
# Values can be overridden via environment variables.
import os

_HOST = os.environ.get("FUSION_HOST", "127.0.0.1")
_PORT = os.environ.get("FUSION_PORT", "5000")
BASE_URL = f"http://{_HOST}:{_PORT}"

API_KEY = os.environ.get("FUSION_API_KEY", "")

HOST = _HOST
PORT = int(_PORT)

REQUEST_TIMEOUT = 35
