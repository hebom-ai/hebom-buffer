import threading, time
from hebom import Room

# 1. Ctrl+C / Ctrl+V level API
r=Room(capacity=10)
a=r.pass_("안녕하세요 🌍", intent="greet", sender="AI-A", recipient="AI-B", event_id="e1")
assert a["accepted"]
x=r.take(recipient="AI-B")
assert x["payload"]=="안녕하세요 🌍" and x["intent"]=="greet"

# 2. exact duplicate is not delivered twice
r=Room()
assert r.pass_({"x":1}, event_id="dup")["accepted"]
assert r.pass_({"x":1}, event_id="dup")["code"]=="DUPLICATE"
assert r.take()["payload"]=={"x":1}
assert r.take() is None

# 3. explicit backpressure
r=Room(capacity=1)
assert r.pass_(1,event_id="b1")["accepted"]
b=r.pass_(2,event_id="b2")
assert b["code"]=="BUSY" and not b["accepted"]
assert r.take()["payload"]==1
assert r.pass_(2,event_id="b2")["accepted"]  # BUSY reservation rolled back

# 4. expiry
r=Room(); r.pass_("old",event_id="ttl",ttl_s=0.01); time.sleep(0.02)
assert r.take() is None

# 5. multilingual / arbitrary JSON remains opaque and hash-stable
r=Room(); payload={"한국어":"값","日本語":"値","العربية":"قيمة","emoji":"🧠","n":7}
r.pass_(payload,event_id="lang"); y=r.take(); assert y["payload"]==payload and len(y["payload_hash"])==64

# 6. concurrent ingress: 32 x 500 = 16,000 accepted, none lost
N,T=32,500; r=Room(capacity=N*T+10); accepted=[]; lock=threading.Lock()
def w(i):
    local=0
    for j in range(T):
        if r.pass_({"i":i,"j":j},event_id=f"{i}:{j}")["accepted"]: local+=1
    with lock: accepted.append(local)
ts=[threading.Thread(target=w,args=(i,)) for i in range(N)]
[t.start() for t in ts]; [t.join() for t in ts]
assert sum(accepted)==N*T, sum(accepted)
seen=set()
for _ in range(N*T):
    z=r.take(); assert z is not None; seen.add(z["id"])
assert len(seen)==N*T and r.take() is None

# 7. after-path failure must not break delivery
r=Room(after_sink=lambda _: (_ for _ in ()).throw(RuntimeError("ledger down")))
r.pass_("safe",event_id="sink"); assert r.take()["payload"]=="safe"

print("ALL TESTS PASSED")
print("concurrent accepted/taken:", N*T, N*T)
print("public operations: PASS / TAKE")
