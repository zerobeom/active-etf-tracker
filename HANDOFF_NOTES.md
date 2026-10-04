# Active ETF Tracker — 인수인계 메모 (새 채팅용)

새 채팅에서 이 메모를 올리면 바로 이어서 작업 가능. **긴 세션들을 정리한 문서라 내용이 많음 — 필요한 섹션만 봐도 됨.**

> ⚠️ **가장 중요 — 최신 소스는 GitHub 저장소다.**
> 이 프로젝트는 매 세션마다 GitHub 웹(연필 아이콘으로 직접 편집, 또는 Add file→Upload files)에 파일을
> 직접 올려서 반영해왔다. 새 채팅에서 코드를 봐야 하면 **저장소(`zerobeom/active-etf-tracker`, 기본
> 브랜치 `main`)에서 최신 파일을 Raw 링크로 받아서** 확인할 것. 특히 `index.html`과
> `scripts/fetch_holdings.py`는 매 세션 계속 바뀌고 있음.
> **사용자는 GitHub 초보 · 한국어로 소통. 파일은 항상 "통째로 교체" 방식으로 안내할 것(부분 수정 X).**

## 무엇인가
- **여러 운용사의 액티브 ETF 7종**의 일별 구성종목("포트폴리오") 변동(편입·매수·유지·매도·편출)과
  벤치마크 지수 대비 수익률을 추적하는 정적 웹사이트(GitHub Pages) + 매일 도는 GitHub Actions
  파이썬 수집 작업.
- 원래 "KoAct ETF Tracker"(삼성 2종만)였다가 SOL·TIME 추가하며 "Active ETF Tracker"로 리브랜딩,
  이후 TIGER 추가 → **SOL 코리아메가테크액티브를 빼고 RISE 코리아전략산업액티브로 교체**(최근 세션).
- 라이브: `https://zerobeom.github.io/active-etf-tracker/` (저장소명 `zerobeom/active-etf-tracker`)
- 배포 방식: 사용자가 GitHub 웹에서 파일을 직접 교체/업로드 후, 필요시 Actions 수동 실행.

## 추적 ETF 7종
| slug | provider | issuer | 이름 | 티커 | 상장일 | region | 비고 |
|---|---|---|---|---|---|---|---|
| `us-nasdaq` | samsung | 삼성액티브자산운용 | KoAct 미국나스닥성장기업액티브 | 0015B0 | 2025-02-25 | US | 나스닥종합·나스닥100 벤치마크 |
| `sol-nexttech` | sol | 신한자산운용 | SOL 미국넥스트테크TOP10액티브 | 0118S0 | 2025-10-28 | US | 나스닥종합·나스닥100 |
| `time-nasdaq100` | time | 타임폴리오자산운용 | TIME 미국나스닥100액티브 | 426030 | 2022-05-11 | US | 나스닥종합·나스닥100 · **관리자만 보임**(`index.html`의 `init()`에서 slug 필터링) |
| `time-sp500` | time | 타임폴리오자산운용 | TIME 미국S&P500액티브 | 426020 | 2022-05-11 | US | S&P500 |
| `tiger-koreatech` | funetf | 미래에셋자산운용 | TIGER 코리아테크액티브 | 471780 | 2023-11-28 | KR | 코스피 벤치마크 |
| `rise-strategy` | funetf | KB자산운용 | RISE 코리아전략산업액티브 | 0151P0 | 2026-01-20 | KR | 코스피 벤치마크. **SOL 코리아메가테크액티브 교체분** |
| `kr-valueup` | samsung | 삼성액티브자산운용 | KoAct 코리아밸류업액티브 | 495230 | 2024-11-04 | KR | 코스피 벤치마크 |

`scripts/fetch_holdings.py` 상단 `ETFS` 리스트에 항목을 추가하면 얼마든지 더 늘어남. **KR 지역 안에서
화면에 보이는 순서는 `ETFS` 리스트에 정의된 순서를 그대로 따라가므로**(`buildEtfOptionsHTML`이 그냥
순서대로 밀어넣음), 사용자가 "국내는 TIGER→RISE→KOACT 순서로 보이게 해달라"고 해서 리스트 자체를
그 순서로 정렬해둔 상태 — 나중에 국내 ETF를 더 추가/순서 변경할 때도 이 리스트 순서를 그대로 바꾸면 됨.

