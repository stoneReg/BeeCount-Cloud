"""transaction_audit_log — 交易修改审计(独立于 sync_changes compact)

Revision ID: 0020_transaction_audit_log
Revises: 0019_account_hidden
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op


revision = "0020_transaction_audit_log"
down_revision = "0019_account_hidden"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transaction_audit_log",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("change_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("ledger_id", sa.String(36), sa.ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_sync_id", sa.String(255), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by_device_id", sa.String(36), nullable=True),
        sa.Column("updated_by_user_id", sa.String(36), nullable=True),
        sa.Column("field_diff_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_transaction_audit_log_change_id", "transaction_audit_log", ["change_id"], unique=True)
    op.create_index("ix_transaction_audit_log_ledger_id", "transaction_audit_log", ["ledger_id"])
    op.create_index("ix_transaction_audit_log_entity_sync_id", "transaction_audit_log", ["entity_sync_id"])
    op.create_index("ix_transaction_audit_log_action", "transaction_audit_log", ["action"])
    op.create_index("ix_transaction_audit_log_updated_at", "transaction_audit_log", ["updated_at"])
    op.create_index("ix_transaction_audit_log_updated_by_user_id", "transaction_audit_log", ["updated_by_user_id"])
    op.create_index(
        "idx_tx_audit_ledger_entity_id",
        "transaction_audit_log",
        ["ledger_id", "entity_sync_id", "id"],
    )
    op.create_index(
        "idx_tx_audit_ledger_updated",
        "transaction_audit_log",
        ["ledger_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_tx_audit_ledger_updated", table_name="transaction_audit_log")
    op.drop_index("idx_tx_audit_ledger_entity_id", table_name="transaction_audit_log")
    op.drop_table("transaction_audit_log")
