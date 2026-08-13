import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link, useLocation } from 'react-router-dom'
import { scenarioApi } from '../api/scenarios'
import { labApi } from '../api/labs'
import { ratingsApi } from '../api/ratings'
import SmallScreenLabGate, { useSmallScreenLabGate } from '../components/SmallScreenLabGate'
import { jiraApi } from '../api/jira'
import ScenarioIssueBar from '../components/ScenarioIssueBar'
import JiraTeamGuide from '../components/JiraTeamGuide'
import StickyPageToolbar from '../components/StickyPageToolbar'
import ScenarioNarrative from '../components/scenarios/ScenarioNarrative'
import LimitReachedModal from '../components/LimitReachedModal'
import { useAuthStore } from '../store/authStore'
import { getScenarioSimInfo } from '../utils/simScenario'
import {
  Clock, Target, Lightbulb, Play, CheckCircle2,
  Wrench, Skull, ArrowLeft, BookmarkPlus, Bookmark,
  Users, BarChart3, Hash, Lock, Eye, Zap, Star, Send, Monitor, BookOpen,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { PageHeader } from '../components/design'
import { ScenarioStatsChip } from '../components/engagement'
import { usePageTitle } from '../hooks/usePageTitle'
import { useStructuredData, scenarioCourseSchema, breadcrumbSchema } from '../hooks/useStructuredData'
import PageBreadcrumbs from '../components/PageBreadcrumbs'

const typeConfig = {
  fix: { icon: Wrench, label: 'Fix', desc: 'Find and fix the broken service' },
  do:  { icon: Play, label: 'Do', desc: 'Complete the given task' },
  hack: { icon: Skull, label: 'Hack', desc: 'Exploit a vulnerability or find a flag' },
}

function StatPill({ icon: Icon, children }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-surface-400 whitespace-nowrap">
      <Icon size={14} className="text-surface-500 shrink-0" />
      {children}
    </span>
  )
}

