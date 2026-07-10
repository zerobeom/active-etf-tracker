#!/usr/bin/env python3
"""
Active ETF 일별 전체 구성종목 수집기 (다중 운용사·다중 ETF 지원).

데이터 소스:
    - 삼성액티브자산운용(KoAct) '투자종목정보(PDF)' 엑셀 다운로드
        https://www.samsungactive.co.kr/excel_pdf.do?fId={펀드ID}&gijunYMD=YYYYMMDD
      (provider: "samsung"). 날짜 파라미터 실제로 작동 → 과거 기간 채우기 됨.
    - 신한자산운용(SOL) 공식 JSON API
        https://www.soletf.com/api/fund/pdfList?fund_cd={내부ID}&work_dt=YYYYMMDD
      (provider: "sol"). `work_dt` 파라미터 실제로 작동 확인됨(과거 날짜 그대로 반환) →
      과거 기간 채우기 됨. 응답에 종목명(SEC_NM)·수량(QTY)·평가금액(PRICE)·비중(WT_DISP)·
      종목코드(STOCK_CODE)가 옴.
        · 한국 종목(SOL 코리아메가테크액티브): STOCK_CODE가 이미 KRX 6자리 코드라 그대로 티커로 씀.
        · 미국 종목(SOL 미국넥스트테크TOP10액티브): STOCK_CODE가 ISIN이라(티커 아님), 실제 거래
          티커는 이름 매칭으로 찾음 — SOL_US_TICKERS 수동 매핑 → KoAct 나스닥 참조 → 나스닥
          심볼 목록 → SEC 티커 목록 순. 리밸런싱으로 새 종목이 들어오면 실행 로그의
          "[ticker] 매핑 안됨" 항목을 보고 SOL_US_TICKERS에 추가해주면 됨.
    - 타임폴리오자산운용(TIME) 엑셀(.xlsx) 다운로드
        https://timeetf.co.kr/pdf_excel.php?idx={내부ID}&cate=&pdfDate=YYYY-MM-DD
      (provider: "time"). `pdfDate` 파라미터 실제로 작동 → 과거 기간 채우기 됨. 종목코드가
      이미 'SNDK US EQUITY'식으로 와서 티커 매핑 불필요.

추적 대상은 아래 ETFS 목록에 추가만 하면 늘어납니다. 세 provider(samsung/sol/time) 모두
날짜 파라미터가 실제로 작동해 과거 기간 채우기(backfill)가 정상적으로 됩니다.

산출물(ETF별로 분리):
    data/etfs.json                      : 사이트가 읽는 ETF 목록
    data/{slug}/snapshots/YYYY-MM-DD.json
    data/{slug}/dates.json
    data/{slug}/latest.json
    data/{slug}/perf.json                : 벤치마크 대비 누적수익률(월별, benchmarks 있는 ETF만)

사용:
    python scripts/fetch_holdings.py            # 오늘(KST) 기준, 모든 ETF
    python scripts/fetch_holdings.py 20260626   # 특정일 강제 수집(과거 채우기, 단일일 · samsung 전용)
    python scripts/fetch_holdings.py 20250201:20260629   # 기간 채우기(영업일만 순회 · samsung 전용)
    python scripts/fetch_holdings.py --debug     # 파싱 전 원본 표 출력
"""
from __future__ import annotations

import io
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── 추적할 ETF 목록 ──────────────────────────────────────────────────────
# slug: 폴더/URL용 영문 식별자
# provider: "samsung"(삼성 KoAct, 엑셀) / "sol"(신한 SOL, 웹페이지 표)
# fid: provider="samsung"이면 운용사 펀드ID / provider="sol"이면 soletf.com 내부 상품ID
# ticker: 거래소 단축코드(표시용)
ETFS = [
    {"slug": "us-nasdaq", "provider": "samsung", "fid": "2ETFQ1", "ticker": "0015B0",
     "name": "KoAct 미국나스닥성장기업액티브", "start": "2025-02-25",
     "usd_price": True,
     "benchmarks": [
         {"k": "b1", "label": "나스닥종합", "sym": ["IXIC", "YAHOO:^IXIC"]},
         {"k": "b2", "label": "나스닥100", "sym": ["YAHOO:^NDX", "NDX"]},
     ]},
    {"slug": "kr-valueup", "provider": "samsung", "fid": "2ETFP3", "ticker": "495230",
     "name": "KoAct 코리아밸류업액티브", "start": "2024-11-04",
     "benchmarks": [
         {"k": "b1", "label": "코스피", "sym": ["KS11", "KOSPI"]},
     ]},
    {"slug": "sol-nexttech", "provider": "sol", "fid": "211099", "ticker": "0118S0",
     "name": "SOL 미국넥스트테크TOP10액티브", "start": "2025-10-28",
     "usd_price": True,
     "benchmarks": [
         {"k": "b1", "label": "나스닥종합", "sym": ["IXIC", "YAHOO:^IXIC"]},
         {"k": "b2", "label": "나스닥100", "sym": ["YAHOO:^NDX", "NDX"]},
     ]},
    {"slug": "sol-megatech", "provider": "sol", "fid": "210940", "ticker": "444200",
     "name": "SOL 코리아메가테크액티브", "start": "2022-10-18",
     "benchmarks": [
         {"k": "b1", "label": "코스피", "sym": ["KS11", "KOSPI"]},
     ]},
    {"slug": "time-nasdaq100", "provider": "time", "fid": "2", "ticker": "426030",
     "name": "TIME 미국나스닥100액티브", "start": "2022-05-11",
     "usd_price": True,
     "benchmarks": [
         {"k": "b1", "label": "나스닥종합", "sym": ["IXIC", "YAHOO:^IXIC"]},
         {"k": "b2", "label": "나스닥100", "sym": ["YAHOO:^NDX", "NDX"]},
     ]},
    {"slug": "time-sp500", "provider": "time", "fid": "5", "ticker": "426020",
     "name": "TIME 미국S&P500액티브", "start": "2022-05-11",
     "usd_price": True,
     "benchmarks": [
         {"k": "b1", "label": "S&P500", "sym": ["US500", "YAHOO:^GSPC"]},
     ]},
]

