import { useState, useEffect, useCallback } from 'react'
import { adminApi } from '../../api/admin'
import { AdminPageHeader } from '../../components/design'
import {
  LifeBuoy, Search, User, Target, X, AlertTriangle, Clock, GitBranch,
  ArrowRightLeft, Plus, Send, MessageSquare, ChevronRight, Loader2, CheckCircle2,
} from 'lucide-react'
import toast from 'react-hot-toast'

// ── ServiceNow-style lozenge styling (mirrors ItsmTicketPanel) ─────────────────
const STATE_STYLE = {
  new: 'bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/20',
  in_progress: 'bg-blue-500/15 text-blue-300 border border-blue-500/20',
  on_hold: 'bg-amber-500/15 text-amber-300 border border-amber-500/20',
  resolved: 'bg-accent-green/15 text-accent-green border border-accent-green/20',
  closed: 'bg-surface-700 text-surface-400 border border-surface-600/40',
  cancelled: 'bg-surface-700 text-surface-400 border border-surface-600/40',
}
const PRIORITY_STYLE = {
  '1': 'text-red-400', '2': 'text-red-300', '3': 'text-amber-400',
  '4': 'text-accent-green', '5': 'text-surface-400',
}
const TYPE_BADGE = {
  incident: 'bg-red-500/15 text-red-300',
  request: 'bg-purple-500/15 text-purple-300',
  change: 'bg-blue-500/15 text-blue-300',
  problem: 'bg-amber-500/15 text-amber-300',
}
const NOTE_DOT = {
  state_change: 'bg-blue-400', system: 'bg-accent-green',
  work_note: 'bg-purple-400', comment: 'bg-amber-400',
}

