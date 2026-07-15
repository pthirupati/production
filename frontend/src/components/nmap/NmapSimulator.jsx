import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Radar, Terminal, Play, RefreshCw,
  XCircle, AlertTriangle, Server, ShieldAlert, Target, CheckCircle2,
  History, Network, Crosshair, X, Copy, Download, Search, HelpCircle,
  GitCompare, FileCode2, Info, Cpu, Monitor, Router, Apple,
} from 'lucide-react'
import { nmapApi } from '../../api/nmap'
import { LabChromeControls } from '../lab/LabChromeBar'

/* ── scoped, self-contained "security tool" chrome (no shared CSS) ── */
const SCAN_PROFILES = [
  { id: 'intense', label: 'Intense scan', flags: ['-T4', '-A', '-v'], ports: '', desc: '-T4 -A -v' },
  { id: 'intense-udp', label: 'Intense scan plus UDP', flags: ['-sS', '-sU', '-T4', '-A', '-v'], ports: '', desc: '-sS -sU -T4 -A -v' },
  { id: 'intense-all', label: 'Intense scan, all TCP ports', flags: ['-T4', '-A', '-v'], ports: '1-65535', desc: '-p 1-65535 -T4 -A -v' },
  { id: 'intense-noping', label: 'Intense scan, no ping', flags: ['-T4', '-A', '-v', '-Pn'], ports: '', desc: '-T4 -A -v -Pn' },
  { id: 'ping', label: 'Ping scan', flags: ['-sn'], ports: '', desc: '-sn' },
  { id: 'quick', label: 'Quick scan', flags: ['-T4', '-F'], ports: '', desc: '-T4 -F' },
  { id: 'quick-plus', label: 'Quick scan plus', flags: ['-sV', '-T4', '-O', '-F', '--version-light'], ports: '', desc: '-sV -T4 -O -F --version-light' },
  { id: 'quick-traceroute', label: 'Quick traceroute', flags: ['-sn', '--traceroute'], ports: '', desc: '-sn --traceroute' },
  { id: 'regular', label: 'Regular scan', flags: [], ports: '', desc: 'Default Nmap scan' },
  { id: 'slow-comprehensive', label: 'Slow comprehensive scan', flags: ['-sS', '-sU', '-T4', '-A', '-v', '-PE', '-PP', '-PS80,443', '-PA3389', '-PU40125', '-g', '53', '--script', 'default or (discovery and safe)'], ports: '', desc: 'Comprehensive discovery + safe NSE scripts' },
  { id: 'custom', label: 'Custom', flags: ['-sV'], ports: '', desc: 'Editable command' },
]

const NM_MENUS = [
  ['Scan', ['New Window', 'Open Scan', 'Save Scan', 'Print', 'Close']],
  ['Tools', ['Compare Results', 'Search Scan Results', 'NSE Scripts Browser', 'Command Wizard']],
  ['Profile', ['New Profile', 'Edit Selected Profile', 'Delete Selected Profile']],
  ['Help', ['Nmap Reference Guide', 'Nmap Online Documentation', 'Zenmap User Guide', 'About']],
]

const NSE_CATEGORIES = ['auth', 'broadcast', 'brute', 'default', 'discovery', 'dos', 'exploit', 'external', 'fuzzer', 'intrusive', 'malware', 'safe', 'version', 'vuln']
const NSE_SCRIPTS = [
  ['http-title', 'default,safe', 'Shows the title of the default HTTP page.'],
  ['ssl-cert', 'default,safe', 'Retrieves SSL certificate information.'],
  ['ssh2-enum-algos', 'safe,discovery', 'Reports supported SSH algorithms.'],
  ['smb-os-discovery', 'safe,discovery', 'Attempts to determine OS information over SMB.'],
  ['vulners', 'vuln,external', 'Maps service versions to known vulnerabilities.'],
  ['dns-zone-transfer', 'intrusive,discovery', 'Attempts AXFR zone transfer checks.'],
]

