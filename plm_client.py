"""Kleiner Lifecycle-Client: Key nur aus $LIFECYCLE_API_KEY, nur an app-be.lifecycleplm.com,
Rate-Limit-Bremse (100/min bei Lifecycle -> wir bleiben bei ~50/min), Protokoll ohne Key."""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
BASE = "https://app-be.lifecycleplm.com/api/v1"
LOG = ROOT / "output" / "upload_log.jsonl"
_last = 0.0


def call(method, path, body=None, **params):
    global _last
    wait = 1.2 - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.time()
    r = requests.request(method, f"{BASE}/{path}", params=params or None, json=body, timeout=40,
                         headers={"Authorization": f"Bearer {os.environ['LIFECYCLE_API_KEY']}"})
    try:
        data = r.json()
    except ValueError:
        data = r.text[:500]
    if method != "GET":  # nur schreibende Aufrufe protokollieren
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as f:
            f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "method": method, "path": path,
                                "status": r.status_code, "request": body, "response": data}, ensure_ascii=False) + "\n")
    return r.status_code, data
