"""한국석유공사 KNOC 메인페이지 일별 국내 유가 조회.

- 출처: https://www.knoc.co.kr/ "오늘의 유가" 섹션 (일 평균가, EUC-KR)
- 유종: 휘발유 / 자동차용경유 / LPG(부탄)
- **자동 스냅샷**: 매일 최초 요청 시 당일 유가를 history.json에 누적 저장
- **과거 조회**: 히스토리에 해당일자 있으면 반환, 없으면 FuelPriceUnavailable
- 주말이면 직전 평일(금요일)로 자동 이동
"""
from __future__ import annotations

import json
import math
import re
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import NamedTuple

HISTORY_PATH = Path(__file__).parent / "fuel_price_history.json"

SOURCE_NAME = "한국석유공사 KNOC 오늘의 유가 (일 평균가)"
SOURCE_NAME_WEEKLY = "한국석유공사 페트로넷 주유소 주간 평균가"
KNOC_URL = "https://www.knoc.co.kr/"
URL = "https://www.petronet.co.kr/v4/main.jsp"  # 주간 fallback
_CACHE: dict[str, tuple[float, dict]] = {}
_TTL_SECONDS = 24 * 60 * 60

# 페트로넷(주간) 파서 정규식
_DATASET_RE = re.compile(
    r'label:\s*"([^"]+)"[\s\S]*?data\s*:\s*\[([^\]]+)\]',
    re.MULTILINE,
)
_LABELS_RE = re.compile(r"labels:\s*\[([^\]]+)\]")

# KNOC 메인 일별 가격 파서
# <div id="panel1-1" ...> ... <strong>1997.94</strong> ... <p>2026.04.15...</p>
_KNOC_PANEL_RE = re.compile(
    r'<div id="panel1-(\d+)"[^>]*>([\s\S]*?)</div>\s*</div>',
)
_KNOC_PRICE_RE = re.compile(r'<strong>([\d.,]+)</strong>')
_KNOC_DATE_RE = re.compile(r'(\d{4})\.(\d{2})\.(\d{2})')


class FuelPriceResult(NamedTuple):
    gasoline: float | None       # 휘발유 원/L
    diesel: float | None         # 경유 원/L
    week_label: str              # 주간 라벨 (예: "4.1" = 4월 1주)
    target_date: str = ""        # 기준 일자 YYYY-MM-DD
    source: str = SOURCE_NAME


