#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A2A example — protect an agent-to-agent handoff.

Runnable with the official a2a-sdk:

    pip install hebom-buffer a2a-sdk
    python examples/a2a_handoff.py

What this shows
  1. Declaring the extension on the AgentCard so peers can see you support it.
  2. Carrying nothing extra on the wire — the A2A Message is untouched.
  3. Refusing a duplicate A2A message id before the downstream model is called.
  4. Dropping an expired (replayed) message.
  5. Preserving order.

⛔ This does not replace A2A. It protects the handoff boundary.
   No A2A field is redefined. An agent that does not know this extension reads
   the same Message normally.
"""
from hebom import Room

EXT = "https://hebom.org/schema/buffer-result/1"

# ── the model call we are protecting ──────────────────────────────
downstream_calls = {"n": 0}


def expensive_model_call(payload):
    downstream_calls["n"] += 1
    return f"processed {payload}"


# ── the middleware — this is the whole integration ────────────────
room = Room()


def on_a2a_message(message_id, sender, recipient, payload, ttl_s=None):
    """Call this from your A2A handler instead of calling the model directly."""
    r = room.pass_(payload, sender=sender, recipient=recipient,
                   event_id=message_id, ttl_s=ttl_s)
    if not r["accepted"]:
        return {"refused": True, "code": r["code"]}      # model never called
    item = room.take(recipient=recipient)
    if item is None:
        return {"refused": True, "code": "NOT_READY"}
    return {"refused": False, "result": expensive_model_call(item["payload"])}


def main():
    print("A2A example — protect an agent-to-agent handoff")
    print("=" * 68)

    # 1. normal handoff
    out = on_a2a_message("msg-1", "agent-a", "agent-b", {"rows": 120})
    print(f"  normal            {out}")

    # 2. A2A duplicate — same message id arrives twice
    on_a2a_message("msg-2", "agent-a", "agent-b", {"rows": 121})
    dup = on_a2a_message("msg-2", "agent-a", "agent-b", {"rows": 121})
    print(f"  duplicate id      {dup}          <- model not called again")

    # 3. A2A replay — an old message comes back after its window
    import time
    on_a2a_message("msg-3", "agent-a", "agent-b", {"rows": 122}, ttl_s=0.01)
    time.sleep(0.05)
    stale = room.take(recipient="agent-b")
    print(f"  expired replay    delivered={stale}                  <- dropped")

    # 4. A2A task ordering
    for i in range(5):
        room.pass_({"i": i}, recipient="agent-c", event_id=f"o{i}")
    order = [room.take(recipient="agent-c")["payload"]["i"] for _ in range(5)]
    print(f"  ordering          {order}                <- FIFO preserved")

    print("-" * 68)
    print(f"  downstream model calls: {downstream_calls['n']}")
    print("  ⛔ Not blocked here: schema validity, authority, completion.")
    print("     See the README table — 3 of 12 guaranteed, 9 out of scope.")

    # ── declaring it on an AgentCard (optional, needs a2a-sdk) ─────
    try:
        from a2a import types as T
        card = T.AgentCard(name="agent-b", description="downstream agent",
                           version="1.0")
        card.capabilities.extensions.append(
            T.AgentExtension(uri=EXT, description="handoff integrity",
                             required=False))
        print(f"\n  AgentCard extension declared: {card.capabilities.extensions[0].uri}")
    except ImportError:
        print("\n  (install a2a-sdk to see the AgentCard declaration)")


if __name__ == "__main__":
    main()
