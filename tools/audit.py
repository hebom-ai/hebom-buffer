# -*- coding: utf-8 -*-
"""출시 전 감사 — README 주장 대 코드. 어긋나면 «올리지 않는다»"""
import os, re, json, subprocess, sys, hashlib, ast, importlib.metadata as md
from pathlib import Path
# ⛔ 2026-09-03: tools/ 에서 실행하면 sys.path[0] 이 tools/ 라 «site-packages 의
#    옛 패키지»를 읽었다. 반드시 «저장소 폴더»를 먼저 본다
sys.path.insert(0, os.getcwd())
for m in [k for k in sys.modules if k.startswith("hebom")]: del sys.modules[m]
R=[]
def T(n, fn):
    try: ok, note = fn()
    except Exception as e: ok, note = False, f"EXC {type(e).__name__}: {str(e)[:52]}"
    R.append((n,ok)); print(("  ★ 통과 " if ok else "  ⛔ 불합격")+f" {n:<34}{note[:52]}")

ROOT=Path("."); README=(ROOT/"README.md").read_text(encoding="utf-8")
BUF=(ROOT/"hebom/_buffer.py").read_text(encoding="utf-8")

print("═"*84); print("  A. 폴더 위생 — «넣지 말아야 할 것»이 없는가"); print("═"*84)
def a1():
    allow={"README.md","LICENSE","NOTICE","TRADEMARK.md","pyproject.toml",".gitignore"}
    bad=[]
    for p in ROOT.rglob("*"):
        if any(x in p.parts for x in ("dist","build",".git","__pycache__",
                                      ".pytest_cache",".venv","venv")) \
           or ".egg-info" in p.relative_to(ROOT).as_posix(): continue
        if p.is_dir(): continue
        # ⛔ 2026-09-03 윈도우 실측: str() 은 «역슬래시»를 준다(hebom\schema.py).
        #    「hebom/」 로 비교하니 «정상 파일»이 전부 허용 밖으로 잡혔다.
        #    ★ as_posix() 로 «항상 슬래시»로 맞춘다
        rel=p.relative_to(ROOT).as_posix()
        if rel in allow or rel.startswith(("hebom/","tests/","examples/","tools/")): continue
        bad.append(rel)
    return not bad, f"허용 밖 파일 {bad}" if bad else "허용 목록만 있음"
def a2():
    leak=[]
    pat=re.compile(r"(사업계획|수익구조|특허|PCT|청구항|계약서|Settlement 계약|영업|매출|원가|KEPT)")
    for p in list(ROOT.rglob("*.py"))+list(ROOT.rglob("*.md"))+list(ROOT.rglob("*.toml")):
        # ⛔ tools/ 는 «배포에 안 들어간다» — 감사 스크립트 자신이 금칙어를 갖고 있다
        if any(x in p.parts for x in ("dist","build","__pycache__",".git","tools",
                                      ".pytest_cache",".venv","venv")): continue
        if p.name.endswith(".egg-info") or ".egg-info" in str(p): continue
        t=p.read_text(encoding="utf-8",errors="ignore")
        m=pat.findall(t)
        if m: leak.append((str(p.relative_to(ROOT)), sorted(set(m))[:3]))
    return not leak, f"내부 용어 유출 {leak}" if leak else "사업·특허 용어 «없음»"
def a3():
    bad=[]
    for p in ROOT.rglob("*.py"):
        if any(x in p.parts for x in ("dist","build","__pycache__")): continue
        t=p.read_text(encoding="utf-8",errors="ignore")
        for pat in (r"sk-[A-Za-z0-9]{10,}", r"AIza[0-9A-Za-z_-]{20,}", r"AQ\.[A-Za-z0-9]{20,}",
                    r"-----BEGIN [A-Z ]*PRIVATE KEY"):
            if re.search(pat,t): bad.append(str(p))
    return not bad, f"열쇠 흔적 {bad}" if bad else "API 키·개인키 «없음»"
def a4():
    t=(ROOT/"pyproject.toml").read_text(encoding="utf-8")
    ph=[x for x in ("PLACEHOLDER","[이름]","[메일]","you@example.com") if x in t]
    return not ph, f"⛔ 자리표시자 남음 {ph}" if ph else "자리표시자 없음"
T("허용 목록 밖 파일", a1); T("사업·특허 용어 유출", a2); T("열쇠·비밀", a3)
T("pyproject 자리표시자", a4)

print("\n"+"═"*84); print("  B. README 주장 «한 줄씩» 코드로 때린다"); print("═"*84)
def b1():
    total=len(BUF.splitlines())
    m=re.search(r"One file, (\d+) lines", README)
    if not m: return False, "README 에 줄 수 주장이 «없다»"
    return int(m.group(1))==total, f"README {m.group(1)}줄 · 실제 파일 {total}줄"
