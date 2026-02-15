from __future__ import annotations

from datetime import datetime, date
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


def _build_base_input(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    tour = snapshot.get("tour") or {}
    selection = snapshot.get("selection") or {}

    route = (tour.get("route") or selection.get("flight") or "").strip()
    airport_start, airport_end = _split_route(route)
    country = (selection.get("country") or "").strip()

    return {
        "q_touragent": settings.DISPATCH_TOURAGENT_NAME,
        "q_touragent_bin": settings.DISPATCH_TOURAGENT_BIN,
        "q_country": country,
        "q_countryen": _country_en(country),
        "q_airlines": settings.DISPATCH_DEFAULT_AIRLINE,
        "q_airport_start": airport_start,
        "q_airport": airport_end,
        "q_date_from": (tour.get("date_start") or "").strip(),
        "q_date_to": (tour.get("date_end") or "").strip(),
        "q_days": int(tour.get("days") or 0),
        "q_remark": "",
    }


def _build_client_block(pilgrim: Dict[str, Any]) -> Dict[str, Any]:
    doc = normalize_document((pilgrim.get("document") or "").strip().upper())

    return {
        "clientcounter": 0,
        "c_name_0": settings.DISPATCH_CLIENT_NAME_TEMPLATE,
        "c_borned_0": settings.DISPATCH_DEFAULT_BIRTH_DATE,
        "c_doc_date_0": settings.DISPATCH_DEFAULT_DOC_DATE,
        "c_doc_number_0": doc,
        "c_doc_production_0": settings.DISPATCH_DEFAULT_DOC_PRODUCTION,
    }


def _build_envelope(single_input: Dict[str, Any]) -> Dict[str, Any]:
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

        single_input = dict(base_input)
        single_input.update(_build_client_block(pilgrim))

        payload = _build_envelope(single_input)
        json_items.append(
            {
                "index": index,
                "payload": payload,
                "meta": {
                    "surname": str(pilgrim.get("surname") or "").strip(),
                    "name": str(pilgrim.get("name") or "").strip(),
                    "document": normalize_document(str(pilgrim.get("document") or "").strip()),
                },
            }
        )

    return {"json_items": json_items}
