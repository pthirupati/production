const STYLES = {
  success: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/35',
  applied: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/35',
  up: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/35',
  ok: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/35',
  running: 'bg-sky-500/15 text-sky-300 border-sky-500/35',
  planned: 'bg-sky-500/15 text-sky-300 border-sky-500/35',
  pending: 'bg-amber-500/15 text-amber-300 border-amber-500/35',
  warning: 'bg-amber-500/15 text-amber-300 border-amber-500/35',
  error: 'bg-red-500/15 text-red-400 border-red-500/35',
  failed: 'bg-red-500/15 text-red-400 border-red-500/35',
  errored: 'bg-red-500/15 text-red-400 border-red-500/35',
  down: 'bg-red-500/15 text-red-400 border-red-500/35',
  firing: 'bg-red-500/15 text-red-400 border-red-500/35',
  info: 'bg-blue-500/15 text-blue-300 border-blue-500/35',
  inactive: 'bg-slate-500/15 text-slate-400 border-slate-500/35',
  normal: 'bg-slate-500/15 text-slate-400 border-slate-500/35',
  queued: 'bg-violet-500/15 text-violet-300 border-violet-500/35',
  processing: 'bg-sky-500/15 text-sky-300 border-sky-500/35',
}

export default function SimStatusBadge({ status, label, className = '' }) {
  const key = String(status || label || '').toLowerCase().replace(/\s+/g, '_')
  const cls = STYLES[key] || STYLES.info
  const text = label || status
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border capitalize ${cls} ${className}`.trim()}>
      {text}
    </span>
  )
}
