# 해양시추 용선료 주간 갱신 규칙

주간 루틴(Claude 클라우드 에이전트)과 사람이 똑같이 따르는 절차다. 목표는 2011~2026.10 원본 데이터와 **같은 기준**으로 새 계약을 `data/drilling/contracts.csv`에 추가하는 것.

## 파일

| 파일 | 역할 |
|---|---|
| `data/drilling/contracts.csv` | 계약 데이터(유일한 원본). 열 순서 바꾸지 말 것 |
| `data/drilling/meta.json` | 회사별 마지막 FSR 날짜(`last_fsr`), 갱신 기록(`update_log`), 마지막 점검일(`last_update_run`) |
| `data/drilling/sources_state.json` | 수집기가 이미 본 공시 ID. 손으로 고치지 말 것 |
| `inbox/drilling/*.txt` | 수집기가 저장한 새 공시 텍스트. 처리 후 `inbox/drilling/processed/`로 옮긴다 |
| `scripts/build_drilling.py` | CSV 검증 + `docs/drilling/index.html` 생성. 검증 실패 시 종료 코드 1 |

## 절차

1. `python -m pip install -q requests beautifulsoup4 pdfplumber` 후 `python scripts/fetch_drilling_sources.py`를 한 번 돌린다. 네트워크가 막혀 실패해도 괜찮다. 매주 토요일 07시(KST) GitHub Actions가 같은 수집을 이미 돌려 `inbox/`에 넣어 둔다.
2. `inbox/drilling/`의 `.txt`를 날짜순으로 하나씩 읽는다. 첫 줄 `source:`가 회사와 종류(FSR / 8K / PR)다.
3. 종류별로 아래 규칙에 따라 CSV를 고친다.
4. 처리한 파일은 내용과 관계없이 `git mv`로 `inbox/drilling/processed/`에 옮긴다. 계약과 무관한 공시(실적 일정, 사채 발행 등)도 옮긴다.
5. `meta.json`을 고친다.
   - `last_update_run`: 오늘 날짜(KST, `YYYY-MM-DD`).
   - `update_log`에 한 줄 추가: `{"date": "...", "summary": "..."}`. 예: `"신규 3건 (RIG Deepwater Atlas $610k, SDRL West Vela ◇$455k …) · RIG 11월 FSR 반영"`. 새 공시가 없으면 `"새 계약 공시 없음"`.
   - FSR을 반영했으면 `last_fsr[회사]`를 그 FSR 공시일로 바꾼다.
6. `python scripts/build_drilling.py`가 `OK`로 끝나야 한다. 실패하면 메시지를 보고 CSV를 고친 뒤 다시 돌린다.
7. 커밋·푸시한다(아래 '커밋' 참고).

## CSV 열 채우는 법

| 열 | 값 |
|---|---|
| company | `RIG`, `NE`, `SDRL` |
| first_seen | 이 (리그, 용선료) 조합이 처음 공시된 날짜 `YYYY-MM-DD`. FSR이면 FSR 게시일, 보도자료면 보도자료 날짜 |
| quarter | first_seen의 분기 `YYYYQn` |
| rig | 기존 CSV에 있는 리그는 **철자 그대로** 쓴다 |
| generation | 기존 리그는 CSV 값 그대로. 새 리그는 아래 세대 분류로 정하고 `gen_from_catalog`를 `False` |
| rig_class | 기존 리그는 CSV 값 그대로. 쓰는 값: `UDW_drillship`, `UDW_semi`, `UDW_floater`, `HE_semi`, `HE_jackup`, `deepwater_floater`, `midwater_floater`, `jackup`, `tender`, `other` |
| customer, location | 공시 표기 그대로. 미공개면 `Undisclosed` |
| start, end | `YYYY-MM`. 분기·반기만 나오면 `2027-Q1`, `2027-H1`처럼 쓰고, 기간이 일수로만 나오면 end에 `+450일 (5공)` 형식 |
| dayrate_usd | 정수 달러 |
| status | `Firm`, `Option`, `LOI`, `LOA`, `Contingent` |
| base_contract, acquired_fleet | 새 계약은 `False` |
| press_release_estimate | 계약총액÷일수로 역산했으면 `True`(차트에서 ◇), 공시 일당이면 `False` |
| confirmed | `True`. 한 보고서에만 보이고 다음 보고서에서 사라진 값은 나중에 `False`로 바꾼다 |
| note | 근거와 계산을 한국어로. 예: `백로그 ~$2.25억(모빌 제외)÷450일 ≈ $500k · 8-K 2026.10.19` |
| stat_exclude | 통계에서 뺄 이유. 보통 비워 둔다 (아래 참고) |

