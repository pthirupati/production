import { useMemo } from 'react'
import { Flame } from 'lucide-react'

/**
 * GitHub-style activity heatmap showing lab activity over the past year.
 * Each cell represents one day, colored by activity level.
 */
export default function ActivityHeatmap({ recentActivity = [] }) {
  const today = new Date()
  const totalWeeks = 52

  // Build activity map: date string → count
  const activityMap = useMemo(() => {
    const map = {}
    recentActivity.forEach(item => {
      const d = item.created_at || item.date || item.ended_at
      if (d) {
        const key = new Date(d).toISOString().slice(0, 10)
        map[key] = (map[key] || 0) + 1
      }
    })
    return map
  }, [recentActivity])

  // Generate grid data (52 weeks × 7 days)
  const weeks = useMemo(() => {
    const result = []
    // Start from (totalWeeks * 7) days ago
    const startDate = new Date(today)
    startDate.setDate(startDate.getDate() - (totalWeeks * 7) + (7 - startDate.getDay()))

    for (let w = 0; w < totalWeeks; w++) {
      const week = []
      for (let d = 0; d < 7; d++) {
        const date = new Date(startDate)
        date.setDate(startDate.getDate() + (w * 7) + d)
        const key = date.toISOString().slice(0, 10)
        const count = activityMap[key] || 0
        const future = date > today
        week.push({ date: key, count, future })
      }
      result.push(week)
    }
    return result
  }, [activityMap])

  const getColor = (count, future) => {
    if (future) return 'bg-surface-900/30'
    if (count === 0) return 'bg-surface-800/50'
    if (count === 1) return 'bg-accent-green/20'
    if (count === 2) return 'bg-accent-green/40'
    if (count <= 4) return 'bg-accent-green/60'
    return 'bg-accent-green/80'
  }

  const totalLabs = Object.values(activityMap).reduce((s, c) => s + c, 0)
  const activeDays = Object.keys(activityMap).length

  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Flame size={18} className="text-accent-green" /> Activity
        </h2>
        <div className="flex items-center gap-4 text-xs text-surface-400">
          <span><strong className="text-white">{totalLabs}</strong> labs</span>
          <span><strong className="text-white">{activeDays}</strong> active days</span>
        </div>
      </div>

      {/* Month labels */}
      <div className="flex gap-[2px] mb-1 ml-8">
        {weeks.map((week, wi) => {
          // Show month label at start of each month
          const firstDay = new Date(week[0].date)
          if (firstDay.getDate() <= 7 && wi > 0) {
            return (
              <div key={wi} className="w-[11px] text-[9px] text-surface-500 text-center">
                {months[firstDay.getMonth()]}
              </div>
            )
          }
          return <div key={wi} className="w-[11px]" />
        })}
      </div>

      {/* Heatmap grid */}
      <div className="flex gap-0">
        {/* Day labels */}
        <div className="flex flex-col gap-[2px] mr-1 text-[9px] text-surface-500">
          <span className="h-[11px]"></span>
          <span className="h-[11px] leading-[11px]">Mon</span>
          <span className="h-[11px]"></span>
          <span className="h-[11px] leading-[11px]">Wed</span>
          <span className="h-[11px]"></span>
          <span className="h-[11px] leading-[11px]">Fri</span>
          <span className="h-[11px]"></span>
        </div>

        {/* Grid */}
        <div className="flex gap-[2px] overflow-x-auto">
          {weeks.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-[2px]">
              {week.map((day) => (
                <div
                  key={day.date}
                  className={`w-[11px] h-[11px] rounded-sm ${getColor(day.count, day.future)} transition-colors`}
                  title={`${day.date}: ${day.count} lab${day.count !== 1 ? 's' : ''}`}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-end gap-1.5 mt-3">
        <span className="text-[10px] text-surface-500">Less</span>
        <div className="w-[11px] h-[11px] rounded-sm bg-surface-800/50" />
        <div className="w-[11px] h-[11px] rounded-sm bg-accent-green/20" />
        <div className="w-[11px] h-[11px] rounded-sm bg-accent-green/40" />
        <div className="w-[11px] h-[11px] rounded-sm bg-accent-green/60" />
        <div className="w-[11px] h-[11px] rounded-sm bg-accent-green/80" />
        <span className="text-[10px] text-surface-500">More</span>
      </div>
    </div>
  )
}
