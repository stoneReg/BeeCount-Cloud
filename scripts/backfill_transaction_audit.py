"""从 sync_changes 回填 transaction_audit_log(一次性)。"""
from __future__ import annotations

import argparse
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.models import SyncChange, TransactionAuditLog
from src.services.transaction_audit.diff import diff_transaction_payloads, infer_audit_action

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _parse_payload(raw) -> dict | None:
    if isinstance(raw, dict):
        return raw
    return None


def backfill(db: Session, *, batch_commit: int = 500) -> tuple[int, int]:
    existing = set(
        db.scalars(
            select(TransactionAuditLog.change_id).where(
                TransactionAuditLog.change_id.is_not(None)
            )
        ).all()
    )
    changes = db.scalars(
        select(SyncChange)
        .where(
            SyncChange.entity_type == "transaction",
            SyncChange.ledger_id.is_not(None),
        )
        .order_by(SyncChange.change_id.asc())
    ).all()

    inserted = 0
    skipped = 0
    # (ledger_id, entity_sync_id) → 上一版 payload
    last_payload: dict[tuple[str, str], dict | None] = {}

    for i, ch in enumerate(changes, start=1):
        if ch.change_id in existing:
            skipped += 1
            continue
        key = (ch.ledger_id, ch.entity_sync_id)
        before = last_payload.get(key)
        if ch.action == "delete":
            after = None
        else:
            after = _parse_payload(ch.payload_json)

        action = infer_audit_action(
            sync_action=ch.action, before=before, after=after
        )
        field_diff = diff_transaction_payloads(before, after)
        if action == "update" and not field_diff:
            skipped += 1
            if ch.action == "delete":
                last_payload.pop(key, None)
            elif after is not None:
                last_payload[key] = after
            continue

        row = TransactionAuditLog(
            change_id=ch.change_id,
            ledger_id=ch.ledger_id,
            entity_sync_id=ch.entity_sync_id,
            action=action,
            updated_at=ch.updated_at,
            updated_by_device_id=ch.updated_by_device_id,
            updated_by_user_id=ch.updated_by_user_id,
            field_diff_json=field_diff,
            payload_json=before if ch.action == "delete" else (after if after is not None else (before or {})),
        )
        db.add(row)
        inserted += 1

        if ch.action == "delete":
            last_payload.pop(key, None)
        elif after is not None:
            last_payload[key] = after

        if inserted % batch_commit == 0:
            db.commit()
            logger.info("committed %d inserted so far", inserted)

    db.commit()
    return inserted, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill transaction_audit_log from sync_changes")
    parser.add_argument("--batch", type=int, default=500)
    args = parser.parse_args()
    with SessionLocal() as db:
        inserted, skipped = backfill(db, batch_commit=args.batch)
    logger.info("done inserted=%d skipped=%d", inserted, skipped)


if __name__ == "__main__":
    main()
