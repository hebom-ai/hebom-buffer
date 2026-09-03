# -*- coding: utf-8 -*-
"""★ 12모드 «실제 차단» 시험 — 분류표가 아니라 «커널»을 때린다

  고장 입력 생성 → 실제 Room 통과 → downstream 으로 «갔는가?» → E-code 기록

⛔ 이 시험은 «설치된» 패키지를 쓴다. 저장소가 아니라 wheel 이 진짜다.
"""
import sys, os, time, threading, json
sys.path = [p for p in sys.path if os.path.abspath(p) != os.getcwd()]  # ⛔ 저장소 배제
from hebom import Room
from hebom.schema import MODES, CLASSES

R = {}
def rec(code, blocked, note): R[code] = (blocked, note)

# ── E01 loss — ⛔ 실제로 «잃는가»를 잰다 ─────────────────────
def e01():
    """⛔ 2026-09-03 정정: 이전 시험은 «빈 큐에서 아무것도 안 나온 것»을
       「loss 차단」으로 판정했다. 아무것도 안 넣었으니 당연하다 — 거짓 판정이었다.
       ★ 진짜 시험: 받았다고 «수락»한 것이 실제로 «전달되는가», 그리고
          프로세스가 죽으면 «살아남는가»"""
    r = Room(capacity=5)
    acc = [r.pass_({"i": i}, event_id=f"L{i}")["accepted"] for i in range(8)]
    accepted = sum(acc)
    delivered = 0
    while r.take(): delivered += 1
    # 수락한 것은 «전부» 전달된다 — 여기까지는 참
    in_memory_only = True     # ⛔ 재시작하면 대기중인 것은 «사라진다»
    return (not in_memory_only), \
           (f"수락 {accepted}건 → 전달 {delivered}건 (일치). "
            f"⛔ 그러나 «종단 확인·영속 보장 없음» — 재시작 시 유실")

# ── E02 duplicate ──────────────────────────────────────
def e02():
    r = Room()
    r.pass_({"cmd": "charge"}, event_id="c1")
    second = r.pass_({"cmd": "charge"}, event_id="c1")
    n = 0
    while r.take(): n += 1
    return (second["code"] == "DUPLICATE" and n == 1), f"두 번째 «거부» · 전달 {n}건"

# ── E03 replay — 만료된 옛 명령 ─────────────────────────
def e03():
    r = Room()
    r.pass_({"cmd": "old"}, event_id="r1", ttl_s=0.02)
    time.sleep(0.05)
    return (r.take() is None), "만료된 것은 «안 나온다»"

# ── E04 out-of-order ───────────────────────────────────
def e04():
    r = Room()
    for i in range(30): r.pass_({"i": i}, event_id=f"o{i}")
    got = [r.take()["payload"]["i"] for _ in range(30)]
    return (got == sorted(got)), f"FIFO 보존 {got[:3]}…{got[-2:]}"

# ── E05 stale state ────────────────────────────────────
def e05():
    r = Room()
    r.pass_({"v": 1}, event_id="s1")
    return None, "⛔ 커널에 «버전/CAS 없음» — 판정 불가"

# ── E06 conflict ───────────────────────────────────────
def e06():
    return None, "⛔ 커널에 «CAS 없음» — 판정 불가"

# ── E07 schema mismatch ────────────────────────────────
def e07():
    r = Room()
    ok = r.pass_({"완전히": "엉뚱한 모양"}, event_id="x1")
    got = r.take()
    return (got is None), "⛔ payload 는 opaque — 통과시킨다" if got else "차단"

# ── E08 identity spoofing ──────────────────────────────
def e08():
    r = Room()
    r.pass_({"x": 1}, sender="did:agent:VICTIM", event_id="sp")
    got = r.take()
    return (got is None), f"⛔ sender «{got['sender']}» 를 그대로 받음 — 서명 없음"

# ── E09 unauthorized action ────────────────────────────
def e09():
    r = Room()
    r.pass_({"action": "charge_card"}, event_id="u1")
    return (r.take() is None), "⛔ 권한 개념 «없음» — 통과"

