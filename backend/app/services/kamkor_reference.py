"""
Проверка значений справочников («Настройки») по справочникам Камкора.

Форма заявки на Камкоре — это автокомплиты, которые ищут значения в
справочниках партнёрской системы:
    GET /Voucher/partner/dictionaries/get/<source>?is_ajax=1&w=<текст>&param=<колонка>
    → {"dictname": ..., "variants": [{...}, ...]}  (пустой ответ = ничего не найдено)

Поле формы      source          колонка   на Камкоре
q_airlines      airlines        iata      список, свои значения принимаются (THY проходит)
q_country       countries       country   только из справочника
q_airport*      airports        iata      только из справочника
q_touragent     portal_agents   bin       реестр турагентов РК
q_hotel         hotels          name      можно вводить своё (addnew)

Сессия Камкора привязана к User-Agent: все запросы должны идти с тем же
User-Agent, что и вход (auth_headers()).

Проверить вручную:
    python -m app.services.kamkor_reference airlines TK
    python -m app.services.kamkor_reference touragents 080340019818
"""
from __future__ import annotations

import difflib
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import httpx

from app.core.config import settings
from app.services.dispatch_auth import auth_headers, auth_payload, authenticate

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 600
_cache: Dict[Tuple[str, str, str], Tuple[float, List[Dict[str, Any]]]] = {}


class KamkorUnavailable(RuntimeError):
    pass


# ── БИН ──────────────────────────────────────────────────

def bin_is_valid(value: str) -> bool:
    """Контрольный разряд ИИН/БИН РК: веса 1..11, при остатке 10 — 3..11,1,2."""
    digits = (value or "").strip()
    if len(digits) != 12 or not digits.isdigit():
        return False
    nums = [int(d) for d in digits]
    for weights in (range(1, 12), [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]):
        control = sum(n * w for n, w in zip(nums[:11], weights)) % 11
        if control != 10:
            return control == nums[11]
    return False


# ── Справочники Камкора ──────────────────────────────────

class KamkorDictionaries:
    """Одна авторизованная сессия на время проверки."""

    def __init__(self) -> None:
        if not settings.DISPATCH_AUTH_URL:
            raise KamkorUnavailable("DISPATCH_AUTH_URL не настроен")
        self._dict_url = urljoin(settings.DISPATCH_AUTH_URL, "/Voucher/partner/dictionaries/get/")
        self._client: Optional[httpx.Client] = None

    def _session(self) -> httpx.Client:
        if self._client is None:
            headers = auth_headers()
            client = httpx.Client(
                timeout=30,
                follow_redirects=True,
                headers={"User-Agent": headers["User-Agent"]},
            )
            try:
                authenticate(
                    client,
                    settings.DISPATCH_AUTH_URL,
                    auth_payload(settings.DISPATCH_AGENT_LOGIN, settings.DISPATCH_AGENT_PASS),
                    headers,
                )
            except Exception as exc:
                client.close()
                raise KamkorUnavailable(f"не удалось войти на Камкор: {exc}") from exc
            self._client = client
        return self._client

    def lookup(self, source: str, column: str, text: str) -> List[Dict[str, Any]]:
        key = (source, column, text.casefold())
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < _CACHE_TTL_SECONDS:
            return hit[1]
        try:
            response = self._session().get(
                self._dict_url + source,
                params={"is_ajax": "1", "w": text, "param": column},
            )
            response.raise_for_status()
        except KamkorUnavailable:
            raise
        except Exception as exc:
            raise KamkorUnavailable(f"справочник {source} недоступен: {exc}") from exc

        body = (response.text or "").strip()
        variants: List[Dict[str, Any]] = []
        if body:
            try:
                data = json.loads(body)
            except ValueError as exc:
                raise KamkorUnavailable(f"неожиданный ответ справочника {source}: {body[:100]}") from exc
            if isinstance(data, dict) and data.get("account") == 0:
                raise KamkorUnavailable("сессия Камкора не авторизована")
            variants = [v for v in (data.get("variants") or []) if isinstance(v, dict)] if isinstance(data, dict) else []
        _cache[key] = (time.monotonic(), variants)
        return variants

    def close(self) -> None:
        if self._client is not None:
            self._client.close()


