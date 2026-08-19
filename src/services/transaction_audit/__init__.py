"""交易修改记录审计 — 写入 sync/push 与 write 路径,供 read API 查询。"""

from .writer import record_transaction_audit_for_sync_change

__all__ = ["record_transaction_audit_for_sync_change"]
