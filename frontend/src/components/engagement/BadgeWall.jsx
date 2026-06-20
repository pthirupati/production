import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Award, Star, ArrowRight } from 'lucide-react'
import { labApi } from '../../api/labs'
import { ACHIEVEMENT_META } from '../../utils/constants'
import { FixitPanel } from '../design'

/**
 * Badge wall — renders the user's achievements as a shareable badge grid,
 * reusing the same /api/achievements/ data + ACHIEVEMENT_META the Achievements
 * page uses. Earned badges are highlighted; locked ones are dimmed.
 * Fails closed — renders nothing if achievements can't be loaded.
 */
export default function BadgeWall({ className = '' }) {
  const [state, setState] = useState({ loading: true, achievements: null })

  useEffect(() => {
    let cancelled = false
    labApi.getAchievements()
      .then((data) => {
        if (!cancelled) setState({ loading: false, achievements: Array.isArray(data) ? data : [] })
      })
      .catch(() => { if (!cancelled) setState({ loading: false, achievements: null }) })
    return () => { cancelled = true }
  }, [])

  if (state.loading || !state.achievements || state.achievements.length === 0) return null

  const achievements = state.achievements
  const earned = achievements.filter((a) => a.earned)

  return (
    <FixitPanel className={`relative overflow-hidden ${className}`}>
      <div className="absolute inset-0 bg-gradient-to-br from-accent-amber/[0.05] via-transparent to-accent-pink/[0.03] pointer-events-none" />
      <div className="flex items-center justify-between mb-4 relative">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Award size={18} className="text-accent-amber" /> Badge Wall
        </h2>
        <Link to="/achievements" className="text-xs text-accent-cyan hover:underline flex items-center gap-1 shrink-0">
          <span className="bg-accent-amber/10 text-accent-amber px-2 py-0.5 rounded-full font-bold border border-accent-amber/20">
            {earned.length}/{achievements.length}
          </span>
          <ArrowRight size={13} />
        </Link>
      </div>

      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2.5 relative">
        {achievements.map((a) => {
          const meta = ACHIEVEMENT_META[a.key] || {}
          const Icon = meta.icon || Star
          return (
            <div
              key={a.key}
              title={`${a.label || meta.label || a.key}${meta.desc ? ` — ${meta.desc}` : ''}${a.earned && a.earned_at ? ` · ${new Date(a.earned_at).toLocaleDateString()}` : a.earned ? '' : ' (locked)'}`}
              className={`flex flex-col items-center text-center p-2.5 rounded-xl border transition-all ${
                a.earned
                  ? `${meta.border || 'border-accent-amber/20'} bg-surface-800/40 hover:scale-[1.04]`
                  : 'border-surface-700/40 bg-surface-900/40 opacity-45 hover:opacity-70'
              }`}
            >
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-1.5 ${
                a.earned ? (meta.bg || 'bg-accent-amber/10') : 'bg-surface-800'
              }`}>
                <Icon size={20} className={a.earned ? (meta.color || 'text-accent-amber') : 'text-surface-600'} />
              </div>
              <span className={`text-[10px] leading-tight ${a.earned ? 'text-surface-300' : 'text-surface-600'}`}>
                {a.label || meta.label || a.key}
              </span>
            </div>
          )
        })}
      </div>
    </FixitPanel>
  )
}