`provider`는 "어느 회사 ETF냐"가 아니라 "데이터를 어떻게 가져오느냐"의 구분자임 — 특히 `funetf`는
TIGER·RISE가 같은 funetf.co.kr API를 공유해서 쓰는 거라 provider만으로는 운용사를 알 수 없음.
그래서 각 ETF 항목에 **`issuer`(운용사명, 화면 하단 "데이터 출처" 문구에 그대로 씀) 필드를 따로 둠**.
새 ETF 추가할 때 `issuer` 빠뜨리지 말 것.

## 데이터 소스 4종(provider 기준)
### 1. 삼성액티브(`provider:"samsung"`)
`https://www.samsungactive.co.kr/excel_pdf.do?fId={펀드ID}&gijunYMD=YYYYMMDD` → 구형 `.xls`(BIFF).
ISIN을 키로 씀. 날짜 파라미터 실제로 작동(과거 조회 됨). 오늘자 없으면 `LOOKBACK_DAYS=7`만큼 하루씩
후퇴 탐색.

### 2. 신한 SOL(`provider:"sol"`)
```
https://www.soletf.com/api/fund/pdfList?fund_cd={내부ID}&work_dt=YYYYMMDD
```
공식 JSON API, `work_dt`가 실제로 그 날짜 데이터를 줌(과거 조회 확인됨). 응답 필드: `SEC_NM`(종목명)·
`QTY`(수량)·`PRICE`(평가금액 원화 총액)·`WT_DISP`(비중, `"15.45%"`)·`STOCK_CODE`.
- 한국 종목: `STOCK_CODE`가 이미 KRX 6자리 코드 → 그대로 티커. **지금 추적 중인 SOL은 미국(넥스트테크)
  1개뿐이라 이 분기는 당장 안 쓰임** — 코드엔 남겨둠(한국 SOL ETF가 다시 추가되면 바로 작동).
- 미국(넥스트테크): `STOCK_CODE`가 ISIN이라 실제 티커는 이름 매칭 필요 — `SOL_US_TICKERS`(스크립트
  상단 수동 매핑) → KoAct 나스닥 최신 스냅샷 참조 → 나스닥 심볼 디렉터리 → SEC 티커 목록, 순서로
  시도. 새 종목 들어오면 로그의 `[ticker] 매핑 안됨` 보고 `SOL_US_TICKERS`에 추가.
- 요청 자체에 재시도(2s/6s/18s 백오프) 있음(`download_sol`).
- 매일 자동 갱신 경로엔 `fetch_latest_available_sol()` 후퇴탐색(최대 7일), **백필 모드에선 꺼짐**
  (`allow_lookback=False`).

### 3. 타임폴리오 TIME(`provider:"time"`)
`https://timeetf.co.kr/pdf_excel.php?idx={내부ID}&cate=&pdfDate=YYYY-MM-DD` → 진짜 최신 `.xlsx`
(openpyxl로 읽음). `pdfDate` 실제로 작동(과거 조회 됨). 종목코드가 이미 `SNDK US EQUITY`식이라 티커
매핑 불필요. 선물종목(나스닥100 E-미니 등) 섞여 있는데 그냥 일반 보유종목처럼 처리(yfinance 가격
조회만 실패, 무해).

### 4. funetf.co.kr 공개 API(`provider:"funetf"`) — TIGER·RISE 공용
```
https://www.funetf.co.kr/api/public/product/view/etfpdf?itemId={펀드ISIN}&etfPdfYmd=YYYYMMDD
```
- **배경**: 처음 TIGER 추가할 때 미래에셋 공식 ajax(`investments.miraeasset.com/.../prdct-item-list.ajax`)
  를 썼는데 **GitHub Actions에서만 계속 403**(로컬/브라우저 헤더를 갖춰도, 세션 쿠키를 받아도, 심지어
  헤드리스 브라우저(Playwright)로도 막힘 — requests 자체를 IP 대역 기준으로 차단하는 걸로 추정)이 나서,
  사용자가 funetf.co.kr API를 찾아와서 이걸로 전면 교체함. 헤더 하나 없이 바로 됨.
