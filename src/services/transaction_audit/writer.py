"""审计写入 — 在 SyncChange flush 后、projection 更新前调用。"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import ReadTxProjection, SyncChange, TransactionAuditLog
from .diff import diff_transaction_payloads, infer_audit_action
from .payload import projection_row_to_payload

logger = logging.getLogger(__name__)


def _parse_payload(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    return None


def _load_before_payload(
    db: Session,
    *,
    ledger_id: str,
    entity_sync_id: str,
) -> dict[str, Any] | None:
    row = db.scalar(
        select(ReadTxProjection).where(
            ReadTxProjection.ledger_id == ledger_id,
            ReadTxProjection.sync_id == entity_sync_id,
        )
    )
    if row is None:
        return None
    return projection_row_to_payload(row)


def record_transaction_audit_for_sync_change(
    db: Session,
    *,
    ledger_id: str,
    change: SyncChange,
) -> TransactionAuditLog | None:
    """根据 SyncChange 写一条 transaction_audit_log(同事务,不 commit)。"""
    if change.entity_type != "transaction":
        return None

    payload = _parse_payload(change.payload_json)
    sync_action = change.action or "upsert"

    if sync_action == "delete":
        before = _load_before_payload(
            db, ledger_id=ledger_id, entity_sync_id=change.entity_sync_id
        )
        after = None
    else:
        before = _load_before_payload(
            db, ledger_id=ledger_id, entity_sync_id=change.entity_sync_id
        )
        after = payload

    action = infer_audit_action(
        sync_action=sync_action, before=before, after=after
    )
    field_diff = diff_transaction_payloads(before, after)

    # delete 或无实质字段变化时仍保留一条(创建/删除/空 upsert 重放)
    if action == "update" and not field_diff:
        return None

    if sync_action == "delete":
        # delete push 的 payload 通常只有 actor 字段;快照必须用删除前 projection。
        stored_payload = dict(before or {})
        if payload:
            for key in ("createdByUserId", "updatedByUserId"):
                if key in payload:
                    stored_payload[key] = payload[key]
    else:
        stored_payload = payload if payload is not None else (before or {})

    row = TransactionAuditLog(
        change_id=change.change_id,
        ledger_id=ledger_id,
        entity_sync_id=change.entity_sync_id,
        action=action,
        updated_at=change.updated_at,
        updated_by_device_id=change.updated_by_device_id,
        updated_by_user_id=change.updated_by_user_id,
        field_diff_json=field_diff,
        payload_json=stored_payload,
    )
    db.add(row)
    logger.debug(
        "transaction_audit recorded change_id=%s ledger=%s sync_id=%s action=%s fields=%d",
        change.change_id,
        ledger_id,
        change.entity_sync_id,
        action,
        len(field_diff),
    )
    return row
