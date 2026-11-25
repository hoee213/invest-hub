"""MYBOX 'KT 주식투자' 폴더의 HTML 자료 -> docs/research/ 복사 + index.json 생성.

폴더 구조(폴더 = 사이드바 메뉴):
  기업분석/국내주식, 기업분석/해외주식
  탐방, 콥데이, 컨콜/국내주식, 탐방, 콥데이, 컨콜/해외주식

사용: python scripts/build_research.py [원본폴더]   (기본 N:\\개인\\KT 주식투자)
      --push 를 붙이면 커밋·푸시까지 한다.
MYBOX는 로컬에만 있으므로 Actions가 아니라 로컬에서 돌린다.
"""
import html, json, re, shutil, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "research"
SRC_DEFAULT = Path(r"N:\개인\KT 주식투자")

SECTIONS = [  # (폴더명, 키, 라벨)
    ("기업분석", "analysis", "기업분석"),
    ("탐방, 콥데이, 컨콜", "meetings", "탐방·콥데이·컨콜"),
]
MARKETS = [("국내주식", "kr"), ("해외주식", "us")]
KINDS = ["컨콜", "콥데이", "탐방", "기업분석"]
TITLE_NOISE = re.compile(r"\s*[|·]\s*(HYPR_Hyperfine|KT)\s*$")


def parse_date(stem):
    toks = re.findall(r"(?<!\d)(\d{8}|\d{6}|\d{4})(?!\d)", stem)
    for t in reversed(toks):
        if len(t) == 8 and t.startswith("20"):
            return f"{t[:4]}-{t[4:6]}-{t[6:]}"
        if len(t) == 6 and 1 <= int(t[2:4]) <= 12 and not re.search(r"_" + t + r"_", stem):
            return f"20{t[:2]}-{t[2:4]}-{t[4:]}"
        if len(t) == 4 and 1 <= int(t[2:]) <= 12:
            return f"20{t[:2]}-{t[2:]}"
    return ""


def read_title(p):
    head = p.read_text(encoding="utf-8", errors="replace")[:6000]
    m = re.search(r"<title>(.*?)</title>", head, re.S | re.I)
    t = html.unescape(m.group(1)).strip() if m else p.stem
    for _ in range(2):
        t = TITLE_NOISE.sub("", t)
    return re.sub(r"\s+", " ", t)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = Path(args[0]) if args else SRC_DEFAULT
    if not src.exists():
        sys.exit(f"원본 폴더 없음: {src}")
    if OUT.exists():
        shutil.rmtree(OUT)
    items = []
    for folder, skey, slabel in SECTIONS:
        for mfolder, mkey in MARKETS:
            d = src / folder / mfolder
            if not d.exists():
                continue
            for p in sorted(d.glob("*.htm*")):
                stem = p.stem
                safe = re.sub(r"[\s,#%?&]+", "_", stem) + ".html"
                rel = f"files/{skey}/{mkey}/{safe}"
                (OUT / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, OUT / rel)
                title = read_title(p)
                kind = next((k for k in KINDS if k in stem), "기업분석" if skey == "analysis" else "탐방")
                code = re.search(r"(?<!\d)(\d{6})(?!\d)", stem + " " + title)
                code = code.group(1) if code and not code.group(1).startswith("26") else ""
                company = re.split(r"[_\s(]", stem, 1)[0]
                items.append({
                    "id": f"{skey}-{mkey}-{len(items)}", "section": skey, "market": mkey,
                    "kind": kind, "company": company, "code": code,
                    "date": parse_date(stem), "title": title, "path": rel,
                    "kb": round(p.stat().st_size / 1024),
                })
    items.sort(key=lambda x: (x["date"], x["company"]), reverse=True)
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"sections": [{"key": k, "label": l} for _, k, l in SECTIONS],
            "markets": [{"key": k, "label": l} for l, k in MARKETS], "items": items}
    (OUT / "index.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    for it in items:
        print(f"{it['section']:8} {it['market']} {it['date']:10} {it['kind']:4} {it['company']:10} {it['title']}")
    print(f"총 {len(items)}건 -> {OUT}")

    if "--push" in sys.argv:
        g = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], check=True)
        g("pull", "--rebase", "-q")
        g("add", "docs/research")
        if subprocess.run(["git", "-C", str(ROOT), "diff", "--cached", "--quiet"]).returncode:
            g("commit", "-q", "-m", f"research: 자료 {len(items)}건 동기화")
            g("push", "-q")
            print("푸시 완료")
        else:
            print("변경 없음")


if __name__ == "__main__":
    main()
