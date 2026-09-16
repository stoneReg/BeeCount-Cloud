"""为 debug 用户复制管理员 AI 配置、创建 debug 账本并 seed 默认二级分类。

用法(容器内):
  PYTHONPATH=/app python3 scripts/dev/bootstrap_debug_user.py

幂等:已有 profile / ledger / 分类时跳过对应步骤。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from src.database import SessionLocal
from src.models import Ledger, LedgerMember, SyncChange, User, UserCategoryProjection, UserProfile
from src.sync_applier import apply_user_change_to_projection

ADMIN_EMAIL = "family@family.com"
DEBUG_EMAIL = "debug@family.com"
LEDGER_NAME = "debug账本"
LEDGER_EXTERNAL_ID = "ledger_debug_harness"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def main() -> None:
    db = SessionLocal()
    try:
        admin = db.scalar(select(User).where(User.email == ADMIN_EMAIL))
        debug = db.scalar(select(User).where(User.email == DEBUG_EMAIL))
        if admin is None or debug is None:
            raise SystemExit(f"user missing: admin={ADMIN_EMAIL!r} debug={DEBUG_EMAIL!r}")

        admin_profile = db.scalar(select(UserProfile).where(UserProfile.user_id == admin.id))
        if admin_profile is None or not admin_profile.ai_config_json:
            raise SystemExit("admin user has no ai_config_json")

        debug_profile = db.scalar(select(UserProfile).where(UserProfile.user_id == debug.id))
        if debug_profile is None:
            debug_profile = UserProfile(
                user_id=debug.id,
                ai_config_json=admin_profile.ai_config_json,
                primary_currency=admin_profile.primary_currency,
                income_is_red=admin_profile.income_is_red,
            )
            db.add(debug_profile)
            print("created debug profile with admin ai_config")
        else:
            debug_profile.ai_config_json = admin_profile.ai_config_json
            if admin_profile.primary_currency:
                debug_profile.primary_currency = admin_profile.primary_currency
            print("updated debug profile ai_config")

        now = _utcnow()
        ledger = db.scalar(
            select(Ledger).where(
                Ledger.user_id == debug.id,
                Ledger.external_id == LEDGER_EXTERNAL_ID,
            )
        )
        if ledger is None:
            ledger = Ledger(
                user_id=debug.id,
                external_id=LEDGER_EXTERNAL_ID,
                name=LEDGER_NAME,
                currency=admin_profile.primary_currency or "CNY",
                month_start_day=1,
            )
            db.add(ledger)
            db.flush()
            db.add(
                LedgerMember(
                    ledger_id=ledger.id,
                    user_id=debug.id,
                    role="owner",
                    joined_at=now,
                )
            )
            db.add(
                SyncChange(
                    user_id=debug.id,
                    ledger_id=ledger.id,
                    scope="ledger",
                    entity_type="ledger",
                    entity_sync_id=LEDGER_EXTERNAL_ID,
                    action="upsert",
                    payload_json={
                        "ledgerName": LEDGER_NAME,
                        "currency": ledger.currency,
                        "monthStartDay": 1,
                    },
                    updated_at=now,
                    updated_by_device_id="admin-bootstrap",
                    updated_by_user_id=debug.id,
                )
            )
            print(f"created ledger {LEDGER_NAME!r} ({LEDGER_EXTERNAL_ID})")
        else:
            print(f"ledger already exists: {ledger.name!r}")

        has_categories = db.scalar(
            select(UserCategoryProjection.sync_id).where(
                UserCategoryProjection.user_id == debug.id
            ).limit(1)
        )
        if has_categories is None:
            admin_cats = db.scalars(
                select(UserCategoryProjection)
                .where(UserCategoryProjection.user_id == admin.id)
                .order_by(
                    UserCategoryProjection.level.asc(),
                    UserCategoryProjection.sort_order.asc(),
                    UserCategoryProjection.name.asc(),
                )
            ).all()
            for cat in admin_cats:
                payload: dict[str, object] = {
                    "syncId": cat.sync_id,
                    "name": cat.name,
                    "kind": cat.kind,
                    "level": cat.level,
                    "sortOrder": cat.sort_order,
                    "icon": cat.icon,
                    "iconType": cat.icon_type,
                }
                if cat.parent_name:
                    payload["parentName"] = cat.parent_name
                if cat.parent_sync_id:
                    payload["parentSyncId"] = cat.parent_sync_id
                payload = {k: v for k, v in payload.items() if v is not None}

                change = SyncChange(
                    user_id=debug.id,
                    ledger_id=None,
                    scope="user",
                    entity_type="category",
                    entity_sync_id=cat.sync_id,
                    action="upsert",
                    payload_json=payload,
                    updated_at=now,
                    updated_by_device_id="admin-bootstrap",
                    updated_by_user_id=debug.id,
                )
                db.add(change)
                db.flush()
                apply_user_change_to_projection(db, user_id=debug.id, change=change)
            print(f"seeded {len(admin_cats)} categories from admin defaults")
        else:
            cat_count = db.scalar(
                select(func.count())
                .select_from(UserCategoryProjection)
                .where(UserCategoryProjection.user_id == debug.id)
            )
            print(f"categories already exist: {cat_count}")

        db.commit()
        print("bootstrap completed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
