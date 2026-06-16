import { useState, useEffect, useCallback, useRef } from 'react'
import { adminApi } from '../../api/admin'
import { scenarioApi } from '../../api/scenarios'
import {
  CreditCard, IndianRupee, DollarSign, Users, Search, Download,
  Filter, X, RefreshCw, BadgeCheck, XCircle
} from 'lucide-react'
import toast from 'react-hot-toast'

export default function AdminSubscriptions() {
  const [logs, setLogs] = useState([])
  const [interviewLogs, setInterviewLogs] = useState([])
  const [allTechs, setAllTechs] = useState([])
  const [stats, setStats] = useState({ total_revenue: 0, active_count: 0, total_count: 0, exchange_rate: null })
  const [loading, setLoading] = useState(true)

  // Filters
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [currency, setCurrency] = useState('INR')
  const [statusFilter, setStatusFilter] = useState('all')
  const [techFilter, setTechFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [showFilters, setShowFilters] = useState(false)

  const searchTimer = useRef(null)

  // Fetch technologies once for the filter dropdown (independent of filtered logs)
  useEffect(() => {
    scenarioApi.getTechnologies()
      .then(techs => setAllTechs(techs.map(t => t.name).sort()))
      .catch(() => {})
  }, [])

  // Debounce search input — 500ms delay
  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => {
      setDebouncedSearch(search)
    }, 500)
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current) }
  }, [search])

  const loadData = useCallback(async () => {
    setLoading(true)
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
    } catch {
      toast.error('Failed to load subscription logs')
    } finally {
      setLoading(false)
    }
  }, [currency, statusFilter, techFilter, debouncedSearch, dateFrom, dateTo])

  useEffect(() => { loadData() }, [loadData])

  const currencySymbol = currency === 'USD' ? '$' : '\u20B9'
  const CurrencyIcon = currency === 'USD' ? DollarSign : IndianRupee

  const clearFilters = () => {
    setSearch('')
    setDebouncedSearch('')
    setStatusFilter('all')
    setTechFilter('')
    setDateFrom('')
    setDateTo('')
  }

  const hasActiveFilters = debouncedSearch || statusFilter !== 'all' || techFilter || dateFrom || dateTo

  const handleExportCSV = () => {
    const headers = ['Subscription ID', 'Username', 'Email', 'Technology', `Amount (${currency})`, 'Status', 'Payment Verified', 'Started', 'Expires']
    const rows = logs.map(l => [
      l.subscription_id,
      l.user?.username,
      l.user?.email,
      l.technology,
      l.amount_display || `\u20B9${l.amount}`,
      l.is_active ? 'Active' : 'Expired',
      l.payment_verified ? 'Yes' : 'No',
      l.created_at ? new Date(l.created_at).toLocaleDateString() : '',
      l.expires_at ? new Date(l.expires_at).toLocaleDateString() : '',
    ])
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `fixitlab-subscriptions-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('CSV exported')
  }

  if (loading && logs.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold">Subscription Logs</h1>
          <p className="text-surface-400 mt-1">Revenue tracking, filters, and subscription management</p>
        </div>
        <div className="flex items-center gap-2">
          {/* Currency Toggle */}
          <div className="flex bg-surface-800 rounded-lg border border-surface-700/40 overflow-hidden">
            <button
              onClick={() => setCurrency('INR')}
              className={`px-3 py-1.5 text-xs font-medium flex items-center gap-1 transition-all ${
                currency === 'INR' ? 'bg-accent-cyan/20 text-accent-cyan' : 'text-surface-400 hover:text-surface-200'
              }`}
            >
              <IndianRupee size={12} /> INR
            </button>
            <button
              onClick={() => setCurrency('USD')}
              className={`px-3 py-1.5 text-xs font-medium flex items-center gap-1 transition-all ${
                currency === 'USD' ? 'bg-accent-cyan/20 text-accent-cyan' : 'text-surface-400 hover:text-surface-200'
              }`}
            >
              <DollarSign size={12} /> USD
            </button>
          </div>
          <button onClick={loadData} className="p-2 text-surface-400 hover:text-surface-200 hover:bg-surface-800 rounded-lg transition-all" title="Refresh">
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
          <button onClick={handleExportCSV} className="btn-secondary text-xs flex items-center gap-1.5 px-3 py-1.5">
            <Download size={14} /> Export CSV
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-card p-5">
          <CurrencyIcon size={20} className="text-accent-green mb-2" />
          <p className="text-2xl font-bold">{currencySymbol}{typeof stats.total_revenue === 'number' ? stats.total_revenue.toLocaleString(undefined, { maximumFractionDigits: 2 }) : stats.total_revenue}</p>
          <p className="text-sm text-surface-400">Total Revenue ({currency})</p>
          {currency === 'USD' && stats.exchange_rate && (
            <p className="text-xs text-surface-500 mt-1">Rate: 1 USD = {'\u20B9'}{stats.exchange_rate.toFixed(2)}</p>
          )}
        </div>
        <div className="glass-card p-5">
          <CreditCard size={20} className="text-accent-cyan mb-2" />
          <p className="text-2xl font-bold">{stats.active_count}</p>
          <p className="text-sm text-surface-400">Active Subscriptions</p>
        </div>
        <div className="glass-card p-5">
          <Users size={20} className="text-accent-amber mb-2" />
          <p className="text-2xl font-bold">{new Set(logs.map(l => l.user?.id)).size}</p>
          <p className="text-sm text-surface-400">Unique Subscribers</p>
        </div>
        <div className="glass-card p-5">
          <BadgeCheck size={20} className="text-accent-purple mb-2" />
          <p className="text-2xl font-bold">{logs.filter(l => l.payment_verified).length}</p>
          <p className="text-sm text-surface-400">Verified Payments</p>
        </div>
      </div>

      {/* Search + Filter Toggle */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[250px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" size={16} />
          <input
            type="text"
            placeholder="Search by username or email..."
            className="input-field pl-10 w-full"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && search !== debouncedSearch && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <div className="w-4 h-4 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
            </div>
          )}
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`btn-secondary text-xs flex items-center gap-1.5 px-3 py-1.5 ${showFilters ? 'border-accent-cyan/40 text-accent-cyan' : ''}`}
        >
          <Filter size={14} /> Filters {hasActiveFilters && <span className="w-2 h-2 rounded-full bg-accent-cyan" />}
        </button>
        {hasActiveFilters && (
          <button onClick={clearFilters} className="text-xs text-surface-400 hover:text-accent-red flex items-center gap-1">
            <X size={12} /> Clear all
          </button>
        )}
      </div>

      {/* Expandable Filters */}
      {showFilters && (
        <div className="glass-card p-4 grid grid-cols-2 lg:grid-cols-4 gap-4 animate-slide-up">
          <div>
            <label className="text-xs text-surface-400 block mb-1">Status</label>
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
              className="input-field w-full text-sm">
              <option value="all">All</option>
              <option value="active">Active</option>
              <option value="expired">Expired / Cancelled</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-surface-400 block mb-1">Technology</label>
            <select value={techFilter} onChange={e => setTechFilter(e.target.value)}
              className="input-field w-full text-sm">
              <option value="">All Technologies</option>
              {allTechs.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-surface-400 block mb-1">From Date</label>
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
              className="input-field w-full text-sm" />
          </div>
          <div>
            <label className="text-xs text-surface-400 block mb-1">To Date</label>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
              className="input-field w-full text-sm" />
          </div>
        </div>
      )}

      {/* Active filter tags */}
      {hasActiveFilters && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-surface-500">Filters:</span>
          {statusFilter !== 'all' && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-accent-cyan/10 text-accent-cyan rounded text-xs">
              Status: {statusFilter}
              <button onClick={() => setStatusFilter('all')}><X size={10} /></button>
            </span>
          )}
          {techFilter && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-accent-purple/10 text-accent-purple rounded text-xs">
              Tech: {techFilter}
              <button onClick={() => setTechFilter('')}><X size={10} /></button>
            </span>
          )}
          {debouncedSearch && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-accent-amber/10 text-accent-amber rounded text-xs">
              User: {debouncedSearch}
              <button onClick={() => { setSearch(''); setDebouncedSearch('') }}><X size={10} /></button>
            </span>
          )}
          {dateFrom && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-accent-green/10 text-accent-green rounded text-xs">
              From: {dateFrom}
              <button onClick={() => setDateFrom('')}><X size={10} /></button>
            </span>
          )}
          {dateTo && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-accent-green/10 text-accent-green rounded text-xs">
              To: {dateTo}
              <button onClick={() => setDateTo('')}><X size={10} /></button>
            </span>
          )}
        </div>
      )}

      {/* Table */}
      <div className="glass-card overflow-hidden">
        {loading && logs.length > 0 && (
          <div className="h-1 w-full bg-surface-800 overflow-hidden">
            <div className="h-full bg-accent-cyan animate-shimmer w-1/3" />
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-700">
                <th className="text-left p-3 text-surface-400 font-medium">Subscription ID</th>
                <th className="text-left p-3 text-surface-400 font-medium">User</th>
                <th className="text-left p-3 text-surface-400 font-medium">Technology</th>
                <th className="text-left p-3 text-surface-400 font-medium">Amount ({currency})</th>
                <th className="text-left p-3 text-surface-400 font-medium">Status</th>
                <th className="text-left p-3 text-surface-400 font-medium">Verified</th>
                <th className="text-left p-3 text-surface-400 font-medium">Started</th>
                <th className="text-left p-3 text-surface-400 font-medium">Expires</th>
              </tr>
            </thead>
            <tbody>
              {logs.map(log => (
                <tr key={log.id} className="border-b border-surface-800 hover:bg-surface-800/30 transition-colors">
                  <td className="p-3 font-mono text-xs text-cyan-400">{log.subscription_id}</td>
                  <td className="p-3">
                    <div>
                      <p className="font-medium">{log.user?.username}</p>
                      <p className="text-xs text-surface-500">{log.user?.email}</p>
                    </div>
                  </td>
                  <td className="p-3">{log.technology}</td>
                  <td className="p-3 font-semibold">{log.amount_display || `\u20B9${log.amount}`}</td>
                  <td className="p-3">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                      log.is_active
                        ? 'bg-accent-green/10 text-accent-green'
                        : 'bg-surface-700 text-surface-400'
                    }`}>
                      {log.is_active ? <><BadgeCheck size={10} /> Active</> : <><XCircle size={10} /> Expired</>}
                    </span>
                  </td>
                  <td className="p-3">
                    {log.payment_verified ? (
                      <span className="text-accent-green text-xs flex items-center gap-1"><BadgeCheck size={12} /> Yes</span>
                    ) : (
                      <span className="text-surface-500 text-xs">No</span>
                    )}
                  </td>
                  <td className="p-3 text-surface-400 text-xs">
                    {log.created_at ? new Date(log.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                  </td>
                  <td className="p-3 text-xs">
                    {log.expires_at ? (
                      <span className={log.needs_renewal ? 'text-accent-amber font-medium' : 'text-surface-400'}>
                        {new Date(log.expires_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
                        {log.days_until_expiry != null && log.is_active && (
                          <span className="text-surface-500 ml-1">({log.days_until_expiry}d)</span>
                        )}
                      </span>
                    ) : '—'}
                  </td>
                </tr>
              ))}
              {logs.length === 0 && !loading && (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-surface-400">
                    {hasActiveFilters ? 'No matching subscriptions found' : 'No subscriptions yet'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {logs.length > 0 && (
          <div className="px-4 py-3 border-t border-surface-700/30 text-xs text-surface-500 flex items-center justify-between">
            <span>Showing {logs.length} of {stats.total_count} technology subscription{stats.total_count !== 1 ? 's' : ''}</span>
            {currency === 'USD' && stats.exchange_rate && (
              <span>Exchange rate: 1 USD = {'\u20B9'}{stats.exchange_rate.toFixed(2)} (updated hourly)</span>
            )}
          </div>
        )}
      </div>

      {/* Interview entitlements */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-3">Interview Studio subscriptions</h2>
        <p className="text-xs text-surface-500 mb-3">
          1-year plans · 10 interview attempts per period · {stats.interview_active_count || 0} active
        </p>
        <div className="glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-700">
                  <th className="text-left p-3 text-surface-400 font-medium">User</th>
                  <th className="text-left p-3 text-surface-400 font-medium">Plan</th>
                  <th className="text-left p-3 text-surface-400 font-medium">Attempts left</th>
                  <th className="text-left p-3 text-surface-400 font-medium">Status</th>
                  <th className="text-left p-3 text-surface-400 font-medium">Expires</th>
                </tr>
              </thead>
              <tbody>
                {interviewLogs.map(log => (
                  <tr key={log.id} className="border-b border-surface-800 hover:bg-surface-800/30">
                    <td className="p-3">
                      <p className="font-medium">{log.user?.username}</p>
                      <p className="text-xs text-surface-500">{log.user?.email}</p>
                    </td>
                    <td className="p-3 text-indigo-300">{log.technology}</td>
                    <td className="p-3">{log.interviews_remaining}</td>
                    <td className="p-3">
                      {log.is_active ? (
                        <span className="text-accent-green text-xs">Active</span>
                      ) : (
                        <span className="text-surface-500 text-xs">Expired / used</span>
                      )}
                      {log.admin_granted && (
                        <span className="text-[10px] text-amber-400 block">Admin granted</span>
                      )}
                    </td>
                    <td className="p-3 text-xs text-surface-400">
                      {log.expires_at ? new Date(log.expires_at).toLocaleDateString() : '—'}
                    </td>
                  </tr>
                ))}
                {interviewLogs.length === 0 && !loading && (
                  <tr>
                    <td colSpan={5} className="p-8 text-center text-surface-400">No interview entitlements yet</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
