"""사용자가 수정한 (상점명 → 카테고리) 매핑을 학습·저장.

- 저장 위치: learned_categories.json
- 조회 시 정확 일치 + 부분 일치 (소문자/공백 제거)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

STORE_PATH = Path(__file__).parent / "learned_categories.json"


def _normalize(name: str) -> str:
    return (name or "").strip().lower().replace(" ", "")


def _load() -> dict:
    if not STORE_PATH.exists():
        return {}
    try:
        with STORE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save(data: dict):
    try:
        with STORE_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def learn(merchant: str, category: str):
    """상점명과 카테고리 매핑을 저장."""
    if not merchant or not category:
        return
    data = _load()
    data[_normalize(merchant)] = {
        "merchant_original": merchant,
        "category": category,
    }
    _save(data)


def lookup(merchant: str) -> Optional[str]:
    """상점명으로 학습된 카테고리 찾기. 정확·부분 일치 모두 시도."""
    if not merchant:
        return None
    data = _load()
    key = _normalize(merchant)
    # 정확 일치
    if key in data:
        return data[key]["category"]
    # 부분 일치 (학습 키가 검색 상점명에 포함되거나 그 반대)
    for k, v in data.items():
        if k and (k in key or key in k):
            return v["category"]
    return None


def list_all() -> list:
    """학습된 모든 매핑 목록."""
    data = _load()
    return [{"merchant": v["merchant_original"], "category": v["category"]} for v in data.values()]


def delete(merchant: str):
    """특정 상점 학습 삭제."""
    data = _load()
    key = _normalize(merchant)
    if key in data:
        del data[key]
        _save(data)
