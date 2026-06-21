import { useState } from 'react'
import {
  Ticket, ArrowRightLeft, GitBranch, Clock, AlertTriangle,
  CheckCircle2, ChevronRight, Plus, Loader2, Send,
} from 'lucide-react'

// ── ServiceNow-style helpers ──────────────────────────────────────────────────
const STATE_STYLE = {
  new: { bg: 'bg-[#DEEBFF]', text: 'text-[#0747A6]', dot: 'bg-[#0052CC]' },
  in_progress: { bg: 'bg-[#DEEBFF]', text: 'text-[#0052CC]', dot: 'bg-[#0052CC]' },
  on_hold: { bg: 'bg-[#FFF0B3]', text: 'text-[#974F0C]', dot: 'bg-[#FF991F]' },
  resolved: { bg: 'bg-[#E3FCEF]', text: 'text-[#006644]', dot: 'bg-[#00875A]' },
  closed: { bg: 'bg-[#EBECF0]', text: 'text-[#42526E]', dot: 'bg-[#42526E]' },
  cancelled: { bg: 'bg-[#EBECF0]', text: 'text-[#42526E]', dot: 'bg-[#42526E]' },
}

const PRIORITY_STYLE = {
  '1': 'text-[#CD1316]',
  '2': 'text-[#E9494A]',
  '3': 'text-[#FF991F]',
  '4': 'text-[#006644]',
  '5': 'text-[#6B778C]',
}

const TYPE_BADGE = {
  incident: 'bg-[#FFEBE6] text-[#BF2600]',
  request: 'bg-[#EAE6FF] text-[#5243AA]',
  change: 'bg-[#DEEBFF] text-[#0747A6]',
  problem: 'bg-[#FFF0B3] text-[#974F0C]',
}

function StateLozenge({ state, label }) {
  const s = STATE_STYLE[state] || STATE_STYLE.new
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wide ${s.bg} ${s.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {label || state}
    </span>
  )
}

function SlaBadge({ ticket }) {
  if (!ticket.sla_due_at || ticket.is_closed) return null
  if (ticket.sla_breached) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#BF2600]">
        <AlertTriangle size={11} /> SLA breached
      </span>
    )
  }
  const secs = ticket.sla_seconds_remaining
  if (secs == null) return null
  const hrs = Math.floor(secs / 3600)
  const mins = Math.floor((secs % 3600) / 60)
  const txt = hrs > 0 ? `${hrs}h ${mins}m` : `${mins}m`
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-surface-400">
      <Clock size={11} /> SLA {txt}
    </span>
  )
}

const NOTE_DOT = {
  state_change: 'bg-[#0052CC]',
  system: 'bg-[#00875A]',
  work_note: 'bg-[#6554C0]',
  comment: 'bg-[#FF991F]',
}

