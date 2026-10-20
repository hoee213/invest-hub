# OPS_LOG — invest-hub

## 2026-10-20 구축
- 원본: 2026-10-19 claude.ai 세션 결과물(CSV 1,114건 + HTML 리포트)을 그대로 이식. HTML 내장 데이터와 CSV 1,114건 전부 일치 확인.
- `stat_exclude` 열 추가, 4건 지정: Deepwater Atlas $185k(20K BOP 설치 기간), Noble Regina Allen $272k·Noble Interceptor $258k(잭업 총액에 모빌 포함), Dhirubhai Deepwater KG2 $411k(서비스·모빌 포함).
- 출처 점검: Noble 보도자료(noble.gcs-web.com)는 Akamai가 403으로 막음 → Noble은 SEC 8-K + noblecorp.com FSR 다운로드만 사용. Seadrill 보도자료는 EDGAR에 없고 ir.seadrill.com Q4 피드(`/feed/PressRelease.svc/GetPressReleaseList`)로만 잡힌다.
- `sources_state.json`은 2026-10-20 기준 현재 공시 전부를 '본 것'으로 시드함(이미 CSV에 반영됨).
- SEC는 www.sec.gov에 `@users.noreply.github.com` 들어간 User-Agent를 403 처리했다. 지금 UA(`admin@invest-hub.example`)는 통과.

## 2026-10-20 KRX 신고가 추가
- 데이터 소스 비교: KRX 직접 조회(MDCSTAT01501)는 `LOGOUT` 400(로그인 필요). FinanceDataReader `StockListing('KRX')`는 FinanceData 깃허브 캐시 CSV를 읽는데, 10-19 파일 2,720행 중 546행이 종가가 고가·저가 범위 밖(장중 스냅샷 혼입) → 가격으로 쓰면 안 됨. 종목 목록 용도로만 사용.
- 네이버 fchart·api.stock.naver.com 일봉은 NXT 체결가가 섞인다(삼성전자 10-19 네이버 223,500 vs 다음 218,000). 다음 `finance.daum.net/api/quote/A{code}/days`(Referer 필요)가 KRX 정규장 값. 6스레드로 120종목 1.8초, 전종목 약 1분.
- 키움 REST API는 앱키 + 허용 IP 등록이 필요해 GitHub 러너(IP 가변)에서 못 쓴다. OpenAPI+는 영웅문 로그인한 윈도 PC 필요. 신고가 계산에는 불필요해 보류.
- 백필 2026-07-01~10-19, 73거래일, 4.1MB. 샘플 검증(삼성SDI·LG엔솔·동국산업) 일치.
