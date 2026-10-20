"""data/drilling/contracts.csv + meta.json -> docs/drilling/index.html

검증에 실패하면 0이 아닌 코드로 종료한다(잘못된 데이터가 게시되지 않도록).
"""
import csv, html, json, re, shutil, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "drilling"
OUT = ROOT / "docs" / "drilling"

COLS = ["company", "first_seen", "quarter", "rig", "generation", "gen_from_catalog", "rig_class",
        "customer", "location", "start", "end", "dayrate_usd", "status", "base_contract",
        "acquired_fleet", "press_release_estimate", "confirmed", "note", "stat_exclude"]
COS = ("RIG", "NE", "SDRL")
GENS = {"8G", "7G", "6G", "5G", "HE", "MW", "JU"}
STATUS = {"Firm", "Option", "LOI", "LOA", "Contingent"}
GEN_COLOR = {"8G": "#E5601F", "7G": "#2B6CB0", "6G": "#2A9D8F", "5G": "#7c8aa0",
             "HE": "#9B5DE5", "MW": "#b7a67a", "JU": "#c9b7d9"}
CO_COLOR = {"RIG": "#E5601F", "NE": "#1C3D5A", "SDRL": "#2A9D8F"}


def tf(v):
    v = str(v).strip().lower()
    if v in ("true", "1"):
        return True
    if v in ("false", "0", ""):
        return False
    raise ValueError(v)


def load():
    with open(DATA / "contracts.csv", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows or list(rows[0].keys()) != COLS:
        sys.exit(f"CSV 열이 다릅니다: {list(rows[0].keys()) if rows else '빈 파일'}")
    errs, seen, gen_of = [], {}, {}
    for n, r in enumerate(rows, start=2):
        def bad(msg):
            errs.append(f"{n}행 {r.get('company')} {r.get('rig')}: {msg}")
        if r["company"] not in COS: bad("company")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["first_seen"]): bad("first_seen 형식")
        if r["generation"] not in GENS: bad("generation")
        if r["status"] not in STATUS: bad("status")
        try:
            rate = int(float(r["dayrate_usd"]))
            if not 20000 <= rate <= 1000000: bad(f"dayrate 범위 {rate}")
        except ValueError:
            bad("dayrate 숫자 아님")
        for b in ("base_contract", "acquired_fleet", "press_release_estimate", "confirmed"):
            try:
                tf(r[b])
            except ValueError:
                bad(f"{b} 값")
        k = (r["company"], r["first_seen"], r["rig"], r["dayrate_usd"], r["start"], r["end"])
        if k in seen: bad(f"{seen[k]}행과 중복")
        seen[k] = n
        g = gen_of.setdefault(r["rig"], r["generation"])
        if g != r["generation"]: bad(f"같은 리그의 세대 불일치 {g} vs {r['generation']}")
    if errs:
        sys.exit("데이터 검증 실패\n" + "\n".join(errs[:50]))
    return rows


def to_fx(r):
    return {"date": r["first_seen"], "q": r["quarter"], "rig": r["rig"], "gen": r["generation"],
            "cls": r["rig_class"], "cust": r["customer"], "loc": r["location"], "start": r["start"],
            "end": r["end"], "rate": int(float(r["dayrate_usd"])), "st": r["status"],
            "base": tf(r["base_contract"]), "note": r["note"], "conf": tf(r["confirmed"]),
            "co": r["company"], "acq": tf(r["acquired_fleet"]), "pr": tf(r["press_release_estimate"]),
            "ex": r["stat_exclude"].strip()}


def esc(v):
    return html.escape(str(v))


def pr_card(fx, meta):
    last = meta["last_fsr"]
    rows = sorted([f for f in fx if f["date"] > last[f["co"]]],
                  key=lambda f: (f["date"], f["rate"]), reverse=True)
    if not rows:
        return ""
    names = meta["companies"]
    since = " · ".join(f"{names[c]} {last[c]}" for c in COS)
    tr = []
    for f in rows:
        rate = f"${round(f['rate'] / 1000)}k" + (" ◇" if f["pr"] else "")
        ex = f' · <b style="color:#b45309">통계 제외</b> {esc(f["ex"])}' if f["ex"] else ""
        tr.append(
            f'<tr><td>{esc(f["date"])}</td><td><span class="dot" style="background:{CO_COLOR[f["co"]]}"></span>{f["co"]}</td>'
            f'<td>{esc(f["rig"])}</td><td><span class="dot" style="background:{GEN_COLOR[f["gen"]]}"></span>{f["gen"]}</td>'
            f'<td>{esc(f["cust"])} · {esc(f["loc"])}</td><td>{esc(f["start"])} ~ {esc(f["end"])}</td>'
            f'<td style="font-weight:700">{rate}</td><td style="color:#6b7280">{esc(f["note"])}{ex}</td></tr>')
    return (
        '<div class="card" style="border-left:4px solid var(--orange)">\n'
        f'  <h2>최근 선대현황보고서(FSR) 이후 공시된 계약 {len(rows)}건</h2>\n'
        '  <div class="sub">아직 FSR 표에 실리지 않은 보도자료 기반 계약. ◇는 계약총액÷일수로 역산한 추정 일당. '
        f'다음 FSR이 나오면 공시값으로 교체한다. 기준 FSR: {since}</div>\n'
        '  <div style="overflow:auto;border:1px solid var(--line);border-radius:10px"><table class="fx">\n'
        '  <thead><tr><th>공시일</th><th>회사</th><th>리그</th><th>세대</th><th>고객 · 지역</th><th>기간</th><th>추정 일당</th><th>비고</th></tr></thead><tbody>\n'
        + "\n".join(tr) + "\n  </tbody></table></div>\n</div>")


