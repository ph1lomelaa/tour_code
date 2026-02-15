"""
Background dispatch task for sending tour-code payloads to partner API.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict
import logging

import httpx

from app.core.config import settings
from app.queue.celery_app import celery_app
from app.services.partner_payload_builder import build_partner_payload
from db.models import DispatchJob, DispatchJobStatus, Tour
from db.setup import SessionLocal

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


def _extract_business_error(response: httpx.Response) -> str | None:
    content_type = response.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            body = response.json()
        except ValueError:
            body = None

        if isinstance(body, dict):
            biz_status = body.get("status")
            if biz_status is not None:
                try:
                    status_int = int(biz_status)
                except (TypeError, ValueError):
                    status_int = 0
                if status_int != 200:
                    message = str(body.get("string") or body.get("message") or "").strip()
                    if not message:
                        message = _truncate_text(str(body), 600)
                    return f"Target business error {status_int}: {message}"

    text = (response.text or "").strip()
    if not text:
        return None
    if "tour dates must be future" in text.lower():
        return _truncate_text(text, 800)
    return None


def _resolve_platform_mode() -> str:
    configured_mode = (settings.DISPATCH_PLATFORM_MODE or "").strip().lower()
    if configured_mode in {"test", "prod"}:
        return configured_mode

    test_target_url = (settings.DISPATCH_TEST_TARGET_URL or "").strip().lower()
    prod_target_url = (settings.DISPATCH_PROD_TARGET_URL or "").strip().lower()
    legacy_target_url = (settings.DISPATCH_TARGET_URL or "").strip().lower()

    if "test.fondkamkor.kz" in legacy_target_url:
        return "test"
    if legacy_target_url:
        return "prod"
    if prod_target_url:
        return "prod"
    if test_target_url:
        return "test"
    return "test"


def _resolve_dispatch_target_url(mode: str) -> str:
    mode_normalized = (mode or "").strip().lower()
    if mode_normalized == "prod":
        target_url = (settings.DISPATCH_PROD_TARGET_URL or "").strip()
        if target_url:
            return target_url
    else:
        target_url = (settings.DISPATCH_TEST_TARGET_URL or "").strip()
        if target_url:
            return target_url

    legacy_target_url = (settings.DISPATCH_TARGET_URL or "").strip()
    if legacy_target_url:
        return legacy_target_url

    raise RuntimeError(f"Dispatch target URL is not configured for mode '{mode_normalized or 'test'}'")


def _json_headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "User-Agent": settings.DISPATCH_USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
    }


def _calc_progress(sent_items: int, total_items: int) -> Dict[str, int]:
    total = max(int(total_items), 0)
    sent = max(int(sent_items), 0)
    if total <= 0:
        return {"total_items": 0, "sent_items": sent, "percent": 0}
    percent = int(round((sent / total) * 100))
    percent = max(0, min(100, percent))
    return {"total_items": total, "sent_items": min(sent, total), "percent": percent}


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

        mode = _resolve_platform_mode()
        tour_db = db.get(Tour, job.tour_id) if job.tour_id else None
        prepared_payload = build_partner_payload(job.payload, mode=mode, tour_db=tour_db)
        job.prepared_payload = {"mode": mode, **prepared_payload}
        db.commit()

        json_items = prepared_payload.get("json_items") or []
        if not isinstance(json_items, list):
            json_items = []

        if settings.DISPATCH_DRY_RUN:
            items_total = len(json_items)
            job.status = DispatchJobStatus.SENT
            job.sent_at = datetime.utcnow()
            job.next_attempt_at = None
            job.error_message = None
            job.response_payload = {
                "mode": "dry_run",
                "message": "Dispatch skipped. Payload prepared only.",
                "platform_mode": mode,
                "items_total": items_total,
                "progress": _calc_progress(items_total, items_total),
            }
            db.commit()
            logger.info("Dispatch job dry-run prepared: %s", job_id)
            return {"ok": True, "job_id": job_id, "status": job.status.value, "dry_run": True}

        if len(json_items) == 0:
            raise RuntimeError("No pilgrims to dispatch: json_items is empty")

        target_url = _resolve_dispatch_target_url(mode)
        headers = _json_headers()
        responses: list[Dict[str, Any]] = []
        total_items = len(json_items)

        job.response_payload = {
            "mode": mode,
            "target_url": target_url,
            "json_items_total": total_items,
            "json_items_sent": 0,
            "progress": _calc_progress(0, total_items),
        }
        db.commit()

        with httpx.Client(timeout=settings.DISPATCH_REQUEST_TIMEOUT_SECONDS, follow_redirects=True) as client:
            for item in json_items:
                item_index = int(item.get("index") or 0)
                payload = item.get("payload") or {}
                if not isinstance(payload, dict):
                    raise RuntimeError(f"Invalid json payload for item index {item_index}")

                response = client.post(target_url, json=payload, headers=headers)
                if response.status_code >= 400:
                    error_text = f"Target returned HTTP {response.status_code} (item #{item_index})"
                    raise RuntimeError(f"{error_text}: {_truncate_text(response.text or '')}")

                business_error = _extract_business_error(response)
                if business_error:
                    raise RuntimeError(f"{business_error} (item #{item_index})")

                responses.append(
                    {
                        "index": item_index,
                        "meta": item.get("meta") or {},
                        "response": _safe_response_payload(response),
                    }
                )
                sent_items = len(responses)
                job.response_payload = {
                    "mode": mode,
                    "target_url": target_url,
                    "json_items_total": total_items,
                    "json_items_sent": sent_items,
                    "progress": _calc_progress(sent_items, total_items),
                    "last_sent_index": item_index,
                    "last_sent_meta": item.get("meta") or {},
                }
                db.commit()

        job.status = DispatchJobStatus.SENT
        job.sent_at = datetime.utcnow()
        job.next_attempt_at = None
        job.error_message = None
        job.response_payload = {
            "mode": mode,
            "target_url": target_url,
            "json_items_total": total_items,
            "json_items_sent": len(responses),
            "progress": _calc_progress(len(responses), total_items),
            "json_items": responses,
        }
        db.commit()

        logger.info("Dispatch job sent: %s", job_id)
        return {"ok": True, "job_id": job_id, "status": job.status.value}

    except Exception as exc:
        logger.error("Dispatch job failed (%s): %s", job_id, exc)

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
