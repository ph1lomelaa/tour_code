"""
Фоновая отправка данных тур-кода во внешний backend.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict
import logging

import httpx

from app.core.celery_app import celery_app
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

        if not settings.DISPATCH_TARGET_URL:
            raise RuntimeError("DISPATCH_TARGET_URL is not configured")

        prepared_payload = build_partner_payload(job.payload)
        job.prepared_payload = prepared_payload
        db.commit()

        with httpx.Client(timeout=settings.DISPATCH_REQUEST_TIMEOUT_SECONDS) as client:
            response = client.post(settings.DISPATCH_TARGET_URL, json=prepared_payload)

        if response.status_code >= 400:
            error_text = f"External backend returned HTTP {response.status_code}"
            raise RuntimeError(f"{error_text}: { _truncate_text(response.text or '') }")

        job.status = DispatchJobStatus.SENT
        job.sent_at = datetime.utcnow()
        job.next_attempt_at = None
        job.error_message = None
        job.response_payload = _safe_response_payload(response)
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
