"""새 공시 수집기: 처음 보는 계약 관련 공시를 텍스트로 바꿔 inbox/drilling/ 에 저장한다.

출처
  RIG  : SEC EDGAR 8-K 첨부(보도자료·FSR) + deepwater.com FSR PDF 목록
  NE   : SEC EDGAR 8-K 첨부 + noblecorp.com FSR 다운로드 목록
  SDRL : SEC EDGAR 8-K 첨부 + ir.seadrill.com 보도자료 피드(Q4) + 재무자료 피드의 FSR

이미 본 항목은 data/drilling/sources_state.json 에 기록한다.
  python scripts/fetch_drilling_sources.py          # 새 항목만 저장
  python scripts/fetch_drilling_sources.py --seed   # 지금 있는 것 전부 '본 것'으로 표시(저장 안 함)
inbox 에 쌓인 파일은 주간 루틴(Claude)이 읽고 CSV 에 반영한 뒤 processed/ 로 옮긴다.
"""
import io, json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "drilling" / "sources_state.json"
INBOX = ROOT / "inbox" / "drilling"

SEC_UA = {"User-Agent": "KT Park invest-hub research admin@invest-hub.example"}
WEB_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
CIK = {"RIG": 1451505, "NE": 1895262, "SDRL": 1737706}
SINCE = "2026-10-01"  # 이보다 오래된 SEC 공시는 보지 않는다
KEYWORDS = re.compile(r"contract|award|extension|fleet status|backlog|dayrate|day rate|option|letter of (intent|award)|LOI|LOA", re.I)
SKIP_TITLE = re.compile(r"conference call|schedules|webcast|dividend|director|pricing|offering|notes due|annual general|proxy", re.I)


def log(*a):
    print(*a, flush=True)


def get(url, ua, **kw):
    for i in range(3):
        try:
            r = requests.get(url, headers=ua, timeout=60, **kw)
            if r.status_code == 200:
                return r
            log(f"  HTTP {r.status_code} {url}")
            if r.status_code in (403, 404):
                return None
        except requests.RequestException as e:
            log(f"  오류 {e} {url}")
        time.sleep(2 + 3 * i)
    return None


def must(url, ua):
    """목록 페이지용: 응답이 없으면 예외를 내서 '깨진 출처'로 보고되게 한다."""
    r = get(url, ua)
    if r is None:
        raise RuntimeError(f"응답 없음 {url}")
    return r


def html_text(raw):
    soup = BeautifulSoup(raw, "html.parser")
    for t in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        t.decompose()
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        tr.replace_with(soup.new_string("\n" + " | ".join(c for c in cells if c) + "\n"))
    for t in soup.find_all(["p", "div", "li", "br", "h1", "h2", "h3", "h4", "table", "section"]):
        t.insert_after("\n")
    txt = re.sub(r"[ \t\r\xa0]+", " ", soup.get_text(""))
    return re.sub(r"\n\s*\n+", "\n\n", txt).strip()


def pdf_text(raw):
    import pdfplumber
    out = []
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        for n, p in enumerate(pdf.pages, 1):
            out.append(f"\n===== page {n} =====\n" + (p.extract_text(layout=False) or ""))
    return "".join(out)


def to_text(resp):
    ct = resp.headers.get("content-type", "")
    if "pdf" in ct or resp.content[:4] == b"%PDF":
        return pdf_text(resp.content)
    return html_text(resp.content)


# ---------- 항목 목록 만들기: (id, co, kind, date, title, url) ----------
def sec_items(co):
    j = must(f"https://data.sec.gov/submissions/CIK{CIK[co]:010d}.json", SEC_UA)
    if not j:
        return []
    r = j.json()["filings"]["recent"]
    items = []
    for i, form in enumerate(r["form"]):
        d = r["filingDate"][i]
        if d < SINCE or form not in ("8-K", "6-K"):
            continue
        its = r.get("items", [""] * len(r["form"]))[i] or ""
        if not re.search(r"7\.01|8\.01|2\.02", its) and form == "8-K":
            continue
        acc = r["accessionNumber"][i]
        base = f"https://www.sec.gov/Archives/edgar/data/{CIK[co]}/{acc.replace('-', '')}/"
        idx = get(base + "index.json", SEC_UA)
        time.sleep(0.3)
        if not idx:
            continue
        for f in idx.json()["directory"]["item"]:
            name = f["name"]
            if re.search(r"ex-?99|ex99|exhibit99", name, re.I) and name.lower().endswith((".htm", ".html", ".pdf")):
                items.append((f"sec:{acc}:{name}", co, "8K", d, f"{form} {acc} {name} items {its}", base + name))
    return items


