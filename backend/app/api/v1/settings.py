"""
Раздел «Настройки»: справочники (авиалинии, страны, отели, маршруты,
турагенты) с проверкой по Камкору.
"""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Dict, Literal, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import kamkor_reference, reference_data
from db.models import (
    AdminAuditLog, DispatchJob, DispatchJobStatus,
    RefAirline, RefCountry, RefHotel, RefRoute, RefTouragent,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

Entity = Literal["airlines", "countries", "hotels", "routes", "touragents"]

# entity -> (модель, редактируемые поля, уникальные поля, поля в верхнем регистре)
_ENTITIES: Dict[str, Tuple[Any, Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]] = {
    "airlines": (RefAirline, ("code", "name"), ("code",), ("code",)),
    "countries": (RefCountry, ("name_ru", "name_en"), ("name_ru",), ()),
    "hotels": (RefHotel, ("name", "city"), ("name",), ()),
    "routes": (RefRoute, ("code", "departure_city"), ("code",), ("code",)),
    "touragents": (RefTouragent, ("name", "bin", "is_default"), ("name", "bin"), ()),
}

# Обязательные при создании. Название турагента можно не вводить —
# оно подставится из реестра Камкора по БИН.
_REQUIRED = {"touragents": ("bin",)}

_ENTITY_LABELS = {
    "airlines": "авиалинию",
    "countries": "страну",
    "hotels": "отель",
    "routes": "маршрут",
    "touragents": "турагента",
}

_SERIALIZED_FIELDS = (
    "id", "code", "name", "name_ru", "name_en", "city", "departure_city", "bin",
    "is_default", "sort_order", "is_active", "kamkor_verified_at",
)


# ── Список для страницы создания тур-кода ────────────────

def _serialize(row: Any) -> Dict[str, Any]:
    data = {}
    for field in _SERIALIZED_FIELDS:
        if hasattr(row, field):
            value = getattr(row, field)
            data[field] = value.isoformat() if isinstance(value, datetime) else value
    return data


def _ordered(db: Session, model: Any, include_inactive: bool = False):
    query = db.query(model)
    if not include_inactive:
        query = query.filter(model.is_active.is_(True))
    return query.order_by(model.sort_order, model.created_at).all()


@router.get("/reference")
def get_reference(db: Session = Depends(get_db)):
    return {entity: [_serialize(r) for r in _ordered(db, model)] for entity, (model, *_rest) in _ENTITIES.items()}


# ── Камкор: аккаунты входа, упавшие отправки ─────────────

@router.get("/kamkor/accounts")
def get_kamkor_accounts():
    return {"accounts": kamkor_reference.check_accounts()}


@router.get("/dispatch/failed")
def list_failed_dispatch_jobs(limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.query(DispatchJob)
        .filter(DispatchJob.status == DispatchJobStatus.FAILED)
        .order_by(desc(DispatchJob.updated_at))
        .limit(max(1, min(limit, 200)))
        .all()
    )
    jobs = []
    for job in rows:
        payload = job.payload if isinstance(job.payload, dict) else {}
        tour = payload.get("tour") or {}
        overrides = payload.get("dispatch_overrides") or {}
        matched = (payload.get("results") or {}).get("matched") or []
        jobs.append({
            "id": str(job.id),
            "tour_label": " ".join(
                part for part in (
                    f'{tour.get("date_start", "")}–{tour.get("date_end", "")}'.strip("–"),
                    tour.get("route") or "",
                ) if part
            ),
            "touragent": overrides.get("q_touragent") or "",
            "pilgrims": len(matched) if isinstance(matched, list) else 0,
            "error_message": job.error_message or "",
            "attempt_count": job.attempt_count,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        })
    return {"jobs": jobs}


# ── Журнал ───────────────────────────────────────────────

@router.get("/audit")
def get_audit_log(limit: int = 100, db: Session = Depends(get_db)):
    rows = (
        db.query(AdminAuditLog)
        .order_by(desc(AdminAuditLog.created_at))
        .limit(max(1, min(limit, 500)))
        .all()
    )
    return {
        "items": [
            {
                "id": r.id, "entity": r.entity, "entity_id": r.entity_id, "action": r.action,
                "before": r.before, "after": r.after, "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }


def _audit(db: Session, entity: str, row: Any, action: str, before: Optional[Dict[str, Any]]) -> None:
    db.add(AdminAuditLog(
        entity=entity, entity_id=row.id, action=action,
        before=before, after=_serialize(row) if action != "delete" else None,
    ))


# ── CRUD справочников ────────────────────────────────────

class EntityWrite(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)
    # Сохранить, даже если Камкор не нашёл значение (галочка «я уверен»).
    force: bool = False


def _clean(entity: str, raw: Dict[str, Any], partial: bool) -> Dict[str, Any]:
    _model, fields, unique_fields, upper_fields = _ENTITIES[entity]
    data: Dict[str, Any] = {}
    for field in fields:
        if field not in raw:
            continue
        value = raw[field]
        if field == "is_default":
            data[field] = bool(value)
            continue
        text = " ".join(str(value or "").split())
        if field in upper_fields:
            text = text.upper().replace(" ", "")
        if field == "bin":
            text = text.replace(" ", "")
        data[field] = text
    if not partial:
        for field in _REQUIRED.get(entity, unique_fields):
            if not data.get(field):
                raise HTTPException(status_code=422, detail=f"Поле «{field}» обязательно")
    for field in unique_fields:
        if field in data and not data[field]:
            raise HTTPException(status_code=422, detail=f"Поле «{field}» не может быть пустым")
    return data


def _check_duplicates(db: Session, entity: str, data: Dict[str, Any], exclude_id: Optional[str] = None) -> None:
    model, _fields, unique_fields, _upper = _ENTITIES[entity]
    for field in unique_fields:
        if field not in data:
            continue
        # Сравнение в Python: lower() в SQLite не работает с кириллицей.
        needle = data[field].casefold()
        existing = next(
            (
                row for row in db.query(model).all()
                if row.id != exclude_id and str(getattr(row, field) or "").casefold() == needle
            ),
            None,
        )
        if existing is None:
            continue
        if existing.is_active:
            raise HTTPException(status_code=409, detail=f"«{data[field]}» уже есть в справочнике")
        raise HTTPException(
            status_code=409,
            detail=f"«{data[field]}» есть среди удалённых — включите «показать удалённые» и восстановите",
        )


def _verify_or_reject(entity: str, merged: Dict[str, Any], force: bool) -> Dict[str, Any]:
    result = kamkor_reference.verify(entity, merged)
    if result["status"] == "invalid":
        raise HTTPException(status_code=422, detail=result["message"])
    if result["status"] == "not_found" and not force:
        raise HTTPException(status_code=422, detail=result["message"])
    return result


def _fill_from_kamkor(entity: str, data: Dict[str, Any], result: Dict[str, Any]) -> None:
    """Пустые необязательные поля заполняем тем, что вернул справочник Камкора."""
    fields = _ENTITIES[entity][1]
    for key, value in (result.get("extra") or {}).items():
        if key in fields and not data.get(key) and value:
            data[key] = value


def _get_row(db: Session, entity: str, row_id: str) -> Any:
    model = _ENTITIES[entity][0]
    row = db.get(model, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return row


def _apply_default(db: Session, entity: str, row: Any) -> None:
    if entity == "touragents" and row.is_default:
        db.query(RefTouragent).filter(RefTouragent.id != row.id).update({"is_default": False})


def _commit(db: Session) -> None:
    db.commit()
    reference_data.invalidate_cache()


@router.get("/{entity}")
def list_entity(entity: Entity, include_inactive: bool = True, db: Session = Depends(get_db)):
    model = _ENTITIES[entity][0]
    return {"items": [_serialize(r) for r in _ordered(db, model, include_inactive)]}


@router.post("/{entity}/verify")
def verify_entity(entity: Entity, body: EntityWrite):
    data = _clean(entity, body.data, partial=False)
    return kamkor_reference.verify(entity, data)


@router.post("/{entity}")
def create_entity(entity: Entity, body: EntityWrite, db: Session = Depends(get_db)):
    model = _ENTITIES[entity][0]
    data = _clean(entity, body.data, partial=False)
    _check_duplicates(db, entity, data)
    result = _verify_or_reject(entity, data, body.force)
    _fill_from_kamkor(entity, data, result)
    if entity == "touragents" and not data.get("name"):
        raise HTTPException(status_code=422, detail="Укажите название турагента — в реестре Камкора его не нашлось")
    _check_duplicates(db, entity, data)

    max_order = db.query(func.max(model.sort_order)).scalar() or 0
    row = model(**data, sort_order=max_order + 1)
    if result["status"] == "found":
        row.kamkor_verified_at = datetime.utcnow()
    db.add(row)
    db.flush()
    _apply_default(db, entity, row)
    _audit(db, entity, row, "create", None)
    _commit(db)
    db.refresh(row)
    return {"item": _serialize(row), "verification": result}


@router.patch("/{entity}/{row_id}")
def update_entity(entity: Entity, row_id: str, body: EntityWrite, db: Session = Depends(get_db)):
    row = _get_row(db, entity, row_id)
    before = _serialize(row)
    data = _clean(entity, body.data, partial=True)
    changed = {k: v for k, v in data.items() if getattr(row, k) != v}
    if not changed:
        return {"item": before, "verification": None}
    if entity == "touragents" and changed.get("is_default") is False and row.is_default:
        raise HTTPException(status_code=400, detail="Выберите другого турагента по умолчанию вместо снятия отметки")
    _check_duplicates(db, entity, changed, exclude_id=row.id)

    result = None
    unique_fields = _ENTITIES[entity][2]
    if any(field in changed for field in unique_fields):
        merged = {**before, **changed}
        result = _verify_or_reject(entity, merged, body.force)
        row.kamkor_verified_at = datetime.utcnow() if result["status"] == "found" else None

    for key, value in changed.items():
        setattr(row, key, value)
    _apply_default(db, entity, row)
    _audit(db, entity, row, "update", before)
    _commit(db)
    db.refresh(row)
    return {"item": _serialize(row), "verification": result}


@router.delete("/{entity}/{row_id}")
def delete_entity(entity: Entity, row_id: str, db: Session = Depends(get_db)):
    model = _ENTITIES[entity][0]
    row = _get_row(db, entity, row_id)
    if not row.is_active:
        return {"item": _serialize(row)}
    if entity == "touragents" and row.is_default:
        raise HTTPException(status_code=400, detail="Нельзя удалить турагента по умолчанию — сначала назначьте другого")
    active_count = db.query(model).filter(model.is_active.is_(True)).count()
    if active_count <= 1:
        raise HTTPException(status_code=400, detail=f"Нельзя удалить последнюю {_ENTITY_LABELS[entity]} в справочнике")

    before = _serialize(row)
    row.is_active = False
    _audit(db, entity, row, "delete", before)
    _commit(db)
    db.refresh(row)
    return {"item": _serialize(row)}


@router.post("/{entity}/{row_id}/restore")
def restore_entity(entity: Entity, row_id: str, db: Session = Depends(get_db)):
    row = _get_row(db, entity, row_id)
    if row.is_active:
        return {"item": _serialize(row)}
    before = _serialize(row)
    row.is_active = True
    _audit(db, entity, row, "restore", before)
    _commit(db)
    db.refresh(row)
    return {"item": _serialize(row)}
