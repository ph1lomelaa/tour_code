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


@celery_app.task(bind=True, name="dispatch.process_job", max_retries=100)
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

        target_url = settings.DISPATCH_TARGET_URL
        if not target_url:
            raise RuntimeError("DISPATCH_TARGET_URL is not configured")

        headers = {
            "Content-Type": "application/json",
            "User-Agent": settings.DISPATCH_USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
        }

        responses: list[Dict[str, Any]] = []
        total_items = len(json_items)

        job.prepared_payload = prepared
        job.response_payload = {
            "target_url": target_url,
            "json_items_total": total_items,
            "json_items_sent": 0,
            "progress": {
                "total_items": total_items,
                "sent_items": 0,
            },
        }
        db.commit()

        with httpx.Client(timeout=settings.DISPATCH_REQUEST_TIMEOUT_SECONDS) as client:
            for item in json_items:
                idx = int(item.get("index") or 0)
                payload = item.get("payload") or {}

                response = client.post(target_url, json=payload, headers=headers)
                if response.status_code >= 400:
                    raise RuntimeError(f"HTTP {response.status_code}: {response.text}")

                responses.append(
                    {
                        "index": idx,
                        "meta": item.get("meta") or {},
                        "status_code": response.status_code,
                        "text": response.text[:4000],
                    }
                )

                job.response_payload = {
                    "target_url": target_url,
                    "json_items_total": total_items,
                    "json_items_sent": len(responses),
                    "last_sent_index": idx,
                    "progress": {
                        "total_items": total_items,
                        "sent_items": len(responses),
                    },
                }
                db.commit()

        job.status = DispatchJobStatus.SENT
        job.sent_at = datetime.utcnow()
        job.next_attempt_at = None
        job.error_message = None
        job.response_payload = {
            "target_url": target_url,
            "json_items_total": total_items,
            "json_items_sent": len(responses),
            "json_items": responses,
            "progress": {
                "total_items": total_items,
                "sent_items": len(responses),
            },
        }
        db.commit()

        return {"ok": True, "job_id": job_id, "status": job.status.value}

    except Exception as exc:
        job = db.get(DispatchJob, job_id)
        if job:
            job.error_message = str(exc)[:2000]

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
