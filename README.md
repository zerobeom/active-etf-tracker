# Active ETF Tracker

여러 운용사의 **액티브 ETF 구성종목**을 매 영업일 자동으로 받아와,
**전일 대비 편입·편출·추가매수·일부매도**를 웹페이지로 보여줍니다. 비중은 주가 등락만으로도
변하지만 **수량(주식 수)은 매니저가 실제로 매매해야만 바뀌므로**, 두 지표를 함께 표시합니다.
운용사 팩트시트(상위 종목만)와 달리 이 데이터는 **전 종목**을 담고 있어, 전체 구성 변화를
빠짐없이 추적합니다. 종목을 클릭하면 **비중·보유수량·주식수 변화율** 추이를 주별/월별/연도별로
볼 수 있고, 벤치마크 지수 대비 누적수익률도 함께 보여줍니다.

한 화면에서 **여러 ETF를 골라** 볼 수 있고, 한 번 세팅하면 손대지 않아도 매일 갱신됩니다.

라이브: `https://<아이디>.github.io/active-etf-tracker/`

## 현재 추적 대상 (5개)

| ETF | 티커 | 운용사 | 상장일 | 벤치마크 |
|---|---|---|---|---|
| KoAct 미국나스닥성장기업액티브 | `0015B0` | 삼성액티브 | 2025-02-25 | 나스닥종합·나스닥100 |
| KoAct 코리아밸류업액티브 | `495230` | 삼성액티브 | 2024-11-04 | 코스피 |
| SOL 미국넥스트테크TOP10액티브 | `0118S0` | 신한자산운용 | 2025-10-28 | 나스닥종합·나스닥100 |
| SOL 코리아메가테크액티브 | `444200` | 신한자산운용 | 2022-10-18 | 코스피 |
| TIME 미국나스닥100액티브 | `426030` | 타임폴리오 | 2022-05-11 | 나스닥종합·나스닥100 |

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
   └─ {slug}/                        # ETF별 폴더 (위 표의 ETF마다 하나씩, 예: us-nasdaq, sol-megatech, time-nasdaq100)
      ├─ latest.json                 # 최신 스냅샷 + changes + updated_at(KST)
      ├─ dates.json                  # 보유 날짜 목록
      ├─ perf.json                   # 벤치마크 대비 누적수익률(월별, FinanceDataReader)
      └─ snapshots/YYYY-MM-DD.json
```

## 운용사별 데이터 소스 (3종)

같은 파이썬 스크립트 안에서 운용사별로 `provider` 값에 따라 서로 다른 방식으로 데이터를 받아옵니다.
사이트(`index.html`)는 이 차이를 몰라도 되게, 세 소스 다 **같은 JSON 모양**(isin/ticker/name/weight/
shares/amount/price/is_cash/key)으로 변환해서 저장합니다.

### 1. 삼성액티브자산운용 (`provider: "samsung"`) — KoAct
`https://www.samsungactive.co.kr/excel_pdf.do?fId={펀드ID}&gijunYMD=YYYYMMDD` → 구형 `.xls`(BIFF).
컬럼: 종목명·**ISIN**·종목코드·수량·비중(%)·평가금액·현재가(원). ISIN을 키로 사용.
**날짜 파라미터가 실제로 작동해서, 과거 기간 백필이 됩니다.**

### 2. 신한자산운용 SOL (`provider: "sol"`)
`https://www.soletf.com/ko/fund/etf/{내부ID}?tabIndex=3` 웹페이지의 "구성종목" 표를 직접 파싱.
티커/ISIN이 없고 **종목명만 있어서**, 아래 순서로 티커를 매핑합니다:
1. `SOL_US_TICKERS`(스크립트 상단) 수동 매핑
2. KoAct 미국나스닥 최신 스냅샷에서 이름 매칭
3. 나스닥거래소 심볼 디렉터리(무료, 종종 403으로 막힘)
4. SEC 공식 티커 목록(무료, 종종 403으로 막힘)
5. 그래도 없으면 로그에 `[ticker] 매핑 안됨`만 남기고 티커 빈칸

한국 종목(코리아메가테크)은 FinanceDataReader의 KRX 전종목 목록으로 이름→코드를 그때그때 조회해서
문제없음.
**⚠️ 날짜를 파라미터로 넘겨도 항상 "오늘" 데이터만 줘서, 과거 기간 백필이 안 됩니다.** 매일 자동
수집만 정상 동작(오늘부터 쌓임).

