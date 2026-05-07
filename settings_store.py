"""회사 규정 설정 — settings.json 기반 런타임 수정 가능한 설정값.

- .env 값은 **기본값(initial default)** 로만 사용
- 실제 런타임 값은 settings.json 에 저장·조회 (서버 재시작 불필요)
- settings.json 이 없거나 비어있으면 .env 값으로 fallback
"""
from __future__ import annotations

import json
import os
from pathlib import Path

SETTINGS_PATH = Path(__file__).parent / "settings.json"

# 관리자 비밀번호 (env). 미설정 시 기본 "admin".
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

DEFAULT_KEYS = [
    ("meal_limit_per_person", "MEAL_LIMIT_PER_PERSON", 12000, int),
    ("lodging_limit_per_night", "LODGING_LIMIT_PER_NIGHT", 70000, int),
    ("overseas_meal_limit_per_person", "OVERSEAS_MEAL_LIMIT_PER_PERSON", 0, int),
    ("overseas_lodging_limit_per_night", "OVERSEAS_LODGING_LIMIT_PER_NIGHT", 0, int),
    # 'warn' | 'cap' — 해외 한도 초과 시 동작
    ("overseas_limit_action", "OVERSEAS_LIMIT_ACTION", "warn", str),
    # 국내 출장 일비
    ("trip_allowance_per_day", "TRIP_ALLOWANCE_PER_DAY", 30000, int),
    # 유가(원/L) — 관리자가 주간 고시 기준으로 수동 입력
    ("fuel_price_gasoline", "FUEL_PRICE_GASOLINE", 0, float),
    ("fuel_price_diesel", "FUEL_PRICE_DIESEL", 0, float),
    ("fuel_price_lpg", "FUEL_PRICE_LPG", 0, float),
]

# 해외 출장일비(지역/직급별) — 중첩 dict 구조라 DEFAULT_KEYS 와 별개로 관리
PER_DIEM_KEY = "per_diem_rates"
PER_DIEM_RANKS = ["exec", "gm", "dgm", "manager", "am", "sv", "staff"]
DEFAULT_PER_DIEM_RATES = {
    "A": {"name": "가 지역", "desc": "북미, 유럽, 일본, 중동 등", "rates": {
        "exec": {"fc": 150, "krw": 200000}, "gm": {"fc": 130, "krw": 170000},
        "dgm": {"fc": 110, "krw": 150000}, "manager": {"fc": 90, "krw": 120000},
        "am": {"fc": 80, "krw": 100000}, "sv": {"fc": 70, "krw": 90000},
        "staff": {"fc": 60, "krw": 80000},
    }},
    "B": {"name": "나 지역", "desc": "아시아, 오세아니아, 남미 등", "rates": {
        "exec": {"fc": 130, "krw": 170000}, "gm": {"fc": 110, "krw": 150000},
        "dgm": {"fc": 90, "krw": 120000}, "manager": {"fc": 80, "krw": 100000},
        "am": {"fc": 70, "krw": 90000}, "sv": {"fc": 60, "krw": 80000},
        "staff": {"fc": 50, "krw": 70000},
    }},
    "C": {"name": "다 지역", "desc": "기타 지역", "rates": {
        "exec": {"fc": 110, "krw": 150000}, "gm": {"fc": 90, "krw": 120000},
        "dgm": {"fc": 80, "krw": 100000}, "manager": {"fc": 70, "krw": 90000},
        "am": {"fc": 60, "krw": 80000}, "sv": {"fc": 50, "krw": 70000},
        "staff": {"fc": 40, "krw": 60000},
    }},
}


def _sanitize_per_diem(raw) -> dict:
    """저장된/입력된 per_diem 데이터를 정규 스키마로 정제."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, val in raw.items():
        if not isinstance(val, dict):
            continue
        rates_in = val.get("rates") if isinstance(val.get("rates"), dict) else {}
        rates_out = {}
        for rk in PER_DIEM_RANKS:
            r = rates_in.get(rk) or {}
            try:
                fc = float(r.get("fc") or 0)
            except Exception:
                fc = 0
            try:
                krw = float(r.get("krw") or 0)
            except Exception:
                krw = 0
            rates_out[rk] = {"fc": fc, "krw": krw}
        out[str(key)] = {
            "name": str(val.get("name") or key),
            "desc": str(val.get("desc") or ""),
            "rates": rates_out,
        }
    return out


def _load_file() -> dict:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _env_default(env_key: str, default, cast):
    raw = os.getenv(env_key)
    if raw is None or raw == "":
        return default
    try:
        return cast(raw)
    except Exception:
        return default


def get_settings() -> dict:
    """현재 유효 설정: settings.json 우선, 없으면 env/default."""
    file_settings = _load_file()
    out = {}
    for key, env_key, default, cast in DEFAULT_KEYS:
        if key in file_settings and file_settings[key] not in (None, ""):
            try:
                out[key] = cast(file_settings[key])
            except Exception:
                out[key] = _env_default(env_key, default, cast)
        else:
            out[key] = _env_default(env_key, default, cast)
    # 일비 기준 (중첩 dict) — 파일에 있으면 정제 후 사용, 없으면 기본값
    raw_pd = file_settings.get(PER_DIEM_KEY)
    pd = _sanitize_per_diem(raw_pd) if raw_pd else {}
    customized = bool(pd)
    out[PER_DIEM_KEY] = pd if customized else DEFAULT_PER_DIEM_RATES
    # 클라이언트 마이그레이션 판단용 — 서버에 실제 저장된 값인지 표시
    out["per_diem_rates_customized"] = customized
    return out


def save_settings(update: dict) -> dict:
    """부분 업데이트. 전달된 키만 덮어쓰고 settings.json 저장."""
    current = _load_file()
    allowed = {k for k, _, _, _ in DEFAULT_KEYS}
    cast_map = {k: cast for k, _, _, cast in DEFAULT_KEYS}
    for k, v in (update or {}).items():
        if k == PER_DIEM_KEY:
            # 일비 기준 — 전체 dict 통째로 교체 (지역 추가/삭제 반영)
            sanitized = _sanitize_per_diem(v)
            if sanitized:
                current[PER_DIEM_KEY] = sanitized
            continue
        if k not in allowed:
            continue
        if v is None or v == "":
            current.pop(k, None)
            continue
        try:
            current[k] = cast_map[k](v)
        except Exception:
            continue
    try:
        with SETTINGS_PATH.open("w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise RuntimeError(f"settings.json 저장 실패: {e}")
    return get_settings()