def _fetch_html() -> str:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _fetch_knoc_html() -> str:
    req = urllib.request.Request(KNOC_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read()
    # EUC-KR 인코딩
    try:
        return raw.decode("euc-kr", errors="ignore")
    except Exception:
        return raw.decode("utf-8", errors="ignore")


def _load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {}
    try:
        with HISTORY_PATH.open("r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save_history(history: dict):
    try:
        with HISTORY_PATH.open("w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2, sort_keys=True)
    except Exception:
        pass


def _snapshot_today_if_needed():
    """오늘 스냅샷이 없으면 KNOC 조회 후 저장.
    KNOC 당일 유가 공시 시각은 관리자 설정 `fuel_snapshot_hour` (기본 9시).
    해당 시각 이전 요청은 스냅샷을 저장하지 않고 대기한다.
    """
    from datetime import datetime
    history = _load_history()
    today_iso = date.today().isoformat()
    if today_iso in history:
        return history
    # 설정된 스냅샷 기준 시각 이전엔 당일 스냅샷 스킵
    try:
        from settings_store import get_settings
        snap_hour = int(get_settings().get("fuel_snapshot_hour", 9))
    except Exception:
        snap_hour = 9
    if datetime.now().hour < snap_hour:
        return history
    try:
        html = _fetch_knoc_html()
        parsed = _parse_knoc_today(html)
        if parsed.get("gasoline") or parsed.get("diesel"):
            # KNOC 페이지가 알려준 고시일자가 오늘이어야만 저장
            snap_date = parsed.get("date") or today_iso
            if snap_date == today_iso:
                history[snap_date] = {
                    "gasoline": parsed.get("gasoline"),
                    "diesel": parsed.get("diesel"),
                    "lpg": parsed.get("lpg"),
                    "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                _save_history(history)
    except Exception:
        pass
    return history


def _parse_knoc_today(html: str) -> dict:
    """KNOC 메인 '오늘의 유가' 파싱 → {gasoline, diesel, lpg, date}."""
    result = {"gasoline": None, "diesel": None, "lpg": None, "date": ""}
    # panel1-1=휘발유, panel1-2=자동차용경유, panel1-3=자동차용부탄(LPG)
    for m in _KNOC_PANEL_RE.finditer(html):
        panel_idx = m.group(1)
        block = m.group(2)
        price_m = _KNOC_PRICE_RE.search(block)
        if not price_m:
            continue
        try:
            price = float(price_m.group(1).replace(",", ""))
        except ValueError:
            continue
        if panel_idx == "1":
            result["gasoline"] = price
        elif panel_idx == "2":
            result["diesel"] = price
        elif panel_idx == "3":
            result["lpg"] = price
        if not result["date"]:
            dm = _KNOC_DATE_RE.search(block)
            if dm:
                result["date"] = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
    return result


def _parse_series(html: str) -> dict:
    """페트로넷 메인 HTML에서 주유소 판매 주간 유가 시리즈 파싱.

    Returns:
        { "labels": [...], "gasoline": [...], "diesel": [...] }
    """
    labels_m = _LABELS_RE.search(html)
    labels = []
    if labels_m:
        labels = [s.strip().strip("'\"") for s in labels_m.group(1).split(",")]

    gasoline = diesel = None
    for label, data_str in _DATASET_RE.findall(html):
        nums = [float(x.strip()) for x in data_str.split(",") if x.strip().replace(".", "").replace("-", "").isdigit()]
        if not nums:
            continue
        if label == "휘발유" and gasoline is None:
            gasoline = nums
        elif label == "경유" and diesel is None:
            diesel = nums
        if gasoline is not None and diesel is not None:
            break
    return {"labels": labels, "gasoline": gasoline or [], "diesel": diesel or []}


def _previous_weekday(d: date) -> date:
    """토(5)·일(6)이면 직전 금요일로 이동."""
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _week_of_month(d: date) -> int:
    """월 내 주차 계산 (1일~7일=1주, 8~14=2주, ...)."""
    return math.ceil(d.day / 7)


def _label_for_date(d: date) -> str:
    """날짜 → "M.W" 라벨 (페트로넷 포맷)."""
    return f"{d.month}.{_week_of_month(d)}"


def _get_html_cached() -> str:
    key = "html"
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _TTL_SECONDS:
        return hit[1]["html"]
    html = _fetch_html()
    _CACHE[key] = (now, {"html": html})
    return html


def fetch_latest_prices() -> FuelPriceResult:
    """KNOC '오늘의 유가' 최신값. 첫 호출 시 히스토리에 자동 스냅샷 저장."""
    history = _snapshot_today_if_needed()
    if not history:
        raise ValueError("유가 데이터가 없습니다.")
    # 가장 최신 날짜 엔트리
    latest_date = sorted(history.keys())[-1]
    entry = history[latest_date]
    return FuelPriceResult(
        gasoline=entry.get("gasoline"),
        diesel=entry.get("diesel"),
        week_label=latest_date,
        target_date=latest_date,
        source=SOURCE_NAME,
    )


def _label_key(label: str) -> int:
    """'4.3' → 403 형태 정렬키. 연도 경계는 호출부에서 보정."""
    try:
        m, w = label.split(".")
        return int(m) * 100 + int(w)
    except Exception:
        return -1


def _find_matching_label_idx(target: date, labels: list) -> int:
    """target 일자에 맞는 라벨 인덱스. 정확 매칭 실패 시 '<=target 중 가장 큰' 라벨 선택.
    라벨 순서는 오래된 → 최신. 연도 경계(예: 12월 → 1월) 처리.
    """
    if not labels:
        return -1
    target_key = target.month * 100 + _week_of_month(target)
    # 라벨 시퀀스에서 월이 감소하면 '전년도'로 간주해 보정
    # 최근(뒤쪽)부터 순회하며 target_key 이하인 첫 라벨 찾기
    year_offset = 0
    prev_month = None
    # 우선 뒤에서부터 훑어 연도 경계 없이 매칭 시도
    for i in range(len(labels) - 1, -1, -1):
        k = _label_key(labels[i])
        if k <= target_key and k >= target.month * 100:
            return i  # 같은 월 또는 이전 주
        if k <= target_key:
            return i  # 다른 월이지만 이전 시점
    # 모두 target 보다 뒤면(데이터가 target 이후밖에 없음) 가장 앞 라벨 사용
    return 0


class FuelPriceUnavailable(Exception):
    """기준일이 자동 조회 범위(최근 3일) 밖인 경우."""


def fetch_price_for_date(target: date) -> FuelPriceResult:
    """특정 일자 유가 — 히스토리 기반.

    1. 오늘 스냅샷이 없으면 KNOC에서 당일치 저장
    2. 주말 → 직전 금요일로 이동
    3. 해당 날짜가 히스토리에 있으면 반환
    4. 없으면 `FuelPriceUnavailable` (수기 입력 필요)
    5. 미래 일자도 마찬가지 불가
    """
    target = _previous_weekday(target)
    today = date.today()
    if target > today:
        raise FuelPriceUnavailable("미래 일자는 조회할 수 없습니다.")

    history = _snapshot_today_if_needed()
    target_iso = target.isoformat()
    if target_iso in history:
        entry = history[target_iso]
        return FuelPriceResult(
            gasoline=entry.get("gasoline"),
            diesel=entry.get("diesel"),
            week_label=target_iso,
            target_date=target_iso,
            source=SOURCE_NAME,
        )
    raise FuelPriceUnavailable(
        f"기준일({target_iso}) 유가 데이터가 히스토리에 없습니다. "
        "이 날짜 이전부터 시스템이 운용되지 않았거나, 해당일이 공휴일일 수 있습니다. "
        "유가 칸에 수기 입력해 주세요."
    )


def get_history() -> dict:
    """저장된 전체 유가 히스토리 반환."""
    return _load_history()


def backfill_day(target_date: str, gasoline: float, diesel: float, lpg: float = None):
    """특정 날짜의 유가를 수동으로 히스토리에 추가/수정 (관리자용)."""
    history = _load_history()
    history[target_date] = {
        "gasoline": gasoline,
        "diesel": diesel,
        "lpg": lpg,
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "manual": True,
    }
    _save_history(history)
    return history[target_date]
