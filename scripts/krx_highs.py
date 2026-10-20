"""KRX 20일·60일 신고가 일간 리스트.

가격: 다음 금융 종목별 일봉 API (KRX 정규장 기준, NXT 체결가 섞이지 않음). 종목당 최근 100거래일.
종목군: 코스피·코스닥 보통주 (FinanceData KRX 상장목록 캐시, 실패 시 마지막 저장본). 스팩·우선주·리츠 제외.
정의 (기존 S&P500 신고가 알림과 같은 방식):
  종가 기준 N일 신고가: 오늘 종가 == 최근 N거래일(오늘 포함) 최고 종가
  장중 기준 N일 신고가: 오늘 고가 == 최근 N거래일(오늘 포함) 최고 고가
  상장 N거래일 미만 종목은 제외 (상장 직후 종목이 전부 신고가로 잡히는 것을 막음)
출력: docs/highs/days/YYYY-MM-DD.json, docs/highs/index.json

  python scripts/krx_highs.py                      # 최근 거래일 계산 + 빠졌거나 잠정인 날 보충
  장 마감(15:45) 전에 돌면 오늘은 장중 값으로 '잠정' 파일을 만들고, 마감 후 실행이 확정값으로 덮어쓴다.
  python scripts/krx_highs.py --backfill 2026-07-01   # 그날부터 최근 거래일까지 전부 다시 계산
"""
import io, json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "highs"
DAYS = OUT / "days"
UNIVERSE = ROOT / "data" / "highs" / "universe.csv"
KST = timezone(timedelta(hours=9))
WINDOWS = (20, 60)
CLOSE_MIN = 15 * 60 + 45  # 이 시각(KST) 전이면 오늘 일봉은 장중 값
CATCHUP = 10  # 최근 N거래일 안에서 빠진 날·잠정인 날을 다시 계산
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
      "Referer": "https://finance.daum.net/"}
EXCLUDE_NAME = re.compile(r"스팩|리츠|[0-9]+호$|우$|우B$|우C$|\(전환\)$")


def log(*a):
    print(*a, flush=True)


def load_universe():
    """코스피·코스닥 보통주 목록. 캐시 저장소에서 최근 날짜 파일을 찾고, 없으면 마지막 저장본을 쓴다."""
    today = datetime.now(KST).date()
    for back in range(0, 10):
        d = (today - timedelta(days=back)).isoformat()
        url = f"https://raw.githubusercontent.com/FinanceData/fdr_krx_data_cache/refs/heads/master/data/listing/krx/{d}.csv"
        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                continue
            df = pd.read_csv(io.StringIO(r.content.decode("utf-8-sig")), index_col=0,
                             dtype={"Code": str, "MarketId": str})
            df = df[df["MarketId"].isin(["STK", "KSQ"])]
            df = df[df["Code"].str.fullmatch(r"\d{5}0") & ~df["Name"].str.contains(EXCLUDE_NAME)]
            u = df[["Code", "Name", "MarketId"]].rename(columns={"Code": "code", "Name": "name", "MarketId": "mkt"})
            u["mkt"] = u["mkt"].map({"STK": "KOSPI", "KSQ": "KOSDAQ"})
            if len(u) > 2000:
                UNIVERSE.parent.mkdir(parents=True, exist_ok=True)
                u.to_csv(UNIVERSE, index=False, encoding="utf-8")
                log(f"종목군 {len(u)}개 (상장목록 {d})")
                return u
        except Exception as e:
            log(f"  상장목록 {d} 실패: {e}")
    if UNIVERSE.exists():
        u = pd.read_csv(UNIVERSE, dtype={"code": str})
        log(f"종목군 {len(u)}개 (저장본 사용)")
        return u
    sys.exit("종목군을 만들 수 없음")


S = requests.Session()
S.headers.update(UA)


def daum_days(code, pages=1):
    rows = []
    for p in range(1, pages + 1):
        for i in range(4):
            try:
                r = S.get(f"https://finance.daum.net/api/quote/A{code}/days", timeout=20,
                          params={"symbolCode": "A" + code, "page": p, "perPage": 100, "pagination": "true"})
                if r.status_code == 200:
                    rows += r.json().get("data", [])
                    break
                if r.status_code == 404:
                    return code, rows
            except (requests.RequestException, ValueError):
                pass
            time.sleep(1 + 2 * i)
        else:
            return code, None  # 실패
    return code, rows