def b2():
    tree=ast.parse(BUF)
    pub=[f.name for c in tree.body if isinstance(c,ast.ClassDef) and c.name=="UniversalRoom"
         for f in c.body if isinstance(f,ast.FunctionDef) and not f.name.startswith("_")]
    return set(pub)<= {"pass_","take","stats"}, f"공개 메서드 {sorted(pub)}"
def b3():
    return "dependencies = []" in (ROOT/"pyproject.toml").read_text(encoding="utf-8"), \
           "No dependencies 주장 대 pyproject"
def b4():
    import hebom
    r=hebom.Room(); r.pass_({"x":1}, event_id="1", recipient="B")
    return r.take(recipient="B")["payload"]=={"x":1}, "README 첫 예제가 «그대로» 돈다"
def b5():
    import hebom.telemetry as T2
    return T2.ENABLED_DEFAULT is False and "off by default" in README.lower(), \
           "README 「off by default」 = 코드 기본값"
def b6():
    import hebom.telemetry as T2, platform, getpass, os as _o
    p=T2.Telemetry(enabled=False); p.note("E01",False)
    blob=json.dumps(p.payload())
    leaks=[]
    for name,v in (("hostname",platform.node()),("cwd",_o.getcwd()),
                   ("user",_o.environ.get("USER",""))):
        if v and v in blob: leaks.append(name)
    return not leaks, f"유출 {leaks}" if leaks else "hostname·cwd·user «없음»"
def b7():
    from hebom.schema import result, ORIGIN_HEBOM
    try: result("E01",False,origin=ORIGIN_HEBOM); return False,"로컬이 hebom_verified 주장 «성공»"
    except ValueError: return True,"«거부»됨"
def b8():
    from hebom import MODES
    claimed=set(re.findall(r"\|\s*(E\d\d)\s*\|", README))
    return claimed==set(MODES), f"README 표 {len(claimed)}개 = MODES {len(MODES)}개"

def b11():
    """★ 분류표 존재 ≠ 탐지기 구현 ≠ 실제 차단. «차단»을 직접 잰다"""
    # ⛔ 2026-09-03 윈도우 실측: 인코딩을 안 정하면 cp949 로 읽어 «UnicodeDecodeError».
    #    감사가 «거짓 불합격»을 냈다 — 도구가 자기 하위 프로세스를 «못 읽은 것»
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    out = subprocess.run([sys.executable, "tools/e2e_attack.py"],
                         capture_output=True, text=True,
                         encoding="utf-8", errors="replace", env=env)
    m = re.search(r"(\d+)\s*/\s*12\s*[·.]", out.stdout or "")
    if not m: m = re.search(r"보장하는 것\s*(\d+)\s*/\s*12", out.stdout or "")
    if not m:
        return False, f"e2e_attack 결과를 «못 읽음» (rc={out.returncode})"
    measured=int(m.group(1))
    blocks=set(re.findall(r"\|\s*(E\d\d)\s*\|[^|]*\|[^|]*\|\s*\*\*blocks\*\*", README))
    return measured==len(blocks), f"실측 차단 {measured}/12 · README 주장 {len(blocks)}개"

def b12():
    """⛔ 과대주장 금지 — 「12 blocked」류 문구가 남아 있으면 불합격"""
    bad=[x for x in ("12 failure modes blocked","blocks all twelve","12 / 12",
                     "blocks four","4 / 12","Neither decides whether the payload")
         if x.lower() in README.lower()]
    return not bad, f"과대주장 {bad}" if bad else "과대주장 «없음»"

def b14():
    """⛔ 2026-09-03: 감사가 「none of the four guarantees」를 «못 잡았다».
       숫자가 문서 «전체»에서 일관되는지 기계로 센다"""
    n=len(re.findall(r"\|\s*E\d\d\s*\|[^|]*\|[^|]*\|\s*\*\*blocks\*\*", README))
    words={3:"three",4:"four",5:"five",12:"twelve"}
    must=words[n]
    stale=[w for k,w in words.items() if k!=n and
           re.search(rf"\b(none of the|the) {w} guarantees?\b", README)]
    ok_here = re.search(rf"\bguarantees {must}\b", README) is not None
    ok_num  = f"prints {n}/12" in README
    return (not stale) and ok_here and ok_num, \
           (f"⛔ 옛 숫자 {stale}" if stale else
            f"blocks {n}개 · 「guarantees {must}」 {ok_here} · 「prints {n}/12」 {ok_num}")

def b15():
    """⛔ pyproject Summary 가 README 보다 «세게» 말하면 불합격.
       PyPI 검색에 «가장 먼저» 뜨는 한 줄이다"""
    t=(ROOT/"pyproject.toml").read_text(encoding="utf-8")
    m=re.search(r'description\s*=\s*"([^"]+)"', t)
    if not m: return False, "description 없음"
    d=m.group(1)
    over=[w for w in ("stops","prevents","blocks all","every downstream","guarantees 12",
                      "twelve") if w in d.lower()]
    return not over, f"⛔ Summary 과대주장 {over} — 「{d[:44]}」" if over else f"「{d[:52]}」"