# ── Проверка значений ────────────────────────────────────

def _result(
    status: str,
    message: str,
    suggestions: Optional[List[str]] = None,
    extra: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    return {"status": status, "message": message, "suggestions": suggestions or [], "extra": extra or {}}


def _exact(variants: List[Dict[str, Any]], column: str, value: str) -> Optional[Dict[str, Any]]:
    needle = value.strip().casefold()
    for variant in variants:
        if str(variant.get(column) or "").strip().casefold() == needle:
            return variant
    return None


def _suggest(
    kd: KamkorDictionaries, source: str, column: str, value: str, label, variants: List[Dict[str, Any]]
) -> List[str]:
    """Похожие значения: то, что Камкор вернул на запрос, иначе — поиск по первым буквам."""
    candidates = list(variants)
    if not candidates and len(value) > 2:
        candidates = kd.lookup(source, column, value[:2])
    labels = list(dict.fromkeys(label(v) for v in candidates if v.get(column)))
    if len(labels) <= 5:
        return labels
    by_casefold = {item.casefold(): item for item in labels}
    close = difflib.get_close_matches(value.casefold(), list(by_casefold), n=5, cutoff=0.3)
    return [by_casefold[key] for key in close] or labels[:5]


def _verify_airline(kd: KamkorDictionaries, data: Dict[str, Any]) -> Dict[str, Any]:
    code = str(data.get("code") or "").strip().upper()
    variants = kd.lookup("airlines", "iata", code)
    found = _exact(variants, "iata", code)
    if found:
        return _result("found", f"Код {code} есть на Камкоре: {found.get('airline') or found.get('companyname') or ''}".strip(),
                       extra={"name": str(found.get("airline") or "")})
    # Камкор ищет по началу значения: «THY» находит «THY - Turkish Airlines»,
    # «Qatar» — «Qatar Airways».
    by_name = kd.lookup("airlines", "airline", code)
    name = str(data.get("name") or "").strip()
    if name and name.casefold() != code.casefold():
        by_name += kd.lookup("airlines", "airline", name)
    suggestions = _suggest(kd, "airlines", "iata", code, lambda v: f"{v.get('iata')} — {v.get('airline', '')}",
                           by_name + variants)
    # Свои значения в q_airlines Камкор не отклоняет (заявка с «THY» создаётся),
    # но в справочнике их нет — предупреждаем и предлагаем код IATA.
    return _result("not_found", f"Кода «{code}» нет в справочнике авиалиний Камкора. Заявку Камкор примет, "
                                "но правильнее указать код IATA из справочника", suggestions)


def _verify_country(kd: KamkorDictionaries, data: Dict[str, Any]) -> Dict[str, Any]:
    name = str(data.get("name_ru") or "").strip()
    variants = kd.lookup("countries", "country", name)
    found = _exact(variants, "country", name)
    if found:
        return _result("found", f"Страна «{name}» есть на Камкоре ({found.get('countryen', '')})",
                       extra={"name_en": str(found.get("countryen") or "")})
    suggestions = _suggest(kd, "countries", "country", name, lambda v: str(v.get("country")), variants)
    return _result("not_found", f"Страны «{name}» нет в справочнике Камкора — Камкор такую заявку не примет",
                   suggestions)


def _route_airports(data: Dict[str, Any]) -> List[str]:
    return [p.strip() for p in str(data.get("code") or "").upper().split("-") if p.strip()]


def _verify_route(kd: KamkorDictionaries, data: Dict[str, Any]) -> Dict[str, Any]:
    names = []
    for code in _route_airports(data):
        variants = kd.lookup("airports", "iata", code)
        found = _exact(variants, "iata", code)
        if not found:
            suggestions = _suggest(kd, "airports", "iata", code,
                                   lambda v: f"{v.get('iata')} — {v.get('airport_en') or v.get('airport', '')}", variants)
            return _result("not_found", f"Аэропорта {code} нет в справочнике Камкора", suggestions)
        names.append(f"{code} ({found.get('airport_en') or found.get('airport') or found.get('country', '')})")
    return _result("found", "Аэропорты есть на Камкоре: " + ", ".join(names))


def _verify_touragent(kd: KamkorDictionaries, data: Dict[str, Any]) -> Dict[str, Any]:
    bin_value = str(data.get("bin") or "").strip()
    variants = kd.lookup("portal_agents", "bin", bin_value)
    found = _exact(variants, "bin", bin_value)
    if not found:
        return _result("not_found", f"Турагента с БИН {bin_value} нет в реестре турагентов Камкора")
    orgname = str(found.get("orgname") or "")
    return _result("found", f"БИН {bin_value} есть в реестре Камкора: «{orgname}»", extra={"name": orgname})


def _verify_hotel(kd: KamkorDictionaries, data: Dict[str, Any]) -> Dict[str, Any]:
    name = str(data.get("name") or "").strip()
    if _exact(kd.lookup("hotels", "name", name), "name", name):
        return _result("found", f"Отель «{name}» есть в справочнике Камкора")
    return _result("unchecked", "Отеля нет в справочнике Камкора, но поле отеля на Камкоре принимает любое название")


_VERIFIERS = {
    "airlines": _verify_airline,
    "countries": _verify_country,
    "routes": _verify_route,
    "touragents": _verify_touragent,
    "hotels": _verify_hotel,
}


def _format_error(entity: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Ошибки формата проверяются без Камкора — их нельзя пропускать даже если он недоступен."""
    if entity == "touragents":
        bin_value = str(data.get("bin") or "").strip()
        if not bin_is_valid(bin_value):
            return _result("invalid", f"БИН «{bin_value}» неверный: нужно 12 цифр с правильной контрольной цифрой")
    if entity == "routes":
        airports = _route_airports(data)
        if len(airports) < 2 or any(len(a) != 3 or not a.isalpha() for a in airports):
            return _result("invalid", "Маршрут должен быть вида ALA-JED или ALA-DOH-JED (коды IATA из 3 букв)")
    return None


def verify(entity: str, data: Dict[str, Any]) -> Dict[str, Any]:
    verifier = _VERIFIERS.get(entity)
    if verifier is None:
        return _result("unchecked", "Для этого справочника проверка не предусмотрена")
    error = _format_error(entity, data)
    if error:
        return error
    try:
        kd = KamkorDictionaries()
    except KamkorUnavailable as exc:
        return _result("unchecked", f"Камкор недоступен, проверка пропущена: {exc}")
    try:
        return verifier(kd, data)
    except KamkorUnavailable as exc:
        logger.warning("Kamkor verification skipped for %s: %s", entity, exc)
        return _result("unchecked", f"Камкор недоступен, проверка пропущена: {exc}")
    finally:
        kd.close()


# ── Аккаунты входа (.env) ────────────────────────────────

def kamkor_accounts() -> List[Dict[str, str]]:
    return [
        {"key": "hikmet", "label": "Хикмет Travel", "login": settings.DISPATCH_AGENT_LOGIN,
         "password": settings.DISPATCH_AGENT_PASS},
        {"key": "almarwa", "label": "AL-MARWA", "login": settings.DISPATCH_AGENT_LOGIN_ALMARWA,
         "password": settings.DISPATCH_AGENT_PASS_ALMARWA},
    ]


def check_accounts() -> List[Dict[str, Any]]:
    results = []
    for account in kamkor_accounts():
        item: Dict[str, Any] = {"key": account["key"], "label": account["label"], "login": account["login"]}
        if not account["login"] or not account["password"]:
            item.update(ok=False, error="Логин или пароль не заданы в .env")
            results.append(item)
            continue
        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                authenticate(client, settings.DISPATCH_AUTH_URL,
                             auth_payload(account["login"], account["password"]), auth_headers())
            item.update(ok=True, error="")
        except Exception as exc:
            item.update(ok=False, error=str(exc))
        results.append(item)
    return results


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.WARNING)
    if len(sys.argv) < 3:
        sys.exit("usage: python -m app.services.kamkor_reference <airlines|countries|routes|touragents|hotels> <value>")
    entity, value = sys.argv[1], sys.argv[2]
    field = {"airlines": "code", "countries": "name_ru", "routes": "code", "touragents": "bin", "hotels": "name"}[entity]
    print(json.dumps(verify(entity, {field: value}), ensure_ascii=False, indent=2))
