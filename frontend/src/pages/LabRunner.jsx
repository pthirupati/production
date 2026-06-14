import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { labApi } from '../api/labs'
import { useLabStore } from '../store/labStore'
import { useAuthStore } from '../store/authStore'
import {
  Clock, CheckCircle2, XCircle, Lightbulb, StopCircle,
  ChevronRight, Trophy, Target, Eye, FileText,
  PanelLeftClose, PanelLeftOpen, Sparkles, Timer, Keyboard, ExternalLink, Terminal
} from 'lucide-react'
import toast from 'react-hot-toast'
import { ConfirmDialog } from '../components/ConfirmModal'
import JiraTicketPanel from '../components/JiraTicketPanel'
import JiraTicketLink from '../components/JiraTicketLink'
import LabTerminal from '../components/LabTerminal'
import useLabShortcuts from '../hooks/useLabShortcuts'
import { useIsMobile } from '../hooks/useMediaQuery'

export default function LabRunner() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const { timeRemaining, startTimer, stopTimer, clearSession } = useLabStore()

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
  const [jiraComments, setJiraComments] = useState([])
  const [jiraActivity, setJiraActivity] = useState([])
  const [jiraTicket, setJiraTicket] = useState(null)
  const [jiraTransitioning, setJiraTransitioning] = useState(false)
  const [closingIn, setClosingIn] = useState(null)
  const [terminalHost, setTerminalHost] = useState('primary')

  const terminalRef = useRef(null)
  const xtermRef = useRef(null)
  const wsRef = useRef(null)
  const fitAddonRef = useRef(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 10  // Cloud labs may need more; simulation capped in onclose handler
  const labChannelRef = useRef(null)  // BroadcastChannel for cross-tab sync
  const inputBufferRef = useRef('')   // Accumulate keystrokes to check blocked commands
  const blockedPatternsRef = useRef([]) // [{pattern: RegExp, label: string}]
  const reconnectTimerRef = useRef(null)
  const terminalSessionRef = useRef(null)
  const closeTimerRef = useRef(null)
  const closeCountdownRef = useRef(null)

  const LAB_CLOSE_SECONDS = 10

  const cleanupLabResources = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.close(1000)
      wsRef.current = null
    }
    if (xtermRef.current) {
      xtermRef.current.dispose()
      xtermRef.current = null
    }
    clearSession()
    stopTimer()
  }, [clearSession, stopTimer])

  const scheduleLabClose = useCallback((result, slug) => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current)
    if (closeCountdownRef.current) clearInterval(closeCountdownRef.current)

    setClosingIn(LAB_CLOSE_SECONDS)
    toast(`Lab is closing in ${LAB_CLOSE_SECONDS} seconds…`, { icon: '⏳', duration: LAB_CLOSE_SECONDS * 1000 })

    closeCountdownRef.current = setInterval(() => {
      setClosingIn(prev => (prev != null && prev > 1 ? prev - 1 : prev))
    }, 1000)

    closeTimerRef.current = setTimeout(() => {
      if (closeCountdownRef.current) clearInterval(closeCountdownRef.current)
      setClosingIn(null)
      cleanupLabResources()
      navigate(`/scenarios/${slug || ''}`, {
        state: {
          labCompleted: true,
          score: result?.score,
          scenarioTitle: session?.scenario?.title || session?.scenario_detail?.title,
        },
      })
    }, LAB_CLOSE_SECONDS * 1000)
  }, [LAB_CLOSE_SECONDS, cleanupLabResources, navigate, session])

  useEffect(() => () => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current)
    if (closeCountdownRef.current) clearInterval(closeCountdownRef.current)
  }, [])

  const WS_NO_RECONNECT = new Set([1000, 4001, 4003, 4004, 4005, 4008, 4500])

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

  // ── Cross-tab sync: detect when lab is stopped/expired from another tab ──
  useEffect(() => {
    if (typeof BroadcastChannel === 'undefined') return

    const channel = new BroadcastChannel('fixitlab_lab_sync')
    labChannelRef.current = channel

    channel.onmessage = (event) => {
      const { type, sessionId: stoppedId, reason, closingDelayMs } = event.data || {}
      if (type === 'lab_stopped' && stoppedId === sessionId) {
        const finish = () => {
          cleanupLabResources()
          const msg = reason === 'completed' ? 'Lab completed in another tab!'
            : reason === 'expired' ? 'Lab time expired!'
            : 'Lab was stopped in another tab'
          toast(msg, { icon: '🔄', duration: 4000 })
          navigate('/scenarios')
        }
        if (reason === 'completed' && closingDelayMs > 0) {
          toast(`Lab completed — closing in ${Math.ceil(closingDelayMs / 1000)}s…`, { icon: '✅', duration: closingDelayMs })
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
          toast(msg, { icon: lab.status === 'COMPLETED' ? '✅' : '⏰', duration: 4000 })
          navigate(`/scenarios/${lab.scenario?.slug || ''}`, {
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

          // Compile blocked command patterns from scenario
          const blockedCmds = lab.scenario?.blocked_commands || []
          blockedPatternsRef.current = blockedCmds.map(entry => {
            if (!entry || typeof entry !== 'string') return null
            const raw = entry.trim()
            if (!raw) return null
            try {
              if (raw.startsWith('^')) {
                return { pattern: new RegExp(raw, 'i'), label: raw }
              } else {
                const escaped = raw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
                return { pattern: new RegExp(`(?:^|[;&|]\\s*)${escaped}`, 'i'), label: raw }
              }
            } catch { return null }
          }).filter(Boolean)

          if (lab.time_remaining > 0) {
            startTimer(lab.time_remaining, async () => {
              // Timer expired — terminate lab, close resources, redirect
              toast('Lab time completed! The environment is being terminated.', { icon: '⏰', duration: 6000 })

              // Close WebSocket + xterm
              if (wsRef.current) {
                wsRef.current.onclose = null
                wsRef.current.close(1000)
                wsRef.current = null
              }
              if (xtermRef.current) {
                xtermRef.current.dispose()
                xtermRef.current = null
              }

              // Terminate the lab (EC2/Docker)
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

  // Initialize xterm.js and WebSocket (single-pane mode only)
  useEffect(() => {
    if (!session || session.status !== 'RUNNING' || !terminalRef.current) return
    const dualPane = session.scenario?.dual_terminal && (session.lab_hosts?.length >= 2)
    if (dualPane) return
    const hasResource = session.container_id || session.instance_id
    if (!hasResource) return
    if (terminalSessionRef.current === `${sessionId}:${terminalHost}`) return

    let disposed = false
    let cleanup = () => {}

    const initTerminal = async () => {
      const { Terminal } = await import('@xterm/xterm')
      const { FitAddon } = await import('@xterm/addon-fit')
      const { WebLinksAddon } = await import('@xterm/addon-web-links')
      await import('@xterm/xterm/css/xterm.css')

      if (disposed) return
      terminalSessionRef.current = `${sessionId}:${terminalHost}`
      reconnectAttempts.current = 0

      const term = new Terminal({
        cursorBlink: true,
        cursorStyle: 'bar',
        fontSize: isMobile ? 11 : 14,
        lineHeight: isMobile ? 1.15 : 1.2,
        fontFamily: '"JetBrains Mono", "Fira Code", "Cascadia Code", monospace',
        theme: {
          background: '#020617',
          foreground: '#e2e8f0',
          cursor: '#06b6d4',
          cursorAccent: '#020617',
          selectionBackground: '#334155',
          black: '#0f172a', red: '#ef4444', green: '#10b981', yellow: '#f59e0b',
          blue: '#3b82f6', magenta: '#8b5cf6', cyan: '#06b6d4', white: '#f1f5f9',
          brightBlack: '#475569', brightRed: '#f87171', brightGreen: '#34d399',
          brightYellow: '#fbbf24', brightBlue: '#60a5fa', brightMagenta: '#a78bfa',
          brightCyan: '#22d3ee', brightWhite: '#f8fafc',
        },
        allowProposedApi: true,
      })

      const fitAddon = new FitAddon()
      const webLinksAddon = new WebLinksAddon()
      term.loadAddon(fitAddon)
      term.loadAddon(webLinksAddon)
      term.open(terminalRef.current)
      fitAddon.fit()

      xtermRef.current = term
      fitAddonRef.current = fitAddon

      const shellReadyRef = { current: false }
      const resizeDebounceRef = { current: null }

      const sendResize = () => {
        const isCloud = session?.provider === 'aws_ec2' || session?.provider === 'digitalocean'
        if (!isCloud || !shellReadyRef.current) return
        if (wsRef.current?.readyState === WebSocket.OPEN && term.cols && term.rows) {
          wsRef.current.send(JSON.stringify({ resize: { cols: term.cols, rows: term.rows } }))
        }
      }

      const scheduleResize = () => {
        if (resizeDebounceRef.current) clearTimeout(resizeDebounceRef.current)
        resizeDebounceRef.current = setTimeout(sendResize, 300)
      }

      const resizeObserver =
        typeof ResizeObserver !== 'undefined'
          ? new ResizeObserver(() => {
              if (disposed) return
              fitAddon.fit()
              scheduleResize()
            })
          : null
      if (resizeObserver && terminalRef.current) {
        resizeObserver.observe(terminalRef.current)
      }

      const wsCloseMessages = {
        4001: '\r\n\x1b[1;31mAuthentication expired — refresh the page to reconnect.\x1b[0m\r\n',
        4003: '\r\n\x1b[1;33mLab is not running yet — wait for provisioning to finish.\x1b[0m\r\n',
        4004: '\r\n\x1b[1;31mLab session not found.\x1b[0m\r\n',
        4005: '\r\n\x1b[1;31mLab environment not ready — try again in a few seconds.\x1b[0m\r\n',
        4008: '\r\n\x1b[1;31mToo many terminal tabs open — close another tab and refresh.\x1b[0m\r\n',
        4500: '\r\n\x1b[1;31mCould not connect to lab shell.\x1b[0m\r\n',
      }

      const buildWsUrl = () => {
        const token = useAuthStore.getState().accessToken
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
        const hostQ = terminalHost && terminalHost !== 'primary' ? `&host=${encodeURIComponent(terminalHost)}` : ''
        return `${protocol}://${window.location.host}/ws/terminal/${sessionId}/?token=${token}${hostQ}`
      }

      const bindEnterRetry = (message) => {
        term.write(message)
        const retryHandler = term.onData((data) => {
          if (data === '\r' || data === '\n') {
            retryHandler.dispose()
            reconnectAttempts.current = 0
            term.write('\r\n\x1b[1;36mRetrying connection...\x1b[0m\r\n')
            connectWs()
          }
        })
      }

      const connectWs = () => {
        if (disposed) return
        if (reconnectTimerRef.current) {
          clearTimeout(reconnectTimerRef.current)
          reconnectTimerRef.current = null
        }
        if (wsRef.current) {
          wsRef.current.onclose = null
          wsRef.current.close(1000)
          wsRef.current = null
        }

        const ws = new WebSocket(buildWsUrl())
        wsRef.current = ws

        ws.onopen = () => {
          reconnectAttempts.current = 0
          shellReadyRef.current = false
        }
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            if (data.type === 'ping') return
            if (data.type === 'shell_respawn') {
              reconnectAttempts.current = 0
              shellReadyRef.current = false
              if (data.output) term.write(data.output)
              return
            }
            if (data.type === 'shell_ready') {
              shellReadyRef.current = true
              scheduleResize()
              return
            }
            if (data.output) term.write(data.output)
          } catch { term.write(event.data) }
        }
        ws.onclose = (e) => {
          if (disposed || e.code === 1000) {
            if (e.code === 1000) term.write('\r\n\x1b[1;33mSession ended\x1b[0m\r\n')
            return
          }
          if (WS_NO_RECONNECT.has(e.code)) {
            term.write(wsCloseMessages[e.code] || '\r\n\x1b[1;31mConnection closed.\x1b[0m\r\n')
            if (e.code === 4500) {
              term.write('\x1b[1;33mPress Enter to retry connection...\x1b[0m\r\n')
              const retryHandler = term.onData((data) => {
                if (data === '\r' || data === '\n') {
                  retryHandler.dispose()
                  reconnectAttempts.current = 0
                  term.write('\r\n\x1b[1;36mRetrying connection...\x1b[0m\r\n')
                  connectWs()
                }
              })
            }
            return
          }
          // Abnormal closure (1006) — server respawns shell in-place; brief pause then one retry
          if (e.code === 1006 && reconnectAttempts.current < 2) {
            reconnectAttempts.current++
            term.write('\r\n\x1b[1;33mConnection interrupted — retrying...\x1b[0m\r\n')
            reconnectTimerRef.current = setTimeout(connectWs, 1500)
            return
          }
          if (reconnectAttempts.current < maxReconnectAttempts) {
            reconnectAttempts.current++
            const isSim = session?.provider === 'simulation'
            const isCloud = session?.provider === 'aws_ec2' || session?.provider === 'digitalocean'
            if (isSim && reconnectAttempts.current > 3) {
              bindEnterRetry('\r\n\x1b[1;33mSimulation shell paused — press Enter to reconnect\x1b[0m\r\n')
              return
            }
            const baseDelay = isCloud ? 3000 : isSim ? 1000 : 2000
            const cap = isSim ? 3 : maxReconnectAttempts
            if (reconnectAttempts.current >= cap) {
              bindEnterRetry('\r\n\x1b[1;31mConnection lost.\x1b[0m Press Enter to retry.\x1b[0m\r\n')
              return
            }
            const delay = Math.min(baseDelay * Math.pow(1.5, reconnectAttempts.current - 1), 20000)
            if (!isSim) {
              term.write(`\r\n\x1b[1;33mReconnecting in ${Math.round(delay / 1000)}s... (${reconnectAttempts.current}/${maxReconnectAttempts})\x1b[0m\r\n`)
            }
            reconnectTimerRef.current = setTimeout(connectWs, delay)
          } else {
            term.write('\r\n\x1b[1;31mConnection lost after multiple attempts.\x1b[0m\r\n')
            term.write('\x1b[1;33mPress Enter to retry connection...\x1b[0m\r\n')
            const retryHandler = term.onData((data) => {
              if (data === '\r' || data === '\n') {
                retryHandler.dispose()
                reconnectAttempts.current = 0
                term.write('\r\n\x1b[1;36mRetrying connection...\x1b[0m\r\n')
                connectWs()
              }
            })
          }
        }
        ws.onerror = () => {} // onclose handles recovery
      }

      connectWs()

      term.onData((data) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          // Accumulate input and check blocked commands on Enter
          if (data === '\r' || data === '\n') {
            const cmd = inputBufferRef.current.trim()
            inputBufferRef.current = ''
            if (cmd && blockedPatternsRef.current.length > 0) {
              // Split on shell separators to check chained commands
              const parts = cmd.split(/\s*(?:;|&&|\|\||\|)\s*/)
              for (const part of parts) {
                const trimmed = part.trim()
                if (!trimmed) continue
                for (const { pattern, label } of blockedPatternsRef.current) {
                  if (pattern.test(trimmed)) {
                    // Block: show warning in terminal, don't send Enter
                    term.write(`\r\n\x1b[1;31m⛔ Command blocked: \x1b[0;33m${label}\x1b[1;31m is not allowed in this scenario.\x1b[0m\r\n`)
                    // Send Ctrl+C to get a fresh prompt
                    wsRef.current.send(JSON.stringify({ input: '\x03' }))
                    return
                  }
                }
              }
            }
            // Command allowed — send the Enter key
            wsRef.current.send(JSON.stringify({ input: data }))
          } else if (data === '\x7f' || data === '\b') {
            // Backspace — remove last char from buffer
            inputBufferRef.current = inputBufferRef.current.slice(0, -1)
            wsRef.current.send(JSON.stringify({ input: data }))
          } else if (data === '\x03') {
            // Ctrl+C — clear buffer
            inputBufferRef.current = ''
            wsRef.current.send(JSON.stringify({ input: data }))
          } else if (data === '\x15') {
            // Ctrl+U — clear line
            inputBufferRef.current = ''
            wsRef.current.send(JSON.stringify({ input: data }))
          } else {
            inputBufferRef.current += data
            wsRef.current.send(JSON.stringify({ input: data }))
          }
        }
      })

      const handleResize = () => {
        fitAddon.fit()
        scheduleResize()
      }
      term.onResize(() => scheduleResize())
      window.addEventListener('resize', handleResize)

      cleanup = () => {
        disposed = true
        resizeObserver?.disconnect()
        window.removeEventListener('resize', handleResize)
        if (resizeDebounceRef.current) {
          clearTimeout(resizeDebounceRef.current)
          resizeDebounceRef.current = null
        }
        if (reconnectTimerRef.current) {
          clearTimeout(reconnectTimerRef.current)
          reconnectTimerRef.current = null
        }
        reconnectAttempts.current = maxReconnectAttempts
        if (wsRef.current) {
          wsRef.current.onclose = null
          wsRef.current.close(1000)
          wsRef.current = null
        }
        term.dispose()
        if (terminalSessionRef.current === sessionId) terminalSessionRef.current = null
      }
    }

    initTerminal()
    return () => cleanup()
  }, [sessionId, session?.status, session?.container_id, session?.instance_id, terminalHost, isMobile])

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
        toast('Lab terminated due to 30 minutes of inactivity.', { icon: '⏰', duration: 8000 })
        try {
          if (wsRef.current) { wsRef.current.close(1000); wsRef.current = null }
          await labApi.stopLab(sessionId)
        } catch {}
        clearSession()
        stopTimer()
        navigate('/scenarios')
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

  // Refit terminal when sidebar toggles
  useEffect(() => {
    if (fitAddonRef.current) {
      setTimeout(() => fitAddonRef.current.fit(), 300)
    }
  }, [sidebarOpen])

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
      setJiraTicket(res.data)
      setJiraComments(res.data?.comments || [])
      toast.success('Customer replied')
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to post comment')
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
        if (wsRef.current) {
          wsRef.current.onclose = null
          wsRef.current.close()
          wsRef.current = null
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
        toast('Validation failed. Keep trying!', { icon: '🔍' })
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
        toast('Use AI coaching hints in interview mode', { icon: '🎯' })
      } else {
        toast.error(err.response?.data?.error || 'No more hints')
      }
    }
  }

  const handleStop = async () => {
    setStopping(true)
    try {
      // Close WebSocket connection first to release the terminal
      if (wsRef.current) {
        wsRef.current.onclose = null  // Prevent "Connection closed" message
        wsRef.current.close()
        wsRef.current = null
      }
      // Dispose xterm to clean up
      if (xtermRef.current) {
        xtermRef.current.dispose()
        xtermRef.current = null
      }
      const result = await labApi.stopLab(sessionId)
      clearSession()
      stopTimer()

      // Broadcast to other tabs that this lab was stopped
      if (labChannelRef.current) {
        labChannelRef.current.postMessage({ type: 'lab_stopped', sessionId, reason: 'stopped' })
      }

      // For cloud labs, wait until the EC2/DO instance is fully terminated
      if (result?.is_cloud) {
        toast('Terminating cloud server — please wait...', { icon: '☁️', duration: 5000 })
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

      toast.success('Lab stopped successfully')
      navigate('/scenarios')
    } catch {
      toast.error('Failed to stop lab')
      navigate('/scenarios')
    } finally {
      setStopping(false)
      setShowStopConfirm(false)
    }
  }

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

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

  const scenario = session?.scenario_detail || session?.scenario || {}
  const labHosts = session?.lab_hosts || []
  const useDualPane = Boolean(scenario.dual_terminal && labHosts.length >= 2)
  const dualHosts = useDualPane ? labHosts.slice(0, 2) : []
  const blockedCmds = scenario.blocked_commands || []
  const sshTargets = labHosts.filter(h => h.ip)
  const insertSshCommand = (host) => {
    const user = host.ssh_user || session?.ssh_user || 'root'
    const ip = host.ip || session?.ssh_host
    if (!ip || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      toast.error('Terminal not ready for SSH')
      return
    }
    const cmd = `ssh -o StrictHostKeyChecking=no ${user}@${ip}\r`
    wsRef.current.send(JSON.stringify({ input: cmd }))
    toast.success(`Sent: ssh ${user}@${ip}`)
  }
  const isTimeLow = timeRemaining < 120 && timeRemaining > 0
  const isTimeCritical = timeRemaining < 60 && timeRemaining > 0
  const solved = validationResult?.passed
  const expired = validationResult?.expired

  return (
    <div className="fixed inset-0 sm:relative flex flex-col bg-surface-950 sm:min-h-[100dvh] sm:h-[100dvh] z-20">
      {/* Mobile top bar */}
      <div className="sm:hidden flex items-center justify-between px-3 py-2 bg-surface-900 border-b border-surface-700/50 shrink-0">
        <button onClick={() => { setSidebarTab('instructions'); setSidebarOpen(true) }} className="p-1.5 text-surface-400">
          <PanelLeftOpen size={18} />
        </button>
        <p className="text-xs font-semibold text-white truncate flex-1 text-center px-2">{scenario.title || 'Lab'}</p>
        <span className={`text-xs font-mono font-bold ${isTimeCritical ? 'text-accent-red' : 'text-surface-300'}`}>
          {formatTime(timeRemaining)}
        </span>
      </div>
      {closingIn != null && (
        <div className="shrink-0 px-4 py-2 bg-accent-green/15 border-b border-accent-green/30 text-center text-sm text-accent-green font-medium animate-pulse">
          Lab is closing in {closingIn}s…
        </div>
      )}
      {/* Top bar - hidden on mobile where floating bar is used */}
      <div className="hidden sm:flex items-center justify-between px-4 py-2 bg-surface-900 border-b border-surface-700/50 shrink-0">
        <div className="flex items-center gap-3">
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="text-surface-400 hover:text-white transition-colors">
            {sidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
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
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-mono font-bold ${
            isTimeCritical ? 'bg-accent-red/20 text-accent-red border border-accent-red/30 animate-pulse'
            : isTimeLow ? 'bg-accent-amber/10 text-accent-amber border border-accent-amber/20'
            : 'bg-surface-800 text-surface-300 border border-surface-700'
          }`}>
            <Timer size={13} />
            {formatTime(timeRemaining)}
          </div>
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
            ? `fixed inset-y-0 left-0 z-40 w-80 max-w-[85vw] transform transition-transform ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`
            : `${sidebarOpen ? 'w-80' : 'w-0'} transition-all duration-300`
        } overflow-hidden border-r border-surface-700/50 bg-surface-900 shrink-0`}
        >
          <div className="w-80 h-full flex flex-col">
            {/* Tabs */}
            <div className="flex border-b border-surface-800">
              {[
                { key: 'instructions', label: 'Info', icon: FileText },
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

        <div className="flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden">
        {/* Terminal action bar — above xterm */}
        <div className="shrink-0 flex flex-wrap items-center gap-1.5 sm:gap-2 px-2 py-2 bg-surface-900 border-b border-surface-800 text-[10px] sm:text-xs">
          {useDualPane && (
            <span className="text-accent-purple font-medium mr-1">Dual terminal</span>
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
                  terminalSessionRef.current = null
                  setTerminalHost(h.name)
                }
              }}
              className={`px-2.5 py-1.5 rounded-md border font-medium ${terminalHost === h.name ? 'border-accent-cyan text-accent-cyan bg-accent-cyan/10' : 'border-surface-700 text-surface-400 hover:border-surface-600'}`}
            >
              {h.role === 'client' || h.name === 'companion' ? 'Client' : (h.role || h.name)}
            </button>
          ))}
          {sshTargets.map(h => (
            <button
              key={`ssh-${h.name}`}
              type="button"
              onClick={() => insertSshCommand(h)}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-surface-700 text-surface-300 hover:border-accent-cyan hover:text-accent-cyan bg-surface-800/50"
              title={`ssh ${h.ssh_user || 'root'}@${h.ip}`}
            >
              <Terminal size={12} /> SSH {h.role || h.name}
            </button>
          ))}
          <div className="w-px h-6 bg-surface-700 mx-0.5 hidden sm:block" />
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
          <button
            onClick={() => setShowStopConfirm(true)}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-red-500/30 text-red-400 bg-red-500/10 hover:bg-red-500/20"
          >
            <StopCircle size={12} /> Stop
          </button>
        </div>
        {/* Terminal */}
        <div className="flex-1 bg-surface-950 relative min-h-0 overflow-hidden pb-[calc(3.75rem+env(safe-area-inset-bottom,0px))] sm:pb-0">
          {useDualPane ? (
            <div className="absolute inset-0 grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-surface-800">
              {dualHosts.map(h => (
                <LabTerminal
                  key={h.name}
                  sessionId={sessionId}
                  session={session}
                  hostKey={h.name}
                  label={`${h.role || h.name} (${h.ip || 'sim'})`}
                  isMobile={isMobile}
                  blockedCommands={blockedCmds}
                  className="h-full"
                />
              ))}
            </div>
          ) : (
            <div ref={terminalRef} className="absolute inset-0 p-0.5 sm:p-1 touch-manipulation" />
          )}
        </div>
        </div>
      </div>

      {/* Mobile: floating action bar */}
      <div className="sm:hidden fixed bottom-0 inset-x-0 bg-surface-900 border-t border-surface-700/50 px-2 py-2 flex items-center justify-around z-30 pb-[max(0.5rem,env(safe-area-inset-bottom))]">
        <span className="absolute left-3 top-1 text-[10px] font-mono text-surface-500">{formatTime(timeRemaining)}</span>
        <button onClick={() => { setSidebarTab('instructions'); setSidebarOpen(p => !p) }}
          className="p-2 text-surface-400 hover:text-white" aria-label="Instructions">
          <FileText size={20} />
        </button>
        <button onClick={toggleHints}
          className="p-2 text-surface-400 hover:text-accent-amber" aria-label="Hints">
          <Lightbulb size={20} />
        </button>
        {sshTargets.length > 0 && (
          <button
            onClick={() => insertSshCommand(sshTargets[0])}
            className="p-2 text-surface-400 hover:text-accent-cyan"
            aria-label="SSH to remote host"
            title={`ssh ${sshTargets[0].ssh_user || 'root'}@${sshTargets[0].ip}`}
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
        <button onClick={() => setShowShortcuts(true)}
          className="p-2 text-surface-400 hover:text-white" aria-label="Keyboard shortcuts">
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

      {/* Keyboard shortcuts help */}
      {showShortcuts && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowShortcuts(false)}>
          <div className="glass-card p-6 max-w-xs w-full" onClick={e => e.stopPropagation()}>
            <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
              <Keyboard size={16} className="text-accent-cyan" /> Keyboard Shortcuts
            </h3>
            <div className="space-y-3 text-sm">
              {[
                ['Ctrl + Enter', 'Check Solution'],
                ['Ctrl + H', 'Toggle Hints'],
                ['Escape', 'Toggle Sidebar'],
              ].map(([key, action]) => (
                <div key={key} className="flex items-center justify-between">
                  <span className="text-surface-400">{action}</span>
                  <kbd className="px-2 py-0.5 bg-surface-800 border border-surface-700 rounded text-xs text-surface-300 font-mono">{key}</kbd>
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