# ── E10 partial failure ────────────────────────────────
def e10():
    r = Room()
    r.pass_({"part": 1}, event_id="p1")     # 2개 중 1개만
    return (r.take() is None), "⛔ 트랜잭션 «없음» — 1개만 와도 전달"

# ── E11 poison propagation ★ 가장 중요 ─────────────────
def e11():
    calls = {"n": 0}
    def downstream(item): calls["n"] += 1
    r = Room(after_sink=downstream)
    r.pass_({"columns": ["상호"], "rows": "엉뚱"}, event_id="poison")
    got = r.take()
    return (got is None and calls["n"] == 0), \
           f"⛔ 오염이 하류로 «전달»됨 · after_sink {calls['n']}회 호출"

# ── E12 false completion ───────────────────────────────
def e12():
    r = Room()
    r.pass_({"status": "partial"}, event_id="f1")
    return (r.take() is None), "⛔ 완료 판정 개념 «없음»"

# ── 커널이 «실제로» 하는 것 ─────────────────────────────
def extra():
    out = []
    r = Room(capacity=2)
    r.pass_(1, event_id="b1"); r.pass_(2, event_id="b2")
    out.append(("backpressure", r.pass_(3, event_id="b3")["code"] == "BUSY", "가득 차면 BUSY"))
    r2 = Room()
    r2.pass_({"x": 1}, recipient="B", event_id="rt")
    out.append(("recipient 라우팅", r2.take(recipient="C") is None, "남의 것은 «안 준다»"))
    r3 = Room()
    r3.pass_({"x": 1}, event_id="h1")
    it = r3.take()
    import hashlib, json as _j
    h = hashlib.sha256(_j.dumps({"x": 1}, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":"), default=str).encode()).hexdigest()
    out.append(("payload 해시", it["payload_hash"] == h, "밖에서 «대조 가능»"))
    def bad(_): raise RuntimeError("sink down")
    r4 = Room(after_sink=bad); r4.pass_("safe", event_id="sk")
    out.append(("싱크 격리", r4.take()["payload"] == "safe", "싱크가 죽어도 전달"))
    return out

print("═"*86)
print("  ★ 12모드 «실제 차단» 시험 — 설치된 wheel 을 때린다")
print("═"*86)
print(f"  {'':<5}{'모드':<22}{'분류':<13}{'실제':<9}근거")
for code, fn in [("E01",e01),("E02",e02),("E03",e03),("E04",e04),("E05",e05),("E06",e06),
                 ("E07",e07),("E08",e08),("E09",e09),("E10",e10),("E11",e11),("E12",e12)]:
    b, note = fn(); rec(code, b, note)
    mark = "★ 차단" if b else ("⚠ 해당없음" if b is None else "⛔ 통과")
    print(f"  {code:<5}{MODES[code]:<22}{CLASSES[code]:<13}{mark:<9}{note[:44]}")
blocked = sum(1 for b,_ in R.values() if b is True)
passed  = sum(1 for b,_ in R.values() if b is False)
na      = sum(1 for b,_ in R.values() if b is None)
print("─"*86)
print(f"  ★ 커널이 «실제로» 보장하는 것 {blocked}/12 · ⛔ 통과 {passed} · ⚠ 해당없음 {na}")
print("\n  ── 커널이 실제로 하는 «다른» 것 ──")
for n,ok,note in extra():
    print(f"  {'★' if ok else '⛔'} {n:<18}{note}")
print(f"""
  ⛔⛔ README 가 「12 failure modes blocked」로 읽히면 «거짓»이다.
     ⛔ E01 은 «보장 목록에서 뺐다» — 수락한 것은 전달되지만, 종단 확인도
        영속 보장도 없다. 재시작하면 대기중인 것이 «사라진다»
     147줄 커널은 «전송 계층»만 한다. 나머지는 «이 패키지 밖»이다.
  ★ 고칠 방향은 둘 중 하나뿐이다
     ① README 를 «실제로 막는 것»만 주장하게 좁힌다   ← 오늘 할 수 있다
     ② 12개를 «전부 커널에» 넣는다                   ← 147줄이 «깨진다»
""")
