import { useState, useEffect } from 'react'
import { Zap, TrendingUp } from 'lucide-react'
import { engagementApi } from '../../api/engagement'
import { FixitPanel } from '../design'

/**
 * XP / level card with a progress bar toward the next level, from /api/xp/.
 * Fails closed — renders nothing on error so it never breaks the page.
 */
export default function XpLevelCard({ className = '' }) {
  const [state, setState] = useState({ loading: true, data: null })

  useEffect(() => {
    let cancelled = false
    engagementApi.getXp()
      .then((data) => { if (!cancelled) setState({ loading: false, data: data || null }) })
      .catch(() => { if (!cancelled) setState({ loading: false, data: null }) })
    return () => { cancelled = true }
  }, [])

  if (state.loading || !state.data) return null

  const { level = 1, xp = 0, xp_into_level = 0, xp_for_next_level = 0, progress_pct = 0, next_level } = state.data

  return (
    <FixitPanel className={`relative overflow-hidden ${className}`}>
      <div className="absolute inset-0 bg-gradient-to-br from-accent-purple/[0.05] via-transparent to-accent-cyan/[0.03] pointer-events-none" />
      <div className="flex items-center justify-between mb-4 relative">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Zap size={18} className="text-accent-purple" /> Level
        </h2>
        <span className="text-xs text-surface-500 flex items-center gap-1 tabular-nums">
          <TrendingUp size={12} /> {xp.toLocaleString()} XP
        </span>
      </div>

      <div className="flex items-center gap-4 relative">
        <div className="w-14 h-14 rounded-2xl bg-accent-purple/15 border border-accent-purple/25 flex flex-col items-center justify-center shrink-0">
          <span className="text-[9px] uppercase tracking-wider text-accent-purple/70 leading-none">Lvl</span>
          <span className="text-2xl font-black text-accent-purple leading-none tabular-nums">{level}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex justify-between text-xs mb-1.5">
            <span className="text-surface-400">Progress to Level {next_level ?? level + 1}</span>
            <span className="text-accent-purple font-bold tabular-nums">{progress_pct}%</span>
          </div>
          <div className="h-2.5 bg-surface-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-accent-purple to-accent-cyan rounded-full transition-all duration-700"
              style={{ width: `${Math.min(100, Math.max(0, progress_pct))}%` }}
            />
          </div>
          <p className="text-[11px] text-surface-500 mt-1.5 tabular-nums">
            {xp_into_level.toLocaleString()} / {xp_for_next_level.toLocaleString()} XP this level
          </p>
        </div>
      </div>
    </FixitPanel>
  )
}
