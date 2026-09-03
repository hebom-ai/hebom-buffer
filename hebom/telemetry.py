# -*- coding: utf-8 -*-
"""Conformance telemetry — OFF by default, opt-in only.

⛔ Why off by default:
   HEBOM's long-term position is a neutral buffer between parties. A neutral
   party that collects by default is not neutral. Collection rate drops;
   the neutrality is worth more.

Turn it on, deliberately:

    python -m hebom.telemetry join     # shows exactly what is sent, then asks
    export HEBOM_TELEMETRY=on          # or set it yourself

What is sent          which check blocked, how many times, its class,
                      package/python version, a random per-install id
⛔ What is NEVER sent  payload · intent text · keys · sender/recipient names
                      hostnames · usernames · file paths · IP-derived identity

⛔ The install id is a random value written to a local file. It is NOT derived
   from the hostname, MAC, username or any machine property. Delete the file
   and you are a different install. (An earlier draft derived it from the
   hostname — that contradicted this promise and was removed.)

In return, participants get their own percentile and the cohort failure map.
"""
from __future__ import annotations
import os, json, platform, secrets, threading
from collections import Counter
from pathlib import Path

ENDPOINT = os.environ.get("HEBOM_TELEMETRY_URL", "https://api.hebom.org/v1/conformance")
_ENV = os.environ.get("HEBOM_TELEMETRY", "").lower()
ENABLED_DEFAULT = _ENV in ("on", "1", "true")        # ★ default is OFF
STATE_FILE = Path(os.environ.get("HEBOM_STATE_DIR", str(Path.home() / ".hebom"))) / "install"


def _install_id():
    """⛔ Random. Not derived from hostname or any machine property."""
    try:
        if STATE_FILE.exists():
            v = STATE_FILE.read_text().strip()
            if v: return v
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        v = secrets.token_hex(8)
        STATE_FILE.write_text(v)
        return v
    except Exception:
        return "ephemeral-" + secrets.token_hex(4)


class Telemetry:
    def __init__(self, enabled=None):
        self.enabled = ENABLED_DEFAULT if enabled is None else bool(enabled)
        self.blocked, self.by_class = Counter(), Counter()
        self.passed = 0
        self._lock = threading.Lock()

    def note(self, code, ok):
        from .schema import CLASSES
        with self._lock:
            if ok: self.passed += 1
            else:
                self.blocked[code] += 1
                self.by_class[CLASSES.get(code, "UNKNOWN")] += 1

    def payload(self):
        from .schema import SCHEMA_ID, SCHEMA_VERSION, ORIGIN_LOCAL
        import importlib.metadata as md
        try: ver = md.version("hebom-buffer")
        except Exception: ver = "dev"
        with self._lock:
            return {"schema": SCHEMA_ID, "v": SCHEMA_VERSION,
                    "origin": ORIGIN_LOCAL,
                    "install": _install_id(), "package": ver,
                    "python": platform.python_version(),
                    "blocked": dict(self.blocked),
                    "by_class": dict(self.by_class),
                    "passed": self.passed}

    def show(self): return json.dumps(self.payload(), ensure_ascii=False, indent=2)

    def submit(self):
        if not self.enabled:
            return {"sent": False, "why": "telemetry is off (opt-in): "
                                          "python -m hebom.telemetry join"}
        try:
            import urllib.request
            req = urllib.request.Request(
                ENDPOINT, data=json.dumps(self.payload()).encode(), method="POST",
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.load(r)
        except Exception as e:
            return {"sent": False, "why": type(e).__name__}


def _cli():
    import sys
    t = Telemetry(enabled=True)
    t.note("E07", False); t.note("E01", False); t.note("E12", False); t.note("OK", True)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    print("Telemetry is OFF by default. This is exactly what WOULD be sent:\n")
    print(t.show())
    print("\nNever sent: payload, intent text, keys, names, hostnames, paths.")
    print(f"Install id is a random value stored at {STATE_FILE} — delete it to reset.")
    if cmd == "join":
        ans = input("\nSend this? [y/N] ").strip().lower()
        if ans == "y":
            print("\nAdd this to your shell profile:\n    export HEBOM_TELEMETRY=on")
            print("In return you get your percentile and the cohort failure map.")
        else:
            print("\nNothing enabled. Telemetry stays off.")


if __name__ == "__main__": _cli()
