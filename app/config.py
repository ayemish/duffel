import os
from dotenv import load_dotenv

load_dotenv()

DUFFEL_API_TOKEN = os.environ.get("DUFFEL_API_TOKEN", "")
DUFFEL_API_BASE = "https://api.duffel.com"
DUFFEL_VERSION = "v2"

if not DUFFEL_API_TOKEN:
    # Fail loudly at import time rather than on the first request — easier to
    # catch during local setup / deploy than a mysterious 401 later.
    raise RuntimeError(
        "DUFFEL_API_TOKEN is not set. Copy .env.example to .env and fill it in, "
        "or export it in your shell/host's environment settings."
    )
