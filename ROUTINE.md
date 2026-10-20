# Claude 주간 루틴 설정 (미생성 · GitHub 연결 대기)

- 이름: 해양시추 용선료 주간 갱신 (invest-hub)
- 일정: 매주 토요일 12:00 KST = cron `0 3 * * 6` (UTC)
- 모델: claude-sonnet-5-5 · 환경: Default (env_01YFK41dct8NnkwZ2JKaHWdw)
- 저장소: https://github.com/hoee213/invest-hub · 도구: Bash, Read, Write, Edit, Glob, Grep
- 2026-10-20 생성 시도 → `github_token_missing`(claude.ai 계정에 GitHub 미연결). 연결 후 Claude에게 "ROUTINE.md대로 루틴 만들어줘"라고 하면 된다.

## 프롬프트
너는 hoee213/invest-hub 저장소의 '해양시추 일당 용선료' 데이터를 매주 갱신하는 에이전트다. 사람에게 질문하지 말고 끝까지 처리한다.

1. `git pull origin main`으로 최신 상태를 받는다.
2. 저장소 루트의 `UPDATE_RULES.md`를 처음부터 끝까지 읽는다. 이 문서가 유일한 작업 기준이다.
3. 문서의 절차 1~7을 그대로 수행한다. 요약하면: 수집기 실행 시도(네트워크가 막혀 실패해도 계속) → `inbox/drilling/*.txt`(processed 폴더 제외)를 날짜순으로 읽기 → 새 계약을 `data/drilling/contracts.csv`에 규칙대로 추가하거나 보도자료 추정 행을 FSR 공시값으로 교체 → 처리한 파일을 `git mv`로 `inbox/drilling/processed/`에 옮기기 → `data/drilling/meta.json`의 `last_update_run`(오늘 KST 날짜), `update_log`, 필요하면 `last_fsr` 갱신 → `python scripts/build_drilling.py`가 OK로 끝날 때까지 수정 → 커밋·푸시.
4. 숫자는 원문에서 두 번 확인한다. 추정 일당은 note에 총액과 일수를 함께 적는다. 기존 행은 지우지 않는다. 확신이 없는 값은 넣지 말고 update_log 요약에 '보류: 리그명(이유)'로 남긴다.
5. inbox가 비어 있어도 `last_update_run`과 update_log(`새 계약 공시 없음`)는 갱신하고 커밋한다. 그래야 홈페이지에 점검 날짜가 찍힌다.
6. 커밋 메시지는 반드시 `drilling: 주간 갱신 YYYY-MM-DD (신규 N건)` 형식(이 접두어가 있어야 텔레그램 요약이 나간다). `git push origin HEAD:main`이 거부되면 `git push origin HEAD:claude/drilling-YYYYMMDD`로 올린다.
7. 마지막에 추가·수정한 행 목록(회사, 리그, 일당, 근거 공시)과 보류 항목을 짧게 보고한다.
