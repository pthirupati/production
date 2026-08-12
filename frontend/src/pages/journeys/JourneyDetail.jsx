import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CheckCircle2, Circle, Clock } from 'lucide-react'
import PublicLayout from '../../components/layout/PublicLayout'
import { FixitPanel } from '../../components/design'
import { usePageTitle } from '../../hooks/usePageTitle'
import { journeyApi } from '../../api/journeys'
import PageBreadcrumbs from '../../components/PageBreadcrumbs'
import { STEP_ICON } from './Journeys'

const KIND_LABEL = {
  tutorial_course: 'Course',
  scenarios: 'Labs',
  project: 'Capstone',
  certification: 'Certification',
  milestone: 'Milestone',
}

/**
 * Where each reference kind lives in the SPA. Mirrors _LINK_PREFIX in
 * journeys_views.py — a reference we cannot route to must never become a dead
 * link. Capstone projects resolve to /projects/:slug (audit §C3).
 */
const REF_PREFIX = {
  scenario: '/scenarios/',
  tutorial_course: '/tutorials/',
  project: '/projects/',
  certification: '/certifications/',
}

/**
 * A single referenced item. Links ONLY when the backend resolved the slug to
 * real content AND we have a route for its kind; otherwise it is inert text.
 * `resolved: false` means the slug points at renamed/unseeded content — the
 * step still renders (that's the point of loose refs) but must not advertise a
 * destination that 404s.
 */
function StepReference({ reference }) {
  const prefix = REF_PREFIX[reference.kind]
  const linkable = prefix && reference.resolved
  const done = reference.completed

  const body = (
    <>
      {done ? (
        <CheckCircle2 size={14} className="text-accent-green shrink-0" />
      ) : (
        <Circle size={14} className="text-surface-600 shrink-0" />
      )}
      <span className={done ? 'text-surface-400 line-through' : ''}>{reference.title}</span>
    </>
  )

  if (!linkable) {
    return (
      <li
        className="flex items-center gap-2 text-sm text-surface-400 py-1"
        // Unresolved refs are still listed so the path stays legible, but they
        // are not interactive. Flagged for the reachability/consistency tests.
        data-unresolved={reference.resolved === false ? 'true' : undefined}
        data-testid="journey-step-ref"
      >
        {body}
      </li>
    )
  }

  return (
    <li data-testid="journey-step-ref">
      <Link
        to={`${prefix}${reference.slug}`}
        className="flex items-center gap-2 text-sm text-surface-300 hover:text-accent-purple py-1 transition-colors"
      >
        {body}
      </Link>
    </li>
  )
}

function StepRow({ step, index, isLast }) {
  const Icon = STEP_ICON[step.kind] || Circle
  const references = step.references || []
  // A step is "complete" only when it has measurable items and all are done —
  // same rule as _step_progress() server-side. Milestones are never complete.
  const measurable = references.filter((r) => 'completed' in r)
  const complete = measurable.length > 0 && measurable.every((r) => r.completed)

  return (
    <li className="relative flex gap-4" data-testid="journey-step">
      {/* Timeline rail */}
      <div className="flex flex-col items-center shrink-0">
        <div
          className={`w-9 h-9 rounded-full border flex items-center justify-center ${
            complete
              ? 'bg-accent-green/10 border-accent-green/40 text-accent-green'
              : 'bg-surface-800/70 border-surface-700 text-accent-purple'
          }`}
        >
          <Icon size={16} />
        </div>
        {!isLast && <div className="w-px flex-1 bg-surface-700/70 my-1" aria-hidden="true" />}
      </div>

      <div className="pb-8 flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <span className="text-[10px] font-medium uppercase tracking-wider text-surface-500">
            Step {index + 1} · {KIND_LABEL[step.kind] || step.kind}
          </span>
          {step.est_minutes > 0 && (
            <span className="inline-flex items-center gap-1 text-[10px] text-surface-500">
              <Clock size={10} />
              {step.est_minutes >= 60 ? `~${Math.round(step.est_minutes / 60)}h` : `~${step.est_minutes}m`}
            </span>
          )}
        </div>

        <h3 className="font-display font-semibold text-white leading-snug">{step.title}</h3>
        {step.description && (
          <p className="text-sm text-surface-400 leading-relaxed mt-1">{step.description}</p>
        )}

        {references.length > 0 && (
          <ul className="mt-3 space-y-0.5">
            {references.map((r, i) => (
              <StepReference key={`${r.kind}-${r.slug}-${i}`} reference={r} />
            ))}
          </ul>
        )}
      </div>
    </li>
  )
}

export default function JourneyDetail() {
  const { slug } = useParams()
  const [journey, setJourney] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  usePageTitle(
    journey ? `${journey.title} — Learning Journey` : 'Learning Journey',
    journey?.description || 'A role-based path through FixitLab tutorials, labs and certifications.',
  )

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setNotFound(false)
    journeyApi.detail(slug)
      .then((data) => {
        if (cancelled) return
        if (!data || !data.slug) { setNotFound(true); return }
        setJourney(data)
      })
      .catch(() => { if (!cancelled) setNotFound(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [slug])

  if (loading) {
    return (
      <PublicLayout>
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10">
          <div className="h-8 w-2/3 rounded bg-surface-900/60 animate-pulse mb-4" />
          <div className="h-4 w-full rounded bg-surface-900/40 animate-pulse mb-10" />
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 rounded bg-surface-900/40 animate-pulse mb-4" />
          ))}
        </div>
      </PublicLayout>
    )
  }

  if (notFound || !journey) {
    return (
      <PublicLayout>
        <div className="max-w-xl mx-auto px-4 py-24 text-center">
          <p className="text-surface-400 mb-4">Learning journey not found.</p>
          <Link to="/journeys" className="btn-secondary text-sm">All journeys</Link>
        </div>
      </PublicLayout>
    )
  }

  const steps = journey.steps || []

  return (
    <PublicLayout>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10">
        <PageBreadcrumbs
          className="mb-6"
          items={[
            { label: 'Home', to: '/' },
            { label: 'Journeys', to: '/journeys' },
            { label: journey.title },
          ]}
        />

        <header className="mb-10">
          <p className="text-[11px] font-medium uppercase tracking-wider text-surface-500 mb-1">
            {journey.role_label}
          </p>
          <h1 className="font-display text-3xl font-bold text-white leading-tight mb-3">{journey.title}</h1>
          <p className="text-surface-400 leading-relaxed">{journey.description}</p>
          <div className="flex flex-wrap items-center gap-2 mt-4">
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full border border-surface-700 text-surface-400 capitalize">
              {journey.level}
            </span>
            <span className="text-xs text-surface-500">{steps.length} steps</span>
          </div>
        </header>

        {steps.length === 0 ? (
          <FixitPanel padding="p-8" className="text-center">
            <p className="text-surface-400">This journey has no published steps yet.</p>
          </FixitPanel>
        ) : (
          <ol className="list-none">
            {steps.map((step, i) => (
              <StepRow key={`${step.order}-${i}`} step={step} index={i} isLast={i === steps.length - 1} />
            ))}
          </ol>
        )}
      </div>
    </PublicLayout>
  )
}
