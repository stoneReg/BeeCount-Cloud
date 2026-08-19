import { AuditRecentPanel } from '../../components/audit/TransactionAuditPanel'
import { useAuth } from '../../context/AuthContext'

/** 云端修改记录总览(设置内入口,非首页)。 */
export function SettingsAuditPage() {
  const { token } = useAuth()
  if (!token) return null
  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <AuditRecentPanel token={token} />
    </div>
  )
}
