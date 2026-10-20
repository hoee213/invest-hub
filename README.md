# invest-hub — KT 투자 지표

페이지: https://hoee213.github.io/invest-hub/

| 목차 | 경로 | 갱신 |
|---|---|---|
| 해양시추 일당 용선료 (RIG·NE·SDRL) | `docs/drilling/` | 매주 토요일 |
| KRX 20일·60일 신고가 | `docs/highs/` | 평일 16:07·18:37 KST |
| 변곡점 대시보드 | 외부 링크 (macro-regime-watch) | 매일 |
| Finviz 차트 | 외부 링크 (finviz-charts) | 매일 |

## 해양시추 용선료 주간 갱신 흐름
1. 토 07:17 KST `drilling-fetch` (GitHub Actions): SEC 8-K, Transocean·Noble FSR PDF, Seadrill IR 보도자료 중 새 것을 `inbox/drilling/`에 텍스트로 저장.
2. 토 12:00 KST Claude 루틴: `UPDATE_RULES.md`대로 새 계약을 `data/drilling/contracts.csv`에 추가하고 커밋.
3. `site` (GitHub Actions): CSV 검증 → `docs/drilling/` 재생성 → Pages 게시 → 텔레그램 요약.

직접 고칠 때: CSV를 고치고 `python scripts/build_drilling.py`로 확인한 뒤 푸시하면 된다.

## KRX 신고가
- `scripts/krx_highs.py`: 다음 금융 종목별 일봉(KRX 정규장, 종목당 100거래일)으로 매일 전부 다시 계산한다. 가격 이력을 저장하지 않는다.
- 결과: `docs/highs/days/YYYY-MM-DD.json`(그날 신고가 종목), `docs/highs/index.json`(날짜별 개수). 2026-07-01부터 백필.
- 과거 날짜 다시 계산: `python scripts/krx_highs.py --backfill 2026-07-01`. 같은 날 강제 재계산: `--force`.
- Actions가 매일 커밋하므로 로컬에서 푸시 전에 `git pull --rebase` 필수.
