import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { fetchAuditRecent, type TransactionAuditEntry } from '@beecount/api-client'
import { cn } from '@beecount/ui'
import { ChevronRight, History, Loader2 } from 'lucide-react'

import { useAuth } from '../../context/AuthContext'
import { useLedgers } from '../../context/LedgersContext'
import { buildAuditPreviewLine } from './auditDisplay'

function AuditPreviewRow({ entry }: { entry: TransactionAuditEntry }) {
  const line = buildAuditPreviewLine(entry)
  return (
    <li className="flex items-center gap-3 px-4 py-2.5">
      <span
        className={cn(
          'shrink-0 rounded-md px-2 py-0.5 text-[11px] font-semibold leading-none',
          line.actionClass,
        )}
      >
        {line.actionLabel}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-foreground/90">{line.summary}</p>
      </div>
      <time className="shrink-0 text-[11px] tabular-nums text-muted-foreground">{line.time}</time>
    </li>
  )
}

/** 首页修改记录预览：展示最近 5 条,整卡点击进入详情页。 */
export function HomeAuditPreview() {
  const navigate = useNavigate()
  const { token } = useAuth()
  const { activeLedgerId } = useLedgers()
  const [items, setItems] = useState<TransactionAuditEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token) {
      setItems([])
      setLoading(false)
      return
    }
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const page = await fetchAuditRecent(token, {
          ledgerId: activeLedgerId || undefined,
          limit: 5,
        })
        if (!cancelled) setItems(page.items)
      } catch {
        if (!cancelled) setItems([])
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token, activeLedgerId])

  if (!token) return null

  return (
    <button
      type="button"
      onClick={() => navigate('/app/settings/audit')}
      className="group w-full rounded-xl border border-border/60 bg-card text-left transition-colors hover:border-border hover:bg-muted/20"
    >
      <div className="flex items-center justify-between gap-3 border-b border-border/50 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-medium">
          <History className="h-4 w-4 text-muted-foreground" />
          修改记录
        </div>
        <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
      </div>

      {loading ? (
        <div className="flex items-center gap-2 px-4 py-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          加载中…
        </div>
      ) : items.length === 0 ? (
        <div className="px-4 py-6 text-sm text-muted-foreground">暂无修改记录</div>
      ) : (
        <ul className="divide-y divide-border/40">
          {items.map((entry) => (
            <AuditPreviewRow key={entry.id} entry={entry} />
          ))}
        </ul>
      )}
    </button>
  )
}
