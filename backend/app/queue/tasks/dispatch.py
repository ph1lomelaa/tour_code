"""
Фоновая отправка данных тур-кода во внешний backend.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict
import logging

import httpx

from app.queue.celery_app import celery_app
from app.core.config import settings
from db.setup import SessionLocal
from db.models import DispatchJob, DispatchJobStatus
from app.services.partner_payload_builder import build_partner_payload

logger = logging.getLogger(__name__)


def _truncate_text(text: str, max_len: int = 4000) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _safe_response_payload(response: httpx.Response) -> Dict[str, Any]:
    content_type = response.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "json": response.json(),
            }
        except ValueError:
            pass

    return {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "text": _truncate_text(response.text or ""),
    }


def _resolve_dispatch_urls() -> tuple[str, str]:
    auth_url = (settings.DISPATCH_AUTH_URL or "").strip()
    save_url = (settings.DISPATCH_SAVE_URL or settings.DISPATCH_TARGET_URL or "").strip()

    if not auth_url:
        raise RuntimeError("DISPATCH_AUTH_URL is not configured")
    if not save_url:
        raise RuntimeError("DISPATCH_SAVE_URL (or DISPATCH_TARGET_URL) is not configured")

    return auth_url, save_url


def _form_headers(referer: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": settings.DISPATCH_USER_AGENT,
        "Origin": settings.DISPATCH_ORIGIN,
        "Referer": referer,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


@celery_app.task(bind=True, name="dispatch.process_job", max_retries=100)
def process_dispatch_job(self, job_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        job = db.get(DispatchJob, job_id)
        if job is None:
            logger.error("Dispatch job not found: %s", job_id)
            return {"ok": False, "error": "job_not_found", "job_id": job_id}

        if job.status == DispatchJobStatus.SENT:
            return {"ok": True, "job_id": job_id, "status": job.status.value}

        job.status = DispatchJobStatus.SENDING
        job.attempt_count += 1
        job.last_attempt_at = datetime.utcnow()
        db.commit()

        prepared_payload = build_partner_payload(job.payload)
        job.prepared_payload = prepared_payload
        db.commit()

        if settings.DISPATCH_DRY_RUN:
            job.status = DispatchJobStatus.SENT
            job.sent_at = datetime.utcnow()
            job.next_attempt_at = None
            job.error_message = None
            job.response_payload = {
                "mode": "dry_run",
                "message": "Dispatch skipped. Payload prepared only.",
                "items_total": len(prepared_payload.get("save_items") or []),
            }
            db.commit()
            logger.info("🧪 Dispatch job dry-run prepared: %s", job_id)
            return {"ok": True, "job_id": job_id, "status": job.status.value, "dry_run": True}

        auth_form = prepared_payload.get("auth") or {}
        save_items = prepared_payload.get("save_items") or []
        if not isinstance(save_items, list):
            save_items = []
        if len(save_items) == 0:
            raise RuntimeError("No pilgrims to dispatch: save_items is empty")

        auth_url, save_url = _resolve_dispatch_urls()
        auth_headers = _form_headers(settings.DISPATCH_AUTH_REFERER)
        save_headers = _form_headers(settings.DISPATCH_SAVE_REFERER)
        save_responses: list[Dict[str, Any]] = []

        with httpx.Client(timeout=settings.DISPATCH_REQUEST_TIMEOUT_SECONDS, follow_redirects=True) as client:
            auth_response = client.post(auth_url, data=auth_form, headers=auth_headers)
            if auth_response.status_code >= 400:
                error_text = f"Auth returned HTTP {auth_response.status_code}"
                raise RuntimeError(f"{error_text}: {_truncate_text(auth_response.text or '')}")

            if not client.cookies.get("tsagent"):
                raise RuntimeError("Auth failed: tsagent cookie was not set")

            for item in save_items:
                item_index = int(item.get("index") or 0)
                save_form = item.get("save") or {}
                if not isinstance(save_form, dict):
                    raise RuntimeError(f"Invalid save payload for item index {item_index}")

                save_response = client.post(save_url, data=save_form, headers=save_headers)
                if save_response.status_code >= 400:
                    error_text = f"Save returned HTTP {save_response.status_code} (item #{item_index})"
                    raise RuntimeError(f"{error_text}: {_truncate_text(save_response.text or '')}")
                if "/Voucher/partner/auth" in str(save_response.url):
                    raise RuntimeError(f"Save failed for item #{item_index}: request was redirected back to auth page")

                save_responses.append(
                    {
                        "index": item_index,
                        "meta": item.get("meta") or {},
                        "response": _safe_response_payload(save_response),
                    }
                )

        job.status = DispatchJobStatus.SENT
        job.sent_at = datetime.utcnow()
        job.next_attempt_at = None
        job.error_message = None
        job.response_payload = {
            "auth": _safe_response_payload(auth_response),
            "save_items_total": len(save_items),
            "save_items_sent": len(save_responses),
            "save_items": save_responses,
        }
        db.commit()

        logger.info("✅ Dispatch job sent: %s", job_id)
        return {"ok": True, "job_id": job_id, "status": job.status.value}

    except Exception as exc:
        logger.error("❌ Dispatch job failed (%s): %s", job_id, exc)

        job = db.get(DispatchJob, job_id)
        if job is None:
            return {"ok": False, "error": str(exc), "job_id": job_id}

        job.error_message = _truncate_text(str(exc), 2000)

        if job.attempt_count >= job.max_attempts:
            job.status = DispatchJobStatus.FAILED
            job.next_attempt_at = None
            db.commit()
            return {
                "ok": False,
                "job_id": job_id,
                "status": job.status.value,
                "error": job.error_message,
            }

        retry_delay = settings.DISPATCH_RETRY_DELAY_SECONDS
        job.status = DispatchJobStatus.QUEUED
        job.next_attempt_at = datetime.utcnow() + timedelta(seconds=retry_delay)
        db.commit()
        raise self.retry(exc=exc, countdown=retry_delay)

    finally:
        db.close()