const SCOPED_CSS = `
.nmap-sim {
  --nm-bg: #0a0f0a;
  --nm-panel: #0e160e;
  --nm-panel-2: #111b11;
  --nm-border: #1d2d1d;
  --nm-text: #cfeccf;
  --nm-muted: #7da37d;
  --nm-green: #4ade80;
  --nm-cyan: #38e0d0;
  --nm-amber: #f5c451;
  --nm-red: #ff6b6b;
  color: var(--nm-text);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  background: var(--nm-bg);
  min-height: 100%;
}
.nmap-sim .nm-topbar {
  display: flex; align-items: center; justify-content: space-between; gap: 0.75rem;
  padding: 0.6rem 1rem; background: #070b07; border-bottom: 1px solid var(--nm-border);
  position: sticky; top: 0; z-index: 10;
}
.nmap-sim .nm-menubar {
  display: flex; align-items: center; gap: .15rem; padding: .28rem .85rem;
  background: #0d140d; border-bottom: 1px solid var(--nm-border); position: sticky; top: 45px; z-index: 9;
}
.nmap-sim .nm-menu-btn {
  position: relative; border: 1px solid transparent; background: transparent; color: var(--nm-text);
  font-size: .78rem; padding: .28rem .55rem; border-radius: 4px; cursor: pointer;
}
.nmap-sim .nm-menu-btn:hover, .nmap-sim .nm-menu-btn.nm-on { background: #132013; border-color: var(--nm-border); }
.nmap-sim .nm-menu-pop {
  position: absolute; top: calc(100% + 2px); left: 0; min-width: 230px; max-height: 380px; overflow-y: auto;
  background: #f8fafc; color: #111827; border: 1px solid #cbd5e1; border-radius: 4px;
  box-shadow: 0 18px 40px rgba(0,0,0,.35); padding: .25rem; z-index: 40;
}
.nmap-sim .nm-menu-item {
  width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  padding: .35rem .55rem; border-radius: 3px; font-size: .74rem; white-space: nowrap;
}
.nmap-sim .nm-menu-item:hover { background: #dcfce7; }
.nmap-sim .nm-btn {
  display: inline-flex; align-items: center; gap: 0.4rem; border-radius: 6px;
  padding: 0.45rem 0.8rem; font-size: 0.8rem; font-weight: 600; cursor: pointer;
  border: 1px solid var(--nm-border); background: #132013; color: var(--nm-text);
  transition: background 0.12s, filter 0.12s;
}
.nmap-sim .nm-btn:hover { background: #1a2b1a; }
.nmap-sim .nm-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.nmap-sim .nm-btn-primary {
  border: none; background: var(--nm-green); color: #03210f;
}
.nmap-sim .nm-btn-primary:hover { filter: brightness(1.08); }
.nmap-sim .nm-input {
  background: #060a06; border: 1px solid var(--nm-border); border-radius: 6px;
  padding: 0.55rem 0.7rem; color: var(--nm-text); font-size: 0.85rem; outline: none;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
}
.nmap-sim .nm-input:focus { border-color: var(--nm-green); box-shadow: 0 0 0 2px rgba(74,222,128,.18); }
.nmap-sim .nm-card {
  background: var(--nm-panel); border: 1px solid var(--nm-border); border-radius: 8px;
}
.nmap-sim .nm-chip {
  display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.72rem; font-weight: 600;
  padding: 0.2rem 0.55rem; border-radius: 6px; cursor: pointer; white-space: nowrap;
  border: 1px solid var(--nm-border); background: #0c140c; color: var(--nm-muted);
  font-family: 'JetBrains Mono', ui-monospace, monospace;
}
.nmap-sim .nm-chip:hover { color: var(--nm-text); border-color: var(--nm-green); }
.nmap-sim .nm-chip-active { color: #03210f; background: var(--nm-green); border-color: var(--nm-green); }
.nmap-sim .nm-tab {
  padding: 0.35rem 0.8rem; border-radius: 6px; font-size: 0.8rem; cursor: pointer;
  color: var(--nm-muted); border: 1px solid transparent; white-space: nowrap;
}
.nmap-sim .nm-tab:hover { color: var(--nm-text); background: #111b11; }
.nmap-sim .nm-tab-active { color: var(--nm-text); background: #132013; border-color: var(--nm-border); }
.nmap-sim .nm-table { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
.nmap-sim .nm-table th {
  text-align: left; color: var(--nm-muted); font-weight: 600; padding: 0.45rem 0.65rem;
  border-bottom: 1px solid var(--nm-border); position: sticky; top: 0; background: var(--nm-panel-2);
}
.nmap-sim .nm-table td { padding: 0.45rem 0.65rem; border-bottom: 1px solid #152015; }
.nmap-sim .nm-table tr:hover td { background: #0f190f; }
.nmap-sim .nm-mono { font-family: 'JetBrains Mono', ui-monospace, monospace; }
.nmap-sim .nm-badge {
  display: inline-flex; align-items: center; font-size: 0.66rem; font-weight: 700;
  padding: 0.12rem 0.45rem; border-radius: 999px; letter-spacing: 0.02em;
}
.nmap-sim .nm-b-open { background: rgba(74,222,128,.16); color: var(--nm-green); }
.nmap-sim .nm-b-closed { background: rgba(125,163,125,.16); color: var(--nm-muted); }
.nmap-sim .nm-b-filtered { background: rgba(245,196,81,.16); color: var(--nm-amber); }
.nmap-sim .nm-b-up { background: rgba(56,224,208,.16); color: var(--nm-cyan); }
.nmap-sim .nm-console {
  font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 0.76rem;
  background: #050805; border: 1px solid var(--nm-border); border-radius: 8px;
  padding: 0.7rem 0.85rem; color: #b6e3b6; white-space: pre-wrap; word-break: break-word;
  line-height: 1.5;
}
.nmap-sim .nm-banner {
  display: flex; align-items: flex-start; gap: 0.5rem; font-size: 0.8rem;
  padding: 0.6rem 0.85rem; border-radius: 8px; margin-bottom: 0.85rem;
}
.nmap-sim .nm-banner-goal { background: rgba(56,224,208,.08); border: 1px solid rgba(56,224,208,.28); color: #9beee3; }
.nmap-sim .nm-banner-err { background: rgba(255,107,107,.1); border: 1px solid rgba(255,107,107,.3); color: #ffb4b4; }
.nmap-sim .nm-sidebar {
  background: #081008; border: 1px solid var(--nm-border); border-radius: 8px; overflow: hidden;
}
.nmap-sim .nm-sidebar-head {
  padding: .5rem .7rem; font-size: .68rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: .08em; color: var(--nm-muted); background: #101a10; border-bottom: 1px solid var(--nm-border);
}
.nmap-sim .nm-side-row {
  width: 100%; display: flex; align-items: center; gap: .5rem; padding: .45rem .65rem;
  color: var(--nm-muted); font-size: .76rem; border-bottom: 1px solid #122012; cursor: pointer;
}
.nmap-sim .nm-side-row:hover, .nmap-sim .nm-side-row.nm-active { background: #132013; color: var(--nm-text); }
.nmap-sim .nm-topology {
  position: relative; height: 380px; background:
    radial-gradient(circle at center, rgba(74,222,128,.08), transparent 55%),
    repeating-radial-gradient(circle at center, transparent 0 72px, rgba(74,222,128,.12) 73px 74px);
  border: 1px solid var(--nm-border); border-radius: 8px; overflow: hidden;
}
.nmap-sim .nm-node {
  position: absolute; transform: translate(-50%, -50%); min-width: 76px; text-align: center;
  color: var(--nm-text); font-size: .7rem; cursor: pointer;
}
.nmap-sim .nm-node-icon {
  margin: 0 auto .25rem; width: 38px; height: 38px; border-radius: 999px;
  display: flex; align-items: center; justify-content: center; border: 1px solid rgba(74,222,128,.35);
  background: #102010; box-shadow: 0 0 20px rgba(74,222,128,.15);
}
.nmap-sim .nm-modal-backdrop {
  position: fixed; inset: 0; z-index: 60; background: rgba(0,0,0,.65);
  display: flex; align-items: center; justify-content: center; padding: 1rem;
}
.nmap-sim .nm-modal {
  width: min(900px, 96vw); max-height: 86vh; overflow: hidden; display: flex; flex-direction: column;
  background: #f8fafc; color: #111827; border: 1px solid #cbd5e1; border-radius: 8px;
  box-shadow: 0 28px 80px rgba(0,0,0,.45);
}
.nmap-sim .nm-modal-head {
  display: flex; align-items: center; justify-content: space-between; padding: .65rem .85rem;
  background: #dcfce7; border-bottom: 1px solid #bbf7d0;
}
.nmap-sim .nm-modal-body { padding: .85rem; overflow: auto; }
`

function StateBadge({ state }) {
  const cls = state === 'open' ? 'nm-b-open' : state === 'filtered' ? 'nm-b-filtered' : 'nm-b-closed'
  return <span className={`nm-badge ${cls}`}>{(state || 'closed').toUpperCase()}</span>
}

function NmapModal({ title, children, onClose }) {
  return (
    <div className="nm-modal-backdrop" onMouseDown={onClose}>
      <div className="nm-modal" onMouseDown={(e) => e.stopPropagation()}>
        <div className="nm-modal-head">
          <div className="font-semibold">{title}</div>
          <button type="button" className="p-1 rounded hover:bg-green-100" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="nm-modal-body">{children}</div>
      </div>
    </div>
  )
}

function hostIcon(host) {
  const os = String(host?.os || host?.hostname || '').toLowerCase()
  if (os.includes('windows')) return Monitor
  if (os.includes('mac') || os.includes('darwin')) return Apple
  if (os.includes('router') || os.includes('gateway')) return Router
  return Server
}

