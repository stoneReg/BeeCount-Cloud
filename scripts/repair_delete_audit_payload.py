"""修复 delete 审计行:从 field_diff 回填 payload_json,便于展示已删账单摘要。"""
from __future__ import annotations

import argparse
import logging

from sqlalchemy import select

from src.database import SessionLocal
from src.models import TransactionAuditLog
from src.services.transaction_audit.diff import snapshot_to_display_changes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _rebuild_snapshot_from_diff(field_diff: list) -> dict:
    snapshot: dict = {}
    for item in field_diff or []:
        if not isinstance(item, dict):
            continue
        field = item.get("field")
        if not field:
            continue
        value = item.get("from")
        if value is not None:
            snapshot[str(field)] = value
    return snapshot


def repair(*, dry_run: bool = False) -> tuple[int, int]:
    updated = 0
    skipped = 0
    with SessionLocal() as db:
        rows = db.scalars(
            select(TransactionAuditLog).where(TransactionAuditLog.action == "delete")
        ).all()
        for row in rows:
            diff = row.field_diff_json if isinstance(row.field_diff_json, list) else []
            payload = row.payload_json if isinstance(row.payload_json, dict) else {}
            has_summary = snapshot_to_display_changes(payload, action="delete")
            if has_summary:
                skipped += 1
                continue
            if not diff:
                skipped += 1
                continue
            rebuilt = _rebuild_snapshot_from_diff(diff)
            if not rebuilt:
                skipped += 1
                continue
            merged = {**rebuilt, **payload}
            if dry_run:
                logger.info("would repair audit id=%s keys=%s", row.id, list(rebuilt.keys())[:6])
            else:
                row.payload_json = merged
            updated += 1
        if not dry_run:
            db.commit()
    return updated, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair delete audit payload_json from field_diff")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    updated, skipped = repair(dry_run=args.dry_run)
    logger.info("done updated=%d skipped=%d", updated, skipped)


if __name__ == "__main__":
    main()
