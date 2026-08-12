import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { labApi } from '../api/labs'
import { scenarioApi } from '../api/scenarios'
import api from '../api/client'
import { subscriptionApi } from '../api/subscriptions'
import { jiraApi } from '../api/jira'
import { journeyApi } from '../api/journeys'
import { useAuthStore } from '../store/authStore'
import {
  Target, Trophy, Zap, Clock, TrendingUp, ArrowRight,
  CheckCircle2, Award, BookOpen, Play, Star,
  Calendar, CreditCard, Crown, Layers, ArrowUpRight, XCircle, AlertTriangle, Sparkles, Download, Ticket,
  Bookmark, Bell, History, BarChart3, X, Mic2, ListChecks, Route,
} from 'lucide-react'
import JiraTicketLink from '../components/JiraTicketLink'
import { SkeletonStats, SkeletonCard } from '../components/Skeleton'
import { ACHIEVEMENT_META } from '../utils/constants'
import ActivityHeatmap from '../components/ActivityHeatmap'
import OnboardingTour from '../components/OnboardingTour'
import { FixitPanel, FixitStatCard } from '../components/design'
import { DailyChallengeCard, StreakWidget, XpLevelCard } from '../components/engagement'
import CertDashboardPanel from '../components/certifications/CertDashboardPanel'
import { tutorialApi } from '../api/tutorials'
import { listLocalContinue, progressPct } from '../utils/tutorialProgress'
import MfaRecommendationBanner from '../components/MfaRecommendationBanner'

function OnboardingChecklist({ subscriptions, progress, jiraTickets, interviewEntitlement }) {
  const [dismissed, setDismissed] = useState(
    () => localStorage.getItem('onboarding_dismissed') === '1'
  )

  const hasSubscription = subscriptions?.length > 0
  const hasCompletedScenario = (progress?.summary?.completed || 0) > 0
  const hasInterview =
    (interviewEntitlement?.interviews_used || 0) > 0 ||
    interviewEntitlement?.sample_interview_used === true
  const jiraConnected = (jiraTickets?.length || 0) > 0

  // Only show to new users who haven't dismissed and have no activity
  const isNewUser = !hasSubscription && !hasCompletedScenario && !hasInterview && !jiraConnected
  const shouldShow = (isNewUser || (!dismissed)) && !dismissed

  if (!shouldShow) return null

  const steps = [
    {
      label: 'Pick a technology',
      desc: 'Subscribe to a technology track to unlock labs',
      to: '/technologies',
      done: hasSubscription,
    },
    {
      label: 'Try a free scenario',
      desc: 'Run your first hands-on lab challenge',
      to: '/scenarios',
      done: hasCompletedScenario,
    },
    {
      label: 'Start an interview',
      desc: 'Practice with AI interview questions',
      to: '/interviews',
      done: hasInterview,
    },
    {
      label: 'Connect Jira',
      desc: 'Link Jira to track incidents as tickets',
      to: '/profile',
      done: jiraConnected,
    },
  ]

  const completedCount = steps.filter(s => s.done).length

  const handleDismiss = () => {
    localStorage.setItem('onboarding_dismissed', '1')
    setDismissed(true)
  }

  return (
    <FixitPanel padding="p-6" className="border border-accent-blue/22 bg-gradient-to-br from-accent-blue/[0.06] via-transparent to-accent-purple/[0.04] relative overflow-hidden animate-fx-rise">
      <div className="flex items-start justify-between relative mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-[11px] bg-accent-blue/15 flex items-center justify-center border border-accent-blue/22">
            <ListChecks size={20} className="text-accent-blue" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">Getting Started</h2>
            <p className="text-xs text-surface-400">{completedCount}/{steps.length} steps complete</p>
          </div>
        </div>
        <button
          type="button"
          onClick={handleDismiss}
          className="p-1.5 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-lg text-surface-500 hover:text-surface-300 hover:bg-surface-800/60 transition-all"
          aria-label="Dismiss checklist"
        >
          <X size={16} />
        </button>
      </div>

      <div className="h-1.5 bg-white/[0.08] rounded-full overflow-hidden mb-5 relative">
        <div
          className="h-full bg-gradient-to-r from-accent-blue to-accent-purple rounded-full transition-all duration-700"
          style={{ width: `${(completedCount / steps.length) * 100}%` }}
        />
      </div>

      <div className="grid sm:grid-cols-2 gap-3 relative">
        {steps.map((step, idx) => (
          <Link
            key={idx}
            to={step.to}
            className={`flex items-start gap-3 p-3.5 rounded-xl border transition-all group ${
              step.done
                ? 'bg-accent-green/5 border-accent-green/20 opacity-75'
                : 'bg-surface-800/40 border-surface-700/40 hover:border-accent-cyan/30 hover:bg-surface-800/70'
            }`}
          >
            <div className={`mt-0.5 shrink-0 w-5 h-5 rounded-full flex items-center justify-center border ${
              step.done
                ? 'bg-accent-green/20 border-accent-green/40 text-accent-green'
                : 'border-surface-600 text-surface-600 group-hover:border-accent-cyan/50 group-hover:text-accent-cyan/50'
            }`}>
              {step.done
                ? <CheckCircle2 size={14} />
                : <span className="text-[10px] font-bold">{idx + 1}</span>
              }
            </div>
            <div className="min-w-0">
              <p className={`text-sm font-semibold ${step.done ? 'text-accent-green line-through decoration-accent-green/40' : 'text-white'}`}>
                {step.label}
              </p>
              <p className="text-xs text-surface-500 mt-0.5">{step.desc}</p>
            </div>
            {!step.done && (
              <ArrowRight size={14} className="text-surface-600 group-hover:text-accent-cyan shrink-0 mt-1 ml-auto transition-colors" />
            )}
          </Link>
        ))}
      </div>
    </FixitPanel>
  )
}

