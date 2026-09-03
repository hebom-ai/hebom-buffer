#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A2A spec probe — observe, do not judge.

    python -m venv .venv-a2a
    source .venv-a2a/bin/activate      # Windows: .venv-a2a\\Scripts\\activate
    pip install a2a-sdk hebom-buffer
    python examples/a2a_spec_probe.py

⛔ THIS IS NOT A CONFORMANCE TEST.

Three of the behaviours probed here are left to the implementer by the A2A
specification. §3.3.1 says Send Message operations **MAY** be idempotent. An
implementation that processes the same messageId twice is **conformant**.
Reporting that as a failure would be wrong.

So this script records what happened. It never prints PASS or FAIL for A2A.

    WRONG   A2A FAILS duplicate test
    RIGHT   OBSERVED: same messageId submitted twice -> <behaviour>
            SPEC:     idempotency = MAY
            HEBOM:    second event_id -> DUPLICATE

What is being separated
  · transport ordering   — A2A MANDATES streaming events arrive in order
  · consumption ordering — the order your receiver takes what it accepted
  These are different guarantees. Only the second belongs to hebom-buffer.
"""
from __future__ import annotations
import json, sys, time

SPEC = {
    "E02": ("§3.3.1", "Send Message operations MAY be idempotent. "
                      "Agents may utilize the messageId to detect duplicate messages."),
    "E02b": ("push notifications", "Clients SHOULD process notifications idempotently, "
                                   "as duplicate deliveries may occur."),
    "E03": ("—", "No message-level TTL or expiry field was found in the specification "
                 "text. This probe re-checks the SDK surface before concluding."),
    "E04": ("§7 / custom bindings", "All implementations MUST deliver events in the "
                                    "order they were generated. Custom bindings must "
                                    "specify ordering guarantees."),
}

OBS = []


def observe(code, what, result, note=""):
    OBS.append({"code": code, "probe": what, "observed": result, "note": note})


# ── environment ───────────────────────────────────────────────────
def check_env():
    have = {}
    try:
        import a2a, importlib.metadata as md
        have["a2a-sdk"] = md.version("a2a-sdk")
    except Exception as e:
        have["a2a-sdk"] = f"NOT INSTALLED ({type(e).__name__})"
    try:
        import hebom, importlib.metadata as md
        have["hebom-buffer"] = md.version("hebom-buffer")
    except Exception as e:
        have["hebom-buffer"] = f"NOT INSTALLED ({type(e).__name__})"
    return have


# ── E02 · duplicate messageId ─────────────────────────────────────
def probe_e02():
    """Submit the same messageId twice. Record what each side does."""
    # hebom side — deterministic, no network needed
    from hebom import Room
    room = Room()
    a = room.pass_({"x": 1}, event_id="probe-dup-1")
    b = room.pass_({"x": 1}, event_id="probe-dup-1")
    delivered = 0
    while room.take():
        delivered += 1
    observe("E02", "hebom: same event_id twice",
            f"first accepted={a['accepted']}, second code={b['code']}, delivered={delivered}")

    # A2A side — needs the SDK; do not guess if it is absent
    try:
        from a2a import types as T
    except ImportError:
        observe("E02", "a2a-sdk: same messageId twice", "NOT MEASURED",
                "a2a-sdk not installed. ⛔ Do not infer the behaviour.")
        return
    # Construct two Messages carrying the same id and record only what the SDK
    # itself does with them at the type level. A live server round-trip needs a
    # running agent; that is the next step and is intentionally not faked here.
    m1 = T.Message(message_id="probe-dup-1", role=T.Role.ROLE_USER)
    m2 = T.Message(message_id="probe-dup-1", role=T.Role.ROLE_USER)
    same = m1.message_id == m2.message_id
    observe("E02", "a2a-sdk: two Messages with identical message_id",
            f"constructed without error, ids equal={same}",
            "⚠ TYPE LEVEL ONLY. Whether a running agent processes it once or "
            "twice is implementation-defined (§3.3.1 MAY) and requires a live "
            "server round-trip to observe.")


# ── E03 · message expiry ──────────────────────────────────────────
def probe_e03():
    from hebom import Room
    room = Room()
    room.pass_("old", event_id="probe-exp-1", ttl_s=0.02)
    time.sleep(0.05)
    observe("E03", "hebom: envelope past its TTL",
            f"delivered={room.take()}")

    try:
        from a2a import types as T
    except ImportError:
        observe("E03", "a2a-sdk: message-level TTL field", "NOT MEASURED",
                "a2a-sdk not installed.")
        return
    fields = set()
    try:
        fields = set(T.Message.DESCRIPTOR.fields_by_name)      # protobuf
    except Exception:
        try:
            fields = set(T.Message.model_fields)                # pydantic
        except Exception:
            pass
    hits = sorted(f for f in fields
                  if any(k in f.lower() for k in ("ttl", "expir", "deadline", "valid")))
    observe("E03", "a2a-sdk: Message fields matching ttl/expiry/deadline",
            hits or "none found",
            f"searched {len(fields)} fields: {sorted(fields)}. "
            "⚠ Absence in the SDK surface is not proof of absence in the spec; "
            "cross-check the specification text before concluding.")


# ── E04 · ordering — two different guarantees ─────────────────────
def probe_e04():
    from hebom import Room
    room = Room()
    for i in range(6):
        room.pass_({"i": i}, event_id=f"probe-ord-{i}")
    got = [room.take()["payload"]["i"] for _ in range(6)]
    observe("E04", "hebom: consumption order on take()",
            f"{got} (FIFO={got == sorted(got)})",
            "This is process-local CONSUMPTION ordering.")

    observe("E04", "a2a: streaming transport ordering", "MANDATED BY SPEC",
            "⛔ A2A already requires events to be delivered in generation order. "
            "hebom-buffer does not add to, replace, or test that. Different "
            "guarantee — do not conflate the two.")


# ── report ────────────────────────────────────────────────────────
def report(env):
    W = 78
    print("=" * W)
    print("  A2A SPEC PROBE — observations only, no A2A pass/fail judgment")
    print("=" * W)
    for k, v in env.items():
        print(f"  {k:<16}{v}")
    print()
    for code in ("E02", "E03", "E04"):
        sec, text = SPEC[code]
        print("-" * W)
        print(f"  {code}   SPEC {sec}")
        for line in _wrap(text, W - 14):
            print(f"       {line}")
        if code == "E02":
            sec2, t2 = SPEC["E02b"]
            for line in _wrap(t2, W - 14):
                print(f"       {line}")
        for o in [x for x in OBS if x["code"] == code]:
            print(f"\n       OBSERVED  {o['probe']}")
            print(f"                 -> {o['observed']}")
            if o["note"]:
                for line in _wrap(o["note"], W - 20):
                    print(f"                 {line}")
        print()
    print("=" * W)
    print("  No A2A PASS/FAIL judgment is made or implied.")
    print("  §3.3.1 makes idempotency a MAY. An implementation that does not")
    print("  de-duplicate is conformant. This probe records behaviour only.")
    print("=" * W)


def _wrap(s, w):
    out, line = [], ""
    for word in s.split():
        if len(line) + len(word) + 1 > w:
            out.append(line); line = word
        else:
            line = (line + " " + word).strip()
    if line: out.append(line)
    return out


def main():
    env = check_env()
    if "NOT INSTALLED" in env.get("hebom-buffer", ""):
        print("hebom-buffer is required:  pip install hebom-buffer")
        return 1
    probe_e02(); probe_e03(); probe_e04()
    report(env)
    if "--json" in sys.argv:
        print("\n" + json.dumps({"env": env, "observations": OBS},
                                indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
