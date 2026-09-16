"""transaction_audit diff / backfill / read API 单元测试。"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base, get_db
from src.main import app
from src.models import Ledger, LedgerMember, TransactionAuditLog, User, UserProfile
from src.services.transaction_audit.diff import (
    diff_transaction_payloads,
    filter_changes_for_display,
    infer_audit_action,
    resolve_display_changes,
    snapshot_to_display_changes,
)


def _make_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), testing_session


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


def test_filter_changes_for_display_hides_id_when_name_present():
    raw = [
        {"field": "categoryId", "label": "分类", "from": "a", "to": "b"},
        {"field": "categoryName", "label": "分类", "from": "餐饮", "to": "交通"},
        {"field": "amount", "label": "金额", "from": 1, "to": 2},
    ]
    filtered = filter_changes_for_display(raw)
    fields = {c["field"] for c in filtered}
    assert "categoryId" not in fields
    assert "categoryName" in fields
    assert filtered[0]["field"] == "amount"


def test_resolve_display_changes_delete_from_diff():
    diff = [
        {"field": "amount", "label": "金额", "from": 8.0, "to": None},
        {"field": "categoryName", "label": "分类", "from": "午餐", "to": None},
        {"field": "excludeFromStats", "label": "不计入收支", "from": False, "to": None},
    ]
    out = resolve_display_changes(action="delete", field_diff=diff, payload={})
    fields = {c["field"] for c in out}
    assert "amount" in fields
    assert "categoryName" in fields
    assert "excludeFromStats" not in fields


def test_resolve_display_changes_delete_from_payload_snapshot():
    payload = {
        "type": "expense",
        "amount": 12.5,
        "categoryName": "交通",
        "accountName": "现金",
    }
    out = resolve_display_changes(action="delete", field_diff=[], payload=payload)
    assert len(out) >= 3
    assert out[0]["field"] == "type"


def test_snapshot_to_display_changes_delete():
    rows = snapshot_to_display_changes(
        {"amount": 5, "categoryName": "餐饮"},
        action="delete",
    )
    assert len(rows) == 2
    assert rows[0]["from"] == 5


def test_audit_recent_api_returns_rows_with_user_profile() -> None:
    client, session_maker = _make_client()
    try:
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": "audit@example.com",
                "password": "123456",
                "client_type": "web",
                "device_name": "pytest-web",
                "platform": "web",
            },
        )
        assert reg.status_code == 200, reg.text
        token = reg.json()["access_token"]

        with session_maker() as db:
            user = db.scalar(select(User).where(User.email == "audit@example.com"))
            assert user is not None
            profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
            if profile is None:
                profile = UserProfile(user_id=user.id)
                db.add(profile)
            profile.display_name = "审计测试"
            ledger = Ledger(
                external_id="ledger-ext-1",
                name="测试账本",
                currency="CNY",
                user_id=user.id,
            )
            db.add(ledger)
            db.flush()
            db.add(
                LedgerMember(
                    ledger_id=ledger.id,
                    user_id=user.id,
                    role="owner",
                )
            )
            db.add(
                TransactionAuditLog(
                    ledger_id=ledger.id,
                    entity_sync_id="tx-sync-1",
                    action="create",
                    updated_at=datetime.now(timezone.utc),
                    updated_by_user_id=user.id,
                    field_diff_json=[{"field": "amount", "label": "金额", "from": None, "to": 10}],
                    payload_json={"amount": 10},
                )
            )
            db.commit()

        res = client.get(
            "/api/v1/read/audit/recent",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["user_display_name"] == "审计测试"
    finally:
        app.dependency_overrides.clear()
