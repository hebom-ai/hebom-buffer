# -*- coding: utf-8 -*-
"""⛔ README 의 «막는다/못 막는다» 표가 커널과 어긋나면 실패한다.
   주장과 코드가 갈라지는 것을 «시험»이 막는다."""
import re, time
from pathlib import Path
from hebom import Room

README = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
BLOCKS = set(re.findall(r"\|\s*(E\d\d)\s*\|[^|]*\|[^|]*\|\s*\*\*blocks\*\*", README))
NOT    = set(re.findall(r"\|\s*(E\d\d)\s*\|[^|]*\|[^|]*\|\s*⛔", README))

def test_table_is_complete_and_disjoint():
    assert BLOCKS | NOT == {f"E{i:02d}" for i in range(1, 13)}
    assert not (BLOCKS & NOT)

def test_readme_claims_exactly_three():
    """⛔ E01 은 «보장 목록에 없다». 빈 큐에서 아무것도 안 나온 것은
       loss 차단의 증거가 아니고, 이 버퍼는 재시작을 못 견딘다"""
    assert BLOCKS == {"E02", "E03", "E04"}, BLOCKS

def test_e01_is_honestly_not_guaranteed():
    import re as _re
    row = _re.search(r"\|\s*E01\s*\|[^\n]*", README).group(0)
    assert "⛔" in row and "durable" in row.lower()

def test_e02_duplicate_really_blocked():
    r = Room(); r.pass_({"c": 1}, event_id="d")
    assert r.pass_({"c": 1}, event_id="d")["code"] == "DUPLICATE"
    n = 0
    while r.take(): n += 1
    assert n == 1

def test_e03_replay_really_blocked():
    r = Room(); r.pass_("old", event_id="t", ttl_s=0.02); time.sleep(0.05)
    assert r.take() is None

def test_e04_fifo_really_preserved():
    r = Room()
    for i in range(20): r.pass_({"i": i}, event_id=f"o{i}")
    assert [r.take()["payload"]["i"] for _ in range(20)] == list(range(20))

def test_e07_is_honestly_not_blocked():
    """README 가 «못 막는다»고 했으면 실제로 통과해야 한다 — 과소주장도 거짓이다"""
    r = Room(); r.pass_({"anything": "at all"}, event_id="s")
    assert r.take() is not None

def test_e08_sender_is_asserted_not_proven():
    r = Room(); r.pass_({"x": 1}, sender="did:agent:VICTIM", event_id="sp")
    it = r.take()
    assert it["sender"] == "did:agent:VICTIM"
    assert "sig" not in it and "signature" not in it
