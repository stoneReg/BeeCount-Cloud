import { AuditRecentPanel } from '../../components/audit/TransactionAuditPanel'
import { useAuth } from '../../context/AuthContext'

/** 云端修改记录总览(首页 + 设置 · 健康页均可进入)。 */
export function SettingsAuditPage() {
  const { token } = useAuth()
  if (!token) return null
  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <AuditRecentPanel token={token} />
    </div>
  )
}
