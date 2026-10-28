"""Merge transaction_audit_log fork with upstream MCP workflows.

Revision ID: 0022_merge_audit_and_mcp
Revises: 0020_transaction_audit_log, 0021_mcp_workflows
"""

revision = "0022_merge_audit_and_mcp"
down_revision = ("0020_transaction_audit_log", "0021_mcp_workflows")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
