# -*- coding: utf-8 -*-
"""Adversarial test of the 12 handoff failure modes — hits the KERNEL, not the table.

  build a broken input → pass it through a real Room → did it reach downstream? → record E-code

This test uses the INSTALLED package. The wheel is the truth, not the source tree.

  git clone https://github.com/hebom-ai/hebom-buffer
  cd hebom-buffer
  pip install hebom-buffer
  python tools/e2e_attack.py
"""
import sys, os, time, threading, json
sys.path = [p for p in sys.path if os.path.abspath(p) != os.getcwd()]  # exclude the source tree
from hebom import Room
from hebom.schema import MODES, CLASSES

R = {}
def rec(code, blocked, note): R[code] = (blocked, note)

# ── E01 loss — measure whether items are actually LOST ──────────────
def e01():
    """Corrected 2026-09-03: the previous test read "nothing came out of an
       empty queue" as "loss blocked". Nothing was put in, so of course — a
       false verdict.
       Real test: does everything ACCEPTED get DELIVERED, and does it survive
       a process restart?"""
    r = Room(capacity=5)
    acc = [r.pass_({"i": i}, event_id=f"L{i}")["accepted"] for i in range(8)]
    accepted = sum(acc)
    delivered = 0
    while r.take(): delivered += 1
    # everything accepted is delivered — true so far
    in_memory_only = True     # a restart drops whatever is queued
    return (not in_memory_only), \
           (f"accepted {accepted} -> delivered {delivered} (match). "
            f"but no end-to-end ack, no durability: a restart loses the queue")

# ── E02 duplicate ─────────────────────────────────────────────────
def e02():
    r = Room()
    r.pass_({"cmd": "charge"}, event_id="c1")
    second = r.pass_({"cmd": "charge"}, event_id="c1")
    n = 0
    while r.take(): n += 1
    return (second["code"] == "DUPLICATE" and n == 1), f"second REFUSED, delivered {n}"

# ── E03 replay — an expired old command ───────────────────────────
def e03():
    r = Room()
    r.pass_({"cmd": "old"}, event_id="r1", ttl_s=0.02)
    time.sleep(0.05)
    return (r.take() is None), "expired item never comes out"

# ── E04 out-of-order ──────────────────────────────────────────────
def e04():
    r = Room()
    for i in range(30): r.pass_({"i": i}, event_id=f"o{i}")
    got = [r.take()["payload"]["i"] for _ in range(30)]
    return (got == sorted(got)), f"FIFO kept {got[:3]}...{got[-2:]}"

# ── E05 stale state ───────────────────────────────────────────────
def e05():
    r = Room()
    r.pass_({"v": 1}, event_id="s1")
    return None, "no version / CAS in the kernel: cannot judge"

# ── E06 conflict ──────────────────────────────────────────────────
def e06():
    return None, "no CAS in the kernel: cannot judge"

# ── E07 schema mismatch ───────────────────────────────────────────
def e07():
    r = Room()
    ok = r.pass_({"totally": "wrong shape"}, event_id="x1")
    got = r.take()
    return (got is None), "payload is opaque: passes through" if got else "blocked"

# ── E08 identity spoofing ─────────────────────────────────────────
def e08():
    r = Room()
    r.pass_({"x": 1}, sender="did:agent:VICTIM", event_id="sp")
    got = r.take()
    return (got is None), f"sender '{got['sender']}' accepted as asserted: no signature"

# ── E09 unauthorized action ───────────────────────────────────────
def e09():
    r = Room()
    r.pass_({"action": "charge_card"}, event_id="u1")
    return (r.take() is None), "no authority model: passes through"

# ── E10 partial failure ───────────────────────────────────────────
def e10():
    r = Room()
    r.pass_({"part": 1}, event_id="p1")     # only 1 of 2 parts
    return (r.take() is None), "no transaction: delivers with 1 of 2 parts"

# ── E11 poison propagation — the expensive one ────────────────────
def e11():
    calls = {"n": 0}
    def downstream(item): calls["n"] += 1
    r = Room(after_sink=downstream)
    r.pass_({"columns": ["name"], "rows": "garbage"}, event_id="poison")
    got = r.take()
    return (got is None and calls["n"] == 0), \
           f"poison reached downstream: after_sink called {calls['n']}x"

# ── E12 false completion ──────────────────────────────────────────
def e12():
    r = Room()
    r.pass_({"status": "partial"}, event_id="f1")
    return (r.take() is None), "no notion of completion in the kernel"

# ── what the kernel ACTUALLY does besides the three ───────────────
def extra():
    out = []
    r = Room(capacity=2)
    r.pass_(1, event_id="b1"); r.pass_(2, event_id="b2")
    out.append(("backpressure", r.pass_(3, event_id="b3")["code"] == "BUSY", "BUSY when full"))
    r2 = Room()
    r2.pass_({"x": 1}, recipient="B", event_id="rt")
    out.append(("recipient routing", r2.take(recipient="C") is None, "never hands out someone else's item"))
    r3 = Room()
    r3.pass_({"x": 1}, event_id="h1")
    it = r3.take()
    import hashlib, json as _j
    h = hashlib.sha256(_j.dumps({"x": 1}, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":"), default=str).encode()).hexdigest()
    out.append(("payload hash", it["payload_hash"] == h, "verifiable from outside"))
    def bad(_): raise RuntimeError("sink down")
    r4 = Room(after_sink=bad); r4.pass_("safe", event_id="sk")
    out.append(("sink isolation", r4.take()["payload"] == "safe", "delivers even if the sink raises"))
    return out

print("=" * 86)
print("  12 failure modes, ADVERSARIAL run against the installed wheel")
print("=" * 86)
print(f"  {'':<5}{'mode':<22}{'class':<13}{'result':<11}evidence")
for code, fn in [("E01",e01),("E02",e02),("E03",e03),("E04",e04),("E05",e05),("E06",e06),
                 ("E07",e07),("E08",e08),("E09",e09),("E10",e10),("E11",e11),("E12",e12)]:
    b, note = fn(); rec(code, b, note)
    mark = "BLOCKS" if b else ("n/a" if b is None else "passes")
    print(f"  {code:<5}{MODES[code]:<22}{CLASSES[code]:<13}{mark:<11}{note[:56]}")
blocked = sum(1 for b,_ in R.values() if b is True)
passed  = sum(1 for b,_ in R.values() if b is False)
na      = sum(1 for b,_ in R.values() if b is None)
print("-" * 86)
print(f"  Guaranteed by the kernel: {blocked}/12 · passes through {passed} · n/a {na}")
print("\n  -- what the kernel also does --")
for n,ok,note in extra():
    print(f"  {'ok ' if ok else 'NO '} {n:<18}{note}")
print(f"""
  If the README ever reads as "12 failure modes blocked", that is FALSE.
  E01 is off the guaranteed list on purpose: accepted items are delivered,
  but there is no end-to-end ack and no durability. A restart loses the queue.
  The 147-line kernel is the transport seam. Everything else is outside this package.
""")