def update_log(meta):
    items = "".join(f"<li><b>{esc(u['date'])}</b> {esc(u['summary'])}</li>"
                    for u in meta.get("update_log", [])[-12:][::-1])
    return ('<div class="card"><h2>갱신 기록</h2><ul class="note" style="margin:0;padding-left:18px;font-size:12.5px;line-height:1.6">'
            + items + "</ul></div>")


def median(a):
    a = sorted(a)
    if not a:
        return None
    k = len(a) // 2
    return a[k] if len(a) % 2 else (a[k - 1] + a[k]) / 2


def main():
    rows = load()
    meta = json.load(open(DATA / "meta.json", encoding="utf-8"))
    fx = [to_fx(r) for r in rows]
    through = max(f["date"] for f in fx)
    y, m = int(through[:4]), int(through[5:7])
    year_ago = f"{y - 1}-{m:02d}"
    prs = [f for f in fx if f["pr"]]
    latest_pr = max((f["date"] for f in prs), default="")
    lp_cos = sorted({f["co"] for f in prs if f["date"] == latest_pr})
    label = f"{int(latest_pr[5:7])}/{int(latest_pr[8:10])} {'·'.join(lp_cos)}" if latest_pr else ""
    js_meta = {"through": through.replace("-", "."), "year_ago": year_ago,
               "x1": max(2027.75, round(y + (m - 0.5) / 12 + 0.95, 2)),
               "latest_pr": latest_pr, "latest_pr_label": label}
    cnt = {c: sum(f["co"] == c for f in fx) for c in COS}
    subtitle = (f"2011.1 ~ {through[:7].replace('-', '.')} 각사 분기 선대현황보고서(FSR)에서 리그별 계약·일당 용선료를 뽑아 "
                f"'최초 등장' 시점에 점으로 찍는다 · RIG {cnt['RIG']}건 · NE {cnt['NE']}건 · SDRL {cnt['SDRL']}건 · 작성 KT")
    t = (ROOT / "templates" / "drilling.html").read_text(encoding="utf-8")
    data_js = json.dumps(fx, ensure_ascii=False).replace("</", "<\\/")
    out = (t.replace("/*DATA*/", data_js).replace("/*META*/", json.dumps(js_meta, ensure_ascii=False))
           .replace("{{SUBTITLE}}", esc(subtitle)).replace("{{THROUGH}}", through)
           .replace("{{CHECKED}}", esc(meta.get("last_update_run", "")))
           .replace("{{SOURCES}}", esc(meta["sources_note"])).replace("{{PR_CARD}}", pr_card(fx, meta))
           .replace("{{UPDATE_LOG}}", update_log(meta)))
    left = re.findall(r"\{\{[A-Z_]+\}\}|/\*(?:DATA|META)\*/", out)
    if left:
        sys.exit(f"치환 안 된 자리표시자: {left}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(out, encoding="utf-8")
    shutil.copy(DATA / "contracts.csv", OUT / "contracts.csv")
    # 허브 카드가 읽는 요약: 7G·8G 확정 신규계약, 최근 1년
    firm = [f["rate"] for f in fx if f["conf"] and not f["ex"] and f["st"] != "Option" and not f["base"]
            and not f["acq"] and f["gen"] in ("7G", "8G") and f["date"] >= year_ago]
    summary = {"through": through, "checked": meta.get("last_update_run", ""), "contracts": len(fx),
               "uldw_median_1y": median(firm), "uldw_n_1y": len(firm), "built": date.today().isoformat()}
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    print(f"OK {len(fx)}건, 기준일 {through}, 7G·8G 최근1년 중앙 {summary['uldw_median_1y']} (n={len(firm)})")


if __name__ == "__main__":
    main()