function ActivityStream({ notes = [] }) {
  if (!notes.length) return null
  return (
    <div className="space-y-2.5">
      {notes.map((n) => (
        <div key={n.id} className="flex gap-2 text-xs">
          <span className={`mt-1 w-1.5 h-1.5 rounded-full shrink-0 ${NOTE_DOT[n.kind] || 'bg-surface-500'}`} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="font-medium text-surface-300">{n.author}</span>
              <span className="text-surface-600">·</span>
              <span className="text-surface-500 text-[10px]">{new Date(n.created_at).toLocaleString()}</span>
            </div>
            <p className="text-surface-400 mt-0.5 leading-relaxed whitespace-pre-wrap break-words">
              {renderInline(n.body)}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}

// Minimal **bold** + `code` rendering for work-note bodies.
function renderInline(text) {
  if (!text) return text
  const parts = String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return parts.map((p, i) => {
    if (p.startsWith('**') && p.endsWith('**')) return <strong key={i} className="text-surface-200">{p.slice(2, -2)}</strong>
    if (p.startsWith('`') && p.endsWith('`')) return <code key={i} className="px-1 rounded bg-surface-800 text-accent-cyan font-mono">{p.slice(1, -1)}</code>
    return p
  })
}

function SubTicketRow({ sub }) {
  const s = STATE_STYLE[sub.state] || STATE_STYLE.new
  return (
    <div className="rounded border border-surface-800 bg-surface-900/40 p-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-[11px] text-accent-cyan">{sub.number}</span>
        <StateLozenge state={sub.state} label={sub.state_label} />
      </div>
      <p className="text-xs text-surface-300 mt-1">{sub.short_description}</p>
      <p className="text-[10px] text-surface-500 mt-0.5">→ {sub.assignment_group_label}</p>
      {sub.action_result?.device && (
        <p className="text-[10px] text-[#36B37E] mt-1 flex items-center gap-1">
          <CheckCircle2 size={10} /> Attached as <code className="font-mono">{sub.action_result.device}</code>
        </p>
      )}
    </div>
  )
}

/**
 * ServiceNow-style ITSM ticket panel for the lab runner. Shows the parent
 * ticket with state/priority/SLA/assignment, an activity stream of work notes,
 * the sub-tickets raised to other teams, and the controls to drive state, raise
 * a sub-ticket, or transfer to another team.
 */
export default function ItsmTicketPanel({
  ticket,
  meta,
  config,
  busy = false,
  onTransition,
  onTransfer,
  onRaiseSubTicket,
}) {
  const [showRaise, setShowRaise] = useState(false)
  const [showTransfer, setShowTransfer] = useState(false)

  if (!ticket) return null

  const actions = meta?.actions || []
  const teams = meta?.teams || []
  const closeCodes = meta?.close_codes || []

  return (
    <div id="itsm-ticket-panel" className="fx-panel border-accent-cyan/20 p-3 space-y-3">
      {/* Header */}
      <div className="flex items-start gap-2">
        <Ticket size={16} className="text-accent-cyan mt-0.5 shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded font-semibold ${TYPE_BADGE[ticket.ticket_type] || TYPE_BADGE.incident}`}>
              {ticket.ticket_type_label}
            </span>
            <span className="font-mono text-xs text-surface-200">{ticket.number}</span>
          </div>
          <p className="text-sm text-surface-100 font-medium mt-1 leading-snug">{ticket.short_description}</p>
        </div>
      </div>

      {/* Meta row */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <StateLozenge state={ticket.state} label={ticket.state_label} />
        <span className={`text-[11px] font-semibold ${PRIORITY_STYLE[ticket.priority] || PRIORITY_STYLE['3']}`}>
          {ticket.priority_label}
        </span>
        <SlaBadge ticket={ticket} />
      </div>
      <div className="text-[11px] text-surface-400">
        Assignment group: <span className="text-surface-200 font-medium">{ticket.assignment_group_label}</span>
      </div>

      {ticket.description && (
        <div className="text-[11px] text-surface-400 bg-surface-950 border border-surface-800 rounded p-2.5 max-h-32 overflow-y-auto leading-relaxed whitespace-pre-wrap">
          {renderInline(ticket.description)}
        </div>
      )}

      {/* State transitions */}
      {!ticket.is_closed && ticket.allowed_transitions?.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {ticket.allowed_transitions.map((st) => {
            const label = (meta?.states || []).find((s) => s.value === st)?.label || st
            const isResolve = st === 'resolved' || st === 'closed'
            return (
              <button
                key={st}
                type="button"
                disabled={busy}
                onClick={() => {
                  if (isResolve) {
                    const code = closeCodes[0]?.value || 'closed_complete'
                    onTransition?.(st, { close_code: code })
                  } else {
                    onTransition?.(st)
                  }
                }}
                className="px-2 py-1 text-[11px] rounded border border-accent-cyan/30 bg-accent-cyan/10 text-accent-cyan hover:bg-accent-cyan/20 disabled:opacity-50 transition-colors inline-flex items-center gap-1"
              >
                {busy ? <Loader2 size={11} className="animate-spin" /> : <ChevronRight size={11} />}
                {label}
              </button>
            )
          })}
        </div>
      )}

      {/* Sub-tickets */}
      {ticket.children?.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] uppercase tracking-wide text-surface-500 flex items-center gap-1">
            <GitBranch size={11} /> Sub-tickets ({ticket.children.length})
          </p>
          {ticket.children.map((sub) => <SubTicketRow key={sub.id} sub={sub} />)}
        </div>
      )}

      {/* Action buttons */}
      {!ticket.is_closed && (
        <div className="flex flex-wrap gap-2 pt-1">
          <button
            type="button"
            onClick={() => { setShowRaise((v) => !v); setShowTransfer(false) }}
            className="btn-secondary px-2.5 py-1 text-[11px] inline-flex items-center gap-1"
          >
            <Plus size={12} /> Raise sub-ticket
          </button>
          <button
            type="button"
            onClick={() => { setShowTransfer((v) => !v); setShowRaise(false) }}
            className="btn-secondary px-2.5 py-1 text-[11px] inline-flex items-center gap-1"
          >
            <ArrowRightLeft size={12} /> Transfer
          </button>
        </div>
      )}

      {showRaise && (
        <RaiseSubTicketForm
          actions={actions}
          teams={teams}
          highlightActions={config?.allowed_actions || []}
          busy={busy}
          onSubmit={async (payload) => {
            await onRaiseSubTicket?.(payload)
            setShowRaise(false)
          }}
        />
      )}

      {showTransfer && (
        <TransferForm
          teams={teams}
          current={ticket.assignment_group}
          busy={busy}
          onSubmit={async (team, reason) => {
            await onTransfer?.(team, reason)
            setShowTransfer(false)
          }}
        />
      )}

      {/* Activity stream */}
      {ticket.notes?.length > 0 && (
        <div className="pt-2 border-t border-white/[0.06]">
          <p className="text-[10px] uppercase tracking-wide text-surface-500 mb-2">Activity</p>
          <ActivityStream notes={ticket.notes} />
        </div>
      )}
    </div>
  )
}

function RaiseSubTicketForm({ actions, highlightActions = [], busy, onSubmit }) {
  const [actionKind, setActionKind] = useState(highlightActions[0] || actions[0]?.kind || '')
  const [shortDesc, setShortDesc] = useState('')
  const [sizeGb, setSizeGb] = useState(50)
  const selected = actions.find((a) => a.kind === actionKind)

  const handleSubmit = (e) => {
    e.preventDefault()
    const params = {}
    if (actionKind === 'add_disk') params.size_gb = Number(sizeGb) || 50
    onSubmit?.({
      action_kind: actionKind,
      short_description: shortDesc.trim(),
      action_params: params,
      auto_fulfil: true,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="rounded border border-surface-800 bg-surface-950 p-2.5 space-y-2">
      <p className="text-[10px] uppercase tracking-wide text-surface-500">Raise a request to another team</p>
      <select
        value={actionKind}
        onChange={(e) => setActionKind(e.target.value)}
        className="input-field w-full text-xs py-1.5"
      >
        {actions.map((a) => (
          <option key={a.kind} value={a.kind}>{a.label} — {a.team_label}</option>
        ))}
      </select>
      {selected && (
        <p className="text-[10px] text-surface-500">Routed to <span className="text-surface-300">{selected.team_label}</span></p>
      )}
      {actionKind === 'add_disk' && (
        <label className="flex items-center gap-2 text-[11px] text-surface-400">
          Disk size (GiB)
          <input
            type="number" min="1" max="2000" value={sizeGb}
            onChange={(e) => setSizeGb(e.target.value)}
            className="input-field w-20 text-xs py-1"
          />
        </label>
      )}
      <input
        type="text"
        value={shortDesc}
        onChange={(e) => setShortDesc(e.target.value)}
        placeholder={selected?.default_short || 'Short description (optional)'}
        className="input-field w-full text-xs py-1.5"
      />
      <button type="submit" disabled={busy || !actionKind} className="btn-primary w-full py-1.5 text-xs disabled:opacity-50 inline-flex items-center justify-center gap-1">
        {busy ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
        Submit to team
      </button>
    </form>
  )
}

function TransferForm({ teams, current, busy, onSubmit }) {
  const [team, setTeam] = useState(teams.find((t) => t.value !== current)?.value || '')
  const [reason, setReason] = useState('')
  return (
    <form
      onSubmit={(e) => { e.preventDefault(); onSubmit?.(team, reason.trim()) }}
      className="rounded border border-surface-800 bg-surface-950 p-2.5 space-y-2"
    >
      <p className="text-[10px] uppercase tracking-wide text-surface-500">Transfer to another team</p>
      <select value={team} onChange={(e) => setTeam(e.target.value)} className="input-field w-full text-xs py-1.5">
        {teams.filter((t) => t.value !== current).map((t) => (
          <option key={t.value} value={t.value}>{t.label}</option>
        ))}
      </select>
      <input
        type="text" value={reason} onChange={(e) => setReason(e.target.value)}
        placeholder="Reason (optional)" className="input-field w-full text-xs py-1.5"
      />
      <button type="submit" disabled={busy || !team} className="btn-primary w-full py-1.5 text-xs disabled:opacity-50 inline-flex items-center justify-center gap-1">
        {busy ? <Loader2 size={12} className="animate-spin" /> : <ArrowRightLeft size={12} />}
        Transfer ticket
      </button>
    </form>
  )
}
