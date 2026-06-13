import { Clock, CheckCircle2, RotateCcw, MessageSquare, AlertCircle } from 'lucide-react'

export const STATUS_STYLES = {
  'To Do': { bg: 'bg-[#DFE1E6]', text: 'text-[#42526E]', dot: 'bg-[#42526E]' },
  'In Progress': { bg: 'bg-[#DEEBFF]', text: 'text-[#0052CC]', dot: 'bg-[#0052CC]' },
  'On Hold': { bg: 'bg-[#FFF0B3]', text: 'text-[#974F0C]', dot: 'bg-[#FF991F]' },
  'Done': { bg: 'bg-[#E3FCEF]', text: 'text-[#006644]', dot: 'bg-[#00875A]' },
  'Closed': { bg: 'bg-[#EBECF0]', text: 'text-[#42526E]', dot: 'bg-[#42526E]' },
}

export const PRIORITY_STYLES = {
  Highest: { color: 'text-[#CD1316]', label: 'Highest' },
  High: { color: 'text-[#E9494A]', label: 'High' },
  Medium: { color: 'text-[#FF991F]', label: 'Medium' },
  Low: { color: 'text-[#006644]', label: 'Low' },
  Lowest: { color: 'text-[#006644]', label: 'Lowest' },
}

const ACTIVITY_STYLES = {
  created: { icon: CheckCircle2, color: 'text-[#00875A]', bg: 'bg-[#E3FCEF]' },
  in_progress: { icon: Clock, color: 'text-[#0052CC]', bg: 'bg-[#DEEBFF]' },
  reset: { icon: RotateCcw, color: 'text-[#974F0C]', bg: 'bg-[#FFF0B3]' },
  completed: { icon: CheckCircle2, color: 'text-[#00875A]', bg: 'bg-[#E3FCEF]' },
  cancelled: { icon: AlertCircle, color: 'text-[#42526E]', bg: 'bg-[#EBECF0]' },
  comment: { icon: MessageSquare, color: 'text-[#6554C0]', bg: 'bg-[#EAE6FF]' },
  webhook: { icon: Clock, color: 'text-[#0052CC]', bg: 'bg-[#DEEBFF]' },
}

export function PriorityIcon({ priority, className = '' }) {
  const p = PRIORITY_STYLES[priority] || PRIORITY_STYLES.Medium
  return (
    <span className={`inline-flex items-center gap-1.5 text-sm ${p.color} ${className}`}>
      <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
        <path d="M8 1l2.5 5.5H14L10 10.5 11.5 16 8 13 4.5 16 6 10.5 2 6.5h3.5z" />
      </svg>
      {p.label}
    </span>
  )
}

export function StatusLozenge({ status, className = '' }) {
  const s = STATUS_STYLES[status] || STATUS_STYLES['To Do']
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wide ${s.bg} ${s.text} ${className}`}>
      <span className={`w-2 h-2 rounded-full ${s.dot}`} />
      {status}
    </span>
  )
}

export function ActivityItem({ action, jiraStatus, createdAt, compact = false, light = false }) {
  const style = ACTIVITY_STYLES[action] || ACTIVITY_STYLES.webhook
  const Icon = style.icon
  const titleClass = light ? 'text-[#172B4D]' : 'text-surface-200'
  const metaClass = light ? 'text-[#6B778C]' : 'text-surface-500'
  return (
    <div className={`flex gap-2 ${compact ? 'text-xs' : 'text-sm'}`}>
      <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${style.bg}`}>
        <Icon size={compact ? 12 : 14} className={style.color} />
      </div>
      <div className="min-w-0 flex-1">
        <p className={titleClass}>
          <span className="font-medium capitalize">{action.replace(/_/g, ' ')}</span>
          {jiraStatus && (
            <span className="inline-flex items-center gap-1 ml-1">
              → <StatusLozenge status={jiraStatus} className="!text-[10px] !py-0" />
            </span>
          )}
        </p>
        {createdAt && (
          <p className={`text-[10px] ${metaClass} mt-0.5`}>
            {new Date(createdAt).toLocaleString()}
          </p>
        )}
      </div>
    </div>
  )
}
