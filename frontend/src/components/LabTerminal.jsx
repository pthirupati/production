import { useEffect, useRef, useState, useCallback, memo, forwardRef, useImperativeHandle } from 'react'
import {
  Download, Maximize2, Minimize2, Minus, Plus, Columns2, Terminal as TerminalIcon, X,
} from 'lucide-react'
import { useAuthStore } from '../store/authStore'

const WS_NO_RECONNECT = new Set([1000, 4001, 4003, 4004, 4005, 4008, 4500])

// Refresh the in-memory JWT used to authenticate the terminal WebSocket. The
// socket reads useAuthStore.accessToken at connect time, but (unlike the axios
// client) it never refreshes on its own — so an expired access token closes the
// socket with 4001 and the user is stuck. We attempt a single silent refresh
// (cookie- or body-based) and let the caller reconnect on success.
async function refreshAuthToken() {
  try {
    const { refreshToken, user, setAuth } = useAuthStore.getState()
    const res = await fetch('/api/auth/refresh/', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify(refreshToken ? { refresh: refreshToken } : {}),
    })
    if (!res.ok) return false
    const data = await res.json()
    if (data?.access) {
      setAuth(user, data.access, data.refresh || refreshToken)
      return true
    }
    // Cookie-only session: middleware accepts httpOnly cookie even without body token.
    if (useAuthStore.getState().isAuthenticated) return true
    return false
  } catch {
    return false
  }
}

const WS_CLOSE_MESSAGES = {
  4001: '\r\n\x1b[1;31mAuthentication expired — refresh the page to reconnect.\x1b[0m\r\n',
  4003: '\r\n\x1b[1;33mLab is not running yet — wait for provisioning to finish.\x1b[0m\r\n',
  4004: '\r\n\x1b[1;31mLab session not found.\x1b[0m\r\n',
  4005: '\r\n\x1b[1;31mLab environment not ready — try again in a few seconds.\x1b[0m\r\n',
  4008: '\r\n\x1b[1;31mToo many terminal tabs open — close another tab and refresh.\x1b[0m\r\n',
  4500: '\r\n\x1b[1;31mCould not connect to lab shell.\x1b[0m\r\n',
}

const TERMINAL_PROFILES = {
  powershell: {
    label: 'Windows PowerShell',
    icon: 'PS',
    prompt: 'PS C:\\Users\\Administrator>',
    theme: { background: '#012456', foreground: '#f3f6fb', cursor: '#ffffff', selectionBackground: '#1b5f9e' },
  },
  cmd: {
    label: 'Windows CMD',
    icon: 'C:\\',
    prompt: 'C:\\Users\\Administrator>',
    theme: { background: '#000000', foreground: '#c0c0c0', cursor: '#ffffff', selectionBackground: '#333333' },
  },
  linux: {
    label: 'Linux Bash',
    icon: '$',
    prompt: 'root@ubuntu:~$',
    theme: { background: '#020617', foreground: '#e2e8f0', cursor: '#06b6d4', selectionBackground: '#334155' },
  },
  esxi: {
    label: 'ESXi Shell',
    icon: 'ESX',
    prompt: '[root@esxi:~]',
    theme: { background: '#2b2f36', foreground: '#e8edf2', cursor: '#f59e0b', selectionBackground: '#4b5563' },
  },
  ansible: {
    label: 'Ansible/AWX CLI',
    icon: 'A',
    prompt: 'awx@controller:~$',
    theme: { background: '#0b1020', foreground: '#dbeafe', cursor: '#60a5fa', selectionBackground: '#1e3a8a' },
  },
  terraform: {
    label: 'Terraform CLI',
    icon: 'TF',
    prompt: 'terraform@workspace:~/infra$',
    theme: { background: '#120b2d', foreground: '#ede9fe', cursor: '#a78bfa', selectionBackground: '#4c1d95' },
  },
  kubectl: {
    label: 'Kubernetes/kubectl',
    icon: 'K8s',
    prompt: 'admin@cluster:~$',
    theme: { background: '#061225', foreground: '#dbeafe', cursor: '#38bdf8', selectionBackground: '#1d4ed8' },
  },
}

