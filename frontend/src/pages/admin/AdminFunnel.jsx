import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { AdminPageHeader } from '../../components/design'
import { Filter, Info, Loader2, Timer, AlertTriangle } from 'lucide-react'
import toast from 'react-hot-toast'

// Activation funnel (audit Z6-6). Derived from first-party rows — no third-party
// analytics, so no consent basis needed and the numbers are retroactive to launch
// rather than to an install date.
//
// The presentation choices matter as much as the data. Two rates are shown per
// stage because they answer different questions: "of signups" is absolute health,
// "of previous" is where the leak actually is. Showing only the first hides which
// step to fix; showing only the second hides how bad it is overall.

const DAY_OPTIONS = [7, 30, 90]

function StageBar({ stage, isWorst }) {
  const width = Math.max(stage.pct_of_signups, 1.5)
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1 gap-3">
        <span className="text-sm text-surface-200 font-medium">{stage.label}</span>
        <span className="text-xs text-surface-500 shrink-0 tabular-nums">
          {stage.users} · {stage.pct_of_signups}% of signups
        </span>
      </div>
      <div className="h-7 rounded-lg bg-surface-800/60 overflow-hidden relative">
        <div
          className={`h-full rounded-lg transition-all ${
            isWorst
              ? 'bg-gradient-to-r from-accent-red/60 to-accent-amber/50'
              : 'bg-gradient-to-r from-accent-cyan/50 to-brand-500/50'
          }`}
          style={{ width: `${width}%` }}
        />
        <span className="absolute inset-y-0 left-3 flex items-center text-xs text-white/90 tabular-nums">
          {stage.pct_of_previous}% of previous step
        </span>
      </div>
    </div>
  )
}

export default function AdminFunnel() {
  const [data, setData] = useState(null)
  const [days, setDays] = useState(30)
  const [loading, setLoading] = useState(true)

  const load = async (refresh = false) => {
    setLoading(true)
    try {
      setData(await adminApi.getFunnel(days, refresh))
      if (refresh) toast.success('Funnel refreshed')
    } catch {
      toast.error('Failed to load funnel')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [days])

  const funnel = data?.funnel
  const stages = funnel?.stages || []

  // Highlight the single biggest drop, which is the whole point of looking at a
  // funnel — a wall of equally-styled bars makes the reader do that arithmetic.
  let worstKey = null
  let worstDrop = 0
  stages.forEach((s) => {
    if (s.key === 'signed_up') return
    const drop = 100 - s.pct_of_previous
    if (drop > worstDrop) { worstDrop = drop; worstKey = s.key }
  })

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Activation Funnel"
        subtitle="Signup → first command → completion → purchase, from first-party data"
        onRefresh={() => load(true)}
        refreshing={loading}
      />

      <div className="flex items-center gap-2">
        <Filter size={14} className="text-surface-500" />
        {DAY_OPTIONS.map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              days === d
                ? 'bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/25'
                : 'text-surface-400 hover:text-white border border-transparent'
            }`}
          >
            {d} days
          </button>
        ))}
      </div>

      {loading && !data ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 size={28} className="text-accent-cyan animate-spin" />
        </div>
      ) : !funnel?.signed_up ? (
        <div className="glass-card p-8 text-center text-surface-400 text-sm">
          No signups in this window.
        </div>
      ) : (
        <>
          <div className="glass-card p-6 space-y-4">
            <p className="text-xs text-surface-500">
              Cohort: {funnel.signed_up} users who signed up in the last {funnel.days} days.
              Every stage counts members of that cohort, so a rate can never exceed 100%.
            </p>
            {stages.map((s) => (
              <StageBar key={s.key} stage={s} isWorst={s.key === worstKey} />
            ))}
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <div className="glass-card p-5">
              <div className="flex items-center gap-2 mb-2">
                <Timer size={15} className="text-accent-cyan" />
                <h3 className="text-sm font-semibold text-white">Time to activation</h3>
              </div>
              {data.time_to_activation?.median_minutes === null ? (
                <p className="text-sm text-surface-500">No activations yet in this window.</p>
              ) : (
                <p className="text-sm text-surface-300">
                  Median{' '}
                  <span className="text-white font-semibold tabular-nums">
                    {data.time_to_activation.median_minutes} min
                  </span>{' '}
                  from signup to first typed command
                  {data.time_to_activation.p90_minutes != null && (
                    <> · p90 <span className="tabular-nums">{data.time_to_activation.p90_minutes} min</span></>
                  )}
                </p>
              )}
            </div>

            <div className="glass-card p-5">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle size={15} className="text-accent-amber" />
                <h3 className="text-sm font-semibold text-white">Provisioning failures</h3>
              </div>
              <p className="text-sm text-surface-300">
                <span className="text-white font-semibold tabular-nums">
                  {funnel.lab_provision_failed_users}
                </span>{' '}
                users in this cohort hit a failed lab start.
              </p>
            </div>
          </div>

          {data.by_technology?.length > 0 && (
            <div className="glass-card p-6">
              <h3 className="text-sm font-semibold text-white mb-3">By technology</h3>
              <p className="text-xs text-surface-500 mb-4">
                A high provisioning-failure rate is an infrastructure problem, not a
                content one — they are separated here so the fix goes to the right place.
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-surface-500 border-b border-surface-700/40">
                      <th className="pb-2 font-medium">Technology</th>
                      <th className="pb-2 font-medium text-right">Learners</th>
                      <th className="pb-2 font-medium text-right">Sessions</th>
                      <th className="pb-2 font-medium text-right">Completed</th>
                      <th className="pb-2 font-medium text-right">Provision fail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.by_technology.map((t) => (
                      <tr key={t.slug || t.technology} className="border-b border-surface-800/40 last:border-0">
                        <td className="py-2 text-surface-200">{t.technology}</td>
                        <td className="py-2 text-right text-surface-400 tabular-nums">{t.learners}</td>
                        <td className="py-2 text-right text-surface-400 tabular-nums">{t.sessions}</td>
                        <td className="py-2 text-right text-surface-300 tabular-nums">{t.completion_rate}%</td>
                        <td className={`py-2 text-right tabular-nums ${
                          t.provision_failure_rate > 10 ? 'text-accent-red' : 'text-surface-400'
                        }`}>
                          {t.provision_failure_rate}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Stated, not hidden. A funnel that silently omits stages it cannot see
              overstates its own completeness. */}
          {funnel.not_tracked && (
            <div className="flex items-start gap-2 text-xs text-surface-500 px-1">
              <Info size={13} className="shrink-0 mt-0.5" />
              <span>
                Not measured: {funnel.not_tracked.stages.join(', ')}. {funnel.not_tracked.reason}
              </span>
            </div>
          )}
        </>
      )}
    </div>
  )
}
