import { useCallback, useEffect, useState } from 'react'
import {
  fetchAuditRecent,
  fetchTransactionHistory,
  type TransactionAuditEntry,
} from '@beecount/api-client'
import { Button, cn, useT } from '@beecount/ui'
import { History, Loader2 } from 'lucide-react'

import {
  buildAuditChangeLines,
  formatAuditAttribution,
  formatAuditWhen,
  getAuditActionMeta,
} from './auditDisplay'

function AuditEntryCard({
  entry,
  showLedger = false,
}: {
  entry: TransactionAuditEntry
  showLedger?: boolean
}) {
  const meta = getAuditActionMeta(entry.action)
  const Icon = meta.icon
  const changes = buildAuditChangeLines(entry)

  return (
    <div className={cn('rounded-xl border px-4 py-3 transition-colors', meta.cardClass)}>
      <div className="flex gap-3">
        <div
          className={cn(
            'mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full',
            meta.iconWrapClass,
          )}
        >
          <Icon className={cn('h-4 w-4', meta.iconClass)} />
        </div>

        <div className="min-w-0 flex-1 space-y-2.5">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                类型
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={cn(
                    'inline-flex rounded-md px-2 py-0.5 text-xs font-semibold',
                    meta.badgeClass,
                  )}
                >
                  {meta.label}
                </span>
                {showLedger && entry.ledger_name ? (
                  <span className="text-xs text-muted-foreground">{entry.ledger_name}</span>
                ) : null}
              </div>
            </div>
            <time className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
              {formatAuditWhen(entry.updated_at)}
            </time>
          </div>

          <div>
            <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              归属
            </div>
            <div className="mt-0.5 text-sm text-foreground/90">{formatAuditAttribution(entry)}</div>
          </div>

          {changes.length > 0 ? (
            <div>
              <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                修改内容
              </div>
              <ul className="mt-1.5 space-y-1">
                {changes.map((line) => (
                  <li
                    key={`${entry.id}-${line.label}-${line.text}`}
                    className="flex gap-2 text-sm leading-snug"
                  >
                    <span className="shrink-0 text-muted-foreground">{line.label}：</span>
                    <span className="min-w-0 break-all text-foreground/90">{line.text}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : meta.kind === 'delete' ? (
            <div className="text-sm text-muted-foreground">（历史删除记录未留存账单详情）</div>
          ) : null}
        </div>
      </div>
    </div>
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
        <AuditEntryCard key={entry.id} entry={entry} />
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
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm font-medium">
        <History className="h-4 w-4" />
        修改记录
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">暂无记录</p>
      ) : (
        <div className="space-y-3">
          {items.map((entry) => (
            <AuditEntryCard key={entry.id} entry={entry} showLedger />
          ))}
        </div>
      )}
    </div>
  )
}