function nmapOutput(scan, activeHost) {
  if (!scan) return 'Starting Nmap 7.94SVN at 2026-06-28 12:37 IST\nNo scan has been executed yet.'
  const hosts = scan.hosts || []
  const blocks = hosts.map((h) => {
    const ports = (h.ports || []).map((p) => {
      const version = [p.product, p.version].filter(Boolean).join(' ')
      return `${String(p.port).padEnd(8)}/${(p.proto || 'tcp').padEnd(4)} ${String(p.state || 'closed').padEnd(9)} ${String(p.service || 'unknown').padEnd(12)} ${version}`.trimEnd()
    }).join('\n')
    const selected = activeHost?.ip === h.ip ? ' [selected]' : ''
    return [
      `Nmap scan report for ${h.hostname ? `${h.hostname} (${h.ip})` : h.ip}${selected}`,
      `Host is ${h.state || 'up'} (${h.latency || '0.0032s'} latency).`,
      h.mac ? `MAC Address: ${h.mac}${h.vendor ? ` (${h.vendor})` : ''}` : null,
      ports ? 'PORT      STATE     SERVICE      VERSION' : 'All 1000 scanned ports are closed or filtered',
      ports || null,
      h.os ? `OS details: ${h.os}${h.os_accuracy ? ` (${h.os_accuracy}% accuracy)` : ''}` : null,
      'Network Distance: 1 hop',
      h.traceroute ? ['TRACEROUTE', 'HOP RTT      ADDRESS', ...(h.traceroute || []).map((r) => `${r.ttl || 1}   ${r.rtt || '0.45ms'}  ${r.address || h.ip}`)].join('\n') : null,
    ].filter(Boolean).join('\n')
  }).join('\n\n')
  return [
    `Starting Nmap 7.94SVN at 2026-06-28 12:37 IST`,
    blocks,
    '',
    `Nmap done: ${scan.addresses_scanned || hosts.length} IP address${(scan.addresses_scanned || hosts.length) === 1 ? '' : 'es'} (${scan.hosts_up || hosts.filter((h) => h.state === 'up').length} host${(scan.hosts_up || hosts.length) === 1 ? '' : 's'} up) scanned in ${scan.duration || '8.42'} seconds`,
  ].join('\n')
}

/**
 * Nmap network-scan simulator. Rendered INLINE by LabRunner for nmap labs
 * (simulation_type 'nmap' / technology.slug 'nmap') — no new route. The learner
 * crafts scans (targets + flags), reads back discovered hosts / ports / versions
 * / OS, then runs Check Solution (graded by validate_nmap_lab via the engine).
 */
