import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Route, ArrowRight, GraduationCap, FlaskConical, BookOpen, Hammer, Flag } from 'lucide-react'
import PublicLayout from '../../components/layout/PublicLayout'
import MarketingPageShell from '../../components/MarketingPageShell'
import { FixitPanel } from '../../components/design'
import { usePageTitle } from '../../hooks/usePageTitle'
import { journeyApi } from '../../api/journeys'

const LEVEL_BADGE = {
  beginner: 'text-accent-green bg-accent-green/10 border-accent-green/20',
  intermediate: 'text-accent-cyan bg-accent-cyan/10 border-accent-cyan/20',
  advanced: 'text-accent-amber bg-accent-amber/10 border-accent-amber/20',
}

/** Step kinds map 1:1 to JourneyStep.KIND_CHOICES (question_bank/models.py:644). */
export const STEP_ICON = {
  tutorial_course: BookOpen,
  scenarios: FlaskConical,
  project: Hammer,
  certification: GraduationCap,
  milestone: Flag,
}

/** Total authored minutes across a journey's steps, rendered as "~12h". */
function totalHours(steps) {
  const minutes = (steps || []).reduce((sum, s) => sum + (s.est_minutes || 0), 0)
  if (!minutes) return null
  return minutes >= 60 ? `~${Math.round(minutes / 60)}h` : `~${minutes}m`
}

function JourneyCard({ journey }) {
  const steps = journey.steps || []
  const hours = totalHours(steps)
  const levelCls = LEVEL_BADGE[journey.level] || LEVEL_BADGE.intermediate
  return (
    <Link
      to={`/journeys/${journey.slug}`}
      className="group fx-panel p-5 flex flex-col hover:border-accent-purple/40 transition-colors"
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="w-10 h-10 rounded-lg bg-surface-800/70 border border-surface-700 flex items-center justify-center text-accent-purple group-hover:border-accent-purple/40 transition-colors">
          <Route size={20} />
        </div>
        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border capitalize ${levelCls}`}>
          {journey.level}
        </span>
      </div>

      <p className="text-[11px] font-medium uppercase tracking-wider text-surface-500 mb-1">
        {journey.role_label}
      </p>
      <h3 className="font-display font-semibold text-white text-base leading-snug mb-1.5 group-hover:text-accent-purple transition-colors">
        {journey.title}
      </h3>
      <p className="text-sm text-surface-400 leading-relaxed flex-1">{journey.description}</p>

      {/* Step-kind rail: shows the shape of the path (learn → labs → build → certify)
          without listing every milestone on a card. */}
      {steps.length > 0 && (
        <div className="mt-4 flex items-center gap-1.5 text-surface-500">
          {steps.slice(0, 7).map((s, i) => {
            const Icon = STEP_ICON[s.kind] || Flag
            return <Icon key={`${s.order}-${i}`} size={13} aria-hidden="true" />
          })}
          {steps.length > 7 && <span className="text-[10px]">+{steps.length - 7}</span>}
        </div>
      )}

      <div className="mt-3 flex items-center justify-between gap-2">
        <span className="text-xs text-surface-500">
          {journey.step_count || steps.length} steps{hours ? ` · ${hours}` : ''}
        </span>
        <span className="flex items-center gap-1.5 text-xs font-medium text-accent-purple">
          View path
          <ArrowRight size={12} className="opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all" />
        </span>
      </div>
    </Link>
  )
}

export default function Journeys() {
  const [journeys, setJourneys] = useState([])
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  usePageTitle(
    'Learning Journeys',
    'Role-based paths that bundle tutorials, hands-on labs, a capstone project and a certification track into one ordered plan.',
  )

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setFailed(false)
    journeyApi.list()
      .then((data) => { if (!cancelled) setJourneys(data || []) })
      // "Request failed" and "no journeys seeded" render differently: an empty
      // catalog is a normal state, a failed fetch needs a retry affordance.
      .catch(() => { if (!cancelled) setFailed(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  return (
    <PublicLayout>
      <MarketingPageShell
        eyebrow="Guided paths"
        title="Learning Journeys"
        subtitle="Each journey is an ordered path for one role: learn the fundamentals, ramp through hands-on labs easy → hard, build a capstone, then prove it on a certification track."
      >
        {loading ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="fx-panel p-5 h-56 animate-pulse bg-surface-900/40" />
            ))}
          </div>
        ) : failed ? (
          <FixitPanel padding="p-8" className="text-center">
            <p className="text-surface-300 mb-1">Couldn&apos;t load learning journeys.</p>
            <p className="text-sm text-surface-500 mb-4">This is a loading problem, not missing content.</p>
            <button onClick={() => window.location.reload()} className="btn-secondary text-sm">Retry</button>
          </FixitPanel>
        ) : journeys.length === 0 ? (
          <FixitPanel padding="p-8" className="text-center">
            <p className="text-surface-300 mb-1">No learning journeys are published yet.</p>
            <Link to="/scenarios" className="btn-secondary text-sm mt-3 inline-block">Browse labs instead</Link>
          </FixitPanel>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {journeys.map((j) => <JourneyCard key={j.slug} journey={j} />)}
          </div>
        )}

        <FixitPanel className="mt-12 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4" padding="p-5">
          <div className="flex items-start gap-3">
            <GraduationCap size={20} className="text-accent-cyan mt-0.5 shrink-0" />
            <div>
              <h2 className="font-display font-semibold text-white">Prefer to pick your own labs?</h2>
              <p className="text-sm text-surface-400">Every journey is built from the same catalog you can browse directly.</p>
            </div>
          </div>
          <Link to="/scenarios" className="btn-secondary text-sm shrink-0">Browse all labs</Link>
        </FixitPanel>
      </MarketingPageShell>
    </PublicLayout>
  )
}
