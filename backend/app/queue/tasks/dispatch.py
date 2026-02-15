"""
Фоновая отправка данных тур-кода во внешний backend.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict
import logging
import re

import httpx
from sqlalchemy import func

from app.queue.celery_app import celery_app
from app.core.config import settings
from db.setup import SessionLocal
from db.models import DispatchJob, DispatchJobStatus, Pilgrim
from app.services.partner_payload_builder import build_partner_payload
from app.services.document_rules import normalize_document

logger = logging.getLogger(__name__)


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
            return str(raw_value).strip()

    text = response.text or ""
    has_ok_status = re.search(r'"status"\s*:\s*"?200"?', text)
    match = re.search(r'"string"\s*:\s*"([^"]+)"', text)
    if has_ok_status and match:
        return match.group(1).strip()

    # Fallback for legacy responses where only `string` is present.
    match = re.search(r'"string"\s*:\s*"([^"]+)"', text)
    if match:
        return match.group(1).strip()

    return ""


def _find_pilgrim(
    db,
    tour_id: str | None,
    item_meta: Dict[str, Any],
) -> Pilgrim | None:
    if not tour_id:
        return None

    document = normalize_document(str(item_meta.get("document") or "").strip().upper())
    if document:
        by_document = (
            db.query(Pilgrim)
            .filter(
                Pilgrim.tour_id == tour_id,
                func.upper(func.coalesce(Pilgrim.document, "")) == document,
            )
            .first()
        )
        if by_document:
            return by_document

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

        job.response_payload = {
            "target_url": target_url,
            "json_items_total": total_items,
            "json_items_sent": 0,
        }
        db.commit()

        with httpx.Client(timeout=settings.DISPATCH_REQUEST_TIMEOUT_SECONDS) as client:
            for item in json_items:
                idx = int(item.get("index") or 0)
                payload = item.get("payload") or {}

                response = client.post(target_url, json=payload, headers=headers)
                if response.status_code >= 400:
                    raise RuntimeError(f"HTTP {response.status_code}: {response.text}")

                item_meta = item.get("meta") or {}
                tour_code = _extract_tour_code(response)
                _save_tour_code_for_item(
                    db,
                    tour_id=str(job.tour_id) if job.tour_id else None,
                    item_meta=item_meta,
                    tour_code=tour_code,
                )

                responses.append(
                    {
                        "index": idx,
                        "meta": item_meta,
                        "status_code": response.status_code,
                        "text": response.text[:4000],
                        "tour_code": tour_code,
                    }
                )

                job.response_payload = {
                    "target_url": target_url,
                    "json_items_total": total_items,
                    "json_items_sent": len(responses),
                    "last_sent_index": idx,
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