export default function ScenarioDetail() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const { isAuthenticated } = useAuthStore()
  const [scenario, setScenario] = useState(null)
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [showSolution, setShowSolution] = useState(false)
  const [limitInfo, setLimitInfo] = useState(null)
  // The API returns {average_score, has_enough_ratings, total_ratings,
  // distribution, recent_reviews}. This page read `r.ratings || r.results` —
  // neither key has ever existed, so the reviews list rendered "No reviews yet"
  // and `avgRating` averaged an empty array, on every scenario, always. Found
  // while wiring the Z3-10 small-sample suppression: the suppression had nothing
  // to suppress because nothing was displayed.
  const [ratings, setRatings] = useState([])
  const [ratingSummary, setRatingSummary] = useState(null)
  const labGate = useSmallScreenLabGate()
  const [userRating, setUserRating] = useState(0)
  const [hoverRating, setHoverRating] = useState(0)
  const [reviewText, setReviewText] = useState('')
  const [submittingRating, setSubmittingRating] = useState(false)
  const [jiraTicket, setJiraTicket] = useState(null)
  const [jiraComments, setJiraComments] = useState([])
  const [activeLabSession, setActiveLabSession] = useState(null)

  usePageTitle(
    scenario?.title,
    scenario ? `${scenario.subtitle || scenario.description?.slice(0, 155) || ''} — hands-on lab on FixitLab` : undefined,
    scenario ? { canonical: `${window.location.origin}/scenarios/${scenario.slug}` } : undefined,
  )

  // Audit Z6-7: there was no structured data anywhere. A scenario IS a Course, and
  // there are 7,280 of them — the highest-value markup on the site.
  useStructuredData('course', scenarioCourseSchema(scenario))
  useStructuredData('breadcrumb', breadcrumbSchema([
    { name: 'Home', path: '/' },
    { name: 'Scenarios', path: '/scenarios' },
    ...(scenario?.technology_name
      ? [{ name: scenario.technology_name, path: `/scenarios?technology=${scenario.technology_name}` }]
      : []),
    ...(scenario?.title ? [{ name: scenario.title }] : []),
  ]))

  const loadJiraTicket = (scenarioId, accessible) => {
    if (!isAuthenticated || !scenarioId || accessible === false) {
      setJiraTicket(null)
      setJiraComments([])
      return
    }
    jiraApi.ensureScenarioTicket(scenarioId)
      .then(res => {
        setJiraTicket(res.data?.ticket || null)
        setJiraComments(res.data?.recent_comments || [])
      })
      .catch(err => {
        if (err.response?.status === 403) {
          setJiraTicket(null)
          setJiraComments([])
          return
        }
        setJiraTicket(null)
        setJiraComments([])
      })
  }

  useEffect(() => {
    if (location.state?.labExpired) {
      toast('Lab time completed — the environment has been terminated. You can try again anytime!', {
        icon: '⏰', duration: 7000, closeButton: true,
      })
      window.history.replaceState({}, '')
    }
    if (location.state?.labCompleted) {
      toast.success(
        location.state.score != null
          ? `Challenge solved! Score: ${location.state.score}`
          : 'Challenge solved! Great work.',
        { duration: 7000 },
      )
      window.history.replaceState({}, '')
    }

    scenarioApi.getScenarioDetail(slug)
      .then(data => {
        setScenario(data)
        loadJiraTicket(data?.id, data?.is_accessible)
        ratingsApi.getRatings({ type: 'scenario', scenario: data.id })
          .then(r => { setRatings(r.recent_reviews || []); setRatingSummary(r) })
          .catch(() => {})
      })
      .catch(() => toast.error('Scenario not found'))
      .finally(() => setLoading(false))
  }, [slug])

  useEffect(() => {
    if (!isAuthenticated || !scenario?.id) return
    labApi.getActiveLabs().then(labs => {
      const list = Array.isArray(labs) ? labs : (labs?.results || [])
      const active = list.find(l => l.scenario === scenario.id && ['RUNNING', 'PROVISIONING'].includes(l.status))
      setActiveLabSession(active || null)
    }).catch(() => setActiveLabSession(null))
  }, [isAuthenticated, scenario?.id, starting])

  const handleStartLab = async () => {
    if (!isAuthenticated) { navigate('/login'); return }
    if (scenario.is_accessible === false) {
      toast.error('Subscribe to this technology first')
      navigate('/pricing')
      return
    }
    // Audit Z6-9: warn before provisioning, not after. Starting is what consumes a
    // daily lab slot, so the interstitial has to come first — checked after the
    // auth and subscription gates so a phone user is not warned about a lab they
    // cannot start anyway.
    if (!labGate.guard(() => { void startLabNow() })) return
    await startLabNow()
  }

  const startLabNow = async () => {
    setStarting(true)
    try {
      const session = await labApi.startLab(scenario.id)
      if (session.jira_reset) {
        toast(`Fresh attempt #${session.jira_run_count || 1} — ticket history cleared`, {
          icon: '🔄', duration: 5000, closeButton: true,
        })
        loadJiraTicket(scenario.id, scenario.is_accessible)
      } else if (session.jira_issue_key) {
        setJiraTicket({
          issue_key: session.jira_issue_key,
          issue_url: '',
          jira_status: session.jira_status || 'In Progress',
          run_count: session.jira_run_count || 1,
        })
      }
      if (session.resumed) {
        toast('You already have an active lab for this scenario — reconnecting...', {
          icon: '🔄', duration: 4000, closeButton: true,
        })
      } else if (session.status === 'PROVISIONING') {
        toast('Launching cloud server — please wait...', { icon: '☁️', duration: 5000, closeButton: true })
      } else {
        toast.success('Lab environment ready!')
      }
      navigate(`/lab/${session.id}`, { state: { techSlug: scenario.technology?.slug || '' } })
    } catch (err) {
      const data = err.response?.data
      if (data?.code === 'LIMIT_REACHED') {
        setLimitInfo(data)
      } else if (data?.code === 'SUBSCRIPTION_REQUIRED') {
        toast.error(`Subscription required for ${data.technology}`)
        navigate('/pricing')
      } else {
        const msg = data?.error || 'Failed to start lab'
        toast.error(msg)
        // Only reconnect to an existing session when the API explicitly says to
        // resume — never bounce the learner back to a different lab they stopped.
        if (data?.resumed && data?.session_id) navigate(`/lab/${data.session_id}`)
      }
    } finally {
      setStarting(false)
    }
  }

  const handleBookmark = async () => {
    if (!isAuthenticated) { toast.error('Sign in to bookmark'); return }
    try {
      const result = await scenarioApi.toggleBookmark(scenario.id)
      setScenario(prev => ({ ...prev, is_bookmarked: result.bookmarked }))
      toast.success(result.bookmarked ? 'Bookmarked!' : 'Removed')
    } catch { toast.error('Failed') }
  }

  const handleSubmitRating = async () => {
    if (!isAuthenticated) { toast.error('Sign in to rate'); return }
    if (!userRating) { toast.error('Select a star rating'); return }
    setSubmittingRating(true)
    try {
      await ratingsApi.submitRating({ ratingType: 'scenario', scenario: scenario.id, score: userRating, review: reviewText })
      toast.success('Rating submitted!')
      setReviewText('')
      const r = await ratingsApi.getRatings({ type: 'scenario', scenario: scenario.id })
      setRatings(r.recent_reviews || [])
      setRatingSummary(r)
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to submit rating')
    } finally {
      setSubmittingRating(false)
    }
  }

  if (loading) return (
    <div className="max-w-4xl mx-auto space-y-6 animate-pulse">
      <div className="h-4 w-32 bg-surface-800 rounded" />
      <div className="glass-card p-8 space-y-4">
        <div className="h-8 w-3/4 bg-surface-800 rounded" />
        <div className="h-4 w-1/2 bg-surface-800 rounded" />
      </div>
    </div>
  )

  if (!scenario) return (
    <div className="text-center py-16 animate-fade-in">
      <Target size={48} className="text-surface-700 mx-auto mb-3" />
      <p className="text-surface-400 text-lg mb-2">Scenario not found</p>
      <Link to="/scenarios" className="text-accent-cyan hover:underline text-sm mt-2 inline-block">Back to scenarios</Link>
    </div>
  )

  const TypeIcon = typeConfig[scenario.scenario_type]?.icon || Wrench
  const typeInfo = typeConfig[scenario.scenario_type] || typeConfig.fix
  const timeMinutes = Math.floor((scenario.time_limit || 900) / 60)
  // Learner avg from finalize_lab_completion_if_ready rolling average. Hide
  // until we have a few samples so a single outlier doesn't look authoritative.
  const avgSolveMinutes = scenario.avg_completion_time > 0
    && (scenario.completions_count || 0) >= 3
    ? Math.max(1, Math.round(scenario.avg_completion_time / 60))
    : null
  const userCompleted = scenario.user_progress?.completed
  const objectives = Array.isArray(scenario.objectives) ? scenario.objectives : []
  const solveRate = scenario.attempts_count > 0
    ? Math.round(scenario.completions_count / Math.max(scenario.attempts_count, 1) * 100)
    : null
  // Server-computed, and null below the sample floor (audit Z3-10). Averaging
  // client-side over `ratings` would be wrong twice over: it only holds the 10
  // most recent reviews *with text*, so it was never the scenario's average.
  const avgRating = ratingSummary?.has_enough_ratings ? ratingSummary.average_score : null

  const locked = scenario.is_accessible === false || scenario.subscription_required === true
  const simInfo = getScenarioSimInfo(scenario)

  // Locked paid labs keep marketing chrome (title / difficulty / tech) but the
  // Start action and incident brief are paywalled — see backend ScenarioDetailView.
  const startButton = locked ? (
    <Link
      to={`/pricing?technology=${scenario.technology?.slug || ''}`}
      className="btn-primary w-full sm:w-auto px-8 py-3.5 text-base flex items-center justify-center gap-2.5"
    >
      <Lock size={18} />
      Subscribe to start
    </Link>
  ) : (
    <button
      onClick={handleStartLab}
      disabled={starting || !!limitInfo}
      className="btn-primary w-full sm:w-auto px-8 py-3.5 text-base flex items-center justify-center gap-2.5 disabled:opacity-50"
    >
      {starting ? (
        <>
          <div className="w-5 h-5 border-2 border-surface-950 border-t-transparent rounded-full animate-spin" />
          {scenario.infrastructure_type && scenario.infrastructure_type !== 'docker'
            ? 'Launching cloud server...'
            : 'Provisioning lab...'}
        </>
      ) : activeLabSession ? (
        <>
          <Play size={18} />
          Resume Lab
        </>
      ) : (
        <>
          <Play size={18} />
          {userCompleted ? 'Launch Again' : 'Start Lab'}
        </>
      )}
    </button>
  )

  return (
    <div className="max-w-4xl mx-auto space-y-5 animate-fade-in pb-8">
      <SmallScreenLabGate
        open={labGate.gateOpen}
        onCancel={labGate.dismiss}
        onProceed={labGate.proceed}
      />
      <PageHeader
        eyebrow="Training"
        title={scenario.title}
        subtitle={scenario.subtitle || scenario.technology_name || scenario.category || typeInfo.desc}
      />

      <StickyPageToolbar>
        {/* Stay in-context: when the scenario belongs to a technology, the
            primary back link returns to that technology's page (its own
            scenario list). The global "All scenarios" list stays reachable as a
            secondary link so users can still browse/filter across technologies. */}
        {scenario.technology?.slug ? (
          <div className="flex items-center gap-3 flex-wrap">
            <Link
              to={`/technologies/${scenario.technology.slug}`}
              className="inline-flex items-center gap-1.5 text-sm text-surface-400 hover:text-white transition-colors"
            >
              <ArrowLeft size={14} /> {scenario.technology.name || 'Technology'}
            </Link>
            <Link to="/scenarios" className="text-xs text-surface-500 hover:text-accent-cyan transition-colors">
              All scenarios
            </Link>
          </div>
        ) : (
          <Link to="/scenarios" className="inline-flex items-center gap-1.5 text-sm text-surface-400 hover:text-white transition-colors">
            <ArrowLeft size={14} /> All Scenarios
          </Link>
        )}
        <div className="flex items-center gap-2 mt-1.5">
          <span className={`shrink-0 text-xs px-2 py-1 rounded border ${typeInfo.label === 'Fix' ? 'border-accent-cyan/30 text-accent-cyan' : 'border-surface-600 text-surface-400'}`}>
            {typeInfo.label}
          </span>
        </div>
      </StickyPageToolbar>

      {/* Issue / Jira bar — top only, no duplicate panel below */}
      <ScenarioIssueBar
        scenario={scenario}
        jiraTicket={jiraTicket}
        jiraComments={jiraComments}
        isAuthenticated={isAuthenticated}
      />

      <PageBreadcrumbs
        items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Scenarios', to: '/scenarios' },
          ...(scenario.technology?.slug
            ? [{ label: scenario.technology.name, to: `/technologies/${scenario.technology.slug}` }]
            : []),
          { label: scenario.title },
        ]}
      />

      {(scenario.lab_mode === 'simulation' || scenario.slug?.startsWith('sim-')) && (
        <JiraTeamGuide scenarioSlug={scenario.slug} />
      )}

      {/* Hero */}
      <div className="relative overflow-hidden glass-card gradient-border p-6 lg:p-8">
        <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/6 via-transparent to-accent-purple/6 pointer-events-none" />
        <div className="relative">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <span className={`badge-${scenario.difficulty}`}>{scenario.difficulty}</span>
          <span className={`px-2 py-0.5 rounded text-xs font-medium border flex items-center gap-1 ${
            scenario.scenario_type === 'hack' ? 'bg-accent-red/10 text-accent-red border-accent-red/20'
            : scenario.scenario_type === 'do' ? 'bg-accent-green/10 text-accent-green border-accent-green/20'
            : 'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/20'
          }`}>
            <TypeIcon size={11} /> {typeInfo.label}
          </span>
          {scenario.category && (
            <span className="bg-surface-700/50 px-2 py-0.5 rounded text-xs text-surface-400">{scenario.category}</span>
          )}
          {scenario.technology && (
            <span className="bg-accent-cyan/5 text-accent-cyan px-2 py-0.5 rounded text-xs border border-accent-cyan/10">
              {scenario.technology.name}
            </span>
          )}
          {scenario.is_free && (
            <span className="bg-accent-green/10 text-accent-green px-2 py-0.5 rounded text-xs border border-accent-green/20">Free</span>
          )}
          {simInfo && (
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs border font-medium"
              style={{ borderColor: `${simInfo.accent}55`, color: simInfo.accent, backgroundColor: `${simInfo.accent}14` }}
              title={`Starts the ${simInfo.label} console with optional lab terminal`}
            >
              <Monitor size={11} /> Opens {simInfo.short} console
            </span>
          )}
          {userCompleted && (
            <span className="flex items-center gap-1 text-accent-green bg-accent-green/10 border border-accent-green/20 rounded-lg px-2 py-0.5 text-xs font-semibold ml-auto">
              <CheckCircle2 size={13} /> Solved
            </span>
          )}
          <button type="button" onClick={handleBookmark} className="text-surface-500 hover:text-accent-amber transition-colors p-1 min-h-[44px] min-w-[44px] inline-flex items-center justify-center ml-auto sm:ml-0" aria-label={scenario.is_bookmarked ? 'Remove bookmark' : 'Bookmark scenario'}>
            {scenario.is_bookmarked
              ? <Bookmark size={18} className="text-accent-amber fill-accent-amber" />
              : <BookmarkPlus size={18} />}
          </button>
        </div>

        {scenario.subtitle && <p className="text-surface-400 text-sm mb-4">{scenario.subtitle}</p>}

        {/* Stats row — matches reference layout */}
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 py-3 border-y border-surface-800/80">
          <StatPill icon={Clock}>
            {avgSolveMinutes != null
              ? `Est. ${timeMinutes} min · learners avg ${avgSolveMinutes} min`
              : `${timeMinutes} min`}
          </StatPill>
          <StatPill icon={Target}>{scenario.max_score} pts max</StatPill>
          <StatPill icon={Lightbulb}>{scenario.hints_count || 0} hints</StatPill>
          {scenario.attempts_count > 0 && (
            <StatPill icon={Users}>{scenario.attempts_count} attempts</StatPill>
          )}
          {solveRate != null && (
            <StatPill icon={BarChart3}>{solveRate}% solve rate</StatPill>
          )}
          {avgRating && (
            <StatPill icon={Star}>{avgRating} avg rating</StatPill>
          )}
        </div>

        {/* Community solve stats — avg time / learners / fail rate (hides if none) */}
        <ScenarioStatsChip slug={scenario.slug} className="mt-3" />

        {scenario.tags?.length > 0 && (
          <div className="flex gap-2 mt-4 flex-wrap">
            {scenario.tags.map(tag => (
              <Link key={tag.slug} to={`/scenarios?tag=${tag.slug}`}
                className="text-xs text-surface-500 hover:text-surface-300 bg-surface-800 hover:bg-surface-700 px-2 py-0.5 rounded flex items-center gap-1 transition-colors"
              >
                <Hash size={10} /> {tag.name}
              </Link>
            ))}
          </div>
        )}

        <div className="mt-5 flex flex-col sm:flex-row gap-3 sm:items-center">
          {startButton}
          {activeLabSession && (
            <p className="text-xs text-accent-cyan">Active lab running — resume to continue where you left off.</p>
          )}
        </div>
        </div>
      </div>

      {/* Daily-limit popup window */}
      <LimitReachedModal info={limitInfo} onClose={() => setLimitInfo(null)} />

      {/* Banners */}
      {scenario.is_accessible === false && (
        <div className="glass-card p-5 border-accent-purple/20 bg-accent-purple/5">
          <div className="flex items-start gap-3">
            <Lock size={18} className="text-accent-purple mt-0.5" />
            <div>
              <h3 className="text-base font-semibold text-white mb-1">Subscription Required</h3>
              <p className="text-sm text-surface-400 mb-3">
                Subscribe to <span className="text-white font-medium">{scenario.technology?.name}</span> to start this lab and open the incident ticket.
              </p>
              <Link to="/pricing" className="btn-primary text-sm px-4 py-2 inline-flex items-center gap-1.5">
                <Zap size={14} /> View Pricing
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Description */}
      {simInfo && (
        <div className="glass-card p-5 border-l-4" style={{ borderLeftColor: simInfo.accent }}>
          <h2 className="text-sm font-semibold text-white mb-1 flex items-center gap-2">
            <Monitor size={16} style={{ color: simInfo.accent }} />
            Lab console
          </h2>
          <p className="text-sm text-surface-400 leading-relaxed">
            This challenge opens the <strong className="text-surface-200">{simInfo.label}</strong> inside the lab.
            Use the <strong className="text-surface-200">Terminal</strong> button in the console toolbar to run shell commands
            (e.g. <code className="text-accent-cyan">terraform apply</code>, edit configs under <code className="text-accent-cyan">/etc</code>).
            Terraform labs default to the VS Code IDE with HCL editor and integrated terminal.
          </p>
        </div>
      )}

      {locked ? (
        <div className="relative overflow-hidden glass-card p-6 border-accent-purple/20">
          <div className="select-none pointer-events-none blur-sm opacity-40 space-y-4" aria-hidden>
            <h2 className="text-base font-semibold text-white">Incident briefing</h2>
            <div className="space-y-3">
              <div className="h-3 bg-surface-700 rounded w-full" />
              <div className="h-3 bg-surface-700 rounded w-11/12" />
              <div className="h-3 bg-surface-700 rounded w-4/5" />
              <div className="h-3 bg-surface-700 rounded w-10/12" />
            </div>
            <h2 className="text-base font-semibold text-white pt-2">Expected outcome</h2>
            <div className="space-y-2">
              <div className="h-3 bg-surface-700 rounded w-3/4" />
              <div className="h-3 bg-surface-700 rounded w-2/3" />
            </div>
          </div>
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-surface-950/55 backdrop-blur-[1px] p-6 text-center">
            <Lock size={22} className="text-accent-purple" />
            <div>
              <p className="text-base font-semibold text-white mb-1">Full incident brief locked</p>
              <p className="text-sm text-surface-400 max-w-md mx-auto">
                Subscribe to{' '}
                <span className="text-white font-medium">{scenario.technology?.name || 'this technology'}</span>
                {' '}to unlock the narrative, objectives, and lab briefing.
              </p>
            </div>
            <Link
              to={`/pricing?technology=${scenario.technology?.slug || ''}`}
              className="btn-primary text-sm px-4 py-2 inline-flex items-center gap-1.5"
            >
              <Zap size={14} /> Subscribe to unlock
            </Link>
          </div>
        </div>
      ) : (
        <>
          <ScenarioNarrative scenario={scenario} />

          {objectives.length > 0 && (
            <div className="glass-card p-6">
              <h2 className="text-base font-semibold text-white mb-3">Expected outcome</h2>
              <ul className="space-y-2">
                {objectives.map((obj, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-surface-300">
                    <CheckCircle2 size={14} className="text-accent-cyan mt-0.5 shrink-0" />
                    <span>{typeof obj === 'string' ? obj : JSON.stringify(obj)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      {scenario.linked_tutorial && (
        <div className="glass-card p-5 border-accent-cyan/20 bg-accent-cyan/5">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-white mb-1 flex items-center gap-2">
                <BookOpen size={16} className="text-accent-cyan" /> Continue the course
              </h2>
              <p className="text-sm text-surface-400">
                This lab is part of{' '}
                <span className="text-surface-200 font-medium">
                  {scenario.related_tutorials?.[0]?.course_title
                    || scenario.linked_tutorial}
                </span>
                . Work through the modules for the full learning path.
              </p>
            </div>
            <Link
              to={`/tutorials?course=${encodeURIComponent(scenario.linked_tutorial)}`}
              className="btn-secondary text-sm px-4 py-2 inline-flex items-center gap-1.5 shrink-0"
            >
              Open course
            </Link>
          </div>
        </div>
      )}

      {scenario.related_tutorials?.length > 0 && (
        <div className="glass-card p-6 border-accent-purple/15">
          <h2 className="text-base font-semibold text-white mb-3 flex items-center gap-2">
            <BookOpen size={16} className="text-accent-purple" /> Related tutorials
          </h2>
          <p className="text-xs text-surface-500 mb-4">Study these lessons before or after this lab.</p>
          <div className="space-y-2">
            {scenario.related_tutorials.map((t) => (
              <Link
                key={t.slug}
                to={`/tutorials/${t.slug}`}
                className="flex items-center justify-between p-3 rounded-lg bg-surface-800/40 border border-surface-700/40 hover:border-accent-purple/30 transition-colors group"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-white group-hover:text-accent-purple truncate">{t.title}</p>
                  <p className="text-xs text-surface-500">
                    {t.topic} · {t.estimated_minutes || '?'} min · {t.section_count || 0} sections
                  </p>
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded border capitalize shrink-0 ml-2 ${
                  t.difficulty === 'advanced' ? 'border-accent-red/30 text-accent-red'
                    : t.difficulty === 'intermediate' ? 'border-accent-amber/30 text-accent-amber'
                      : 'border-accent-green/30 text-accent-green'
                }`}>
                  {t.difficulty || 'beginner'}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Initial state */}
      {scenario.initial_state && (
        <div className="glass-card p-6">
          <h2 className="text-base font-semibold text-white mb-3">Initial State</h2>
          <div className="bg-surface-950 rounded-lg p-4 font-mono text-sm text-surface-300 leading-relaxed whitespace-pre-wrap border border-surface-800">
            {scenario.initial_state}
          </div>
        </div>
      )}

      {/* Your progress */}
      {scenario.user_progress && (
        <div className="glass-card p-6">
          <h2 className="text-base font-semibold text-white mb-4">Your Progress</h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-surface-800/50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-white">{scenario.user_progress.attempts}</p>
              <p className="text-xs text-surface-400 mt-0.5">Attempts</p>
            </div>
            <div className="bg-surface-800/50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-accent-amber">{scenario.user_progress.best_score || 0}</p>
              <p className="text-xs text-surface-400 mt-0.5">Best Score</p>
            </div>
            <div className="bg-surface-800/50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-white">
                {scenario.user_progress.best_time
                  ? `${Math.floor(scenario.user_progress.best_time / 60)}m ${scenario.user_progress.best_time % 60}s`
                  : '—'}
              </p>
              <p className="text-xs text-surface-400 mt-0.5">Best Time</p>
            </div>
            <div className="bg-surface-800/50 rounded-lg p-3 text-center">
              <p className={`text-2xl font-bold ${userCompleted ? 'text-accent-green' : 'text-surface-500'}`}>
                {userCompleted ? 'Yes' : 'No'}
              </p>
              <p className="text-xs text-surface-400 mt-0.5">Completed</p>
            </div>
          </div>
        </div>
      )}

      {/* Solution */}
      {userCompleted && scenario.solution_explanation && (
        <div className="glass-card p-6 border border-accent-green/10">
          <button
            onClick={() => setShowSolution(!showSolution)}
            className="flex items-center gap-2 text-base font-semibold text-accent-green w-full"
          >
            <Eye size={16} />
            {showSolution ? 'Hide Solution' : 'View Solution Explanation'}
          </button>
          {showSolution && (
            <div className="mt-4 pt-4 border-t border-surface-800">
              <p className="text-sm text-surface-300 leading-relaxed whitespace-pre-wrap">{scenario.solution_explanation}</p>
            </div>
          )}
        </div>
      )}

      {/* Ratings */}
      <div className="glass-card p-6">
        <h2 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <Star size={16} className="text-accent-amber" /> Ratings & Reviews
          {ratingSummary?.total_ratings > 0 && (
            <span className="text-xs text-surface-500 ml-auto flex items-center gap-2">
              {avgRating !== null && (
                <span className="text-accent-amber font-semibold">{avgRating} ★</span>
              )}
              <span>
                {ratingSummary.total_ratings} rating{ratingSummary.total_ratings !== 1 ? 's' : ''}
              </span>
            </span>
          )}
        </h2>

        {isAuthenticated && (
          <div className="bg-surface-800/50 rounded-lg p-4 mb-4">
            <p className="text-sm text-surface-300 mb-2">Rate this scenario</p>
            <div className="flex items-center gap-1 mb-3">
              {[1, 2, 3, 4, 5].map(star => (
                <button
                  key={star}
                  onMouseEnter={() => setHoverRating(star)}
                  onMouseLeave={() => setHoverRating(0)}
                  onClick={() => setUserRating(star)}
                  className="p-0.5 transition-transform hover:scale-110"
                >
                  <Star size={24} className={star <= (hoverRating || userRating) ? 'text-accent-amber fill-accent-amber' : 'text-surface-600'} />
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={reviewText}
                onChange={(e) => setReviewText(e.target.value)}
                placeholder="Write a short review (optional)..."
                className="input-field flex-1 text-sm"
              />
              <button
                onClick={handleSubmitRating}
                disabled={!userRating || submittingRating}
                className="btn-primary px-4 py-2 text-sm flex items-center gap-1.5 disabled:opacity-50"
              >
                <Send size={14} /> {submittingRating ? 'Sending...' : 'Submit'}
              </button>
            </div>
          </div>
        )}

        {ratings.length === 0 ? (
          <p className="text-sm text-surface-500 text-center py-3">
            {ratingSummary?.total_ratings > 0
              ? 'No written reviews yet.'
              : 'No reviews yet. Be the first to rate!'}
          </p>
        ) : (
          <div className="space-y-3 max-h-72 overflow-y-auto">
            {ratings.slice(0, 10).map((r, i) => (
              <div key={i} className="flex items-start gap-3 py-2 border-b border-surface-800/50 last:border-0">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-accent-cyan to-brand-600 flex items-center justify-center text-xs font-bold text-white shrink-0">
                  {r.user?.username?.[0]?.toUpperCase() || 'U'}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-surface-200">{r.user?.username || 'Anonymous'}</span>
                    <div className="flex items-center gap-0.5">
                      {[1, 2, 3, 4, 5].map(s => (
                        <Star key={s} size={12} className={s <= r.score ? 'text-accent-amber fill-accent-amber' : 'text-surface-700'} />
                      ))}
                    </div>
                  </div>
                  {r.review && <p className="text-sm text-surface-400 mt-0.5">{r.review}</p>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Bottom CTA */}
      <div className="flex flex-col items-center gap-2 pt-2">
        {startButton}
        {userCompleted && (
          <p className="text-xs text-surface-500 text-center">
            Each launch creates a fresh environment. Your solved badge resets until you pass validation again.
          </p>
        )}
      </div>
    </div>
  )
}