function StateLozenge({ state, label }) {
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${STATE_STYLE[state] || STATE_STYLE.new}`}>
      {label || state}
    </span>
  )
}

function SlaBadge({ ticket }) {
  if (!ticket.sla_due_at || ticket.is_closed) return null
  if (ticket.sla_breached) {
    return <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-red-400"><AlertTriangle size={11} /> SLA breached</span>
  }
  const secs = ticket.sla_seconds_remaining
  if (secs == null) return null
  const hrs = Math.floor(secs / 3600)
  const mins = Math.floor((secs % 3600) / 60)
  return <span className="inline-flex items-center gap-1 text-[11px] text-surface-400"><Clock size={11} /> SLA {hrs > 0 ? `${hrs}h ${mins}m` : `${mins}m`}</span>
}

// Minimal **bold** + `code` rendering for work-note bodies (mirrors the user panel).
function renderInline(text) {
  if (!text) return text
  return String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((p, i) => {
    if (p.startsWith('**') && p.endsWith('**')) return <strong key={i} className="text-surface-200">{p.slice(2, -2)}</strong>
    if (p.startsWith('`') && p.endsWith('`')) return <code key={i} className="px-1 rounded bg-surface-800 text-accent-cyan font-mono">{p.slice(1, -1)}</code>
    return p
  })
}

export default function AdminItsm() {
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState({ total: 0, open_count: 0, closed_count: 0, sla_breached_count: 0 })
  const [meta, setMeta] = useState({ states: [], ticket_types: [], teams: [], priorities: [], close_codes: [], actions: [] })
  const [search, setSearch] = useState('')
  const [stateFilter, setStateFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [teamFilter, setTeamFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [selectedId, setSelectedId] = useState(null)

  const loadTickets = useCallback(async () => {
    setLoading(true)
    try {
      const data = await adminApi.getItsmTickets({
        search, state: stateFilter, ticket_type: typeFilter,
        team: teamFilter, status: statusFilter,
      })
      setTickets(data.tickets || [])
      setStats(data)
    } catch {
      toast.error('Failed to load ITSM tickets')
    } finally {
      setLoading(false)
    }
  }, [search, stateFilter, typeFilter, teamFilter, statusFilter])

  useEffect(() => {
    adminApi.getItsmMeta().then(setMeta).catch(() => {})
  }, [])

  // Debounce list reloads on filter/search change.
  useEffect(() => {
    const t = setTimeout(loadTickets, 250)
    return () => clearTimeout(t)
  }, [loadTickets])

  if (loading && !tickets.length) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="ITSM Tickets"
        subtitle={`${stats.open_count} open · ${stats.closed_count} closed · ${stats.total} total${stats.sla_breached_count ? ` · ${stats.sla_breached_count} SLA breached` : ''}`}
        actions={
          <button onClick={loadTickets} className="btn-secondary flex items-center gap-2 text-sm">Refresh</button>
        }
      />

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" size={16} />
          <input
            type="text"
            placeholder="Search by number, user, scenario, description..."
            className="input-field pl-10 w-full"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select className="input-field w-auto" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All</option>
          <option value="open">Open</option>
          <option value="active">Active (working)</option>
          <option value="closed">Closed</option>
        </select>
        <select className="input-field w-auto" value={stateFilter} onChange={(e) => setStateFilter(e.target.value)}>
          <option value="">All states</option>
          {meta.states.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        <select className="input-field w-auto" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">All types</option>
          {meta.ticket_types.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        <select className="input-field w-auto" value={teamFilter} onChange={(e) => setTeamFilter(e.target.value)}>
          <option value="">All teams</option>
          {meta.teams.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </div>

      <div className="space-y-3">
        {tickets.map(t => (
          <button
            key={t.id}
            type="button"
            onClick={() => setSelectedId(t.id)}
            className="glass-card p-4 w-full text-left hover:border-accent-cyan/30 transition-colors"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className={`text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded font-semibold ${TYPE_BADGE[t.ticket_type] || TYPE_BADGE.incident}`}>
                    {t.ticket_type_label}
                  </span>
                  <span className="font-mono text-accent-cyan font-semibold text-sm">{t.number}</span>
                  <StateLozenge state={t.state} label={t.state_label} />
                  <span className={`text-[11px] font-semibold ${PRIORITY_STYLE[t.priority] || PRIORITY_STYLE['3']}`}>{t.priority_label}</span>
                  {t.sla_breached && !t.is_closed && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-red-400"><AlertTriangle size={10} /> SLA</span>
                  )}
                </div>
                <p className="text-sm font-medium text-white">{t.short_description}</p>
                <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-surface-500">
                  <span className="flex items-center gap-1"><User size={12} /> {t.user?.username} ({t.user?.email})</span>
                  {t.scenario && <span className="flex items-center gap-1"><Target size={12} /> {t.scenario.slug}</span>}
                  <span>{t.assignment_group_label}</span>
                  {t.child_count > 0 && <span className="flex items-center gap-1"><GitBranch size={12} /> {t.child_count} sub</span>}
                  <span>{new Date(t.updated_at).toLocaleString()}</span>
                </div>
              </div>
              <ChevronRight size={16} className="text-surface-500 shrink-0 mt-1" />
            </div>
          </button>
        ))}

        {!tickets.length && (
          <div className="text-center py-12 text-surface-400">
            <LifeBuoy size={40} className="mx-auto mb-3 opacity-50" />
            <p>{search || stateFilter || typeFilter || teamFilter || statusFilter ? 'No matching tickets' : 'No ITSM tickets yet'}</p>
          </div>
        )}
      </div>

      {selectedId && (
        <TicketDetailModal
          ticketId={selectedId}
          meta={meta}
          onClose={() => setSelectedId(null)}
          onChanged={loadTickets}
        />
      )}
    </div>
  )
}

function TicketDetailModal({ ticketId, meta, onClose, onChanged }) {
  const [ticket, setTicket] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [panel, setPanel] = useState(null) // 'transfer' | 'sub_ticket' | null
  const [comment, setComment] = useState('')

  const load = useCallback(async () => {
    try {
      setTicket(await adminApi.getItsmTicket(ticketId))
    } catch {
      toast.error('Failed to load ticket')
      onClose()
    } finally {
      setLoading(false)
    }
  }, [ticketId, onClose])

  useEffect(() => { load() }, [load])

  // Run an admin action, refresh both the modal and the parent list on success.
  const runAction = async (payload, successMsg) => {
    setBusy(true)
    try {
      const res = await adminApi.itsmTicketAction(ticketId, payload)
      // comment/sub_ticket return { ticket }, transition/transfer/fulfil return the ticket.
      setTicket(res.ticket || res)
      if (successMsg) toast.success(successMsg)
      onChanged?.()
      return true
    } catch (err) {
      toast.error(err.response?.data?.error || 'Action failed')
      return false
    } finally {
      setBusy(false)
    }
  }

  const submitComment = async (e) => {
    e.preventDefault()
    const text = comment.trim()
    if (!text) return
    if (await runAction({ action: 'comment', message: text })) setComment('')
  }

  const closeCodes = meta.close_codes || []

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="glass-card w-full max-w-2xl max-h-[88vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        {loading || !ticket ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-7 h-7 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="p-6 space-y-4">
            {/* Header */}
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded font-semibold ${TYPE_BADGE[ticket.ticket_type] || TYPE_BADGE.incident}`}>
                    {ticket.ticket_type_label}
                  </span>
                  <span className="font-mono text-accent-cyan font-semibold">{ticket.number}</span>
                  <StateLozenge state={ticket.state} label={ticket.state_label} />
                  <span className={`text-[11px] font-semibold ${PRIORITY_STYLE[ticket.priority] || PRIORITY_STYLE['3']}`}>{ticket.priority_label}</span>
                  <SlaBadge ticket={ticket} />
                </div>
                <h2 className="text-lg font-bold text-white mt-2 leading-snug">{ticket.short_description}</h2>
                <div className="flex flex-wrap items-center gap-3 mt-1.5 text-xs text-surface-500">
                  {ticket.user && <span className="flex items-center gap-1"><User size={12} /> {ticket.user.username} ({ticket.user.email})</span>}
                  {ticket.scenario && <span className="flex items-center gap-1"><Target size={12} /> {ticket.scenario.title}</span>}
                </div>
                <p className="text-xs text-surface-400 mt-1">
                  Assignment group: <span className="text-surface-200 font-medium">{ticket.assignment_group_label}</span>
                  {ticket.is_sub_ticket && ticket.parent_number && <span> · sub-ticket of {ticket.parent_number}</span>}
                </p>
              </div>
              <button type="button" onClick={onClose} className="text-surface-400 hover:text-white p-1 rounded-md hover:bg-surface-800/60 shrink-0">
                <X size={20} />
              </button>
            </div>

            {ticket.description && (
              <div className="text-xs text-surface-400 bg-surface-950 border border-surface-800 rounded p-3 max-h-32 overflow-y-auto leading-relaxed whitespace-pre-wrap">
                {renderInline(ticket.description)}
              </div>
            )}

            {/* State transitions */}
            {!ticket.is_closed && ticket.allowed_transitions?.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {ticket.allowed_transitions.map(st => {
                  const label = meta.states.find(s => s.value === st)?.label || st
                  const isResolve = st === 'resolved' || st === 'closed'
                  return (
                    <button
                      key={st}
                      type="button"
                      disabled={busy}
                      onClick={() => runAction(
                        { action: 'transition', state: st, ...(isResolve ? { close_code: closeCodes[0]?.value || 'closed_complete' } : {}) },
                        `Moved to ${label}`,
                      )}
                      className="px-2.5 py-1 text-[11px] rounded border border-accent-cyan/30 bg-accent-cyan/10 text-accent-cyan hover:bg-accent-cyan/20 disabled:opacity-50 transition-colors inline-flex items-center gap-1"
                    >
                      {busy ? <Loader2 size={11} className="animate-spin" /> : <ChevronRight size={11} />} {label}
                    </button>
                  )
                })}
              </div>
            )}

            {/* Action buttons */}
            <div className="flex flex-wrap gap-2">
              {!ticket.is_sub_ticket && !ticket.is_closed && (
                <>
                  <button type="button" onClick={() => setPanel(p => p === 'sub_ticket' ? null : 'sub_ticket')} className="btn-secondary px-2.5 py-1 text-[11px] inline-flex items-center gap-1">
                    <Plus size={12} /> Raise sub-ticket
                  </button>
                  <button type="button" onClick={() => setPanel(p => p === 'transfer' ? null : 'transfer')} className="btn-secondary px-2.5 py-1 text-[11px] inline-flex items-center gap-1">
                    <ArrowRightLeft size={12} /> Transfer
                  </button>
                </>
              )}
              {ticket.is_sub_ticket && !ticket.is_closed && ticket.state !== 'resolved' && (
                <button type="button" disabled={busy} onClick={() => runAction({ action: 'fulfil' }, 'Team actioned the request')} className="btn-secondary px-2.5 py-1 text-[11px] inline-flex items-center gap-1">
                  {busy ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />} Fulfil (run team action)
                </button>
              )}
            </div>

            {panel === 'transfer' && (
              <TransferForm
                teams={meta.teams}
                current={ticket.assignment_group}
                busy={busy}
                onSubmit={async (team, reason) => { if (await runAction({ action: 'transfer', team, reason }, 'Transferred')) setPanel(null) }}
              />
            )}
            {panel === 'sub_ticket' && (
              <RaiseSubTicketForm
                actions={meta.actions}
                busy={busy}
                onSubmit={async (payload) => { if (await runAction({ action: 'sub_ticket', ...payload }, 'Sub-ticket raised')) setPanel(null) }}
              />
            )}

            {/* Sub-tickets */}
            {ticket.children?.length > 0 && (
              <div className="space-y-2">
                <p className="text-[10px] uppercase tracking-wide text-surface-500 flex items-center gap-1"><GitBranch size={11} /> Sub-tickets ({ticket.children.length})</p>
                {ticket.children.map(sub => (
                  <button
                    key={sub.id}
                    type="button"
                    onClick={() => { setTicket(null); setLoading(true); adminApi.getItsmTicket(sub.id).then(setTicket).finally(() => setLoading(false)) }}
                    className="rounded border border-surface-800 bg-surface-900/40 p-2.5 w-full text-left hover:border-accent-cyan/30 transition-colors"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[11px] text-accent-cyan">{sub.number}</span>
                      <StateLozenge state={sub.state} label={sub.state_label} />
                    </div>
                    <p className="text-xs text-surface-300 mt-1">{sub.short_description}</p>
                    <p className="text-[10px] text-surface-500 mt-0.5">→ {sub.assignment_group_label}</p>
                    {sub.action_result?.device && (
                      <p className="text-[10px] text-accent-green mt-1 flex items-center gap-1"><CheckCircle2 size={10} /> Attached as <code className="font-mono">{sub.action_result.device}</code></p>
                    )}
                  </button>
                ))}
              </div>
            )}

            {/* Activity stream */}
            {ticket.notes?.length > 0 && (
              <div className="pt-2 border-t border-white/[0.06]">
                <p className="text-[10px] uppercase tracking-wide text-surface-500 mb-2">Activity</p>
                <div className="space-y-2.5">
                  {ticket.notes.map(n => (
                    <div key={n.id} className="flex gap-2 text-xs">
                      <span className={`mt-1 w-1.5 h-1.5 rounded-full shrink-0 ${NOTE_DOT[n.kind] || 'bg-surface-500'}`} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="font-medium text-surface-300">{n.author}</span>
                          <span className="text-surface-600">·</span>
                          <span className="text-surface-500 text-[10px]">{new Date(n.created_at).toLocaleString()}</span>
                        </div>
                        <p className="text-surface-400 mt-0.5 leading-relaxed whitespace-pre-wrap break-words">{renderInline(n.body)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Add comment — posts as the assignment group bot reply too */}
            <form onSubmit={submitComment} className="pt-2 border-t border-white/[0.06] space-y-1.5">
              <p className="text-[10px] uppercase tracking-wide text-surface-500 flex items-center gap-1">
                <MessageSquare size={11} /> Comment as admin (triggers {ticket.assignment_group_label} reply)
              </p>
              <div className="flex items-start gap-1.5">
                <textarea
                  rows={2}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitComment(e) } }}
                  placeholder="Add a comment or question on this ticket…"
                  className="input-field flex-1 text-xs py-1.5 resize-none"
                />
                <button type="submit" disabled={busy || !comment.trim()} className="btn-primary px-2.5 py-1.5 text-xs disabled:opacity-50 inline-flex items-center gap-1 shrink-0">
                  {busy ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  )
}

function TransferForm({ teams, current, busy, onSubmit }) {
  const [team, setTeam] = useState(teams.find(t => t.value !== current)?.value || '')
  const [reason, setReason] = useState('')
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit?.(team, reason.trim()) }} className="rounded border border-surface-800 bg-surface-950 p-3 space-y-2">
      <p className="text-[10px] uppercase tracking-wide text-surface-500">Transfer to another team</p>
      <select value={team} onChange={(e) => setTeam(e.target.value)} className="input-field w-full text-xs py-1.5">
        {teams.filter(t => t.value !== current).map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
      </select>
      <input type="text" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason (optional)" className="input-field w-full text-xs py-1.5" />
      <button type="submit" disabled={busy || !team} className="btn-primary w-full py-1.5 text-xs disabled:opacity-50 inline-flex items-center justify-center gap-1">
        {busy ? <Loader2 size={12} className="animate-spin" /> : <ArrowRightLeft size={12} />} Transfer ticket
      </button>
    </form>
  )
}

