import { useState, useEffect, useMemo } from 'react'
import { Flame, CalendarCheck } from 'lucide-react'
import { engagementApi } from '../../api/engagement'
import { FixitPanel } from '../design'

const DAYS = 119 // ~17 weeks; +1 for today = 120 (matches backend default)

function colorFor(count, future) {
  if (future) return 'bg-surface-900/30'
  if (!count) return 'bg-surface-800/50'
  if (count === 1) return 'bg-accent-amber/25'
  if (count === 2) return 'bg-accent-amber/45'
  if (count <= 4) return 'bg-accent-amber/65'
  return 'bg-accent-amber/85'
}

/**
 * Current-streak number + a compact activity heatmap, built entirely from the
 * /api/streak/ calendar ({ISO-date: count}). Fails closed — renders nothing on
 * error so it never breaks Dashboard/Profile.
 */
export default function StreakWidget({ className = '' }) {
  const [state, setState] = useState({ loading: true, data: null })

  useEffect(() => {
    let cancelled = false
    engagementApi.getStreak(DAYS + 1)
      .then((data) => { if (!cancelled) setState({ loading: false, data: data || null }) })
      .catch(() => { if (!cancelled) setState({ loading: false, data: null }) })
    return () => { cancelled = true }
  }, [])

  // Build week columns (Sun→Sat) ending today, from the calendar map.
  const weeks = useMemo(() => {
    const calendar = state.data?.calendar || {}
    const today = new Date()
    const start = new Date(today)
    start.setDate(start.getDate() - DAYS)
    // Back up to the start of that week (Sunday) so columns align.
    start.setDate(start.getDate() - start.getDay())

    const cols = []
    let cursor = new Date(start)
    while (cursor <= today || cursor.getDay() !== 0) {
      const col = []
      for (let d = 0; d < 7; d++) {
        const key = cursor.toISOString().slice(0, 10)
        col.push({ key, count: calendar[key] || 0, future: cursor > today })
        cursor.setDate(cursor.getDate() + 1)
      }
      cols.push(col)
      if (cursor > today && cursor.getDay() === 0) break
    }
    return cols
  }, [state.data])

  if (state.loading || !state.data) return null

  const current = state.data.current_streak || 0
  const longest = state.data.longest_streak || 0
  const activeDays = state.data.total_active_days || 0

  return (
    <FixitPanel className={`relative overflow-hidden ${className}`}>
      <div className="absolute inset-0 bg-gradient-to-br from-accent-amber/[0.05] via-transparent to-accent-red/[0.03] pointer-events-none" />
      <div className="flex items-center justify-between mb-4 relative">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Flame size={18} className="text-accent-amber" /> Streak
        </h2>
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1.5">
            <span className="text-xl font-black text-accent-amber tabular-nums leading-none">{current}</span>
            <span className="text-surface-500">day{current === 1 ? '' : 's'}</span>
          </span>
        </div>
      </div>

      {/* Mini heatmap */}
      <div className="flex gap-[3px] overflow-x-auto relative pb-1">
        {weeks.map((col, ci) => (
          <div key={ci} className="flex flex-col gap-[3px]">
            {col.map((day) => (
              <div
                key={day.key}
                className={`w-[10px] h-[10px] rounded-sm ${colorFor(day.count, day.future)} transition-colors`}
                title={`${day.key}: ${day.count} solve${day.count === 1 ? '' : 's'}`}
              />
            ))}
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between mt-3 text-[11px] text-surface-500 relative">
        <span className="flex items-center gap-1.5">
          <CalendarCheck size={12} className="text-surface-500" />
          {activeDays} active day{activeDays === 1 ? '' : 's'}
        </span>
        <span>Longest: <strong className="text-surface-300">{longest}</strong></span>
      </div>
    </FixitPanel>
  )
}