### 3. 타임폴리오자산운용 TIME (`provider: "time"`)
`https://timeetf.co.kr/pdf_excel.php?idx={내부ID}&cate=&pdfDate=YYYY-MM-DD` → 진짜 최신 `.xlsx`.
컬럼이 삼성이랑 비슷해서(종목코드가 `SNDK US EQUITY`식으로 이미 포함) 티커 매핑이 따로 필요 없음.
**`pdfDate` 파라미터가 실제로 작동해서, 과거 기간 백필이 됩니다.**

---

## 1. 저장소 만들기

GitHub에서 새 저장소 생성(예: `active-etf-tracker`, **Public** 권장) 후 이 폴더를 그대로 push:

```bash
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/<아이디>/active-etf-tracker.git
git push -u origin main
```

## 2. 자동 실행(Actions) 켜기

1. **Settings → Actions → General → Workflow permissions** 에서 **Read and write permissions** 선택 후 저장.
2. **Actions** 탭 → *Update KoAct holdings* → **Run workflow** 를 한 번 눌러 즉시 실행.
   → `data/`에 그날 구성종목이 생성됩니다(폴더가 없어도 스크립트가 자동으로 만듭니다).
3. 이후 매 영업일 06:00·18:00(KST) 자동 실행. (시간은 `update.yml`의 `cron`에서 변경, GitHub
   스케줄은 "best effort"라 몇 분~몇 시간 지연될 수 있음)

## 3. 사이트 공개(Pages)

1. **Settings → Pages**.
2. **Source: Deploy from a branch**, **Branch: `main` / `(root)`** 선택 후 저장.
3. 1~2분 뒤 `https://<아이디>.github.io/active-etf-tracker/` 에서 열립니다.

## 4. 로그인 게이트 (선택)

`index.html` 맨 아래 `AUTH_ENABLED` 값으로 켜고 끕니다.
- `false`(기본): 아무나 바로 접속 가능.
- `true`: Firebase Authentication(이메일/비밀번호) 로그인 필요. 켜려면 Firebase 콘솔에서 프로젝트를
  만들고 `firebaseConfig` 자리(스크립트 상단)를 본인 프로젝트 값으로 채워야 합니다.
  단, 이건 로그인 **화면**만 막는 거라 `data/*.json` URL을 직접 알면 로그인 없이도 그 데이터는
  보입니다(정적 호스팅이라 파일 단위 접근 차단 불가). 진짜로 데이터까지 잠그려면 Firestore 등으로
  구조를 옮겨야 함(더 큰 작업).

---

## 로컬에서 직접 돌려보기

```bash
pip install -r requirements.txt
python scripts/fetch_holdings.py            # 오늘(KST) 기준, 모든 ETF
python scripts/fetch_holdings.py 20260626   # 특정일 강제 수집(samsung·time만 실제로 그 날짜로 됨)
python scripts/fetch_holdings.py 20250201:20260629   # 기간 채우기(영업일만, sol 계열은 자동 제외)
python scripts/fetch_holdings.py --debug    # 파싱 전 원본 표 확인
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
| 로그인 게이트 on/off | `index.html` 맨 아래 `AUTH_ENABLED` |
| 색/디자인 | `index.html` 상단 `:root` CSS 변수 |

---

## 알아둘 점

- 현금성 행(설정현금액·원화현금·현금성자산·100%현금설정액 등)은 `is_cash`로 표시되고
  편입/편출/비중 집계에서 제외하며, 사이트 표 하단에 흐리게 보입니다.
- 비중 값이 소수(0.07)로 들어오든 `7.00%`로 들어오든 자동으로 백분율(합 100%)로 정규화합니다
  (samsung 경로만 해당; sol/time은 원래부터 %로 옴).
- `.xls`(구형, samsung) 파싱엔 `xlrd`, `.xlsx`(신형, time) 파싱엔 `openpyxl`이 필요합니다
  (둘 다 `requirements.txt`에 포함). 삼성 응답이 드물게 HTML 표로 올 경우 `lxml`로 자동 폴백.
- 벤치마크 수익률은 전부 FinanceDataReader로 상장일부터 실시간 계산(월별 마지막 거래일 종가
  기준) — 별도 수동 시드 파일 필요 없음.
- 휴장일·미공시일에는(samsung만) 자동으로 직전 영업일 파일까지 후퇴해 찾고, 그래도 없으면
  건너뜁니다. sol/time은 해당 없음(항상 그날 결과 그대로 사용).
- 컨테이너/CI 환경에 따라 SEC·나스닥 등 외부 무료 API가 403으로 막힐 수 있습니다 — 실패해도
  조용히 다음 우선순위로 넘어가게 되어 있어 전체 수집은 멈추지 않습니다.

데이터 출처: 삼성액티브자산운용 · 신한자산운용(SOL) · 타임폴리오자산운용(TIME).
정보 제공용이며 투자 권유가 아닙니다.
