# -*- coding: utf-8 -*-
"""Result schema for hebom-buffer v1.

⛔ This is HEBOM's v1 schema. It is NOT a claim to be an industry standard.
   Whether it becomes one is decided by adoption, not by this file.

Immutability rules (strong):
  · E01–E12 meanings and numbers never change within v1
  · new failures get new numbers: E13, E14, ...
  · a structural change means a new URL: .../buffer-result/2
  · a v1 consumer can read v1 forever
"""
SCHEMA_ID = "https://hebom.org/schema/buffer-result/1"
SCHEMA_VERSION = "1.0.0"

# ── External surface: flat codes. Callers only ever see these. ──────────
MODES = {
    "E01": "loss",                 "E02": "duplicate",
    "E03": "replay",               "E04": "out_of_order",
    "E05": "stale_state",          "E06": "conflict",
    "E07": "schema_mismatch",      "E08": "identity_spoofing",
    "E09": "unauthorized_action",  "E10": "partial_failure",
    "E11": "poison_propagation",   "E12": "false_completion",
}

# ── Internal axis: what KIND of failure it is. ─────────────────────────
# ⛔ Not part of the public API. It exists so aggregate analysis can say
#    "this pipeline breaks at STATE 2.1%, AUTHORITY 0.4%, COMPLETION 6.8%"
#    instead of only "E07: 41,234".
CLASSES = {
    "E01": "TRANSPORT",   "E02": "TRANSPORT",   "E03": "TRANSPORT",
    "E04": "TRANSPORT",
    "E05": "STATE",       "E06": "STATE",
    "E07": "SCHEMA",
    "E08": "AUTHORITY",   "E09": "AUTHORITY",
    "E10": "PROPAGATION", "E11": "PROPAGATION",
    "E12": "COMPLETION",
}
CLASS_NAMES = ("TRANSPORT", "STATE", "SCHEMA", "AUTHORITY", "PROPAGATION", "COMPLETION")

# ── Where the result came from. ────────────────────────────────────────
# ⛔ A local run is NOT a HEBOM verification. Keeping these apart is what
#    makes "hebom_verified" mean anything later.
ORIGIN_LOCAL = "local"              # you ran the package on your own machine
ORIGIN_THIRD_PARTY = "third_party"  # an independent operator ran it
ORIGIN_HEBOM = "hebom_verified"     # ⛔ only HEBOM's operated service may set this


def result(code, ok, detail="", origin=ORIGIN_LOCAL, **extra):
    if origin == ORIGIN_HEBOM:
        raise ValueError(
            "⛔ 'hebom_verified' cannot be set by this package. A local run is "
            "not a HEBOM verification. See TRADEMARK.md.")
    return {"schema": SCHEMA_ID, "v": SCHEMA_VERSION,
            "code": code, "ok": bool(ok),
            "mode": MODES.get(code), "class": CLASSES.get(code),
            "origin": origin, "detail": detail, **extra}
