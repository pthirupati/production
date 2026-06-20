import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Calendar, ArrowRight, CheckCircle2, Wrench, Play, Skull, Flame } from 'lucide-react'
import { engagementApi } from '../../api/engagement'
import { FixitPanel } from '../design'

const typeIcon = { fix: Wrench, do: Play, hack: Skull }

/**
 * "Today's Challenge" card — one scenario chosen deterministically by date
 * (same for everyone all day). Fails closed: if the fetch errors or no
 * scenario exists, the card renders nothing so it never breaks the page.
 *
 * Usage: drop <DailyChallengeCard /> on an authed surface (Dashboard / Home).
 */
export default function DailyChallengeCard({ className = '' }) {
  const [state, setState] = useState({ loading: true, challenge: null, completed: false })

  useEffect(() => {
    let cancelled = false
    engagementApi.getDailyChallenge()
      .then((data) => {
        if (cancelled) return
        setState({
          loading: false,
          challenge: data?.challenge || null,
          completed: !!data?.completed,
        })
      })
      .catch(() => { if (!cancelled) setState({ loading: false, challenge: null, completed: false }) })
    return () => { cancelled = true }
  }, [])

  // Hide gracefully while loading or when nothing to show.
  if (state.loading || !state.challenge) return null

  const c = state.challenge
  const TypeIcon = typeIcon[c.scenario_type] || Wrench
  const diffColor = c.difficulty === 'hard'
    ? 'text-accent-red' : c.difficulty === 'medium' ? 'text-accent-amber' : 'text-accent-green'

  return (
    <Link to={`/scenarios/${c.slug}`} className={`block group ${className}`}>
      <FixitPanel
        padding="p-5"
        className="border border-accent-amber/25 bg-gradient-to-r from-accent-amber/[0.08] via-transparent to-accent-purple/[0.04] hover:border-accent-amber/45 transition-colors relative overflow-hidden"
      >
        <div className="flex items-center justify-between gap-4 relative">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-accent-amber/15 border border-accent-amber/25 flex items-center justify-center shrink-0">
              <Flame size={20} className="text-accent-amber" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-accent-amber flex items-center gap-1">
                  <Calendar size={10} /> Today's Challenge
                </span>
                {state.completed && (
                  <span className="text-[10px] text-accent-green flex items-center gap-0.5 font-semibold">
                    <CheckCircle2 size={11} /> Done
                  </span>
                )}
              </div>
              <p className="text-sm font-bold text-white truncate group-hover:text-accent-amber transition-colors">
                {c.title}
              </p>
              <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                <span className={`text-[11px] font-semibold ${diffColor} capitalize`}>{c.difficulty}</span>
                <span className="text-[11px] text-surface-500 flex items-center gap-1">
                  <TypeIcon size={10} /> {c.technology?.name || c.category}
                </span>
              </div>
            </div>
          </div>
          <span className="text-xs text-accent-amber flex items-center gap-1 shrink-0 font-medium">
            <span className="hidden sm:inline">{state.completed ? 'Replay' : 'Solve'}</span> <ArrowRight size={14} />
          </span>
        </div>
      </FixitPanel>
    </Link>
  )
}
