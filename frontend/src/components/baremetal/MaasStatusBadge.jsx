import { Power, Check, X } from 'lucide-react'

export const TRANSIENT_STATUSES = new Set([
  'Commissioning',
  'Deploying',
  'Releasing',
  'Testing',
  'Entering rescue mode',
  'Exiting rescue mode',
])

const READY_LIKE = new Set(['Ready', 'Deployed'])
const FAILED_LIKE = new Set([
  'Failed',
  'Broken',
  'Failed commissioning',
  'Failed deployment',
  'Failed testing',
])

export function statusClass(status) {
  if (TRANSIENT_STATUSES.has(status)) return 'maas-badge-transient'
  if (READY_LIKE.has(status)) return status === 'Deployed' ? 'maas-badge-deployed' : 'maas-badge-ready'
  if (FAILED_LIKE.has(status)) return status === 'Broken' ? 'maas-badge-broken' : 'maas-badge-failed'
  if (status === 'Rescue mode') return 'maas-badge-rescue'
  if (status === 'Allocated') return 'maas-badge-allocated'
  return 'maas-badge-neutral'
}

export function MaasStatusBadge({ status }) {
  const s = status || 'Unknown'
  const transient = TRANSIENT_STATUSES.has(s)
  const ok = READY_LIKE.has(s)
  const bad = FAILED_LIKE.has(s)
  return (
    <span className={`maas-badge ${statusClass(s)}`} title={s}>
      {transient && <span className="maas-spinner" aria-hidden />}
      {ok && !transient && <Check size={11} strokeWidth={3} />}
      {bad && <X size={11} strokeWidth={3} />}
      {s}
    </span>
  )
}

export function PowerIcon({ power }) {
  const p = (power || 'unknown').toLowerCase()
  const cls = p === 'on' ? 'maas-power-on' : p === 'off' ? 'maas-power-off' : 'maas-power-unknown'
  return (
    <span className={`maas-power-icon ${cls}`} title={`Power ${p}`}>
      <Power size={12} />
      {p}
    </span>
  )
}

export default MaasStatusBadge
