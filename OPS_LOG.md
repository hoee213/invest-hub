# OPS_LOG — invest-hub

## 2026-10-20 구축
- 원본: 2026-10-19 claude.ai 세션 결과물(CSV 1,114건 + HTML 리포트)을 그대로 이식. HTML 내장 데이터와 CSV 1,114건 전부 일치 확인.
- `stat_exclude` 열 추가, 4건 지정: Deepwater Atlas $185k(20K BOP 설치 기간), Noble Regina Allen $272k·Noble Interceptor $258k(잭업 총액에 모빌 포함), Dhirubhai Deepwater KG2 $411k(서비스·모빌 포함).
- 출처 점검: Noble 보도자료(noble.gcs-web.com)는 Akamai가 403으로 막음 → Noble은 SEC 8-K + noblecorp.com FSR 다운로드만 사용. Seadrill 보도자료는 EDGAR에 없고 ir.seadrill.com Q4 피드(`/feed/PressRelease.svc/GetPressReleaseList`)로만 잡힌다.
- `sources_state.json`은 2026-10-20 기준 현재 공시 전부를 '본 것'으로 시드함(이미 CSV에 반영됨).
- SEC는 www.sec.gov에 `@users.noreply.github.com` 들어간 User-Agent를 403 처리했다. 지금 UA(`admin@invest-hub.example`)는 통과.
