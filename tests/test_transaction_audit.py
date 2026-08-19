"""transaction_audit diff / backfill 单元测试。"""
from src.services.transaction_audit.diff import diff_transaction_payloads, infer_audit_action


def test_diff_create_detects_fields():
    after = {"type": "expense", "amount": 10.0, "note": "午餐"}
    changes = diff_transaction_payloads(None, after)
    fields = {c["field"] for c in changes}
    assert "amount" in fields
    assert "note" in fields
    assert infer_audit_action(sync_action="upsert", before=None, after=after) == "create"


def test_diff_update_amount():
    before = {"type": "expense", "amount": 10.0, "note": "午餐"}
    after = {"type": "expense", "amount": 15.0, "note": "午餐"}
    changes = diff_transaction_payloads(before, after)
    assert len(changes) == 1
    assert changes[0]["field"] == "amount"
    assert changes[0]["from"] == 10.0
    assert changes[0]["to"] == 15.0


def test_diff_delete():
    before = {"type": "expense", "amount": 10.0}
    changes = diff_transaction_payloads(before, None)
    assert any(c["field"] == "amount" for c in changes)
    assert infer_audit_action(sync_action="delete", before=before, after=None) == "delete"
