import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link, useLocation } from 'react-router-dom'
import { scenarioApi } from '../api/scenarios'
import { labApi } from '../api/labs'
import { ratingsApi } from '../api/ratings'
import { jiraApi } from '../api/jira'
import JiraTicketPanel from '../components/JiraTicketPanel'
import { useAuthStore } from '../store/authStore'
import {
  Clock, Target, Lightbulb, Play, CheckCircle2,
  Wrench, Skull, ArrowLeft, BookmarkPlus, Bookmark,
  Users, BarChart3, Hash, Award, Lock, Eye, Zap, Star, Send, ExternalLink
} from 'lucide-react'
import toast from 'react-hot-toast'

const typeConfig = {
  fix: { icon: Wrench, label: 'Fix', desc: 'Find and fix the broken service' },
  do:  { icon: Play, label: 'Do', desc: 'Complete the given task' },
  hack: { icon: Skull, label: 'Hack', desc: 'Exploit a vulnerability or find a flag' },
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
  const [ratings, setRatings] = useState([])
  const [userRating, setUserRating] = useState(0)
  const [hoverRating, setHoverRating] = useState(0)
  const [reviewText, setReviewText] = useState('')
  const [submittingRating, setSubmittingRating] = useState(false)
  const [jiraTicket, setJiraTicket] = useState(null)
  const [jiraComments, setJiraComments] = useState([])
  const [jiraActivity, setJiraActivity] = useState([])
  const [activeLabSession, setActiveLabSession] = useState(null)

  useEffect(() => {
    // Show lab expired toast if redirected from LabRunner timeout
    if (location.state?.labExpired) {
      toast('Lab time completed — the environment has been terminated. You can try again anytime!', {
        icon: '⏰',
        duration: 7000,
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
        if (isAuthenticated && data?.id) {
          jiraApi.ensureScenarioTicket(data.id)
            .then(res => {
              setJiraTicket(res.data?.ticket || null)
              setJiraComments(res.data?.recent_comments || [])
              setJiraActivity(res.data?.activity || [])
            })
            .catch(() => { setJiraTicket(null); setJiraComments([]); setJiraActivity([]) })
        }
        // Fetch ratings for this scenario
        ratingsApi.getRatings({ type: 'scenario', scenario: data.id })
          .then(r => setRatings(r.ratings || r.results || []))
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
    setStarting(true)
    try {
      const session = await labApi.startLab(scenario.id)
      if (session.jira_reset) {
        toast(`Fresh attempt #${session.jira_run_count || 1} — ticket history cleared`, { icon: '🔄', duration: 5000 })
        jiraApi.getScenarioTicket(scenario.id, { details: 1 })
          .then(res => {
            setJiraTicket(res.data?.ticket || null)
            setJiraComments(res.data?.recent_comments || [])
            setJiraActivity(res.data?.activity || [])
          })
          .catch(() => {})
      } else if (session.jira_issue_key) {
        setJiraTicket({
          issue_key: session.jira_issue_key,
          issue_url: '',
          jira_status: session.jira_status || 'In Progress',
          run_count: session.jira_run_count || 1,
        })
      }
      if (session.resumed) {
        toast('You already have an active lab for this scenario — reconnecting...', { icon: '🔄', duration: 4000 })
      } else if (session.status === 'PROVISIONING') {
        toast('Launching cloud server — please wait...', { icon: '☁️', duration: 5000 })
      } else {
        toast.success('Lab environment ready!')
      }
      navigate(`/lab/${session.id}`)
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
        if (data?.session_id) {
          navigate(`/lab/${data.session_id}`)
        }
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
      // Refresh ratings
      const r = await ratingsApi.getRatings({ type: 'scenario', scenario: scenario.id })
      setRatings(r.ratings || r.results || [])
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
        <div className="flex gap-2">
          <div className="h-6 w-16 bg-surface-700 rounded-full" />
          <div className="h-6 w-20 bg-surface-700 rounded-full" />
        </div>
        <div className="h-8 w-3/4 bg-surface-800 rounded" />
        <div className="h-4 w-1/2 bg-surface-800 rounded" />
        <div className="flex gap-4 mt-4">
          <div className="h-10 w-24 bg-surface-700 rounded-lg" />
          <div className="h-10 w-24 bg-surface-700 rounded-lg" />
          <div className="h-10 w-24 bg-surface-700 rounded-lg" />
        </div>
      </div>
      <div className="glass-card p-8 space-y-3">
        <div className="h-6 w-40 bg-surface-800 rounded" />
        <div className="h-4 w-full bg-surface-800 rounded" />
        <div className="h-4 w-5/6 bg-surface-800 rounded" />
        <div className="h-4 w-2/3 bg-surface-800 rounded" />
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
  const userCompleted = scenario.user_progress?.completed
  const objectives = Array.isArray(scenario.objectives) ? scenario.objectives : []

  return (
    <div className="max-w-4xl mx-auto space-y-5 animate-fade-in">
      {/* Back link */}
      <Link to="/scenarios" className="inline-flex items-center gap-1.5 text-sm text-surface-400 hover:text-white transition-colors">
        <ArrowLeft size={14} /> All Scenarios
      </Link>

      {/* Header card */}
      <div className="glass-card p-6 lg:p-8">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            {/* Badges row */}
            <div className="flex items-center gap-2 flex-wrap mb-3">
              <span className={`badge-${scenario.difficulty}`}>{scenario.difficulty}</span>
              <span className={`px-2 py-0.5 rounded text-xs font-medium border flex items-center gap-1 ${
                scenario.scenario_type === 'hack' ? 'bg-accent-red/10 text-accent-red border-accent-red/20'
                : scenario.scenario_type === 'do' ? 'bg-accent-green/10 text-accent-green border-accent-green/20'
                : 'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/20'
              }`}>
                <TypeIcon size={11} /> {typeInfo.label}
              </span>
              <span className="bg-surface-700/50 px-2 py-0.5 rounded text-xs text-surface-400">
                {scenario.category}
              </span>
              {scenario.technology && (
                <span className="bg-accent-cyan/5 text-accent-cyan px-2 py-0.5 rounded text-xs border border-accent-cyan/10">
                  {scenario.technology.name}
                </span>
              )}
              {scenario.is_free && (
                <span className="bg-accent-green/10 text-accent-green px-2 py-0.5 rounded text-xs border border-accent-green/20">
                  Free
                </span>
              )}
            </div>

            <h1 className="text-2xl lg:text-3xl font-bold text-white mb-1">{scenario.title}</h1>
            {scenario.subtitle && (
              <p className="text-surface-400 text-sm">{scenario.subtitle}</p>
            )}

            {/* Stats row */}
            <div className="flex items-center gap-5 text-sm text-surface-400 mt-4">
              <span className="flex items-center gap-1.5"><Clock size={14} /> {timeMinutes} min</span>
              <span className="flex items-center gap-1.5"><Target size={14} /> {scenario.max_score} pts max</span>
              <span className="flex items-center gap-1.5"><Lightbulb size={14} /> {scenario.hints_count || 0} hints</span>
              {scenario.attempts_count > 0 && (
                <span className="flex items-center gap-1.5"><Users size={14} /> {scenario.attempts_count} attempts</span>
              )}
              {scenario.completions_count > 0 && (
                <span className="flex items-center gap-1.5"><BarChart3 size={14} /> {Math.round(scenario.completions_count / Math.max(scenario.attempts_count, 1) * 100)}% solve rate</span>
              )}
            </div>
          </div>

          {/* Right side — status & bookmark */}
          <div className="flex flex-col items-end gap-2">
            {userCompleted && (
              <div className="flex items-center gap-2 text-accent-green bg-accent-green/10 border border-accent-green/20 rounded-lg px-3 py-1.5">
                <CheckCircle2 size={16} />
                <span className="text-sm font-semibold">Solved</span>
              </div>
            )}
            <button onClick={handleBookmark} className="text-surface-500 hover:text-accent-amber transition-colors p-1">
              {scenario.is_bookmarked
                ? <Bookmark size={20} className="text-accent-amber fill-accent-amber" />
                : <BookmarkPlus size={20} />
              }
            </button>
          </div>
        </div>

        {/* Tags */}
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
      </div>

      {/* Description */}
      <div className="glass-card p-6">
        <h2 className="text-base font-semibold text-white mb-3">Description</h2>
        <p className="text-sm text-surface-300 leading-relaxed whitespace-pre-wrap">{scenario.description}</p>
      </div>

      {/* Objectives */}
      {objectives.length > 0 && (
        <div className="glass-card p-6">
          <h2 className="text-base font-semibold text-white mb-3">Expected outcome</h2>
          <ul className="space-y-2">
            {objectives.map((obj, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-surface-300">
                <Target size={14} className="text-accent-cyan mt-0.5 shrink-0" />
                <span>{typeof obj === 'string' ? obj : JSON.stringify(obj)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Initial State */}
      {scenario.initial_state && (
        <div className="glass-card p-6">
          <h2 className="text-base font-semibold text-white mb-3">Initial State</h2>
          <div className="bg-surface-950 rounded-lg p-4 font-mono text-sm text-surface-300 leading-relaxed whitespace-pre-wrap border border-surface-800">
            {scenario.initial_state}
          </div>
        </div>
      )}

      {/* User Progress */}
      {scenario.user_progress && (
        <div className="glass-card p-6">
          <h2 className="text-base font-semibold text-white mb-4">Your Progress</h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-surface-800/50 rounded-lg p-3">
              <p className="text-xl font-bold text-white">{scenario.user_progress.attempts}</p>
              <p className="text-xs text-surface-400">Attempts</p>
            </div>
            <div className="bg-surface-800/50 rounded-lg p-3">
              <p className="text-xl font-bold text-accent-amber">{scenario.user_progress.best_score}</p>
              <p className="text-xs text-surface-400">Best Score</p>
            </div>
            <div className="bg-surface-800/50 rounded-lg p-3">
              <p className="text-xl font-bold text-white">
                {scenario.user_progress.best_time ? `${Math.floor(scenario.user_progress.best_time / 60)}m ${scenario.user_progress.best_time % 60}s` : '—'}
              </p>
              <p className="text-xs text-surface-400">Best Time</p>
            </div>
            <div className="bg-surface-800/50 rounded-lg p-3">
              <p className={`text-xl font-bold ${userCompleted ? 'text-accent-green' : 'text-surface-500'}`}>
                {userCompleted ? 'Yes' : 'No'}
              </p>
              <p className="text-xs text-surface-400">Completed</p>
            </div>
          </div>
        </div>
      )}

      {/* Solution — only after solving */}
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
              <p className="text-sm text-surface-300 leading-relaxed whitespace-pre-wrap">
                {scenario.solution_explanation}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Daily Limit Reached Banner */}
      {limitInfo && (
        <div className="glass-card p-6 border-accent-amber/20 bg-accent-amber/5 animate-slide-up">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-xl bg-accent-amber/10 flex items-center justify-center shrink-0">
              <Zap size={20} className="text-accent-amber" />
            </div>
            <div className="flex-1">
              <h3 className="text-base font-semibold text-white mb-1">Daily Limit Reached</h3>
              <p className="text-sm text-surface-400 mb-3">
                You've used {limitInfo.usage?.labs_today} of {limitInfo.plan?.max_labs_per_day} labs today on the <span className="text-white font-medium">{limitInfo.plan?.name}</span> plan. Your limit resets at midnight UTC.
              </p>
              <div className="flex gap-3">
                <Link to="/pricing" className="btn-primary text-sm px-4 py-2 flex items-center gap-1.5">
                  <Zap size={14} /> Upgrade to Pro
                </Link>
                <button onClick={() => setLimitInfo(null)} className="text-sm text-surface-500 hover:text-surface-300 transition-colors px-3">
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Subscription Required Banner */}
      {scenario.is_accessible === false && (
        <div className="glass-card p-6 border-accent-purple/20 bg-accent-purple/5 animate-slide-up">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-xl bg-accent-purple/10 flex items-center justify-center shrink-0">
              <Lock size={20} className="text-accent-purple" />
            </div>
            <div className="flex-1">
              <h3 className="text-base font-semibold text-white mb-1">Subscription Required</h3>
              <p className="text-sm text-surface-400 mb-3">
                This scenario requires an active subscription for <span className="text-white font-medium">{scenario.technology?.name}</span>. Subscribe to unlock all scenarios for this technology.
              </p>
              <Link to="/pricing" className="btn-primary text-sm px-4 py-2 inline-flex items-center gap-1.5">
                <Zap size={14} /> View Pricing
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Ratings & Reviews */}
      <div className="glass-card p-6">
        <h2 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <Star size={16} className="text-accent-amber" /> Ratings & Reviews
          {ratings.length > 0 && (
            <span className="text-xs text-surface-500 ml-auto">{ratings.length} review{ratings.length !== 1 ? 's' : ''}</span>
          )}
        </h2>

        {/* Submit Rating */}
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
                  <Star
                    size={24}
                    className={`transition-colors ${
                      star <= (hoverRating || userRating)
                        ? 'text-accent-amber fill-accent-amber'
                        : 'text-surface-600'
                    }`}
                  />
                </button>
              ))}
              {userRating > 0 && (
                <span className="text-sm text-surface-400 ml-2">{userRating}/5</span>
              )}
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

        {/* Existing Reviews */}
        {ratings.length === 0 ? (
          <p className="text-sm text-surface-500 text-center py-3">No reviews yet. Be the first to rate!</p>
        ) : (
          <div className="space-y-3 max-h-60 overflow-y-auto">
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

      {/* Jira incident ticket (realistic workflow) */}
      {jiraTicket?.issue_key && (
        <JiraTicketPanel
          ticket={jiraTicket}
          comments={jiraComments}
          activity={jiraActivity}
          hideHistory={!!activeLabSession || starting}
          hideComments={!!activeLabSession || starting}
        />
      )}

      {/* Start Lab button */}
      <div className="flex gap-3">
        <button
          onClick={handleStartLab}
          disabled={starting || !!limitInfo || scenario.is_accessible === false}
          className="btn-primary flex-1 py-4 text-lg flex items-center justify-center gap-3 disabled:opacity-50"
        >
          {starting ? (
            <>
              <div className="w-5 h-5 border-2 border-surface-950 border-t-transparent rounded-full animate-spin" />
              {scenario.infrastructure_type && scenario.infrastructure_type !== 'docker'
                ? 'Launching cloud server...'
                : 'Provisioning lab environment...'}
            </>
          ) : (
            <>
              <Play size={20} />
              {userCompleted ? 'Launch Again (Fresh Environment)' : 'Start Challenge'}
            </>
          )}
        </button>
      </div>
      {userCompleted && (
        <p className="text-xs text-surface-500 text-center -mt-2">
          Each launch creates a fresh broken environment. Your previous "Solved" status will reset until you solve it again.
        </p>
      )}
    </div>
  )
}
