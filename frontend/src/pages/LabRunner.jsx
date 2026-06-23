import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom'
import api from '../api/client'
import { labApi } from '../api/labs'
import { ratingsApi } from '../api/ratings'
import { useLabStore } from '../store/labStore'
import { useAuthStore } from '../store/authStore'
import {
  Clock, CheckCircle2, XCircle, Lightbulb, StopCircle,
  ChevronRight, Trophy, Target, Eye, FileText,
  PanelLeftClose, PanelLeftOpen, Sparkles, Timer, Keyboard, ExternalLink, Terminal, Wand2, Ticket as TicketIcon
} from 'lucide-react'
import toast from 'react-hot-toast'
import { ConfirmDialog } from '../components/ConfirmModal'
import JiraTicketPanel from '../components/JiraTicketPanel'
import ItsmTicketPanel from '../components/itsm/ItsmTicketPanel'
import { itsmApi } from '../api/itsm'
import JiraTicketLink from '../components/JiraTicketLink'
import LabTerminal from '../components/LabTerminal'
import CodingIDE from '../components/ide/CodingIDE'
import PromptPlayground from '../components/promptlab/PromptPlayground'
import MonitoringSimulator from '../components/monitoring/MonitoringSimulator'
import SimLabTips from '../components/SimLabTips'
import DevOpsNetworkingSimToolkit from '../components/DevOpsNetworkingSimToolkit'
import SimLabQuickActions from '../components/SimLabQuickActions'
import SimLabWizard from '../components/SimLabWizard'
import useLabShortcuts from '../hooks/useLabShortcuts'
import { useIsMobile } from '../hooks/useMediaQuery'

function formatLabTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

