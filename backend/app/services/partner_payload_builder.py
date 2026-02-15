from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

from app.core.config import settings
from app.services.document_rules import normalize_document


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


def _parse_ddmmyyyy(value: str) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        return None


def _fmt_ddmmyyyy(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _future_test_dates(date_from_raw: str, date_to_raw: str, days_raw: Any) -> Tuple[str, str]:
    """
    Test platform rejects past dates.
    In test mode, auto-shift past dates to near future to keep integration flow testable.
    """
    parsed_from = _parse_ddmmyyyy(date_from_raw)
    parsed_to = _parse_ddmmyyyy(date_to_raw)
    today = date.today()

    try:
        days_int = int(days_raw or 0)
    except (TypeError, ValueError):
        days_int = 0
    trip_days = max(days_int, 1)

    if parsed_from and parsed_from > today and parsed_to and parsed_to > parsed_from:
        return date_from_raw, date_to_raw

    # Temporary test fallback: move departure to ближайшую будущую дату.
    shifted_from = today + timedelta(days=2)
    shifted_to = shifted_from + timedelta(days=trip_days - 1)
    return _fmt_ddmmyyyy(shifted_from), _fmt_ddmmyyyy(shifted_to)


def _resolve_override(overrides: Dict[str, Any], key: str, fallback: str) -> str:
    value = overrides.get(key)
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _pilgrim_meta(row: Dict[str, Any]) -> Dict[str, str]:
    return {
        "surname": str(row.get("surname") or "").strip(),
        "name": str(row.get("name") or "").strip(),
        "document": normalize_document(str(row.get("document") or "").strip()),
    }


def _build_clients_input_prod(matched: List[Dict[str, Any]]) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for idx, row in enumerate(matched):
        surname = (row.get("surname") or "").strip().upper()
        name = (row.get("name") or "").strip().upper()
        doc = normalize_document((row.get("document") or "").strip().upper())
        client_name = settings.DISPATCH_CLIENT_NAME_TEMPLATE or f"Client_{idx + 1}"

        data[f"c_name_{idx}"] = client_name
        data[f"c_nmeng_{idx}"] = surname or name or f"CLIENT_{idx + 1}"
        data[f"c_borned_{idx}"] = settings.DISPATCH_DEFAULT_BIRTH_DATE
        data[f"c_doc_type_{idx}"] = settings.DISPATCH_DEFAULT_DOC_TYPE
        data[f"c_doc_number_{idx}"] = doc
        data[f"c_doc_production_{idx}"] = settings.DISPATCH_DEFAULT_DOC_PRODUCTION
        data[f"c_doc_date_{idx}"] = settings.DISPATCH_DEFAULT_DOC_DATE
        data[f"c_bin_{idx}"] = ""
        data[f"c_sex_{idx}"] = ""
        data[f"c_address_{idx}"] = ""
        data[f"c_resident_{idx}"] = settings.DISPATCH_DEFAULT_RESIDENT
        data[f"c_rnn_{idx}"] = ""
        data[f"c_phone2_{idx}"] = ""
        data[f"c_cellphone2_{idx}"] = ""

    data["clientcounter"] = str(max(len(matched) - 1, 0))
    return data


def _build_clients_input_test(matched: List[Dict[str, Any]]) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for idx, row in enumerate(matched):
        doc = normalize_document((row.get("document") or "").strip().upper())
        client_name = settings.DISPATCH_CLIENT_NAME_TEMPLATE or f"Client_{idx + 1}"

        data[f"c_name_{idx}"] = client_name
        data[f"c_borned_{idx}"] = settings.DISPATCH_DEFAULT_BIRTH_DATE
        data[f"c_doc_date_{idx}"] = settings.DISPATCH_DEFAULT_DOC_DATE
        data[f"c_doc_number_{idx}"] = doc
        data[f"c_doc_production_{idx}"] = settings.DISPATCH_DEFAULT_DOC_PRODUCTION

    data["clientcounter"] = str(max(len(matched) - 1, 0))
    return data


def _build_save_form_base_prod(snapshot: Dict[str, Any]) -> Dict[str, str]:
    tour = snapshot.get("tour") or {}
    selection = snapshot.get("selection") or {}
    dispatch_overrides = snapshot.get("dispatch_overrides") or {}
    if not isinstance(dispatch_overrides, dict):
        dispatch_overrides = {}

    route = (tour.get("route") or selection.get("flight") or "").strip()
    airport_start, airport_end = _split_route(route)
    country = (selection.get("country") or "").strip()

    return {
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


def _build_input_base_test(snapshot: Dict[str, Any]) -> Dict[str, str]:
    tour = snapshot.get("tour") or {}
    selection = snapshot.get("selection") or {}
    dispatch_overrides = snapshot.get("dispatch_overrides") or {}
    if not isinstance(dispatch_overrides, dict):
        dispatch_overrides = {}

    route = (tour.get("route") or selection.get("flight") or "").strip()
    airport_start, airport_end = _split_route(route)
    country = (selection.get("country") or "").strip()

    date_from_raw = (tour.get("date_start") or "").strip()
    date_to_raw = (tour.get("date_end") or "").strip()
    days_raw = tour.get("days") or 0
    date_from, date_to = _future_test_dates(date_from_raw, date_to_raw, days_raw)

    return {
        "q_touragent": _resolve_override(dispatch_overrides, "q_touragent", settings.DISPATCH_TOURAGENT_NAME),
        "q_touragent_bin": _resolve_override(dispatch_overrides, "q_touragent_bin", settings.DISPATCH_TOURAGENT_BIN),
        "q_country": country,
        "q_countryen": _country_en(country),
        "q_airport_start": airport_start,
        "q_airlines": settings.DISPATCH_DEFAULT_AIRLINE,
        "q_airport": airport_end,
        "q_date_from": date_from,
        "q_date_to": date_to,
        "q_days": int(days_raw or 0),
        "q_remark": (selection.get("remark") or "").strip(),
    }


def _build_json_envelope_test(single_input: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "input": single_input,
        "module": settings.DISPATCH_MODULE,
        "section": settings.DISPATCH_SECTION,
        "object": settings.DISPATCH_OBJECT,
        "param1": settings.DISPATCH_PARAM1,
        "param2": settings.DISPATCH_PARAM2,
        "formid": int(settings.DISPATCH_FORM_ID),
        "agentlogin": settings.DISPATCH_AGENT_LOGIN,
        "agentpass": settings.DISPATCH_AGENT_PASS,
        "return": settings.DISPATCH_RETURN_FIELD,
    }


def build_partner_payload(snapshot: Dict[str, Any], mode: str = "test") -> Dict[str, Any]:
    results = snapshot.get("results") or {}
    matched = results.get("matched") or []
    if not isinstance(matched, list):
        matched = []

    if mode == "prod":
        base_form = _build_save_form_base_prod(snapshot)
        save_items: List[Dict[str, Any]] = []
        for index, pilgrim in enumerate(matched):
            if not isinstance(pilgrim, dict):
                continue
            save_form = dict(base_form)
            save_form.update(_build_clients_input_prod([pilgrim]))  # 1 pilgrim per request
            save_items.append(
                {
                    "index": index,
                    "save": save_form,
                    "meta": _pilgrim_meta(pilgrim),
                }
            )

        auth_form = {
            "agentlogin": settings.DISPATCH_AGENT_LOGIN,
            "agentpass": settings.DISPATCH_AGENT_PASS,
            "jump2": settings.DISPATCH_AUTH_JUMP2,
            "submit": settings.DISPATCH_AUTH_SUBMIT,
        }
        return {"auth": auth_form, "save_items": save_items}

    # test mode (default): POST JSON to target URL
    base_input = _build_input_base_test(snapshot)
    json_items: List[Dict[str, Any]] = []
    for index, pilgrim in enumerate(matched):
        if not isinstance(pilgrim, dict):
            continue

        single_input: Dict[str, Any] = dict(base_input)
        single_input.update(_build_clients_input_test([pilgrim]))  # 1 pilgrim per request
        payload = _build_json_envelope_test(single_input)
        json_items.append(
            {
                "index": index,
                "payload": payload,
                "meta": _pilgrim_meta(pilgrim),
            }
        )

    return {"json_items": json_items}
