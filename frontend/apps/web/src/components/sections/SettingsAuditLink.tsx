import { Link } from 'react-router-dom'

import { ChevronRight, History } from 'lucide-react'

/** 健康页底部链到修改记录总览。 */
export function SettingsAuditLink() {
  return (
    <Link
      to="/app/settings/audit"
      className="block rounded-xl border border-border/60 bg-card p-4 transition-colors hover:bg-muted/20"
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium">
            <History className="h-4 w-4" />
            修改记录
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            查看 BeeCount Cloud 同步账单的修改历史(设备、时间与字段变更)
          </p>
        </div>
        <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
      </div>
    </Link>
  )
}