/** Isolated timer display — avoids re-rendering the terminal tree every second. */
function LabTimerBadge({ variant = 'desktop' }) {
  const timeRemaining = useLabStore((s) => s.timeRemaining)
  const isTimeLow = timeRemaining < 120 && timeRemaining > 0
  const isTimeCritical = timeRemaining < 60 && timeRemaining > 0

  if (variant === 'mobile-bar') {
    return (
      <span className={`text-xs font-mono font-bold ${isTimeCritical ? 'text-accent-red' : 'text-surface-300'}`}>
        {formatLabTime(timeRemaining)}
      </span>
    )
  }

  if (variant === 'mobile-float') {
    return (
      <span className="absolute left-3 top-1 text-[10px] font-mono text-surface-500">
        {formatLabTime(timeRemaining)}
      </span>
    )
  }

  return (
    <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-mono font-bold ${
      isTimeCritical ? 'bg-accent-red/20 text-accent-red border border-accent-red/30 animate-pulse'
      : isTimeLow ? 'bg-accent-amber/10 text-accent-amber border border-accent-amber/20'
      : 'bg-surface-800 text-surface-300 border border-surface-700'
    }`}>
      <Timer size={13} />
      {formatLabTime(timeRemaining)}
    </div>
  )
}

export default function LabRunner() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const startTimer = useLabStore((s) => s.startTimer)
  const stopTimer = useLabStore((s) => s.stopTimer)
  const clearSession = useLabStore((s) => s.clearSession)

  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [provisioning, setProvisioning] = useState(false)
  const [provisioningStep, setProvisioningStep] = useState(0)
  const [provisioningElapsed, setProvisioningElapsed] = useState(0)
  const [isCloudLab, setIsCloudLab] = useState(false)
  const [validating, setValidating] = useState(false)
  const [validationResult, setValidationResult] = useState(null)
  const [hints, setHints] = useState({ revealed: [], next_available: false, total_hints: 0, hints_used: 0, interview_mode: false })
  const [interviewMode, setInterviewMode] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const isMobile = useIsMobile()
  const [sidebarTab, setSidebarTab] = useState('instructions') // instructions | hints | result
  const [showStopConfirm, setShowStopConfirm] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [showShortcuts, setShowShortcuts] = useState(false)
  const [terminalFullscreen, setTerminalFullscreen] = useState(false)
  // Feature: Lab time extension
  const [extending, setExtending] = useState(false)
  const [extensionsUsed, setExtensionsUsed] = useState(0)
  // Feature: Ask AI coaching hint
  const [aiHint, setAiHint] = useState(null)
  const [aiHintLoading, setAiHintLoading] = useState(false)
  const [aiCreditsRemaining, setAiCreditsRemaining] = useState(null)
  // Feature: Scenario star rating
  const [hasRated, setHasRated] = useState(false)
  const [rating, setRating] = useState(0)
  const [ratingHover, setRatingHover] = useState(0)
  const [ratingSubmitting, setRatingSubmitting] = useState(false)
  const [jiraComments, setJiraComments] = useState([])
  const [jiraActivity, setJiraActivity] = useState([])
  const [jiraTicket, setJiraTicket] = useState(null)
  const [jiraTransitioning, setJiraTransitioning] = useState(false)
  // ── ITSM (ServiceNow-style) ticket state ──
  const [itsmTicket, setItsmTicket] = useState(null)
  const [itsmMeta, setItsmMeta] = useState(null)
  const [itsmConfig, setItsmConfig] = useState(null)
  const [itsmBusy, setItsmBusy] = useState(false)
  const [closingIn, setClosingIn] = useState(null)
  const [terminalHost, setTerminalHost] = useState('primary')
  const [showSimWizard, setShowSimWizard] = useState(false)
  // Grafana/Prometheus simulator overlay (opened from the lab toolbar button).
  const [showMonitoringSim, setShowMonitoringSim] = useState(false)
  const [mobileInput, setMobileInput] = useState('')
  const [showMobileInput, setShowMobileInput] = useState(false)
  const terminalRefs = useRef({})
  const [sshClientTarget, setSshClientTarget] = useState(null)

  const TOAST = {}

  const labChannelRef = useRef(null)  // BroadcastChannel for cross-tab sync
  const closeTimerRef = useRef(null)
  const closeCountdownRef = useRef(null)
  // Always-fresh technology slug so cross-tab / async handlers can route back to
  // the right technology page without re-subscribing on every session change.
  // Seed it from the launch-time slug (passed via router state by the launcher)
  // so completion redirects work even for sessions whose detail payload never
  // populated technology (simulation / coding / cross-tech labs).
  const techSlugRef = useRef(useLocation().state?.techSlug || '')

  const LAB_CLOSE_SECONDS = 10

  const cleanupLabResources = useCallback(() => {
    clearSession()
    stopTimer()
  }, [clearSession, stopTimer])

  const scheduleLabClose = useCallback((result, slug) => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current)
    if (closeCountdownRef.current) clearInterval(closeCountdownRef.current)

    setClosingIn(LAB_CLOSE_SECONDS)
    toast(`Lab is closing in ${LAB_CLOSE_SECONDS} seconds…`, { icon: '⏳', duration: LAB_CLOSE_SECONDS * 1000, ...TOAST })

    closeCountdownRef.current = setInterval(() => {
      setClosingIn(prev => (prev != null && prev > 1 ? prev - 1 : prev))
    }, 1000)

    closeTimerRef.current = setTimeout(() => {
      if (closeCountdownRef.current) clearInterval(closeCountdownRef.current)
      setClosingIn(null)
      cleanupLabResources()
      // Return to the SAME technology's page so the user can immediately pick
      // another scenario in that technology, rather than the global list.
      const sc = session?.scenario || session?.scenario_detail || {}
      const techSlug = sc.technology?.slug
      const dest = techSlug ? `/technologies/${techSlug}` : `/scenarios/${slug || ''}`
      navigate(dest, {
        state: {
          labCompleted: true,
          score: result?.score,
          scenarioTitle: sc.title,
        },
      })
    }, LAB_CLOSE_SECONDS * 1000)
  }, [LAB_CLOSE_SECONDS, cleanupLabResources, navigate, session])

  useEffect(() => () => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current)
    if (closeCountdownRef.current) clearInterval(closeCountdownRef.current)
  }, [])

  // Keyboard shortcuts
  const toggleHints = useCallback(() => {
    setSidebarTab('hints')
    setSidebarOpen(prev => {
      if (sidebarTab === 'hints') return !prev
      return true
    })
  }, [sidebarTab])

  useLabShortcuts({
    onValidate: () => { if (!validating && !validationResult?.passed) handleValidate() },
    onToggleHints: toggleHints,
    onToggleSidebar: () => setSidebarOpen(p => !p),
    disabled: loading,
  })

  // Single-key shortcuts: V, H, F, R, ?
  useEffect(() => {
    if (loading) return
    const handleKey = (e) => {
      // Skip when focus is on a text input or textarea
      const tag = document.activeElement?.tagName?.toLowerCase()
      if (tag === 'input' || tag === 'textarea' || document.activeElement?.isContentEditable) return
      switch (e.key) {
        case 'v':
        case 'V':
          if (!validating && !validationResult?.passed) handleValidate()
          break
        case 'h':
        case 'H':
          toggleHints()
          break
        case 'f':
        case 'F':
          setTerminalFullscreen(p => {
            const next = !p
            setSidebarOpen(next ? false : true)
            return next
          })
          break
        case 'r':
        case 'R':
          // Reset timer display: restart the visible countdown from current remaining
          // (We call startTimer with the current value to re-render the badge)
          break
        case '?':
          setShowShortcuts(p => !p)
          break
        default:
          break
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [loading, validating, validationResult, toggleHints])

  // ── Cross-tab sync: detect when lab is stopped/expired from another tab ──
  useEffect(() => {
    if (typeof BroadcastChannel === 'undefined') return

    const channel = new BroadcastChannel(`fixitlab_lab_sync_${sessionId || 'global'}`)
    labChannelRef.current = channel

    channel.onmessage = (event) => {
      const { type, sessionId: stoppedId, reason, closingDelayMs } = event.data || {}
      if (type === 'lab_stopped' && stoppedId === sessionId) {
        const finish = () => {
          cleanupLabResources()
          const msg = reason === 'completed' ? 'Lab completed in another tab!'
            : reason === 'expired' ? 'Lab time expired!'
            : 'Lab was stopped in another tab'
          toast(msg, { icon: '🔄', duration: 4000, ...TOAST })
          // After completing, drop back to the technology page when known.
          const techSlug = techSlugRef.current
          navigate(reason === 'completed' && techSlug ? `/technologies/${techSlug}` : '/scenarios')
        }
        if (reason === 'completed' && closingDelayMs > 0) {
          toast(`Lab completed — closing in ${Math.ceil(closingDelayMs / 1000)}s…`, { icon: '✅', duration: closingDelayMs, ...TOAST })
          setTimeout(finish, closingDelayMs)
          return
        }
        finish()
      }
    }

    return () => {
      channel.close()
      labChannelRef.current = null
    }
  }, [sessionId, cleanupLabResources, navigate])

  // ── Background status poll (every 30s) — detect server-side termination ──
  useEffect(() => {
    if (!session) return
    let cancelled = false

    const pollInterval = setInterval(async () => {
      if (cancelled) return
      try {
        const lab = await labApi.getSessionStatus(sessionId)
        if (cancelled) return
        if (lab.status === 'TERMINATED' || lab.status === 'EXPIRED' || lab.status === 'FAILED' || lab.status === 'COMPLETED') {
          cleanupLabResources()
          const msg = lab.status === 'COMPLETED' ? 'Lab completed!'
            : lab.status === 'EXPIRED' ? 'Lab time expired!'
            : 'Lab session ended'
          toast(msg, { icon: lab.status === 'COMPLETED' ? '✅' : '⏰', duration: 4000, ...TOAST })
          // On completion, return to the technology page (continue other
          // scenarios there); otherwise fall back to the scenario detail page.
          const techSlug = lab.scenario?.technology?.slug
          const dest = lab.status === 'COMPLETED' && techSlug
            ? `/technologies/${techSlug}`
            : `/scenarios/${lab.scenario?.slug || ''}`
          navigate(dest, {
            state: lab.status === 'COMPLETED'
              ? { labCompleted: true, scenarioTitle: lab.scenario?.title }
              : undefined,
          })
        }
      } catch {
        // Ignore polling errors — don't disrupt the user
      }
    }, 30000) // every 30 seconds

    return () => {
      cancelled = true
      clearInterval(pollInterval)
    }
  }, [session, sessionId])

  // Load session info — poll if still provisioning
  useEffect(() => {
    let pollTimer = null
    let cancelled = false
    let elapsedCounter = 0

    const loadSession = async () => {
      try {
        // Use lightweight single-session endpoint instead of fetching all sessions
        const lab = await labApi.getSessionStatus(sessionId)
        if (cancelled) return

        if (!lab) {
          toast.error('Lab session not found')
          navigate('/scenarios')
          return
        }

        if (lab.status === 'PROVISIONING') {
          setProvisioning(true)
          const cloud = lab.provider === 'aws_ec2' || lab.provider === 'digitalocean'
          setIsCloudLab(cloud)
          elapsedCounter += 3
          setProvisioningElapsed(elapsedCounter)
          // For cloud labs, advance steps more slowly (they take 60-90s)
          if (cloud) {
            setProvisioningStep(prev => {
              if (prev === 0) return 1
              if (prev === 1 && elapsedCounter > 15) return 2
              if (prev === 2 && elapsedCounter > 40) return 3
              if (prev === 3 && elapsedCounter > 70) return 4
              return prev
            })
          } else {
            setProvisioningStep(prev => Math.min(prev + 1, 3))
          }
          pollTimer = setTimeout(loadSession, 3000) // poll every 3s
        } else if (lab.status === 'RUNNING') {
          setProvisioning(false)
          // Build session object compatible with the rest of the component
          // The status endpoint returns scenario as nested object
          const sessionData = {
            id: lab.id,
            status: lab.status,
            provider: lab.provider,
            ssh_host: lab.ssh_host,
            instance_id: lab.instance_id,
            container_id: lab.container_id,
            time_remaining: lab.time_remaining,
            duration_limit: lab.duration_limit,
            started_at: lab.started_at,
            score: lab.score,
            hints_used: lab.hints_used,
            validation_passed: lab.validation_passed,
            scenario: lab.scenario,
            scenario_detail: lab.scenario,
            jira_issue_key: lab.jira_issue_key || '',
            jira_issue_url: lab.jira_issue_url || '',
            lab_hosts: lab.lab_hosts || [],
          }
          setSession(sessionData)

          // Redirect pure VMware simulation labs to the dedicated vSphere simulator
          // UI. Cross-technology labs are NOT redirected — they open the Linux
          // terminal and merely surface an "Open VMware" link (handled below), since
          // the fix happens in the terminal after the VMware-side hardware change.
          const isCrossTech = Boolean(lab.scenario?.cross_technology)
          if (!isCrossTech && (lab.scenario?.simulation_type === 'vmware' || lab.scenario?.technology?.slug === 'vmware')) {
            navigate(`/vmware-sim?session=${sessionId}&scenario=${lab.scenario?.slug || ''}`, { replace: true })
            return
          }

          if (lab.jira_issue_key && lab.scenario?.id) {
            import('../api/jira').then(({ jiraApi }) =>
              jiraApi.getScenarioTicket(lab.scenario.id, { details: 1 })
                .then(res => {
                  setJiraComments(res.data?.recent_comments || [])
                  setJiraActivity(res.data?.activity || [])
                  if (res.data?.ticket) setJiraTicket(res.data.ticket)
                })
                .catch(() => { setJiraComments([]); setJiraActivity([]); setJiraTicket(null) })
            )
          }

          // ── ITSM (ServiceNow-style) ticket — open it on first load so the
          // panel has a parent ticket to raise sub-tickets from. Bound to this
          // session so a Storage sub-ticket's disk hot-add hits the right sim.
          if (lab.scenario?.itsm_enabled && lab.scenario?.id) {
            itsmApi.getMeta().then(r => setItsmMeta(r.data)).catch(() => {})
            itsmApi.ensureScenarioTicket(lab.scenario.id, sessionId)
              .then(res => { setItsmTicket(res.data?.ticket || null); setItsmConfig(res.data?.config || null) })
              .catch(() => {
                // Subscription-gated or disabled — leave the panel empty.
                setItsmTicket(null)
              })
          }

          if (lab.time_remaining > 0) {
            startTimer(lab.time_remaining, async () => {
              toast('Lab time completed! The environment is being terminated.', { icon: '⏰', duration: 6000, ...TOAST })

              try {
                await labApi.stopLab(sessionId)
              } catch (e) {
                console.warn('Failed to stop expired lab:', e)
              }

              clearSession()
              stopTimer()

              // Broadcast to other tabs that this lab expired
              if (labChannelRef.current) {
                labChannelRef.current.postMessage({ type: 'lab_stopped', sessionId, reason: 'expired' })
              }

              // Redirect to scenarios page after brief delay
              setTimeout(() => {
                navigate(`/scenarios/${lab.scenario?.slug || ''}`, {
                  state: { labExpired: true, scenarioTitle: lab.scenario?.title }
                })
              }, 2000)
            })
          }
          setLoading(false)
        } else if (lab.status === 'FAILED') {
          setProvisioning(false)
          setLoading(false)
          toast.error('Server failed to launch. Please try again.')
          navigate(`/scenarios/${lab.scenario?.slug || ''}`)
        } else {
          // TERMINATED, etc.
          toast.error(`Lab session ended (${lab.status.toLowerCase()})`)
          navigate('/scenarios')
        }
      } catch (err) {
        if (!cancelled) {
          console.error(err)
          // If session not found (404), redirect
          if (err.response?.status === 404) {
            toast.error('Lab session not found')
            navigate('/scenarios')
            return
          }
          // For other errors, retry after delay
          pollTimer = setTimeout(loadSession, 5000)
        }
      }
    }

    loadSession()
    labApi.getHints(sessionId).then((data) => {
      setHints(data)
      setInterviewMode(!!data.interview_mode)
    }).catch(console.error)

    return () => {
      cancelled = true
      if (pollTimer) clearTimeout(pollTimer)
      stopTimer()
    }
  }, [sessionId])


  // Auto-terminate lab on tab close / navigate away
  useEffect(() => {
    if (!session) return

    const handleBeforeUnload = (e) => {
      // Only show a warning dialog — do NOT send stopLab here.
      // beforeunload fires on BOTH reload and tab close, and we
      // don't want to kill the EC2 instance on a simple page refresh.
      // The lab stays alive and user can reconnect after reload.
      // Actual cleanup happens via:
      //   - Explicit "Stop Lab" button
      //   - 30-minute idle timeout (below)
      //   - Celery cleanup task (stuck PROVISIONING > 10 min, expired labs)
      e.preventDefault()
      e.returnValue = 'Your lab session is running. Are you sure you want to leave?'
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [session, sessionId])

  // Idle timeout: auto-terminate after 30 minutes of no terminal input
  useEffect(() => {
    if (!session) return

    const IDLE_TIMEOUT = 30 * 60 * 1000 // 30 minutes
    let idleTimer = null

    const resetIdleTimer = () => {
      if (idleTimer) clearTimeout(idleTimer)
      idleTimer = setTimeout(async () => {
        toast('Lab terminated due to 30 minutes of inactivity.', { icon: '⏰', duration: 8000, ...TOAST })
        try {
          await labApi.stopLab(sessionId)
        } catch {}
        clearSession()
        stopTimer()
        navigate(techSlugRef.current ? `/technologies/${techSlugRef.current}` : '/scenarios')
      }, IDLE_TIMEOUT)
    }

    // Reset timer on any user interaction
    const events = ['keydown', 'mousedown', 'mousemove', 'touchstart', 'scroll']
    events.forEach(e => window.addEventListener(e, resetIdleTimer, { passive: true }))
    resetIdleTimer() // Start the timer

    return () => {
      if (idleTimer) clearTimeout(idleTimer)
      events.forEach(e => window.removeEventListener(e, resetIdleTimer))
    }
  }, [session, sessionId])

  const handleJiraTransition = async (status) => {
    if (!session?.jira_issue_key) return
    setJiraTransitioning(true)
    try {
      const { jiraApi } = await import('../api/jira')
      const res = await jiraApi.transitionIssue(session.jira_issue_key, status)
      setJiraTicket(res.data)
      setJiraComments(res.data?.comments || [])
      setJiraActivity(res.data?.activity || [])
      toast.success(`Ticket moved to ${status}`)
      if (res.data?.is_closed && validationResult?.passed) {
        toast.success('Scenario marked complete — Jira ticket closed!', { duration: 6000 })
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to update ticket')
    } finally {
      setJiraTransitioning(false)
    }
  }

  const handleJiraComment = async (text) => {
    if (!session?.jira_issue_key) return
    try {
      const { jiraApi } = await import('../api/jira')
      const res = await jiraApi.addComment(session.jira_issue_key, text)
      const data = res.data || res
      setJiraTicket(data)
      setJiraComments(data?.comments || data?.recent_comments || [])
      setJiraActivity(data?.activity || [])

      if (data?.team_reply?.scheduled) {
        const delay = (data.team_reply.delay_seconds || 30) * 1000
        toast.success(`Teams notified — reply expected in ~${data.team_reply.delay_seconds || 30}s`, { duration: 5000 })
        const pollUntil = Date.now() + delay + 8000
        const poll = async () => {
          if (Date.now() > pollUntil || !session?.scenario?.id) return
          try {
            const fresh = await jiraApi.getScenarioTicket(session.scenario.id, { details: 1 })
            const fd = fresh.data || fresh
            setJiraComments(fd?.recent_comments || fd?.comments || [])
            if (fd?.ticket) setJiraTicket(fd.ticket)
            setJiraActivity(fd?.activity || [])
          } catch { /* ignore */ }
          setTimeout(poll, 4000)
        }
        setTimeout(poll, delay)
      } else {
        toast.success('Comment posted')
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to post comment')
    }
  }

  // ── ITSM ticket handlers ──
  const handleItsmTransition = async (state, extra = {}) => {
    if (!itsmTicket?.id) return
    setItsmBusy(true)
    try {
      const res = await itsmApi.transition(itsmTicket.id, state, extra)
      setItsmTicket(res.data)
      if (state === 'resolved' || state === 'closed') {
        toast.success(`Ticket ${res.data?.number} ${res.data?.state_label?.toLowerCase()}`)
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not change ticket state')
    } finally {
      setItsmBusy(false)
    }
  }

  const handleItsmTransfer = async (team, reason) => {
    if (!itsmTicket?.id) return
    setItsmBusy(true)
    try {
      const res = await itsmApi.transfer(itsmTicket.id, team, reason)
      setItsmTicket(res.data)
      toast.success(`Transferred to ${res.data?.assignment_group_label}`)
    } catch (err) {
      toast.error(err.response?.data?.error || 'Transfer failed')
    } finally {
      setItsmBusy(false)
    }
  }

  const handleItsmRaiseSubTicket = async (payload) => {
    if (!itsmTicket?.id) return
    setItsmBusy(true)
    try {
      const res = await itsmApi.raiseSubTicket(itsmTicket.id, payload)
      // The response carries the refreshed parent (with the new sub-ticket + notes).
      if (res.data?.parent) setItsmTicket(res.data.parent)
      const dev = res.data?.sub_ticket?.action_result?.device
      if (dev) {
        toast.success(`Storage attached ${dev}. Run a SCSI rescan (or reboot) on the server to see it.`, { duration: 7000 })
      } else {
        toast.success(`Sub-ticket ${res.data?.sub_ticket?.number} raised to the team`)
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not raise sub-ticket')
    } finally {
      setItsmBusy(false)
    }
  }

  const handleValidate = async () => {
    setValidating(true)
    try {
      const result = await labApi.validateLab(sessionId)
      setValidationResult(result)
      setSidebarTab('result')
      setSidebarOpen(true)
      if (result.passed) {
        toast.success(result.message || `Challenge solved! Score: ${result.score}`, { duration: 6000 })
        stopTimer()
        if (labChannelRef.current) {
          labChannelRef.current.postMessage({
            type: 'lab_stopped',
            sessionId,
            reason: 'completed',
            closingDelayMs: LAB_CLOSE_SECONDS * 1000,
          })
        }
        const slug = session?.scenario?.slug || session?.scenario_detail?.slug || ''
        scheduleLabClose(result, slug)
        if (session?.scenario?.id) {
          import('../api/jira').then(({ jiraApi }) =>
            jiraApi.getScenarioTicket(session.scenario.id, { details: 1 })
              .then(res => {
                setJiraComments(res.data?.recent_comments || [])
                setJiraActivity(res.data?.activity || [])
                if (res.data?.ticket) setJiraTicket(res.data.ticket)
              })
              .catch(() => {})
          )
        }
      } else {
        toast('Validation failed. Keep trying!', { icon: '🔍', ...TOAST })
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Validation error')
    } finally { setValidating(false) }
  }

  const handleRevealHint = async () => {
    try {
      const result = interviewMode || hints.interview_mode
        ? await labApi.revealAiHint(sessionId)
        : await labApi.revealHint(sessionId)
      setHints(prev => ({
        ...prev,
        revealed: [...prev.revealed, result.hint],
        hints_used: result.hints_used,
        next_available: result.hints_used < (result.total_hints ?? prev.total_hints),
        total_hints: result.total_hints ?? prev.total_hints,
      }))
    } catch (err) {
      const code = err.response?.data?.code
      if (code === 'INTERVIEW_MODE') {
        setInterviewMode(true)
        toast('Use AI coaching hints in interview mode', { icon: '🎯', ...TOAST })
      } else {
        toast.error(err.response?.data?.error || 'No more hints')
      }
    }
  }

  const handleExtendLab = async () => {
    if (extending) return
    setExtending(true)
    try {
      const res = await labApi.extendLab(sessionId)
      setExtensionsUsed(res.extensions_used)
      startTimer(res.time_remaining, async () => {
        await labApi.stopLab(sessionId)
        clearSession()
        navigate(techSlugRef.current ? `/technologies/${techSlugRef.current}` : '/scenarios')
      })
      toast.success(`+30 min added. ${res.extensions_remaining} extension${res.extensions_remaining !== 1 ? 's' : ''} remaining today.`)
    } catch (err) {
      toast.error(err.response?.data?.error || 'Extension unavailable')
    } finally {
      setExtending(false)
    }
  }

  const handleAiHint = async () => {
    setAiHintLoading(true)
    try {
      const res = await api.post(`/labs/${sessionId}/ai-hint/`)
      // The endpoint returns a hint OBJECT ({content, ai_generated, order, penalty})
      // for the no-question path and a string `answer` for typed questions —
      // normalize to a string so React never tries to render the raw object.
      const h = res.data.hint
      setAiHint(typeof h === 'string' ? h : (h?.content ?? h?.answer ?? res.data.answer ?? ''))
      if (res.data.credits_remaining != null) {
        setAiCreditsRemaining(res.data.credits_remaining)
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'AI hint unavailable')
    } finally {
      setAiHintLoading(false)
    }
  }

  const handleRatingSubmit = async (starValue) => {
    if (ratingSubmitting || hasRated) return
    setRating(starValue)
    setRatingSubmitting(true)
    try {
      const scenarioId = session?.scenario?.id || session?.scenario_detail?.id
      await ratingsApi.submitRating({ ratingType: 'scenario', scenario: scenarioId, score: starValue, review: '' })
      setHasRated(true)
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to submit rating')
    } finally {
      setRatingSubmitting(false)
    }
  }

  const handleStop = async () => {
    setStopping(true)
    try {
      const result = await labApi.stopLab(sessionId)
      clearSession()
      stopTimer()

      // Broadcast to other tabs that this lab was stopped
      if (labChannelRef.current) {
        labChannelRef.current.postMessage({ type: 'lab_stopped', sessionId, reason: 'stopped' })
      }

      // For cloud labs, wait until the EC2/DO instance is fully terminated
      if (result?.is_cloud) {
        toast('Terminating cloud server — please wait...', { icon: '☁️', duration: 5000, ...TOAST })
        const maxWait = 30 // max 30 seconds polling
        const start = Date.now()
        while ((Date.now() - start) / 1000 < maxWait) {
          await new Promise(r => setTimeout(r, 2000))
          try {
            const labs = await labApi.getActiveLabs()
            const lab = labs.find(l => l.id === sessionId)
            // Session gone or terminated — done
            if (!lab || lab.status === 'TERMINATED') break
          } catch {
            break // If API fails, just exit
          }
        }
      }

      const stopDest = techSlugRef.current ? `/technologies/${techSlugRef.current}` : '/scenarios'
      toast.success('Lab stopped successfully')
      navigate(stopDest)
    } catch {
      toast.error('Failed to stop lab')
      navigate(techSlugRef.current ? `/technologies/${techSlugRef.current}` : '/scenarios')
    } finally {
      setStopping(false)
      setShowStopConfirm(false)
    }
  }

  const scenario = session?.scenario_detail || session?.scenario || {}
  // Keep the technology slug in a ref so async/cross-tab handlers (which don't
  // re-subscribe on session changes) can route back to the technology page.
  techSlugRef.current = scenario?.technology?.slug || techSlugRef.current
  const labHosts = session?.lab_hosts || []
  const blockedCmds = useMemo(
    () => (Array.isArray(scenario.blocked_commands) ? scenario.blocked_commands : []),
    [scenario.blocked_commands],
  )
  const terminalSession = useMemo(() => {
    if (!session || session.status !== 'RUNNING') return null
    return {
      status: session.status,
      provider: session.provider,
      container_id: session.container_id,
      instance_id: session.instance_id,
    }
  }, [session?.status, session?.provider, session?.container_id, session?.instance_id])

  const sendSimCommand = useCallback((cmd, host) => {
    const targetHost = host || terminalHost
    const run = () => {
      const term = terminalRefs.current[targetHost]
      if (!term?.sendCommand?.(cmd)) {
        toast.error('Terminal not ready — wait for connection')
        return
      }
      toast.success(`Sent: ${cmd.split('\n')[0].slice(0, 42)}`, { duration: 2000 })
    }
    if (targetHost !== terminalHost) {
      setTerminalHost(targetHost)
      setTimeout(run, 450)
    } else {
      run()
    }
  }, [terminalHost])

  if (loading || provisioning) {
    const cloudSteps = [
      { label: 'Launching cloud server', done: provisioningStep >= 1 },
      { label: 'Booting operating system', done: provisioningStep >= 2 },
      { label: 'Installing packages & tools', done: provisioningStep >= 3 },
      { label: 'Setting up broken scenario', done: provisioningStep >= 4 },
      { label: 'Starting terminal session', done: provisioningStep >= 5 },
    ]
    const dockerSteps = [
      { label: 'Creating isolated container', done: provisioningStep >= 1 },
      { label: 'Setting up broken scenario', done: provisioningStep >= 2 },
      { label: 'Starting terminal session', done: provisioningStep >= 3 },
    ]
    const steps = isCloudLab ? cloudSteps : dockerSteps

    return (
    <div className="flex items-center justify-center h-screen bg-surface-950">
      <div className="text-center max-w-sm">
        <div className="relative mb-6">
          <div className="w-20 h-20 border-4 border-accent-cyan/20 border-t-accent-cyan rounded-full animate-spin mx-auto" />
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-accent-cyan to-brand-600 flex items-center justify-center">
              <span className="text-white font-bold text-lg">F</span>
            </div>
          </div>
        </div>
        <h2 className="text-xl font-bold text-white mb-2">
          {provisioning
            ? (isCloudLab ? 'Launching Cloud Server' : 'Preparing Lab Environment')
            : 'Connecting to Lab...'}
        </h2>
        {provisioning && isCloudLab && (
          <p className="text-sm text-accent-cyan mb-4">
            Please wait — cloud servers take 60–90 seconds to boot
          </p>
        )}
        <div className="space-y-3 mt-6">
          {steps.map((step, i) => {
            const isActive = !step.done && (i === 0 || steps[i - 1]?.done)
            return (
            <div key={i} className={`flex items-center gap-3 px-4 py-2 rounded-lg transition-all ${
              step.done ? 'bg-accent-green/10 border border-accent-green/20' : isActive ? 'bg-surface-800/80 border border-accent-cyan/30' : 'bg-surface-800/50 border border-surface-700/50'
            }`}>
              {step.done ? (
                <CheckCircle2 size={16} className="text-accent-green shrink-0" />
              ) : isActive ? (
                <div className="w-4 h-4 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin shrink-0" />
              ) : (
                <div className="w-4 h-4 rounded-full border border-surface-600 shrink-0" />
              )}
              <span className={`text-sm ${step.done ? 'text-accent-green' : isActive ? 'text-white' : 'text-surface-500'}`}>
                {step.label}
              </span>
            </div>
          )})}
        </div>
        {provisioning && (
          <p className="text-xs text-surface-500 mt-6">
            {isCloudLab
              ? `Elapsed: ${provisioningElapsed}s — this usually takes 60–90 seconds`
              : 'This usually takes 5–15 seconds...'}
          </p>
        )}
      </div>
    </div>
  )}

  const useDualPane = Boolean(scenario.dual_terminal && labHosts.length >= 2)
  const dualHosts = useDualPane ? labHosts.slice(0, 2) : []
  const isSimulationLab = session?.provider === 'simulation' || scenario.lab_mode === 'simulation'
  // Cross-technology labs (shared server in both VMware + terminal) open the Linux
  // terminal but expose an "Open VMware" link so the hypervisor-side step can be
  // performed in the SAME lab session.
  const isCrossTech = Boolean(scenario?.cross_technology)
  const isVmwareLab = !isCrossTech && (
    scenario?.technology?.slug === 'vmware'
    || scenario?.simulation_type === 'vmware'
  )
  // Monitoring labs (Grafana + Prometheus) open the in-app observability
  // simulator inline (login gate → dashboards/panels/alerts + PromQL), the same
  // way prompt/coding labs open their own surface. No dedicated route needed.
  const monitoringSimType = ['grafana', 'prometheus', 'monitoring'].includes(scenario?.simulation_type)
  const monitoringTech = ['grafana', 'prometheus'].includes(scenario?.technology?.slug)
  const isMonitoringLab = !isCrossTech && (monitoringSimType || monitoringTech)
  const monitoringFlavor = (scenario?.simulation_type === 'prometheus' || scenario?.technology?.slug === 'prometheus')
    ? 'prometheus' : 'grafana'
  // coding_mode scenarios open a browser surface instead of a terminal. Prompt
  // Engineering lessons reuse coding_mode with coding_kind/coding_spec.kind ===
  // 'prompt' to open the PromptPlayground; everything else opens the code IDE.
  // Mirrors the vmware detection above.
  const promptKind = scenario?.coding_kind === 'prompt'
    || scenario?.coding_spec?.kind === 'prompt'
    || scenario?.technology?.slug === 'prompt-engineering'
  const isPromptLab = Boolean(scenario?.coding_mode) && promptKind
  const isCodingLab = Boolean(scenario?.coding_mode) && !isPromptLab

  const labUnavailable = session && !['RUNNING', 'PROVISIONING'].includes(session.status)

  if (labUnavailable) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center p-6">
        <div className="max-w-md text-center glass-card p-8 space-y-4">
          <XCircle size={40} className="text-accent-red mx-auto" />
          <h1 className="text-xl font-bold text-white">Lab environment is not available</h1>
          <p className="text-surface-400 text-sm">
            This lab session is {session.status?.toLowerCase() || 'unavailable'}. The terminal cannot be opened.
            Please contact support if you believe this is an error.
          </p>
          <Link to="/contact" className="btn-primary inline-block">Contact support</Link>
          <Link to={`/scenarios/${scenario?.slug || ''}`} className="block text-sm text-accent-cyan hover:underline mt-2">
            Back to scenario
          </Link>
        </div>
      </div>
    )
  }

  const remoteSshTargets = labHosts.filter(h => h.ip && h.name !== 'primary' && h.name !== 'ssh_client')
  const hasSshClient = labHosts.some(h => h.name === 'ssh_client')
  const openSshClient = (host) => {
    if (!hasSshClient) {
      toast.error('SSH client not available for this lab', TOAST)
      return
    }
    setSshClientTarget(host)
    setTerminalHost('ssh_client')
    toast(`SSH client terminal — connect with: ssh ${host.ssh_user || 'root'}@${host.ip}`, { ...TOAST, duration: 8000 })
  }
  const solved = validationResult?.passed
  const expired = validationResult?.expired

  // The CodingIDE grades on the backend through the SAME completion path as
  // ValidateLabView, so when it reports solved the scenario is already complete.
  // Here we only run the post-completion UI (toast, timer stop, lab close) —
  // mirroring handleValidate's success branch without re-validating.
  const handleCodingSolved = (result) => {
    setValidationResult(result)
    setSidebarTab('result')
    stopTimer()
    if (labChannelRef.current) {
      labChannelRef.current.postMessage({
        type: 'lab_stopped', sessionId, reason: 'completed',
        closingDelayMs: LAB_CLOSE_SECONDS * 1000,
      })
    }
    const slug = session?.scenario?.slug || session?.scenario_detail?.slug || ''
    scheduleLabClose(result, slug)
  }

  // ── Prompt Engineering layout (rule-based AI practice console, free) ──
  if (isPromptLab) {
    return (
      <div className="fixed inset-0 sm:relative flex flex-col bg-surface-950 sm:min-h-[100dvh] sm:h-[100dvh] z-20">
        <div className="shrink-0 flex items-center justify-between px-4 py-2 bg-surface-900 border-b border-surface-700/50">
          <div className="flex items-center gap-3 min-w-0">
            <Sparkles size={15} className="text-accent-purple shrink-0" />
            <h2 className="text-sm font-semibold text-white truncate max-w-[280px]">
              {scenario.title || 'Prompt Engineering'}
            </h2>
            {scenario.difficulty && <span className={`badge-${scenario.difficulty} text-[10px] py-0`}>{scenario.difficulty}</span>}
          </div>
          <div className="flex items-center gap-2">
            <LabTimerBadge variant="desktop" />
            <button
              onClick={() => setShowStopConfirm(true)}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-red-500/30 text-red-400 bg-red-500/10 hover:bg-red-500/20 text-xs"
            >
              <StopCircle size={13} /> Stop
            </button>
          </div>
        </div>
        {closingIn != null && (
          <div className="shrink-0 px-4 py-2 bg-accent-green/15 border-b border-accent-green/30 text-center text-sm text-accent-green font-medium animate-pulse">
            Lesson complete — closing in {closingIn}s…
          </div>
        )}
        <PromptPlayground
          sessionId={sessionId}
          scenario={scenario}
          solved={solved}
          onSolved={handleCodingSolved}
        />
        <ConfirmDialog
          open={showStopConfirm}
          onClose={() => !stopping && setShowStopConfirm(false)}
          title={stopping ? 'Stopping Lab...' : 'Exit Lesson?'}
          message={stopping ? 'Closing the practice console...' : 'Are you sure you want to exit? Your progress in this lesson will be lost.'}
          confirmLabel={stopping ? 'Exiting...' : 'Exit Lesson'}
          danger
          onConfirm={handleStop}
          loading={stopping}
        />
      </div>
    )
  }

  // ── Coding IDE layout (browser editor instead of terminal) ──
  if (isCodingLab) {
    return (
      <div className="fixed inset-0 sm:relative flex flex-col bg-surface-950 sm:min-h-[100dvh] sm:h-[100dvh] z-20">
        <div className="shrink-0 flex items-center justify-between px-4 py-2 bg-surface-900 border-b border-surface-700/50">
          <div className="flex items-center gap-3 min-w-0">
            <h2 className="text-sm font-semibold text-white truncate max-w-[280px]">
              {scenario.title || 'Coding Challenge'}
            </h2>
            {scenario.difficulty && <span className={`badge-${scenario.difficulty} text-[10px] py-0`}>{scenario.difficulty}</span>}
            {session?.jira_issue_key && (
              <JiraTicketLink
                issueKey={session.jira_issue_key}
                issueUrl={session.jira_issue_url || `/jira/${session.jira_issue_key}`}
                className="text-[10px]"
              />
            )}
          </div>
          <div className="flex items-center gap-2">
            <LabTimerBadge variant="desktop" />
            <button
              onClick={() => setShowStopConfirm(true)}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-red-500/30 text-red-400 bg-red-500/10 hover:bg-red-500/20 text-xs"
            >
              <StopCircle size={13} /> Stop
            </button>
          </div>
        </div>
        {closingIn != null && (
          <div className="shrink-0 px-4 py-2 bg-accent-green/15 border-b border-accent-green/30 text-center text-sm text-accent-green font-medium animate-pulse">
            Challenge solved — lab is closing in {closingIn}s…
          </div>
        )}
        <CodingIDE
          sessionId={sessionId}
          scenario={scenario}
          solved={solved}
          onSolved={handleCodingSolved}
        />
        <ConfirmDialog
          open={showStopConfirm}
          onClose={() => !stopping && setShowStopConfirm(false)}
          title={stopping ? 'Stopping Lab...' : 'Stop Lab?'}
          message={stopping ? 'Stopping lab environment...' : 'Are you sure you want to stop? Your progress will be lost.'}
          confirmLabel={stopping ? 'Stopping...' : 'Stop Lab'}
          danger
          onConfirm={handleStop}
          loading={stopping}
        />
      </div>
    )
  }

  return (
    <div className="fixed inset-0 sm:relative flex flex-col bg-surface-950 sm:min-h-[100dvh] sm:h-[100dvh] z-20">
      {/* Mobile top bar */}
      <div className="sm:hidden flex items-center justify-between px-3 py-2 bg-surface-900 border-b border-surface-700/50 shrink-0">
        <button onClick={() => { setSidebarTab('instructions'); setSidebarOpen(true) }} className="p-1.5 text-surface-400">
          <PanelLeftOpen size={18} />
        </button>
        <p className="text-xs font-semibold text-white truncate flex-1 text-center px-2">{scenario.title || 'Lab'}</p>
        <LabTimerBadge variant="mobile-bar" />
      </div>
      {closingIn != null && (
        <div className="shrink-0 px-4 py-2 bg-accent-green/15 border-b border-accent-green/30 text-center text-sm text-accent-green font-medium animate-pulse">
          Lab is closing in {closingIn}s…
        </div>
      )}
      {/* Top bar - hidden on mobile where floating bar is used */}
      <div className="hidden sm:flex items-center justify-between px-4 py-2 bg-surface-900 border-b border-surface-700/50 shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              // Opening the panel must also drop fullscreen, otherwise the
              // fullscreen rule keeps the sidebar collapsed and the toggle
              // would look dead.
              const open = !sidebarOpen
              setSidebarOpen(open)
              if (open && terminalFullscreen) setTerminalFullscreen(false)
            }}
            className="text-surface-400 hover:text-white transition-colors"
          >
            {sidebarOpen && !terminalFullscreen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
          </button>
          <h2 className="text-sm font-semibold text-white truncate max-w-[280px]">
            {scenario.title || 'Lab Session'}
          </h2>
          {scenario.difficulty && <span className={`badge-${scenario.difficulty} text-[10px] py-0`}>{scenario.difficulty}</span>}
          {session?.jira_issue_key && (
            <span
              className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 border border-blue-500/20"
              title="Your incident ticket — see sidebar for details"
            >
              <JiraTicketLink
                issueKey={session.jira_issue_key}
                issueUrl={session.jira_issue_url || `/jira/${session.jira_issue_key}`}
                className="text-[10px]"
              />
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <LabTimerBadge variant="desktop" />
          <button onClick={() => setShowShortcuts(true)} className="p-2 text-surface-400 hover:text-white" title="Keyboard shortcuts">
            <Keyboard size={16} />
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden relative">
        {isMobile && sidebarOpen && (
          <button type="button" className="fixed inset-0 bg-black/50 z-30 lg:hidden" onClick={() => setSidebarOpen(false)} aria-label="Close sidebar" />
        )}
        <div className={`${
          isMobile
            ? `fixed inset-y-0 left-0 z-40 w-80 max-w-[85vw] transform transition-transform ${sidebarOpen && !terminalFullscreen ? 'translate-x-0' : '-translate-x-full'}`
            : `${sidebarOpen && !terminalFullscreen ? 'w-80' : 'w-0'} transition-all duration-300`
        } overflow-hidden border-r border-surface-700/50 bg-surface-900 shrink-0`}
        >
          <div className="w-80 h-full flex flex-col">
            {/* Tabs */}
            <div className="flex border-b border-surface-800">
              {[
                { key: 'instructions', label: 'Info', icon: FileText },
                ...(scenario?.itsm_enabled ? [{ key: 'ticket', label: 'Ticket', icon: TicketIcon }] : []),
                { key: 'hints', label: 'Hints', icon: Lightbulb },
                { key: 'result', label: 'Result', icon: Target },
              ].map(({ key, label, icon: Icon }) => (
                <button
                  key={key}
                  onClick={() => setSidebarTab(key)}
                  className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors ${
                    sidebarTab === key
                      ? 'text-accent-cyan border-b-2 border-accent-cyan'
                      : 'text-surface-500 hover:text-surface-300'
                  }`}
                ><Icon size={12} /> {label}</button>
              ))}
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Instructions tab */}
              {sidebarTab === 'instructions' && (
                <>
                  {session?.jira_issue_key && (
                    <JiraTicketPanel
                      compact
                      labInfoMode
                      hideHistory
                      hideComments
                      hideStatus
                      ticket={jiraTicket || {
                        issue_key: session.jira_issue_key,
                        issue_url: session.jira_issue_url,
                        run_count: session.jira_run_count || 1,
                      }}
                    />
                  )}
                  <div>
                    <h3 className="text-xs font-semibold text-surface-400 uppercase tracking-wider mb-2">Description</h3>
                    <p className="text-sm text-surface-300 leading-relaxed">{scenario.description || 'Fix the broken server.'}</p>
                  </div>
                  {scenario.objectives && scenario.objectives.length > 0 && (
                    <div>
                      <h3 className="text-xs font-semibold text-surface-400 uppercase tracking-wider mb-2">Expected outcome</h3>
                      {Array.isArray(scenario.objectives) ? (
                        <ul className="space-y-1.5">
                          {scenario.objectives.map((obj, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-surface-300">
                              <Target size={12} className="text-accent-cyan mt-0.5 shrink-0" />
                              <span>{typeof obj === 'string' ? obj : JSON.stringify(obj)}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-sm text-surface-300 whitespace-pre-wrap">{scenario.objectives}</p>
                      )}
                    </div>
                  )}
                  {scenario.initial_state && (
                    <div>
                      <h3 className="text-xs font-semibold text-surface-400 uppercase tracking-wider mb-2">Initial State</h3>
                      <div className="bg-surface-950 rounded p-3 text-xs font-mono text-surface-400 whitespace-pre-wrap border border-surface-800">
                        {scenario.initial_state}
                      </div>
                    </div>
                  )}

                  {(scenario.lab_mode === 'simulation' || session?.provider === 'simulation') && (
                    <>
                      <SimLabTips scenario={scenario} />
                      <DevOpsNetworkingSimToolkit scenario={scenario} onRunCommand={sendSimCommand} />
                    </>
                  )}

                  {/* Reminder to stop lab */}
                  <div className="mt-4 bg-accent-amber/5 border border-accent-amber/20 rounded-lg p-3">
                    <div className="flex items-start gap-2">
                      <StopCircle size={14} className="text-accent-amber mt-0.5 shrink-0" />
                      <div>
                        <p className="text-xs font-medium text-accent-amber">Please stop the lab once you are done</p>
                        <p className="text-[11px] text-surface-500 mt-0.5">Click the "Stop" button when finished to free up resources. Labs auto-terminate after the time limit expires.</p>
                      </div>
                    </div>
                  </div>
                </>
              )}

              {/* ITSM (ServiceNow-style) ticket tab */}
              {sidebarTab === 'ticket' && (
                <>
                  {itsmTicket ? (
                    <ItsmTicketPanel
                      ticket={itsmTicket}
                      meta={itsmMeta}
                      config={itsmConfig}
                      busy={itsmBusy}
                      onTransition={handleItsmTransition}
                      onTransfer={handleItsmTransfer}
                      onRaiseSubTicket={handleItsmRaiseSubTicket}
                    />
                  ) : (
                    <div className="text-center py-8 text-surface-500">
                      <TicketIcon size={28} className="mx-auto mb-2 opacity-40" />
                      <p className="text-sm">Opening your ServiceNow ticket…</p>
                      <p className="text-[11px] mt-1">If this persists, a subscription to this technology may be required.</p>
                    </div>
                  )}
                  <div className="mt-3 bg-accent-cyan/5 border border-accent-cyan/20 rounded-lg p-3">
                    <p className="text-[11px] text-surface-400 leading-relaxed">
                      <span className="font-medium text-surface-300">How this works:</span> raise a sub-ticket to an
                      assisting team (e.g. Storage for a disk). The team actions it and the change lands on this
                      server — for a disk, run a SCSI rescan (<code className="text-accent-cyan">echo "- - -" &gt; /sys/class/scsi_host/host0/scan</code>)
                      or reboot to see the new <code className="text-accent-cyan">/dev/sdX</code>, then continue your fix.
                    </p>
                  </div>
                </>
              )}

              {/* Hints tab */}
              {sidebarTab === 'hints' && (
                <>
                  {interviewMode && (
                    <div className="mb-4 p-3 rounded-lg bg-accent-purple/10 border border-accent-purple/20">
                      <p className="text-xs font-semibold text-accent-purple flex items-center gap-1.5">
                        <Sparkles size={12} /> Interview mode
                      </p>
                      <p className="text-[11px] text-surface-400 mt-1">
                        Standard hints are disabled. AI coaching gives directional guidance without spoilers.
                      </p>
                    </div>
                  )}
                  {hints.revealed.length > 0 ? (
                    <div className="space-y-3">
                      {hints.revealed.map((hint) => (
                        <div key={hint.order} className="bg-surface-800 rounded-lg p-3 border border-accent-amber/10">
                          <div className="flex items-center gap-2 mb-1.5">
                            <Lightbulb size={12} className="text-accent-amber" />
                            <span className="text-xs font-semibold text-accent-amber">Hint {hint.order}</span>
                            <span className="text-[10px] text-surface-600">(-{hint.penalty} pts)</span>
                          </div>
                          <p className="text-sm text-surface-300 leading-relaxed">{hint.content}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <Lightbulb size={24} className="mx-auto text-surface-700 mb-2" />
                      <p className="text-sm text-surface-500">No hints revealed yet</p>
                      <p className="text-xs text-surface-600 mt-1">Each hint costs points from your score</p>
                    </div>
                  )}

                  {(hints.next_available || interviewMode) && hints.hints_used < (hints.total_hints || 5) && (
                    <button
                      onClick={handleRevealHint}
                      className="w-full py-2.5 rounded-lg text-sm font-medium bg-accent-amber/10 text-accent-amber border border-accent-amber/20 hover:bg-accent-amber/20 transition-all"
                    >
                      {interviewMode ? 'Get AI Coaching Hint' : 'Reveal Next Hint'}
                    </button>
                  )}

                  {!hints.next_available && !interviewMode && hints.total_hints > 0 && (
                    <p className="text-xs text-surface-600 text-center">All hints revealed</p>
                  )}

                  {/* Ask AI coaching hint */}
                  <div className="mt-4 rounded-lg p-px" style={{ background: 'linear-gradient(135deg, #06b6d4, #8b5cf6, #06b6d4)' }}>
                    <div className="rounded-[7px] bg-surface-900 p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-semibold text-accent-cyan flex items-center gap-1.5">
                          <Sparkles size={12} /> AI Coaching
                        </span>
                        {aiCreditsRemaining != null && (
                          <span className="text-[10px] text-surface-500">{aiCreditsRemaining} credits left</span>
                        )}
                      </div>
                      <p className="text-[11px] text-surface-400 mb-2.5">
                        Get a personalized coaching nudge without revealing the full solution.
                        {aiCreditsRemaining == null && <span className="text-surface-500"> (costs 1 credit)</span>}
                      </p>
                      {aiHint ? (
                        <div className="rounded-md bg-accent-cyan/5 border border-accent-cyan/20 p-2.5 text-xs text-surface-200 leading-relaxed whitespace-pre-wrap">
                          {aiHint}
                        </div>
                      ) : null}
                      <button
                        onClick={handleAiHint}
                        disabled={aiHintLoading}
                        className="mt-2.5 w-full py-2 rounded-md text-xs font-medium text-white disabled:opacity-50 flex items-center justify-center gap-1.5"
                        style={{ background: 'linear-gradient(135deg, #0891b2, #7c3aed)' }}
                      >
                        {aiHintLoading ? (
                          <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        ) : (
                          <Sparkles size={12} />
                        )}
                        {aiHint ? 'Ask Again' : 'Ask AI'}
                      </button>
                    </div>
                  </div>
                </>
              )}

              {/* Result tab */}
              {sidebarTab === 'result' && (
                <>
                  {!validationResult ? (
                    <div className="text-center py-8">
                      <Target size={24} className="mx-auto text-surface-700 mb-2" />
                      <p className="text-sm text-surface-500">Click "Check Solution" when ready</p>
                    </div>
                  ) : validationResult.passed ? (
                    <div className="space-y-4">
                      <div className="text-center py-4">
                        <div className="w-16 h-16 rounded-full bg-accent-green/10 border-2 border-accent-green/30 flex items-center justify-center mx-auto mb-3">
                          <Sparkles size={28} className="text-accent-green" />
                        </div>
                        <h3 className="text-lg font-bold text-accent-green mb-1">Challenge Solved!</h3>
                        <p className="text-sm text-surface-400">{validationResult.message}</p>
                        {closingIn != null && (
                          <p className="text-sm text-accent-amber mt-2 font-medium">
                            Lab is closing in {closingIn} seconds…
                          </p>
                        )}
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                          <Trophy size={16} className="text-accent-amber mx-auto mb-1" />
                          <p className="text-xl font-bold text-accent-amber">{validationResult.score}</p>
                          <p className="text-[10px] text-surface-500 uppercase">Score</p>
                        </div>
                        <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                          <Timer size={16} className="text-accent-cyan mx-auto mb-1" />
                          <p className="text-xl font-bold text-white">
                            {validationResult.time_taken ? `${Math.floor(validationResult.time_taken / 60)}m ${validationResult.time_taken % 60}s` : '—'}
                          </p>
                          <p className="text-[10px] text-surface-500 uppercase">Time</p>
                        </div>
                      </div>

                      {validationResult.output && (
                        <div>
                          <h4 className="text-xs font-semibold text-surface-400 uppercase mb-1">Output</h4>
                          <pre className="text-xs text-accent-green bg-surface-950 rounded p-3 overflow-x-auto whitespace-pre-wrap border border-surface-800">
                            {validationResult.output}
                          </pre>
                        </div>
                      )}

                      {validationResult.jira_pending_close && session?.jira_issue_key && (
                        <div className="border-t border-surface-800 pt-4">
                          <JiraTicketPanel
                            compact
                            ticket={jiraTicket || { issue_key: session.jira_issue_key, issue_url: session.jira_issue_url }}
                            comments={jiraComments}
                            onTransition={handleJiraTransition}
                            onComment={handleJiraComment}
                            transitioning={jiraTransitioning}
                          />
                        </div>
                      )}

                      {/* Scenario star rating */}
                      <div className="border-t border-surface-800 pt-4">
                        {hasRated ? (
                          <p className="text-xs text-accent-green text-center font-medium">Thanks for your rating!</p>
                        ) : (
                          <div>
                            <p className="text-xs text-surface-400 text-center mb-2">Rate this scenario</p>
                            <div className="flex items-center justify-center gap-1">
                              {[1, 2, 3, 4, 5].map((star) => (
                                <button
                                  key={star}
                                  type="button"
                                  disabled={ratingSubmitting}
                                  onClick={() => handleRatingSubmit(star)}
                                  onMouseEnter={() => setRatingHover(star)}
                                  onMouseLeave={() => setRatingHover(0)}
                                  className="text-2xl leading-none transition-transform hover:scale-110 disabled:opacity-50"
                                  aria-label={`Rate ${star} star${star !== 1 ? 's' : ''}`}
                                >
                                  <span className={star <= (ratingHover || rating) ? 'text-accent-amber' : 'text-surface-700'}>
                                    ★
                                  </span>
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {validationResult.solution && (
                        <div className="border-t border-surface-800 pt-4">
                          <h4 className="text-xs font-semibold text-accent-green uppercase mb-2 flex items-center gap-1">
                            <Eye size={12} /> Solution Explanation
                          </h4>
                          <p className="text-sm text-surface-300 leading-relaxed whitespace-pre-wrap">
                            {validationResult.solution}
                          </p>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="text-center py-4">
                        <div className="w-16 h-16 rounded-full bg-accent-red/10 border-2 border-accent-red/30 flex items-center justify-center mx-auto mb-3">
                          <XCircle size={28} className="text-accent-red" />
                        </div>
                        <h3 className="text-lg font-bold text-accent-red mb-1">
                          {validationResult.expired ? 'Time Expired' : 'Not Quite'}
                        </h3>
                        <p className="text-sm text-surface-400">
                          {validationResult.expired
                            ? 'Time ran out. Review the solution below.'
                            : 'Check the output below and keep trying.'}
                        </p>
                      </div>
                      {validationResult.output && !validationResult.expired && (
                        <pre className="text-xs text-accent-red bg-surface-950 rounded p-3 overflow-x-auto whitespace-pre-wrap border border-surface-800">
                          {validationResult.output}
                        </pre>
                      )}
                      {validationResult.solution && (
                        <div className="border-t border-surface-800 pt-4">
                          <h4 className="text-xs font-semibold text-accent-amber uppercase mb-2 flex items-center gap-1">
                            <Eye size={12} /> Solution
                          </h4>
                          <p className="text-sm text-surface-300 leading-relaxed whitespace-pre-wrap">
                            {validationResult.solution}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden relative">
        {/* Fullscreen restore tab — collapses the side panel and lets the lab
            fill the width. Click to exit fullscreen and bring the panel back. */}
        {terminalFullscreen && !isMobile && (
          <button
            type="button"
            onClick={() => { setTerminalFullscreen(false); setSidebarOpen(true) }}
            title="Exit fullscreen — show side panel"
            aria-label="Exit fullscreen and show side panel"
            className="absolute left-0 top-1/2 -translate-y-1/2 z-30 flex items-center gap-1 pl-1 pr-2 py-3 rounded-r-lg bg-surface-800/90 border border-l-0 border-surface-600 text-surface-300 hover:text-accent-cyan hover:border-accent-cyan shadow-lg backdrop-blur-sm"
          >
            <ChevronRight size={16} />
          </button>
        )}
        {/* Terminal action bar — above xterm */}
        <div className="shrink-0 flex flex-wrap items-center gap-1.5 sm:gap-2 px-2 py-2 bg-surface-900 border-b border-surface-800 text-[10px] sm:text-xs">
          {useDualPane && (
            <span className="text-accent-purple font-medium mr-1">Dual terminal</span>
          )}
          {isVmwareLab && (
            <Link
              to={`/vmware/${sessionId}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-[#4fa7e8]/40 text-[#4fa7e8] bg-[#4fa7e8]/10 hover:bg-[#4fa7e8]/20 text-[10px] font-medium"
            >
              <ExternalLink size={12} /> vCenter Simulator
            </Link>
          )}
          {isCrossTech && (scenario?.vmware_link !== false) && (
            <Link
              to={`/vmware/${sessionId}?scenario=${scenario?.slug || ''}`}
              target="_blank"
              rel="noopener noreferrer"
              title="This server also lives in VMware. Open the vCenter simulator to perform the hypervisor-side step (e.g. add a disk), then return here and rescan/reboot."
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-[#4fa7e8]/50 text-[#4fa7e8] bg-[#4fa7e8]/10 hover:bg-[#4fa7e8]/20 text-[10px] font-semibold"
            >
              <ExternalLink size={12} /> Open VMware (same server)
            </Link>
          )}
          {isMonitoringLab && (
            <button
              type="button"
              onClick={() => setShowMonitoringSim(true)}
              title="Open the in-app Grafana + Prometheus simulator to investigate dashboards, panels, targets, alert rules, and run PromQL. Apply the fix in the terminal, then Check Solution."
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md border text-[10px] font-semibold"
              style={{ borderColor: `${monitoringFlavor === 'prometheus' ? '#e6522c' : '#f7913b'}66`,
                       color: monitoringFlavor === 'prometheus' ? '#e6522c' : '#f7913b',
                       background: `${monitoringFlavor === 'prometheus' ? '#e6522c' : '#f7913b'}1a` }}
            >
              <ExternalLink size={12} /> Open {monitoringFlavor === 'prometheus' ? 'Prometheus' : 'Grafana'}
            </button>
          )}
          {isSimulationLab && (
            <>
              <SimLabQuickActions
                scenario={scenario}
                labHosts={labHosts}
                activeHost={terminalHost}
                onSendCommand={sendSimCommand}
              />
              <button
                type="button"
                onClick={() => setShowSimWizard(true)}
                className="inline-flex items-center gap-1 px-2 py-1.5 rounded-md border border-indigo-500/30 bg-indigo-500/10 text-indigo-300 hover:bg-indigo-500/20 text-[10px] font-medium"
                title="Step-by-step disk, NIC, SSH, firewall, and MySQL wizards"
              >
                <Wand2 size={12} /> Wizards
              </button>
            </>
          )}
          {!useDualPane && labHosts.length > 1 && (
            <span className="text-surface-500 mr-0.5 hidden sm:inline">Shell:</span>
          )}
          {!useDualPane && (labHosts.length > 0 ? labHosts : [{ name: 'primary', role: 'Primary' }]).map(h => (
            <button
              key={h.name}
              type="button"
              onClick={() => {
                if (h.name !== terminalHost) {
                  setTerminalHost(h.name)
                  if (h.name !== 'ssh_client') setSshClientTarget(null)
                }
              }}
              className={`px-2.5 py-1.5 rounded-md border font-medium ${terminalHost === h.name ? 'border-accent-cyan text-accent-cyan bg-accent-cyan/10' : 'border-surface-700 text-surface-400 hover:border-surface-600'}`}
            >
              {h.role === 'SSH Client' || h.name === 'ssh_client' ? 'SSH Client' : (h.role || h.name)}
            </button>
          ))}
          {remoteSshTargets.map(h => (
            <button
              key={`ssh-${h.name}`}
              type="button"
              onClick={() => openSshClient(h)}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-surface-700 text-surface-300 hover:border-accent-cyan hover:text-accent-cyan bg-surface-800/50"
              title={`Open SSH client → ssh ${h.ssh_user || 'root'}@${h.ip}`}
            >
              <Terminal size={12} /> SSH {h.role || h.name}
            </button>
          ))}
          <div className="w-px h-6 bg-surface-700 mx-0.5 hidden sm:block" />
          <button
            onClick={() => setTerminalFullscreen(p => {
              const next = !p
              // Entering fullscreen hides the side panel; exiting restores it.
              setSidebarOpen(next ? false : true)
              return next
            })}
            className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md border ${
              terminalFullscreen
                ? 'border-accent-cyan/40 text-accent-cyan bg-accent-cyan/10'
                : 'border-surface-700 text-surface-300 hover:border-accent-cyan hover:text-accent-cyan'
            }`}
            title="Toggle fullscreen — hide side panel (F)"
          >
            {terminalFullscreen ? <PanelLeftOpen size={12} /> : <Terminal size={12} />}
            {terminalFullscreen ? 'Exit Full' : 'Fullscreen'}
          </button>
          <button
            onClick={() => { setSidebarTab('hints'); setSidebarOpen(true) }}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-surface-700 text-surface-300 hover:border-accent-amber hover:text-accent-amber"
          >
            <Lightbulb size={12} /> Hints ({hints.hints_used}/{hints.total_hints})
          </button>
          <button
            onClick={handleValidate}
            disabled={validating || solved}
            className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md border font-medium disabled:opacity-50 ${
              solved ? 'border-accent-green/30 text-accent-green bg-accent-green/10' : 'border-accent-cyan/40 text-accent-cyan bg-accent-cyan/10 hover:bg-accent-cyan/20'
            }`}
          >
            {validating ? (
              <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : (
              <CheckCircle2 size={12} />
            )}
            Check
          </button>
          {extensionsUsed < 2 && (
            <button
              onClick={handleExtendLab}
              disabled={extending}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-accent-cyan/30 text-accent-cyan bg-accent-cyan/10 hover:bg-accent-cyan/20 disabled:opacity-50"
              title={`Add 30 min (${2 - extensionsUsed} left today)`}
            >
              {extending ? (
                <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
              ) : (
                <Clock size={12} />
              )}
              +30m
            </button>
          )}
          <button
            onClick={() => setShowStopConfirm(true)}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-red-500/30 text-red-400 bg-red-500/10 hover:bg-red-500/20"
          >
            <StopCircle size={12} /> Stop
          </button>
        </div>
        {/* Terminal */}
        <div className="flex-1 bg-surface-950 relative min-h-0 overflow-hidden flex flex-col pb-[calc(3.75rem+env(safe-area-inset-bottom,0px))] sm:pb-0">
          {useDualPane && !sshClientTarget && (
            <div className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-surface-800">
              {dualHosts.map(h => (
                <LabTerminal
                  key={h.name}
                  ref={(el) => { terminalRefs.current[h.name] = el }}
                  sessionId={sessionId}
                  session={terminalSession}
                  hostKey={h.name}
                  label={`${h.role || h.name} (${h.ip || 'sim'})`}
                  isMobile={isMobile}
                  blockedCommands={blockedCmds}
                  className="h-full"
                  layoutKey={sidebarOpen}
                />
              ))}
            </div>
          )}
          {!useDualPane && !sshClientTarget && (
            <LabTerminal
              key={`${sessionId}:${terminalHost}`}
              ref={(el) => { terminalRefs.current[terminalHost] = el }}
              sessionId={sessionId}
              session={terminalSession}
              hostKey={terminalHost}
              label={terminalHost !== 'primary' ? `${labHosts.find(h => h.name === terminalHost)?.role || terminalHost}` : ''}
              isMobile={isMobile}
              blockedCommands={blockedCmds}
              className="flex-1 min-h-0"
              layoutKey={sidebarOpen}
              welcomeHint={terminalHost === 'ssh_client' && sshClientTarget
                ? `Type: ssh -o StrictHostKeyChecking=no ${sshClientTarget.ssh_user || 'root'}@${sshClientTarget.ip}`
                : ''}
            />
          )}
          {sshClientTarget && (
            <div className={`${useDualPane ? 'h-[45%]' : 'flex-1'} min-h-0 border-t border-accent-cyan/30`}>
              <div className="flex items-center justify-between px-2 py-1 bg-surface-900 border-b border-surface-800">
                <span className="text-[10px] text-accent-cyan font-medium">
                  SSH Client (labuser) → {sshClientTarget.role || sshClientTarget.name}
                </span>
                <button type="button" onClick={() => setSshClientTarget(null)} className="text-[10px] text-surface-400 hover:text-white">Close</button>
              </div>
              <LabTerminal
                ref={(el) => { terminalRefs.current.ssh_client = el }}
                sessionId={sessionId}
                session={terminalSession}
                hostKey="ssh_client"
                isMobile={isMobile}
                blockedCommands={blockedCmds}
                className="h-[calc(100%-1.75rem)]"
                welcomeHint={`Type: ssh -o StrictHostKeyChecking=no ${sshClientTarget.ssh_user || 'root'}@${sshClientTarget.ip}`}
              />
            </div>
          )}
        </div>
        </div>
      </div>

      {/* Mobile: floating terminal input bar */}
      {showMobileInput && (
        <div className="sm:hidden fixed bottom-14 inset-x-0 bg-surface-950/95 border-t border-accent-cyan/30 px-3 py-2 flex gap-2 z-40 backdrop-blur-sm">
          <input
            autoFocus
            type="text"
            value={mobileInput}
            onChange={e => setMobileInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') {
                const term = terminalRefs.current[terminalHost]
                if (term?.sendCommand) { term.sendCommand(mobileInput); setMobileInput('') }
              }
            }}
            placeholder="Type command and press Enter…"
            className="flex-1 bg-surface-800 text-white text-sm rounded px-3 py-1.5 border border-surface-600 focus:border-accent-cyan focus:outline-none font-mono"
          />
          <button
            onClick={() => {
              const term = terminalRefs.current[terminalHost]
              if (term?.sendCommand) { term.sendCommand(mobileInput); setMobileInput('') }
            }}
            className="px-3 py-1.5 bg-accent-cyan text-surface-950 rounded text-sm font-medium"
          >Run</button>
          <button onClick={() => navigator.clipboard.readText().then(t => setMobileInput(prev => prev + t)).catch(() => {})}
            className="px-2 py-1.5 bg-surface-700 rounded text-surface-300 text-sm">Paste</button>
          <button onClick={() => setShowMobileInput(false)} className="p-1.5 text-surface-400">✕</button>
        </div>
      )}

      {/* Mobile: floating action bar */}
      <div className="sm:hidden fixed bottom-0 inset-x-0 bg-surface-900 border-t border-surface-700/50 px-2 py-2 flex items-center justify-around z-30 pb-[max(0.5rem,env(safe-area-inset-bottom))]">
        <LabTimerBadge variant="mobile-float" />
        <button onClick={() => { setSidebarTab('instructions'); setSidebarOpen(p => !p) }}
          className="p-2 text-surface-400 hover:text-white" aria-label="Instructions">
          <FileText size={20} />
        </button>
        <button onClick={toggleHints}
          className="p-2 text-surface-400 hover:text-accent-amber" aria-label="Hints">
          <Lightbulb size={20} />
        </button>
        {remoteSshTargets.length > 0 && (
          <button
            onClick={() => openSshClient(remoteSshTargets[0])}
            className="p-2 text-surface-400 hover:text-accent-cyan"
            aria-label="SSH client terminal"
            title={`SSH client → ${remoteSshTargets[0].ssh_user || 'root'}@${remoteSshTargets[0].ip}`}
          >
            <Terminal size={20} />
          </button>
        )}
        <button onClick={handleValidate} disabled={validating || solved}
          className="p-3 bg-accent-cyan rounded-full text-surface-950" aria-label="Check solution">
          <CheckCircle2 size={22} />
        </button>
        <button onClick={() => setShowStopConfirm(true)}
          className="p-2 text-surface-400 hover:text-accent-red" aria-label="Stop lab">
          <StopCircle size={20} />
        </button>
        <button onClick={() => setShowMobileInput(p => !p)}
          className={`p-2 ${showMobileInput ? 'text-accent-cyan' : 'text-surface-400 hover:text-white'}`}
          aria-label="Terminal input">
          <Keyboard size={20} />
        </button>
      </div>

      {/* Stop confirmation dialog */}
      <ConfirmDialog
        open={showStopConfirm}
        onClose={() => !stopping && setShowStopConfirm(false)}
        title={stopping ? "Stopping Lab..." : "Stop Lab?"}
        message={stopping
          ? (isCloudLab ? "Terminating cloud server — please wait..." : "Stopping lab environment...")
          : "Are you sure you want to stop? Your progress will be lost and the environment will be terminated."
        }
        confirmLabel={stopping ? "Stopping..." : "Stop Lab"}
        danger
        onConfirm={handleStop}
        loading={stopping}
      />

      {isSimulationLab && (
        <SimLabWizard
          open={showSimWizard}
          onClose={() => setShowSimWizard(false)}
          scenario={scenario}
          labHosts={labHosts}
          onSendCommand={sendSimCommand}
        />
      )}

      {/* Grafana / Prometheus simulator — full-screen overlay opened from the
          toolbar. The learner inspects dashboards/panels/targets/alerts + runs
          PromQL here, applies the documented config fix in the terminal, then
          runs Check Solution (which grades via check.sh, never auto-passes). */}
      {isMonitoringLab && showMonitoringSim && (
        <div className="fixed inset-0 z-[60] bg-surface-950">
          <button
            type="button"
            onClick={() => setShowMonitoringSim(false)}
            className="absolute top-3 right-3 z-[70] inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-surface-600 bg-surface-900/90 text-surface-200 hover:bg-surface-800 text-xs font-medium"
          >
            <XCircle size={14} /> Close simulator
          </button>
          <div className="h-full overflow-auto">
            <MonitoringSimulator
              sessionId={sessionId}
              scenario={scenario}
              flavor={monitoringFlavor}
              onExit={() => setShowMonitoringSim(false)}
              onHints={() => { setShowMonitoringSim(false); toggleHints() }}
              onStop={() => { setShowMonitoringSim(false); setShowStopConfirm(true) }}
            />
          </div>
        </div>
      )}

      {/* Keyboard shortcuts help */}
      {showShortcuts && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setShowShortcuts(false)}>
          <div className="glass-card p-6 max-w-xs w-full" onClick={e => e.stopPropagation()}>
            <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
              <Keyboard size={16} className="text-accent-cyan" /> Keyboard Shortcuts
            </h3>
            <div className="space-y-2.5 text-sm">
              {[
                ['V', 'Validate / Check Solution'],
                ['H', 'Show / Hide Hints Panel'],
                ['F', 'Toggle Fullscreen Terminal'],
                ['R', 'Reset Timer Display'],
                ['?', 'Show / Hide This Overlay'],
                ['Ctrl + Enter', 'Check Solution (alt)'],
                ['Escape', 'Toggle Sidebar'],
              ].map(([key, action]) => (
                <div key={key} className="flex items-center justify-between gap-4">
                  <span className="text-surface-400 text-xs">{action}</span>
                  <kbd className="shrink-0 px-2 py-0.5 bg-surface-800 border border-surface-700 rounded text-xs text-surface-200 font-mono">{key}</kbd>
                </div>
              ))}
            </div>
            <button onClick={() => setShowShortcuts(false)} className="btn-secondary w-full mt-5 text-sm">Close</button>
          </div>
        </div>
      )}
    </div>
  )
}
