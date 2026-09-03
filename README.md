hebom-buffer
Deduplication, expiry and ordering at the boundary between AI agents.
Using A2A?
A2A defines how agents discover and communicate.
hebom-buffer sits at the handoff boundary and adds three local transport
guarantees:
duplicate suppression
expiry
FIFO ordering
It does not replace A2A and does not claim schema, identity, authorization, or
completion guarantees.
★ A2A example — protect an agent-to-agent handoff
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
Where this sits in the A2A spec
Not an opinion — quotes from the specification.
	A2A specification says	So the receiver must
duplicate	§3.3.1: "Send Message operations MAY be idempotent. Agents may utilize the `messageId` to detect duplicate messages."	implement it. `MAY` is optional.
duplicate	"Clients SHOULD process notifications idempotently, as duplicate deliveries may occur."	handle a delivery the spec expects to happen.
expiry	⛔ nothing. The words `expiry` and `ttl` do not appear for messages.	decide for itself.
ordering	§7: "All implementations MUST deliver events in the order they were generated." Custom bindings must "specify ordering guarantees".	⚠ A2A does mandate streaming event ordering. That is a different guarantee from this package's.
★ This package is one implementation of that `MAY`, plus the expiry the spec
leaves open.
To check any of this yourself rather than take our word for it:
```bash
pip install a2a-sdk hebom-buffer
python examples/a2a_spec_probe.py
```
⛔ That script is not a conformance test. §3.3.1 makes idempotency a `MAY`,
so an implementation that does not de-duplicate is conformant. The probe
records behaviour and prints no A2A pass or fail.
⛔ On ordering, be precise. A2A does require streaming events to be
delivered in the order they were generated. This package does not add to that
and does not replace it. What it provides is a different guarantee:
process-local FIFO on `take()` — the order in which your own receiver
consumes what it has already accepted. Transport ordering and consumption
ordering are two separate things, and only the second is ours.
⛔ It is not a criticism of A2A. Leaving idempotency to the implementer is a
reasonable protocol decision — someone still has to implement it.
Using this with A2A
If you are building on A2A (Agent2Agent), the question is which of the
twelve modes A2A already covers and which are left to you. Short answer: A2A
defines the message, not the seam.
You searched for	Where it actually lives
A2A duplicate message	A2A gives every `Message` an id. Acting on it once is the receiver's job. This buffer refuses the second `event_id`.
A2A replay of an old task	A2A has no expiry on a delivered message. This buffer drops an envelope past its TTL.
A2A task ordering	A2A mandates streaming event delivery order. It does not define the order your receiver consumes what it accepted. This buffer is process-local FIFO on `take()` — a different guarantee, not a replacement.
A2A agent handoff integrity	A2A moves the handoff. Whether what arrives is what was sent is the failure boundary — that is this package.
A2A agent failure that is silent	The expensive ones raise nothing. See the production quotes above.
A2A reliability middleware	This is A2A middleware in Python: one call in your handler, no A2A field redefined.
A2A middleware in Python — the whole integration
```python
from hebom import Room
room = Room()

def on_a2a_message(msg):                       # your existing A2A handler
    r = room.pass_(msg.payload,
                   sender=msg.sender,
                   recipient=msg.recipient,
                   event_id=msg.message_id)     # A2A message id → dedup key
    if not r["accepted"]:
        return refuse(r)                        # downstream model never called
    item = room.take(recipient=msg.recipient)
    return handle(item["payload"])
```
A runnable version is in
`examples/a2a_handoff.py` —
A2A example: protect an agent-to-agent handoff.
⛔ This does not replace A2A. It protects the handoff boundary.
No A2A field is redefined; an agent that does not know the extension reads the
message normally.
What this looks like in production
This is not hypothetical. From a public LangGraph issue thread, in the words of
people who hit it:
> Silent failures like this are an absolute nightmare because the application
> doesn't actually crash — the agent's trajectory just stealthily drifts.
> The agent receives a successful response from the wrong tool and has no way
> to know the substitution happened. No error surface, no observable signal in
> the trace.
One reported case: two MCP servers each exposed a tool named `create_item`.
One was a read-only catalog, the other a write-capable workflow engine. The
second registration silently replaced the first. The agent kept calling what it
believed was a preview operation.
⛔ This package does not fix that particular bug — that belongs in the tool
registry. It is here because it is the clearest description of the failure
class this buffer exists for: no crash, no error, no signal in the trace.
Source: langchain-ai/langgraph#7988
What this actually blocks
We catalogued twelve ways an agent-to-agent handoff fails. This package
guarantees three of them. Not twelve. The rest are not transport-boundary
problems and are deliberately outside a 147-line buffer.
Every row below is verified by `tools/e2e_attack.py` against the installed
wheel, not against the source tree.
	Failure	Class	This package
