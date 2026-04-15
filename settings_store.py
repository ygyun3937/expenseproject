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
    return out


def save_settings(update: dict) -> dict:
    """부분 업데이트. 전달된 키만 덮어쓰고 settings.json 저장."""
    current = _load_file()
    allowed = {k for k, _, _, _ in DEFAULT_KEYS}
    cast_map = {k: cast for k, _, _, cast in DEFAULT_KEYS}
    for k, v in (update or {}).items():
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