PERF_START = "2025-01-01"   # 수익률 시계열 조회 시작(ETF 상장 이전)

URL = "https://www.samsungactive.co.kr/excel_pdf.do"
TIME_URL = "https://timeetf.co.kr/pdf_excel.php"
LOOKBACK_DAYS = 7                       # (samsung 전용) 해당일 파일이 없으면 며칠 전까지 후퇴 탐색

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
KST = timezone(timedelta(hours=9))

# SOL 미국넥스트테크TOP10액티브(0118S0) 종목명 -> 티커 수동 매핑.
# 리밸런싱으로 새 종목이 들어오면 실행 로그의 "[ticker] 매핑 안됨: ..." 항목을 보고
# 여기 한 줄 추가해주면 됨(추가 전까지는 해당 종목 티커가 빈칸으로 저장됨).
SOL_US_TICKERS = {
    "Sandisk Corp/DE": "SNDK",
    "Planet Labs PBC": "PL",
    "Bloom Energy Corp": "BE",
    "Rocket Lab Corp": "RKLB",
    "Viasat Inc": "VSAT",
    "IonQ Inc": "IONQ",
    "D-Wave Quantum Inc": "QBTS",
    "Oklo Inc": "OKLO",
    "TTM Technologies Inc": "TTMI",
    "Lumentum Holdings Inc": "LITE",
    "Cloudflare Inc": "NET",
    "Vertiv Holdings Co": "VRT",
    "Cogent Biosciences Inc": "COGT",
    "Vicor Corp": "VICR",
    "Ondas Inc": "ONDS",
    "Intuitive Machines Inc": "LUNR",
    "USA Rare Earth Inc": "USAR",
    "CoreWeave Inc": "CRWV",
    "TARGA RESOURCES CORP": "TRGP",
    "Aehr Test Systems": "AEHR",
    "Roundhill Memory ETF": "DRAM",
    "Rocket Lab USA Inc": "RKLB",     # 'Rocket Lab Corp'와 같은 회사의 다른 표기(날짜별로 표기가 바뀜)
    "Crowdstrike Holdings Inc": "CRWD",
    "DELL TECHNOLOGIES - C": "DELL",
    "LAM RESEARCH CORP": "LRCX",
    "Navitas Semiconductor Corp": "NVTS",
    "Nokia Oyj": "NOK",
    "STMicroelectronics NV": "STM",
    "Coherent Corp": "COHR",
    "GE Vernova Inc": "GEV",
    "Space Exploration Technologies Corp": "SPCX",
    "Marvell Technology Inc": "MRVL",
    "Micron Technology Inc": "MU",
}


# ── 유틸 ────────────────────────────────────────────────────────────────
def today_kst() -> str:
    return datetime.now(KST).strftime("%Y%m%d")


def today_iso_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def to_num(v):
    if v is None:
        return None
    try:
        s = str(v).replace(",", "").replace("%", "").strip()
        if s in ("", "-", "nan", "None"):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def clean(v):
    s = str(v).strip()
    return "" if s.lower() in ("nan", "none") else s


def clean_ticker(code: str) -> str:
    """'MU US Equity' -> 'MU', '005930 KS Equity' -> '005930'. 현금/특수코드는 빈 문자열."""
    code = clean(code)
    if not code or code.startswith(("CASH", "KRD", "KRW")):
        return ""
    return code.split()[0]


def strip_brand(name: str) -> str:
    return re.sub(r"^(KoAct|SOL)\s*", "", name or "")


# ── 다운로드 + 파싱 (삼성 KoAct · 엑셀) ──────────────────────────────────
def download(date_yyyymmdd: str, fid: str) -> bytes:
    import requests
    r = requests.get(
        URL,
        params={"fId": fid, "gijunYMD": date_yyyymmdd},
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0",
                 "Referer": "https://www.samsungactive.co.kr/"},
    )
    r.raise_for_status()
    return r.content


def read_table(content: bytes):
    """엑셀(.xls BIFF) 우선, 실패 시 HTML 표로 폴백. header 없이 원본 셀 그대로."""
    import pandas as pd
    try:
        return pd.read_excel(io.BytesIO(content), header=None, dtype=str, engine="xlrd")
    except Exception:
        pass
    try:
        tables = pd.read_html(io.BytesIO(content))
        if tables:
            return max(tables, key=len)
    except Exception:
        pass
    return None


