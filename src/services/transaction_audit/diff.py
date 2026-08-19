"""交易 payload 字段 diff — 供审计表 field_diff_json 使用。"""
from __future__ import annotations

import json
from typing import Any

# camelCase payload 键 → 中文标签(UI/App/Web 共用)
FIELD_LABELS: dict[str, str] = {
    "type": "类型",
    "amount": "金额",
    "happenedAt": "时间",
    "note": "备注",
    "categoryId": "分类",
    "categoryName": "分类",
    "categoryKind": "分类类型",
    "accountId": "账户",
    "accountName": "账户",
    "fromAccountId": "转出账户",
    "fromAccountName": "转出账户",
    "toAccountId": "转入账户",
    "toAccountName": "转入账户",
    "tags": "标签",
    "tagIds": "标签",
    "attachments": "附件",
    "txIndex": "序号",
    "excludeFromStats": "不计入收支",
    "excludeFromBudget": "不计入预算",
    "currencyCode": "币种",
    "nativeAmount": "本位币金额",
    "createdByUserId": "创建人",
    "updatedByUserId": "编辑人",
}

# diff 时忽略仅 rename cascade 的名称字段(与 _tx_diff_only_cascade 对齐)
_SKIP_WHEN_PAIR: set[tuple[str, str]] = {
    ("categoryName", "categoryId"),
    ("accountName", "accountId"),
    ("fromAccountName", "fromAccountId"),
    ("toAccountName", "toAccountId"),
}


def _normalize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) if isinstance(value, float) or isinstance(value, int) else value
    if isinstance(value, str):
        return value.strip() if value.strip() else None
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return value


def _values_equal(a: Any, b: Any) -> bool:
    return _normalize(a) == _normalize(b)


def diff_transaction_payloads(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """比较两次交易快照,返回变更字段列表。"""
    before = before or {}
    after = after or {}
    keys = set(before.keys()) | set(after.keys())
    # 稳定顺序:按 FIELD_LABELS 再补其余键
    ordered = [k for k in FIELD_LABELS if k in keys]
    ordered.extend(sorted(keys - set(ordered)))

    changes: list[dict[str, Any]] = []
    for key in ordered:
        if key in ("syncId", "createdByUserId", "updatedByUserId"):
            continue
        old_v = before.get(key)
        new_v = after.get(key)
        if _values_equal(old_v, new_v):
            continue
        # 名称随 id cascade 时若 id 未变则跳过 name-only 变化
        if key.endswith("Name"):
            id_key = key.replace("Name", "Id")
            if id_key in before or id_key in after:
                if _values_equal(before.get(id_key), after.get(id_key)):
                    continue
        changes.append(
            {
                "field": key,
                "label": FIELD_LABELS.get(key, key),
                "from": old_v,
                "to": new_v,
            }
        )
    return changes


def infer_audit_action(
    *,
    sync_action: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> str:
    if sync_action == "delete":
        return "delete"
    if not before:
        return "create"
    changes = diff_transaction_payloads(before, after)
    if not changes:
        return "update"
    return "update"
