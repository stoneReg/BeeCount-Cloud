import { useCallback, useEffect, useState } from 'react'
import {
  fetchAuditRecent,
  fetchTransactionHistory,
  type TransactionAuditEntry,
} from '@beecount/api-client'
import { Button, useT } from '@beecount/ui'
import { History, Loader2 } from 'lucide-react'

function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}

function actionLabel(action: string): string {
  if (action === 'create') return '创建'
  if (action === 'delete') return '删除'
  return '修改'
}

function actorLine(entry: TransactionAuditEntry): string {
  const parts: string[] = []
  if (entry.device_name) parts.push(entry.device_name)
  else if (entry.updated_by_device_id) parts.push(entry.updated_by_device_id.slice(0, 8))
  if (entry.user_display_name) parts.push(entry.user_display_name)
  else if (entry.user_email) parts.push(entry.user_email)
  return parts.join(' · ') || '—'
}

function ChangeList({ entry }: { entry: TransactionAuditEntry }) {
  if (entry.action === 'create') {
    const amount = entry.payload.amount
    const note = entry.payload.note as string | undefined
    return (
      <div className="text-xs text-muted-foreground">
        {typeof amount === 'number' ? `金额 ${amount}` : null}
        {note ? ` · ${note}` : null}
      </div>
    )
  }
  if (entry.changes.length === 0) {
    return <div className="text-xs text-muted-foreground">—</div>
  }
  return (
    <ul className="space-y-0.5 text-xs text-muted-foreground">
      {entry.changes.map((c) => (
        <li key={c.field}>
          {c.label}: {String(c.from_value ?? '—')} → {String(c.to_value ?? '—')}
        </li>
      ))}
    </ul>
  )
}

export function TransactionAuditTimeline({
  token,
  ledgerId,
  syncId,
  compact = false,
}: {
  token: string
  ledgerId: string
  syncId: string
  compact?: boolean
}) {
  const t = useT()
  const [items, setItems] = useState<TransactionAuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [beforeId, setBeforeId] = useState<number | null>(null)

  const load = useCallback(
    async (append = false) => {
      setLoading(true)
      setError(null)
      try {
        const page = await fetchTransactionHistory(token, ledgerId, syncId, {
          limit: compact ? 20 : 50,
          beforeId: append && beforeId ? beforeId : undefined,
        })
        setItems((prev) => (append ? [...prev, ...page.items] : page.items))
        setHasMore(page.has_more)
        setBeforeId(page.next_before_id)
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
      } finally {
        setLoading(false)
      }
    },
    [token, ledgerId, syncId, compact, beforeId],
  )

  useEffect(() => {
    void load(false)
  }, [token, ledgerId, syncId])

  if (loading && items.length === 0) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        {t('common.loading')}
      </div>
    )
  }
  if (error) {
    return <div className="py-3 text-sm text-destructive">{error}</div>
  }
  if (items.length === 0) {
    return <div className="py-3 text-sm text-muted-foreground">暂无修改记录</div>
  }

  return (
    <div className="space-y-3">
      {items.map((entry) => (
        <div key={entry.id} className="rounded-lg border border-border/60 bg-muted/10 px-3 py-2">
          <div className="flex items-center justify-between gap-2 text-xs">
            <span className="font-medium text-foreground">{actionLabel(entry.action)}</span>
            <span className="text-muted-foreground">{formatWhen(entry.updated_at)}</span>
          </div>
          <div className="mt-1 text-[11px] text-muted-foreground">{actorLine(entry)}</div>
          <div className="mt-2">
            <ChangeList entry={entry} />
          </div>
        </div>
      ))}
      {hasMore ? (
        <Button variant="ghost" size="sm" disabled={loading} onClick={() => void load(true)}>
          {loading ? <Loader2 className="mr-2 h-3 w-3 animate-spin" /> : null}
          加载更多
        </Button>
      ) : null}
    </div>
  )
}

export function AuditRecentPanel({ token, ledgerId }: { token: string; ledgerId?: string }) {
  const [items, setItems] = useState<TransactionAuditEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const page = await fetchAuditRecent(token, { ledgerId, limit: 100 })
        if (!cancelled) setItems(page.items)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token, ledgerId])

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        加载中…
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium">
        <History className="h-4 w-4" />
        修改记录
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">暂无记录</p>
      ) : (
        items.map((entry) => (
          <div key={entry.id} className="rounded-lg border border-border/60 px-3 py-2 text-sm">
            <div className="flex justify-between gap-2 text-xs text-muted-foreground">
              <span>
                {entry.ledger_name || entry.ledger_id} · {actionLabel(entry.action)}
              </span>
              <span>{formatWhen(entry.updated_at)}</span>
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground">{actorLine(entry)}</div>
            <ChangeList entry={entry} />
          </div>
        ))
      )}
    </div>
  )
}
