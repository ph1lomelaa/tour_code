from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.core.config import settings
from app.services.document_rules import normalize_document


COUNTRY_EN_MAP = {
    "Саудовская Аравия": "Saudi Arabia",
}


def _drop_empty_values(values: Dict[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, str) and value == "":
            continue
        cleaned[key] = value
    return cleaned


def _resolve_touragent(snapshot: Dict[str, Any]) -> Tuple[str, str]:
    overrides = snapshot.get("dispatch_overrides") or {}
    if not isinstance(overrides, dict):
        overrides = {}

    default_name = (settings.DISPATCH_TOURAGENT_NAME or "").strip()
    default_bin = (settings.DISPATCH_TOURAGENT_BIN or "").strip()

    override_name = str(overrides.get("q_touragent") or "").strip()
    override_bin = str(overrides.get("q_touragent_bin") or "").strip()

    # HICKMET preset is protected: always use backend-configured values.
    normalized_name = override_name.upper()
    if (
        not override_name
        or normalized_name in {"HICKMET", "HICKMET PREMIUM", default_name.upper()}
    ):
        return default_name, default_bin

    # Any non-HICKMET value from frontend is allowed.
    return override_name, override_bin


def _resolve_company(snapshot: Dict[str, Any]) -> Tuple[str, str, str]:
    overrides = snapshot.get("dispatch_overrides") or {}
    if not isinstance(overrides, dict):
        overrides = {}

    filialid = str(overrides.get("filialid") or "").strip() or str(settings.DISPATCH_FILIAL_ID or "").strip()
    firmid = str(overrides.get("firmid") or "").strip() or str(settings.DISPATCH_FIRM_ID or "").strip()
    firmname = str(overrides.get("firmname") or "").strip() or str(settings.DISPATCH_FIRM_NAME or "").strip()
    return filialid, firmid, firmname


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


def _build_base_input(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    tour = snapshot.get("tour") or {}
    selection = snapshot.get("selection") or {}
    q_touragent, q_touragent_bin = _resolve_touragent(snapshot)
    filialid, firmid, firmname = _resolve_company(snapshot)

    route = (tour.get("route") or selection.get("flight") or "").strip()
    airport_start, airport_end = _split_route(route)
    country = (selection.get("country") or "").strip()

    q_date_from = (tour.get("date_start") or "").strip()
    q_date_to = (tour.get("date_end") or "").strip()

    return {
        "filialid": filialid,
        "firmid": firmid,
        "firmname": firmname,
        "q_internal": str(settings.DISPATCH_Q_INTERNAL),
        "q_cost": "",
        "q_agent_assign": str(settings.DISPATCH_Q_AGENT_ASSIGN),
        "q_tourist_phone": "",
        "q_currency": str(settings.DISPATCH_Q_CURRENCY),
        "q_number": str(settings.DISPATCH_Q_NUMBER_TEMPLATE),
        "q_short_number": "",
        "q_pretk": "",
        "q_touragent": q_touragent,
        "q_touragent_bin": q_touragent_bin,
        "q_country": country,
        "q_countryen": _country_en(country),
        "q_airlines": settings.DISPATCH_DEFAULT_AIRLINE,
        "q_airport_start": airport_start,
        "q_airport": airport_end,
        "q_date_from": q_date_from,
        "q_date_to": q_date_to,
        "q_days": str(int(tour.get("days") or 0)),
        "q_flight": "",
        "q_flight_from": "",
        "q_hotel": (selection.get("hotel") or "").strip(),
        "q_remark": (selection.get("remark") or "").strip(),
        "q_profit_type": "",
        "q_profit": "",
        "q_start_commission": "",
        "offercounter": str(settings.DISPATCH_OFFER_COUNTER),
        "formid": str(settings.DISPATCH_FORM_ID),
    }


def _build_client_block(pilgrim: Dict[str, Any]) -> Dict[str, Any]:
    doc = normalize_document((pilgrim.get("document") or "").strip().upper())
    surname = str(pilgrim.get("surname") or "").strip().upper()

    return {
        "clientcounter": 0,
        "c_name_0": settings.DISPATCH_CLIENT_NAME_TEMPLATE,
        "c_nmeng_0": surname,
        "c_borned_0": settings.DISPATCH_DEFAULT_BIRTH_DATE,
        "c_doc_type_0": settings.DISPATCH_DEFAULT_DOC_TYPE,
        "c_doc_date_0": settings.DISPATCH_DEFAULT_DOC_DATE,
        "c_doc_number_0": doc,
        "c_doc_production_0": settings.DISPATCH_DEFAULT_DOC_PRODUCTION,
        "c_bin_0": "",
        "c_sex_0": "",
        "c_address_0": "",
        "c_resident_0": settings.DISPATCH_DEFAULT_RESIDENT,
        "c_rnn_0": "",
        "c_phone2_0": "",
        "c_cellphone2_0": "",
    }


def _build_json_envelope(single_input: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "input": single_input,
        "module": settings.DISPATCH_MODULE,
        "section": settings.DISPATCH_SECTION,
        "object": settings.DISPATCH_OBJECT,
        "param1": settings.DISPATCH_PARAM1,
        "param2": settings.DISPATCH_PARAM2,
        "formid": settings.DISPATCH_FORM_ID,
        "agentlogin": settings.DISPATCH_AGENT_LOGIN,
        "agentpass": settings.DISPATCH_AGENT_PASS,
        "return": settings.DISPATCH_RETURN_FIELD,
    }


def build_partner_payload(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    results = snapshot.get("results") or {}
    matched = results.get("matched") or []
    if not isinstance(matched, list):
        matched = []

    base_input = _build_base_input(snapshot)
    json_items: List[Dict[str, Any]] = []
    for index, pilgrim in enumerate(matched):
        if not isinstance(pilgrim, dict):
            continue

        normalized_document = normalize_document(str(pilgrim.get("document") or "").strip())
        if not normalized_document:
            # Skip invalid/empty passport numbers to avoid partner-side mandatory-field errors.
            continue

        single_input = dict(base_input)
        single_input.update(_build_client_block({**pilgrim, "document": normalized_document}))
        json_items.append(
            {
                "index": index,
                "payload": single_input,
                "meta": {
                    "pilgrim_id": str(pilgrim.get("pilgrim_id") or "").strip(),
                    "surname": str(pilgrim.get("surname") or "").strip(),
                    "name": str(pilgrim.get("name") or "").strip(),
                    "document": normalized_document,
                },
            }
        )

    result: Dict[str, Any] = {
        "mode": "partner_form",
        "json_items": json_items,
        "auth": {
            "url": settings.DISPATCH_AUTH_URL,
            "payload": {
                "agentlogin": settings.DISPATCH_AGENT_LOGIN,
                "agentpass": settings.DISPATCH_AGENT_PASS,
                "jump2": settings.DISPATCH_AUTH_JUMP2,
                "submit": settings.DISPATCH_AUTH_SUBMIT,
            },
        },
        "save": {
            "url": settings.DISPATCH_SAVE_URL,
        },
    }

    return result