def fetch_all(codes, pages):
    data, failed = {}, []
    t = time.time()
    with ThreadPoolExecutor(6) as ex:
        for n, (code, rows) in enumerate(ex.map(lambda c: daum_days(c, pages), codes), 1):
            if rows is None:
                failed.append(code)
            elif rows:
                data[code] = rows
            if n % 500 == 0:
                log(f"  수집 {n}/{len(codes)} ({time.time() - t:.0f}초)")
    log(f"수집 완료 {len(data)}종목, 실패 {len(failed)} ({time.time() - t:.0f}초)")
    if len(failed) > len(codes) * 0.05:
        sys.exit(f"실패가 너무 많음 {len(failed)}개 — 다음 금융 응답 이상")
    return data


def panels(data):
    recs = []
    for code, rows in data.items():
        for x in rows:
            recs.append((code, x["date"][:10], x["tradePrice"], x["highPrice"], x["accTradeVolume"],
                         x["accTradePrice"], x["prevClosingPrice"], x.get("listedSharesCount") or 0))
    df = pd.DataFrame(recs, columns=["code", "date", "close", "high", "vol", "amt", "prev", "shares"])
    df = df.drop_duplicates(["code", "date"])
    P = {k: df.pivot(index="date", columns="code", values=k).sort_index() for k in
         ("close", "high", "vol", "amt", "prev", "shares")}
    # 휴장일·거래정지 처리: 거래량 0인 날은 신고가 판정에서 뺀다
    traded = P["vol"].fillna(0) > 0
    for k in ("close", "high"):
        P[k] = P[k].where(traded)
    return P


def compute_day(P, d, uni):
    names = uni.set_index("code")
    i = P["close"].index.get_loc(d)
    out, counts = [], {}
    flags = {}
    for n in WINDOWS:
        if i + 1 < n:
            return None
        wc = P["close"].iloc[i + 1 - n:i + 1]
        wh = P["high"].iloc[i + 1 - n:i + 1]
        enough = wc.notna().sum() >= n * 0.8  # 상장 N거래일 미만·장기 정지 제외
        today_c, today_h = wc.iloc[-1], wh.iloc[-1]
        flags[f"c{n}"] = (today_c >= wc.max()) & enough & today_c.notna()
        flags[f"h{n}"] = (today_h >= wh.max()) & enough & today_h.notna()
        counts[f"c{n}"] = int(flags[f"c{n}"].sum())
        counts[f"h{n}"] = int(flags[f"h{n}"].sum())
    any_flag = pd.concat(flags.values(), axis=1).any(axis=1)
    row = {k: P[k].iloc[i] for k in P}
    for code in any_flag[any_flag].index:
        if code not in names.index:
            continue
        c, prev = float(row["close"][code]), float(row["prev"][code] or 0)
        out.append({
            "code": code, "name": names.at[code, "name"], "mkt": names.at[code, "mkt"],
            "close": int(c), "chg": round((c / prev - 1) * 100, 2) if prev else None,
            "amt": round(float(row["amt"][code]) / 1e8, 1),
            "cap": round(c * float(row["shares"][code] or 0) / 1e8),
            **{k: bool(v[code]) for k, v in flags.items()},
        })
    out.sort(key=lambda x: -x["amt"])
    traded_n = int((P["vol"].iloc[i].fillna(0) > 0).sum())
    return {"date": d, "universe": traded_n, "counts": counts, "items": out}


def add_streak_and_new(day, prev):
    """연속 일수와 '신규 진입'(어제 목록에 없던 종목) 표시."""
    pmap = {x["code"]: x for x in (prev or {}).get("items", [])}
    for x in day["items"]:
        p = pmap.get(x["code"], {})
        for k in ("c20", "h20", "c60", "h60"):
            x[k + "s"] = (p.get(k + "s", 0) + 1) if x[k] else 0