## 종류별 규칙

### FSR(선대현황보고서)
- 표를 리그별로 훑어 일당이 숫자로 적힌 계약만 본다. `Not Disclosed`, `Market based`는 넣지 않는다.
- **최초 등장 규칙**: CSV에 같은 회사·같은 리그·같은 일당(±3.5%)·같은 기간이 이미 있으면 넣지 않는다. ±3.5% 이내 변화는 에스컬레이션으로 본다.
- 연 단계 인상 계약은 첫 단계만 넣는다.
- 보도자료 추정 행(◇)과 같은 계약이 FSR에 일당으로 나오면 **새 행을 만들지 말고 그 추정 행을 고친다**: `dayrate_usd`를 공시 일당으로, `press_release_estimate`를 `False`로, `stat_exclude`는 비우고, note 앞에 `보도자료 추정 $471k → FSR 공시 $455k · ` 를 붙인다. first_seen은 보도자료 날짜 그대로 둔다.
- Seadrill FSR은 2025.11부터 일당 열이 없다. TCV가 있으면 보도자료 규칙으로 처리한다.
- Noble FSR은 `valued at USD xM` 같은 총액이 많다. 보도자료 규칙으로 처리한다.
- FSR 공시일을 `meta.json`의 `last_fsr[회사]`에 적는다. Noble 파일에는 날짜가 비어 있으니 PDF 본문의 보고서 날짜를 쓴다.

### 보도자료·8-K(계약총액만 공시된 경우)
- 추정 일당 = 계약총액 ÷ 일수. 일수가 없으면 (종료월−시작월 개월 수 × 30.4).
- 플로터 추정값이 $20만 미만이거나 $65만 초과면 기간·모빌 왜곡으로 보고 **넣지 않는다**. update_log에 이름만 남긴다.
- 총액에 모빌라이제이션·추가 서비스가 **포함**됐다고 명시돼 있으면 넣되, `stat_exclude`에 `모빌·서비스 포함 총액÷일수, 실제 일당보다 높음`이라고 적는다. 잭업은 범위 필터가 없으니 이 규칙이 특히 중요하다.
- 금액 없이 기간만 늘어난 연장(예: "remaining priced options exercised", 금액 미공시)은 넣지 않는다.
- 옵션 행사로 원계약 단가가 그대로 이어지면 `status=Firm`, note에 `가격옵션 행사, 원계약 단가`.

### 통계 제외(stat_exclude)를 쓰는 경우
- 설치·업그레이드 기간의 임시 단가.
- 모빌·서비스가 섞인 총액 역산값.
- 그 밖에 시장 단가로 보기 어려운 값. 이유를 한 문장으로.

## 세대 분류(KT)
- 8G: Deepwater Titan, Deepwater Atlas (20K psi)
- 7G: Asgard, Invictus, Thalassa, Proteus, Pontus, Poseidon, Conqueror, Aquila, Skyros, Athena, Mylos, Apollo. Noble·Seadrill 리그는 **CSV 기존 값을 따른다**(예: Noble Voyager·Viking·Valiant·Faye Kozack, West Carina = 7G, West Capella·West Polaris = 6G)
- 6G: Clear Leader, Americas, Inspiration, India, Luanda, Champion, KG1/KG2, Petrobras 10000, Corcovado, Mykonos, Orion, Olympia, DD3
- 5G: Enterprise급, Deepwater Discovery급, DD I/II 등
- HE: 극한환경 반잠수식, MW: 구형 심해·중수심 플로터, JU: 잭업

## 정확성
- 숫자는 원문에서 두 번 읽고 넣는다. 341↔431 같은 자리 바뀜이 원본 데이터의 가장 흔한 오류였다.
- 추정 일당을 계산했으면 note에 총액과 일수를 함께 적어 누구나 다시 계산할 수 있게 한다.
- 기존 행은 지우지 않는다. 고칠 때는 note에 무엇을 왜 바꿨는지 남긴다.

## 커밋
- 커밋 메시지: `drilling: 주간 갱신 YYYY-MM-DD (신규 N건)`.
- `git push origin HEAD:main`. 거부되면 `git push origin HEAD:claude/drilling-YYYYMMDD`로 올린다. 이 브랜치는 GitHub Actions가 검증 후 main에 합치고 페이지를 다시 만든다.
