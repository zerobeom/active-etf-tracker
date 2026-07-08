# Active ETF Tracker

여러 운용사의 **액티브 ETF 구성종목**을 매 영업일 자동으로 받아와,
**전일 대비 편입·편출·추가매수·일부매도**를 웹페이지로 보여줍니다. 비중은 주가 등락만으로도
변하지만 **수량(주식 수)은 매니저가 실제로 매매해야만 바뀌므로**, 두 지표를 함께 표시합니다.
운용사 팩트시트(상위 종목만)와 달리 이 데이터는 **전 종목**을 담고 있어, 전체 구성 변화를
빠짐없이 추적합니다. 종목을 클릭하면 **비중·보유수량·주식수 변화율** 추이를 주별/월별/연도별로
볼 수 있고, 벤치마크 지수 대비 누적수익률도 함께 보여줍니다.

한 화면에서 **여러 ETF를 골라** 볼 수 있고, 한 번 세팅하면 손대지 않아도 매일 갱신됩니다.

라이브: `https://<아이디>.github.io/active-etf-tracker/`

## 현재 추적 대상 (7개)

| ETF | 티커 | 운용사 | 상장일 | 벤치마크 | 공개 여부 |
|---|---|---|---|---|---|
| KoAct 미국나스닥성장기업액티브 | `0015B0` | 삼성액티브 | 2025-02-25 | 나스닥종합·나스닥100 | 전체 공개 |
| KoAct 코리아밸류업액티브 | `495230` | 삼성액티브 | 2024-11-04 | 코스피 | 전체 공개 |
| SOL 미국넥스트테크TOP10액티브 | `0118S0` | 신한자산운용 | 2025-10-28 | 나스닥종합·나스닥100 | 전체 공개 |
| SOL 코리아메가테크액티브 | `444200` | 신한자산운용 | 2022-10-18 | 코스피 | 전체 공개 |
| TIME 미국나스닥100액티브 | `426030` | 타임폴리오 | 2022-05-11 | 나스닥종합·나스닥100 | **관리자만** |
| TIME 미국S&P500액티브 | `426020` | 타임폴리오 | 2022-05-11 | S&P500 | 전체 공개 |

`scripts/fetch_holdings.py` 상단 `ETFS` 목록에 항목을 추가하면 얼마든지 더 늘릴 수 있습니다
(아래 "새 ETF/운용사 추가하기" 참고).

```
active-etf-tracker/
├─ index.html                        # 보여주는 사이트 (GitHub Pages)
├─ scripts/fetch_holdings.py         # 다운로드 + 파싱 + 변동/수익률 계산 (모든 ETF, 모든 운용사)
├─ .github/workflows/update.yml      # 매 영업일 자동 실행
├─ .github/workflows/backfill.yml    # 과거 기간 일괄 채우기(수동 실행)
├─ requirements.txt
└─ data/                             # 자동 생성/갱신되는 데이터(JSON) — 폴더 직접 안 만들어도 됨
   ├─ etfs.json                      # 사이트가 읽는 ETF 목록(스크립트가 자동 생성)
   └─ {slug}/                        # ETF별 폴더 (위 표의 ETF마다 하나씩)
      ├─ latest.json                 # 최신 스냅샷 + changes + updated_at(KST)
      ├─ dates.json                  # 보유 날짜 목록
      ├─ perf.json                   # 벤치마크 대비 누적수익률(월별, FinanceDataReader)
      └─ snapshots/YYYY-MM-DD.json
```

## 운용사별 데이터 소스 (3종) — **셋 다 과거 날짜 조회(백필) 됩니다**

같은 파이썬 스크립트 안에서 운용사별로 `provider` 값에 따라 서로 다른 방식으로 데이터를 받아옵니다.
사이트(`index.html`)는 이 차이를 몰라도 되게, 세 소스 다 **같은 JSON 모양**(isin/ticker/name/weight/
shares/amount/price/is_cash/key)으로 변환해서 저장합니다.

### 1. 삼성액티브자산운용 (`provider: "samsung"`) — KoAct
`https://www.samsungactive.co.kr/excel_pdf.do?fId={펀드ID}&gijunYMD=YYYYMMDD` → 구형 `.xls`(BIFF).
컬럼: 종목명·**ISIN**·종목코드·수량·비중(%)·평가금액·현재가(원). ISIN을 키로 사용.

### 2. 신한자산운용 SOL (`provider: "sol"`)
`https://www.soletf.com/api/fund/pdfList?fund_cd={내부ID}&work_dt=YYYYMMDD` — **공식 JSON API**
(HTML 페이지 스크래핑이 아님). `work_dt` 파라미터가 실제로 그 날짜 데이터를 돌려줘서 과거 조회가
됩니다. 응답 필드: `SEC_NM`(종목명)·`QTY`(수량)·`PRICE`(평가금액, 필드명과 달리 원 단위 총액)·
`WT_DISP`(비중, `"15.45%"` 형태)·`STOCK_CODE`.
- 한국 종목(코리아메가테크): `STOCK_CODE`가 이미 KRX 6자리 코드라 그대로 티커로 씀.
- 미국 종목(넥스트테크): `STOCK_CODE`가 ISIN이라(티커 아님), 실제 거래 티커는 이름 매칭으로 찾음 —
  1) `SOL_US_TICKERS`(스크립트 상단) 수동 매핑 → 2) KoAct 미국나스닥 최신 스냅샷 참조 →
  3) 나스닥거래소 심볼 디렉터리(무료, 종종 403) → 4) SEC 공식 티커 목록(무료, 종종 403) →
  5) 그래도 없으면 로그에 `[ticker] 매핑 안됨`만 남기고 티커 빈칸. 새 종목 들어오면 이 로그 보고
  `SOL_US_TICKERS`에 한 줄 추가하면 됨.