def needs_update(d):
    f = DAYS / f"{d}.json"
    return not f.exists() or json.loads(f.read_text(encoding="utf-8")).get("prelim", False)


def write_index():
    idx = []
    for f in sorted(DAYS.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        idx.append({"date": d["date"], "universe": d["universe"], **d["counts"],
                    **({"prelim": True, "asof": d["asof"]} if d.get("prelim") else {})})
    (OUT / "index.json").write_text(json.dumps({"updated": datetime.now(KST).isoformat(timespec="minutes"), "days": idx},
                                               ensure_ascii=False), encoding="utf-8")
    return idx


def telegram(day, caught=()):
    tok, chat = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT")
    if not tok or not chat:
        return
    c = day["counts"]
    top = [x for x in day["items"] if x["c60"]][:10]
    head = f"⏳ KRX 신고가 {day['date']} 장중 잠정 ({day['asof']} 기준)" if day.get("prelim")         else f"📈 KRX 신고가 {day['date']} (종가 기준)"
    lines = [head,
             f"20일 {c['c20']}개 · 60일 {c['c60']}개 / {day['universe']}종목",
             "60일 신고가 거래대금 상위:"]
    lines += [f"• {x['name']} {x['close']:,}원 {x['chg']:+.1f}% · {x['amt']:,.0f}억" + (" 🆕" if x["c60s"] == 1 else "") for x in top]
    if caught:
        lines.append("밀린 날 확정 반영: " + ", ".join(caught))
    lines.append(f"https://hoee213.github.io/invest-hub/highs/#{day['date']}")
    try:
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", timeout=30,
                      data={"chat_id": chat, "text": "\n".join(lines), "disable_web_page_preview": "true"})
    except requests.RequestException as e:
        log(f"텔레그램 실패 {e}")


def main():
    backfill = sys.argv[sys.argv.index("--backfill") + 1] if "--backfill" in sys.argv else None
    uni = load_universe()
    data = fetch_all(uni["code"].tolist(), pages=2 if backfill else 1)
    P = panels(data)
    # 거래일 달력: 삼성전자처럼 거래가 꾸준한 종목이 다수 있는 날만 남긴다
    alive = P["vol"].notna().sum(axis=1)
    P = {k: v[alive > len(data) * 0.5] for k, v in P.items()}
    dates = list(P["close"].index)
    now = datetime.now(KST)
    intraday = bool(dates) and dates[-1] == now.date().isoformat() and now.hour * 60 + now.minute < CLOSE_MIN
    complete = dates[:-1] if intraday else dates
    DAYS.mkdir(parents=True, exist_ok=True)
    if backfill:
        targets = [d for d in complete if d >= backfill]
    else:
        targets = [d for d in complete[-CATCHUP:] if needs_update(d) or ("--force" in sys.argv and d == complete[-1])]
    if intraday and not backfill:
        targets.append(dates[-1])
    if not targets:
        log("새로 계산할 날 없음 — 건너뜀 (휴장일이거나 이미 처리됨)")
        write_index()
        return
    made, finals = None, []
    for d in targets:
        day = compute_day(P, d, uni)
        if day is None:
            log(f"{d}: 이력 부족으로 건너뜀")
            continue
        prev_dates = [x for x in dates if x < d]
        pf = DAYS / f"{prev_dates[-1]}.json" if prev_dates else None
        prev = json.loads(pf.read_text(encoding="utf-8")) if pf and pf.exists() else None
        add_streak_and_new(day, prev)
        if intraday and d == dates[-1]:
            day["prelim"], day["asof"] = True, now.strftime("%H:%M")
        else:
            finals.append(d)
        (DAYS / f"{d}.json").write_text(json.dumps(day, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        log(f"{d}{' (잠정)' if day.get('prelim') else ''}: 종가 20일 {day['counts']['c20']} · 60일 {day['counts']['c60']} | 장중 20일 {day['counts']['h20']} · 60일 {day['counts']['h60']}")
        made = day
    write_index()
    if made and not backfill:
        telegram(made, [d for d in finals if d != made["date"]])


if __name__ == "__main__":
    main()