def normalize(raw, debug: bool = False):
    """원본 표(header=None DataFrame) -> (기준일 'YYYY-MM-DD', holdings[list])."""
    if raw is None or len(raw) == 0:
        return None, None
    raw = raw.reset_index(drop=True)
    if debug:
        print(raw.head(6).to_string())

    hdr = None
    for i in range(min(12, len(raw))):
        cells = [str(x).strip() for x in raw.iloc[i].tolist()]
        if "종목명" in cells and any("ISIN" in c or "비중" in c for c in cells):
            hdr = i
            break
    if hdr is None:
        return None, None

    cols = [str(x).strip() for x in raw.iloc[hdr].tolist()]
    body = raw.iloc[hdr + 1:].reset_index(drop=True)
    body.columns = cols

    base_date = None
    for i in range(hdr):
        for x in raw.iloc[i].tolist():
            m = re.match(r"(\d{4})[/.\-](\d{2})[/.\-](\d{2})", str(x).strip())
            if m:
                base_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                break
        if base_date:
            break

    def col(*names):
        for n in names:
            for c in cols:
                if n in c:
                    return c
        return None

    cN = col("종목명")
    cI = col("ISIN")
    cC = col("종목코드", "코드")
    cQ = col("수량")
    cW = col("비중")
    cA = col("평가금액", "평가")
    cP = col("현재가", "현재가(원)")

    holdings = []
    for _, r in body.iterrows():
        name = clean(r.get(cN)) if cN else ""
        if not name or name in ("번호", "종목명"):
            continue
        isin = clean(r.get(cI)) if cI else ""
        code = clean(r.get(cC)) if cC else ""
        is_cash = (isin.startswith(("CASH", "KRD", "KRW"))
                   or "현금" in name or "설정현금" in name)
        holdings.append({
            "isin": isin, "name": name, "code": code,
            "ticker": clean_ticker(code),
            "weight": to_num(r.get(cW)) if cW else None,
            "shares": to_num(r.get(cQ)) if cQ else None,
            "amount": to_num(r.get(cA)) if cA else None,
            "price": to_num(r.get(cP)) if cP else None,   # 현재가(원) — 갱신 시점 가격
            "is_cash": is_cash,
            "key": isin or code or name,
        })

    holdings = [h for h in holdings if h["key"]]

    total = sum((h["weight"] or 0) for h in holdings)
    if 0 < total <= 3:
        for h in holdings:
            if h["weight"] is not None:
                h["weight"] *= 100
    for h in holdings:
        if h["weight"] is not None:
            h["weight"] = round(h["weight"], 4)
        if h["shares"] is not None:
            h["shares"] = int(round(h["shares"]))
        if h["price"] is not None:
            h["price"] = int(round(h["price"]))   # 현재가(원) 정수

    holdings.sort(key=lambda z: (z["weight"] or 0), reverse=True)
    return base_date, holdings


def fetch_latest_available(start_yyyymmdd: str, fid: str, debug: bool = False):
    d = datetime.strptime(start_yyyymmdd, "%Y%m%d")
    for _ in range(LOOKBACK_DAYS + 1):
        ds = d.strftime("%Y%m%d")
        try:
            content = download(ds, fid)
            base_date, holdings = normalize(read_table(content), debug=debug)
            if holdings:
                if not base_date:
                    base_date = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"
                return base_date, holdings
            print(f"    - {ds}: 유효 데이터 없음, 하루 전으로")
        except Exception as e:
            print(f"    - {ds}: 다운로드/파싱 실패 ({e})")
        d -= timedelta(days=1)
    return None, None


# ── 다운로드 + 파싱 (신한 SOL · JSON API, 과거 날짜 조회 가능) ───────────
_SEC_TICKER_MAP = None
_NASDAQ_TICKER_MAP = None
SOL_API_URL = "https://www.soletf.com/api/fund/pdfList"