E01	loss	TRANSPORT	⛔ no end-to-end acknowledgement or durable delivery here
E02	duplicate	TRANSPORT	blocks — the same `event_id` is accepted once
E03	replay	TRANSPORT	blocks — expired envelopes are never delivered
E04	out-of-order	TRANSPORT	blocks — FIFO is preserved
E05	stale state	STATE	⛔ no versioning here
E06	conflict	STATE	⛔ no compare-and-swap here
E07	schema mismatch	SCHEMA	⛔ payload is opaque by design
E08	identity spoofing	AUTHORITY	⛔ `sender` is asserted, not proven
E09	unauthorized action	AUTHORITY	⛔ no authority model here
E10	partial failure	PROPAGATION	⛔ no transaction here
E11	poison propagation	PROPAGATION	⛔ needs a payload contract, which is not here
E12	false completion	COMPLETION	⛔ this buffer does not judge completion
Run it yourself:
```bash
pip install hebom-buffer
python tools/e2e_attack.py     # prints 3/12 and why
```
If that number ever disagrees with this table, the table is wrong. A test
enforces it.
What it also does
These four are what handoff integrity looks like when nothing goes wrong:
	
backpressure	a full buffer returns `BUSY`, it never blocks silently
recipient routing	an item addressed to B is not handed to C
payload hash	every item carries a SHA-256 you can check yourself
sink isolation	if your recording sink throws, delivery still succeeds
⛔ None of them decide whether the payload is correct. They decide whether
the handoff itself was intact.
Why three is worth having
E11 is the expensive failure — one malformed handoff calls every downstream
model. This package does not block E11 on its own, because deciding what
"malformed" means requires a payload contract, and this buffer treats payloads
as opaque.
What it does give you is the place to put that check. Before:
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
~11µs, a model call is ~1.5s. Having a place to reject early is worth
four orders of magnitude — but only if you put a contract there. This package
gives you the seam, not the contract.
⛔ And it is in-memory. If the process restarts, anything still queued is gone.
That is why E01 is not on the guaranteed list.
We attacked our own implementation first
Our first buffer had none of the three guarantees above. It lost items on
overload, delivered duplicates, and had no expiry.
```bash
python -m pytest tests/          # unit tests
python tools/e2e_attack.py       # adversarial, against the installed wheel
```
Not a replacement for A2A or MCP
A2A moves messages. MCP invokes tools. HEBOM Buffer adds transport-boundary
guarantees before downstream consumption — deduplication, expiry and ordering
at the seam between two agents.
⛔ It does not decide whether a payload is semantically valid. Neither does
A2A. That judgement needs a payload contract, and this buffer treats payloads
as opaque.
```python
def on_a2a_message(msg):
    r = room.pass_(msg.payload, sender=msg.sender, recipient=msg.recipient)
    if not r["ok"]:
        return refuse(r["why"])        # the downstream model is never called
```
Honest limits
Process-local. Separate workers cannot share this buffer.
Multi-core scaling is unproven. Our test machine has one core.
It does not judge payload quality. Only whether the handoff is well-formed.
No sender signatures. Identity is asserted, not proven, in this package.
Result schema
Every result carries `https://hebom.org/schema/buffer-result/1`.
This is our v1 schema, not an industry standard. Whether it becomes one is
decided by adoption. What we do promise:
`E01`–`E12` meanings and numbers never change within v1
new failures get new numbers (`E13`, `E14`, …)
a structural change means a new URL (`/buffer-result/2`)
a v1 consumer can read v1 forever
Results also carry `origin`. A run on your own machine is `local`. It is
not a HEBOM verification, and this package cannot claim otherwise —
`origin="hebom_verified"` raises. See TRADEMARK.md.
Conformance telemetry — off by default
Nothing is sent unless you turn it on. See exactly what would be sent:
```bash
python -m hebom.telemetry join
```
Sent (only if you opt in): which check blocked, how many times, its class,
package and Python version, and a random per-install id stored at
`~/.hebom/install`.
⛔ Never sent: payload, intent text, keys, sender/recipient names, hostnames,
usernames, file paths. The install id is not derived from any machine
property — delete the file and you are a different install.
Why off by default: this is meant to sit between parties who do not trust each
other. A neutral party that collects by default is not neutral. Participants
get their percentile and the cohort failure map in return.
Questions we would like torn apart
Is this the right layer, or should A2A absorb it?
Which failure modes are we missing?
Does anyone actually lose money to this, or are we solving our own problem?
Related work
Different layer, same failure class — worth knowing about:
Attow Nexus — a local
coordination daemon and Git-like state ledger for agents. Replay, rollback and
diffing after something went wrong. This buffer sits before that: it
refuses the handoff so there is less to roll back.
A2A, MCP — transport and tool invocation. Neither decides whether a payload
should have been delivered.
Licence
Code: Apache-2.0. Name: see TRADEMARK.md — the code is open,
the name is not.