export default function NmapSimulator({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
}) {
  const slug = scenario?.slug || ''
  const [state, setState] = useState(null)
  const [error, setError] = useState('')
  const [profile, setProfile] = useState('quick')
  const [targets, setTargets] = useState('')
  const [ports, setPorts] = useState('')
  const [flags, setFlags] = useState(new Set(['-sV']))
  const [sudo, setSudo] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [lastScan, setLastScan] = useState(null)
  const [tab, setTab] = useState('output') // output | ports | topology | details | scans
  const [outputMode, setOutputMode] = useState('normal')
  const [menuOpen, setMenuOpen] = useState(null)
  const [modal, setModal] = useState(null)
  const [scriptCategory, setScriptCategory] = useState('default')
  const [selectedHost, setSelectedHost] = useState(null)
  const [progressLines, setProgressLines] = useState([]) // live nmap progress feed while scanning
  const [scanProgress, setScanProgress] = useState(0)     // 0..100 for the progress bar
  const [portFilter, setPortFilter] = useState('')        // Search Scan Results → filters the ports table
  const [topoZoom, setTopoZoom] = useState(1)             // functional topology zoom (replaces decorative buttons)
  const pollRef = useRef(null)
  const streamTimersRef = useRef([])   // setTimeout ids for the progressive reveal
  const streamingRef = useRef(false)   // true while a scan animation is in flight (pauses poll clobber)

  const load = useCallback(async () => {
    try {
      const data = await nmapApi.getState(sessionId, slug)
      setState(data)
      setError('')
      // Seed the targets box with the subnet so the learner has a sensible start.
      if (!targets && data?.inventory?.subnet) setTargets(data.inventory.subnet)
    } catch {
      setError('Could not load the Nmap simulator')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, slug])

  useEffect(() => {
    load()
    // The 20s aggregate poll must NOT clobber an in-progress scan reveal, so it
    // no-ops while the progressive stream is running (streamScan calls load()
    // itself once the reveal completes).
    pollRef.current = setInterval(() => { if (!streamingRef.current) load() }, 20000)
    return () => clearInterval(pollRef.current)
  }, [load])

  // Abort any pending reveal timers if the component unmounts mid-scan.
  useEffect(() => () => {
    streamTimersRef.current.forEach(clearTimeout)
    streamTimersRef.current = []
  }, [])

  const toggleFlag = (f) => {
    setFlags(prev => {
      const next = new Set(prev)
      if (next.has(f)) next.delete(f)
      else {
        next.add(f)
        // mutually-exclusive scan types: keep the UI honest.
        if (f === '-sn') { next.delete('-sS'); next.delete('-sT'); next.delete('-sV'); next.delete('-O'); next.delete('-A') }
        if (['-sS', '-sT'].includes(f)) { next.delete('-sn'); ;['-sS', '-sT'].filter(x => x !== f).forEach(x => next.delete(x)) }
        if (['-sS', '-sT', '-sV', '-O', '-A'].includes(f)) next.delete('-sn')
      }
      return next
    })
  }

  const command = useMemo(() => {
    const fl = Array.from(flags)
    const parts = []
    if (sudo) parts.push('sudo')
    parts.push('nmap')
    if (fl.length) parts.push(fl.join(' '))
    if (ports.trim()) parts.push(`-p ${ports.trim()}`)
    parts.push(targets.trim() || '<targets>')
    return parts.join(' ')
  }, [flags, ports, sudo, targets])

  // Cancel any in-flight progressive-reveal timers and stop the streaming state.
  const clearStream = useCallback(() => {
    streamTimersRef.current.forEach(clearTimeout)
    streamTimersRef.current = []
    streamingRef.current = false
  }, [])

  // Build the sequence of realistic nmap "process" log lines for a scan result,
  // scaled by the backend-authoritative duration. Returns [{ text }] steps that
  // the reveal loop paces out; the final host output is appended by the caller.
  const buildProgressPlan = useCallback((scan) => {
    const caps = scan?.caps || {}
    const hostCount = scan?.host_count ?? (scan?.addresses_scanned || 1)
    const upCount = scan?.hosts_up ?? (scan?.hosts || []).length
    const ts = new Date().toTimeString().slice(0, 5)
    const isPing = scan?.scan_type === 'ping_sweep'
    const isSyn = !!(caps.syn_scan) && !!scan?.sudo
    const isConnect = !!caps.connect_scan
    const scanLabel = isSyn ? 'SYN Stealth Scan' : isConnect ? 'Connect Scan' : 'SYN Stealth Scan'

    const lines = []
    lines.push(`Starting Nmap 7.94SVN ( https://nmap.org ) at ${ts}`)
    lines.push(`Initiating Ping Scan at ${ts}`)
    lines.push(`Scanning ${hostCount} host${hostCount === 1 ? '' : 's'} [${isPing ? '2' : '1'} port${isPing ? 's' : ''}/host]`)
    lines.push(`Completed Ping Scan at ${ts}, ${(scan?.duration ? Math.max(0.4, scan.duration * 0.12) : 0.6).toFixed(2)}s elapsed (${hostCount} total hosts)`)
    if (!isPing) {
      lines.push(`Initiating Parallel DNS resolution of ${hostCount} host${hostCount === 1 ? '' : 's'}.`)
      lines.push(`Initiating ${scanLabel} at ${ts}`)
      lines.push(`Scanning ${upCount || hostCount} host${(upCount || hostCount) === 1 ? '' : 's'} [${scan?.port_count ?? 1000} ports]`)
      // Mid-scan timing estimates (the "About X% done; ETC ..." heartbeat).
      lines.push({ pct: 33, text: `${scanLabel} Timing: About 33.00% done; ETC: ${ts} (${(scan?.duration ? scan.duration * 0.66 : 5).toFixed(0)}s remaining)` })
      lines.push({ pct: 68, text: `${scanLabel} Timing: About 68.00% done; ETC: ${ts} (${(scan?.duration ? scan.duration * 0.31 : 2).toFixed(0)}s remaining)` })
      lines.push(`Completed ${scanLabel} at ${ts}, ${(scan?.duration ? scan.duration * 0.7 : 4).toFixed(2)}s elapsed`)
      if (caps.version) {
        lines.push(`Initiating Service scan at ${ts}`)
        lines.push(`Scanning ${scan?.port_count ?? 'several'} services on ${upCount || hostCount} host${(upCount || hostCount) === 1 ? '' : 's'}`)
      }
      if (caps.os_detect && scan?.sudo) {
        lines.push(`Initiating OS detection (try #1) against ${upCount || hostCount} host${(upCount || hostCount) === 1 ? '' : 's'}`)
      }
    }
    if (scan?.warning) lines.push(scan.warning)
    return lines.map((l) => (typeof l === 'string' ? { text: l } : l))
  }, [])

  // Progressively reveal the scan: stream the process log lines paced to the
  // backend duration, then flip lastScan on so the tables/output render. This
  // is DISPLAY ONLY — the engine already recorded discovery when scan() resolved.
  const streamScan = useCallback((scan) => {
    clearStream()
    streamingRef.current = true
    setProgressLines([])
    setScanProgress(0)
    setTab('output')

    const plan = buildProgressPlan(scan)
    // Total wall-clock the animation should span, capped so the UI never feels
    // stuck (a 4-minute full-range sweep animates in a watchable ~8s window).
    const total = Math.min(Math.max((scan?.duration || 2) * 1000, 900), 8000)
    const step = total / (plan.length + 1)

    plan.forEach((entry, idx) => {
      const t = setTimeout(() => {
        setProgressLines((prev) => [...prev, entry.text])
        setScanProgress(entry.pct != null ? entry.pct : Math.round(((idx + 1) / (plan.length + 1)) * 100))
      }, Math.round(step * (idx + 1)))
      streamTimersRef.current.push(t)
    })

    // Final tick: reveal the parsed results and end the "process".
    const done = setTimeout(() => {
      setScanProgress(100)
      setLastScan(scan)
      const firstUp = (scan.hosts || []).find(h => h.state === 'up') || scan.hosts?.[0]
      setSelectedHost(firstUp?.ip || null)
      streamingRef.current = false
      setScanning(false)
      // Refresh aggregate KPIs/history now that the reveal is complete (deferred
      // so an early poll can't clobber the in-progress stream).
      load()
    }, Math.round(total))
    streamTimersRef.current.push(done)
  }, [buildProgressPlan, clearStream, load])

  const runScan = useCallback(async () => {
    if (scanning) return
    if (!targets.trim()) { setError('Enter a target (IP, CIDR, range, hostname, or "all")'); return }
    clearStream()
    setScanning(true)
    setError('')
    setLastScan(null)      // clear the previous result so the stream reads as a fresh run
    setProgressLines(['Starting Nmap 7.94SVN ...'])
    setScanProgress(0)
    setTab('output')
    try {
      const res = await nmapApi.scan(sessionId, {
        targets: targets.trim(),
        flags: Array.from(flags),
        ports: ports.trim() || undefined,
        sudo,
      })
      if (res?.ok === false) {
        setError(res.error || res.message || 'Scan rejected')
        setScanning(false)
        clearStream()
      } else if (res?.scan) {
        // The engine has already recorded discovery; now defer the DISPLAY,
        // streaming the process feel paced to the backend-authoritative duration.
        streamScan(res.scan)
      } else {
        setScanning(false)
        clearStream()
        load()
      }
    } catch {
      setError('Scan failed — try again')
      setScanning(false)
      clearStream()
    }
  }, [scanning, targets, flags, ports, sudo, sessionId, load, clearStream, streamScan])

  // Cancel an in-flight scan: abort the reveal timers (nmap's Ctrl-C feel).
  const cancelScan = useCallback(() => {
    clearStream()
    setScanning(false)
    setProgressLines((prev) => [...prev, '', 'Scan aborted by user (caught SIGINT).'])
    setScanProgress(0)
  }, [clearStream])

  const resetSession = useCallback(async () => {
    clearStream()
    setScanning(false)
    setProgressLines([])
    setScanProgress(0)
    setPortFilter('')
    try { await nmapApi.action(sessionId, 'reset', {}) } catch { /* ignore */ }
    setLastScan(null)
    setSelectedHost(null)
    load()
  }, [sessionId, load, clearStream])

  // Stop/start a listening service on a host. The port's state changes on the
  // network after a short wall-clock delay (modelled server-side), so a re-scan
  // is required to observe it — mirroring real socket teardown/bind latency.
  const serviceControl = useCallback(async (ip, port, action) => {
    try {
      await nmapApi.action(sessionId, action, { ip, port })
    } catch { /* ignore — surfaced via reload */ }
    load()
  }, [sessionId, load])

  const summary = state?.summary || {}
  const inventory = state?.inventory || {}
  const goal = state?.goal || {}
  const pendingTransitions = state?.pending_transitions || []
  const firewall = inventory.firewall
  const scanHosts = useMemo(() => lastScan?.hosts || [], [lastScan])
  const activeHost = scanHosts.find(h => h.ip === selectedHost) || scanHosts[0] || null
  const allPorts = scanHosts.flatMap((h) => (h.ports || []).map((p) => ({ ...p, host: h.ip, hostname: h.hostname })))
  const services = [...new Set(allPorts.map((p) => p.service).filter(Boolean))]
  // Search Scan Results → substring match across host/port/state/service/version.
  const filteredPorts = useMemo(() => {
    const q = portFilter.trim().toLowerCase()
    if (!q) return allPorts
    return allPorts.filter((p) => [
      p.host, p.hostname, String(p.port), p.proto, p.state, p.service, p.product, p.version,
    ].filter(Boolean).some((v) => String(v).toLowerCase().includes(q)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [portFilter, lastScan, selectedHost])
  const rawOutput = nmapOutput(lastScan, activeHost)

  // Render the scan output in a given format (shared by the on-screen console
  // and the Save Output download so both stay identical).
  const formatOutput = useCallback((mode) => {
    if (mode === 'xml') {
      return `<nmaprun scanner="nmap" args="${command}">\n${scanHosts.map((h) => `  <host><status state="${h.state || 'up'}"/><address addr="${h.ip}" addrtype="ipv4"/></host>`).join('\n')}\n</nmaprun>`
    }
    if (mode === 'grepable') {
      return scanHosts.map((h) => `Host: ${h.ip} (${h.hostname || ''})\tStatus: ${h.state || 'up'}\tPorts: ${(h.ports || []).map((p) => `${p.port}/${p.state}/${p.proto || 'tcp'}/${p.service || ''}/`).join(', ')}`).join('\n')
    }
    if (mode === 'script-kiddie') {
      return rawOutput.replace(/[aeios]/gi, (m) => ({ a: '4', e: '3', i: '1', o: '0', s: '5' }[m.toLowerCase()] || m))
    }
    return rawOutput
  }, [command, scanHosts, rawOutput])

  // Save Output → actually download the current scan via a Blob (no server round
  // trip). File extension mirrors nmap's -oN/-oX/-oG/-oS output selectors.
  const downloadOutput = useCallback((mode) => {
    const ext = mode === 'xml' ? 'xml' : mode === 'grepable' ? 'gnmap' : 'nmap'
    const body = formatOutput(mode)
    const blob = new Blob([body], { type: mode === 'xml' ? 'application/xml' : 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `nmap-scan-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '')}.${ext}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }, [formatOutput])

  const FLAG_OPTS = [
    ['-sn', 'Ping sweep'], ['-sS', 'SYN (sudo)'], ['-sT', 'Connect'],
    ['-sV', 'Version'], ['-O', 'OS (sudo)'], ['-A', 'Aggressive'], ['-Pn', 'Skip discovery'], ['--traceroute', 'Traceroute'],
  ]

  const handleMenu = (item) => {
    setMenuOpen(null)
    if (item === 'NSE Scripts Browser') setModal('nse')
    else if (item === 'Compare Results') setModal('compare')
    else if (item === 'Command Wizard') setModal('wizard')
    else if (item === 'About') setModal('about')
    else if (item === 'Search Scan Results') setModal('search')
    else if (item === 'Save Scan') setModal('save')
  }

  return (
    <div className={`nmap-sim ${embedded ? 'h-full min-h-0 flex flex-col overflow-hidden' : 'min-h-screen'}`}>
      <style>{SCOPED_CSS}</style>

      <div className="nm-topbar">
        <div className="flex items-center gap-3 min-w-0">
          <Radar size={18} style={{ color: 'var(--nm-green)' }} />
          <span className="font-semibold text-white">Nmap scanner</span>
          <span className="text-xs hidden sm:inline" style={{ color: 'var(--nm-muted)' }}>{scenario?.title || slug}</span>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <button className="nm-btn" onClick={load}><RefreshCw size={13} /> Refresh</button>
          <button className="nm-btn" onClick={resetSession}><History size={13} /> Reset</button>
          <LabChromeControls
            buttonClass="nm-btn"
            primaryClass="nm-btn nm-btn-primary"
            onHints={onHints}
            onCheck={onCheck}
            onExtend={onExtend}
            onStop={onStop}
            onBackToTerminal={onExit}
            hintsLabel={hintsLabel || 'Hints'}
            checkDisabled={checkDisabled}
            extendDisabled={extendDisabled}
          />
        </div>
      </div>

      <div className="nm-menubar" onMouseLeave={() => setMenuOpen(null)}>
        {NM_MENUS.map(([menu, items]) => (
          <div key={menu} className="relative">
            <button
              type="button"
              className={`nm-menu-btn ${menuOpen === menu ? 'nm-on' : ''}`}
              onClick={() => setMenuOpen(menuOpen === menu ? null : menu)}
              onMouseEnter={() => menuOpen && setMenuOpen(menu)}
            >
              {menu}
            </button>
            {menuOpen === menu && (
              <div className="nm-menu-pop">
                {items.map((item) => (
                  <button key={item} type="button" className="nm-menu-item" onClick={() => handleMenu(item)}>
                    <span>{item}</span><span className="text-slate-400">›</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="p-4 max-w-[1180px] mx-auto">
        {error && <div className="nm-banner nm-banner-err"><XCircle size={15} className="shrink-0 mt-0.5" /> {error}</div>}

        {/* objective banner */}
        {(goal.objective || goal.title) && (
          <div className="nm-banner nm-banner-goal">
            <Target size={15} className="shrink-0 mt-0.5" style={{ color: 'var(--nm-cyan)' }} />
            <span><b>{goal.title || 'Objective'}:</b> {goal.objective}</span>
          </div>
        )}

        {/* topology / KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
          {[
            ['Subnet', inventory.subnet || '—', 'var(--nm-cyan)', Network],
            ['Hosts up', `${summary.hosts_discovered ?? 0}/${summary.hosts_total ?? '?'}`, summary.hosts_discovered ? 'var(--nm-green)' : 'var(--nm-muted)', Server],
            ['Open ports', summary.open_ports_found ?? 0, summary.open_ports_found ? 'var(--nm-green)' : 'var(--nm-muted)', Crosshair],
            ['Versions', summary.versions_found ?? 0, 'var(--nm-text)', Terminal],
            ['Scans run', summary.scans_run ?? 0, 'var(--nm-text)', Radar],
          ].map(([label, val, color, Icon]) => (
            <div key={label} className="nm-card p-3">
              <div className="flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--nm-muted)' }}>
                <Icon size={12} /> {label}
              </div>
              <div className="text-lg font-bold mt-0.5 nm-mono" style={{ color }}>{val}</div>
            </div>
          ))}
        </div>

        {/* network context strip */}
        {(inventory.gateway || inventory.scanner_ip || firewall) && (
          <div className="flex flex-wrap items-center gap-2 mb-4 text-[11px]" style={{ color: 'var(--nm-muted)' }}>
            {inventory.scanner_ip && <span className="nm-chip" style={{ cursor: 'default' }}>scanner {inventory.scanner_ip}</span>}
            {inventory.gateway && <span className="nm-chip" style={{ cursor: 'default' }}>gateway {inventory.gateway}</span>}
            {firewall && (
              <span className="nm-chip" style={{ cursor: 'default', color: 'var(--nm-amber)', borderColor: 'rgba(245,196,81,.3)' }}>
                <ShieldAlert size={11} /> {firewall.name || 'firewall'} {firewall.ip || ''} {firewall.drops_icmp ? '· drops ICMP' : ''}
              </span>
            )}
          </div>
        )}

        {/* scan builder */}
        <div className="nm-card p-4 mb-4">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_260px_auto_auto] gap-3 items-end mb-3">
            <label className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--nm-muted)' }}>
              Target
              <input
                className="nm-input w-full mt-1"
                value={targets}
                spellCheck={false}
                placeholder="10.10.10.0/24  ·  10.10.10.20  ·  10.10.10.1-50  ·  all"
                onChange={e => setTargets(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') runScan() }}
              />
            </label>
            <label className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--nm-muted)' }}>
              Profile
              <select
                className="nm-input w-full mt-1"
                value={profile}
                onChange={(e) => {
                  const p = SCAN_PROFILES.find((sp) => sp.id === e.target.value)
                  setProfile(e.target.value)
                  if (p) { setFlags(new Set(p.flags)); setPorts(p.ports) }
                }}
              >
                {SCAN_PROFILES.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </label>
            <button className="nm-btn nm-btn-primary justify-center" disabled={scanning} onClick={runScan}>
              {scanning ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />} Scan
            </button>
            <button className="nm-btn justify-center" disabled={!scanning} onClick={cancelScan}>
              <XCircle size={14} /> Cancel
            </button>
          </div>
          <div className="flex flex-col lg:flex-row gap-3">
            <div className="w-full lg:w-56">
              <label className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--nm-muted)' }}>Ports (-p)</label>
              <input
                className="nm-input w-full mt-1"
                value={ports}
                spellCheck={false}
                placeholder="22,80,443  ·  1-1024"
                onChange={e => setPorts(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') runScan() }}
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 mt-3">
            {FLAG_OPTS.map(([f, label]) => (
              <button
                key={f}
                type="button"
                onClick={() => toggleFlag(f)}
                title={label}
                className={`nm-chip ${flags.has(f) ? 'nm-chip-active' : ''}`}
              >
                {f}
              </button>
            ))}
            <button
              type="button"
              onClick={() => setSudo(s => !s)}
              className={`nm-chip ${sudo ? 'nm-chip-active' : ''}`}
              title="Run as root — required for -sS SYN scan and -O OS detection"
            >
              sudo
            </button>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 mt-3">
            <div className="nm-console flex-1 !py-2 !text-[12px] flex items-center">
              <span style={{ color: 'var(--nm-green)' }}>$</span>&nbsp;{command}
            </div>
            <button className="nm-btn justify-center" onClick={() => navigator.clipboard?.writeText(command)}>
              <Copy size={13} /> Copy
            </button>
          </div>
        </div>

        {/* tabs */}
        <div className="flex items-center gap-2 mb-3">
          {[
            ['output', 'Nmap Output', Terminal],
            ['ports', 'Ports/Hosts', Crosshair],
            ['topology', 'Topology', Network],
            ['details', 'Host Details', Info],
            ['scans', 'Scans', History],
          ].map(([k, label, Icon]) => (
            <button key={k} onClick={() => setTab(k)} className={`nm-tab flex items-center gap-1.5 ${tab === k ? 'nm-tab-active' : ''}`}>
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>

        {!lastScan && !scanning && tab !== 'scans' ? (
          <div className="nm-card p-10 text-center text-sm" style={{ color: 'var(--nm-muted)' }}>
            <Radar size={26} className="mx-auto mb-2 opacity-50" />
            Build a scan above and press <b>Scan</b> to discover the network.
          </div>
        ) : null}

        {/* live scan process — progressive nmap log while the scan runs */}
        {scanning && tab === 'output' && (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <RefreshCw size={14} className="animate-spin" style={{ color: 'var(--nm-green)' }} />
              <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: '#0c140c', border: '1px solid var(--nm-border)' }}>
                <div className="h-full transition-all duration-300" style={{ width: `${scanProgress}%`, background: 'var(--nm-green)' }} />
              </div>
              <span className="nm-mono text-xs" style={{ color: 'var(--nm-muted)' }}>{scanProgress}%</span>
              <button className="nm-btn !py-1 !text-xs" onClick={cancelScan}><XCircle size={12} /> Cancel</button>
            </div>
            <div className="nm-console min-h-[360px] overflow-auto">
              {progressLines.join('\n')}
            </div>
          </div>
        )}

        {!scanning && lastScan && tab === 'output' && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 flex-wrap">
              {['normal', 'xml', 'script-kiddie', 'grepable'].map((mode) => (
                <button key={mode} className={`nm-tab ${outputMode === mode ? 'nm-tab-active' : ''}`} onClick={() => setOutputMode(mode)}>
                  {mode === 'script-kiddie' ? 'S|<rIpt kIddi3' : mode.toUpperCase()}
                </button>
              ))}
              <span className="flex-1" />
              <button className="nm-btn" onClick={() => navigator.clipboard?.writeText(formatOutput(outputMode))}><Copy size={13} /> Copy output</button>
              <button className="nm-btn" onClick={() => downloadOutput(outputMode)}><Download size={13} /> Save output</button>
            </div>
            <div className="nm-console min-h-[360px] overflow-auto">
              {formatOutput(outputMode)}
            </div>
          </div>
        )}

        {lastScan && tab === 'ports' && (
          <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-3">
            {pendingTransitions.length > 0 && (
              <div className="lg:col-span-2 nm-card p-2 text-[12px] flex items-center gap-2 flex-wrap"
                   style={{ borderColor: 'rgba(240,200,80,.5)', background: 'rgba(240,200,80,.08)' }}>
                <Radar size={13} style={{ color: 'var(--nm-muted)' }} />
                <span style={{ color: 'var(--nm-muted)' }}>Service change in progress —</span>
                {pendingTransitions.map((t) => (
                  <span key={`${t.ip}-${t.port}`} className="nm-mono">
                    {t.ip}:{t.port} → {t.to}
                  </span>
                ))}
                <span style={{ color: 'var(--nm-muted)' }}>· re-scan to confirm the new state.</span>
              </div>
            )}
            <div className="nm-sidebar">
              <div className="nm-sidebar-head">Hosts</div>
              {scanHosts.map((h) => {
                const Icon = hostIcon(h)
                return (
                  <button key={h.ip} className={`nm-side-row ${h.ip === selectedHost ? 'nm-active' : ''}`} onClick={() => setSelectedHost(h.ip)}>
                    <Icon size={14} /><span className="nm-mono">{h.ip}</span><span className="ml-auto text-[10px]">{h.state || 'up'}</span>
                  </button>
                )
              })}
              <div className="nm-sidebar-head">Services</div>
              {services.map((s) => <div key={s} className="nm-side-row"><Cpu size={13} /> {s}</div>)}
            </div>
            <div className="nm-card overflow-hidden">
              <div className="flex items-center gap-2 p-2 border-b" style={{ borderColor: 'var(--nm-border)' }}>
                <Search size={14} style={{ color: 'var(--nm-muted)' }} />
                <input
                  className="nm-input flex-1 !py-1.5 !text-[13px]"
                  value={portFilter}
                  spellCheck={false}
                  placeholder="Filter ports — host, port, state, service, or version"
                  onChange={(e) => setPortFilter(e.target.value)}
                />
                {portFilter && (
                  <button className="nm-btn !py-1 !text-xs" onClick={() => setPortFilter('')}><X size={12} /> Clear</button>
                )}
                <span className="text-[11px] nm-mono" style={{ color: 'var(--nm-muted)' }}>{filteredPorts.length}/{allPorts.length}</span>
              </div>
              <table className="nm-table">
                <thead><tr><th>Host</th><th>Port</th><th>Protocol</th><th>State</th><th>Service</th><th>Version</th><th>Service control</th></tr></thead>
                <tbody>
                  {filteredPorts.length === 0 ? (
                    <tr><td colSpan={7} className="text-center py-6" style={{ color: 'var(--nm-muted)' }}>No ports match “{portFilter}”.</td></tr>
                  ) : filteredPorts.map((p) => {
                    const pending = pendingTransitions.find((t) => t.ip === p.host && t.port === p.port)
                    return (
                    <tr key={`${p.host}-${p.port}-${p.proto}`} onClick={() => setSelectedHost(p.host)}>
                      <td className="nm-mono">{p.host}</td><td className="nm-mono">{p.port}</td><td>{p.proto || 'tcp'}</td><td><StateBadge state={p.state} /></td><td>{p.service || '—'}</td>
                      <td className="nm-mono text-[11px]" style={{ color: 'var(--nm-muted)' }}>{[p.product, p.version].filter(Boolean).join(' ') || '—'}</td>
                      <td>
                        {pending ? (
                          <span className="text-[11px] nm-mono" style={{ color: 'var(--nm-muted)' }}>→ {pending.to}…</span>
                        ) : p.state === 'open' ? (
                          <button className="nm-btn !py-0.5 !px-2 !text-[11px]"
                                  onClick={(e) => { e.stopPropagation(); serviceControl(p.host, p.port, 'stop_service') }}>
                            Stop service
                          </button>
                        ) : p.state === 'closed' ? (
                          <button className="nm-btn !py-0.5 !px-2 !text-[11px]"
                                  onClick={(e) => { e.stopPropagation(); serviceControl(p.host, p.port, 'start_service') }}>
                            Start service
                          </button>
                        ) : <span style={{ color: 'var(--nm-muted)' }}>—</span>}
                      </td>
                    </tr>
                  )})}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {lastScan && tab === 'topology' && (
          <div className="nm-card p-3">
            <div className="flex items-center gap-2 mb-3">
              <button className="nm-btn !text-xs" onClick={() => setTopoZoom((z) => Math.min(2, +(z + 0.2).toFixed(2)))} disabled={topoZoom >= 2}>Zoom +</button>
              <button className="nm-btn !text-xs" onClick={() => setTopoZoom((z) => Math.max(0.6, +(z - 0.2).toFixed(2)))} disabled={topoZoom <= 0.6}>Zoom -</button>
              <button className="nm-btn !text-xs" onClick={() => setTopoZoom(1)} disabled={topoZoom === 1}>Reset</button>
              <span className="text-[11px] nm-mono ml-1" style={{ color: 'var(--nm-muted)' }}>{Math.round(topoZoom * 100)}%</span>
            </div>
            <div className="nm-topology">
              <div style={{ position: 'absolute', inset: 0, transform: `scale(${topoZoom})`, transformOrigin: 'center center', transition: 'transform 0.2s ease' }}>
              <div className="nm-node" style={{ left: '50%', top: '50%' }}>
                <div className="nm-node-icon"><Radar size={18} /></div><div>Nmap</div>
              </div>
              {scanHosts.map((h, i) => {
                const Icon = hostIcon(h)
                const angle = (Math.PI * 2 * i) / Math.max(1, scanHosts.length)
                const r = i % 3 === 0 ? 105 : 155
                const x = 50 + Math.cos(angle) * (r / 3.8)
                const y = 50 + Math.sin(angle) * (r / 3.8)
                return (
                  <button key={h.ip} className="nm-node" style={{ left: `${x}%`, top: `${y}%` }} onClick={() => { setSelectedHost(h.ip); setTab('details') }}>
                    <div className="nm-node-icon" style={{ borderColor: h.state === 'up' ? 'rgba(56,224,208,.5)' : 'rgba(125,163,125,.25)' }}><Icon size={17} /></div>
                    <div className="nm-mono">{h.ip}</div>
                  </button>
                )
              })}
              </div>
            </div>
          </div>
        )}

        {lastScan && tab === 'details' && (
          <div className="nm-card overflow-hidden">
            {!activeHost ? <div className="p-6 text-sm text-center" style={{ color: 'var(--nm-muted)' }}>Select a host.</div> : (
              <div className="p-4 space-y-4">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="nm-mono text-lg text-white">{activeHost.ip}</span>
                  {activeHost.hostname && <span>{activeHost.hostname}</span>}
                  <span className={`nm-badge ${activeHost.state === 'up' ? 'nm-b-up' : 'nm-b-closed'}`}>{activeHost.state || 'up'}</span>
                </div>
                <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  {[
                    ['IPv4', activeHost.ip],
                    ['MAC', activeHost.mac || '—'],
                    ['Vendor', activeHost.vendor || '—'],
                    ['OS', activeHost.os || 'Unknown'],
                    ['Last boot', activeHost.last_boot || '2026-06-28 08:11'],
                    ['Distance', '1 hop'],
                    ['Open ports', (activeHost.ports || []).filter((p) => p.state === 'open').length],
                    ['OS accuracy', activeHost.os_accuracy ? `${activeHost.os_accuracy}%` : '—'],
                  ].map(([k, v]) => (
                    <div key={k} className="nm-card p-3"><div className="text-[10px]" style={{ color: 'var(--nm-muted)' }}>{k}</div><div className="nm-mono text-sm">{v}</div></div>
                  ))}
                </div>
                <div>
                  <div className="text-xs font-semibold mb-2" style={{ color: 'var(--nm-muted)' }}>OS Matches</div>
                  <table className="nm-table"><tbody><tr><td>{activeHost.os || 'Linux 5.x / Ubuntu 20.04'}</td><td>{activeHost.os_accuracy || 96}%</td><td className="nm-mono">cpe:/o:linux:linux_kernel</td></tr></tbody></table>
                </div>
                <div>
                  <div className="text-xs font-semibold mb-2" style={{ color: 'var(--nm-muted)' }}>Traceroute</div>
                  <table className="nm-table"><thead><tr><th>TTL</th><th>RTT</th><th>Address</th><th>Hostname</th></tr></thead><tbody>{(activeHost.traceroute || [{ ttl: 1, rtt: '0.45ms', address: inventory.gateway || '192.168.1.1' }, { ttl: 2, rtt: '1.22ms', address: activeHost.ip }]).map((r, i) => <tr key={i}><td>{r.ttl || i + 1}</td><td>{r.rtt}</td><td>{r.address}</td><td>{r.hostname || '—'}</td></tr>)}</tbody></table>
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'scans' && (
          <div className="nm-card overflow-hidden">
            {(state?.scan_log || []).length === 0 ? (
              <div className="p-8 text-sm text-center" style={{ color: 'var(--nm-muted)' }}>No scans run yet.</div>
            ) : (
              <div className="max-h-[460px] overflow-y-auto p-3 space-y-2">
                {(state.scan_log || []).slice().reverse().map((entry, i) => {
                  const text = typeof entry === 'string' ? entry : (entry.command || entry.summary || JSON.stringify(entry))
                  return (
                    <button key={i} className="nm-console !py-2 !text-[12px] w-full text-left flex items-start gap-2" onClick={() => setTab('output')}>
                      <span style={{ color: 'var(--nm-green)' }}>$</span>
                      <span className="flex-1">{text}</span>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* events feed */}
        {(state?.events || []).length > 0 && (
          <div className="mt-4 nm-card p-3">
            <div className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--nm-muted)' }}>Events</div>
            <div className="space-y-1.5">
              {(state.events || []).slice(-6).map((ev, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  {ev.severity === 'error' ? <XCircle size={13} className="mt-0.5 shrink-0" style={{ color: 'var(--nm-red)' }} />
                    : ev.severity === 'warning' ? <AlertTriangle size={13} className="mt-0.5 shrink-0" style={{ color: 'var(--nm-amber)' }} />
                    : <CheckCircle2 size={13} className="mt-0.5 shrink-0" style={{ color: 'var(--nm-green)' }} />}
                  <span style={{ color: 'var(--nm-text)' }}>{ev.message}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {modal === 'nse' && (
        <NmapModal title="NSE Scripts Browser" onClose={() => setModal(null)}>
          <div className="grid md:grid-cols-[220px_1fr] gap-4">
            <div className="border rounded overflow-hidden">
              {NSE_CATEGORIES.map((cat) => (
                <button key={cat} className={`block w-full text-left px-3 py-2 text-sm ${scriptCategory === cat ? 'bg-green-100 text-green-800' : 'hover:bg-slate-100'}`} onClick={() => setScriptCategory(cat)}>
                  {cat}
                </button>
              ))}
            </div>
            <div>
              <div className="flex items-center gap-2 mb-3">
                <FileCode2 size={16} className="text-green-700" />
                <span className="font-semibold">Category: {scriptCategory}</span>
              </div>
              <table className="w-full text-sm border-collapse">
                <thead><tr className="bg-slate-100 text-slate-500"><th className="text-left p-2">Script</th><th className="text-left p-2">Categories</th><th className="text-left p-2">Description</th></tr></thead>
                <tbody>
                  {NSE_SCRIPTS.filter((s) => s[1].includes(scriptCategory) || scriptCategory === 'default').map(([name, cats, desc]) => (
                    <tr key={name} className="border-t"><td className="p-2 font-mono">{name}.nse</td><td className="p-2">{cats}</td><td className="p-2">{desc}</td></tr>
                  ))}
                </tbody>
              </table>
              <button className="mt-3 px-3 py-1.5 rounded bg-green-600 text-white text-sm" onClick={() => { setFlags((prev) => new Set([...prev, '--script', scriptCategory])); setModal(null) }}>Add category to command</button>
            </div>
          </div>
        </NmapModal>
      )}

      {modal === 'wizard' && (
        <NmapModal title="Command Wizard" onClose={() => setModal(null)}>
          <div className="grid sm:grid-cols-2 gap-3 text-sm">
            {SCAN_PROFILES.map((p) => (
              <button key={p.id} className="text-left border rounded p-3 hover:bg-green-50" onClick={() => { setProfile(p.id); setFlags(new Set(p.flags)); setPorts(p.ports); setModal(null) }}>
                <div className="font-semibold">{p.label}</div>
                <div className="font-mono text-xs text-slate-500 mt-1">{p.desc}</div>
              </button>
            ))}
          </div>
        </NmapModal>
      )}

      {modal === 'compare' && (
        <NmapModal title="Compare Scans" onClose={() => setModal(null)}>
          <div className="flex items-center gap-2 mb-3 text-sm"><GitCompare size={16} /> Compare current scan against previous scan history.</div>
          <table className="w-full text-sm"><tbody>
            <tr className="border-t"><td className="p-2">New hosts</td><td className="p-2 font-mono">{scanHosts.length}</td></tr>
            <tr className="border-t"><td className="p-2">Open ports</td><td className="p-2 font-mono">{allPorts.filter((p) => p.state === 'open').length}</td></tr>
            <tr className="border-t"><td className="p-2">Changed services</td><td className="p-2 font-mono">{services.length}</td></tr>
          </tbody></table>
        </NmapModal>
      )}

      {modal === 'search' && (
        <NmapModal title="Search Scan Results" onClose={() => setModal(null)}>
          <div className="flex gap-2">
            <input
              className="border rounded px-2 py-1 flex-1"
              autoFocus
              value={portFilter}
              placeholder="Search hosts, services, versions, or ports"
              onChange={(e) => setPortFilter(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { setTab('ports'); setModal(null) } }}
            />
            <button className="px-3 py-1 rounded bg-green-600 text-white flex items-center gap-1" onClick={() => { setTab('ports'); setModal(null) }}><Search size={13} /> Search</button>
          </div>
          <p className="text-xs text-slate-500 mt-2">Filters the Ports/Hosts table by any field.</p>
        </NmapModal>
      )}

      {modal === 'save' && (
        <NmapModal title="Save Output" onClose={() => setModal(null)}>
          <p className="text-sm mb-3">Save current scan as normal, XML, script kiddie, or grepable output.</p>
          {!lastScan ? (
            <p className="text-sm text-slate-500">Run a scan first — there is no output to save yet.</p>
          ) : (
            <div className="grid sm:grid-cols-4 gap-2">
              {[['Normal', 'normal'], ['XML', 'xml'], ['S|<rIpt kIddi3', 'script-kiddie'], ['Grepable', 'grepable']].map(([label, mode]) => (
                <button key={mode} className="border rounded px-3 py-2 hover:bg-green-50" onClick={() => { downloadOutput(mode); setModal(null) }}>
                  <Download size={13} className="inline mr-1" /> {label}
                </button>
              ))}
            </div>
          )}
        </NmapModal>
      )}

      {modal === 'about' && (
        <NmapModal title="About Nmap / Zenmap" onClose={() => setModal(null)}>
          <div className="flex items-start gap-3 text-sm">
            <HelpCircle size={22} className="text-green-700 shrink-0" />
            <p>FixitLab Nmap simulation with Zenmap-style profiles, output tabs, topology, host details, scan history, NSE script browser, and command builder.</p>
          </div>
        </NmapModal>
      )}
    </div>
  )
}