- `itemId`가 바로 펀드 ISIN이라 **운용사 상관없이 어느 액티브 ETF든 이 API 하나로 다 됨** — RISE
  코리아전략산업액티브도 이렇게 추가함(TIGER 전용 함수명 `download_tiger`/`normalize_tiger`를 그대로
  재사용 중, 이름만 TIGER고 실제로는 funetf 공용 함수임).
- 응답 필드: `citmNm`(종목명)·`ticker`(KRX 6자리, 현금행은 `null`)·`grpItmNo`(ISIN)·`icuStkc`(수량)·
  `evP`(비중, 이미 숫자)·`evAmt`(평가금액)·`curp`(현재가, 이미 숫자). 현금행은 `grpItmNo`가 `KRD`로
  시작하거나 종목명에 "현금" 포함.
- ⚠️ **`etfPdfYmd`로 과거 조회가 실제로 되는지 미검증** — 응답 자체에 날짜 필드가 없어서(samsung/time
  처럼 응답에 기준일이 안 찍혀 나옴) 요청한 날짜를 그대로 기준일로 신뢰하는 구조. 백필 한 번 돌려서
  날짜별로 실제 값이 바뀌는지 확인 필요(다음 섹션 참고).

## 백필(과거 기간 채우기)
- `.github/workflows/backfill.yml`의 `providers` 입력은 **자유 텍스트가 아니라 드롭다운(choice)**으로
  바꿔놨음(사용자가 어떤 provider/slug가 있는지 헷갈려해서) — "전체" / provider 단위(`samsung`,
  `sol`, `time`, `funetf`) / ETF 7종 각각을 목록에서 고르는 방식. 단, **GitHub Actions 드롭다운은
  한 번에 하나만 선택 가능**이라 "sol이랑 time만 같이" 같은 조합은 못 고름 — 필요하면 같은 기간으로
  두 번 나눠 돌리면 됨. 드롭다운 값은 `"sol (SOL 1종)"`처럼 설명이 붙어 있어서, 워크플로 내부에서
  `${RAW%% *}`로 첫 단어만 잘라 실제 `--only=` 값으로 씀(`전체`는 빈 값 취급).
- 로컬/CLI: `python scripts/fetch_holdings.py 20220501:20260708 --only=sol`
- 벤치마크(`perf.json`)는 백필 중엔 계산 안 하고 **맨 끝에 ETF당 한 번씩만** 계산.
- 가장 이른 상장일은 TIME 2종(2022-05-11). 전체 백필하면 수천 회 요청, 2~4시간+ 걸릴 수 있음(Actions
  1회 6시간 제한 — 중간에 멎어도 이미 처리된 건 저장되니 남은 구간만 좁혀서 재실행하면 됨).

## 사이트 기능 (`index.html`)

### 로그인 게이트
- 맨 아래 `AUTH_MODE` 변수로 3가지: `"off"` / `"password"`(현재 사용 중) / `"firebase"`.
- 지금 비밀번호는 **`carpediem`**(해시만 `AUTH_HASH`에 저장). 바꾸려면 새 비밀번호의 SHA-256을
  계산해서 `AUTH_HASH` 교체.
- Firebase 모드용 `firebaseConfig`는 아직 placeholder — 필요해지면 Firebase 콘솔에서 프로젝트
  생성부터 해야 함.
- 이 로그인은 **화면만 막는 거지 `data/*.json` 파일 URL을 직접 알면 데이터 자체는 그대로 노출됨**
  (정적 호스팅이라 파일 단위 접근 차단 불가, 사용자도 인지 중).
- 저장소 Private 전환은 보류(무료 계정은 Private에서 GitHub Pages 자체가 안 켜짐) — Public 유지 +
  비밀번호 게이트 조합으로 정리.

### 관리자 모드
- 주소에 `?admin=1` 붙이면 `localStorage`에 저장돼 계속 관리자로 인식(`?admin=0`으로 해제).
- 관리자만: 🔄 데이터 업데이트 버튼, 수량/비중 설명 문구, 벤치마크 캡션 문구, **TIME
  나스닥100액티브 ETF 자체**(일반 방문자 목록에서 빠짐).