def b13():
    """⛔ 자리표시자가 wheel METADATA 에 «박히지» 않았는가"""
    import zipfile
    ws=list(Path("dist").glob("*.whl"))
    if not ws: return False, "wheel 없음"
    meta=[n for n in zipfile.ZipFile(ws[0]).namelist() if n.endswith("METADATA")][0]
    t=zipfile.ZipFile(ws[0]).read(meta).decode()
    ph=[x for x in ("[org]","PLACEHOLDER","you@example.com","[이름]","[메일]") if x in t]
    return not ph, f"⛔ METADATA 에 자리표시자 {ph}" if ph else "METADATA 깨끗"
def b9():
    # README 가 «인정한 한계»가 실제로 한계인가
    import hebom
    r=hebom.Room(); r.pass_({"x":1}, sender="did:agent:A", event_id="s")
    it=r.take()
    has_sig = any(k in it for k in ("sig","signature"))
    claims_no_sig = "No sender signatures" in README
    return (not has_sig) and claims_no_sig, "「서명 없음」을 «인정»했고 실제로 없다"
def b10():
    return ("Process-local" in README and "Multi-core scaling is unproven" in README
            and "does not judge payload quality" in README), "한계 3종 «명시»됨"
for n,f in [("147줄 주장",b1),("공개 표면 = pass_/take",b2),("의존성 0",b3),
            ("README 첫 예제 동작",b4),("텔레메트리 기본 OFF",b5),
            ("★ 텔레메트리 신원 유출",b6),("★ origin 거부",b7),
            ("12모드 표 일치",b8),("한계: 서명 없음",b9),("한계 3종 명시",b10),
            ("★★★ 주장 = 실제 차단 수",b11),("★ 과대주장 금지",b12),
            ("★ wheel METADATA 자리표시자",b13),
            ("★★ 숫자 일관성 (문서 전체)",b14),("★★ Summary 과대주장",b15)]:
    T(n,f)

print("\n"+"═"*84); print("  C. 패키지 — 깨끗한 환경에서"); print("═"*84)
def c1():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    out = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"],
                         capture_output=True, text=True,
                         encoding="utf-8", errors="replace", env=env)
    return out.returncode==0, out.stdout.strip().splitlines()[-1] if out.stdout else "?"
def c2():
    ws=list(Path("dist").glob("*.whl")) if Path("dist").exists() else []
    return len(ws)==1, f"wheel {ws[0].name if ws else '없음'}"
def c3():
    import zipfile
    w=list(Path("dist").glob("*.whl"))[0]
    names=zipfile.ZipFile(w).namelist()
    bad=[n for n in names if n.endswith((".jsonl",".xlsx",".db")) or "test" in n.lower()]
    return not bad, f"wheel 안 «불필요 파일» {bad}" if bad else f"{len(names)}개 파일 · 군더더기 없음"
def c4():
    t=(ROOT/"LICENSE").read_text(encoding="utf-8")
    return "Apache License" in t and "Version 2.0" in t, "LICENSE = Apache-2.0"
def c5():
    t=(ROOT/"NOTICE").read_text(encoding="utf-8")
    return "trademark" in t.lower() and "TRADEMARK.md" in t, "NOTICE 가 상표 분리를 «명시»"
for n,f in [("전체 시험",c1),("wheel 1개",c2),("wheel 내용물",c3),
            ("LICENSE",c4),("NOTICE↔TRADEMARK",c5)]:
    T(n,f)

print("\n"+"═"*84); print("  D. ★ 경계 — 본체가 «새어 들어오지» 않았는가"); print("═"*84)
def d1():
    ban=("Shapley","counterfactual","반사실","Settlement","Guarantee","CompletionRank",
         "Contribution","Verified Completion","VCP","Outcome")
    hit=[]
    for p in list(ROOT.rglob("hebom/*.py"))+list(ROOT.rglob("tests/*.py")):
        if "tools" in p.parts: continue
        t=p.read_text(encoding="utf-8",errors="ignore")
        for b in ban:
            if b in t: hit.append((p.name,b))
    return not hit, f"본체 개념 유입 {hit}" if hit else "입구층만 있음"
def d2():
    import hebom
    pub=[x for x in hebom.__all__]
    return set(pub)<={"Room","UniversalRoom","Envelope","BufferFull","InvalidEnvelope",
                      "SCHEMA_ID","SCHEMA_VERSION","MODES","result","Telemetry","VERSION"}, \
           f"__all__ {len(pub)}개"
T("★ 본체 개념 유입", d1); T("공개 심볼 목록", d2)

print("─"*84)
ok=sum(1 for _,o in R if o)
print(f"  {ok}/{len(R)}")
print("\n  ⛔ 하나라도 불합격이면 «PyPI 에 올리지 않는다». 1.0.0 은 되돌릴 수 없다"
      if ok<len(R) else "\n  ★ 전부 통과 — 올릴 준비가 됐다")
