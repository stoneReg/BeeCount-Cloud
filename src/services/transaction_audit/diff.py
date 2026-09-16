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


# UI 展示时若已有 *_Name / tags,则隐藏对应 Id 字段,避免重复。
_DISPLAY_SKIP_IF_PRESENT: dict[str, str] = {
    "categoryId": "categoryName",
    "accountId": "accountName",
    "fromAccountId": "fromAccountName",
    "toAccountId": "toAccountName",
    "tagIds": "tags",
}

_DISPLAY_FIELD_ORDER: list[str] = list(FIELD_LABELS.keys())

# 新增/删除记录 UI 摘要字段(避免展示 excludeFromStats 等技术项)
SUMMARY_DISPLAY_FIELDS: tuple[str, ...] = (
    "type",
    "amount",
    "categoryName",
    "accountName",
    "fromAccountName",
    "toAccountName",
    "happenedAt",
    "note",
    "tags",
)


def filter_changes_for_display(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """去掉 Id/Name 重复项,并按产品字段顺序排序。"""
    fields = {c.get("field") for c in changes if isinstance(c, dict)}
    filtered = [
        c
        for c in changes
        if isinstance(c, dict)
        and _DISPLAY_SKIP_IF_PRESENT.get(str(c.get("field", "")), "") not in fields
    ]
    order_index = {name: idx for idx, name in enumerate(_DISPLAY_FIELD_ORDER)}

    def _sort_key(item: dict[str, Any]) -> tuple[int, str]:
        field = str(item.get("field", ""))
        return (order_index.get(field, len(_DISPLAY_FIELD_ORDER)), field)

    return sorted(filtered, key=_sort_key)


def snapshot_to_display_changes(
    snapshot: dict[str, Any] | None,
    *,
    action: str,
) -> list[dict[str, Any]]:
    """从交易快照生成 UI 展示行(create 展示 to, delete 展示 from)。"""
    data = snapshot or {}
    changes: list[dict[str, Any]] = []
    for key in SUMMARY_DISPLAY_FIELDS:
        if key not in data:
            continue
        value = data.get(key)
        if _normalize(value) is None:
            continue
        label = FIELD_LABELS.get(key, key)
        if action == "create":
            changes.append({"field": key, "label": label, "from": None, "to": value})
        elif action == "delete":
            changes.append({"field": key, "label": label, "from": value, "to": None})
    return filter_changes_for_display(changes)


def _summarize_changes(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary = [c for c in changes if str(c.get("field", "")) in SUMMARY_DISPLAY_FIELDS]
    return summary if summary else changes


def resolve_display_changes(
    *,
    action: str,
    field_diff: list[dict[str, Any]] | None,
    payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """合并 field_diff 与 payload 快照,保证删除/新增记录有可读摘要。"""
    raw = [c for c in (field_diff or []) if isinstance(c, dict)]
    filtered = filter_changes_for_display(raw)
    if filtered:
        if action in ("create", "delete"):
            return _summarize_changes(filtered)
        return filtered

    snapshot = payload or {}
    if action in ("create", "delete") and snapshot:
        from_snapshot = snapshot_to_display_changes(snapshot, action=action)
        if from_snapshot:
            return from_snapshot

    return []


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