def _norm_us_name(n: str) -> str:
    """미국 종목명을 비교 가능하게 정규화. 'Sandisk Corp/DE' -> 'SANDISK'."""
    n = (n or "").upper()
    n = re.sub(r"/[A-Z]{2}$", "", n)                          # '/DE', '/MD' 같은 주(州) 표기 제거
    n = re.sub(r"[.,]", "", n)
    n = re.sub(r"\b(INC|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|"
               r"PLC|PBC|LLC|HOLDINGS?|GROUP|TRUST)\b", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def koact_us_ticker_map():
    """이미 수집해둔 KoAct 미국나스닥성장기업액티브 최신 스냅샷에서 종목명 -> 티커를 뽑아
    SOL 미국 종목 매핑의 보조 소스로 쓴다(겹치는 종목이 있으면 공짜로 해결됨)."""
    m = {}
    try:
        f = DATA / "us-nasdaq" / "latest.json"
        if f.exists():
            latest = json.loads(f.read_text(encoding="utf-8"))
            for h in latest.get("holdings", []):
                if h.get("ticker") and h.get("name"):
                    m[_norm_us_name(h["name"])] = h["ticker"]
    except Exception as e:
        print(f"  [ticker] KoAct 나스닥 스냅샷 참조 실패: {e}")
    return m


def sec_us_ticker_map():
    """SEC(미국 증권거래위원회)가 무료 공개하는 전체 상장기업 티커 목록으로
    '정규화된 회사명 -> 티커' 맵을 만든다(런 1회, 캐시). 로그인/키 불필요.
    ⚠️ SEC가 클라우드/데이터센터 IP 요청을 종종 403으로 막아서, 이 함수는
    실패해도 조용히 빈 맵을 돌려주고 다음 소스(나스닥 심볼 디렉터리)로 넘어간다."""
    global _SEC_TICKER_MAP
    if _SEC_TICKER_MAP is not None:
        return _SEC_TICKER_MAP
    m = {}
    try:
        import requests
        r = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            timeout=30,
            headers={"User-Agent": "koact-tracker research contact@example.com"},
        )
        r.raise_for_status()
        for row in r.json().values():
            title, ticker = row.get("title", ""), row.get("ticker", "")
            if title and ticker:
                m[_norm_us_name(title)] = ticker
    except Exception as e:
        print(f"  [ticker] SEC 티커 목록 조회 실패(건너뜀): {e}")
    _SEC_TICKER_MAP = m
    return m


def nasdaq_us_ticker_map():
    """나스닥거래소가 공개하는 상장기업 심볼 디렉터리(HTTP, 로그인/키 불필요)로
    '정규화된 회사명 -> 티커' 맵을 만든다(런 1회, 캐시). SEC보다 차단 이슈가 적어
    실전에서 더 안정적인 편."""
    global _NASDAQ_TICKER_MAP
    if _NASDAQ_TICKER_MAP is not None:
        return _NASDAQ_TICKER_MAP
    m = {}
    try:
        import requests
        for url in ("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
                    "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"):
            r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            lines = r.text.splitlines()
            if not lines:
                continue
            header = lines[0].split("|")
            sym_i = header.index("Symbol") if "Symbol" in header else 0
            name_i = next((i for i, h in enumerate(header) if "Name" in h), 1)
            for line in lines[1:]:
                parts = line.split("|")
                if len(parts) <= max(sym_i, name_i) or "File Creation Time" in line:
                    continue
                sym, name = parts[sym_i].strip(), parts[name_i].strip()
                if not sym or not name:
                    continue
                # 'ATA Creativity Global - American Depositary Shares...'처럼 뒤에
                # 주식 종류 설명이 붙는 경우가 많아 첫 ' - ' 앞부분만 회사명으로 씀
                base_name = name.split(" - ")[0]
                m[_norm_us_name(base_name)] = sym
    except Exception as e:
        print(f"  [ticker] 나스닥 심볼 목록 조회 실패(건너뜀): {e}")
    _NASDAQ_TICKER_MAP = m
    return m


