import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { interviewsApi } from '../../api/interviews'
import { usePageTitle } from '../../hooks/usePageTitle'
import { PageHeader } from '../../components/design'
import SkillRadar from '../../components/interviews/SkillRadar'
import ScoreTrendChart from '../../components/interviews/ScoreTrendChart'
import { TrendingUp, TrendingDown, Award, Target, ChevronLeft, Users } from 'lucide-react'

const REC_LABELS = {
  strong_hire: 'Strong hire', hire: 'Hire', maybe: 'Maybe', no_hire: 'No hire',
}

function StatCard({ icon: Icon, label, value, accent = 'text-white' }) {
  return (
    <div className="glass-card p-4 border border-surface-800">
      <Icon size={16} className="text-indigo-400 mb-2" />
      <p className={`text-2xl font-bold ${accent}`}>{value}</p>
      <p className="text-xs text-surface-500">{label}</p>
    </div>
  )
}

export default function InterviewAnalytics() {
  usePageTitle('Interview Analytics', 'Your interview score trend, skill radar, and progress.')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [isRecruiter, setIsRecruiter] = useState(false)

  useEffect(() => {
    interviewsApi.getMyAnalytics()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
    // Probe recruiter access silently (200 => can compare).
    interviewsApi.compareCandidates().then(() => setIsRecruiter(true)).catch(() => {})
  }, [])

  if (loading) return <p className="text-surface-500 text-sm p-8">Loading analytics…</p>

  const hasData = data && data.attempts > 0
  const improvement = data?.improvement || 0

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in">
      <Link to="/interviews" className="text-xs text-surface-500 hover:text-white inline-flex items-center gap-1">
        <ChevronLeft size={14} /> Back to interviews
      </Link>
      <PageHeader
        eyebrow="AI Interview Studio"
        title="Your performance"
        subtitle="Track your score trend and competency radar across every attempt."
        actions={isRecruiter && (
          <Link to="/interviews/compare" className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-surface-700 text-surface-300 text-sm hover:bg-surface-800">
            <Users size={15} /> Compare candidates
          </Link>
        )}
      />

      {!hasData ? (
        <div className="glass-card p-8 text-center border border-dashed border-surface-700">
          <Target className="mx-auto text-surface-600 mb-3" size={32} />
          <p className="text-surface-400 text-sm">Complete an interview to unlock your analytics dashboard.</p>
          <Link to="/interviews/setup" className="mt-4 inline-block text-sm text-indigo-400 hover:underline">Start an interview →</Link>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard icon={Award} label="Best score" value={Math.round(data.best_score)} />
            <StatCard icon={Target} label="Average score" value={Math.round(data.average_score)} />
            <StatCard icon={TrendingUp} label="Pass rate" value={`${Math.round(data.pass_rate)}%`} />
            <StatCard
              icon={improvement >= 0 ? TrendingUp : TrendingDown}
              label="Improvement"
              value={`${improvement >= 0 ? '+' : ''}${improvement}`}
              accent={improvement >= 0 ? 'text-emerald-400' : 'text-red-400'}
            />
          </div>

          <div className="grid lg:grid-cols-2 gap-4">
            <div className="glass-card p-5 border border-surface-800">
              <h3 className="text-sm font-semibold text-white mb-3">Score trend</h3>
              <ScoreTrendChart trend={data.trend} />
              <p className="text-[10px] text-surface-600 mt-2">Amber dashed line = 65 pass threshold. Green dot = passed.</p>
            </div>
            <div className="glass-card p-5 border border-surface-800">
              <h3 className="text-sm font-semibold text-white mb-3">Competency radar</h3>
              <SkillRadar data={data.radar} />
            </div>
          </div>

          {Object.keys(data.recommendation_breakdown || {}).length > 0 && (
            <div className="glass-card p-4 border border-surface-800">
              <h3 className="text-sm font-semibold text-white mb-3">Recommendations received</h3>
              <div className="flex flex-wrap gap-2">
                {Object.entries(data.recommendation_breakdown).map(([k, v]) => (
                  <span key={k} className="text-xs px-3 py-1.5 rounded-lg border border-surface-700 text-surface-300">
                    {REC_LABELS[k] || k}: <strong className="text-white">{v}</strong>
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="glass-card p-4 border border-surface-800">
            <h3 className="text-sm font-semibold text-white mb-3">Recent attempts</h3>
            <div className="space-y-2">
              {data.trend.slice().reverse().slice(0, 12).map((t, i) => (
                <Link
                  key={i}
                  to={`/interviews/round/${t.round_id}/report`}
                  className="flex items-center justify-between p-2.5 rounded-lg hover:bg-surface-800/60 transition-colors"
                >
                  <div className="min-w-0">
                    <p className="text-sm text-white truncate">{t.title || t.round_type}</p>
                    <p className="text-[11px] text-surface-500">{new Date(t.date).toLocaleDateString()}</p>
                  </div>
                  <span className={`text-sm font-semibold shrink-0 ${t.passed ? 'text-emerald-400' : 'text-red-400'}`}>
                    {Math.round(t.overall_score)}/100
                  </span>
                </Link>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
