
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


def _build_clients_input(matched: List[Dict[str, Any]]) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for idx, row in enumerate(matched):
        surname = (row.get("surname") or "").strip()
        name = (row.get("name") or "").strip()
        doc = (row.get("document") or "").strip()
        full_name = f"{surname} {name}".strip()

        data[f"c_name_{idx}"] = full_name or f"Client_{idx + 1}"
        data[f"c_doc_number_{idx}"] = doc

    data["clientcounter"] = max(len(matched) - 1, 0)
    return data


def _build_offers_input(tour: Dict[str, Any], selection: Dict[str, Any]) -> Dict[str, Any]:
    route = (tour.get("route") or selection.get("flight") or "").strip().upper()
    dep_airport, arr_airport = _split_route(route)
    if not dep_airport or not arr_airport:
        return {}

    country = (selection.get("country") or "").strip()
    country_en = _country_en(country)
    airline = settings.DISPATCH_DEFAULT_AIRLINE
    date_start = (tour.get("date_start") or "").strip()
    date_end = (tour.get("date_end") or "").strip()

    data: Dict[str, Any] = {}

    # Offer 0: outbound (dep → arr)
    data["offertype_0"] = "flight"
    data["o_date_from_0"] = date_start
    data["o_date_to_0"] = date_start
    data["o_airlines_0"] = airline
    data["o_airport_0"] = arr_airport
    data["o_country_0"] = country_en

    # Offer 1: return (arr → dep)
    data["offertype_1"] = "flight"
    data["o_date_from_1"] = date_end
    data["o_date_to_1"] = date_end
    data["o_airlines_1"] = airline
    data["o_airport_1"] = dep_airport
    data["o_country_1"] = "Kazakhstan"

    data["offercounter"] = 1  # последний индекс
    return data


def build_partner_payload(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    tour = snapshot.get("tour") or {}
    selection = snapshot.get("selection") or {}
    results = snapshot.get("results") or {}
    matched = results.get("matched") or []

    route = (tour.get("route") or selection.get("flight") or "").strip().upper()
    airport_start, airport_end = _split_route(route)
    country = (selection.get("country") or "").strip()

    payload_input: Dict[str, Any] = {
        "q_touragent": settings.DISPATCH_TOURAGENT_NAME,
        "q_touragent_bin": settings.DISPATCH_TOURAGENT_BIN,
        "q_country": country,
        "q_countryen": _country_en(country),
        "q_airport_start": airport_start,
        "q_airlines": settings.DISPATCH_DEFAULT_AIRLINE,
        "q_airport": airport_end,
        "q_date_from": (tour.get("date_start") or "").strip(),
        "q_date_to": (tour.get("date_end") or "").strip(),
        "q_days": int(tour.get("days") or 0),
        "q_remark": (selection.get("remark") or "").strip(),
    }
    payload_input.update(_build_clients_input(matched))
    payload_input.update(_build_offers_input(tour, selection))

    return {
        "input": payload_input,
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
