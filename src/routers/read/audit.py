"""交易修改记录 read API。"""
from __future__ import annotations

from typing import Any

from fastapi import Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...deps import get_current_user
from ...ledger_access import list_accessible_ledgers
from ...models import Device, Ledger, TransactionAuditLog, User
from ...schemas import (
    TransactionAuditEntryOut,
    TransactionAuditFieldChangeOut,
    TransactionAuditPageOut,
)
from ._shared import (
    _READ_SCOPE_DEP,
    _is_admin,
    _require_ledger,
    _resolve_ledger_name,
    get_db,
    router,
)


def _audit_row_to_out(
    row: TransactionAuditLog,
    *,
    ledger_external_id: str,
    ledger_name: str | None,
    device_name: str | None,
    user_display_name: str | None,
    user_email: str | None,
) -> TransactionAuditEntryOut:
    changes = [
        TransactionAuditFieldChangeOut(
            field=c.get("field", ""),
            label=c.get("label", c.get("field", "")),
            from_value=c.get("from"),
            to_value=c.get("to"),
        )
        for c in (row.field_diff_json or [])
        if isinstance(c, dict)
    ]
    return TransactionAuditEntryOut(
        id=row.id,
        change_id=row.change_id,
        ledger_id=ledger_external_id,
        ledger_name=ledger_name,
        entity_sync_id=row.entity_sync_id,
        action=row.action,
        updated_at=row.updated_at,
        updated_by_device_id=row.updated_by_device_id,
        device_name=device_name,
        updated_by_user_id=row.updated_by_user_id,
        user_display_name=user_display_name,
        user_email=user_email,
        changes=changes,
        payload=row.payload_json or {},
    )


def _load_device_names(db: Session, device_ids: set[str]) -> dict[str, str]:
    if not device_ids:
        return {}
    rows = db.execute(
        select(Device.id, Device.name).where(Device.id.in_(device_ids))
    ).all()
    return {r.id: r.name for r in rows}


def _load_user_info(db: Session, user_ids: set[str]) -> dict[str, tuple[str | None, str | None]]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(User.id, User.display_name, User.email).where(User.id.in_(user_ids))
    ).all()
    return {r.id: (r.display_name, r.email) for r in rows}


def _serialize_page(
    db: Session,
    rows: list[TransactionAuditLog],
    ledger_map: dict[str, Ledger],
    *,
    limit: int,
) -> TransactionAuditPageOut:
    device_ids = {r.updated_by_device_id for r in rows if r.updated_by_device_id}
    user_ids = {r.updated_by_user_id for r in rows if r.updated_by_user_id}
    devices = _load_device_names(db, device_ids)
    users = _load_user_info(db, user_ids)

    has_more = len(rows) > limit
    rows = rows[:limit]
    items: list[TransactionAuditEntryOut] = []
    for row in rows:
        lg = ledger_map.get(row.ledger_id)
        ext_id = lg.external_id if lg else row.ledger_id
        lg_name = _resolve_ledger_name(db, ledger=lg) if lg else None
        uid = row.updated_by_user_id
        disp, email = users.get(uid, (None, None)) if uid else (None, None)
        items.append(
            _audit_row_to_out(
                row,
                ledger_external_id=ext_id,
                ledger_name=lg_name,
                device_name=devices.get(row.updated_by_device_id or ""),
                user_display_name=disp,
                user_email=email,
            )
        )
    next_before = items[-1].id if items and has_more else None
    return TransactionAuditPageOut(
        items=items, has_more=has_more, next_before_id=next_before
    )


@router.get(
    "/ledgers/{ledger_external_id}/transactions/{sync_id}/history",
    response_model=TransactionAuditPageOut,
)
def list_transaction_history(
    ledger_external_id: str,
    sync_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    before_id: int | None = Query(default=None, ge=1),
    _scopes: set[str] = Depends(_READ_SCOPE_DEP),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionAuditPageOut:
    is_admin = _is_admin(current_user)
    ledger, _ = _require_ledger(
        db,
        user_id=current_user.id,
        ledger_external_id=ledger_external_id,
        is_admin=is_admin,
    )
    q = (
        select(TransactionAuditLog)
        .where(
            TransactionAuditLog.ledger_id == ledger.id,
            TransactionAuditLog.entity_sync_id == sync_id,
        )
        .order_by(TransactionAuditLog.id.desc())
    )
    if before_id is not None:
        q = q.where(TransactionAuditLog.id < before_id)
    q = q.limit(limit + 1)
    rows = list(db.scalars(q).all())
    return _serialize_page(
        db, rows, {ledger.id: ledger}, limit=limit
    )


@router.get("/audit/recent", response_model=TransactionAuditPageOut)
def list_recent_audit(
    ledger_id: str | None = Query(default=None, description="账本 external_id,可选"),
    limit: int = Query(default=50, ge=1, le=200),
    before_id: int | None = Query(default=None, ge=1),
    _scopes: set[str] = Depends(_READ_SCOPE_DEP),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionAuditPageOut:
    accessible = list_accessible_ledgers(db, user_id=current_user.id)
    ledger_map = {lg.id: lg for lg in accessible}
    ledger_ids = list(ledger_map.keys())
    if not ledger_ids:
        return TransactionAuditPageOut(items=[], has_more=False)

    if ledger_id:
        lg = next((x for x in accessible if x.external_id == ledger_id), None)
        if lg is None:
            from fastapi import HTTPException, status

            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ledger not found")
        ledger_ids = [lg.id]

    q = (
        select(TransactionAuditLog)
        .where(TransactionAuditLog.ledger_id.in_(ledger_ids))
        .order_by(TransactionAuditLog.updated_at.desc(), TransactionAuditLog.id.desc())
    )
    if before_id is not None:
        q = q.where(TransactionAuditLog.id < before_id)
    q = q.limit(limit + 1)
    rows = list(db.scalars(q).all())
    return _serialize_page(db, rows, ledger_map, limit=limit)
