from __future__ import annotations

from typing import Tuple


def route_endpoints(route: str) -> Tuple[str, str]:
    """Return the first and last IATA codes from a route such as ALA-DOH-JED."""
    airports = [part.strip() for part in (route or "").upper().split("-") if part.strip()]
    if len(airports) < 2:
        return "", ""
    return airports[0], airports[-1]