### 하단 "데이터 출처" 문구
- 선택한 ETF가 바뀔 때마다(`setTitle()`) `etf.issuer` 값을 그대로 가져다 "데이터 출처:
  {issuer} · 매 영업일 자동 갱신." 형태로 표시. 회사명만 나오게 짧게 다듬어둔 상태(예전엔
  "삼성액티브자산운용 투자종목정보(PDF)"처럼 길었는데 지금은 "삼성액티브자산운용"까지만).
  `data/etfs.json`에 `issuer` 필드가 있어야 하니, 스크립트 자동생성 로직(`main()`의 `etfs.json` 쓰는
  부분) 건드릴 땐 이 필드 빠뜨리지 말 것.

### "포트폴리오 변동 내역" 현황판 + 카드
- 5개 카테고리: **편입(▶)·매수(▲)·유지(⏸)·매도(▼)·편출(■)**.
- 편입/편출은 더 진하게(`--in-strong`/`--out-strong`), 매수/매도는 일반(`--in`/`--out`), 유지는
  무채색. 큰 숫자(v) 자체는 색 안 넣음.
- **카드 제목(`.clist h3`)의 아이콘도 상단 통계 카드와 똑같이 옅은 배경 알약(pill) 스타일 적용됨**
  (`clist()` 함수가 아이콘을 `<span class="icn">`으로 감싸고, `.clist h3 .icn`에 카테고리별 배경색)
  — 예전엔 상단 통계 카드에만 있고 이 카드 제목엔 빠져 있던 버그를 고친 것.
- 순서: 편입 → 매수 → 유지 → 매도 → 편출 — 실제 코드(`renderBand`/`renderChangeLists`)로 재확인할 것.
- 각 통계 박스 클릭 → 해당 카드로 스크롤(`data-target`). 카드 안 각 줄 클릭 → 아래 표로 스크롤 +
  상세 차트 열림(`onChangeListClick` → `openDetailFor`). 편출 종목은 표에 행이 없어서 표 맨 위에
  별도로 열림.
- 열 순서: 비중 → 수량 → 변화. 다운로드 버튼(⬇) — 진짜 엑셀(.xlsx, SheetJS), 시트 6개.

### 전체 포트폴리오 표
- ETF 셀렉터가 **지역별(`<optgroup>` 미국/국내)로 묶여서** 나옴(`buildEtfOptionsHTML`,
  `etfs.json`의 `region` 필드 기준). **그룹 안에서의 순서는 `ETFS` 리스트 작성 순서를 그대로 따름**
  (정렬 안 함) — 국내는 TIGER→RISE→KOACT 순으로 보이게 하려고 Python `ETFS` 리스트 자체를 그
  순서로 맞춰둔 상태.
- 헤더 밑에 "상장일 YYYY.MM.DD" 표시(`listDate`, `etfs.json`의 `start` 필드).
- 비중 막대 색: 편입은 진한 단색, 매수/매도는 옅은 파스텔 그라데이션.
- 종목 클릭 → 상세 콤보 차트(주별/월별/연도별 토글).

### 상세 콤보 차트 (비중·보유수량·주식수 변화율)
- 열면 자동으로 스크롤 맨 오른쪽(최신 날짜)부터 보임.
- 변화율(오른쪽) 축: 편입(0%)·편출(-100%) 고정값은 축 크기 계산에서 제외, 양수/음수 비대칭 독립
  계산, **진짜 데이터 값은 절대 안 자름**(극단값 clamp 없음 — "테슬라 800% 스파이크" 요청으로 확정),
  15% 여유 + `niceRateCeil()`로 5/10 단위 눈금.
- 비중(왼쪽 축)·보유수량은 기존 `niceCeil` 그대로.

### 벤치마크 수익률 비교
- FinanceDataReader로 상장일부터 실시간 계산, 월별/연도별 토글. SOL/TIME/TIGER/RISE 전부 KRX 정식
  상장 코드라 FDR로 바로 됨(별도 시드 파일 불필요).
- 하단 캡션 문구 삭제함. 초과수익 설명 문구는 관리자만 보임.

