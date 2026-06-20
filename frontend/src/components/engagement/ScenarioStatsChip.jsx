import { useState, useEffect } from 'react'
import { Users, Clock, TrendingDown } from 'lucide-react'
import { engagementApi } from '../../api/engagement'

function fmtTime(seconds) {
  if (!seconds) return null
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return m > 0 ? `${m}m${s ? ` ${s}s` : ''}` : `${s}s`
}

/**
 * Per-scenario stats chip — avg solve time, learner count, fail rate.
 *
 * Two modes:
 *  - Pass `stats` (already-loaded ScenarioStats object) to render inline with
 *    zero network cost (used on list cards).
 *  - Pass `slug` to self-fetch from /api/scenarios/<slug>/stats/ (used on the
 *    detail page — one request).
 *
 * Renders nothing when there's no meaningful data (safe default / unavailable),
 * so cards never show empty or broken chips.
 */
export default function ScenarioStatsChip({ slug, stats: statsProp, className = '' }) {
  const [stats, setStats] = useState(statsProp || null)

  useEffect(() => {
    if (statsProp || !slug) return
    let cancelled = false
    engagementApi.getScenarioStats(slug)
      .then((data) => { if (!cancelled) setStats(data || null) })
      .catch(() => { if (!cancelled) setStats(null) })
    return () => { cancelled = true }
  }, [slug, statsProp])

  if (!stats) return null

  const learners = stats.learners || 0
  const avgTime = fmtTime(stats.avg_solve_seconds)
  const failRate = stats.fail_rate_pct

  // Nothing worth showing yet — hide rather than render zeros.
  if (!learners && !avgTime) return null

  return (
    <div className={`flex items-center gap-3 flex-wrap text-[11px] text-surface-500 ${className}`}>
      {learners > 0 && (
        <span className="inline-flex items-center gap-1" title="Learners who attempted this">
          <Users size={11} className="text-surface-500 shrink-0" /> {learners.toLocaleString()}
        </span>
      )}
      {avgTime && (
        <span className="inline-flex items-center gap-1" title="Average solve time">
          <Clock size={11} className="text-surface-500 shrink-0" /> {avgTime} avg
        </span>
      )}
      {learners > 0 && failRate > 0 && (
        <span className="inline-flex items-center gap-1" title="Share of learners who attempted but haven't solved it">
          <TrendingDown size={11} className="text-accent-amber/70 shrink-0" /> {failRate}% fail
        </span>
      )}
    </div>
  )
}
