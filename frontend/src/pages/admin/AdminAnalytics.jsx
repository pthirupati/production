import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { BarChart3, TrendingUp, Target, RefreshCw, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'

export default function AdminAnalytics() {
  const [data, setData] = useState(null)
  const [days, setDays] = useState(30)
  const [loading, setLoading] = useState(true)

  const load = async (refresh = false) => {
    setLoading(true)
    try {
      const res = await adminApi.getAnalytics(days, refresh)
      setData(res)
      if (refresh) toast.success('Analytics refreshed')
    } catch {
      toast.error('Failed to load analytics')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [days])

  const maxDaily = Math.max(...(data?.daily_labs?.map(d => d.count) || [1]), 1)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart3 size={24} className="text-accent-cyan" /> Analytics
          </h1>
          <p className="text-surface-400 text-sm mt-1">Lab activity, top scenarios, difficulty mix</p>
        </div>
        <div className="flex items-center gap-3">
          <select value={days} onChange={e => setDays(Number(e.target.value))} className="input-field text-sm py-2">
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button onClick={() => load(true)} className="btn-secondary flex items-center gap-2 text-sm">
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader2 className="animate-spin text-accent-cyan" size={32} /></div>
      ) : (
        <>
          {data?.summary && (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              {[
                ['New users', data.summary.new_users, 'text-accent-cyan'],
                ['Active users', data.summary.active_users, 'text-accent-green'],
                ['Lab starts', data.summary.total_lab_starts, 'text-accent-purple'],
                ['Completed labs', data.summary.completed_labs, 'text-accent-amber'],
                ['Completion rate', `${data.summary.completion_rate_pct ?? 0}%`, 'text-accent-green'],
                ['New subscriptions', data.summary.new_subscriptions, 'text-accent-blue'],
                ['Revenue (INR)', `₹${Math.round(data.summary.revenue_inr ?? 0)}`, 'text-accent-amber'],
                ['Interviews', data.summary.interview_campaigns, 'text-accent-pink'],
              ].map(([label, val, cls]) => (
                <div key={label} className="glass-card p-4">
                  <p className={`text-2xl font-bold ${cls}`}>{val ?? 0}</p>
                  <p className="text-xs text-surface-400 mt-1">{label}</p>
                </div>
              ))}
            </div>
          )}

          <div className="glass-card p-6">
            <h2 className="text-sm font-semibold text-surface-400 uppercase tracking-wider mb-4 flex items-center gap-2">
              <TrendingUp size={16} /> Daily Lab Starts
            </h2>
            <div className="flex items-end gap-1 h-40">
              {(data?.daily_labs || []).map(d => (
                <div key={d.date} className="flex-1 flex flex-col items-center gap-1 group">
                  <span className="text-[10px] text-surface-500 opacity-0 group-hover:opacity-100">{d.count}</span>
                  <div
                    className="w-full bg-gradient-to-t from-accent-cyan/80 to-accent-cyan/30 rounded-t min-h-[4px] transition-all"
                    style={{ height: `${Math.max(4, (d.count / maxDaily) * 100)}%` }}
                    title={`${d.date}: ${d.count} labs`}
                  />
                  <span className="text-[9px] text-surface-600 rotate-[-45deg] origin-top-left mt-2 hidden sm:block">{d.date.slice(5)}</span>
                </div>
              ))}
              {(!data?.daily_labs || data.daily_labs.length === 0) && (
                <p className="text-surface-500 text-sm">No lab activity in this period.</p>
              )}
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            <div className="glass-card p-6">
              <h2 className="text-sm font-semibold text-surface-400 uppercase tracking-wider mb-4">Top Technologies (lab starts)</h2>
              <div className="space-y-2">
                {(data?.top_technologies || []).map((t, i) => (
                  <div key={i} className="flex items-center justify-between text-sm py-2 border-b border-surface-800/50 last:border-0">
                    <span className="text-surface-300">{t.scenario__technology__name || t.scenario__technology__slug}</span>
                    <span className="text-surface-500">{t.count} starts</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            <div className="glass-card p-6">
              <h2 className="text-sm font-semibold text-surface-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                <Target size={16} /> Top Scenarios
              </h2>
              <div className="space-y-2">
                {(data?.top_scenarios || []).map((s, i) => (
                  <div key={i} className="flex items-center justify-between text-sm py-2 border-b border-surface-800/50 last:border-0">
                    <span className="text-surface-300 truncate flex-1 mr-2">{s.title}</span>
                    <span className="text-surface-500 shrink-0">{s.attempt_count} tries · {s.completion_count} done</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="glass-card p-6">
              <h2 className="text-sm font-semibold text-surface-400 uppercase tracking-wider mb-4">Difficulty Mix</h2>
              <div className="space-y-3">
                {(data?.difficulty_distribution || []).map(d => (
                  <div key={d.difficulty}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-surface-300 capitalize">{d.difficulty}</span>
                      <span className="text-surface-500">{d.count}</span>
                    </div>
                    <div className="h-2 bg-surface-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent-purple rounded-full"
                        style={{ width: `${Math.min(100, (d.count / Math.max(...(data?.difficulty_distribution || []).map(x => x.count), 1)) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {data?.cached_at && (
            <p className="text-xs text-surface-600 text-center">Cached at {new Date(data.cached_at).toLocaleString()}</p>
          )}
        </>
      )}
    </div>
  )
}
