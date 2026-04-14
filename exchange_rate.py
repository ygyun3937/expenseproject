"""서울외국환중개(smbs.biz) 매매기준율 조회.

- 출처: http://www.smbs.biz/ExRate/StdExRate_xml.jsp?arr_value={CURR}_{YYYY-MM-DD}_{YYYY-MM-DD}
- JPY는 100엔 기준 고시이므로 1엔 기준으로 환산(÷100)한다.
- 주말/공휴일은 고시값이 없으므로 응답에 포함되지 않는다(영업일만 평균 계산).
- 동일 요청은 1일 TTL 메모리 캐시로 트래픽을 줄인다.
"""
from __future__ import annotations

import re
import time
import urllib.request
from datetime import date, timedelta
from typing import NamedTuple

SOURCE_NAME = "서울외국환중개 매매기준율"
XML_URL = "http://www.smbs.biz/ExRate/StdExRate_xml.jsp?arr_value={curr}_{start}_{end}"
_CACHE: dict[tuple, tuple[float, dict]] = {}
_TTL_SECONDS = 24 * 60 * 60

_SET_RE = re.compile(r"label='([^']+)'\s+value='([^']+)'")


class RateResult(NamedTuple):
    currency: str
    rate: float          # 1 단위당 KRW (JPY는 1엔 기준으로 변환됨)
    start: str           # YYYY-MM-DD
    end: str             # YYYY-MM-DD
    business_days: int   # 평균 산정에 사용된 영업일 수
    daily: list[tuple[str, float]]  # [(YYYY-MM-DD, rate), ...]
    source: str = SOURCE_NAME


def _fetch_xml(currency: str, start: str, end: str) -> str:
    url = XML_URL.format(curr=currency, start=start, end=end)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read()
    return raw.decode("euc-kr", errors="ignore")


def _parse(xml_text: str) -> list[tuple[str, float]]:
    out = []
    for label, value in _SET_RE.findall(xml_text):
        # label 예: "26.04.09" → "2026-04-09"
        parts = label.split(".")
        if len(parts) != 3:
            continue
        yy, mm, dd = parts
        iso = f"20{yy}-{mm.zfill(2)}-{dd.zfill(2)}"
        try:
            out.append((iso, float(value)))
        except ValueError:
            continue
    return out


def fetch_rates(currency: str, start: str, end: str) -> RateResult:
    """기간 내 영업일별 매매기준율을 가져오고 평균을 계산한다.

    Args:
        currency: ISO 통화코드 (USD, JPY, EUR 등)
        start: YYYY-MM-DD
        end:   YYYY-MM-DD

    Raises:
        ValueError: 기간 내 고시값을 하나도 찾지 못한 경우.
    """
    currency = currency.strip().upper()
    key = (currency, start, end)
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _TTL_SECONDS:
        data = hit[1]
        return RateResult(**data)

    xml_text = _fetch_xml(currency, start, end)
    daily = _parse(xml_text)
    if not daily:
        raise ValueError(f"서울외국환중개에서 {currency} {start}~{end} 기간의 고시환율을 찾을 수 없습니다.")

    if currency == "JPY":
        daily = [(d, v / 100.0) for d, v in daily]

    avg = sum(v for _, v in daily) / len(daily)
    result = RateResult(
        currency=currency,
        rate=round(avg, 4),
        start=start,
        end=end,
        business_days=len(daily),
        daily=daily,
    )
    _CACHE[key] = (now, result._asdict())
    return result


def fetch_latest(currency: str) -> RateResult:
    """최근 영업일 매매기준율 (오늘부터 7일 창에서 가장 최근값)."""
    today = date.today()
    start = (today - timedelta(days=7)).isoformat()
    end = today.isoformat()
    res = fetch_rates(currency, start, end)
    last_date, last_rate = res.daily[-1]
    return RateResult(
        currency=res.currency,
        rate=last_rate,
        start=last_date,
        end=last_date,
        business_days=1,
        daily=[(last_date, last_rate)],
    )
