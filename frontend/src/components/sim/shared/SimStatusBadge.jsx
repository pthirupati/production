const LIGHT = {
  success: 'sim-badge sim-badge-success',
  applied: 'sim-badge sim-badge-success',
  up: 'sim-badge sim-badge-success',
  ok: 'sim-badge sim-badge-success',
  running: 'sim-badge sim-badge-running',
  planned: 'sim-badge sim-badge-running',
  pending: 'sim-badge sim-badge-pending',
  warning: 'sim-badge sim-badge-pending',
  error: 'sim-badge sim-badge-error',
  failed: 'sim-badge sim-badge-error',
  errored: 'sim-badge sim-badge-error',
  down: 'sim-badge sim-badge-error',
  firing: 'sim-badge sim-badge-error',
  info: 'sim-badge sim-badge-info',
  inactive: 'sim-badge sim-badge-inactive',
  normal: 'sim-badge sim-badge-inactive',
  queued: 'sim-badge sim-badge-queued',
  processing: 'sim-badge sim-badge-running',
}

export default function SimStatusBadge({ status, label, className = '' }) {
  const key = String(status || label || '').toLowerCase().replace(/\s+/g, '_')
  const cls = LIGHT[key] || LIGHT.info
  const text = label || status
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border capitalize ${cls} ${className}`.trim()}>
      {text}
    </span>
  )
}
