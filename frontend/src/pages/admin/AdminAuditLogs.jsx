import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { ScrollText, RefreshCw, Filter } from 'lucide-react'
import toast from 'react-hot-toast'

export default function AdminAuditLogs() {
  const [logs, setLogs] = useState([])
  const [stats, setStats] = useState([])
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(7)
  const [actionFilter, setActionFilter] = useState('')

  const loadData = async () => {
    setLoading(true)
    try {
      const params = { days: String(days) }
      if (actionFilter) params.action = actionFilter
      const data = await adminApi.getAuditLogs(params)
      setLogs(data.logs || [])
      setStats(data.stats || [])
    } catch {
      toast.error('Failed to load audit logs')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [days, actionFilter])

  const complimentaryLogs = logs.filter(l => l.metadata?.event === 'complimentary_access')

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <ScrollText size={22} className="text-accent-cyan" /> Audit Logs
          </h1>
          <p className="text-surface-400 mt-1">Admin actions, logins, lab events, and complimentary access grants</p>
        </div>
        <button onClick={loadData} className="btn-secondary text-sm flex items-center gap-2">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      <div className="flex flex-wrap gap-3">
        <select value={days} onChange={e => setDays(Number(e.target.value))} className="input-field text-sm w-auto">
          <option value={1}>Last 24 hours</option>
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
        </select>
        <select value={actionFilter} onChange={e => setActionFilter(e.target.value)} className="input-field text-sm w-auto">
          <option value="">All actions</option>
          <option value="admin_action">Admin actions</option>
          <option value="login">Login</option>
          <option value="lab_start">Lab start</option>
          <option value="lab_stop">Lab stop</option>
        </select>
      </div>

      {stats.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {stats.slice(0, 6).map(s => (
            <span key={s.action} className="text-xs px-2 py-1 rounded bg-surface-800 text-surface-300 border border-surface-700">
              {s.action}: {s.count}
            </span>
          ))}
        </div>
      )}

      {complimentaryLogs.length > 0 && (
        <div className="glass-card p-4 border border-accent-green/20">
          <h2 className="text-sm font-semibold text-accent-green mb-2">Recent free access changes</h2>
          <div className="space-y-2">
            {complimentaryLogs.slice(0, 5).map(l => (
              <div key={l.id} className="text-xs text-surface-300 flex justify-between gap-2">
                <span>
                  {l.metadata?.enabled ? 'Granted' : 'Revoked'} for {l.metadata?.target_email || l.metadata?.target_user_id}
                  {l.user ? ` by ${l.user}` : ''}
                </span>
                <span className="text-surface-500 shrink-0">{new Date(l.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="glass-card overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-surface-400">Loading audit logs...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-700">
                  <th className="text-left p-3 text-surface-400 font-medium">Time</th>
                  <th className="text-left p-3 text-surface-400 font-medium">User</th>
                  <th className="text-left p-3 text-surface-400 font-medium">Action</th>
                  <th className="text-left p-3 text-surface-400 font-medium">Resource</th>
                  <th className="text-left p-3 text-surface-400 font-medium">Details</th>
                </tr>
              </thead>
              <tbody>
                {logs.map(log => (
                  <tr key={log.id} className="border-b border-surface-800 hover:bg-surface-800/30">
                    <td className="p-3 text-xs text-surface-500 whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="p-3 text-white">{log.user || '—'}</td>
                    <td className="p-3">
                      <span className="text-xs px-2 py-0.5 rounded bg-surface-800 text-accent-cyan">{log.action}</span>
                    </td>
                    <td className="p-3 text-xs text-surface-400 font-mono truncate max-w-[200px]">{log.resource}</td>
                    <td className="p-3 text-xs text-surface-500 max-w-xs truncate">
                      {log.metadata?.event === 'complimentary_access'
                        ? `${log.metadata.enabled ? 'Grant' : 'Revoke'} ${log.metadata.target_email}`
                        : JSON.stringify(log.metadata || {}).slice(0, 80)}
                    </td>
                  </tr>
                ))}
                {logs.length === 0 && (
                  <tr>
                    <td colSpan={5} className="p-8 text-center text-surface-400">No audit logs in this period</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
