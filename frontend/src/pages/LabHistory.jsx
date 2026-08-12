import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../api/auth'
import { CheckCircle2, XCircle, Clock, ArrowRight, Server, Cloud, Box, Play } from 'lucide-react'
import toast from 'react-hot-toast'
import Pagination from '../components/Pagination'
import { PageHeader } from '../components/design'

const PAGE_SIZE = 20

const STATUS_STYLES = {
  COMPLETED: { color: 'text-accent-green', bg: 'bg-accent-green/10', label: 'Completed' },
  TERMINATED: { color: 'text-surface-400', bg: 'bg-surface-700/30', label: 'Stopped' },
  RUNNING: { color: 'text-accent-cyan', bg: 'bg-accent-cyan/10', label: 'Running' },
  FAILED: { color: 'text-accent-red', bg: 'bg-accent-red/10', label: 'Failed' },
}

function formatDuration(start, end) {
  if (!start) return '—'
  const s = new Date(start)
  const e = end ? new Date(end) : new Date()
  const diff = Math.floor((e - s) / 1000)
  if (diff < 60) return `${diff}s`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ${diff % 60}s`
  return `${Math.floor(diff / 3600)}h ${Math.floor((diff % 3600) / 60)}m`
}

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function LabHistory() {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)

  useEffect(() => {
    authApi.getLabHistory()
      .then((data) => setHistory(data.history || []))
      .catch(() => toast.error('Failed to load lab history'))
      .finally(() => setLoading(false))
  }, [])

  const passed = history.filter(h => h.passed).length
  const total = history.length

  return (
    <div className="space-y-4 animate-fade-in">
      <PageHeader
        eyebrow="Your progress"
        title="Lab History"
        subtitle={`${total} session${total !== 1 ? 's' : ''} · ${passed} passed`}
      />

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="glass-card p-4 text-center">
          <p className="text-2xl font-bold text-white">{total}</p>
          <p className="text-xs text-surface-400 mt-1">Total Labs</p>
        </div>
        <div className="glass-card p-4 text-center">
          <p className="text-2xl font-bold text-accent-green">{passed}</p>
          <p className="text-xs text-surface-400 mt-1">Passed</p>
        </div>
        <div className="glass-card p-4 text-center">
          <p className="text-2xl font-bold text-accent-red">{total - passed}</p>
          <p className="text-xs text-surface-400 mt-1">Not Passed</p>
        </div>
        <div className="glass-card p-4 text-center">
          <p className="text-2xl font-bold text-accent-cyan">{total > 0 ? Math.round((passed / total) * 100) : 0}%</p>
          <p className="text-xs text-surface-400 mt-1">Pass Rate</p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
        </div>
      ) : history.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <Server size={48} className="text-surface-600 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-white mb-2">No lab sessions yet</h3>
          <p className="text-surface-400 text-sm mb-4">Start your first lab to see your history here</p>
          <Link to="/scenarios" className="btn-primary px-6 inline-flex items-center gap-2">
            Browse Scenarios <ArrowRight size={16} />
          </Link>
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-700/50 text-left">
                <th className="px-4 py-3 text-surface-400 font-medium">Scenario</th>
                <th className="px-4 py-3 text-surface-400 font-medium">Status</th>
                <th className="px-4 py-3 text-surface-400 font-medium hidden md:table-cell">Provider</th>
                <th className="px-4 py-3 text-surface-400 font-medium hidden sm:table-cell">Duration</th>
                <th className="px-4 py-3 text-surface-400 font-medium">Result</th>
                <th className="px-4 py-3 text-surface-400 font-medium hidden lg:table-cell">Date</th>
                <th className="px-4 py-3 text-surface-400 font-medium">Replay</th>
              </tr>
            </thead>
            <tbody>
              {history.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).map((session) => {
                const st = STATUS_STYLES[session.status] || STATUS_STYLES.TERMINATED
                return (
                  <tr key={session.id} className="border-b border-surface-800/40 hover:bg-surface-800/20 transition-colors">
                    <td className="px-4 py-3">
                      <Link to={`/scenarios/${session.scenario_slug}`} className="text-white hover:text-accent-cyan transition-colors font-medium">
                        {session.scenario}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${st.bg} ${st.color}`}>
                        {st.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell">
                      <span className="text-surface-400 flex items-center gap-1.5">
                        {session.provider === 'docker' ? <Box size={12} /> : <Cloud size={12} />}
                        {session.provider || 'docker'}
                      </span>
                    </td>
                    <td className="px-4 py-3 hidden sm:table-cell">
                      <span className="text-surface-400 flex items-center gap-1">
                        <Clock size={12} /> {formatDuration(session.started_at, session.ended_at)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {session.passed ? (
                        <CheckCircle2 size={16} className="text-accent-green" />
                      ) : (
                        <XCircle size={16} className="text-surface-600" />
                      )}
                    </td>
                    <td className="px-4 py-3 hidden lg:table-cell text-surface-500 text-xs">
                      {formatDate(session.started_at)}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/session-replay/${session.id}`}
                        className="text-surface-500 hover:text-accent-cyan transition-colors"
                        title="View replay & commands"
                      >
                        <Play size={14} />
                      </Link>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {history.length > PAGE_SIZE && (
            <Pagination
              currentPage={page}
              totalPages={Math.ceil(history.length / PAGE_SIZE)}
              onPageChange={(p) => { setPage(p); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
            />
          )}
        </div>
      )}
    </div>
  )
}
