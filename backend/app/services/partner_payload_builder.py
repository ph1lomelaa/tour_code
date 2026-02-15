from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

from app.core.config import settings


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
    test.fondkamkor rejects past dates.
    In test mode, shift invalid/past dates to near future.
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

    shifted_from = today + timedelta(days=2)
    shifted_to = shifted_from + timedelta(days=trip_days - 1)
    return _fmt_ddmmyyyy(shifted_from), _fmt_ddmmyyyy(shifted_to)


def _to_clean_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_days(value: Any, fallback: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 0
    if parsed > 0:
        return parsed
    return max(int(fallback or 0), 0)


def _tour_text(snapshot_tour: Dict[str, Any], tour_db: Any, key: str, fallback: str = "") -> str:
    db_value = _to_clean_str(getattr(tour_db, key, "")) if tour_db is not None else ""
    if db_value:
        return db_value

    snapshot_value = _to_clean_str(snapshot_tour.get(key))
    if snapshot_value:
        return snapshot_value

    return fallback


def _tour_days(snapshot_tour: Dict[str, Any], tour_db: Any) -> int:
    db_value = getattr(tour_db, "days", None) if tour_db is not None else None
    if db_value is not None:
        parsed_db = _coerce_days(db_value)
        if parsed_db > 0:
            return parsed_db

    parsed_snapshot = _coerce_days(snapshot_tour.get("days"))
    if parsed_snapshot > 0:
        return parsed_snapshot

    return _coerce_days(settings.DISPATCH_DEFAULT_DAYS)


def _resolve_agent_credentials(mode: str) -> Tuple[str, str]:
    mode_normalized = (mode or "").strip().lower()
    if mode_normalized == "prod":
        login = _to_clean_str(settings.DISPATCH_PROD_AGENT_LOGIN) or _to_clean_str(settings.DISPATCH_AGENT_LOGIN)
        password = _to_clean_str(settings.DISPATCH_PROD_AGENT_PASS) or _to_clean_str(settings.DISPATCH_AGENT_PASS)
        return login, password

    login = _to_clean_str(settings.DISPATCH_TEST_AGENT_LOGIN) or _to_clean_str(settings.DISPATCH_AGENT_LOGIN)
    password = _to_clean_str(settings.DISPATCH_TEST_AGENT_PASS) or _to_clean_str(settings.DISPATCH_AGENT_PASS)
    return login, password


def _build_input_base(snapshot: Dict[str, Any], mode: str, tour_db: Any) -> Dict[str, Any]:
    tour = snapshot.get("tour") if isinstance(snapshot.get("tour"), dict) else {}
    selection = snapshot.get("selection") if isinstance(snapshot.get("selection"), dict) else {}

    route = _tour_text(tour, tour_db, "route")
    if not route:
        route = _to_clean_str(selection.get("flight"))
    airport_start, airport_end = _split_route(route)
    airport_start = airport_start or settings.DISPATCH_DEFAULT_AIRPORT_START
    airport_end = airport_end or settings.DISPATCH_DEFAULT_AIRPORT

    q_airlines = _tour_text(tour, tour_db, "airlines", settings.DISPATCH_DEFAULT_AIRLINE)
    q_date_from = _tour_text(tour, tour_db, "date_start", settings.DISPATCH_DEFAULT_DATE_FROM)
    q_date_to = _tour_text(tour, tour_db, "date_end", settings.DISPATCH_DEFAULT_DATE_TO)
    q_days = _tour_days(tour, tour_db)

    if (mode or "").strip().lower() == "test":
        q_date_from, q_date_to = _future_test_dates(q_date_from, q_date_to, q_days)

    return {
        # Defaults from settings: do not derive from DB/user snapshot
        "q_touragent": settings.DISPATCH_TOURAGENT_NAME,
        "q_touragent_bin": settings.DISPATCH_TOURAGENT_BIN,
        "q_country": settings.DISPATCH_DEFAULT_COUNTRY,
        "q_countryen": settings.DISPATCH_DEFAULT_COUNTRY_EN,
        "q_remark": settings.DISPATCH_DEFAULT_REMARK,
        # Values sourced from tour data (DB/snapshot)
        "q_airport_start": airport_start,
        "q_airlines": q_airlines,
        "q_airport": airport_end,
        "q_date_from": q_date_from,
        "q_date_to": q_date_to,
        "q_days": q_days,
    }


def _pilgrim_meta(row: Dict[str, Any]) -> Dict[str, str]:
    return {
        "surname": _to_clean_str(row.get("surname")),
        "name": _to_clean_str(row.get("name")),
        "document": _to_clean_str(row.get("document")),
    }


def _build_single_client_input(row: Dict[str, Any]) -> Dict[str, Any]:
    doc_number = _to_clean_str(row.get("document")).upper() or settings.DISPATCH_DEFAULT_DOC_NUMBER
    return {
        # One pilgrim per request
        "clientcounter": 0,
        # Defaults from settings
        "c_name_0": settings.DISPATCH_CLIENT_NAME_TEMPLATE,
        "c_borned_0": settings.DISPATCH_DEFAULT_BIRTH_DATE,
        "c_doc_date_0": settings.DISPATCH_DEFAULT_DOC_DATE,
        "c_doc_production_0": settings.DISPATCH_DEFAULT_DOC_PRODUCTION,
        # Value sourced from tour participant
        "c_doc_number_0": doc_number,
    }


def _build_json_envelope(single_input: Dict[str, Any], mode: str) -> Dict[str, Any]:
    agent_login, agent_pass = _resolve_agent_credentials(mode)
    return {
        "input": single_input,
        "module": settings.DISPATCH_MODULE,
        "section": settings.DISPATCH_SECTION,
        "object": settings.DISPATCH_OBJECT,
        "param1": settings.DISPATCH_PARAM1,
        "param2": settings.DISPATCH_PARAM2,
        "formid": int(settings.DISPATCH_FORM_ID),
        "agentlogin": agent_login,
        "agentpass": agent_pass,
        "return": settings.DISPATCH_RETURN_FIELD,
    }


def build_partner_payload(snapshot: Dict[str, Any], mode: str = "test", tour_db: Any = None) -> Dict[str, Any]:
    results = snapshot.get("results") if isinstance(snapshot.get("results"), dict) else {}
    matched = results.get("matched") if isinstance(results.get("matched"), list) else []

    base_input = _build_input_base(snapshot, mode=mode, tour_db=tour_db)
    json_items: List[Dict[str, Any]] = []
    for index, pilgrim in enumerate(matched):
        if not isinstance(pilgrim, dict):
            continue

        single_input = dict(base_input)
        single_input.update(_build_single_client_input(pilgrim))
        payload = _build_json_envelope(single_input, mode=mode)
        json_items.append(
            {
                "index": index,
                "payload": payload,
                "meta": _pilgrim_meta(pilgrim),
            }
        )

    return {"json_items": json_items}
