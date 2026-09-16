import type { TransactionAuditEntry, TransactionAuditFieldChange } from '@beecount/api-client'
import type { LucideIcon } from 'lucide-react'
import { MinusCircle, PencilLine, PlusCircle } from 'lucide-react'

export type AuditActionKind = 'create' | 'update' | 'delete'

export type AuditActionMeta = {
  kind: AuditActionKind
  label: string
  icon: LucideIcon
  cardClass: string
  iconWrapClass: string
  iconClass: string
  badgeClass: string
}

const FIELD_ORDER = [
  'type',
  'amount',
  'categoryName',
  'accountName',
  'fromAccountName',
  'toAccountName',
  'happenedAt',
  'note',
  'tags',
]

const SUMMARY_FIELDS = new Set(FIELD_ORDER)

const SKIP_IF_PRESENT: Record<string, string> = {
  categoryId: 'categoryName',
  accountId: 'accountName',
  fromAccountId: 'fromAccountName',
  toAccountId: 'toAccountName',
  tagIds: 'tags',
}

const PAYLOAD_FALLBACK: Array<{ key: string; label: string }> = [
  { key: 'type', label: '类型' },
  { key: 'amount', label: '金额' },
  { key: 'categoryName', label: '分类' },
  { key: 'accountName', label: '账户' },
  { key: 'happenedAt', label: '时间' },
  { key: 'note', label: '备注' },
]

export function resolveAuditActionKind(action: string): AuditActionKind {
  if (action === 'create') return 'create'
  if (action === 'delete') return 'delete'
  return 'update'
}

export function getAuditActionMeta(action: string): AuditActionMeta {
  const kind = resolveAuditActionKind(action)
  if (kind === 'create') {
    return {
      kind,
      label: '新增记录',
      icon: PlusCircle,
      cardClass: 'border-emerald-500/25 bg-emerald-500/[0.04]',
      iconWrapClass: 'bg-emerald-500/15',
      iconClass: 'text-emerald-600 dark:text-emerald-400',
      badgeClass: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300',
    }
  }
  if (kind === 'delete') {
    return {
      kind,
      label: '删除记录',
      icon: MinusCircle,
      cardClass: 'border-red-500/25 bg-red-500/[0.04]',
      iconWrapClass: 'bg-red-500/15',
      iconClass: 'text-red-600 dark:text-red-400',
      badgeClass: 'bg-red-500/15 text-red-700 dark:text-red-300',
    }
  }
  return {
    kind,
    label: '修改记录',
    icon: PencilLine,
    cardClass: 'border-sky-500/25 bg-sky-500/[0.04]',
    iconWrapClass: 'bg-sky-500/15',
    iconClass: 'text-sky-600 dark:text-sky-400',
    badgeClass: 'bg-sky-500/15 text-sky-700 dark:text-sky-300',
  }
}

export function formatAuditWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}

function accountLabel(entry: TransactionAuditEntry): string {
  if (entry.user_display_name) return entry.user_display_name
  if (entry.user_email) return entry.user_email
  return '—'
}

function deviceLabel(entry: TransactionAuditEntry): string {
  if (entry.device_name) return entry.device_name
  if (entry.updated_by_device_id) return entry.updated_by_device_id.slice(0, 8)
  return '—'
}

/** 归属：账号 — 设备 */
export function formatAuditAttribution(entry: TransactionAuditEntry): string {
  const account = accountLabel(entry)
  const device = deviceLabel(entry)
  if (account === '—' && device === '—') return '—'
  if (account === '—') return device
  if (device === '—') return account
  return `${account} — ${device}`
}

function formatFieldValue(field: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (field === 'type') {
    const s = String(value).toLowerCase()
    if (s === 'expense') return '支出'
    if (s === 'income') return '收入'
    if (s === 'transfer') return '转账'
  }
  if (field === 'happenedAt') {
    try {
      return new Date(String(value)).toLocaleString('zh-CN', { hour12: false })
    } catch {
      return String(value)
    }
  }
  if (Array.isArray(value)) {
    return value.map((v) => String(v)).filter(Boolean).join('、') || '—'
  }
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function filterChanges(
  changes: TransactionAuditFieldChange[],
  kind: AuditActionKind,
): TransactionAuditFieldChange[] {
  const fields = new Set(changes.map((c) => c.field))
  let filtered = changes.filter((c) => {
    const skip = SKIP_IF_PRESENT[c.field]
    return !(skip && fields.has(skip))
  })
  if (kind === 'create' || kind === 'delete') {
    const summary = filtered.filter((c) => SUMMARY_FIELDS.has(c.field))
    if (summary.length > 0) filtered = summary
  }
  const order = new Map(FIELD_ORDER.map((f, i) => [f, i]))
  return [...filtered].sort((a, b) => {
    const ai = order.get(a.field) ?? 999
    const bi = order.get(b.field) ?? 999
    if (ai !== bi) return ai - bi
    return a.field.localeCompare(b.field)
  })
}

function payloadFallbackLines(entry: TransactionAuditEntry): Array<{ label: string; text: string }> {
  const lines: Array<{ label: string; text: string }> = []
  for (const { key, label } of PAYLOAD_FALLBACK) {
    const raw = entry.payload[key]
    if (raw === null || raw === undefined || raw === '') continue
    const text = formatFieldValue(key, raw)
    if (text === '—') continue
    lines.push({ label, text })
  }
  return lines
}

export type AuditPreviewLine = {
  actionLabel: string
  actionClass: string
  summary: string
  time: string
}

/** 首页预览用单行摘要 */
export function buildAuditPreviewLine(entry: TransactionAuditEntry): AuditPreviewLine {
  const meta = getAuditActionMeta(entry.action)
  const changes = buildAuditChangeLines(entry)
  let summary = ''
  if (changes.length > 0) {
    summary = changes
      .slice(0, 2)
      .map((line) => `${line.label} ${line.text}`)
      .join(' · ')
  } else {
    summary = formatAuditAttribution(entry)
  }
  if (entry.ledger_name) {
    summary = summary ? `${entry.ledger_name} · ${summary}` : entry.ledger_name
  }
  return {
    actionLabel: meta.label,
    actionClass: meta.badgeClass,
    summary: summary || '—',
    time: formatAuditWhen(entry.updated_at),
  }
}

export type AuditChangeLine = {
  label: string
  text: string
}

export function buildAuditChangeLines(entry: TransactionAuditEntry): AuditChangeLine[] {
  const kind = resolveAuditActionKind(entry.action)
  const changes = filterChanges(entry.changes, kind)

  const fromChanges = changes
    .map((c) => {
      const from = formatFieldValue(c.field, c.from_value)
      const to = formatFieldValue(c.field, c.to_value)
      if (kind === 'create') {
        return { label: c.label, text: to }
      }
      if (kind === 'delete') {
        return { label: c.label, text: from }
      }
      return { label: c.label, text: `${from} → ${to}` }
    })
    .filter((line) => line.text !== '—')

  if (fromChanges.length > 0) return fromChanges

  if (kind === 'create' || kind === 'delete') {
    const fallback = payloadFallbackLines(entry)
    if (fallback.length > 0) return fallback.map(({ label, text }) => ({ label, text }))
  }

  return []
}
