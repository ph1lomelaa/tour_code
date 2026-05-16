"""
Фоновая отправка данных тур-кода во внешний backend.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import logging
import re
from urllib.parse import urljoin, urlsplit

import httpx
from sqlalchemy import func

from app.queue.celery_app import celery_app
from app.core.config import settings
from db.setup import SessionLocal
from db.models import DispatchJob, DispatchJobStatus, Pilgrim
from app.services.partner_payload_builder import build_partner_payload
from app.services.document_rules import normalize_document

logger = logging.getLogger(__name__)


def _public_dispatch_error_message(raw_error: str) -> str:
    text = str(raw_error or "").strip()
    if not text:
        return "Отправка не завершилась. Проверьте данные и повторите попытку."

    lowered = text.lower()

    if "no pilgrims to dispatch" in lowered:
        return "Нет подтвержденных паломников для отправки."
    if "dispatch_auth_url is not configured" in lowered or "dispatch_save_url is not configured" in lowered:
        return "Не настроены параметры отправки. Нужна проверка сервера."
    if "invalid credentials" in lowered:
        return "Не удалось авторизоваться во внешней системе. Нужна проверка учетных данных."
    if "tsagent cookie was not set" in lowered or "unauthorized session" in lowered:
        return "Внешняя система не подтвердила сессию. Повторите отправку позже."
    if lowered.startswith("auth http"):
        return "Внешняя система не приняла авторизацию. Повторите попытку позже."
    if lowered.startswith("http "):
        return "Внешняя система временно недоступна. Повторите попытку позже."
    if lowered.startswith("view http"):
        return "Заявка создана, но подтверждение от внешней системы прочиталось не полностью."

    return text


def _build_failed_items_message(failed_items: int, total_items: int, failure_reasons: list[str]) -> str:
    if not failure_reasons:
        return (
            f"Не удалось завершить отправку для {failed_items} из {total_items} записей. "
            "Проверьте данные и повторите попытку."
        )

    reason_counts: Dict[str, int] = {}
    for reason in failure_reasons:
        public_reason = _public_dispatch_error_message(reason)
        reason_counts[public_reason] = reason_counts.get(public_reason, 0) + 1

    top_reason, top_count = max(reason_counts.items(), key=lambda x: x[1])
    return (
        f"Не удалось завершить отправку для {failed_items} из {total_items} записей. "
        f"Чаще всего: {top_reason}"
        + (f" ({top_count})" if top_count > 1 else "")
    )


TOUR_CODE_MAX_LENGTH = 64


def _is_valid_tour_code(candidate: str) -> bool:
    if not candidate:
        return False
    if "tmpl_var" in candidate:
        return False
    if "[" in candidate or "]" in candidate:
        return False
    if candidate.lower().startswith("base64:"):
        return False
    if len(candidate) > TOUR_CODE_MAX_LENGTH:
        return False
    return True


def _extract_tour_code(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        status_value = payload.get("status")
        if status_value is not None:
            try:
                if int(status_value) != 200:
                    return ""
            except (TypeError, ValueError):
                return ""

        raw_value = payload.get("string")
        if raw_value is not None:
            candidate = str(raw_value).strip()
            if _is_valid_tour_code(candidate):
                return candidate

    text = response.text or ""

    # Common partner HTML form pattern: <input name="q_number" value="...">
    html_field = re.search(
        r'name=["\']q_number["\'][^>]*value=["\']([^"\']+)["\']',
        text,
        re.IGNORECASE,
    )
    if html_field:
        candidate = html_field.group(1).strip()
        if _is_valid_tour_code(candidate):
            return candidate

    # Pattern for span/div with id="q_number": <span id="q_number">CODE</span>
    span_field = re.search(
        r'<(?:span|div)[^>]*id=["\']q_number["\'][^>]*>([^<]+)</',
        text,
        re.IGNORECASE,
    )
    if span_field:
        candidate = span_field.group(1).strip()
        if _is_valid_tour_code(candidate):
            return candidate

    js_field = re.search(r'"q_number"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
    if js_field:
        candidate = js_field.group(1).strip()
        if _is_valid_tour_code(candidate):
            return candidate

    has_ok_status = re.search(r'"status"\s*:\s*"?200"?', text)
    match = re.search(r'"string"\s*:\s*"([^"]+)"', text)
    if has_ok_status and match:
        candidate = match.group(1).strip()
        if _is_valid_tour_code(candidate):
            return candidate

    # Fallback for HTML responses where code is embedded in page content.
    # Updated pattern to match formats like: NOR82Sa60224-18948731, 12AB12345-123, etc
    code_match = re.search(r"\b[A-Z]{2,3}\d{2}[A-Za-z]{1,2}\d{5,6}-\d+\b", text)
    if code_match:
        candidate = code_match.group(0).strip()
        if _is_valid_tour_code(candidate):
            return candidate

    # Fallback for legacy responses where only `string` is present.
    match = re.search(r'"string"\s*:\s*"([^"]+)"', text)
    if match:
        candidate = match.group(1).strip()
        if _is_valid_tour_code(candidate):
            return candidate

    return ""


def _extract_business_error(response: httpx.Response) -> Optional[str]:
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        status_value = payload.get("status")
        error_text = str(payload.get("string") or "").strip()
        try:
            if status_value is not None and int(status_value) != 200:
                return error_text or f"Business status={status_value}"
        except (TypeError, ValueError):
            if error_text:
                return error_text

    text = response.text or ""

    fatal = re.search(r"FatalError:\s*(.+?)</div>", text, re.IGNORECASE | re.DOTALL)
    if fatal:
        raw = fatal.group(1)
        normalized = re.sub(r"<[^>]+>", " ", raw)
        normalized = " ".join(normalized.split())
        if normalized:
            return normalized

    text_status = re.search(r'"status"\s*:\s*"?(\d+)"?', text)
    text_message = re.search(r'"string"\s*:\s*"([^"]+)"', text)
    if text_status and text_message:
        try:
            if int(text_status.group(1)) != 200:
                return text_message.group(1).strip()
        except (TypeError, ValueError):
            return text_message.group(1).strip()

    return None


def _extract_created_query_id(response: httpx.Response) -> str:
    text = response.text or ""

    # Typical partner_form success:
    # ... operation=op_query_created,262876 ...
    created_match = re.search(r"operation=op_query_created,(\d+)", text, re.IGNORECASE)
    if created_match:
        return created_match.group(1).strip()

    view_match = re.search(r"/queries/(\d+)/view", text, re.IGNORECASE)
    if view_match:
        return view_match.group(1).strip()

    return ""


def _build_query_view_url(save_url: str, query_id: str) -> str:
    if not save_url or not query_id:
        return ""

    parsed = urlsplit(save_url)
    if not parsed.scheme or not parsed.netloc:
        return ""

    return f"{parsed.scheme}://{parsed.netloc}/Voucher/partner/queries/{query_id}/view"


def _extract_meta_refresh_url(response: httpx.Response) -> str:
    text = response.text or ""

    # <META HTTP-EQUIV="refresh" CONTENT="0; URL=/path">
    meta = re.search(
        r'<meta[^>]*http-equiv=["\']?refresh["\']?[^>]*content=["\'][^"\']*url=([^"\'>]+)',
        text,
        re.IGNORECASE,
    )
    if not meta:
        return ""

    return meta.group(1).strip()


def _follow_meta_refresh(
    client: httpx.Client,
    response: httpx.Response,
    headers: Dict[str, str],
    max_hops: int = 3,
) -> httpx.Response:
    current = response
    visited: set[str] = set()

    for _ in range(max_hops):
        next_url = _extract_meta_refresh_url(current)
        if not next_url:
            break

        resolved = urljoin(str(current.url), next_url)
        if not resolved or resolved in visited:
            break

        visited.add(resolved)
        current = client.get(resolved, headers=headers)

    return current


def _find_pilgrim(
    db,
    tour_id: str | None,
    item_meta: Dict[str, Any],
) -> Pilgrim | None:
    if not tour_id:
        return None

    pilgrim_id = str(item_meta.get("pilgrim_id") or "").strip()
    if pilgrim_id:
        by_id = (
            db.query(Pilgrim)
            .filter(Pilgrim.id == pilgrim_id, Pilgrim.tour_id == tour_id)
            .first()
        )
        if by_id:
            return by_id

    document = normalize_document(str(item_meta.get("document") or "").strip().upper())
    if document:
        by_document = (
            db.query(Pilgrim)
            .filter(
                Pilgrim.tour_id == tour_id,
                func.upper(func.trim(func.coalesce(Pilgrim.document, ""))) == document,
            )
            .first()
        )
        if by_document:
            return by_document

        by_document_global = (
            db.query(Pilgrim)
            .filter(func.upper(func.trim(func.coalesce(Pilgrim.document, ""))) == document)
            .order_by(Pilgrim.created_at.asc())
            .first()
        )
        if by_document_global:
            return by_document_global

    surname = str(item_meta.get("surname") or "").strip().upper()
    name = str(item_meta.get("name") or "").strip().upper()
    if not surname and not name:
        return None

    query = db.query(Pilgrim).filter(Pilgrim.tour_id == tour_id)
    if surname:
        query = query.filter(Pilgrim.surname == surname)
    if name:
        query = query.filter(Pilgrim.name == name)

    return query.order_by(Pilgrim.created_at.asc()).first()


def _save_tour_code_for_item(
    db,
    tour_id: str | None,
    item_meta: Dict[str, Any],
    tour_code: str,
) -> None:
    if not tour_code:
        return

    pilgrim = _find_pilgrim(db, tour_id=tour_id, item_meta=item_meta)
    if pilgrim is None:
        logger.warning(
            "Tour code received but pilgrim not found: tour_id=%s, meta=%s, tour_code=%s",
            tour_id,
            item_meta,
            tour_code,
        )
        return

    pilgrim.tour_code = tour_code


def _build_auth_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": settings.DISPATCH_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if settings.DISPATCH_ORIGIN:
        headers["Origin"] = settings.DISPATCH_ORIGIN
    if settings.DISPATCH_AUTH_REFERER:
        headers["Referer"] = settings.DISPATCH_AUTH_REFERER
    return headers


def _build_save_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": settings.DISPATCH_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if settings.DISPATCH_ORIGIN:
        headers["Origin"] = settings.DISPATCH_ORIGIN
    if settings.DISPATCH_SAVE_REFERER:
        headers["Referer"] = settings.DISPATCH_SAVE_REFERER
    return headers


def _build_view_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {
        "User-Agent": settings.DISPATCH_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if settings.DISPATCH_ORIGIN:
        headers["Origin"] = settings.DISPATCH_ORIGIN
    if settings.DISPATCH_SAVE_REFERER:
        headers["Referer"] = settings.DISPATCH_SAVE_REFERER
    return headers


def _is_guest_page(text: str) -> bool:
    raw = (text or "").lower()
    if not raw:
        return False
    # Check for actual guest status, not logout links
    return "logged as:guest" in raw or "@ guest" in raw


@celery_app.task(bind=True, name="dispatch.process_job", max_retries=5)
def process_dispatch_job(self, job_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        job = db.get(DispatchJob, job_id)
        if job is None:
            return {"ok": False, "error": "job_not_found", "job_id": job_id}

        if job.status == DispatchJobStatus.SENT:
            return {"ok": True, "job_id": job_id, "status": job.status.value}

        job.status = DispatchJobStatus.SENDING
        job.attempt_count += 1
        job.last_attempt_at = datetime.utcnow()
        db.commit()

        prepared = build_partner_payload(job.payload)
        json_items = prepared.get("json_items") or []
        if not json_items:
            raise RuntimeError("No pilgrims to dispatch")

        mode = "partner_form"
        auth_data = (prepared.get("auth") or {}) if isinstance(prepared.get("auth"), dict) else {}
        save_data = (prepared.get("save") or {}) if isinstance(prepared.get("save"), dict) else {}

        responses: list[Dict[str, Any]] = []
        total_items = len(json_items)
        failed_items = 0

        job.prepared_payload = prepared
        job.response_payload = {
            "mode": mode,
            "stage": "prepare",
            "json_items_total": total_items,
            "json_items_sent": 0,
            "progress": {
                "total_items": total_items,
                "sent_items": 0,
            },
        }
        db.commit()

        with httpx.Client(timeout=settings.DISPATCH_REQUEST_TIMEOUT_SECONDS, follow_redirects=True) as client:
            auth_url = str(auth_data.get("url") or settings.DISPATCH_AUTH_URL).strip()
            save_url = str(save_data.get("url") or settings.DISPATCH_SAVE_URL).strip()
            auth_payload = auth_data.get("payload") if isinstance(auth_data.get("payload"), dict) else {}
            if not auth_payload:
                auth_payload = {
                    "agentlogin": settings.DISPATCH_AGENT_LOGIN,
                    "agentpass": settings.DISPATCH_AGENT_PASS,
                    "jump2": settings.DISPATCH_AUTH_JUMP2,
                    "submit": settings.DISPATCH_AUTH_SUBMIT,
                }

            if not auth_url:
                raise RuntimeError("DISPATCH_AUTH_URL is not configured")
            if not save_url:
                raise RuntimeError("DISPATCH_SAVE_URL is not configured")

            # Use explicit cookies like in working version
            auth_cookies = {"lg": "ru"}
            auth_response = client.post(
                auth_url,
                data=auth_payload,
                headers=_build_auth_headers(),
                cookies=auth_cookies
            )
            if auth_response.status_code >= 400:
                raise RuntimeError(f"Auth HTTP {auth_response.status_code}: {auth_response.text[:500]}")

            # Check for auth errors in response body
            auth_text = auth_response.text or ""
            if "Invalid username or password" in auth_text:
                raise RuntimeError("Auth failed: Invalid credentials in .env file")

            # Extract tsagent from response cookies
            tsagent = None
            for cookie in auth_response.cookies.jar:
                if cookie.name == "tsagent":
                    tsagent = cookie.value
                    break

            if not tsagent:
                raise RuntimeError("Auth failed: tsagent cookie was not set")

            logger.info("Dispatch auth succeeded, session cookie received")

            job.response_payload = {
                "mode": mode,
                "stage": "auth",
                "auth_url": auth_url,
                "save_url": save_url,
                "auth_status_code": auth_response.status_code,
                "json_items_total": total_items,
                "json_items_sent": 0,
                "progress": {
                    "total_items": total_items,
                    "sent_items": 0,
                },
            }
            db.commit()
            save_headers = _build_save_headers()
            save_cookies = {"lg": "ru", "tsagent": tsagent}

            for item in json_items:
                idx = int(item.get("index") or 0)
                payload = item.get("payload") or {}

                # DEBUG: Log cookies for first save request
                if idx == 0:
                    logger.info("Dispatch save request initialized")

                response = client.post(save_url, data=payload, headers=save_headers, cookies=save_cookies)

                if response.status_code >= 400:
                    raise RuntimeError(f"HTTP {response.status_code}: {response.text}")

                item_meta = item.get("meta") or {}
                business_error = _extract_business_error(response)

                # DEBUG: Check if guest page for first item
                if idx == 0:
                    is_guest = _is_guest_page(response.text or "")
                    logger.info("Dispatch response received, guest page=%s", is_guest)

                if not business_error and _is_guest_page(response.text or ""):
                    business_error = "Unauthorized session (guest)"
                item_error_message = business_error
                created_query_id = ""
                query_view_url = ""
                query_view_status_code: Optional[int] = None
                query_view_text = ""

                # Код из ответа /save не читаем — там лежит невычисленный шаблон.
                # Настоящий код достаём только из /view (см. ниже).
                tour_code = ""
                if not business_error:
                    created_query_id = _extract_created_query_id(response)
                    if created_query_id:
                        query_view_url = _build_query_view_url(save_url, created_query_id)
                        if query_view_url:
                            query_view_headers = _build_view_headers()
                            query_view_response = client.get(query_view_url, headers=query_view_headers)
                            query_view_response = _follow_meta_refresh(
                                client,
                                query_view_response,
                                headers=query_view_headers,
                            )

                            query_view_status_code = query_view_response.status_code
                            query_view_text = (query_view_response.text or "")[:4000]
                            if query_view_response.status_code < 400:
                                tour_code = _extract_tour_code(query_view_response) or tour_code
                            else:
                                item_error_message = (
                                    item_error_message
                                    or f"View HTTP {query_view_response.status_code}"
                                )

                if created_query_id and not tour_code and not item_error_message:
                    logger.warning(
                        "Query created without q_number in view response: tour_id=%s, query_id=%s, meta=%s",
                        str(job.tour_id) if job.tour_id else None,
                        created_query_id,
                        item_meta,
                    )

                # Заявка считается успешно зарегистрированной у партнёра, если:
                #   - HTTP 200 (нет сетевой ошибки)
                #   - нет business_error в теле ответа
                #   - страница не "guest" (сессия валидна)
                # query_id может быть невычисляемым из ответа (партнёр меняет формат),
                # но это НЕ повод считать заявку неуспешной — она реально создана.
                save_request_succeeded = (
                    response.status_code < 400
                    and not business_error
                )

                if tour_code:
                    _save_tour_code_for_item(
                        db,
                        tour_id=str(job.tour_id) if job.tour_id else None,
                        item_meta=item_meta,
                        tour_code=tour_code,
                    )
                elif not save_request_succeeded:
                    failed_items += 1

                responses.append(
                    {
                        "index": idx,
                        "meta": item_meta,
                        "status_code": response.status_code,
                        "text": response.text[:4000],
                        "tour_code": tour_code,
                        "created_query_id": created_query_id,
                        "query_view_url": query_view_url,
                        "query_view_status_code": query_view_status_code,
                        "query_view_text": query_view_text,
                        "error_message": item_error_message,
                    }
                )

                job.response_payload = {
                    "mode": mode,
                    "stage": "sending",
                    "save_url": save_url,
                    "json_items_total": total_items,
                    "json_items_sent": len(responses),
                    "json_items_failed": failed_items,
                    "last_sent_index": idx,
                    "progress": {
                        "total_items": total_items,
                        "sent_items": len(responses),
                    },
                }
                db.commit()

        # Подсчёт исходов:
        #   completed  — тур-код получен и сохранён в БД паломнику
        #   registered — заявка ушла к партнёру (HTTP 200, без business_error),
        #                но код ещё не получен/не сгенерирован (типично: ждём оплаты,
        #                либо партнёр поменял формат ответа и query_id не достали)
        #   failed_items — заявка не дошла: HTTP-ошибка или business_error
        completed_count = sum(1 for r in responses if r.get("tour_code"))
        registered_count = sum(
            1 for r in responses
            if not r.get("tour_code")
            and (r.get("status_code") or 0) < 400
            and not (r.get("error_message") or "").strip()
        )

        if completed_count == 0 and registered_count == 0 and failed_items > 0:
            # Полный провал — ни одна запись не дошла до партнёра
            failure_reasons = [
                str(item.get("error_message") or "").strip()
                for item in responses
                if str(item.get("error_message") or "").strip()
            ]
            job.error_message = _build_failed_items_message(
                failed_items, total_items, failure_reasons
            )
            job.status = DispatchJobStatus.FAILED
            job.sent_at = None
        else:
            # Хотя бы часть записей дошла до партнёра — считаем отправку успешной,
            # детали показываем в error_message (фронт отрисует амбер-«warning»).
            job.status = DispatchJobStatus.SENT
            job.sent_at = datetime.utcnow()

            if completed_count == total_items:
                # Идеальный случай: все получили тур-коды
                job.error_message = None
            else:
                parts: list[str] = []
                if completed_count:
                    parts.append(
                        f"тур-коды получены для {completed_count} из {total_items}"
                    )
                if registered_count:
                    parts.append(
                        f"{registered_count} ожидают подтверждения от партнёра"
                    )
                if failed_items:
                    parts.append(
                        f"{failed_items} требуют проверки данных"
                    )
                job.error_message = "Отправлено. " + ", ".join(parts) + "."

        job.next_attempt_at = None
        job.response_payload = {
            "mode": mode,
            "stage": "finalize",
            "save_url": save_url,
            "json_items_total": total_items,
            "json_items_sent": len(responses),
            "json_items_failed": failed_items,
            "json_items": responses,
            "progress": {
                "total_items": total_items,
                "sent_items": len(responses),
            },
        }
        db.commit()

        return {
            "ok": job.status == DispatchJobStatus.SENT,
            "job_id": job_id,
            "status": job.status.value,
            "failed_items": failed_items,
            "total_items": total_items,
        }

    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            logger.exception("Failed to rollback session after dispatch error")
        job = db.get(DispatchJob, job_id)
        if job:
            technical_error = str(exc)[:2000]
            job.error_message = _public_dispatch_error_message(technical_error)
            logger.exception("Dispatch job failed: %s", technical_error)

            if job.attempt_count >= job.max_attempts:
                job.status = DispatchJobStatus.FAILED
                job.next_attempt_at = None
                db.commit()
                return {"ok": False, "job_id": job_id, "status": job.status.value, "error": job.error_message}

            retry_delay = settings.DISPATCH_RETRY_DELAY_SECONDS
            job.status = DispatchJobStatus.QUEUED
            job.next_attempt_at = datetime.utcnow() + timedelta(seconds=retry_delay)
            db.commit()
            raise self.retry(exc=exc, countdown=retry_delay)

        return {"ok": False, "job_id": job_id, "error": str(exc)}

    finally:
        db.close()
