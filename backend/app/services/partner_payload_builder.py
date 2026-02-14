
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.core.config import settings


COUNTRY_EN_MAP = {
    "Саудовская Аравия": "Saudi Arabia",
}


def _country_en(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return COUNTRY_EN_MAP.get(text, text)


def _split_route(route: str) -> Tuple[str, str]:
    raw = (route or "").strip().upper()
    if "-" not in raw:
        return "", ""
    left, right = raw.split("-", 1)
    return left.strip(), right.strip()


def _build_clients_input(matched: List[Dict[str, Any]]) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for idx, row in enumerate(matched):
        surname = (row.get("surname") or "").strip().upper()
        name = (row.get("name") or "").strip().upper()
        doc = (row.get("document") or "").strip().upper()
        client_name = settings.DISPATCH_CLIENT_NAME_TEMPLATE or f"Client_{idx + 1}"

        data[f"c_name_{idx}"] = client_name
        # В прод-формате это поле передаём только фамилией (латиница/верхний регистр).
        data[f"c_nmeng_{idx}"] = surname or name or f"CLIENT_{idx + 1}"
        data[f"c_borned_{idx}"] = settings.DISPATCH_DEFAULT_BIRTH_DATE
        data[f"c_doc_type_{idx}"] = settings.DISPATCH_DEFAULT_DOC_TYPE
        data[f"c_doc_number_{idx}"] = doc
        data[f"c_doc_production_{idx}"] = settings.DISPATCH_DEFAULT_DOC_PRODUCTION
        data[f"c_doc_date_{idx}"] = ""
        data[f"c_bin_{idx}"] = ""
        data[f"c_sex_{idx}"] = ""
        data[f"c_address_{idx}"] = ""
        data[f"c_resident_{idx}"] = settings.DISPATCH_DEFAULT_RESIDENT
        data[f"c_rnn_{idx}"] = ""
        data[f"c_phone2_{idx}"] = ""
        data[f"c_cellphone2_{idx}"] = ""

    data["clientcounter"] = str(max(len(matched) - 1, 0))
    return data


def _build_auth_form() -> Dict[str, str]:
    return {
        "agentlogin": settings.DISPATCH_AGENT_LOGIN,
        "agentpass": settings.DISPATCH_AGENT_PASS,
        "jump2": settings.DISPATCH_AUTH_JUMP2,
        "submit": settings.DISPATCH_AUTH_SUBMIT,
    }


def _resolve_override(overrides: Dict[str, Any], key: str, fallback: str) -> str:
    value = overrides.get(key)
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _build_save_form_base(snapshot: Dict[str, Any]) -> Dict[str, str]:
    tour = snapshot.get("tour") or {}
    selection = snapshot.get("selection") or {}
    dispatch_overrides = snapshot.get("dispatch_overrides") or {}
    if not isinstance(dispatch_overrides, dict):
        dispatch_overrides = {}

    route = (tour.get("route") or selection.get("flight") or "").strip()
    airport_start, airport_end = _split_route(route)
    country = (selection.get("country") or "").strip()
    save_form: Dict[str, str] = {
        "filialid": _resolve_override(dispatch_overrides, "filialid", settings.DISPATCH_FILIAL_ID),
        "firmid": _resolve_override(dispatch_overrides, "firmid", settings.DISPATCH_FIRM_ID),
        "firmname": _resolve_override(dispatch_overrides, "firmname", settings.DISPATCH_FIRM_NAME),
        "q_internal": settings.DISPATCH_Q_INTERNAL,
        "q_cost": "",
        "q_agent_assign": settings.DISPATCH_Q_AGENT_ASSIGN,
        "q_tourist_phone": "",
        "q_currency": settings.DISPATCH_Q_CURRENCY,
        "q_number": settings.DISPATCH_Q_NUMBER_TEMPLATE,
        "q_short_number": "",
        "q_countryen": _country_en(country),
        "q_pretk": "",
        "q_touragent_bin": _resolve_override(dispatch_overrides, "q_touragent_bin", settings.DISPATCH_TOURAGENT_BIN),
        "q_touragent": _resolve_override(dispatch_overrides, "q_touragent", settings.DISPATCH_TOURAGENT_NAME),
        "q_date_from": (tour.get("date_start") or "").strip(),
        "q_date_to": (tour.get("date_end") or "").strip(),
        "q_days": str(int(tour.get("days") or 0)),
        "q_airlines": settings.DISPATCH_DEFAULT_AIRLINE,
        "q_airport_start": airport_start,
        "q_airport": airport_end,
        "q_flight": "",
        "q_flight_from": "",
        "q_country": country,
        "q_hotel": (selection.get("hotel") or "").strip(),
        "q_remark": (selection.get("remark") or "").strip(),
        "q_profit_type": "",
        "q_profit": "",
        "q_start_commission": "",
        "offercounter": str(settings.DISPATCH_OFFER_COUNTER),
        "formid": str(settings.DISPATCH_FORM_ID),
    }
    return save_form


def build_partner_payload(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    results = snapshot.get("results") or {}
    matched = results.get("matched") or []
    if not isinstance(matched, list):
        matched = []

    base_form = _build_save_form_base(snapshot)
    save_items: List[Dict[str, Any]] = []
    for index, pilgrim in enumerate(matched):
        if not isinstance(pilgrim, dict):
            continue

        save_form = dict(base_form)
        save_form.update(_build_clients_input([pilgrim]))  # 1 pilgrim per request
        save_items.append(
            {
                "index": index,
                "save": save_form,
                "meta": {
                    "surname": str(pilgrim.get("surname") or "").strip(),
                    "name": str(pilgrim.get("name") or "").strip(),
                    "document": str(pilgrim.get("document") or "").strip(),
                },
            }
        )

    return {
        "auth": _build_auth_form(),
        "save_items": save_items,
    }
