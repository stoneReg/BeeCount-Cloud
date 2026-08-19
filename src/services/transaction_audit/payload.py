"""ReadTxProjection → camelCase payload(与 write/_shared 一致,避免循环 import)。"""
from __future__ import annotations

import json
from typing import Any

from ...models import ReadTxProjection
from ...snapshot_builder import _to_iso_utc


def projection_row_to_payload(row: ReadTxProjection) -> dict[str, Any]:
    item: dict[str, Any] = {
        "syncId": row.sync_id,
        "type": row.tx_type,
        "amount": row.amount,
        "happenedAt": _to_iso_utc(row.happened_at),
    }
    if row.note is not None:
        item["note"] = row.note
    if row.category_sync_id:
        item["categoryId"] = row.category_sync_id
    if row.category_name:
        item["categoryName"] = row.category_name
    if row.category_kind:
        item["categoryKind"] = row.category_kind
    if row.account_sync_id:
        item["accountId"] = row.account_sync_id
    if row.account_name:
        item["accountName"] = row.account_name
    if row.from_account_sync_id:
        item["fromAccountId"] = row.from_account_sync_id
    if row.from_account_name:
        item["fromAccountName"] = row.from_account_name
    if row.to_account_sync_id:
        item["toAccountId"] = row.to_account_sync_id
    if row.to_account_name:
        item["toAccountName"] = row.to_account_name
    if row.tags_csv:
        item["tags"] = row.tags_csv
    if row.tag_sync_ids_json:
        try:
            tag_ids = json.loads(row.tag_sync_ids_json)
            if isinstance(tag_ids, list) and tag_ids:
                item["tagIds"] = tag_ids
        except json.JSONDecodeError:
            pass
    if row.attachments_json:
        try:
            atts = json.loads(row.attachments_json)
            if isinstance(atts, list) and atts:
                item["attachments"] = atts
        except json.JSONDecodeError:
            pass
    if row.tx_index:
        item["txIndex"] = row.tx_index
    if row.created_by_user_id:
        item["createdByUserId"] = row.created_by_user_id
    if row.last_edited_by_user_id:
        item["updatedByUserId"] = row.last_edited_by_user_id
    item["excludeFromStats"] = bool(row.exclude_from_stats)
    item["excludeFromBudget"] = bool(row.exclude_from_budget)
    if row.currency_code is not None:
        item["currencyCode"] = row.currency_code
    if row.native_amount is not None:
        item["nativeAmount"] = row.native_amount
    return item
