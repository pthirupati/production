import { useState, useEffect, useCallback, useRef } from 'react'
import { adminApi } from '../../api/admin'
import { scenarioApi } from '../../api/scenarios'
import {
  CreditCard, IndianRupee, DollarSign, Users, Search, Download,
  Filter, X, RefreshCw, BadgeCheck, XCircle, ChevronRight, ChevronLeft,
  Mail, Send, WrenchIcon, BarChart3, ArrowLeft, Clock, CheckCircle,
  TrendingUp, Layers, User as UserIcon, Save, AlertTriangle, Cpu,
} from 'lucide-react'
import toast from 'react-hot-toast'

// ─── Helper: format date ─────────────────────────────────────────────
function fmt(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

// ─── Tech stat card ──────────────────────────────────────────────────
function TechStatCard({ tech, onClick }) {
  return (
    <div
      onClick={() => onClick(tech)}
      className={`glass-card-hover p-5 cursor-pointer relative ${tech.maintenance_enabled ? 'border-amber-500/30' : ''}`}
    >
      {tech.maintenance_enabled && (
        <span className="absolute top-2 right-2 flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30">
          <WrenchIcon size={9} /> Maintenance
        </span>
      )}
      <div className={`w-9 h-9 rounded-xl bg-accent-${tech.color || 'cyan'}/10 flex items-center justify-center mb-3`}>
        <Cpu size={18} className={`text-accent-${tech.color || 'cyan'}`} />
      </div>
      <h3 className="font-semibold text-white text-sm mb-0.5">{tech.name}</h3>
      <p className="text-xs text-surface-500 font-mono">/{tech.slug}</p>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <div className="rounded-lg bg-surface-800/50 p-2 text-center">
          <p className="text-lg font-bold text-accent-cyan">{tech.active_subscribers}</p>
          <p className="text-[10px] text-surface-500 uppercase tracking-wide">Paid</p>
        </div>
        <div className="rounded-lg bg-surface-800/50 p-2 text-center">
          <p className="text-lg font-bold text-accent-amber">{tech.free_users ?? 0}</p>
          <p className="text-[10px] text-surface-500 uppercase tracking-wide">Free</p>
        </div>
        <div className="rounded-lg bg-surface-800/50 p-2 text-center">
          <p className="text-lg font-bold text-accent-green">{tech.revenue_display || '₹0'}</p>
          <p className="text-[10px] text-surface-500 uppercase tracking-wide">Revenue</p>
        </div>
      </div>
      {(tech.complimentary_users ?? 0) > 0 && (
        <p className="text-[10px] text-accent-purple mt-2">{tech.complimentary_users} complimentary user(s)</p>
      )}
      <div className="mt-2 flex items-center justify-between text-xs text-surface-500">
        <span>{tech.total_subscribers} total subscribers</span>
        <ChevronRight size={12} />
      </div>
    </div>
  )
}

// ─── Technology detail view ───────────────────────────────────────────
function TechDetailView({ tech, onBack }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeSubTab, setActiveSubTab] = useState('subscribers') // subscribers | email | maintenance
  const [emailForm, setEmailForm] = useState({ subject: '', body: '' })
  const [emailSending, setEmailSending] = useState(false)
  const [maintenanceForm, setMaintenanceForm] = useState({ enabled: false, message: '', scheduled_start: '', scheduled_end: '' })
  const [maintenanceLoading, setMaintenanceLoading] = useState(false)
  const [maintenanceLoaded, setMaintenanceLoaded] = useState(false)
  const [searchSub, setSearchSub] = useState('')

  useEffect(() => { loadData() }, [tech.id])

  const loadData = async () => {
    setLoading(true)
    try {
      const res = await adminApi.getTechSubscribers(tech.id)
      setData(res)
    } catch { toast.error('Failed to load subscribers') } finally { setLoading(false) }
  }

  const loadMaintenance = async () => {
    if (maintenanceLoaded) return
    try {
      const m = await adminApi.getTechMaintenance(tech.id)
      setMaintenanceForm({
        enabled: m.maintenance_enabled || false,
        message: m.maintenance_message || '',
        scheduled_start: m.maintenance_scheduled_start ? m.maintenance_scheduled_start.slice(0, 16) : '',
        scheduled_end: m.maintenance_scheduled_end ? m.maintenance_scheduled_end.slice(0, 16) : '',
      })
      setMaintenanceLoaded(true)
    } catch {}
  }

  const handleSubTabChange = (tab) => {
    setActiveSubTab(tab)
    if (tab === 'maintenance') loadMaintenance()
  }

  const sendEmail = async () => {
    if (!emailForm.subject.trim() || !emailForm.body.trim()) {
      toast.error('Subject and body are required')
      return
    }
    setEmailSending(true)
    try {
      const res = await adminApi.sendTechEmail(tech.id, { subject: emailForm.subject, body: emailForm.body, send_now: true })
      toast.success(`Sent to ${res.sent} subscriber(s)${res.failed ? ` (${res.failed} failed)` : ''}`)
      setEmailForm({ subject: '', body: '' })
    } catch { toast.error('Failed to send email') } finally { setEmailSending(false) }
  }

  const saveMaintenance = async () => {
    setMaintenanceLoading(true)
    try {
      await adminApi.setTechMaintenance(tech.id, {
        enabled: maintenanceForm.enabled,
        message: maintenanceForm.message,
        scheduled_start: maintenanceForm.scheduled_start || null,
        scheduled_end: maintenanceForm.scheduled_end || null,
      })
      toast.success(maintenanceForm.enabled ? 'Maintenance enabled — subscribers notified' : 'Maintenance disabled')
    } catch { toast.error('Failed to save') } finally { setMaintenanceLoading(false) }
  }

  const filteredSubs = (data?.subscribers || []).filter(s =>
    !searchSub || s.user.username.toLowerCase().includes(searchSub.toLowerCase()) || s.user.email.toLowerCase().includes(searchSub.toLowerCase())
  )

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="p-2 rounded-lg text-surface-400 hover:text-white hover:bg-surface-800 transition-all">
          <ArrowLeft size={18} />
        </button>
        <div className={`w-9 h-9 rounded-xl bg-accent-${tech.color || 'cyan'}/10 flex items-center justify-center`}>
          <Cpu size={18} className={`text-accent-${tech.color || 'cyan'}`} />
        </div>
        <div>
          <h2 className="text-lg font-bold text-white">{tech.name}</h2>
          <p className="text-xs text-surface-400">{tech.active_subscribers} active · {tech.revenue_display} revenue</p>
        </div>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Active Subs', value: data?.active_count ?? tech.active_subscribers, color: 'text-accent-cyan', icon: Users },
          { label: 'Total Subs', value: data?.total_subscribers ?? tech.total_subscribers, color: 'text-surface-300', icon: CreditCard },
          { label: 'Revenue', value: data ? `₹${Math.round(data.total_revenue).toLocaleString('en-IN')}` : tech.revenue_display, color: 'text-accent-green', icon: IndianRupee },
          { label: 'Price', value: `₹${Number(tech.price).toLocaleString('en-IN')}`, color: 'text-accent-purple', icon: TrendingUp },
        ].map(({ label, value, color, icon: Icon }) => (
          <div key={label} className="glass-card p-4">
            <Icon size={16} className={`${color} mb-1`} />
            <p className={`text-xl font-bold ${color}`}>{value}</p>
            <p className="text-xs text-surface-500">{label}</p>
          </div>
        ))}
      </div>

      {/* Sub-tabs */}
      <div className="flex gap-1 bg-surface-800/50 rounded-lg p-1 w-fit">
        {[
          { key: 'subscribers', label: 'Subscribers', icon: Users },
          { key: 'email', label: 'Email Campaign', icon: Mail },
          { key: 'maintenance', label: 'Maintenance', icon: WrenchIcon },
        ].map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => handleSubTabChange(key)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
              activeSubTab === key ? 'bg-surface-700 text-white' : 'text-surface-400 hover:text-white'
            }`}>
            <Icon size={12} /> {label}
          </button>
        ))}
      </div>

      {/* Subscribers list */}
      {activeSubTab === 'subscribers' && (
        <div className="glass-card overflow-hidden">
          <div className="p-4 border-b border-surface-700/40">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" size={14} />
              <input
                type="text"
                value={searchSub}
                onChange={e => setSearchSub(e.target.value)}
                placeholder="Search subscriber..."
                className="input-field pl-9 text-sm w-full max-w-xs"
              />
            </div>
          </div>
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <div className="w-6 h-6 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-700/40">
                    <th className="text-left p-3 text-xs text-surface-400 font-medium">User</th>
                    <th className="text-left p-3 text-xs text-surface-400 font-medium">Status</th>
                    <th className="text-left p-3 text-xs text-surface-400 font-medium">Amount</th>
                    <th className="text-left p-3 text-xs text-surface-400 font-medium">Subscribed</th>
                    <th className="text-left p-3 text-xs text-surface-400 font-medium">Expires</th>
                    <th className="text-left p-3 text-xs text-surface-400 font-medium">Progress</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredSubs.map(sub => (
                    <tr key={sub.id} className="border-b border-surface-800/50 hover:bg-surface-800/20">
                      <td className="p-3">
                        <p className="font-medium text-white text-xs">{sub.user.username}</p>
                        <p className="text-[10px] text-surface-500">{sub.user.email}</p>
                        <p className="text-[10px] text-surface-600">Joined {fmt(sub.user.date_joined)}</p>
                      </td>
                      <td className="p-3">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium ${
                          sub.is_active ? 'bg-accent-green/10 text-accent-green' : 'bg-surface-700 text-surface-400'
                        }`}>
                          {sub.is_active ? <><BadgeCheck size={9} /> Active</> : <><XCircle size={9} /> Expired</>}
                        </span>
                        {sub.days_remaining != null && sub.is_active && (
                          <p className="text-[10px] text-surface-500 mt-0.5">{sub.days_remaining}d left</p>
                        )}
                      </td>
                      <td className="p-3 font-semibold text-xs text-accent-green">{sub.amount_display}</td>
                      <td className="p-3 text-xs text-surface-400">{fmt(sub.subscribed_at)}</td>
                      <td className="p-3 text-xs text-surface-400">{fmt(sub.expires_at)}</td>
                      <td className="p-3 text-xs">
                        <span className="text-accent-cyan font-semibold">{sub.completed_scenarios}</span>
                        <span className="text-surface-500"> scenarios</span>
                      </td>
                    </tr>
                  ))}
                  {filteredSubs.length === 0 && !loading && (
                    <tr><td colSpan={6} className="p-8 text-center text-surface-400 text-sm">No subscribers found</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Email campaign */}
      {activeSubTab === 'email' && (
        <div className="glass-card p-6 space-y-4">
          <div className="flex items-center gap-2 mb-2">
            <Mail size={16} className="text-accent-cyan" />
            <p className="text-sm font-medium text-white">Send email to all <span className="text-accent-cyan">{data?.active_count ?? 0}</span> active subscribers</p>
          </div>
          <div>
            <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Subject</label>
            <input
              type="text"
              value={emailForm.subject}
              onChange={e => setEmailForm(f => ({ ...f, subject: e.target.value }))}
              className="input-field w-full"
              placeholder="Important update for subscribers..."
            />
          </div>
          <div>
            <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Message Body</label>
            <textarea
              value={emailForm.body}
              onChange={e => setEmailForm(f => ({ ...f, body: e.target.value }))}
              className="input-field w-full h-40 resize-y font-mono text-sm"
              placeholder="Write your message here..."
            />
          </div>
          <div className="flex justify-end gap-3 pt-2 border-t border-surface-700/40">
            <button onClick={() => setEmailForm({ subject: '', body: '' })} className="btn-secondary text-sm">Clear</button>
            <button
              onClick={async () => {
                try {
                  const res = await adminApi.sendTechEmail(tech.id, { ...emailForm, send_now: false })
                  toast.success(`Draft saved for ${res.recipient_count ?? 0} recipients`)
                } catch { toast.error('Failed to save draft') }
              }}
              disabled={!emailForm.subject.trim() || !emailForm.body.trim()}
              className="btn-secondary text-sm disabled:opacity-50"
            >
              Save Draft
            </button>
            <button
              onClick={sendEmail}
              disabled={emailSending || !emailForm.subject.trim() || !emailForm.body.trim()}
              className="btn-primary flex items-center gap-2 text-sm disabled:opacity-50"
            >
              <Send size={14} /> {emailSending ? 'Sending…' : 'Send to All Active'}
            </button>
          </div>
        </div>
      )}

      {/* Maintenance */}
      {activeSubTab === 'maintenance' && (
        <div className="glass-card p-6 space-y-4 border border-amber-500/20">
          <div className="flex items-center gap-2 mb-1">
            <WrenchIcon size={16} className="text-amber-400" />
            <p className="text-sm font-medium text-white">Technology Maintenance Mode</p>
          </div>
          <p className="text-xs text-surface-400">When enabled, labs under this technology will be blocked and a message shown to users. Subscribers will receive an email notification.</p>

          <label className="flex items-center justify-between p-3 rounded-xl bg-surface-800/60 border border-surface-700/40 cursor-pointer">
            <div>
              <p className="text-sm font-medium text-white">Enable Maintenance</p>
              <p className="text-xs text-surface-500 mt-0.5">Blocks all labs for this technology</p>
            </div>
            <div className={`relative w-11 h-6 rounded-full transition-all cursor-pointer ${maintenanceForm.enabled ? 'bg-amber-500' : 'bg-surface-700'}`}
              onClick={() => setMaintenanceForm(f => ({ ...f, enabled: !f.enabled }))}>
              <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all ${maintenanceForm.enabled ? 'left-5' : 'left-0.5'}`} />
            </div>
          </label>

          <div>
            <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Maintenance Message</label>
            <textarea
              value={maintenanceForm.message}
              onChange={e => setMaintenanceForm(f => ({ ...f, message: e.target.value }))}
              className="input-field h-20 resize-y"
              placeholder="e.g. Database infrastructure upgrades. Labs will resume within 2 hours."
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Scheduled Start</label>
              <input type="datetime-local" value={maintenanceForm.scheduled_start} onChange={e => setMaintenanceForm(f => ({ ...f, scheduled_start: e.target.value }))} className="input-field" />
            </div>
            <div>
              <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Scheduled End</label>
              <input type="datetime-local" value={maintenanceForm.scheduled_end} onChange={e => setMaintenanceForm(f => ({ ...f, scheduled_end: e.target.value }))} className="input-field" />
            </div>
          </div>

          {maintenanceForm.enabled && (
            <div className="flex items-start gap-2 p-3 rounded-xl bg-amber-500/5 border border-amber-500/20">
              <AlertTriangle size={14} className="text-amber-400 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-amber-300">Enabling maintenance will email all active subscribers. This action will be logged.</p>
            </div>
          )}

          <div className="flex justify-end pt-2 border-t border-surface-700/40">
            <button onClick={saveMaintenance} disabled={maintenanceLoading} className="btn-primary flex items-center gap-2 text-sm">
              <Save size={14} /> {maintenanceLoading ? 'Saving…' : 'Save Maintenance Settings'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Main AdminSubscriptions component ───────────────────────────────
export default function AdminSubscriptions() {
  const [view, setView] = useState('overview') // 'overview' | 'tech-detail' | 'logs'
  const [selectedTech, setSelectedTech] = useState(null)
  const [techStats, setTechStats] = useState(null)
  const [techStatsLoading, setTechStatsLoading] = useState(true)

  // Legacy logs state
  const [logs, setLogs] = useState([])
  const [interviewLogs, setInterviewLogs] = useState([])
  const [stats, setStats] = useState({ total_revenue: 0, active_count: 0, total_count: 0 })
  const [logsLoading, setLogsLoading] = useState(false)
  const [logsLoaded, setLogsLoaded] = useState(false)
  const [currency, setCurrency] = useState('INR')
  const [statusFilter, setStatusFilter] = useState('all')
  const [techFilter, setTechFilter] = useState('')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  // Interview maintenance
  const [interviewMaintenance, setInterviewMaintenance] = useState({ enabled: false, message: '', scheduled_start: '', scheduled_end: '' })
  const [interviewMaintenanceLoaded, setInterviewMaintenanceLoaded] = useState(false)
  const [interviewMaintenanceSaving, setInterviewMaintenanceSaving] = useState(false)

  const searchTimer = useRef(null)

  useEffect(() => { loadTechStats() }, [])

  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => setDebouncedSearch(search), 500)
    return () => clearTimeout(searchTimer.current)
  }, [search])

  const loadTechStats = async () => {
    setTechStatsLoading(true)
    try {
      const res = await adminApi.getTechStats()
      setTechStats(res)
    } catch { toast.error('Failed to load tech stats') } finally { setTechStatsLoading(false) }
  }

  const loadLogs = useCallback(async () => {
    setLogsLoading(true)
    try {
      const params = new URLSearchParams()
      params.set('currency', currency)
      if (statusFilter !== 'all') params.set('status', statusFilter)
      if (techFilter) params.set('technology', techFilter)
      if (debouncedSearch) params.set('user', debouncedSearch)
      if (dateFrom) params.set('date_from', dateFrom)
      if (dateTo) params.set('date_to', dateTo)
      const data = await adminApi.getSubscriptionLogs(Object.fromEntries(params))
      setLogs(data.logs || [])
      setInterviewLogs(data.interview_logs || [])
      setStats({
        total_revenue: data.total_revenue || 0,
        active_count: data.active_count || 0,
        total_count: data.total_count || 0,
        exchange_rate: data.exchange_rate || null,
        display_currency: data.display_currency || 'INR',
        interview_active_count: data.interview_active_count || 0,
      })
      setLogsLoaded(true)
    } catch { toast.error('Failed to load subscription logs') } finally { setLogsLoading(false) }
  }, [currency, statusFilter, techFilter, debouncedSearch, dateFrom, dateTo])

  const loadInterviewMaintenance = async () => {
    if (interviewMaintenanceLoaded) return
    try {
      const m = await adminApi.getInterviewMaintenance()
      setInterviewMaintenance({
        enabled: m.maintenance_enabled || false,
        message: m.maintenance_message || '',
        scheduled_start: m.maintenance_scheduled_start ? m.maintenance_scheduled_start.slice(0, 16) : '',
        scheduled_end: m.maintenance_scheduled_end ? m.maintenance_scheduled_end.slice(0, 16) : '',
      })
      setInterviewMaintenanceLoaded(true)
    } catch {}
  }

  const saveInterviewMaintenance = async () => {
    setInterviewMaintenanceSaving(true)
    try {
      await adminApi.setInterviewMaintenance({
        enabled: interviewMaintenance.enabled,
        message: interviewMaintenance.message,
        scheduled_start: interviewMaintenance.scheduled_start || null,
        scheduled_end: interviewMaintenance.scheduled_end || null,
      })
      toast.success('Interview maintenance settings saved')
    } catch { toast.error('Failed to save') } finally { setInterviewMaintenanceSaving(false) }
  }

  const openTechDetail = (tech) => {
    setSelectedTech(tech)
    setView('tech-detail')
  }

  const openLogs = () => {
    setView('logs')
    if (!logsLoaded) loadLogs()
  }

  const handleExportCSV = () => {
    const headers = ['Subscription ID', 'Username', 'Email', 'Technology', 'Amount', 'Status', 'Started', 'Expires']
    const rows = logs.map(l => [l.subscription_id, l.user?.username, l.user?.email, l.technology, l.amount_display || `₹${l.amount}`, l.is_active ? 'Active' : 'Expired', l.created_at ? new Date(l.created_at).toLocaleDateString() : '', l.expires_at ? new Date(l.expires_at).toLocaleDateString() : ''])
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `subscriptions-${new Date().toISOString().slice(0, 10)}.csv`; a.click()
    URL.revokeObjectURL(url)
    toast.success('CSV exported')
  }

  const currencySymbol = currency === 'USD' ? '$' : '₹'
  const CurrencyIcon = currency === 'USD' ? DollarSign : IndianRupee

  // ─── Technology detail view ────────────────────────────────────────
  if (view === 'tech-detail' && selectedTech) {
    return <TechDetailView tech={selectedTech} onBack={() => setView('overview')} />
  }

  // ─── Subscription logs view ────────────────────────────────────────
  if (view === 'logs') {
    const hasActiveFilters = debouncedSearch || statusFilter !== 'all' || techFilter || dateFrom || dateTo
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <button onClick={() => setView('overview')} className="p-2 rounded-lg text-surface-400 hover:text-white hover:bg-surface-800 transition-all">
            <ArrowLeft size={18} />
          </button>
          <div>
            <h1 className="text-xl font-bold text-white">All Subscription Logs</h1>
            <p className="text-sm text-surface-400">Detailed transaction log with filters</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <div className="flex bg-surface-800 rounded-lg border border-surface-700/40 overflow-hidden">
              {['INR', 'USD'].map(c => (
                <button key={c} onClick={() => setCurrency(c)}
                  className={`px-3 py-1.5 text-xs font-medium flex items-center gap-1 transition-all ${currency === c ? 'bg-accent-cyan/20 text-accent-cyan' : 'text-surface-400 hover:text-surface-200'}`}>
                  {c === 'INR' ? <IndianRupee size={12} /> : <DollarSign size={12} />} {c}
                </button>
              ))}
            </div>
            <button onClick={loadLogs} className="p-2 text-surface-400 hover:text-surface-200 hover:bg-surface-800 rounded-lg" title="Refresh">
              <RefreshCw size={16} className={logsLoading ? 'animate-spin' : ''} />
            </button>
            <button onClick={handleExportCSV} className="btn-secondary text-xs flex items-center gap-1.5 px-3 py-1.5">
              <Download size={14} /> CSV
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="glass-card p-4">
            <CurrencyIcon size={18} className="text-accent-green mb-1" />
            <p className="text-xl font-bold">{currencySymbol}{typeof stats.total_revenue === 'number' ? stats.total_revenue.toLocaleString(undefined, { maximumFractionDigits: 2 }) : stats.total_revenue}</p>
            <p className="text-xs text-surface-400">Total Revenue ({currency})</p>
          </div>
          <div className="glass-card p-4">
            <CreditCard size={18} className="text-accent-cyan mb-1" />
            <p className="text-xl font-bold">{stats.active_count}</p>
            <p className="text-xs text-surface-400">Active Subscriptions</p>
          </div>
          <div className="glass-card p-4">
            <Users size={18} className="text-accent-amber mb-1" />
            <p className="text-xl font-bold">{new Set(logs.map(l => l.user?.id)).size}</p>
            <p className="text-xs text-surface-400">Unique Subscribers</p>
          </div>
          <div className="glass-card p-4">
            <BadgeCheck size={18} className="text-accent-purple mb-1" />
            <p className="text-xl font-bold">{logs.filter(l => l.payment_verified).length}</p>
            <p className="text-xs text-surface-400">Verified Payments</p>
          </div>
        </div>

        <div className="flex gap-3 flex-wrap">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" size={14} />
            <input type="text" placeholder="Search user..." className="input-field pl-9 w-full" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="input-field text-sm">
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="expired">Expired</option>
          </select>
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="input-field text-sm" />
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="input-field text-sm" />
          {hasActiveFilters && (
            <button onClick={() => { setSearch(''); setDebouncedSearch(''); setStatusFilter('all'); setTechFilter(''); setDateFrom(''); setDateTo('') }}
              className="text-xs text-surface-400 hover:text-accent-red flex items-center gap-1">
              <X size={12} /> Clear
            </button>
          )}
        </div>

        <div className="glass-card overflow-hidden">
          {logsLoading && <div className="h-0.5 bg-accent-cyan/60 animate-shimmer" />}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-700">
                  <th className="text-left p-3 text-surface-400 font-medium text-xs">Sub ID</th>
                  <th className="text-left p-3 text-surface-400 font-medium text-xs">User</th>
                  <th className="text-left p-3 text-surface-400 font-medium text-xs">Technology</th>
                  <th className="text-left p-3 text-surface-400 font-medium text-xs">Amount</th>
                  <th className="text-left p-3 text-surface-400 font-medium text-xs">Status</th>
                  <th className="text-left p-3 text-surface-400 font-medium text-xs">Started</th>
                  <th className="text-left p-3 text-surface-400 font-medium text-xs">Expires</th>
                </tr>
              </thead>
              <tbody>
                {logs.map(log => (
                  <tr key={log.id} className="border-b border-surface-800 hover:bg-surface-800/30">
                    <td className="p-3 font-mono text-xs text-cyan-400">{log.subscription_id}</td>
                    <td className="p-3"><p className="font-medium text-xs">{log.user?.username}</p><p className="text-[10px] text-surface-500">{log.user?.email}</p></td>
                    <td className="p-3 text-xs">{log.technology}</td>
                    <td className="p-3 font-semibold text-xs text-accent-green">{log.amount_display || `₹${log.amount}`}</td>
                    <td className="p-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium ${log.is_active ? 'bg-accent-green/10 text-accent-green' : 'bg-surface-700 text-surface-400'}`}>
                        {log.is_active ? <><BadgeCheck size={9} /> Active</> : <><XCircle size={9} /> Expired</>}
                      </span>
                    </td>
                    <td className="p-3 text-xs text-surface-400">{fmt(log.created_at)}</td>
                    <td className="p-3 text-xs text-surface-400">{fmt(log.expires_at)}</td>
                  </tr>
                ))}
                {logs.length === 0 && !logsLoading && (
                  <tr><td colSpan={7} className="p-8 text-center text-surface-400">No subscriptions found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    )
  }

  // ─── Overview ──────────────────────────────────────────────────────
  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Subscriptions</h1>
          <p className="text-surface-400 mt-1">Revenue, subscriber management, maintenance, and email campaigns by technology</p>
        </div>
        <div className="flex gap-2">
          <button onClick={loadTechStats} className="p-2 text-surface-400 hover:text-surface-200 hover:bg-surface-800 rounded-lg" title="Refresh">
            <RefreshCw size={16} className={techStatsLoading ? 'animate-spin' : ''} />
          </button>
          <button onClick={openLogs} className="btn-secondary text-xs flex items-center gap-1.5 px-3 py-1.5">
            <BarChart3 size={14} /> All Logs
          </button>
        </div>
      </div>

      {/* Platform stats strip */}
      {techStats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          <div className="glass-card p-4">
            <IndianRupee size={18} className="text-accent-green mb-1" />
            <p className="text-xl font-bold text-accent-green">₹{Math.round(techStats.total_revenue_inr).toLocaleString('en-IN')}</p>
            <p className="text-xs text-surface-400">Total Revenue</p>
          </div>
          <div className="glass-card p-4">
            <Users size={18} className="text-accent-cyan mb-1" />
            <p className="text-xl font-bold text-accent-cyan">{techStats.total_active_subscribers}</p>
            <p className="text-xs text-surface-400">Active Subscribers</p>
          </div>
          <div className="glass-card p-4">
            <UserIcon size={18} className="text-accent-blue mb-1" />
            <p className="text-xl font-bold text-accent-blue">{techStats.total_unique_subscribers ?? techStats.total_active_subscribers}</p>
            <p className="text-xs text-surface-400">Unique Users</p>
          </div>
          <div className="glass-card p-4">
            <UserIcon size={18} className="text-accent-amber mb-1" />
            <p className="text-xl font-bold text-accent-amber">{techStats.total_free_users ?? 0}</p>
            <p className="text-xs text-surface-400">Free / Complimentary</p>
          </div>
          <div className="glass-card p-4">
            <Layers size={18} className="text-accent-purple mb-1" />
            <p className="text-xl font-bold text-accent-purple">{techStats.technologies?.length || 0}</p>
            <p className="text-xs text-surface-400">Technologies</p>
          </div>
          <div className="glass-card p-4">
            <WrenchIcon size={18} className="text-amber-400 mb-1" />
            <p className="text-xl font-bold text-amber-400">{techStats.maintenance_technologies ?? 0}</p>
            <p className="text-xs text-surface-400">In Maintenance</p>
          </div>
          <div className="glass-card p-4">
            <Clock size={18} className="text-surface-400 mb-1" />
            <p className="text-xl font-bold text-surface-300">{techStats.coming_soon_technologies ?? 0}</p>
            <p className="text-xs text-surface-400">Coming Soon</p>
          </div>
        </div>
      )}

      {/* Per-tech grid */}
      <div>
        <h2 className="text-sm font-semibold text-surface-300 uppercase tracking-widest mb-3">By Technology</h2>
        {techStatsLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="w-7 h-7 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {(techStats?.technologies || []).map(tech => (
              <TechStatCard key={tech.id} tech={tech} onClick={openTechDetail} />
            ))}
          </div>
        )}
      </div>

      {/* Interview maintenance section */}
      <div>
        <h2 className="text-sm font-semibold text-surface-300 uppercase tracking-widest mb-3">Interview Studio Maintenance</h2>
        <div
          className={`glass-card p-5 border cursor-pointer transition-all ${interviewMaintenance.enabled ? 'border-amber-500/30' : 'border-surface-700/40'}`}
          onClick={() => { loadInterviewMaintenance(); }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${interviewMaintenance.enabled ? 'bg-amber-500/10' : 'bg-surface-800'}`}>
                <WrenchIcon size={18} className={interviewMaintenance.enabled ? 'text-amber-400' : 'text-surface-400'} />
              </div>
              <div>
                <p className="text-sm font-medium text-white">Interview Maintenance Mode</p>
                <p className="text-xs text-surface-400">Block all interview sessions platform-wide</p>
              </div>
            </div>
            <div className={`relative w-11 h-6 rounded-full transition-all cursor-pointer ${interviewMaintenance.enabled ? 'bg-amber-500' : 'bg-surface-700'}`}
              onClick={e => { e.stopPropagation(); loadInterviewMaintenance(); setInterviewMaintenance(f => ({ ...f, enabled: !f.enabled })) }}>
              <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all ${interviewMaintenance.enabled ? 'left-5' : 'left-0.5'}`} />
            </div>
          </div>

          {interviewMaintenanceLoaded && (
            <div className="mt-4 space-y-3 border-t border-surface-700/40 pt-4">
              <div>
                <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Maintenance Message</label>
                <textarea
                  value={interviewMaintenance.message}
                  onChange={e => setInterviewMaintenance(f => ({ ...f, message: e.target.value }))}
                  className="input-field w-full h-16 resize-none"
                  placeholder="e.g. Interview Studio is temporarily unavailable for upgrades."
                  onClick={e => e.stopPropagation()}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Scheduled Start</label>
                  <input type="datetime-local" value={interviewMaintenance.scheduled_start} onChange={e => setInterviewMaintenance(f => ({ ...f, scheduled_start: e.target.value }))} className="input-field" onClick={e => e.stopPropagation()} />
                </div>
                <div>
                  <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Scheduled End</label>
                  <input type="datetime-local" value={interviewMaintenance.scheduled_end} onChange={e => setInterviewMaintenance(f => ({ ...f, scheduled_end: e.target.value }))} className="input-field" onClick={e => e.stopPropagation()} />
                </div>
              </div>
              <div className="flex justify-end" onClick={e => e.stopPropagation()}>
                <button onClick={saveInterviewMaintenance} disabled={interviewMaintenanceSaving} className="btn-primary text-sm flex items-center gap-2">
                  <Save size={14} /> {interviewMaintenanceSaving ? 'Saving…' : 'Save'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
