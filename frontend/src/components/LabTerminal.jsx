import { useEffect, useRef, useState, useCallback, memo, forwardRef, useImperativeHandle } from 'react'
import { useAuthStore } from '../store/authStore'

const WS_NO_RECONNECT = new Set([1000, 4001, 4003, 4004, 4005, 4008, 4500])

const WS_CLOSE_MESSAGES = {
  4001: '\r\n\x1b[1;31mAuthentication expired — refresh the page to reconnect.\x1b[0m\r\n',
  4003: '\r\n\x1b[1;33mLab is not running yet — wait for provisioning to finish.\x1b[0m\r\n',
  4004: '\r\n\x1b[1;31mLab session not found.\x1b[0m\r\n',
  4005: '\r\n\x1b[1;31mLab environment not ready — try again in a few seconds.\x1b[0m\r\n',
  4008: '\r\n\x1b[1;31mToo many terminal tabs open — close another tab and refresh.\x1b[0m\r\n',
  4500: '\r\n\x1b[1;31mCould not connect to lab shell.\x1b[0m\r\n',
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
        fontSize: isMobileRef.current ? 10 : 13,
        lineHeight: 1.2,
        fontFamily: '"JetBrains Mono", "Fira Code", monospace',
        theme: {
          background: '#020617',
          foreground: '#e2e8f0',
          cursor: '#06b6d4',
          selectionBackground: '#334155',
        },
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
      const resizeDebounceRef = { current: null }

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
        const hostQ = hostKey && hostKey !== 'primary' ? `&host=${encodeURIComponent(hostKey)}` : ''
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
        }
        const ws = new WebSocket(buildWsUrl())
        wsRef.current = ws
        ws.onopen = () => {
          reconnectAttempts.current = 0
          shellReadyRef.current = false
          onReady?.()
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
          if (disposed || e.code === 1000) return
          if (WS_NO_RECONNECT.has(e.code)) {
            term.write(WS_CLOSE_MESSAGES[e.code] || '\r\n\x1b[1;31mConnection closed.\x1b[0m\r\n')
            if (e.code === 4500) {
              bindEnterRetry('\x1b[1;33mPress Enter to retry connection...\x1b[0m\r\n')
            }
            return
          }
          const isSim = session?.provider === 'simulation'
          const max1006Retries = isSim ? 4 : 3
          if (e.code === 1006 && reconnectAttempts.current < max1006Retries) {
            reconnectAttempts.current++
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current - 1), 8000)
            if (reconnectAttempts.current >= max1006Retries) {
              bindEnterRetry('\r\n\x1b[1;33mConnection paused — press Enter to reconnect\x1b[0m\r\n')
              return
            }
            term.write('\r\n\x1b[1;33mConnection interrupted — retrying...\x1b[0m\r\n')
            reconnectTimerRef.current = setTimeout(connectWs, delay)
            return
          }
          if (reconnectAttempts.current < maxReconnectAttempts) {
            reconnectAttempts.current++
            const cap = isSim ? 3 : maxReconnectAttempts
            if (isSim && reconnectAttempts.current > 3) {
              bindEnterRetry('\r\n\x1b[1;33mAI Lab shell paused — press Enter to reconnect\x1b[0m\r\n')
              return
            }
            if (reconnectAttempts.current >= cap) {
              bindEnterRetry('\r\n\x1b[1;31mConnection lost.\x1b[0m Press Enter to retry.\x1b[0m\r\n')
              return
            }
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current - 1), 30000)
            if (!isSim) {
              term.write(`\r\n\x1b[1;33mReconnecting in ${Math.round(delay / 1000)}s... (${reconnectAttempts.current}/${maxReconnectAttempts})\x1b[0m\r\n`)
            }
            reconnectTimerRef.current = setTimeout(connectWs, delay)
          } else {
            bindEnterRetry('\r\n\x1b[1;31mConnection lost after multiple attempts.\x1b[0m\r\n')
          }
        }
      }
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
        if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
        if (resizeDebounceRef.current) clearTimeout(resizeDebounceRef.current)
        ro?.disconnect()
        window.removeEventListener('resize', handleWindowResize)
        wsRef.current?.close(1000)
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

  return (
    <div className={`flex flex-col min-h-0 min-w-0 ${className}`}>
      {label && (
        <div className="shrink-0 px-2 py-1 text-[10px] sm:text-xs font-medium text-accent-cyan border-b border-surface-800 bg-surface-900/90">
          {label}
        </div>
      )}
      <div ref={mountRef} className="flex-1 min-h-0 p-0.5 touch-manipulation" />
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