function RaiseSubTicketForm({ actions, busy, onSubmit }) {
  const [actionKind, setActionKind] = useState(actions[0]?.kind || '')
  const [shortDesc, setShortDesc] = useState('')
  const [sizeGb, setSizeGb] = useState(50)
  const selected = actions.find(a => a.kind === actionKind)
  const handleSubmit = (e) => {
    e.preventDefault()
    const params = {}
    if (actionKind === 'add_disk') params.size_gb = Number(sizeGb) || 50
    onSubmit?.({ action_kind: actionKind, short_description: shortDesc.trim(), action_params: params, auto_fulfil: true })
  }
  return (
    <form onSubmit={handleSubmit} className="rounded border border-surface-800 bg-surface-950 p-3 space-y-2">
      <p className="text-[10px] uppercase tracking-wide text-surface-500">Raise a request to another team</p>
      <select value={actionKind} onChange={(e) => setActionKind(e.target.value)} className="input-field w-full text-xs py-1.5">
        {actions.map(a => <option key={a.kind} value={a.kind}>{a.label} — {a.team_label}</option>)}
      </select>
      {selected && <p className="text-[10px] text-surface-500">Routed to <span className="text-surface-300">{selected.team_label}</span></p>}
      {actionKind === 'add_disk' && (
        <label className="flex items-center gap-2 text-[11px] text-surface-400">
          Disk size (GiB)
          <input type="number" min="1" max="2000" value={sizeGb} onChange={(e) => setSizeGb(e.target.value)} className="input-field w-20 text-xs py-1" />
        </label>
      )}
      <input type="text" value={shortDesc} onChange={(e) => setShortDesc(e.target.value)} placeholder={selected?.default_short || 'Short description (optional)'} className="input-field w-full text-xs py-1.5" />
      <button type="submit" disabled={busy || !actionKind} className="btn-primary w-full py-1.5 text-xs disabled:opacity-50 inline-flex items-center justify-center gap-1">
        {busy ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />} Submit to team
      </button>
    </form>
  )
}
