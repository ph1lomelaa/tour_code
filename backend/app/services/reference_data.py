"""
Чтение справочников из раздела «Настройки» для бэкенд-логики (маршруты,
города вылета, английские названия стран).

Если БД недоступна или справочник пуст, используются значения, которые были
зашиты в код до появления «Настроек» (db/seed_reference.py) — отправка
тур-кодов не должна ломаться из-за справочников.
"""
from __future__ import annotations

import logging
import time
from typing import Dict, List, Tuple

from db.seed_reference import COUNTRIES, ROUTES

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30
_cache: Dict[str, Tuple[float, object]] = {}

_FALLBACK_COUNTRY_EN = {
    **dict(COUNTRIES),
    # Туры, сохранённые до перехода на полное название из справочника.
    "ОАЭ": "United Arab Emirates",
}


def invalidate_cache() -> None:
    _cache.clear()


def _cached(key: str, loader):
    now = time.monotonic()
    hit = _cache.get(key)
    if hit and now - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]
    value = loader()
    _cache[key] = (now, value)
    return value


def _load_routes() -> Dict[str, str]:
    try:
        from db.models import RefRoute
        from db.setup import SessionLocal

        with SessionLocal() as db:
            rows = (
                db.query(RefRoute.code, RefRoute.departure_city)
                .filter(RefRoute.is_active.is_(True))
                .all()
            )
        if rows:
            return {code.upper(): city for code, city in rows}
    except Exception as exc:
        logger.warning("ref_routes unavailable, using built-in routes: %s", exc)
    return dict(ROUTES)


def _load_country_en() -> Dict[str, str]:
    mapping = dict(_FALLBACK_COUNTRY_EN)
    try:
        from db.models import RefCountry
        from db.setup import SessionLocal

        # Неактивные тоже: старый тур с удалённой страной должен отправиться корректно.
        with SessionLocal() as db:
            rows = db.query(RefCountry.name_ru, RefCountry.name_en).all()
        mapping.update({ru: en for ru, en in rows if en})
    except Exception as exc:
        logger.warning("ref_countries unavailable, using built-in countries: %s", exc)
    return mapping


def route_departure_cities() -> Dict[str, str]:
    return _cached("routes", _load_routes)


def route_codes() -> List[str]:
    # Длинные маршруты первыми, чтобы "ALA-DOH-JED" не перехватывался более коротким.
    return sorted(route_departure_cities(), key=len, reverse=True)


def departure_city(route: str) -> str:
    return route_departure_cities().get((route or "").upper(), "") or "Не указан"


def country_en(country_ru: str) -> str:
    text = (country_ru or "").strip()
    if not text:
        return ""
    return _cached("country_en", _load_country_en).get(text, text)
