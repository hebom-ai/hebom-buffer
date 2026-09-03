# hebom-buffer

**Deduplication, expiry and ordering at the boundary between AI agents.**

```bash
pip install hebom-buffer
```

```python
from hebom import Room

room = Room()
room.pass_({"rows": 120, "columns": ["name", "phone"]}, recipient="summarizer")

item = room.take(recipient="summarizer")
```

Two operations: `pass_` and `take`. One file, 147 lines, no dependencies.

## What this actually blocks

We catalogued twelve ways an agent-to-agent handoff fails. **This package
guarantees three of them.** Not twelve. The rest are not transport-boundary
problems and are deliberately outside a 147-line buffer.

Every row below is verified by `tools/e2e_attack.py` against the installed
wheel, not against the source tree.

| | Failure | Class | This package |
|---|---|---|---|
| E01 | loss | TRANSPORT | ⛔ no end-to-end acknowledgement or durable delivery here |
| E02 | duplicate | TRANSPORT | **blocks** — the same `event_id` is accepted once |
| E03 | replay | TRANSPORT | **blocks** — expired envelopes are never delivered |
| E04 | out-of-order | TRANSPORT | **blocks** — FIFO is preserved |
| E05 | stale state | STATE | ⛔ no versioning here |
| E06 | conflict | STATE | ⛔ no compare-and-swap here |
| E07 | schema mismatch | SCHEMA | ⛔ payload is opaque by design |
| E08 | identity spoofing | AUTHORITY | ⛔ `sender` is asserted, not proven |
| E09 | unauthorized action | AUTHORITY | ⛔ no authority model here |
| E10 | partial failure | PROPAGATION | ⛔ no transaction here |
| E11 | poison propagation | PROPAGATION | ⛔ needs a payload contract, which is not here |
| E12 | false completion | COMPLETION | ⛔ this buffer does not judge completion |

**Run it yourself:**

```bash
pip install hebom-buffer
python tools/e2e_attack.py     # prints 3/12 and why
```

If that number ever disagrees with this table, the table is wrong. A test
enforces it.

## What it also does

| | |
|---|---|
| backpressure | a full buffer returns `BUSY`, it never blocks silently |
| recipient routing | an item addressed to B is not handed to C |
| payload hash | every item carries a SHA-256 you can check yourself |
| sink isolation | if your recording sink throws, delivery still succeeds |

## Why three is worth having

E11 is the expensive failure — one malformed handoff calls every downstream
model. This package does not block E11 on its own, because deciding what
"malformed" means requires a payload contract, and this buffer treats payloads
as opaque.

What it does give you is the **place to put that check**. Before:

```python
result = agent_a()
agent_b(result)          # nothing sits between them
```

After:

```python
r = room.pass_(agent_a(), recipient="b")
if not r["ok"]:
    return              # your contract check has somewhere to live
agent_b(room.take(recipient="b")["payload"])
```

The measurement that motivated this: on our machine the buffer check is
**~11µs**, a model call is **~1.5s**. Having a place to reject early is worth
four orders of magnitude — but only if you put a contract there. This package
gives you the seam, not the contract.

⛔ And it is in-memory. If the process restarts, anything still queued is gone.
That is why E01 is not on the guaranteed list.

## We attacked our own implementation first

Our first buffer had none of the three guarantees above. It lost items on
overload, delivered duplicates, and had no expiry.

```bash
python -m pytest tests/          # unit tests
python tools/e2e_attack.py       # adversarial, against the installed wheel
```

## Not a replacement for A2A or MCP

A2A moves messages. MCP invokes tools. **HEBOM Buffer adds transport-boundary
guarantees before downstream consumption** — deduplication, expiry and ordering
at the seam between two agents.

⛔ It does **not** decide whether a payload is semantically valid. Neither does
A2A. That judgement needs a payload contract, and this buffer treats payloads
as opaque.

```python
def on_a2a_message(msg):
    r = room.pass_(msg.payload, sender=msg.sender, recipient=msg.recipient)
    if not r["ok"]:
        return refuse(r["why"])        # the downstream model is never called
```

## Honest limits

- **Process-local.** Separate workers cannot share this buffer.
- **Multi-core scaling is unproven.** Our test machine has one core.
- **It does not judge payload quality.** Only whether the handoff is well-formed.
- **No sender signatures.** Identity is asserted, not proven, in this package.

## Result schema

Every result carries `https://hebom.org/schema/buffer-result/1`.

This is **our v1 schema, not an industry standard.** Whether it becomes one is
decided by adoption. What we do promise:

- `E01`–`E12` meanings and numbers never change within v1
- new failures get new numbers (`E13`, `E14`, …)
- a structural change means a new URL (`/buffer-result/2`)
- a v1 consumer can read v1 forever

Results also carry `origin`. A run on your own machine is `local`. It is
**not** a HEBOM verification, and this package cannot claim otherwise —
`origin="hebom_verified"` raises. See [TRADEMARK.md](TRADEMARK.md).

## Conformance telemetry — off by default

Nothing is sent unless you turn it on. See exactly what *would* be sent:

```bash
python -m hebom.telemetry join
```

Sent (only if you opt in): which check blocked, how many times, its class,
package and Python version, and a **random** per-install id stored at
`~/.hebom/install`.

⛔ Never sent: payload, intent text, keys, sender/recipient names, hostnames,
usernames, file paths. The install id is not derived from any machine
property — delete the file and you are a different install.

Why off by default: this is meant to sit between parties who do not trust each
other. A neutral party that collects by default is not neutral. Participants
get their percentile and the cohort failure map in return.

## Questions we would like torn apart

1. Is this the right layer, or should A2A absorb it?
2. Which failure modes are we missing?
3. Does anyone actually lose money to this, or are we solving our own problem?

## Licence

Code: Apache-2.0. Name: see [TRADEMARK.md](TRADEMARK.md) — the code is open,
the name is not.