export default function Dashboard() {
  const { user, isAuthenticated } = useAuthStore()
  const [progress, setProgress] = useState(null)
  const [achievements, setAchievements] = useState([])
  const [activeLabs, setActiveLabs] = useState([])
  const [subscriptions, setSubscriptions] = useState([])
  const [complimentaryAccess, setComplimentaryAccess] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  // Which specific fetches failed. A blanket flag is not enough: "your labs
  // failed to load" and "you have no labs" need different copy in different
  // places on this page, and collapsing them is what caused the bug below.
  const [failed, setFailed] = useState({})
  const [cancelModal, setCancelModal] = useState(null)
  const [cancelling, setCancelling] = useState(false)
  const [jiraTickets, setJiraTickets] = useState([])
  const [bookmarks, setBookmarks] = useState([])
  const [unreadNotifications, setUnreadNotifications] = useState(0)
  const [interviewEntitlement, setInterviewEntitlement] = useState(null)
  const [tutorialContinue, setTutorialContinue] = useState([])
  const [interviewAnalytics, setInterviewAnalytics] = useState(null)
  const [journeyNext, setJourneyNext] = useState(null)

  useEffect(() => {
    // allSettled + a per-call failure map, not Promise.all with `.catch(() => [])`.
    // The old form resolved all ten calls to empty defaults that are byte-identical
    // to a brand-new account, so a backend blip rendered a plausible-looking empty
    // dashboard. The two dangerous cases: a RUNNING lab disappearing (the user
    // starts a duplicate) and a subscription fetch degrading to "no subscription"
    // (a paying user looks free). Only getProgress ever set loadError before.
    let active = true
    const notifController = new AbortController()
    // One dynamic import shared by both interview calls. Kept lazy (the studio
    // is a heavy chunk) but resolved once, so the two consumers below can't
    // race two separate module evaluations.
    const interviewsMod = import('../api/interviews')
    Promise.allSettled([
      labApi.getProgress(),
      labApi.getAchievements(),
      labApi.getActiveLabs(),
      subscriptionApi.getMySubscriptions(),
      jiraApi.getUserTickets(),
      scenarioApi.getBookmarks(),
      api.get('/notifications/', { silentError: true, signal: notifController.signal }),
      interviewsMod.then(m => m.interviewsApi.getEntitlement()),
      tutorialApi.list(),
      isAuthenticated ? tutorialApi.getContinue() : Promise.resolve([]),
      // Competency radar — the only per-skill signal the platform actually
      // computes (interview reports). Used to name a weakest area to work on.
      isAuthenticated
        ? interviewsMod.then(m => m.interviewsApi.getMyAnalytics())
        : Promise.resolve(null),
      // Next journey step — the third thing audit L2317 wants surfaced, after
      // the active lab and the weakest competency.
      isAuthenticated ? journeyApi.getNext() : Promise.resolve(null),
    ]).then(([progRes, achRes, labsRes, subsRes, jiraSettled, bmsRes, notifSettled, entRes, tutListSettled, tutContinueRes, analyticsRes, journeyRes]) => {
      if (!active) return
      const val = (r) => (r.status === 'fulfilled' ? r.value : null)
      const prog = val(progRes)
      const labs = val(labsRes)
      const subs = val(subsRes)
      const jiraRes = val(jiraSettled)
      const bms = val(bmsRes)
      const notifRes = val(notifSettled)
      const interviewEnt = val(entRes)
      const tutListRes = val(tutListSettled)
      const tutContinue = val(tutContinueRes)

      setFailed({
        progress: progRes.status === 'rejected',
        achievements: achRes.status === 'rejected',
        activeLabs: labsRes.status === 'rejected',
        subscriptions: subsRes.status === 'rejected',
        jira: jiraSettled.status === 'rejected',
        bookmarks: bmsRes.status === 'rejected',
        // Notifications are fetched with silentError: true — a failure here is
        // deliberately non-disruptive, so it feeds the badge but not the banner.
        notifications: notifSettled.status === 'rejected',
        interviewEntitlement: entRes.status === 'rejected',
        tutorials: tutListSettled.status === 'rejected' && tutContinueRes.status === 'rejected',
        // Same trap as subscriptions: a rejected fetch and "you haven't started
        // a journey" both arrive as no card. Flagged so the card can say which.
        journey: journeyRes.status === 'rejected',
      })
      setLoadError(progRes.status === 'rejected')
      setProgress(prog)
      setAchievements(val(achRes) || [])
      setActiveLabs(Array.isArray(labs) ? labs.filter(l => l.status === 'RUNNING') : [])
      setSubscriptions(subs?.subscriptions || [])
      setComplimentaryAccess(subs?.complimentary_access || false)
      setJiraTickets(jiraRes?.data?.tickets || jiraRes?.tickets || [])
      setBookmarks(Array.isArray(bms) ? bms : [])
      const notifs = notifRes?.data?.notifications || notifRes?.data?.results || []
      setUnreadNotifications(Array.isArray(notifs) ? notifs.filter(n => !(n.read ?? n.is_read)).length : 0)
      setInterviewEntitlement(interviewEnt)
      setInterviewAnalytics(val(analyticsRes))
      setJourneyNext(val(journeyRes))
      const tutorialsBySlug = Object.fromEntries(
        (tutListRes?.tutorials || []).map((t) => [t.slug, t]),
      )
      let continueItems = []
      if (isAuthenticated && Array.isArray(tutContinue) && tutContinue.length) {
        continueItems = tutContinue
      } else {
        continueItems = listLocalContinue().map((p) => {
          const meta = tutorialsBySlug[p.tutorial_slug] || {}
          const sectionCount = meta.section_count || p.completed_sections?.length || 0
          return {
            ...p,
            tutorial_title: meta.title || p.tutorial_slug,
            topic: meta.topic,
            section_count: sectionCount,
            progress_pct: p.progress_pct || progressPct(p.completed_sections, sectionCount),
          }
        })
      }
      setTutorialContinue(
        continueItems.filter((i) => !i.completed && (i.progress_pct ?? 0) < 100).slice(0, 4),
      )
    }).finally(() => { if (active) setLoading(false) })
    return () => {
      active = false
      notifController.abort()
    }
  }, [isAuthenticated])

  const handleCancelSubscription = async (sub) => {
    setCancelling(true)
    try {
      await subscriptionApi.cancelSubscription(sub.subscription_id)
      // Still active — access runs to the end of the paid term (audit Z1-11).
      // Marking it inactive here would grey out a subscription the customer can
      // still use, which is the same lie the old backend told.
      setSubscriptions(prev => prev.map(s => s.id === sub.id ? { ...s, cancelled: true } : s))
      setCancelModal(null)
    } catch (err) {
      alert(err?.response?.data?.error || 'Failed to cancel subscription. Please try again.')
    } finally {
      setCancelling(false)
    }
  }

  if (loading) return (
    <div className="max-w-7xl mx-auto space-y-8">
      <SkeletonStats count={4} />
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2"><SkeletonCard lines={6} /></div>
        <div className="space-y-6"><SkeletonCard lines={3} /><SkeletonCard lines={4} /></div>
      </div>
    </div>
  )

  const stats = progress?.summary || {}
  const techProgress = progress?.technology_progress || {}
  const subscribedTechNames = complimentaryAccess
    ? null
    : new Set(
        subscriptions
          .filter(s => s.is_active)
          .map(s => s.technology?.name)
          .filter(Boolean)
      )
  const displayedTechProgress = subscribedTechNames
    ? Object.fromEntries(Object.entries(techProgress).filter(([name]) => subscribedTechNames.has(name)))
    : techProgress
  const diffProgress = progress?.difficulty_progress || {}
  const recent = progress?.recent_activity || []
  const recommended = progress?.recommended_scenarios || []
  const earnedAch = achievements.filter?.(a => a.earned) || []

  const statCards = [
    { label: 'Completed', value: stats.completed || 0, icon: CheckCircle2, color: 'text-accent-green', bg: 'bg-accent-green/10', glow: 'shadow-accent-green/20' },
    { label: 'Total Attempts', value: stats.total_attempts || 0, icon: Target, color: 'text-accent-cyan', bg: 'bg-accent-cyan/10', glow: 'shadow-accent-cyan/20' },
    { label: 'Avg Score', value: stats.average_score || 0, icon: Trophy, color: 'text-accent-amber', bg: 'bg-accent-amber/10', glow: 'shadow-accent-amber/20' },
    { label: 'Completion', value: `${stats.completion_rate || 0}%`, icon: TrendingUp, color: 'text-accent-purple', bg: 'bg-accent-purple/10', glow: 'shadow-accent-purple/20' },
  ]

  const difficultyColors = {
    easy: { bar: 'from-accent-green to-emerald-400', text: 'text-accent-green' },
    medium: { bar: 'from-accent-amber to-yellow-400', text: 'text-accent-amber' },
    hard: { bar: 'from-accent-red to-rose-400', text: 'text-accent-red' },
  }

  // Only surface the scary banner for loads that blank primary dashboard cards.
  // Flaky interview/journey/tutorial endpoints used to force a full-page reload
  // prompt even when progress + labs rendered fine.
  const partialFailure = Object.entries(failed)
    .some(([key, didFail]) => didFail && [
      'achievements', 'activeLabs', 'subscriptions', 'jira', 'bookmarks',
    ].includes(key))

  // Weakest competency, from the interview radar — the only real per-skill score
  // the platform computes. Requires at least one graded attempt, otherwise every
  // dimension is 0 and "weakest" would be an arbitrary pick off an empty radar.
  const weakestCompetency = (interviewAnalytics?.attempts || 0) > 0
    ? (interviewAnalytics?.radar || [])
        .filter(d => typeof d.score === 'number')
        .reduce((min, d) => (min === null || d.score < min.score ? d : min), null)
    : null

  // Journey resume point. Both halves must be present: the backend returns
  // nulls for a user who hasn't started one, and there is nothing to show
  // without a concrete next step.
  const journeyStep = journeyNext?.journey && journeyNext?.next_step ? journeyNext : null
  const journeyPct = journeyStep?.journey.total_steps
    ? Math.round((journeyStep.journey.completed_steps / journeyStep.journey.total_steps) * 100)
    : 0

  return (
    <div className="flex flex-col gap-[22px] w-full relative">
      <OnboardingTour />

      {/* Audit Z2-3: suggested, never required. On the dashboard rather than as a
          login interstitial — interrupting a sign-in to sell a security feature is
          how prompts get dismissed reflexively. */}
      <MfaRecommendationBanner />

      {loadError && (
        <div className="text-center py-8" data-testid="dashboard-load-error">
          <p className="text-red-400 mb-3">Failed to load dashboard data.</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            Reload
          </button>
        </div>
      )}

      {!loadError && partialFailure && (
        <div
          data-testid="dashboard-partial-error"
          className="glass-card p-4 border-accent-red/30 bg-accent-red/[0.04] flex items-start gap-3"
        >
          <AlertTriangle size={18} className="text-accent-red shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm text-surface-200">Some of your dashboard couldn&apos;t be loaded</p>
            <p className="text-xs text-surface-500 mt-0.5">
              Anything missing below is a loading problem, not lost work. Reload to try again.
            </p>
          </div>
          <button onClick={() => window.location.reload()} className="btn-secondary text-xs px-3 py-1.5 shrink-0">
            Reload
          </button>
        </div>
      )}

      {/* The checklist infers "new user" from empty subscriptions/progress/tickets.
          If any of those fetches failed, that inference is wrong — it would tell a
          paying customer to go pick a technology they already bought. */}
      {!failed.subscriptions && !failed.progress && !failed.jira && !failed.interviewEntitlement && (
        <OnboardingChecklist
          subscriptions={subscriptions.filter(s => s.is_active)}
          progress={progress}
          jiraTickets={jiraTickets}
          interviewEntitlement={interviewEntitlement}
        />
      )}

      {/* ═══ HERO HEADER ═══ */}
      <div className="fx-hero-panel p-6 sm:p-8 animate-fx-rise">
        <div className="absolute -top-16 -left-16 w-60 h-60 rounded-full bg-accent-blue/16 blur-[40px] pointer-events-none" aria-hidden="true" />
        <div className="absolute -bottom-12 -right-12 w-52 h-52 rounded-full bg-accent-purple/16 blur-[40px] pointer-events-none" aria-hidden="true" />

        <div className="relative">
          {/* Top row */}
          <div className="flex items-start justify-between flex-wrap gap-4 mb-5">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <div className="w-[7px] h-[7px] rounded-full bg-accent-green shadow-[0_0_10px] shadow-accent-green animate-pulse" />
                <span className="text-[11px] font-bold text-accent-green uppercase tracking-[0.16em]">Your dashboard</span>
              </div>
              <h1 className="font-display text-2xl sm:text-[30px] font-extrabold text-white tracking-tight leading-tight">
                Welcome back,{' '}
                <span className="text-gradient-brand">
                  {user?.first_name || user?.username}
                </span>
              </h1>
              <p className="text-surface-400 text-sm mt-1.5">Track your progress, manage labs, and keep levelling up.</p>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              {activeLabs.length > 0 && (
                <Link to={`/lab/${activeLabs[0].id}`} className="btn-primary flex items-center gap-2 shadow-lg shadow-accent-cyan/25 animate-pulse-glow text-sm">
                  <Play size={15} /> Resume Lab
                </Link>
              )}
              <Link to="/subscriptions" className="btn-secondary flex items-center gap-2 text-sm"><CreditCard size={14} /> Subscriptions</Link>
            </div>
          </div>

          {/* Stats strip */}
          <div className="flex flex-wrap items-center gap-2.5 pt-4 border-t border-white/[0.08]">
            {[
              { label: 'Completed', value: stats.completed || 0, color: 'text-accent-green' },
              { label: 'Avg Score', value: stats.average_score || 0, color: 'text-accent-amber' },
              { label: 'Active Subs', value: subscriptions.filter(s => s.is_active).length, color: 'text-accent-blue' },
              { label: 'Achievements', value: earnedAch.length, color: 'text-accent-purple' },
            ].map(({ label, value, color }) => (
              <div key={label} className="flex items-center gap-2 px-3 py-1.5 rounded-[10px] bg-white/[0.04] border border-white/[0.08]">
                <span className={`text-sm font-bold tabular-nums ${color}`}>{value}</span>
                <span className="text-xs text-surface-500">{label}</span>
              </div>
            ))}
            {user?.date_joined && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-800/50 border border-surface-700/30 ml-auto">
                <Calendar size={11} className="text-surface-500" />
                <span className="text-xs text-surface-500">Since {new Date(user.date_joined).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* "What should I work on?" — the dashboard previously answered this only
          with raw counts. The radar is per-dimension, so name the lowest one and
          link straight into practice rather than making the user infer it. */}
      {weakestCompetency && (
        <FixitPanel padding="p-4" className="border border-accent-purple/25 bg-accent-purple/[0.05]">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-accent-purple/15 flex items-center justify-center shrink-0">
                <BarChart3 size={18} className="text-accent-purple" />
              </div>
              <div>
                <p className="text-sm font-semibold text-white">
                  Weakest area: {weakestCompetency.dimension}
                </p>
                <p className="text-xs text-surface-400 mt-0.5">
                  Averaging {weakestCompetency.score}/100 across {interviewAnalytics.attempts} graded
                  {interviewAnalytics.attempts === 1 ? ' attempt' : ' attempts'}.
                </p>
              </div>
            </div>
            <Link to="/interviews" className="btn-secondary text-xs px-3 py-1.5 shrink-0">
              Practice this
            </Link>
          </div>
        </FixitPanel>
      )}

      {/* "Continue your journey" — audit L2317. A journey is a multi-week track,
          so the useful thing is not the track name but the one step to open
          next; the backend resolves that down to a single piece of content. */}
      {failed.journey ? (
        <div
          data-testid="dashboard-journey-error"
          className="fx-panel p-4 border-accent-red/30 bg-accent-red/[0.05]"
        >
          <h3 className="text-sm font-semibold text-accent-red mb-1.5 flex items-center gap-2">
            <AlertTriangle size={14} /> Couldn&apos;t load your learning journey
          </h3>
          <p className="text-xs text-surface-400">
            This is a loading problem — your progress is intact. Reload to try again.
          </p>
        </div>
      ) : journeyStep && (
        /* Plain div, not FixitPanel: that component only forwards children,
           className and padding, so a data-testid on it would be dropped. */
        <div
          data-testid="dashboard-journey-card"
          className="fx-panel p-4 border border-accent-cyan/25 bg-accent-cyan/[0.05]"
        >
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-10 h-10 rounded-xl bg-accent-cyan/15 flex items-center justify-center shrink-0">
                <Route size={18} className="text-accent-cyan" />
              </div>
              <div className="min-w-0">
                <p className="text-[11px] font-bold text-accent-cyan uppercase tracking-[0.14em]">
                  Continue your journey
                </p>
                <p className="text-sm font-semibold text-white truncate">
                  {journeyStep.next_step.target_title}
                </p>
                <p className="text-xs text-surface-400 mt-0.5">
                  {journeyStep.journey.title} · step {journeyStep.journey.completed_steps + 1} of{' '}
                  {journeyStep.journey.total_steps}
                  {journeyStep.next_step.items_total > 1 && (
                    <> · {journeyStep.next_step.items_completed}/{journeyStep.next_step.items_total} done</>
                  )}
                </p>
              </div>
            </div>
            {journeyStep.next_step.link ? (
              <Link to={journeyStep.next_step.link} className="btn-secondary text-xs px-3 py-1.5 shrink-0">
                Resume
              </Link>
            ) : (
              <span className="text-xs text-surface-500 shrink-0">Up next</span>
            )}
          </div>
          <div className="h-1.5 bg-white/[0.08] rounded-full overflow-hidden mt-3.5">
            <div
              className="h-full bg-gradient-to-r from-accent-cyan to-accent-blue rounded-full transition-all duration-700"
              style={{ width: `${journeyPct}%` }}
            />
          </div>
        </div>
      )}

      {interviewEntitlement?.platform_enabled !== false && (
        <Link
          to="/interviews"
          className="relative block"
        >
          <FixitPanel padding="p-5" className="border border-indigo-500/25 bg-gradient-to-r from-indigo-500/10 to-purple-500/5 hover:border-indigo-500/40 transition-colors animate-slide-up">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center">
                <Mic2 size={20} className="text-indigo-400" />
              </div>
              <div>
                <p className="text-sm font-semibold text-white">AI Interview Studio</p>
                <p className="text-xs text-surface-400">
                  {interviewEntitlement?.sample_available
                    ? `Free ${interviewEntitlement?.sample_duration_minutes || 10}-min sample available`
                    : `${interviewEntitlement?.plan?.name || 'Free'} · ${interviewEntitlement?.interviews_remaining ?? '—'} attempt(s) left`}
                  {interviewEntitlement?.days_remaining != null && interviewEntitlement.days_remaining <= 30 && (
                    <span className="text-amber-400"> · {interviewEntitlement.days_remaining}d left</span>
                  )}
                </p>
              </div>
            </div>
            <span className="text-xs text-indigo-300 flex items-center gap-1">
              Open <ArrowRight size={14} />
            </span>
          </div>
          </FixitPanel>
        </Link>
      )}

      {/* Today's Challenge — deterministic daily pick (hides gracefully on error) */}
      <DailyChallengeCard />

      {/* ═══ STAT CARDS ═══ */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map(({ label, value, icon, color, bg }, idx) => (
          <div key={label} className="animate-fx-rise" style={{ animationDelay: `${idx * 80}ms` }}>
            <FixitStatCard
              icon={icon}
              value={value}
              label={label}
              iconBg={bg}
              iconColor={color}
            />
          </div>
        ))}
      </div>

      {/* Quick actions + continue learning */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Link to="/bookmarks" className="block group">
          <FixitPanel padding="p-4" className="hover:border-accent-cyan/30 transition-all h-full">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-medium text-white"><Bookmark size={16} className="text-accent-cyan" /> Bookmarks</div>
              <span className="text-lg font-bold text-accent-cyan">{bookmarks.length}</span>
            </div>
            <p className="text-xs text-surface-500 mt-2">Saved scenarios to retry</p>
          </FixitPanel>
        </Link>
        <Link to="/profile" className="block">
          <FixitPanel padding="p-4" className="hover:border-accent-purple/30 transition-all h-full">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-medium text-white"><Bell size={16} className="text-accent-purple" /> Notifications</div>
              <span className="text-lg font-bold text-accent-purple">{unreadNotifications}</span>
            </div>
            <p className="text-xs text-surface-500 mt-2">Unread updates</p>
          </FixitPanel>
        </Link>
        <Link to="/lab-history" className="block">
          <FixitPanel padding="p-4" className="hover:border-accent-amber/30 transition-all h-full">
            <div className="flex items-center gap-2 text-sm font-medium text-white"><History size={16} className="text-accent-amber" /> Lab History</div>
            <p className="text-xs text-surface-500 mt-2">Past attempts & scores</p>
          </FixitPanel>
        </Link>
        <Link to="/achievements" className="block">
          <FixitPanel padding="p-4" className="hover:border-accent-green/30 transition-all h-full">
            <div className="flex items-center gap-2 text-sm font-medium text-white"><BarChart3 size={16} className="text-accent-green" /> Progress</div>
            <p className="text-xs text-surface-500 mt-2">{stats.completed || 0} scenarios completed</p>
          </FixitPanel>
        </Link>
      </div>

      {Object.keys(displayedTechProgress).length > 0 && (
        <FixitPanel>
          <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2"><Layers size={18} className="text-accent-cyan" /> Progress by Technology</h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(displayedTechProgress).map(([name, data]) => {
              const pct = data.total ? Math.round((data.completed / data.total) * 100) : 0
              return (
                <Link key={name} to="/technologies" className="p-4 rounded-xl bg-surface-800/40 border border-surface-700/40 hover:border-accent-cyan/30 transition-all">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-semibold text-white">{name}</span>
                    <span className="text-xs text-accent-cyan font-bold">{pct}%</span>
                  </div>
                  <div className="h-2 bg-surface-700 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-accent-cyan to-accent-blue" style={{ width: `${pct}%` }} />
                  </div>
                  <p className="text-[11px] text-surface-500 mt-2">{data.completed}/{data.total} scenarios · avg {data.avg_score || 0}</p>
                </Link>
              )
            })}
          </div>
        </FixitPanel>
      )}

      {tutorialContinue.length > 0 && (
        <FixitPanel className="border-accent-purple/20">
          <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
            <BookOpen size={18} className="text-accent-purple" /> Continue Tutorials
          </h2>
          <div className="space-y-2">
            {tutorialContinue.map((item) => (
              <Link
                key={item.tutorial_slug}
                to={`/tutorials/${item.tutorial_slug}`}
                className="flex items-center justify-between p-3 rounded-lg bg-surface-800/50 hover:bg-surface-800 transition-colors"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-white truncate">{item.tutorial_title}</p>
                  <p className="text-xs text-surface-500">
                    {item.topic || 'Tutorial'} · {item.progress_pct ?? 0}% read
                  </p>
                </div>
                <ArrowRight size={14} className="text-accent-purple shrink-0" />
              </Link>
            ))}
          </div>
        </FixitPanel>
      )}

      {recent.filter(r => !r.completed && r.status !== 'COMPLETED').length > 0 && (
        <FixitPanel className="border-accent-cyan/20">
          <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2"><Play size={18} className="text-accent-cyan" /> Continue Learning</h2>
          <div className="space-y-2">
            {recent.filter(r => !r.completed && r.status !== 'COMPLETED').slice(0, 4).map(item => (
              <Link key={item.id || item.scenario_slug} to={`/scenarios/${item.scenario_slug}`} className="flex items-center justify-between p-3 rounded-lg bg-surface-800/50 hover:bg-surface-800 transition-colors">
                <div>
                  <p className="text-sm font-medium text-white">{item.title}</p>
                  <p className="text-xs text-surface-500">{item.technology || 'Lab'} · {item.attempts || 1} attempt(s)</p>
                </div>
                <ArrowRight size={14} className="text-accent-cyan" />
              </Link>
            ))}
          </div>
        </FixitPanel>
      )}

      {/* Worst case on the page: a running lab that silently vanishes. The user
          concludes they have nothing running and starts a second one, which burns
          quota and can collide with the still-live environment.
          Plain div, not FixitPanel: that component only forwards children,
          className and padding, so a data-testid on it would be dropped. */}
      {failed.activeLabs && (
        <div
          data-testid="dashboard-active-labs-error"
          className="fx-panel p-4 border-accent-red/30 bg-accent-red/[0.05]"
        >
          <h3 className="text-sm font-semibold text-accent-red mb-1.5 flex items-center gap-2">
            <AlertTriangle size={14} /> Couldn&apos;t check for running labs
          </h3>
          <p className="text-xs text-surface-400">
            You may still have a lab running. Don&apos;t start a new one until this loads —
            check <Link to="/lab-history" className="text-accent-cyan hover:underline">your lab history</Link> or reload.
          </p>
        </div>
      )}

      {activeLabs.length > 0 && (
        <FixitPanel padding="p-4" className="border-accent-amber/20 bg-accent-amber/5 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-r from-accent-amber/[0.04] via-transparent to-transparent pointer-events-none" />
          <h3 className="text-sm font-semibold text-accent-amber mb-3 flex items-center gap-2 relative"><Zap size={14} className="animate-pulse" /> Active Labs</h3>
          <div className="space-y-2 relative">
            {activeLabs.map(lab => (
              <Link key={lab.id} to={`/lab/${lab.id}`} className="flex items-center justify-between p-3 bg-surface-800/50 rounded-lg hover:bg-surface-800 transition-all hover:translate-x-1 duration-200">
                <div>
                  <span className="text-sm font-medium text-white">{lab.scenario_detail?.title || 'Lab'}</span>
                  <span className="text-xs text-surface-400 ml-3">{Math.floor(lab.time_remaining / 60)}m remaining</span>
                </div>
                <ArrowRight size={14} className="text-accent-amber" />
              </Link>
            ))}
          </div>
        </FixitPanel>
      )}

      {jiraTickets.length > 0 && (
        <FixitPanel padding="p-4" className="border-blue-500/20 bg-blue-500/5 relative overflow-hidden">
          <h3 className="text-sm font-semibold text-blue-400 mb-3 flex items-center gap-2">
            <Ticket size={14} /> My Incident Tickets
          </h3>
          {jiraTickets.filter(t => !t.is_closed).length > 0 && (
            <div className="space-y-2 mb-4">
              <p className="text-[10px] uppercase tracking-wide text-surface-500">Open</p>
              {jiraTickets.filter(t => !t.is_closed).slice(0, 5).map(t => (
                <Link
                  key={t.issue_key}
                  to={`/scenarios/${t.scenario?.slug}`}
                  className="flex items-center justify-between p-3 bg-surface-800/50 rounded-lg hover:bg-surface-800 transition-colors"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-white truncate">{t.scenario?.title}</p>
                    <p className="text-xs text-surface-400">{t.jira_status || 'Open'} · {t.run_count} run{t.run_count !== 1 ? 's' : ''}</p>
                  </div>
                  <JiraTicketLink issueKey={t.issue_key} issueUrl={t.issue_url} className="text-xs shrink-0 ml-2" />
                </Link>
              ))}
            </div>
          )}
          {jiraTickets.filter(t => t.is_closed).length > 0 && (
            <div className="space-y-2">
              <p className="text-[10px] uppercase tracking-wide text-surface-500">Closed</p>
              {jiraTickets.filter(t => t.is_closed).slice(0, 3).map(t => (
                <Link
                  key={t.issue_key}
                  to={`/scenarios/${t.scenario?.slug}`}
                  className="flex items-center justify-between p-3 bg-surface-900/30 rounded-lg opacity-75 hover:opacity-100 transition-opacity"
                >
                  <div className="min-w-0">
                    <p className="text-sm text-surface-300 truncate">{t.scenario?.title}</p>
                    <p className="text-xs text-surface-500">{t.jira_status} · closed</p>
                  </div>
                  <JiraTicketLink issueKey={t.issue_key} issueUrl={t.issue_url} className="text-xs shrink-0 ml-2 text-surface-500" />
                </Link>
              ))}
            </div>
          )}
          <p className="text-[11px] text-surface-500 mt-3">Personal tickets only — you cannot see other learners&apos; incidents.</p>
        </FixitPanel>
      )}

      <div className="bg-gradient-stripe rounded-full" />

      <CertDashboardPanel />

      {/* ═══ MY SUBSCRIPTIONS ═══ */}
      <FixitPanel className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-accent-amber/[0.04] via-transparent to-accent-cyan/[0.04] pointer-events-none" />
        <div className="flex items-center justify-between mb-5 relative">
          <h2 className="text-lg font-bold text-white flex items-center gap-2"><Crown size={18} className="text-accent-amber" /> My Subscriptions</h2>
          <Link to="/pricing" className="text-xs text-accent-cyan hover:underline flex items-center gap-1 bg-accent-cyan/5 px-3 py-1 rounded-full border border-accent-cyan/20 hover:border-accent-cyan/40 transition-all">Manage <ArrowUpRight size={12} /></Link>
        </div>
        {complimentaryAccess && (
          <div className="mb-4 p-3 rounded-lg bg-accent-green/10 border border-accent-green/20 flex items-center gap-2 relative">
            <Sparkles size={16} className="text-accent-green shrink-0" />
            <p className="text-sm text-accent-green">You have complimentary free access to all technologies.</p>
          </div>
        )}
        {failed.subscriptions ? (
          /* Never show "No active subscriptions" + a Subscribe CTA on a failed
             fetch — that is the duplicate-purchase trap: the page would tell a
             paying customer their subscription is gone and invite them to rebuy. */
          <div
            data-testid="dashboard-subscriptions-error"
            className="p-4 rounded-lg bg-accent-red/[0.06] border border-accent-red/25 text-sm relative"
          >
            <p className="text-surface-200">Couldn&apos;t load your subscriptions</p>
            <p className="text-xs text-surface-500 mt-1">
              Don&apos;t purchase again — this is a loading problem, not a lapsed subscription.
              Reload to try again.
            </p>
            <button onClick={() => window.location.reload()} className="btn-secondary text-xs px-3 py-1.5 mt-3">
              Reload
            </button>
          </div>
        ) : subscriptions.filter(s => s.is_active).length === 0 && !complimentaryAccess ? (
          <div className="text-center py-8 relative">
            <div className="w-16 h-16 mx-auto mb-3 rounded-2xl bg-surface-800/50 flex items-center justify-center"><Layers size={28} className="text-surface-600" /></div>
            <p className="text-surface-400 text-sm mb-4">No active subscriptions</p>
            <p className="text-xs text-surface-500 mb-4 max-w-xs mx-auto">
              Subscribe to a technology track to unlock its hands-on labs and start building a streak.
            </p>
            <Link to="/pricing" className="btn-primary text-sm px-6 py-2 inline-flex items-center gap-2"><CreditCard size={14} /> Subscribe to a Technology</Link>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 relative">
            {subscriptions.filter(s => s.is_active).map(sub => {
              const techData = techProgress[sub.technology?.name] || {}
              const pct = techData.total ? Math.round((techData.completed / techData.total) * 100) : 0
              return (
                <div key={sub.id} className="bg-surface-800/40 rounded-xl p-4 border border-surface-700/40 group hover:bg-surface-800/70 hover:border-accent-cyan/20 transition-all duration-300 relative overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/[0.03] via-transparent to-accent-purple/[0.02] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
                  <div className="flex items-center justify-between mb-3 relative">
                    <Link to="/technologies" className="text-sm font-bold text-white hover:text-accent-cyan transition-colors">{sub.technology?.name}</Link>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] bg-accent-amber/10 text-accent-amber px-2 py-0.5 rounded-full font-medium flex items-center gap-1"><Crown size={10} /> Active</span>
                      <button onClick={(e) => { e.stopPropagation(); setCancelModal(sub) }}
                        className="p-1.5 rounded-lg text-surface-500 hover:text-accent-red hover:bg-accent-red/10 transition-all border border-transparent hover:border-accent-red/20" title="Cancel subscription">
                        <XCircle size={14} />
                      </button>
                    </div>
                  </div>
                  <div className="w-full h-2.5 bg-surface-700/60 rounded-full overflow-hidden mb-2 relative">
                    <div className="h-full bg-gradient-to-r from-accent-cyan to-accent-blue rounded-full transition-all duration-1000" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-surface-400">{techData.completed || 0}/{techData.total || 0} completed</span>
                    <span className="text-accent-cyan font-bold">{pct}%</span>
                  </div>
                  {pct === 100 && (
                    <Link to="/achievements" className="mt-2 flex items-center gap-1.5 text-[10px] text-accent-green hover:text-accent-green/80 transition-colors font-medium">
                      <Download size={10} /> Download Certificate
                    </Link>
                  )}
                  <p className="text-[10px] text-surface-500 mt-2 truncate font-mono">ID: {sub.subscription_id}</p>
                  {sub.created_at && (
                    <p className="text-[10px] text-surface-500 mt-1">
                      Started: {new Date(sub.created_at).toLocaleDateString()}
                    </p>
                  )}
                  {sub.expires_at && (
                    <p className={`text-[10px] mt-0.5 ${sub.needs_renewal ? 'text-accent-amber font-medium' : 'text-surface-500'}`}>
                      Expires: {new Date(sub.expires_at).toLocaleDateString()}
                      {sub.days_until_expiry != null && ` (${sub.days_until_expiry}d left)`}
                    </p>
                  )}
                  {(sub.needs_renewal || sub.is_expired || sub.in_grace_period) && (
                    <Link
                      to={`/payment?technology=${sub.technology?.slug}&renew=1`}
                      className="mt-2 inline-flex items-center gap-1 text-[10px] text-accent-amber hover:text-accent-amber/80 font-semibold"
                    >
                      <CreditCard size={10} /> {sub.in_grace_period ? 'Renew to restore labs' : 'Renew Subscription'}
                    </Link>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </FixitPanel>

      <div className="bg-gradient-stripe rounded-full" />
      <ActivityHeatmap recentActivity={recent} />

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {Object.keys(diffProgress).length > 0 && (
            <FixitPanel className="relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/[0.04] via-transparent to-accent-purple/[0.03] pointer-events-none" />
              <h2 className="text-lg font-bold text-white mb-5 flex items-center gap-2 relative"><Target size={18} className="text-accent-cyan" /> By Difficulty</h2>
              <div className="grid grid-cols-3 gap-4 relative">
                {Object.entries(diffProgress).map(([diff, data]) => {
                  const pct = data.total ? Math.round((data.completed / data.total) * 100) : 0
                  const colors = difficultyColors[diff] || difficultyColors.easy
                  return (
                    <div key={diff} className="bg-surface-800/40 rounded-xl p-4 text-center border border-surface-700/30 hover:border-surface-600/50 transition-all">
                      <p className={`text-xs font-bold uppercase tracking-wider ${colors.text} mb-2`}>{diff}</p>
                      <p className="text-2xl font-black text-white">{data.completed}<span className="text-surface-400 text-sm font-medium">/{data.total}</span></p>
                      <div className="w-full h-2.5 bg-surface-700/50 rounded-full overflow-hidden mt-3">
                        <div className={`h-full bg-gradient-to-r ${colors.bar} rounded-full transition-all duration-700`} style={{ width: `${pct}%` }} />
                      </div>
                      <p className="text-xs text-surface-400 mt-1.5 font-medium">{pct}%</p>
                    </div>
                  )
                })}
              </div>
            </FixitPanel>
          )}
          <FixitPanel className="relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-accent-blue/[0.03] via-transparent to-accent-green/[0.02] pointer-events-none" />
            <h2 className="text-lg font-bold text-white mb-5 flex items-center gap-2 relative"><Clock size={18} className="text-accent-blue" /> Recent Activity</h2>
            {recent.length === 0 ? (
              <div className="text-center py-6"><Clock size={32} className="text-surface-700 mx-auto mb-2" /><p className="text-surface-400 text-sm">No recent activity. Start a challenge!</p></div>
            ) : (
              <div className="space-y-2 relative">
                {recent.slice(0, 8).map((item, i) => (
                  <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-surface-800/30 hover:bg-surface-800/60 transition-all duration-200 group border border-transparent hover:border-surface-700/30">
                    <div className={`w-3 h-3 rounded-full shrink-0 ${item.status === 'COMPLETED' ? 'bg-accent-green shadow-lg shadow-accent-green/40' : item.status === 'RUNNING' ? 'bg-accent-amber animate-pulse shadow-lg shadow-accent-amber/40' : 'bg-surface-500'}`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-surface-200 truncate font-medium">{item.scenario_title}</p>
                      <p className="text-xs text-surface-400">{item.status === 'COMPLETED' ? `Score: ${item.score}` : item.status}{item.technology && <span className="ml-2 text-surface-500">· {item.technology}</span>}</p>
                    </div>
                    {item.status === 'COMPLETED' && <CheckCircle2 size={14} className="text-accent-green shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />}
                  </div>
                ))}
              </div>
            )}
          </FixitPanel>
        </div>
        <div className="space-y-6">
          {/* Engagement: XP/level + streak (both hide gracefully on error) */}
          <XpLevelCard />
          <StreakWidget />
          <FixitPanel className="relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-accent-amber/[0.04] via-transparent to-accent-pink/[0.03] pointer-events-none" />
            <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2 relative">
              <Award size={18} className="text-accent-amber" /> Achievements
              {earnedAch.length > 0 && <span className="ml-auto text-xs bg-accent-amber/10 text-accent-amber px-2.5 py-0.5 rounded-full font-bold border border-accent-amber/20">{earnedAch.length}/{Object.keys(ACHIEVEMENT_META).length}</span>}
            </h2>
            {earnedAch.length === 0 ? (
              <div className="text-center py-6"><div className="w-14 h-14 mx-auto mb-3 rounded-2xl bg-accent-amber/5 border border-accent-amber/10 flex items-center justify-center"><Award size={24} className="text-surface-600" /></div><p className="text-surface-400 text-sm">Solve challenges to earn badges!</p></div>
            ) : (
              <div className="grid grid-cols-3 gap-2 relative">
                {earnedAch.map((ach) => {
                  const meta = ACHIEVEMENT_META[ach.key] || { icon: Star, color: 'text-surface-400', label: ach.label || ach.key }
                  const Icon = meta.icon
                  return (
                    <div key={ach.key} className="flex flex-col items-center p-2.5 bg-surface-800/40 rounded-xl border border-surface-700/30 hover:border-accent-amber/20 transition-all group" title={meta.label}>
                      <Icon size={20} className={`${meta.color} group-hover:scale-110 transition-transform`} />
                      <span className="text-[10px] text-surface-400 mt-1 text-center leading-tight">{meta.label}</span>
                    </div>
                  )
                })}
              </div>
            )}
          </FixitPanel>
          <FixitPanel className="relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-accent-purple/[0.04] via-transparent to-accent-blue/[0.03] pointer-events-none" />
            <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2 relative"><BookOpen size={18} className="text-accent-purple" /> Account</h2>
            <div className="space-y-3 text-sm relative">
              {[
                { label: 'Username', value: user?.username, color: 'text-white font-semibold' },
                { label: 'Email', value: user?.email, color: 'text-surface-300 text-xs truncate' },
                ...(user?.date_joined ? [{ label: 'Joined', value: new Date(user.date_joined).toLocaleDateString(), color: 'text-surface-300' }] : []),
                { label: 'Active Subs', value: subscriptions.filter(s => s.is_active).length, color: 'text-accent-cyan font-bold' },
              ].map(({ label, value, color }) => (
                <div key={label} className="flex justify-between items-center py-1 border-b border-surface-700/20 last:border-0">
                  <span className="text-surface-400">{label}</span>
                  <span className={`${color} ml-2`}>{value}</span>
                </div>
              ))}
            </div>
          </FixitPanel>
        </div>
      </div>

      {recommended.length > 0 && (
        <FixitPanel padding="p-5" className="space-y-3">
          <h3 className="font-semibold text-white text-sm flex items-center gap-2">
            <TrendingUp size={16} className="text-accent-cyan" /> Recommended Next
          </h3>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
            {recommended.map(s => (
              <Link
                key={s.slug}
                to={`/scenarios/${s.slug}`}
                className="flex flex-col gap-1 p-3 rounded-lg bg-surface-800/50 border border-surface-700/30 hover:border-accent-cyan/30 hover:bg-surface-800/80 transition-all group"
              >
                <span className="text-white text-xs font-medium group-hover:text-accent-cyan transition-colors line-clamp-2">{s.title}</span>
                <div className="flex items-center gap-1.5 mt-auto pt-1">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                    s.difficulty === 'easy' ? 'bg-accent-green/10 text-accent-green' :
                    s.difficulty === 'medium' ? 'bg-accent-amber/10 text-accent-amber' :
                    'bg-accent-red/10 text-accent-red'
                  }`}>{s.difficulty}</span>
                  <span className="text-[10px] text-surface-500 truncate">{s.technology}</span>
                </div>
              </Link>
            ))}
          </div>
        </FixitPanel>
      )}

      <div className="flex flex-wrap gap-3">
        <Link to="/technologies" className="btn-secondary flex items-center gap-2"><Target size={16} /> Browse Technologies</Link>
        <Link to="/scenarios" className="btn-secondary flex items-center gap-2"><Target size={16} /> All Scenarios</Link>
        <Link to="/leaderboard" className="btn-secondary flex items-center gap-2"><Trophy size={16} /> Leaderboard</Link>
      </div>

      {/* ═══ CANCEL MODAL ═══ */}
      {cancelModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-fade-in" onClick={() => !cancelling && setCancelModal(null)}>
          <div className="max-w-md w-full animate-scale-in" onClick={e => e.stopPropagation()}>
          <FixitPanel padding="p-6" className="gradient-border relative overflow-hidden">
            <button
              type="button"
              onClick={() => !cancelling && setCancelModal(null)}
              className="absolute top-4 right-4 text-surface-400 hover:text-white p-1 rounded-md hover:bg-surface-800/60 transition-colors"
              aria-label="Close"
            >
              <X size={18} />
            </button>
            <div className="absolute inset-0 bg-gradient-to-br from-accent-red/[0.05] via-transparent to-accent-red/[0.02] pointer-events-none" />
            <div className="flex items-center gap-3 mb-4 relative">
              <div className="w-12 h-12 rounded-xl bg-accent-red/10 flex items-center justify-center border border-accent-red/20 shadow-lg shadow-accent-red/10"><AlertTriangle size={24} className="text-accent-red" /></div>
              <div><h3 className="text-lg font-bold text-white">Cancel Subscription</h3><p className="text-sm text-surface-400">You keep access until your term ends</p></div>
            </div>
            <p className="text-surface-300 text-sm mb-2 relative">Are you sure you want to cancel your <span className="font-bold text-white">{cancelModal.technology?.name}</span> subscription?</p>
            {/* Cancellation is at period end (audit Z1-11) — this list used to say
                access was lost immediately, which was true of the old behaviour and
                would now be a false warning that talks people out of cancelling. */}
            <ul className="text-sm text-surface-400 space-y-1.5 mb-6 ml-4 list-disc relative">
              <li>
                You keep full access to {cancelModal.technology?.name} until
                {' '}<span className="font-semibold text-white">
                  {cancelModal.expires_at
                    ? new Date(cancelModal.expires_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
                    : 'the end of your paid term'}
                </span> — nothing is lost today
              </li>
              <li>It simply will not renew after that</li>
              <li>Your progress is kept either way</li>
            </ul>
            <div className="flex gap-3 justify-end relative">
              <button onClick={() => setCancelModal(null)} disabled={cancelling} className="btn-secondary text-sm px-5 py-2">Keep Subscription</button>
              <button onClick={() => handleCancelSubscription(cancelModal)} disabled={cancelling} className="btn-danger text-sm px-5 py-2 flex items-center gap-2">
                {cancelling ? <><div className="w-4 h-4 border-2 border-accent-red/30 border-t-accent-red rounded-full animate-spin" /> Cancelling...</> : <><XCircle size={14} /> Cancel Subscription</>}
              </button>
            </div>
          </FixitPanel>
          </div>
        </div>
      )}
    </div>
  )
}