## 파일 구조
```
active-etf-tracker/
├─ index.html                        # 사이트 전체
├─ scripts/fetch_holdings.py         # 수집 스크립트 (4개 provider 다 여기: samsung/sol/time/funetf)
├─ .github/workflows/update.yml      # 매일 자동 (06:00·18:00 KST)
├─ .github/workflows/backfill.yml    # 수동 백필 (providers 드롭다운 선택)
├─ requirements.txt                  # requests, pandas, xlrd, openpyxl, lxml,
│                                     # finance-datareader, yfinance
└─ data/
   ├─ etfs.json                      # {slug,name,ticker,fid,start,region,provider,issuer} — 스크립트가 자동 생성
   └─ {slug}/latest.json, dates.json, perf.json, snapshots/YYYY-MM-DD.json
```

## 작업 규칙 (계속 지켜온 것들)
- **컨테이너 외부망 차단** → 실제 API/사이트가 진짜 작동하는지는 못 봄(단, `web_fetch`/`web_search`
  도구로 공개 API 엔드포인트 자체는 확인 가능했음 — funetf API 응답 형태는 이렇게 확인함). 대신:
  - JS는 `node --check` + 관련 함수만 잘라내서 실제 데이터로 실행 테스트까지 매번 했음.
  - 파이썬은 `py_compile` + 실제 함수(`normalize_sol`, `normalize_tiger` 등)에 진짜 API 응답 형태의
    가짜 데이터 넣어서 단위 테스트.
- **모든 파일은 "통째로 교체"로 안내** — 사용자가 GitHub 초보라 부분 수정 어려워함.
- 수정할 때마다 최종본을 `/mnt/user-data/outputs/`에 복사 → 파일로 전달.
- 사용자가 "전체 모든 파일이 포함된 zip으로 달라"고 요청한 적 있음(오랜만에 재개할 때) — 그럴 땐
  프로젝트 폴더 구조 그대로 zip으로 묶어서 전달.
- 화면 요청은 스크린샷으로 자주 옴 — 캡처 보고 정확히 어느 요소인지(band vs card vs table) 짚어서
  수정. "이 색 빼줘 → 다시 넣어줘" 왔다갔다 했으니, 되돌리라고 하면 정확히 어느 시점인지 확인하며
  진행.
- 로그 확인 요청할 땐 Actions 실행 펼쳐서 `Ctrl+F`로 provider별 키워드 검색해서 캡처 보내달라고
  안내하는 패턴 자주 씀. GitHub Actions에서만 재현되는 문제(403 등)는 로컬 web_fetch로는 원인
  진단이 안 될 수 있다는 점 유의(미래에셋 ajax 403 사례 — Anthropic 인프라에선 200인데 Actions
  에서만 403이었음, 결국 API 자체를 교체해서 해결).

## 열린 항목 / 다음에 확인하면 좋은 것
- **funetf API(`provider:"funetf"`)의 `etfPdfYmd` 과거 조회 지원 여부 아직 미검증** — TIGER·RISE
  둘 다 백필 돌려서 날짜별로 실제 값이 바뀌는지 확인 필요(현재는 요청 날짜를 그대로 믿고 저장하는
  구조라, 만약 서버가 항상 최신값만 주는 거라면 과거 날짜 전부에 최신 스냅샷이 중복 저장되는
  문제가 생길 수 있음).
- SOL lookback 안전장치(`fetch_latest_available_sol`) — 실제로 하루 누락이 줄어드는지 지켜볼 것.
- TIME `pdfDate` 파라미터·SOL `work_dt` 파라미터는 과거 조회 되는 건 확인했지만, 아주 오래된 날짜
  (TIME 2022-05-11 상장일 근처)까지 서버가 보관하는지는 미검증 — 전체 백필 한 번 돌려서 확인 필요.
- Firebase 로그인 모드 — 프로젝트 자체가 아직 안 만들어짐.
- SOL_US_TICKERS 수동 매핑은 리밸런싱 때마다 로그 보고 계속 추가해줘야 하는 구조.
- 정보 제공용/투자 권유 아니라는 문구, 수량·비중 설명 문구 등 일부는 삭제하거나 관리자 전용으로
  뺐음 — 나중에 공개 여부 다시 확인해볼 것.