def download_sol(internal_id: str, work_dt: str, retries: int = 3) -> list:
    """work_dt('YYYYMMDD')는 실제로 그 날짜의 데이터를 준다(확인됨) — 과거 조회 가능.
    짧은 시간에 요청이 몰리면(백필) SOL 쪽에서 일시적으로 막을 수 있어서, 실패하면
    점점 더 오래 기다렸다가 재시도한다(2초 → 6초 → 18초)."""
    import requests, time as _time
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(
                SOL_API_URL,
                params={"fund_cd": internal_id, "work_dt": work_dt},
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.soletf.com/"},
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                wait = 2 * (3 ** attempt)   # 2s, 6s, 18s
                print(f"    [retry] SOL 요청 실패({e}), {wait}초 후 재시도 ({attempt+1}/{retries})")
                _time.sleep(wait)
    raise last_err


def normalize_sol(rows: list, is_us: bool, work_dt: str, debug: bool = False):
    """API 응답(JSON 리스트) -> (기준일, holdings).
    한국 종목은 STOCK_CODE가 이미 KRX 6자리 코드라 그대로 티커로 씀(이름 매칭 불필요).
    미국 종목은 STOCK_CODE가 ISIN이라, 실제 거래 티커는 여전히 이름 매칭으로 찾아야 함."""
    if not rows:
        return None, None
    if debug:
        print(rows[:3])

    koact_map = koact_us_ticker_map() if is_us else None
    nasdaq_map = nasdaq_us_ticker_map() if is_us else None
    sec_map = sec_us_ticker_map() if is_us else None

    holdings = []
    for row in rows:
        name = clean(row.get("SEC_NM"))
        if not name:
            continue
        code = clean(row.get("STOCK_CODE"))
        is_cash = "현금" in name or code.startswith(("CASH", "KRD", "KRW"))
        isin, ticker = "", ""
        if is_cash:
            pass
        elif is_us:
            isin = code   # 미국은 STOCK_CODE 자리에 ISIN이 옴
            ticker = SOL_US_TICKERS.get(name, "")
            src = "수동매핑"
            if not ticker:
                ticker = koact_map.get(_norm_us_name(name), "")
                src = "KoAct나스닥참조"
            if not ticker:
                ticker = nasdaq_map.get(_norm_us_name(name), "")
                src = "나스닥목록"
            if not ticker:
                ticker = sec_map.get(_norm_us_name(name), "")
                src = "SEC목록"
            if not ticker:
                print(f"  [ticker] 매핑 안됨(SOL_US_TICKERS에 추가 검토): {name}")
            elif debug:
                print(f"  [ticker] {name} -> {ticker} ({src})")
        else:
            ticker = code   # 한국은 STOCK_CODE가 곧 KRX 코드

        weight_raw = clean(row.get("WT_DISP")).replace("%", "").strip()
        weight = to_num(weight_raw) if weight_raw else None
        shares = to_num(row.get("QTY"))
        amount = to_num(row.get("PRICE"))   # 필드명은 PRICE지만 실제로는 평가금액(원)
        price = None
        if not is_cash and not is_us and shares:
            price = int(round(amount / shares)) if amount else None

        holdings.append({
            "isin": isin, "name": name, "code": ticker, "ticker": ticker,
            "weight": weight, "shares": shares, "amount": amount,
            "price": price, "is_cash": is_cash,
            "key": ticker or name,
        })

    holdings = [h for h in holdings if h["key"]]
    for h in holdings:
        if h["weight"] is not None:
            h["weight"] = round(h["weight"], 4)
        if h["shares"] is not None:
            h["shares"] = round(h["shares"], 2) if is_us else int(round(h["shares"]))

    holdings.sort(key=lambda z: (z["weight"] or 0), reverse=True)
    base_date = f"{work_dt[:4]}-{work_dt[4:6]}-{work_dt[6:]}"
    return base_date, holdings


# ── 다운로드 + 파싱 (타임폴리오 TIME · xlsx 직접 다운로드) ───────────────
def download_time(internal_id: str, pdf_date: str = None) -> bytes:
    """pdf_date('YYYY-MM-DD')를 주면 그 날짜의 구성종목을, 안 주면 최신을 받는다.
    TIME은 SOL과 달리 실제로 과거 날짜 조회가 되는 걸 확인함(pdfDate 파라미터)."""
    import requests
    params = {"idx": internal_id, "cate": ""}
    if pdf_date:
        params["pdfDate"] = pdf_date
    r = requests.get(
        TIME_URL,
        params=params,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://timeetf.co.kr/"},
    )
    r.raise_for_status()
    return r.content


def read_time_table(content: bytes):
    """TIME은 진짜 최신 .xlsx라 openpyxl로 바로 읽힌다(엑셀/HTML 폴백도 대비)."""
    import pandas as pd
    try:
        return pd.read_excel(io.BytesIO(content), header=None, dtype=str, engine="openpyxl")
    except Exception:
        pass
    try:
        return pd.read_excel(io.BytesIO(content), header=None, dtype=str, engine="xlrd")
    except Exception:
        pass
    try:
        tables = pd.read_html(io.BytesIO(content))
        if tables:
            return max(tables, key=len)
    except Exception:
        pass
    return None


def normalize_time(raw, debug: bool = False):
    """TIME 엑셀 -> (기준일, holdings). 컬럼 구조가 삼성 포맷과 비슷해서
    (종목코드/종목명/수량/평가금액/비중) 같은 방식으로 표를 찾아 판다."""
    if raw is None or len(raw) == 0:
        return None, None
    raw = raw.reset_index(drop=True)
    if debug:
        print(raw.head(6).to_string())

    hdr = None
    for i in range(min(12, len(raw))):
        cells = [str(x).strip() for x in raw.iloc[i].tolist()]
        if "종목명" in cells and any("종목코드" in c or "비중" in c for c in cells):
            hdr = i
            break
    if hdr is None:
        return None, None

    cols = [str(x).strip() for x in raw.iloc[hdr].tolist()]
    body = raw.iloc[hdr + 1:].reset_index(drop=True)
    body.columns = cols

    base_date = None
    for i in range(hdr):
        for x in raw.iloc[i].tolist():
            m = re.match(r"(\d{4})[/.\-](\d{2})[/.\-](\d{2})", str(x).strip())
            if m:
                base_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                break
        if base_date:
            break

    def col(*names):
        for n in names:
            for c in cols:
                if n in c:
                    return c
        return None

    cN = col("종목명")
    cC = col("종목코드", "코드")
    cQ = col("수량")
    cW = col("비중")
    cA = col("평가금액", "평가")

    holdings = []
    for _, r in body.iterrows():
        name = clean(r.get(cN)) if cN else ""
        if not name or name in ("번호", "종목명"):
            continue
        code = clean(r.get(cC)) if cC else ""
        is_cash = "현금" in name or (cC and not code)
        holdings.append({
            "isin": "", "name": name, "code": code,
            "ticker": clean_ticker(code),
            "weight": to_num(r.get(cW)) if cW else None,
            "shares": to_num(r.get(cQ)) if cQ else None,
            "amount": to_num(r.get(cA)) if cA else None,
            "price": None,
            "is_cash": is_cash,
            "key": code or name,
        })

    holdings = [h for h in holdings if h["key"]]
    for h in holdings:
        if h["weight"] is not None:
            h["weight"] = round(h["weight"], 4)
        if h["shares"] is not None:
            h["shares"] = round(h["shares"], 4)

    holdings.sort(key=lambda z: (z["weight"] or 0), reverse=True)
    return base_date, holdings


# ── 변동 계산 (수량 중심) ────────────────────────────────────────────────
def diff(cur, prev):
    if not prev:
        return {"added": [], "removed": [], "bought": [], "sold": []}
    pmap = {h["key"]: h for h in prev}
    cmap = {h["key"]: h for h in cur}
    added, removed, bought, sold = [], [], [], []

    for k, h in cmap.items():
        if h.get("is_cash"):
            continue
        if k not in pmap:
            added.append({"name": h["name"], "ticker": h["ticker"],
                          "weight": h["weight"], "shares": h["shares"]})
            continue
        cs = h["shares"] or 0
        ps = pmap[k]["shares"] or 0
        ds = round(cs - ps, 4)
        if ds == 0:
            continue
        rec = {"name": h["name"], "ticker": h["ticker"],
               "shares": cs, "prev_shares": ps, "share_delta": ds,
               "weight": h["weight"], "prev_weight": pmap[k]["weight"],
               "weight_delta": round((h["weight"] or 0) - (pmap[k]["weight"] or 0), 4)}
        (bought if ds > 0 else sold).append(rec)

    for k, h in pmap.items():
        if h.get("is_cash"):
            continue
        if k not in cmap:
            removed.append({"name": h["name"], "ticker": h["ticker"],
                            "weight": h["weight"], "shares": h["shares"]})

    added.sort(key=lambda z: z["weight"] or 0, reverse=True)
    removed.sort(key=lambda z: z["weight"] or 0, reverse=True)
    bought.sort(key=lambda z: z["weight"] or 0, reverse=True)
    sold.sort(key=lambda z: z["weight"] or 0, reverse=True)
    return {"added": added, "removed": removed, "bought": bought, "sold": sold}


# ── 미국 종목 현재가(달러) ───────────────────────────────────────────────
def fetch_usd_prices(tickers, end_iso: str):
    """미국 티커들의 기준일(end_iso) 종가(USD)를 한 번에 받아온다. {ticker: price}."""
    import yfinance as yf
    import pandas as pd
    from datetime import datetime, timedelta
    tickers = sorted(set(t for t in tickers if t))
    if not tickers:
        return {}
    end = datetime.strptime(end_iso, "%Y-%m-%d")
    start = (end - timedelta(days=12)).strftime("%Y-%m-%d")
    endp = (end + timedelta(days=1)).strftime("%Y-%m-%d")
    data = yf.download(tickers, start=start, end=endp,
                       progress=False, auto_adjust=False, threads=True)
    if data is None or len(data) == 0:
        return {}
    close = data["Close"] if "Close" in getattr(data, "columns", []) else data
    out = {}
    if isinstance(close, pd.Series):
        s = close.ffill().dropna()
        if len(s):
            out[tickers[0]] = float(s.iloc[-1])
    else:
        last = close.ffill().iloc[-1]
        for t in close.columns:
            v = last.get(t)
            if v is not None and v == v:        # NaN 제외
                out[str(t)] = float(v)
    return out


# ── 벤치마크 수익률 ──────────────────────────────────────────────────────
def _close(sym, start: str, end: str):
    """FinanceDataReader로 일별 종가 시리즈(인덱스=날짜) 반환. 실패 시 예외/None.

    sym은 문자열 또는 후보 목록(list). 목록이면 데이터가 나올 때까지 차례로 시도한다.
    예: '0015B0'(ETF·네이버), 'KS11'(코스피), ['KS100','KOSPI100'](코스피100),
        'IXIC'(나스닥종합), 'YAHOO:^NDX'(나스닥100).
    KRX 직접 접근이 아니라 네이버/야후를 쓰므로 로그인이 필요 없다.
    """
    import FinanceDataReader as fdr
    cands = sym if isinstance(sym, (list, tuple)) else [sym]
    last_err = None
    for s in cands:
        try:
            df = fdr.DataReader(s, start, end)
            if df is not None and len(df) and "Close" in df.columns and df["Close"].notna().any():
                return df["Close"]
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err
    return None


def monthly_last(series):
    """일별 종가 -> {YYYY-MM: 그 달 마지막 종가}."""
    import pandas as pd
    if series is None or len(series) == 0:
        return {}
    s = series.dropna()
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()
    out = {}
    for ts, v in s.items():
        out[f"{ts.year:04d}-{ts.month:02d}"] = float(v)   # 정렬됐으므로 마지막 값이 남음
    return out


def build_perf(etf: dict, end_iso: str, debug: bool = False):
    bms = etf.get("benchmarks") or []
    if not bms:
        return
    start = etf.get("start", PERF_START)   # ETF 상장월부터
    try:
        etf_m = monthly_last(_close(etf["ticker"], start, end_iso))
    except Exception as e:
        print(f"  [perf] ETF 시세 실패: {e}")
        etf_m = {}
    if not etf_m:
        print("  [perf] ETF 시세를 받지 못해 건너뜀")
        return

    bm_m, labels = {}, []
    for b in bms:
        try:
            bm_m[b["k"]] = monthly_last(_close(b["sym"], start, end_iso))
            if not bm_m[b["k"]]:
                print(f"  [perf] {b['label']}({b['sym']}) 데이터 비어있음")
        except Exception as e:
            print(f"  [perf] {b['label']}({b['sym']}) 시세 실패: {e}")
            bm_m[b["k"]] = {}
        labels.append({"k": b["k"], "label": b["label"]})

    months = sorted(etf_m.keys())
    base = next((mo for mo in months if all(mo in bm_m[b["k"]] for b in bms)), months[0])

    def cum(m, mo):
        if mo not in m or base not in m or m[base] == 0:
            return None
        return round(m[mo] / m[base] * 100 - 100, 2)

    series = []
    for mo in months:
        if mo < base:
            continue
        row = {"month": mo, "etf": cum(etf_m, mo)}
        for b in bms:
            row[b["k"]] = cum(bm_m[b["k"]], mo)
        series.append(row)

    perf = {"as_of": end_iso, "base": base,
            "etf_label": strip_brand(etf["name"]),
            "benchmarks": labels, "series": series}
    (DATA / etf["slug"] / "perf.json").write_text(
        json.dumps(perf, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [perf] {len(series)}개월 수익률 (기준월 {base})")


# ── 저장 ────────────────────────────────────────────────────────────────
def load_snapshot(snap_dir: Path, date_iso: str):
    f = snap_dir / f"{date_iso}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))["holdings"]
    return None


def existing_dates(snap_dir: Path):
    return sorted(p.stem for p in snap_dir.glob("*.json"))


def prune_before_start(snap_dir: Path, start_iso: str):
    """상장일(start_iso, 'YYYY-MM-DD') 이전 날짜 스냅샷 파일을 삭제하고
    삭제한 날짜 목록을 돌려준다. ISO 날짜라 문자열 비교로 충분하다."""
    if not start_iso:
        return []
    removed = []
    for p in snap_dir.glob("*.json"):
        if p.stem < start_iso:
            p.unlink()
            removed.append(p.stem)
    return sorted(removed)


def process_etf(etf: dict, start: str, debug: bool = False, skip_perf: bool = False):
    slug = etf["slug"]
    provider = etf.get("provider", "samsung")
    edir = DATA / slug
    snap_dir = edir / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)

    # 상장일 이전에 잘못 수집된 스냅샷이 있으면 정리 (dates.json은 아래에서 재생성)
    pruned = prune_before_start(snap_dir, etf.get("start"))
    if pruned:
        print(f"  [prune] 상장일({etf.get('start')}) 이전 {len(pruned)}건 삭제: {', '.join(pruned)}")

    print(f"[{slug}] {etf['name']} ({etf['ticker']}) — provider={provider}, 요청 기준일 {start}")

    if provider == "sol":
        try:
            rows = download_sol(etf["fid"], work_dt=start)
            date_iso, holdings = normalize_sol(rows, is_us=bool(etf.get("usd_price")), work_dt=start, debug=debug)
        except Exception as e:
            print(f"  [skip] SOL API 요청/파싱 실패: {e}")
            return False
    elif provider == "time":
        pdf_date = f"{start[:4]}-{start[4:6]}-{start[6:]}"
        try:
            content = download_time(etf["fid"], pdf_date=pdf_date)
            date_iso, holdings = normalize_time(read_time_table(content), debug=debug)
        except Exception as e:
            print(f"  [skip] TIME 엑셀 요청/파싱 실패: {e}")
            return False
        if holdings and not date_iso:
            date_iso = pdf_date
    else:
        date_iso, holdings = fetch_latest_available(start, etf["fid"], debug=debug)

    if not holdings:
        print(f"  [skip] 최근 영업일 데이터를 찾지 못함.")
        return None   # 실패가 아니라 "그날 데이터 없음"일 수 있어 연속실패 카운트엔 안 넣음

    # 미국 종목 현재가(달러) — 표에 현재가가 없는 종목만
    if etf.get("usd_price"):
        try:
            tks = [h["ticker"] for h in holdings
                   if not h["is_cash"] and h["ticker"] and h["price"] is None]
            px = fetch_usd_prices(tks, date_iso)
            for h in holdings:
                if h["ticker"] in px:
                    h["price_usd"] = round(px[h["ticker"]], 2)
            print(f"  [price] 미국 현재가(USD) {len(px)}/{len(tks)}종목")
        except Exception as e:
            print(f"  [price] 미국 현재가 실패(건너뜀): {e}")

    prev_dates = [d for d in existing_dates(snap_dir) if d < date_iso]
    prev_date = prev_dates[-1] if prev_dates else None
    prev = load_snapshot(snap_dir, prev_date) if prev_date else None

    snap = {"date": date_iso, "ticker": etf["ticker"], "fund_id": etf["fid"],
            "name": etf["name"],
            "count": sum(1 for h in holdings if not h["is_cash"]),
            "holdings": holdings}
    (snap_dir / f"{date_iso}.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")

    latest = dict(snap)
    latest["prev_date"] = prev_date
    latest["changes"] = diff(holdings, prev)
    latest["updated_at"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M")  # 갱신 시각(KST)
    (edir / "latest.json").write_text(
        json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")
    (edir / "dates.json").write_text(
        json.dumps(existing_dates(snap_dir), ensure_ascii=False, indent=2), encoding="utf-8")

    c = latest["changes"]
    print(f"  [ok] {date_iso} · {snap['count']}종목. 전일({prev_date}) 대비 "
          f"편입 {len(c['added'])} · 편출 {len(c['removed'])} · "
          f"추가매수 {len(c['bought'])} · 일부매도 {len(c['sold'])}")

    # 벤치마크 수익률 (실패해도 보유종목 데이터에는 영향 없음. benchmarks가 없으면 자동 스킵)
    # ⚠️ build_perf는 매번 상장일~end_iso 전체 기간을 새로 계산한다. 백필처럼 날짜를 수백~수천 번
    # 반복하는 상황에서 매 날짜마다 부르면 극도로 비효율적이라, skip_perf=True면 건너뛰고
    # 백필이 다 끝난 뒤 맨 마지막에 딱 한 번만 계산한다(main() 참고).
    if not skip_perf:
        try:
            build_perf(etf, date_iso, debug=debug)
        except Exception as e:
            print(f"  [perf] 실패(건너뜀): {e}")
    return True


def business_days(start_yyyymmdd: str, end_yyyymmdd: str):
    d = datetime.strptime(start_yyyymmdd, "%Y%m%d")
    end = datetime.strptime(end_yyyymmdd, "%Y%m%d")
    while d <= end:
        if d.weekday() < 5:  # 월~금
            yield d.strftime("%Y%m%d")
        d += timedelta(days=1)


def main():
    import time

    only_arg = None
    args = []
    for a in sys.argv[1:]:
        if a == "--debug":
            continue
        if a.startswith("--only="):
            only_arg = a.split("=", 1)[1]
            continue
        args.append(a)
    debug = "--debug" in sys.argv

    def wanted(etf):
        if not only_arg:
            return True
        keys = [k.strip() for k in only_arg.split(",") if k.strip()]
        return etf.get("provider") in keys or etf["slug"] in keys

    DATA.mkdir(parents=True, exist_ok=True)
    # 사이트가 읽는 ETF 목록
    (DATA / "etfs.json").write_text(
        json.dumps([{k: e[k] for k in ("slug", "name", "ticker", "fid", "start")} for e in ETFS],
                   ensure_ascii=False, indent=2), encoding="utf-8")

    if args and ":" in args[0]:
        # 기간 채우기: "20250201:20260629" — 영업일만, 과거→최근 순서로 처리
        # samsung/sol/time 전부 실제 과거 날짜 조회가 되므로 세 provider 다 정상 백필됨.
        # --only=sol 처럼 provider명(samsung/sol/time) 또는 slug를 콤마로 넘기면 그것만 처리.
        start_s, end_s = args[0].split(":", 1)
        days = list(business_days(start_s, end_s))
        targets = [e for e in ETFS if wanted(e)]
        print(f"[backfill] {start_s} ~ {end_s} · 영업일 {len(days)}일 · 대상 ETF: "
              f"{', '.join(e['slug'] for e in targets) or '(없음)'}")
        # provider별 요청 간 딜레이(SOL이 유독 차단에 민감해서 더 여유있게)
        DELAY = {"sol": 2.5, "time": 1.5, "samsung": 1.0}
        fail_streak = {}   # slug -> 연속 실패 횟수
        for i, ds in enumerate(days, 1):
            print(f"\n--- ({i}/{len(days)}) {ds} ---")
            for etf in targets:
                etf_start = etf.get("start", "1900-01-01").replace("-", "")
                if ds < etf_start:
                    continue  # 상장 전 날짜는 건너뜀
                ok = process_etf(etf, ds, debug=debug, skip_perf=True)
                if ok is False:
                    fail_streak[etf["slug"]] = fail_streak.get(etf["slug"], 0) + 1
                    if fail_streak[etf["slug"]] >= 5:
                        cooldown = 90
                        print(f"  [cooldown] {etf['slug']} 5회 연속 실패 — 차단/제한 가능성, "
                              f"{cooldown}초 쉬었다가 계속")
                        time.sleep(cooldown)
                        fail_streak[etf["slug"]] = 0
                else:
                    fail_streak[etf["slug"]] = 0
                time.sleep(DELAY.get(etf.get("provider"), 1.0))  # 서버 부담 완화

        print(f"\n[backfill] 홀딩스 수집 끝 → 벤치마크 수익률은 ETF당 한 번씩만 계산")
        end_iso = f"{end_s[:4]}-{end_s[4:6]}-{end_s[6:]}"
        for etf in targets:
            if not etf.get("benchmarks"):
                continue
            try:
                build_perf(etf, end_iso, debug=debug)
            except Exception as e:
                print(f"  [perf] {etf['slug']} 실패(건너뜀): {e}")
        return 0

    start = args[0] if args else today_kst()
    for etf in ETFS:
        if not wanted(etf):
            continue
        process_etf(etf, start, debug=debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