def rig_fsr_items():
    r = must("https://www.deepwater.com/investors/fleet-status-report", WEB_UA)
    if not r:
        return []
    out = []
    for h in sorted(set(re.findall(r'href="([^"]*FleetStatusReport[^"]*\.pdf)"', r.text))):
        url = urljoin("https://www.deepwater.com/", h)
        m = re.search(r"/(\d{4})/([A-Za-z]+)%20\d{4}", h)
        d = f"{m.group(1)}-{datetime.strptime(m.group(2)[:3], '%b').month:02d}" if m else ""
        out.append((f"rigfsr:{h}", "RIG", "FSR", d, "Transocean Fleet Status Report " + h.split("/")[-1].replace("%20", " "), url))
    return out


def ne_fsr_items():
    r = must("https://noblecorp.com/our-investors/reports-filings/fleet-status-report/", WEB_UA)
    if not r:
        return []
    out = []
    for slug, wid in sorted(set(re.findall(r'href="https://noblecorp.com/download/([^/"]+)/\?wpdmdl=(\d+)', r.text))):
        if "fleet-status" not in slug:
            continue
        out.append((f"nefsr:{wid}", "NE", "FSR", "", f"Noble Fleet Status Report ({slug}, id {wid})",
                    f"https://noblecorp.com/download/{slug}/?wpdmdl={wid}"))
    return out


def sdrl_pr_items():
    u = ("https://ir.seadrill.com/feed/PressRelease.svc/GetPressReleaseList?LanguageId=1&bodyType=0"
         "&pressReleaseDateFilter=3&pageSize=30&pageNumber=0&includeTags=true&year=-1&excludeSelection=1")
    r = must(u, WEB_UA)
    if not r:
        return []
    out = []
    for p in r.json().get("GetPressReleaseListResult", []):
        d = datetime.strptime(p["PressReleaseDate"].split()[0], "%m/%d/%Y").date().isoformat()
        out.append((f"sdrlpr:{p['PressReleaseId']}", "SDRL", "PR", d, p["Headline"],
                    "https://ir.seadrill.com" + p["LinkToDetailPage"]))
    return out


def sdrl_fsr_items():
    u = ("https://ir.seadrill.com/feed/FinancialReport.svc/GetFinancialReportList?LanguageId=1&reportTypes="
         "&pageSize=8&pageNumber=0&year=-1&includeTags=true&reportSubType=")
    r = must(u, WEB_UA)
    if not r:
        return []
    out = []
    for rep in r.json().get("GetFinancialReportListResult", []):
        for doc in rep.get("Documents", []):
            if re.search(r"fleet", doc.get("DocumentTitle", ""), re.I):
                out.append((f"sdrlfsr:{doc['DocumentId']}", "SDRL", "FSR", "", f"Seadrill {rep['ReportTitle']} {doc['DocumentTitle']}",
                            doc["DocumentPath"]))
    return out


def main():
    seed = "--seed" in sys.argv
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"seen": {}}
    seen = state["seen"]
    sources = [("RIG SEC", lambda: sec_items("RIG")), ("NE SEC", lambda: sec_items("NE")),
               ("SDRL SEC", lambda: sec_items("SDRL")), ("RIG FSR", rig_fsr_items),
               ("NE FSR", ne_fsr_items), ("SDRL PR", sdrl_pr_items), ("SDRL FSR", sdrl_fsr_items)]
    items, broken = [], []
    for name, fn in sources:
        try:
            got = fn()
        except Exception as e:  # 한 출처가 깨져도 나머지는 계속
            got = []
            broken.append(name)
            log(f"[{name}] 실패: {e}")
        log(f"[{name}] {len(got)}개")
        items += got
    INBOX.mkdir(parents=True, exist_ok=True)
    new = 0
    today = datetime.now(timezone.utc).date().isoformat()
    for iid, co, kind, d, title, url in items:
        if iid in seen:
            continue
        if seed:
            seen[iid] = today
            continue
        if kind != "FSR" and SKIP_TITLE.search(title) and not KEYWORDS.search(title):
            seen[iid] = today
            continue
        r = get(url, SEC_UA if "sec.gov" in url else WEB_UA)
        time.sleep(0.5)
        if not r:
            continue  # 다음 주에 다시 시도
        txt = to_text(r)
        if kind != "FSR" and not KEYWORDS.search(title + " " + txt[:20000]):
            seen[iid] = today
            log(f"  관련 없음: {title[:70]}")
            continue
        slug = re.sub(r"[^A-Za-z0-9]+", "-", iid)[-60:].strip("-")
        fn = INBOX / f"{d or today}_{co}_{kind}_{slug}.txt"
        fn.write_text(f"source: {co} {kind}\ndate: {d}\ntitle: {title}\nurl: {url}\nfetched: {today}\n\n{txt}", encoding="utf-8")
        seen[iid] = today
        new += 1
        log(f"  저장 {fn.name}")
    state["seen"] = seen
    state["last_run"] = today
    state["broken_sources"] = broken
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    log(f"새 파일 {new}개 · 응답 없는 출처 {broken or '없음'}")


if __name__ == "__main__":
    main()
