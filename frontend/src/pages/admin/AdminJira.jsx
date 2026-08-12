import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { AdminPageHeader } from '../../components/design'
import { useModalA11y } from '../../components/ConfirmModal'
import { Ticket, Search, Plus, User, Target, X } from 'lucide-react'
import toast from 'react-hot-toast'
import JiraTicketLink from '../../components/JiraTicketLink'

export default function AdminJira() {
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [stats, setStats] = useState({ count: 0, open_count: 0, closed_count: 0, jira_enabled: false })
  const [showCreate, setShowCreate] = useState(false)
  const [users, setUsers] = useState([])
  const [scenarios, setScenarios] = useState([])
  const [createForm, setCreateForm] = useState({ user_id: '', scenario_id: '' })
  const [creating, setCreating] = useState(false)

  const closeCreate = () => setShowCreate(false)
  const createDialogRef = useModalA11y(showCreate, closeCreate)

  useEffect(() => { loadTickets() }, [])

  const loadTickets = async (liveSync = false) => {
    setLoading(true)
    try {
      const data = await adminApi.getJiraTickets(liveSync ? { sync: '1' } : {})
      setTickets(data.tickets || [])
      setStats(data)
    } catch {
      toast.error('Failed to load Jira tickets')
    } finally {
      setLoading(false)
    }
  }

  const openCreateModal = async () => {
    setShowCreate(true)
    try {
      const [u, s] = await Promise.all([
        adminApi.getUsers(),
        adminApi.getScenarios(),
      ])
      setUsers(Array.isArray(u) ? u : u.users || [])
      setScenarios(Array.isArray(s) ? s : s.results || [])
    } catch {
      toast.error('Failed to load users/scenarios')
    }
  }

  const handleCreate = async () => {
    if (!createForm.user_id || !createForm.scenario_id) {
      toast.error('Select user and scenario')
      return
    }
    setCreating(true)
    try {
      const result = await adminApi.createJiraTicket(createForm.user_id, createForm.scenario_id)
      toast.success(result.jira_created ? `Created ${result.issue_key}` : `Ticket exists: ${result.issue_key}`)
      setShowCreate(false)
      setCreateForm({ user_id: '', scenario_id: '' })
      loadTickets()
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to create ticket')
    } finally {
      setCreating(false)
    }
  }

  const filtered = tickets.filter(t => {
    const q = search.toLowerCase()
    const matchesSearch = !q ||
      t.issue_key?.toLowerCase().includes(q) ||
      t.user?.username?.toLowerCase().includes(q) ||
      t.user?.email?.toLowerCase().includes(q) ||
      t.scenario?.title?.toLowerCase().includes(q)
    const matchesFilter =
      filter === 'all' ||
      (filter === 'open' && !t.is_closed) ||
      (filter === 'closed' && t.is_closed)
    return matchesSearch && matchesFilter
  })

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Jira Tickets"
        subtitle={`${stats.open_count} open · ${stats.closed_count} closed${!stats.jira_enabled ? ' · Jira integration disabled' : ''}`}
        actions={
          <>
            <button onClick={() => loadTickets(true)} className="btn-secondary flex items-center gap-2 text-sm">
              Refresh from Jira
            </button>
            <button onClick={openCreateModal} className="btn-primary flex items-center gap-2 text-sm">
              <Plus size={14} /> Create Ticket
            </button>
          </>
        }
      />

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" size={16} />
          <input
            type="text"
            placeholder="Search by key, user, scenario..."
            className="input-field pl-10 w-full"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="input-field w-auto"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">All tickets</option>
          <option value="open">Open only</option>
          <option value="closed">Closed only</option>
        </select>
      </div>

      <div className="space-y-3">
        {filtered.map(t => (
          <div key={`${t.user?.id}-${t.scenario?.id}-${t.issue_key}`} className="glass-card p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-blue-400 font-semibold">
                    <JiraTicketLink issueKey={t.issue_key} issueUrl={t.issue_url} allowExternalLink />
                  </span>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${
                    t.is_closed
                      ? 'bg-surface-700 text-surface-400'
                      : 'bg-accent-green/15 text-accent-green border border-accent-green/20'
                  }`}>
                    {t.jira_status || (t.is_closed ? 'Closed' : 'Open')}
                  </span>
                </div>
                <p className="text-sm font-medium text-white">{t.scenario?.title}</p>
                <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-surface-500">
                  <span className="flex items-center gap-1">
                    <User size={12} /> {t.user?.username} ({t.user?.email})
                  </span>
                  <span className="flex items-center gap-1">
                    <Target size={12} /> {t.scenario?.slug}
                  </span>
                  <span>{t.run_count} run{t.run_count !== 1 ? 's' : ''}</span>
                  <span>{new Date(t.updated_at).toLocaleString()}</span>
                </div>
              </div>
            </div>
          </div>
        ))}

        {filtered.length === 0 && (
          <div className="text-center py-12 text-surface-400">
            <Ticket size={40} className="mx-auto mb-3 opacity-50" />
            <p>{search || filter !== 'all' ? 'No matching tickets' : 'No Jira tickets yet'}</p>
          </div>
        )}
      </div>

      {showCreate && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={closeCreate}>
          <div
            ref={createDialogRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-label="Create Jira Ticket"
            className="glass-card p-6 w-full max-w-md space-y-4 outline-none"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">Create Jira Ticket</h2>
              <button type="button" onClick={closeCreate} aria-label="Close create Jira ticket" className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-surface-400 hover:text-white p-1 rounded-md hover:bg-surface-800/60">
                <X size={20} />
              </button>
            </div>
            <p className="text-sm text-surface-400">Creates a personal ticket for the selected user and scenario.</p>
            <div>
              <label className="text-xs text-surface-400 mb-1 block">User</label>
              <select
                className="input-field w-full"
                value={createForm.user_id}
                onChange={(e) => setCreateForm(f => ({ ...f, user_id: e.target.value }))}
              >
                <option value="">Select user...</option>
                {(Array.isArray(users) ? users : []).map(u => (
                  <option key={u.id} value={u.id}>{u.username} ({u.email})</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-surface-400 mb-1 block">Scenario</label>
              <select
                className="input-field w-full"
                value={createForm.scenario_id}
                onChange={(e) => setCreateForm(f => ({ ...f, scenario_id: e.target.value }))}
              >
                <option value="">Select scenario...</option>
                {scenarios.filter(s => s.is_active).map(s => (
                  <option key={s.id} value={s.id}>{s.title}</option>
                ))}
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setShowCreate(false)} className="btn-secondary text-sm">Cancel</button>
              <button onClick={handleCreate} disabled={creating} className="btn-primary text-sm">
                {creating ? 'Creating...' : 'Create Ticket'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
