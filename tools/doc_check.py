# -*- coding: utf-8 -*-
"""⛔ 실행서·릴리스 문구는 «코드 밖»이라 audit.py 가 못 잡는다.
   그래서 따로 본다. 올리기 전에 돌릴 것.

    python3 tools/doc_check.py ../HEBOM_출시실행서.md
"""
import sys, re
from pathlib import Path

# ⛔ 2026-09-03: 「every downstream model」을 통짜로 금지했더니
#    «문제를 설명하는» 문장까지 잡았다("one malformed handoff calls every
#    downstream model" — 이건 사실이고 과대주장이 아니다).
#    ★ 금지 대상은 «능력 주장»이다. 정규식으로 «주어 + 동사»를 본다
BANNED_RE = [
    (r"(stops|prevents|blocks)\s+(one\s+bad\s+)?[a-z ]*handoff[a-z ]*from\s+calling",
     "능력 주장 — 이 패키지는 E11 을 «못 막는다»"),
    (r"(this|the)\s+(package|buffer|library)[^.]{0,40}(stops|prevents)[^.]{0,40}downstream",
     "능력 주장 — E11 과대주장"),
]
BANNED = [
    ("stops one bad AI handoff",        "E11 을 막는다는 인상"),
    ("12 failure modes blocked",        "12개를 막는다는 거짓"),
    ("Twelve failure modes blocked",    "같음"),
    ("12 failure modes, pinned",        "커밋 메시지 오독 여지"),
    ("broke our own AI agent pipeline 12 ways", "옛 Show HN 제목"),
    ("failed all 12",                   "옛 표현"),
    ("blocks four",                     "옛 숫자"),
    ("4 / 12",                          "옛 숫자"),
    ("none of the four guarantees",     "옛 숫자"),
    ("8 passed",                        "옛 시험 결과"),
]
# ⛔ 공통 한 줄은 «패키지 문서»에만 필수다. 게시문은 채널마다 문장이 다르다
REQUIRED_ALL = [("3/12", "실측 보장 수")]
REQUIRED_PKG = [("Deduplication, expiry and ordering at the boundary between AI agents",
                 "공통 한 줄 — pyproject·README·GitHub Description 이 같아야 한다")]
# ⛔ 문서마다 표현이 다르다. 「3개」를 말하는 방식만 다를 뿐 뜻은 같아야 한다
REQUIRED_ANY = [(("guarantees three", "guarantees 3"), "보장 수를 «명시»")]

def check(path):
    t = Path(path).read_text(encoding="utf-8")
    bad = [(p, why) for p, why in BANNED if p.lower() in t.lower()]
    for rx, why in BANNED_RE:
        m = re.search(rx, t, re.I)
        if m: bad.append((m.group(0)[:44], why))
    miss = [(p, why) for p, why in REQUIRED_ALL if p not in t]
    if Path(path).name in ("README.md",):
        miss += [(p, why) for p, why in REQUIRED_PKG if p not in t]
    miss += [(" 또는 ".join(g), why) for g, why in REQUIRED_ANY
             if not any(x in t for x in g)]
    print("=" * 72); print(f"  문서 점검 — {path}"); print("=" * 72)
    for p, why in bad:  print(f"  ⛔ 옛 문구 남음   「{p}」 — {why}")
    for p, why in miss: print(f"  ⚠ 필수 문구 없음 「{p}」 — {why}")
    if not bad and not miss: print("  ★ 통과 — 옛 문구 없음, 필수 문구 있음")
    return not bad and not miss

if __name__ == "__main__":
    ok = all(check(p) for p in (sys.argv[1:] or ["README.md"]))
    sys.exit(0 if ok else 1)