### 3. 타임폴리오자산운용 TIME (`provider: "time"`)
`https://timeetf.co.kr/pdf_excel.php?idx={내부ID}&cate=&pdfDate=YYYY-MM-DD` → 진짜 최신 `.xlsx`.
`pdfDate` 파라미터가 실제로 작동해 과거 조회가 됩니다. 종목코드가 이미 `SNDK US EQUITY`식으로
와서 티커 매핑이 따로 필요 없음. 선물종목(예: 나스닥100 E-미니)이 섞여 있을 수 있는데 일반
보유종목처럼 처리됨(yfinance 가격 조회는 실패하지만 무해).

---

## 1. 저장소 만들기

GitHub에서 새 저장소 생성(예: `active-etf-tracker`, **Public** 권장 — 무료 계정은 Public이어야
GitHub Pages가 켜집니다) 후 이 폴더를 그대로 push:

```bash
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/<아이디>/active-etf-tracker.git
git push -u origin main
```

> ⚠️ 저장소를 Private으로 바꾸면 무료 계정 기준 GitHub Pages 배포가 아예 안 됩니다(Pro 이상
> 필요). 소스 코드를 숨기고 싶은 게 아니라 "사이트 자체를 아무나 못 보게" 하고 싶은 거라면,
> Private 전환 대신 아래 "로그인 게이트"를 쓰세요.

## 2. 자동 실행(Actions) 켜기

1. **Settings → Actions → General → Workflow permissions** 에서 **Read and write permissions** 선택 후 저장.
2. **Actions** 탭 → *Update KoAct holdings* → **Run workflow** 를 한 번 눌러 즉시 실행.
   → `data/`에 그날 구성종목이 생성됩니다(폴더가 없어도 스크립트가 자동으로 만듭니다).
3. 이후 매 영업일 06:00·18:00(KST) 자동 실행. (시간은 `update.yml`의 `cron`에서 변경, GitHub
   스케줄은 "best effort"라 몇 분~몇 시간 지연될 수 있음)

### 과거 기간 한 번에 채우기 (백필)

**Actions → Backfill KoAct holdings (past dates) → Run workflow**에 시작일·종료일을 넣으면,
그 사이 모든 영업일 × 모든 ETF(각자 상장일 이후분만)를 자동으로 채웁니다. 세 운용사 다 실제
과거 날짜 조회가 되므로 정상 동작합니다. 가장 이른 상장일(2022-05-11)부터 오늘까지 전부 채우면
영업일 기준 약 1,000일 × ETF 7개 = 수천 회 요청이라 **몇 시간 걸릴 수 있습니다**(GitHub Actions
1회 실행 6시간 제한 있음 — 도중에 멈춰도 그때까지 처리된 데이터는 남으니, 남은 구간만 좁혀서
다시 돌리면 이어서 채워짐). 벤치마크 수익률(`perf.json`)은 백필 중엔 계산을 건너뛰고 맨 마지막에
ETF당 한 번씩만 계산해서 시간을 크게 아낍니다.

## 3. 사이트 공개(Pages)

1. **Settings → Pages**.
2. **Source: Deploy from a branch**, **Branch: `main` / `(root)`** 선택 후 저장.
3. 1~2분 뒤 `https://<아이디>.github.io/active-etf-tracker/` 에서 열립니다.

## 4. 로그인 게이트 (선택)

`index.html` 맨 아래 `AUTH_MODE` 값으로 세 가지 중 고릅니다.
- `"off"`: 아무나 바로 접속 가능.
- `"password"`(기본): 공유 비밀번호 하나로 잠금. `AUTH_HASH`에 비밀번호의 SHA-256 해시값만
  저장되고 원문은 코드에 안 남음. 비밀번호를 바꾸려면 새 해시값을 계산해서 `AUTH_HASH`만 교체.
- `"firebase"`: Firebase Authentication(이메일/비밀번호) 계정별 로그인. 쓰려면 Firebase 콘솔에서
  프로젝트를 만들고 `firebaseConfig` 자리(스크립트 상단)를 본인 프로젝트 값으로 채워야 함.

**어느 모드든 이건 로그인 "화면"만 막는 거지, `data/*.json` URL을 직접 알면 로그인 없이도 그
파일 자체는 보입니다**(정적 호스팅이라 파일 단위 접근 차단이 불가능). 진짜로 데이터까지 잠그려면
Firestore 등으로 구조를 옮겨야 함(훨씬 큰 작업).

