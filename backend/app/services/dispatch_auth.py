"""
Авторизация во внешней системе (report.fondkamkor.kz) для отправки тур-кодов.
"""
from __future__ import annotations

from typing import Dict
import logging
import re

import httpx

logger = logging.getLogger(__name__)


class DispatchAuthError(RuntimeError):
    """Внешняя система не выдала сессию. retryable=False — повтор бессмысленен
    (неверный логин/пароль, аккаунт заблокирован)."""

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


_CREDENTIAL_ERROR_MARKERS = (
    "invalid username or password",
    "имя пользователя или пароль",
    "неверный логин",
    "неверный пароль",
    "неправильный логин",
    "неправильный пароль",
    "логин или пароль",
    "заблокирован",
    "blocked",
)


def _page_text(html: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_login_form(html: str) -> bool:
    return 'name="agentpass"' in (html or "") or "name='agentpass'" in (html or "")


def authenticate(client: httpx.Client, auth_url: str, auth_payload: Dict[str, str], headers: Dict[str, str]) -> str:
    """Логинится и возвращает значение cookie tsagent."""
    response = client.post(auth_url, data=auth_payload, headers=headers, cookies={"lg": "ru"})
    if response.status_code >= 400:
        raise DispatchAuthError(f"Auth HTTP {response.status_code}: {response.text[:500]}")

    # Cookie может прийти на промежуточном редиректе — тогда он только в jar клиента.
    tsagent = response.cookies.get("tsagent") or client.cookies.get("tsagent")
    if tsagent:
        return tsagent

    html = response.text or ""
    page_text = _page_text(html)
    # Страница ошибки повторяет введённый пароль — не пишем его в лог.
    password = str(auth_payload.get("agentpass") or "")
    if password:
        page_text = page_text.replace(password, "***")
    logger.warning(
        "Dispatch auth: no tsagent cookie; login=%s final_url=%s history=%s cookies=%s page=%r",
        auth_payload.get("agentlogin"),
        response.url,
        [(r.status_code, str(r.url)) for r in response.history],
        list(client.cookies.keys()),
        page_text[:1500],
    )

    lowered = page_text.lower()
    if any(marker in lowered for marker in _CREDENTIAL_ERROR_MARKERS):
        raise DispatchAuthError("Auth failed: Invalid credentials", retryable=False)
    if _is_login_form(html):
        # Сайт снова показал форму входа — логин не принят.
        raise DispatchAuthError("Auth failed: Invalid credentials (login form returned)", retryable=False)
    raise DispatchAuthError("Auth failed: tsagent cookie was not set")


if __name__ == "__main__":
    # Проверка логина без отправки данных:
    #   python -m app.services.dispatch_auth            # аккаунт по умолчанию (Хикмет)
    #   python -m app.services.dispatch_auth almarwa    # аккаунт AL-MARWA
    import sys

    from app.core.config import settings

    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) > 1 and sys.argv[1].lower() == "almarwa":
        login, password = settings.DISPATCH_AGENT_LOGIN_ALMARWA, settings.DISPATCH_AGENT_PASS_ALMARWA
    else:
        login, password = settings.DISPATCH_AGENT_LOGIN, settings.DISPATCH_AGENT_PASS

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": settings.DISPATCH_USER_AGENT,
    }
    if settings.DISPATCH_ORIGIN:
        headers["Origin"] = settings.DISPATCH_ORIGIN
    if settings.DISPATCH_AUTH_REFERER:
        headers["Referer"] = settings.DISPATCH_AUTH_REFERER

    payload = {
        "agentlogin": login,
        "agentpass": password,
        "jump2": settings.DISPATCH_AUTH_JUMP2,
        "submit": settings.DISPATCH_AUTH_SUBMIT,
    }
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        try:
            authenticate(client, settings.DISPATCH_AUTH_URL, payload, headers)
        except DispatchAuthError as exc:
            print(f"FAIL ({login}): {exc} [retryable={exc.retryable}]")
            sys.exit(1)
    print(f"OK ({login}): tsagent cookie received")