function inferProfiles(session, hostKey, label) {
  const sim = String(session?.simulation_type || '').toLowerCase()
  const tech = String(session?.technology_slug || session?.technology_name || '').toLowerCase()
  const text = `${sim} ${tech} ${hostKey || ''} ${label || ''}`.toLowerCase()
  if (text.includes('windows')) return ['powershell', 'cmd']
  if (text.includes('vmware') || text.includes('vsphere') || text.includes('esxi')) return ['esxi', 'linux']
  if (text.includes('terraform')) return ['terraform', 'linux']
  if (text.includes('awx') || text.includes('ansible')) return ['ansible', 'linux']
  if (text.includes('kubernetes') || text.includes('k8s') || text.includes('kubectl')) return ['kubectl', 'linux']
  return ['linux']
}

function makeTab(id, profileKey) {
  const p = TERMINAL_PROFILES[profileKey] || TERMINAL_PROFILES.linux
  return { id, profileKey, label: p.label }
}

/**
 * Single xterm + WebSocket pane for a lab host (primary, companion, or ssh_client).
 */
function LabTerminal({
  sessionId,
  session,
  hostKey = 'primary',
  label = '',
  isMobile = false,
  blockedCommands = [],
  className = '',
  welcomeHint = '',
  layoutKey,
  onReady,
}, ref) {
  const mountElRef = useRef(null)
  const [mountReady, setMountReady] = useState(false)
  const mountRef = useCallback((node) => {
    mountElRef.current = node
    setMountReady(Boolean(node))
  }, [])
  const blockedCommandsRef = useRef(blockedCommands)
  const welcomeHintRef = useRef(welcomeHint)
  blockedCommandsRef.current = blockedCommands
  welcomeHintRef.current = welcomeHint
  const xtermRef = useRef(null)
  const wsRef = useRef(null)
  const fitAddonRef = useRef(null)
  const reconnectAttempts = useRef(0)
  const reconnectTimerRef = useRef(null)
  const inputBufferRef = useRef('')
  const initGenRef = useRef(0)
  const isMobileRef = useRef(isMobile)
  isMobileRef.current = isMobile
  const maxReconnectAttempts = 10
  const [fontSize, setFontSize] = useState(isMobile ? 10 : 13)
  const fontSizeRef = useRef(fontSize)
  fontSizeRef.current = fontSize
  const initialProfiles = inferProfiles(session, hostKey, label)
  const [tabs, setTabs] = useState(() => initialProfiles.map((p, i) => makeTab(`${p}-${i}`, p)))
  const [activeTabId, setActiveTabId] = useState(() => `${initialProfiles[0]}-0`)
  const [split, setSplit] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const [statusText, setStatusText] = useState('Connecting')
  const activeTab = tabs.find((t) => t.id === activeTabId) || tabs[0] || makeTab('linux-0', 'linux')
  const activeProfile = TERMINAL_PROFILES[activeTab.profileKey] || TERMINAL_PROFILES.linux
  const activeProfileRef = useRef(activeProfile)
  activeProfileRef.current = activeProfile

  useImperativeHandle(ref, () => ({
    sendCommand(text) {
      const ws = wsRef.current
      if (!ws || ws.readyState !== WebSocket.OPEN || !text) return false
      for (const ch of text) {
        ws.send(JSON.stringify({ input: ch }))
      }
      ws.send(JSON.stringify({ input: '\r' }))
      return true
    },
    isConnected() {
      return wsRef.current?.readyState === WebSocket.OPEN
    },
  }), [])

  useEffect(() => {
    const mountNode = mountElRef.current
    if (!session || session.status !== 'RUNNING' || !mountReady || !mountNode) return
    const isSimulation = session.provider === 'simulation'
    const hasResource = session.container_id || session.instance_id || isSimulation
    if (!hasResource) return

    const gen = ++initGenRef.current
    let disposed = false
    let cleanup = () => {}

    const init = async () => {
      const { Terminal } = await import('@xterm/xterm')
      const { FitAddon } = await import('@xterm/addon-fit')
      const { WebLinksAddon } = await import('@xterm/addon-web-links')
      await import('@xterm/xterm/css/xterm.css')
      if (disposed || gen !== initGenRef.current || !mountElRef.current) return

      reconnectAttempts.current = 0

      const term = new Terminal({
        cursorBlink: true,
        cursorStyle: 'bar',
        fontSize: fontSizeRef.current,
        lineHeight: 1.2,
        fontFamily: '"JetBrains Mono", "Fira Code", monospace',
        theme: activeProfileRef.current.theme,
        scrollback: 5000,
        allowProposedApi: false,
      })
      const fitAddon = new FitAddon()
      term.loadAddon(fitAddon)
      term.loadAddon(new WebLinksAddon())
      term.open(mountNode)
      fitAddon.fit()
      xtermRef.current = term
      fitAddonRef.current = fitAddon

      const hint = welcomeHintRef.current
      if (hint) {
        term.write(`\r\n\x1b[1;36m${hint}\x1b[0m\r\n`)
      }

      const isCloud = session?.provider === 'aws_ec2' || session?.provider === 'digitalocean'
      const shellReadyRef = { current: false }
      const readyFiredRef = { current: false }
      const reconnectMsgShown = { current: false }
      const authRefreshTriedRef = { current: false }
      const connectingRef = { current: false }
      const connectionStableAtRef = { current: null }
      const pauseUntilVisibleRef = { current: false }
      const resizeDebounceRef = { current: null }

      const fireReady = () => {
        if (!readyFiredRef.current) {
          readyFiredRef.current = true
          onReady?.()
        }
      }

      const markStable = () => {
        connectionStableAtRef.current = Date.now()
      }

      const sendResize = () => {
        if (!isCloud || !shellReadyRef.current) return
        if (wsRef.current?.readyState === WebSocket.OPEN && term.cols && term.rows) {
          wsRef.current.send(JSON.stringify({ resize: { cols: term.cols, rows: term.rows } }))
        }
      }

      const scheduleResize = () => {
        if (resizeDebounceRef.current) clearTimeout(resizeDebounceRef.current)
        resizeDebounceRef.current = setTimeout(sendResize, 300)
      }

      const blockedPatterns = (blockedCommandsRef.current || []).map(entry => {
        if (!entry || typeof entry !== 'string') return null
        const raw = entry.trim()
        if (!raw) return null
        try {
          if (raw.startsWith('^')) return { pattern: new RegExp(raw, 'i'), label: raw }
          const escaped = raw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
          return { pattern: new RegExp(`(?:^|[;&|]\\s*)${escaped}`, 'i'), label: raw }
        } catch { return null }
      }).filter(Boolean)

      const buildWsUrl = () => {
        const token = useAuthStore.getState().accessToken
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
        const params = new URLSearchParams()
        if (token && token !== 'null') params.set('token', token)
        if (hostKey && hostKey !== 'primary') params.set('host', hostKey)
        const qs = params.toString()
        return `${protocol}://${window.location.host}/ws/terminal/${sessionId}/${qs ? `?${qs}` : ''}`
      }

      const ensureWsAuth = async () => {
        const token = useAuthStore.getState().accessToken
        if (token && token !== 'null') return true
        if (useAuthStore.getState().isAuthenticated) {
          return refreshAuthToken()
        }
        return false
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

      const scheduleReconnect = (delayMs, message) => {
        if (disposed) return
        if (document.hidden) {
          pauseUntilVisibleRef.current = true
          return
        }
        if (message && !reconnectMsgShown.current) {
          reconnectMsgShown.current = true
          term.write(message)
        }
        reconnectTimerRef.current = setTimeout(connectWs, delayMs)
      }

      const connectWs = async () => {
        if (disposed || connectingRef.current) return
        if (document.hidden) {
          pauseUntilVisibleRef.current = true
          return
        }
        pauseUntilVisibleRef.current = false
        connectingRef.current = true
        if (!(await ensureWsAuth())) {
          connectingRef.current = false
          if (!disposed) {
            term.write('\r\n\x1b[1;33mSign in required — refresh the page or log in again.\x1b[0m\r\n')
            bindEnterRetry('\x1b[1;33mPress Enter to retry connection...\x1b[0m\r\n')
          }
          return
        }
        if (reconnectTimerRef.current) {
          clearTimeout(reconnectTimerRef.current)
          reconnectTimerRef.current = null
        }
        const prev = wsRef.current
        if (prev) {
          prev.onclose = null
          prev.onmessage = null
          if (prev._readyFallback) clearTimeout(prev._readyFallback)
          if (prev._stableTimer) clearTimeout(prev._stableTimer)
          if (prev._clientPing) clearInterval(prev._clientPing)
          if (prev.readyState === WebSocket.OPEN || prev.readyState === WebSocket.CONNECTING) {
            prev.close(1000)
          }
        }
        const ws = new WebSocket(buildWsUrl())
        wsRef.current = ws
        ws.onopen = () => {
          setStatusText('Connected')
          connectingRef.current = false
          shellReadyRef.current = false
          // Only clear the retry budget once the socket survives a stable
          // window. Resetting on bare onopen made an open->die-within-8s socket
          // loop forever at "Reconnecting (1/10)" (the count reset every cycle).
          // Gating the reset behind a stability timer keeps a flapping
          // connection bounded so it surfaces the manual "press Enter" retry
          // instead of an endless silent loop, while a genuinely-recovered
          // connection still earns a fresh budget for future drops.
          if (ws._stableTimer) clearTimeout(ws._stableTimer)
          ws._stableTimer = setTimeout(() => {
            reconnectAttempts.current = 0
            reconnectMsgShown.current = false
          }, 10000)
          const fallbackMs = isSimulation ? 800 : isCloud ? 8000 : 1500
          ws._readyFallback = setTimeout(fireReady, fallbackMs)
          // Client-side keepalive. The backend pings server->client every 25s,
          // but an idle terminal sends nothing client->server, and some proxies
          // / NAT gateways reap a tunnel based on CLIENT inactivity only. Send a
          // tiny no-op every 20s (the consumer ignores any frame without an
          // "input"/"resize" key) so the connection stays warm in both
          // directions and idle terminals stop dropping into the reconnect loop.
          if (ws._clientPing) clearInterval(ws._clientPing)
          ws._clientPing = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              try { ws.send(JSON.stringify({ keepalive: 1 })) } catch { /* socket closing */ }
            }
          }, 20000)
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
              markStable()
              if (ws._readyFallback) clearTimeout(ws._readyFallback)
              scheduleResize()
              fireReady()
              return
            }
            if (data.output) {
              markStable()
              term.write(data.output)
            }
          } catch { term.write(event.data) }
        }
        ws.onclose = (e) => {
          setStatusText(e.code === 1000 ? 'Closed' : 'Reconnecting')
          connectingRef.current = false
          if (ws._readyFallback) clearTimeout(ws._readyFallback)
          if (ws._stableTimer) clearTimeout(ws._stableTimer)
          if (ws._clientPing) clearInterval(ws._clientPing)
          if (disposed || e.code === 1000) return
          // Auth expired: silently refresh the access token once and reconnect
          // instead of dead-ending on "refresh the page".
          if (e.code === 4001 && !authRefreshTriedRef.current) {
            authRefreshTriedRef.current = true
            term.write('\r\n\x1b[1;33mSession expired — refreshing credentials...\x1b[0m\r\n')
            refreshAuthToken().then((ok) => {
              if (disposed) return
              if (ok) {
                reconnectAttempts.current = 0
                reconnectMsgShown.current = false
                connectWs()
              } else {
                term.write(WS_CLOSE_MESSAGES[4001])
                bindEnterRetry('\x1b[1;33mPress Enter to retry connection...\x1b[0m\r\n')
              }
            })
            return
          }
          if (WS_NO_RECONNECT.has(e.code)) {
            term.write(WS_CLOSE_MESSAGES[e.code] || '\r\n\x1b[1;31mConnection closed.\x1b[0m\r\n')
            if (e.code === 4500) {
              bindEnterRetry('\x1b[1;33mPress Enter to retry connection...\x1b[0m\r\n')
            }
            return
          }
          const wasStable = connectionStableAtRef.current
            && (Date.now() - connectionStableAtRef.current) > 8000
          if (reconnectAttempts.current >= maxReconnectAttempts) {
            bindEnterRetry('\r\n\x1b[1;31mConnection lost after multiple attempts.\x1b[0m Press Enter to retry.\x1b[0m\r\n')
            return
          }
          reconnectAttempts.current++
          const delay = wasStable
            ? Math.min(800 + reconnectAttempts.current * 400, 4000)
            : Math.min(1000 * Math.pow(2, reconnectAttempts.current - 1), 12000)
          if (reconnectAttempts.current >= maxReconnectAttempts - 1) {
            bindEnterRetry('\r\n\x1b[1;33mConnection paused — press Enter to reconnect\x1b[0m\r\n')
            return
          }
          const msg = wasStable
            ? null
            : `\r\n\x1b[1;33mReconnecting (${reconnectAttempts.current}/${maxReconnectAttempts})...\x1b[0m\r\n`
          scheduleReconnect(delay, msg)
        }
        ws.onerror = () => {
          connectingRef.current = false
        }
      }

      const onVisibility = () => {
        if (document.hidden) return
        if (pauseUntilVisibleRef.current || (wsRef.current?.readyState !== WebSocket.OPEN && !connectingRef.current)) {
          pauseUntilVisibleRef.current = false
          reconnectAttempts.current = 0
          reconnectMsgShown.current = false
          connectWs()
        }
      }
      document.addEventListener('visibilitychange', onVisibility)

      connectWs()

      term.onData((data) => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) return
        if (data === '\r' || data === '\n') {
          const cmd = inputBufferRef.current.trim()
          inputBufferRef.current = ''
          if (cmd && blockedPatterns.length) {
            for (const part of cmd.split(/\s*(?:;|&&|\|\||\|)\s*/)) {
              for (const { pattern, label: lbl } of blockedPatterns) {
                if (pattern.test(part.trim())) {
                  term.write(`\r\n\x1b[1;31m⛔ Command blocked: ${lbl}\x1b[0m\r\n`)
                  wsRef.current.send(JSON.stringify({ input: '\x03' }))
                  return
                }
              }
            }
          }
          wsRef.current.send(JSON.stringify({ input: data }))
        } else if (data === '\x7f' || data === '\b') {
          inputBufferRef.current = inputBufferRef.current.slice(0, -1)
          wsRef.current.send(JSON.stringify({ input: data }))
        } else if (data === '\x03' || data === '\x15') {
          inputBufferRef.current = ''
          wsRef.current.send(JSON.stringify({ input: data }))
        } else {
          inputBufferRef.current += data
          wsRef.current.send(JSON.stringify({ input: data }))
        }
      })

      term.onResize(() => scheduleResize())

      const ro = typeof ResizeObserver !== 'undefined'
        ? new ResizeObserver(() => {
            if (!disposed) {
              fitAddon.fit()
              scheduleResize()
            }
          })
        : null
      ro?.observe(mountNode)

      const handleWindowResize = () => {
        if (!disposed) {
          fitAddon.fit()
          scheduleResize()
        }
      }
      window.addEventListener('resize', handleWindowResize)

      cleanup = () => {
        disposed = true
        document.removeEventListener('visibilitychange', onVisibility)
        if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
        if (resizeDebounceRef.current) clearTimeout(resizeDebounceRef.current)
        ro?.disconnect()
        window.removeEventListener('resize', handleWindowResize)
        const ws = wsRef.current
        if (ws) {
          if (ws._readyFallback) clearTimeout(ws._readyFallback)
          if (ws._stableTimer) clearTimeout(ws._stableTimer)
          if (ws._clientPing) clearInterval(ws._clientPing)
          ws.onclose = null
          ws.close(1000)
        }
        wsRef.current = null
        term.dispose()
        xtermRef.current = null
        fitAddonRef.current = null
      }
    }

    init()
    return () => {
      disposed = true
      cleanup()
    }
  }, [sessionId, session?.status, session?.container_id, session?.instance_id, session?.provider, hostKey, mountReady])

  useEffect(() => {
    if (fitAddonRef.current) {
      requestAnimationFrame(() => fitAddonRef.current?.fit())
    }
  }, [layoutKey])

  useEffect(() => {
    const term = xtermRef.current
    if (!term) return
    term.options.fontSize = fontSize
    requestAnimationFrame(() => fitAddonRef.current?.fit())
  }, [fontSize])

  useEffect(() => {
    const term = xtermRef.current
    if (!term || !activeProfile) return
    term.options.theme = activeProfile.theme
    term.write(`\r\n\x1b[1;36m${activeProfile.label} profile selected — expected prompt: ${activeProfile.prompt}\x1b[0m\r\n`)
    requestAnimationFrame(() => fitAddonRef.current?.fit())
  }, [activeProfile])

  const addTab = () => {
    setTabs((prev) => {
      const nextProfile = inferProfiles(session, hostKey, label)[prev.length % Math.max(1, inferProfiles(session, hostKey, label).length)] || 'linux'
      const id = `${nextProfile}-${Date.now()}`
      setActiveTabId(id)
      return [...prev, makeTab(id, nextProfile)]
    })
  }

  const closeTab = (id) => {
    setTabs((prev) => {
      if (prev.length <= 1) return prev
      const next = prev.filter((t) => t.id !== id)
      if (activeTabId === id) setActiveTabId(next[0]?.id)
      return next
    })
  }

  const downloadLog = () => {
    const term = xtermRef.current
    if (!term) return
    const lines = []
    const buffer = term.buffer?.active
    if (buffer) {
      for (let i = 0; i < buffer.length; i += 1) {
        lines.push(buffer.getLine(i)?.translateToString(true) || '')
      }
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `fixitlab-terminal-${hostKey || 'primary'}-${Date.now()}.log`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className={`flex flex-col min-h-0 min-w-0 ${fullscreen ? 'fixed inset-3 z-[9999] rounded-lg border border-accent-cyan/40 shadow-2xl' : ''} ${className}`}>
      {label && (
        <div className="shrink-0 px-2 py-1 text-[10px] sm:text-xs font-medium text-accent-cyan border-b border-surface-800 bg-surface-900/90">
          {label}
        </div>
      )}
      <div className="shrink-0 flex items-center gap-1 px-2 py-1 bg-surface-900 border-b border-surface-800 overflow-x-auto">
        {tabs.map((tab) => {
          const p = TERMINAL_PROFILES[tab.profileKey] || TERMINAL_PROFILES.linux
          const active = tab.id === activeTabId
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTabId(tab.id)}
              className={`group shrink-0 inline-flex items-center gap-1.5 rounded px-2 py-1 text-[11px] font-medium border ${
                active ? 'bg-accent-cyan/15 text-accent-cyan border-accent-cyan/30' : 'bg-surface-950 text-surface-400 border-surface-800 hover:text-white'
              }`}
              title={`${p.label} · ${p.prompt}`}
            >
              <span className="font-mono text-[10px] opacity-80">{p.icon}</span>
              <span>{tab.label}</span>
              {tabs.length > 1 && (
                <span
                  role="button"
                  tabIndex={0}
                  className="opacity-50 group-hover:opacity-100 hover:text-white"
                  onClick={(e) => { e.stopPropagation(); closeTab(tab.id) }}
                  onKeyDown={(e) => { if (e.key === 'Enter') closeTab(tab.id) }}
                >
                  <X size={10} />
                </span>
              )}
            </button>
          )
        })}
        <button type="button" className="shrink-0 p-1 rounded text-surface-400 hover:text-white hover:bg-surface-800" title="New terminal tab" onClick={addTab}>
          <Plus size={14} />
        </button>
        <span className="flex-1" />
        <span className="hidden md:inline text-[10px] text-surface-500 font-mono">{statusText}</span>
        <button type="button" className={`p-1 rounded ${split ? 'text-accent-cyan bg-accent-cyan/10' : 'text-surface-400 hover:text-white hover:bg-surface-800'}`} title="Split terminal" onClick={() => setSplit((s) => !s)}>
          <Columns2 size={14} />
        </button>
        <button type="button" className="p-1 rounded text-surface-400 hover:text-white hover:bg-surface-800" title="Decrease font size" onClick={() => setFontSize((s) => Math.max(9, s - 1))}>
          <Minus size={14} />
        </button>
        <button type="button" className="p-1 rounded text-surface-400 hover:text-white hover:bg-surface-800" title="Increase font size" onClick={() => setFontSize((s) => Math.min(20, s + 1))}>
          <Plus size={14} />
        </button>
        <button type="button" className="p-1 rounded text-surface-400 hover:text-white hover:bg-surface-800" title="Download session log" onClick={downloadLog}>
          <Download size={14} />
        </button>
        <button type="button" className="p-1 rounded text-surface-400 hover:text-white hover:bg-surface-800" title={fullscreen ? 'Exit full screen' : 'Full screen'} onClick={() => setFullscreen((f) => !f)}>
          {fullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
        </button>
      </div>
      <div className={`flex-1 min-h-0 grid ${split ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1'}`}>
        <div ref={mountRef} className="min-h-0 p-0.5 touch-manipulation" style={{ background: activeProfile.theme.background }} />
        {split && (
          <div className="min-h-0 border-t md:border-t-0 md:border-l border-surface-800 bg-surface-950 p-3 font-mono text-xs text-surface-300 overflow-auto">
            <div className="flex items-center gap-2 text-accent-cyan mb-2">
              <TerminalIcon size={14} /> Split terminal reference
            </div>
            <div className="text-surface-500 mb-3">Active profile: {activeProfile.label}</div>
            <pre className="whitespace-pre-wrap leading-5">{[
              `${activeProfile.prompt} # examples`,
              activeTab.profileKey === 'powershell' ? 'Get-Service | Where-Object Status -eq Stopped' : null,
              activeTab.profileKey === 'cmd' ? 'ipconfig /all' : null,
              activeTab.profileKey === 'esxi' ? 'esxcli network ip interface list' : null,
              activeTab.profileKey === 'terraform' ? 'terraform plan' : null,
              activeTab.profileKey === 'ansible' ? 'ansible-inventory --list' : null,
              activeTab.profileKey === 'kubectl' ? 'kubectl get pods -A' : null,
              activeTab.profileKey === 'linux' ? 'systemctl status nginx' : null,
              'clear    # clear screen',
              'Tab      # backend shell completion',
              '↑ / ↓    # command history',
            ].filter(Boolean).join('\n')}</pre>
          </div>
        )}
      </div>
    </div>
  )
}

function terminalPropsEqual(prev, next) {
  if (prev.sessionId !== next.sessionId || prev.hostKey !== next.hostKey) return false
  if (prev.layoutKey !== next.layoutKey || prev.className !== next.className) return false
  if (prev.label !== next.label || prev.welcomeHint !== next.welcomeHint) return false
  if (prev.isMobile !== next.isMobile) return false
  if (prev.blockedCommands !== next.blockedCommands) return false
  const ps = prev.session
  const ns = next.session
  if (ps === ns) return true
  if (!ps || !ns) return ps === ns
  return ps.status === ns.status
    && ps.provider === ns.provider
    && ps.container_id === ns.container_id
    && ps.instance_id === ns.instance_id
}

export default memo(forwardRef(LabTerminal), terminalPropsEqual)