## 5. 특정 ETF만 관리자에게만 보이게 하기

`index.html`의 `init()` 함수 안, `list.filter(e=>e.slug!=="...")` 부분에 슬러그를 추가하면 그
ETF는 일반 방문자 목록에서 빠지고, 관리자(주소에 `?admin=1` 붙여서 한 번 접속한 브라우저)에게만
보입니다. 지금은 `time-nasdaq100`이 이렇게 설정되어 있습니다.

---

## 로컬에서 직접 돌려보기

```bash
pip install -r requirements.txt
python scripts/fetch_holdings.py            # 오늘(KST) 기준, 모든 ETF
python scripts/fetch_holdings.py 20260626   # 특정일 강제 수집 (세 운용사 다 실제로 그 날짜로 됨)
python scripts/fetch_holdings.py 20220501:20260708   # 기간 채우기(영업일만)
python scripts/fetch_holdings.py --debug    # 파싱 전 원본 표/응답 확인
python -m http.server 8000   →   http://localhost:8000   # 사이트 미리보기
```

## 새 ETF/운용사 추가하기

`scripts/fetch_holdings.py` 상단 `ETFS` 목록에 한 줄(딕셔너리) 추가:

```python
{"slug": "새폴더이름", "provider": "samsung|sol|time", "fid": "펀드ID/내부ID", "ticker": "거래소코드",
 "name": "표시할 이름", "start": "YYYY-MM-DD",
 "usd_price": True,   # 미국 종목이라 현재가를 yfinance로 따로 받아야 하면
 "benchmarks": [{"k": "b1", "label": "비교지수 이름", "sym": ["FDR심볼", "대체심볼"]}]},
```

이미 있는 3개 운용사(삼성/SOL/TIME) 중 하나면 코드 수정 없이 이 줄만 추가하면 됩니다.
**새로운 운용사**라면 `download_*`/`normalize_*` 함수 한 쌍을 새로 만들고 `process_etf()`의
`if/elif provider ==` 분기에 추가해야 합니다(기존 3개 참고).

## 커스터마이즈

| 바꾸고 싶은 것 | 위치 |
|---|---|
| 추적 ETF 추가/변경 | `scripts/fetch_holdings.py` 상단 `ETFS` 목록 (위 항목 참고) |
| SOL 미국 종목 수동 티커 매핑 | 같은 파일의 `SOL_US_TICKERS` |
| 파일 없을 때 후퇴 일수(samsung) | 같은 파일의 `LOOKBACK_DAYS` (기본 7일) |
| 자동 실행 시각 | `.github/workflows/update.yml`의 `cron` (UTC 기준) |
| 로그인 게이트 모드 | `index.html` 맨 아래 `AUTH_MODE` / `AUTH_HASH` |
| 특정 ETF 관리자 전용 처리 | `index.html`의 `init()` 안 `list.filter(...)` |
| 색/디자인 | `index.html` 상단 `:root` CSS 변수 |

---

## 알아둘 점

- 현금성 행(설정현금액·원화현금·현금성자산·100%현금설정액 등)은 `is_cash`로 표시되고
  편입/편출/비중 집계에서 제외하며, 사이트 표 하단에 흐리게 보입니다.
- 비중 값이 소수(0.07)로 들어오든 `7.00%`로 들어오든 자동으로 백분율(합 100%)로 정규화합니다
  (samsung 경로만 해당; sol/time은 원래부터 %로 옴).
- `.xls`(구형, samsung) 파싱엔 `xlrd`, `.xlsx`(신형, time) 파싱엔 `openpyxl`이 필요합니다
  (둘 다 `requirements.txt`에 포함 — 하나라도 빠지면 해당 provider만 조용히 실패하니, 처음
  추가할 때 Actions 로그에서 `[ok]`가 뜨는지 꼭 확인).
- 벤치마크 수익률은 전부 FinanceDataReader로 계산(월별 마지막 거래일 종가 기준). 백필 중엔
  ETF당 맨 마지막에 한 번만 계산(매 날짜마다 전체 기간을 다시 계산하면 극도로 느려서).
- 상세 차트의 "변화율" 축은 편입(0%)·편출(-100%) 같은 규칙상 고정값은 축 크기 계산에서 빼고
  실제 변동폭 기준으로 잡습니다. 그 고정값들은 축 가장자리로 clamp해서 그리되, 툴팁엔 정확한
  값이 그대로 표시됩니다.
- 휴장일·미공시일에는(samsung만) 자동으로 직전 영업일 파일까지 후퇴해 찾고, 그래도 없으면
  건너뜁니다. sol/time은 해당 없음(항상 요청한 날짜 결과 그대로 사용, 없으면 스킵).
- 컨테이너/CI 환경에 따라 SEC·나스닥 등 외부 무료 API가 403으로 막힐 수 있습니다 — 실패해도
  조용히 다음 우선순위로 넘어가게 되어 있어 전체 수집은 멈추지 않습니다.

데이터 출처: 삼성액티브자산운용 · 신한자산운용(SOL) · 타임폴리오자산운용(TIME).
정보 제공용이며 투자 권유가 아닙니다.
