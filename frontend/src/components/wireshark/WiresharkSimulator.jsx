import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Waves, Filter, Search, ArrowLeft, RefreshCw,
  XCircle, AlertTriangle, CheckCircle2, GitBranch, Flag, Eraser, Target,
  ArrowRight, ArrowLeftRight, FolderOpen, Save, Square, PlayCircle, ZoomIn,
  ZoomOut, SkipBack, SkipForward, BarChart3, Network,
  Settings, Radio, X, Eye,
} from 'lucide-react'
import { wiresharkApi } from '../../api/wireshark'
import { LabChromeControls } from '../lab/LabChromeBar'

/* ── scoped, self-contained Wireshark-style chrome (no shared CSS) ── */
const SCOPED_CSS = `
.ws-sim {
  --ws-bg: #0c1018;
  --ws-panel: #121723;
  --ws-panel-2: #161c2b;
  --ws-border: #243049;
  --ws-text: #d6def0;
  --ws-muted: #8893ac;
  --ws-blue: #4c8dff;
  --ws-green: #4ade80;
  --ws-amber: #f5c451;
  --ws-red: #ff6b6b;
  --ws-purple: #b18cff;
  --ws-teal: #34d3c2;
  color: var(--ws-text);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  background: var(--ws-bg);
  min-height: 100%;
}
.ws-sim .ws-topbar {
  display: flex; align-items: center; justify-content: space-between; gap: 0.75rem;
  padding: 0.6rem 1rem; background: #0a0e15; border-bottom: 1px solid var(--ws-border);
  position: sticky; top: 0; z-index: 10;
}
.ws-sim .ws-menubar {
  display: flex; align-items: center; gap: 0.1rem; padding: 0.25rem 0.75rem;
  background: #101522; border-bottom: 1px solid var(--ws-border); position: sticky; top: 45px; z-index: 9;
}
.ws-sim .ws-menu-btn {
  position: relative; border: 1px solid transparent; background: transparent; color: var(--ws-text);
  font-size: 0.78rem; padding: 0.28rem 0.55rem; border-radius: 4px; cursor: pointer;
}
.ws-sim .ws-menu-btn:hover, .ws-sim .ws-menu-btn.ws-on { background: #1a2233; border-color: var(--ws-border); }
.ws-sim .ws-menu-pop {
  position: absolute; top: calc(100% + 2px); left: 0; min-width: 230px; max-height: 420px; overflow-y: auto;
  background: #f8fafc; color: #111827; border: 1px solid #cbd5e1; box-shadow: 0 18px 40px rgba(0,0,0,.35);
  border-radius: 4px; padding: 0.25rem; z-index: 40;
}
.ws-sim .ws-menu-item {
  display: flex; justify-content: space-between; align-items: center; gap: 1rem;
  width: 100%; padding: 0.35rem 0.55rem; font-size: 0.74rem; border-radius: 3px; white-space: nowrap;
}
.ws-sim .ws-menu-item:hover { background: #e6f0ff; }
.ws-sim .ws-toolbar {
  display: flex; align-items: center; gap: 0.25rem; padding: 0.35rem 0.85rem;
  background: #141b2a; border-bottom: 1px solid var(--ws-border); overflow-x: auto;
}
.ws-sim .ws-tool {
  display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 28px;
  border-radius: 5px; color: var(--ws-muted); border: 1px solid transparent; background: transparent; cursor: pointer;
}
.ws-sim .ws-tool:hover { color: var(--ws-text); background: #202a3f; border-color: var(--ws-border); }
.ws-sim .ws-tool.ws-live { color: var(--ws-green); background: rgba(74,222,128,.08); }
.ws-sim .ws-btn {
  display: inline-flex; align-items: center; gap: 0.4rem; border-radius: 6px;
  padding: 0.45rem 0.8rem; font-size: 0.8rem; font-weight: 600; cursor: pointer;
  border: 1px solid var(--ws-border); background: #1a2233; color: var(--ws-text);
  transition: background 0.12s, filter 0.12s;
}
.ws-sim .ws-btn:hover { background: #212b40; }
.ws-sim .ws-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.ws-sim .ws-btn-primary { border: none; background: var(--ws-blue); color: #061327; }
.ws-sim .ws-btn-primary:hover { filter: brightness(1.08); }
.ws-sim .ws-filterbar {
  display: flex; align-items: center; gap: 0; border-radius: 6px; overflow: hidden;
  border: 1px solid var(--ws-border);
}
.ws-sim .ws-filterbar.ws-display { background: rgba(74,222,128,.06); }
.ws-sim .ws-filterbar.ws-capture { background: rgba(76,141,255,.06); }
.ws-sim .ws-filterbar.ws-bad { border-color: var(--ws-red); background: rgba(255,107,107,.1); }
.ws-sim .ws-filter-input {
  flex: 1; background: transparent; border: none; outline: none; color: var(--ws-text);
  padding: 0.5rem 0.7rem; font-size: 0.82rem;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
}
.ws-sim .ws-filter-tag {
  font-size: 0.62rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
  padding: 0 0.6rem; align-self: stretch; display: flex; align-items: center;
  color: var(--ws-muted); border-right: 1px solid var(--ws-border);
}
.ws-sim .ws-chip {
  display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.7rem; font-weight: 600;
  padding: 0.2rem 0.5rem; border-radius: 6px; cursor: pointer; white-space: nowrap;
  border: 1px solid var(--ws-border); background: #131a28; color: var(--ws-muted);
  font-family: 'JetBrains Mono', ui-monospace, monospace;
}
.ws-sim .ws-chip:hover { color: var(--ws-text); border-color: var(--ws-blue); }
.ws-sim .ws-card {
  background: var(--ws-panel); border: 1px solid var(--ws-border); border-radius: 8px;
}
.ws-sim .ws-table { width: 100%; border-collapse: collapse; font-size: 0.76rem; }
.ws-sim .ws-table th {
  text-align: left; color: var(--ws-muted); font-weight: 600; padding: 0.4rem 0.6rem;
  border-bottom: 1px solid var(--ws-border); position: sticky; top: 0; background: var(--ws-panel-2);
  white-space: nowrap;
}
.ws-sim .ws-table td { padding: 0.32rem 0.6rem; border-bottom: 1px solid #1a2233; white-space: nowrap; }
.ws-sim .ws-table td.ws-info { white-space: normal; }
.ws-sim .ws-row { cursor: pointer; }
.ws-sim .ws-row.ws-selected td { outline: 1px solid var(--ws-blue); background: rgba(76,141,255,.14) !important; }
.ws-sim .ws-mono { font-family: 'JetBrains Mono', ui-monospace, monospace; }
.ws-sim .ws-banner {
  display: flex; align-items: flex-start; gap: 0.5rem; font-size: 0.8rem;
  padding: 0.6rem 0.85rem; border-radius: 8px; margin-bottom: 0.85rem;
}
.ws-sim .ws-banner-task { background: rgba(76,141,255,.08); border: 1px solid rgba(76,141,255,.28); color: #b9d2ff; }
.ws-sim .ws-banner-err { background: rgba(255,107,107,.1); border: 1px solid rgba(255,107,107,.3); color: #ffb4b4; }
.ws-sim .ws-stream {
  font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 0.76rem;
  background: #07090f; border: 1px solid var(--ws-border); border-radius: 8px;
  padding: 0.7rem 0.85rem; max-height: 360px; overflow-y: auto; line-height: 1.55;
  white-space: pre-wrap; word-break: break-word;
}
.ws-sim .ws-modal-backdrop {
  position: fixed; inset: 0; z-index: 60; background: rgba(0,0,0,.65);
  display: flex; align-items: center; justify-content: center; padding: 1rem;
}
.ws-sim .ws-modal {
  width: min(980px, 96vw); max-height: 88vh; overflow: hidden; display: flex; flex-direction: column;
  background: #f8fafc; color: #111827; border-radius: 8px; border: 1px solid #cbd5e1;
  box-shadow: 0 28px 80px rgba(0,0,0,.45);
}
.ws-sim .ws-modal-head {
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  padding: 0.65rem 0.85rem; background: #e5edf7; border-bottom: 1px solid #cbd5e1;
}
.ws-sim .ws-modal-body { padding: 0.85rem; overflow: auto; }
.ws-sim .ws-light-table { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
.ws-sim .ws-light-table th { text-align: left; background: #e2e8f0; color: #475569; padding: 0.42rem 0.55rem; }
.ws-sim .ws-light-table td { padding: 0.38rem 0.55rem; border-bottom: 1px solid #e2e8f0; }
.ws-sim .ws-graph-row { display: grid; grid-template-columns: 120px 1fr 80px; align-items: center; gap: 0.65rem; margin: 0.45rem 0; }
.ws-sim .ws-graph-bar { height: 12px; border-radius: 999px; background: linear-gradient(90deg, #4c8dff, #34d3c2); }
.ws-sim .ws-statusbar {
  display: flex; align-items: center; gap: 0.75rem; padding: 0.35rem 0.85rem;
  border-top: 1px solid var(--ws-border); background: #0f1522; color: var(--ws-muted);
  font-size: 0.7rem; font-family: 'JetBrains Mono', ui-monospace, monospace;
}
`

/* Wireshark colorizes rows by protocol. Mirror the familiar palette. */
function protoColor(proto) {
  switch ((proto || '').toUpperCase()) {
    case 'HTTP': return '#4ade80'
    case 'DNS': return '#34d3c2'
    case 'TLS':
    case 'SSL': return '#b18cff'
    case 'SSH': return '#f5c451'
    case 'UDP': return '#8ec5ff'
    case 'TCP': return '#9fb0d0'
    default: return '#d6def0'
  }
}
function rowTint(pkt) {
  const flags = (pkt.tcp_flags || '').toUpperCase()
  if (flags.includes('RST')) return 'rgba(255,107,107,.10)'
  if ((pkt.protocol || '').toUpperCase() === 'TLS') return 'rgba(177,140,255,.07)'
  if ((pkt.protocol || '').toUpperCase() === 'HTTP') return 'rgba(74,222,128,.06)'
  if ((pkt.protocol || '').toUpperCase() === 'DNS') return 'rgba(52,211,194,.06)'
  return 'transparent'
}

/** Mock protocol dissection tree (Wireshark-style). */
function dissectTree(pkt) {
  if (!pkt) return []
  const proto = (pkt.protocol || 'DATA').toUpperCase()
  const rows = [
    { depth: 0, label: `Frame ${pkt.no}: ${pkt.length} bytes on wire` },
    { depth: 1, label: `Ethernet II, Src/Dst` },
    { depth: 1, label: `Internet Protocol Version 4, Src: ${pkt.src}, Dst: ${pkt.dst}` },
  ]
  if (proto === 'TCP' || pkt.src_port) {
    rows.push({ depth: 1, label: `Transmission Control Protocol, Src Port: ${pkt.src_port || '?'}, Dst Port: ${pkt.dst_port || '?'}` })
    if (pkt.tcp_flags) rows.push({ depth: 2, label: `Flags: ${pkt.tcp_flags}` })
  }
  if (proto === 'UDP') rows.push({ depth: 1, label: `User Datagram Protocol, Src Port: ${pkt.src_port}, Dst Port: ${pkt.dst_port}` })
  rows.push({ depth: 1, label: `${proto} Protocol`, highlight: true })
  if (pkt.info) rows.push({ depth: 2, label: pkt.info })
  return rows
}

/** Generate a mock hex dump from packet metadata. */
function hexDump(pkt) {
  if (!pkt) return []
  const seed = pkt.no * 17 + (pkt.length || 64)
  const lines = []
  const bytesPerLine = 16
  const total = Math.min(pkt.length || 64, 128)
  for (let off = 0; off < total; off += bytesPerLine) {
    const bytes = []
    const ascii = []
    for (let i = 0; i < bytesPerLine && off + i < total; i++) {
      const b = (seed + off + i * 7) % 256
      bytes.push(b.toString(16).padStart(2, '0'))
      ascii.push(b >= 32 && b < 127 ? String.fromCharCode(b) : '.')
    }
    lines.push({ offset: off.toString(16).padStart(4, '0'), bytes, ascii: ascii.join('') })
  }
  return lines
}

const WS_MENUS = [
  ['File', ['Open', 'Open Recent', 'Merge', 'Import from hex dump', 'Close', 'Save', 'Save As', 'Export Specified Packets', 'Export Packet Dissections as CSV', 'Export Objects HTTP', 'Print', 'Quit']],
  ['Edit', ['Copy as Text', 'Copy as Bytes', 'Copy as JSON', 'Find Packet', 'Find Next', 'Find Previous', 'Mark/Unmark Packet', 'Ignore Packet', 'Set Time Reference', 'Preferences']],
  ['View', ['Main Toolbar', 'Filter Toolbar', 'Statusbar', 'Packet List', 'Packet Details', 'Packet Bytes', 'Time Display Format', 'Name Resolution', 'Colorize Packet List', 'Zoom In', 'Zoom Out', 'Resize Columns']],
  ['Go', ['Back', 'Forward', 'Go to Packet', 'First Packet', 'Last Packet', 'Previous Packet', 'Next Packet']],
  ['Capture', ['Options', 'Start', 'Stop', 'Restart', 'Capture Filters', 'Refresh Interfaces']],
  ['Analyze', ['Display Filters', 'Apply as Column', 'Apply as Filter', 'Prepare as Filter', 'Enable Protocol', 'Decode As', 'Expert Information', 'Follow TCP Stream', 'Follow UDP Stream', 'Follow HTTP Stream']],
  ['Statistics', ['Capture File Properties', 'Protocol Hierarchy', 'Conversations', 'Endpoints', 'Packet Lengths', 'I/O Graph', 'Service Response Time', 'Flow Graph', 'HTTP', 'TCP Stream Graphs']],
  ['Telephony', ['VoIP Calls', 'RTP Streams', 'SIP Flows', 'H.225', 'IAX2', 'RTSP', 'SMPP Operations']],
  ['Wireless', ['WLAN Traffic', 'Bluetooth ATT Server Attributes', 'Bluetooth Devices', 'Bluetooth HCI Summary']],
  ['Tools', ['Firewall ACL Rules', 'Credentials', 'Lua Console']],
  ['Help', ['Contents', 'Supported Protocols', 'FAQ', 'Man Pages', 'Website', 'Sample Captures', 'About Wireshark']],
]

// Field snippets that insert a *complete, usable* display filter for THIS
// capture (the packet set only carries HTTP/DNS/TLS/SSH over TCP/UDP, so we
// don't offer arp/eth/frame fields that would match nothing). Clicking a chip
// drops a ready-to-apply term; the engine accepts these verbatim, so the filter
// bar never goes red on a suggested field. Mirrors Wireshark's field-name
// autocomplete but pre-filled with real values from the capture.
const DISPLAY_AUTOCOMPLETE = [
  'ip.addr==93.184.216.34', 'ip.src==10.0.0.15', 'tcp.port==80', 'udp.port==53',
  'http.request', 'http.response', 'tcp.flags.syn==1', 'tls',
]

function ModalShell({ title, children, onClose }) {
  return (
    <div className="ws-modal-backdrop" onMouseDown={onClose}>
      <div className="ws-modal" onMouseDown={(e) => e.stopPropagation()}>
        <div className="ws-modal-head">
          <div className="font-semibold">{title}</div>
          <button type="button" className="p-1 rounded hover:bg-slate-200" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="ws-modal-body">{children}</div>
      </div>
    </div>
  )
}

function protocolStats(packets) {
  const total = packets.length || 1
  const byProto = new Map()
  packets.forEach((p) => byProto.set(p.protocol || 'DATA', (byProto.get(p.protocol || 'DATA') || 0) + 1))
  return Array.from(byProto.entries()).sort((a, b) => b[1] - a[1]).map(([proto, count]) => ({
    proto,
    count,
    pct: Math.round((count / total) * 100),
    bytes: packets.filter((p) => (p.protocol || 'DATA') === proto).reduce((sum, p) => sum + (p.length || 0), 0),
  }))
}

function conversationRows(packets) {
  const rows = new Map()
  packets.forEach((p) => {
    const a = `${p.src}${p.src_port ? `:${p.src_port}` : ''}`
    const b = `${p.dst}${p.dst_port ? `:${p.dst_port}` : ''}`
    const key = [a, b].sort().join(' <-> ')
    const cur = rows.get(key) || { a, b, proto: p.protocol || 'DATA', packets: 0, bytes: 0, duration: 0 }
    cur.packets += 1
    cur.bytes += p.length || 0
    cur.duration = Math.max(cur.duration, Number(p.time || 0))
    rows.set(key, cur)
  })
  return Array.from(rows.values()).sort((a, b) => b.bytes - a.bytes).slice(0, 12)
}

/**
 * Re-render a Follow-Stream segment's text in the chosen Wireshark display
 * format. Mirrors Wireshark's "Show data as" selector: ASCII/UTF-8 show the
 * text as-is, Hex Dump lays out offset + hex bytes + ascii gutter, Raw shows
 * the contiguous hex string, C Arrays emits a char[] initializer.
 */
function formatStreamData(text, format) {
  const data = text == null ? '' : String(text)
  switch (format) {
    case 'Hex Dump': {
      const lines = []
      for (let off = 0; off < data.length; off += 16) {
        const chunk = data.slice(off, off + 16)
        const hex = Array.from(chunk).map((ch) => ch.charCodeAt(0).toString(16).padStart(2, '0')).join(' ')
        const ascii = Array.from(chunk).map((ch) => {
          const c = ch.charCodeAt(0)
          return c >= 32 && c < 127 ? ch : '.'
        }).join('')
        lines.push(`${off.toString(16).padStart(8, '0')}  ${hex.padEnd(47, ' ')}  ${ascii}`)
      }
      return lines.join('\n')
    }
    case 'Raw':
      return Array.from(data).map((ch) => ch.charCodeAt(0).toString(16).padStart(2, '0')).join('')
    case 'C Arrays':
      return `char stream[] = {\n${Array.from(data).map((ch) => `0x${ch.charCodeAt(0).toString(16).padStart(2, '0')}`).join(', ')}\n};`
    case 'UTF-8':
    case 'ASCII':
    default:
      return data
  }
}

/**
 * Wireshark packet-capture simulator. Rendered INLINE by LabRunner for wireshark
 * labs (simulation_type 'wireshark' / technology.slug 'wireshark') — no new route.
 * The learner sets a capture filter (what lands on disk), narrows the view with a
 * display filter, follows TCP streams, and marks packets, then runs Check Solution
 * (graded by validate_wireshark_lab via the engine).
 */
export default function WiresharkSimulator({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
}) {
  const slug = scenario?.slug || ''
  const [state, setState] = useState(null)
  const [error, setError] = useState('')
  const [captureInput, setCaptureInput] = useState('')
  const [displayInput, setDisplayInput] = useState('')
  const [displayBad, setDisplayBad] = useState(false)
  const [busy, setBusy] = useState(false)
  const [menuOpen, setMenuOpen] = useState(null)
  const [modal, setModal] = useState(null)
  const [capturing, setCapturing] = useState(true)
  const [zoom, setZoom] = useState(100)
  const [findQuery, setFindQuery] = useState('')
  const [findError, setFindError] = useState('')
  const [streamFormat, setStreamFormat] = useState('ASCII')
  const pollRef = useRef(null)
  const hydrated = useRef(false)
  const rowRefs = useRef({})

  const load = useCallback(async () => {
    try {
      const data = await wiresharkApi.getState(sessionId, slug)
      setState(data)
      setError('')
      // Hydrate the filter inputs from server state once (don't clobber typing).
      if (!hydrated.current) {
        const inv = data?.inventory || {}
        setCaptureInput(inv.capture_filter || '')
        setDisplayInput(inv.display_filter || '')
        hydrated.current = true
      }
    } catch {
      setError('Could not load Wireshark')
    }
  }, [sessionId, slug])

  useEffect(() => {
    load()
    pollRef.current = setInterval(load, 20000)
    return () => clearInterval(pollRef.current)
  }, [load])

  const inv = state?.inventory || {}
  const summary = state?.summary || {}
  const packets = useMemo(() => inv.packets || [], [inv.packets])
  const selected = inv.selected_packet

  // Reset the Find dialog's transient search state each time it opens so a
  // prior no-match error / stale query doesn't leak into a fresh search.
  useEffect(() => {
    if (modal === 'find') { setFindQuery(''); setFindError('') }
  }, [modal])

  // Scroll the selected packet's row into view (used by Find Packet and the
  // First/Prev/Next/Last navigation toolbar). Purely a viewport nicety — no
  // state change.
  useEffect(() => {
    if (selected == null) return
    const el = rowRefs.current[selected]
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'nearest' })
    }
  }, [selected])
  const marked = useMemo(() => new Set((inv.marked_packets || []).map(Number)), [inv.marked_packets])
  const streamPayload = inv.stream_payload || []
  const followedStream = inv.followed_stream

  const applyCaptureFilter = useCallback(async () => {
    setBusy(true); setError('')
    try {
      const res = await wiresharkApi.setCaptureFilter(sessionId, captureInput.trim())
      if (res?.ok === false) setError(res.error || res.message || 'Capture filter rejected')
      await load()
    } catch { setError('Could not apply capture filter') }
    finally { setBusy(false) }
  }, [sessionId, captureInput, load])

  const applyDisplayFilter = useCallback(async () => {
    setBusy(true); setError(''); setDisplayBad(false)
    try {
      const res = await wiresharkApi.setDisplayFilter(sessionId, displayInput.trim())
      if (res?.ok === false) {
        setDisplayBad(true)
        setError(res.error || res.message || 'Invalid display filter syntax')
      }
      await load()
    } catch { setError('Could not apply display filter') }
    finally { setBusy(false) }
  }, [sessionId, displayInput, load])

  const clearFilters = useCallback(async () => {
    setBusy(true); setError(''); setDisplayBad(false)
    try {
      await wiresharkApi.clearFilters(sessionId)
      setDisplayInput('')
      await load()
    } catch { /* ignore */ }
    finally { setBusy(false) }
  }, [sessionId, load])

  const selectPacket = useCallback(async (no) => {
    try { await wiresharkApi.selectPacket(sessionId, no); await load() } catch { /* ignore */ }
  }, [sessionId, load])

  const toggleMark = useCallback(async (no, e) => {
    e?.stopPropagation()
    try { await wiresharkApi.markPacket(sessionId, no); await load() } catch { /* ignore */ }
  }, [sessionId, load])

  const follow = useCallback(async (pkt, e) => {
    e?.stopPropagation()
    setBusy(true)
    try {
      const payload = pkt.stream_id != null ? { stream_id: pkt.stream_id } : { packet_no: pkt.no }
      await wiresharkApi.followStream(sessionId, payload)
      setDisplayInput(pkt.stream_id != null ? `tcp.stream==${pkt.stream_id}` : displayInput)
      await load()
      setModal('stream')
    } catch { /* ignore */ }
    finally { setBusy(false) }
  }, [sessionId, displayInput, load])

  // Find Packet: match query against Info / Source / Destination / Protocol
  // (case-insensitive substring) and select the first matching displayed
  // packet, scrolling it into view. Does NOT alter capture/grading state —
  // it reuses the same selectPacket path as clicking a row.
  const findPacket = useCallback(async () => {
    const q = findQuery.trim().toLowerCase()
    if (!q) { setFindError('Enter a search term'); return }
    const hit = packets.find((p) => {
      const hay = [
        p.info,
        p.src,
        p.dst,
        p.protocol,
        p.src_port != null ? `${p.src}:${p.src_port}` : '',
        p.dst_port != null ? `${p.dst}:${p.dst_port}` : '',
      ].filter(Boolean).join(' ').toLowerCase()
      return hay.includes(q)
    })
    if (!hit) { setFindError(`No packet matches "${findQuery.trim()}"`); return }
    setFindError('')
    await selectPacket(hit.no)
    setModal(null)
  }, [findQuery, packets, selectPacket])

  const DISPLAY_SAMPLES = ['http', 'dns', 'tls', 'ssh', 'tcp.flags.reset==1', 'tcp.analysis.retransmission', 'tcp.port==443']
  const CAPTURE_SAMPLES = ['tcp', 'udp', 'port 80', 'tcp port 443', 'host 10.0.0.5']

  const selPkt = packets.find(p => p.no === selected) || null
  const stats = protocolStats(packets)
  const conversations = conversationRows(packets)

  const handleMenuItem = (menu, item) => {
    setMenuOpen(null)
    if (item === 'Options') setModal('capture-options')
    else if (item === 'Find Packet') setModal('find')
    else if (item === 'Protocol Hierarchy') setModal('protocol-hierarchy')
    else if (item === 'Conversations') setModal('conversations')
    else if (item === 'I/O Graph') setModal('io-graph')
    else if (item.includes('Follow') && streamPayload.length) setModal('stream')
    else if (item === 'Start') setCapturing(true)
    else if (item === 'Stop') setCapturing(false)
    else if (item === 'Restart') { setCapturing(true); load() }
    else if (item === 'Zoom In') setZoom((z) => Math.min(140, z + 10))
    else if (item === 'Zoom Out') setZoom((z) => Math.max(80, z - 10))
    else if (item === 'About Wireshark') setModal('about')
  }

  return (
    <div className={`ws-sim ${embedded ? 'h-full min-h-0 flex flex-col overflow-hidden' : 'min-h-screen'}`}>
      <style>{SCOPED_CSS}</style>

      <div className="ws-topbar">
        <div className="flex items-center gap-3 min-w-0">
          <Waves size={18} style={{ color: 'var(--ws-blue)' }} />
          <span className="font-semibold text-white">Wireshark</span>
          <span className="text-xs hidden sm:inline" style={{ color: 'var(--ws-muted)' }}>
            {inv.interface ? `${inv.interface} · ` : ''}{scenario?.title || slug}
          </span>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <button className="ws-btn" onClick={load}><RefreshCw size={13} /> Refresh</button>
          <LabChromeControls
            buttonClass="ws-btn"
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

      <div className="ws-menubar" onMouseLeave={() => setMenuOpen(null)}>
        {WS_MENUS.map(([menu, items]) => (
          <div key={menu} className="relative">
            <button
              type="button"
              className={`ws-menu-btn ${menuOpen === menu ? 'ws-on' : ''}`}
              onClick={() => setMenuOpen(menuOpen === menu ? null : menu)}
              onMouseEnter={() => menuOpen && setMenuOpen(menu)}
            >
              {menu}
            </button>
            {menuOpen === menu && (
              <div className="ws-menu-pop">
                {items.map((item, i) => (
                  <button key={`${item}-${i}`} type="button" className="ws-menu-item" onClick={() => handleMenuItem(menu, item)}>
                    <span>{item}</span>
                    {['Open', 'Save', 'Start', 'Stop', 'Options', 'Protocol Hierarchy', 'Conversations', 'I/O Graph'].includes(item) && <span className="text-slate-400">›</span>}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="ws-toolbar">
        {[
          [FolderOpen, 'Open capture', () => setModal('capture-options')],
          [Save, 'Save capture', () => setModal('saved')],
          [capturing ? Square : PlayCircle, capturing ? 'Stop capture' : 'Start capture', () => setCapturing((c) => !c), capturing ? 'ws-live' : ''],
          [RefreshCw, 'Restart capture', () => { setCapturing(true); load() }],
          [Search, 'Find packet', () => setModal('find')],
          [SkipBack, 'First packet', () => packets[0] && selectPacket(packets[0].no)],
          [ArrowLeft, 'Previous packet', () => {
            const idx = packets.findIndex((p) => p.no === selected)
            if (idx > 0) selectPacket(packets[idx - 1].no)
          }],
          [ArrowRight, 'Next packet', () => {
            const idx = packets.findIndex((p) => p.no === selected)
            if (idx >= 0 && idx < packets.length - 1) selectPacket(packets[idx + 1].no)
          }],
          [SkipForward, 'Last packet', () => packets[packets.length - 1] && selectPacket(packets[packets.length - 1].no)],
          [ZoomIn, 'Zoom in', () => setZoom((z) => Math.min(140, z + 10))],
          [ZoomOut, 'Zoom out', () => setZoom((z) => Math.max(80, z - 10))],
          [BarChart3, 'I/O Graph', () => setModal('io-graph')],
          [Network, 'Conversations', () => setModal('conversations')],
          [Settings, 'Capture Options', () => setModal('capture-options')],
        ].map(([Icon, title, action, klass]) => (
          <button key={title} type="button" className={`ws-tool ${klass || ''}`} title={title} onClick={action}>
            <Icon size={15} />
          </button>
        ))}
        <span className="ml-auto text-[10px] ws-mono" style={{ color: 'var(--ws-muted)' }}>
          {capturing ? 'Live capture running' : 'Capture stopped'} · zoom {zoom}%
        </span>
      </div>

      <div className="p-4 max-w-[1200px] mx-auto" style={{ fontSize: `${zoom}%` }}>
        {error && <div className="ws-banner ws-banner-err"><XCircle size={15} className="shrink-0 mt-0.5" /> {error}</div>}

        {inv.task && (
          <div className="ws-banner ws-banner-task">
            <Target size={15} className="shrink-0 mt-0.5" style={{ color: 'var(--ws-blue)' }} />
            <span><b>Task:</b> {inv.task}</span>
          </div>
        )}

        {/* KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
          {[
            ['On wire', summary.wire_packets ?? 0, 'var(--ws-muted)'],
            ['Captured', summary.captured_packets ?? 0, 'var(--ws-blue)'],
            ['Displayed', summary.displayed_packets ?? packets.length, 'var(--ws-green)'],
            ['Marked', summary.marked_packets ?? marked.size, marked.size ? 'var(--ws-amber)' : 'var(--ws-muted)'],
            ['Stream', summary.followed_stream != null && summary.followed_stream !== '' ? `#${summary.followed_stream}` : '—', followedStream != null ? 'var(--ws-purple)' : 'var(--ws-muted)'],
          ].map(([label, val, color]) => (
            <div key={label} className="ws-card p-3">
              <div className="text-[11px]" style={{ color: 'var(--ws-muted)' }}>{label}</div>
              <div className="text-lg font-bold mt-0.5 ws-mono" style={{ color }}>{val}</div>
            </div>
          ))}
        </div>

        {/* Capture filter bar (what's recorded on the wire) */}
        <div className="mb-2">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--ws-muted)' }}>
              Capture filter (BPF) — decides which packets are recorded
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="ws-filterbar ws-capture flex-1">
              <span className="ws-filter-tag" style={{ color: 'var(--ws-blue)' }}>capture</span>
              <input
                className="ws-filter-input"
                value={captureInput}
                spellCheck={false}
                placeholder="e.g. tcp port 443  ·  host 10.0.0.5  ·  empty = all"
                onChange={e => setCaptureInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') applyCaptureFilter() }}
              />
            </div>
            <button className="ws-btn ws-btn-primary" disabled={busy} onClick={applyCaptureFilter}>
              {busy ? <RefreshCw size={13} className="animate-spin" /> : <Filter size={13} />} Set capture
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {CAPTURE_SAMPLES.map(s => (
              <button key={s} className="ws-chip" onClick={() => setCaptureInput(s)}>{s}</button>
            ))}
          </div>
        </div>

        {/* Display filter bar (narrows the captured view) */}
        <div className="mb-3 mt-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--ws-muted)' }}>
              Display filter — narrows the captured view
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`ws-filterbar ws-display flex-1 ${displayBad ? 'ws-bad' : ''}`}>
              <span className="ws-filter-tag" style={{ color: displayBad ? 'var(--ws-red)' : 'var(--ws-green)' }}>display</span>
              <input
                className="ws-filter-input"
                value={displayInput}
                spellCheck={false}
                placeholder="e.g. http  ·  tcp.stream==4  ·  tcp.flags.reset==1"
                onChange={e => { setDisplayInput(e.target.value); setDisplayBad(false) }}
                onKeyDown={e => { if (e.key === 'Enter') applyDisplayFilter() }}
              />
            </div>
            <button className="ws-btn ws-btn-primary" disabled={busy} onClick={applyDisplayFilter} style={{ background: 'var(--ws-green)' }}>
              {busy ? <RefreshCw size={13} className="animate-spin" /> : <Search size={13} />} Apply
            </button>
            <button className="ws-btn" disabled={busy} onClick={clearFilters} title="Clear display filter + followed stream">
              <Eraser size={13} /> Clear
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {DISPLAY_SAMPLES.map(s => (
              <button key={s} className="ws-chip" onClick={() => { setDisplayInput(s); setDisplayBad(false) }}>{s}</button>
            ))}
            {DISPLAY_AUTOCOMPLETE.map(s => (
              <button key={s} className="ws-chip" onClick={() => { setDisplayInput((prev) => prev ? `${prev} && ${s}` : s); setDisplayBad(false) }}>{s}</button>
            ))}
          </div>
        </div>

        {/* Packet list */}
        <div className="ws-card overflow-hidden">
          <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider border-b flex items-center justify-between"
               style={{ color: 'var(--ws-muted)', borderColor: 'var(--ws-border)' }}>
            <span>Packet list ({packets.length} displayed)</span>
            {inv.capture_active === false && <span style={{ color: 'var(--ws-amber)' }}>capture stopped</span>}
          </div>
          <div className="max-h-[360px] overflow-y-auto">
            {packets.length === 0 ? (
              <div className="p-8 text-center text-sm" style={{ color: 'var(--ws-muted)' }}>
                No packets match the current filters. Adjust the capture or display filter above.
              </div>
            ) : (
              <table className="ws-table">
                <thead>
                  <tr>
                    <th style={{ width: 36 }}></th>
                    <th>No.</th><th>Time</th><th>Source</th><th>Destination</th>
                    <th>Proto</th><th>Length</th><th>Info</th><th style={{ width: 60 }}></th>
                  </tr>
                </thead>
                <tbody>
                  {packets.map(p => {
                    const isSel = p.no === selected
                    const isMarked = marked.has(Number(p.no))
                    return (
                      <tr
                        key={p.no}
                        ref={(el) => { if (el) rowRefs.current[p.no] = el; else delete rowRefs.current[p.no] }}
                        onClick={() => selectPacket(p.no)}
                        className={`ws-row ${isSel ? 'ws-selected' : ''}`}
                        style={{ background: isMarked ? 'rgba(245,196,81,.12)' : rowTint(p) }}
                      >
                        <td>
                          <button
                            onClick={(e) => toggleMark(p.no, e)}
                            title={isMarked ? 'Unmark packet' : 'Mark packet'}
                            style={{ color: isMarked ? 'var(--ws-amber)' : 'var(--ws-muted)' }}
                          >
                            <Flag size={12} fill={isMarked ? 'currentColor' : 'none'} />
                          </button>
                        </td>
                        <td className="ws-mono" style={{ color: 'var(--ws-muted)' }}>{p.no}</td>
                        <td className="ws-mono" style={{ color: 'var(--ws-muted)' }}>{Number(p.time).toFixed(6)}</td>
                        <td className="ws-mono">{p.src}{p.src_port ? `:${p.src_port}` : ''}</td>
                        <td className="ws-mono">{p.dst}{p.dst_port ? `:${p.dst_port}` : ''}</td>
                        <td className="ws-mono font-semibold" style={{ color: protoColor(p.protocol) }}>{p.protocol}</td>
                        <td className="ws-mono" style={{ color: 'var(--ws-muted)' }}>{p.length}</td>
                        <td className="ws-info">{p.info}{p.tcp_flags ? `  [${p.tcp_flags}]` : ''}</td>
                        <td>
                          {(p.protocol || '').toUpperCase() === 'TCP' || p.stream_id != null ? (
                            <button
                              onClick={(e) => follow(p, e)}
                              title="Follow TCP stream"
                              className="inline-flex items-center gap-1 text-[10px] font-semibold"
                              style={{ color: 'var(--ws-purple)' }}
                            >
                              <GitBranch size={11} /> follow
                            </button>
                          ) : null}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Packet detail — Wireshark 3-pane: tree + hex + stream */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mt-3">
          <div className="ws-card overflow-hidden lg:col-span-2">
            <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider border-b flex items-center justify-between"
                 style={{ color: 'var(--ws-muted)', borderColor: 'var(--ws-border)' }}>
              <span>Packet Bytes {selPkt ? `· #${selPkt.no}` : ''}</span>
              <span className="normal-case font-normal">Protocol tree · Hex dump</span>
            </div>
            {!selPkt ? (
              <div className="p-6 text-sm text-center" style={{ color: 'var(--ws-muted)' }}>Select a packet to view the dissection tree and hex dump.</div>
            ) : (
              <div className="ws-hex-grid p-3">
                <div className="ws-dissect-tree">
                  {dissectTree(selPkt).map((row, i) => (
                    <div key={i} className="ws-dissect-row" style={{ paddingLeft: `${row.depth * 12 + 4}px`, color: row.highlight ? protoColor(selPkt.protocol) : 'var(--ws-text)' }}>
                      ▸ {row.label}
                    </div>
                  ))}
                </div>
                <div className="ws-hex-dump">
                  {hexDump(selPkt).map((line) => (
                    <div key={line.offset} className="flex gap-2">
                      <span className="ws-hex-offset">{line.offset}</span>
                      <span className="ws-hex-byte">{line.bytes.join(' ')}</span>
                      <span className="ws-hex-ascii ml-auto">{line.ascii}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* follow tcp stream */}
          <div className="ws-card overflow-hidden">
            <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider border-b flex items-center gap-1.5"
                 style={{ color: 'var(--ws-muted)', borderColor: 'var(--ws-border)' }}>
              <GitBranch size={12} /> Follow TCP stream {followedStream != null ? `· #${followedStream}` : ''}
            </div>
            {streamPayload.length === 0 ? (
              <div className="p-6 text-sm text-center" style={{ color: 'var(--ws-muted)' }}>
                Click <b>follow</b> on a TCP packet to reassemble its conversation.
              </div>
            ) : (
              <div className="ws-stream m-3">
                {streamPayload.map((seg, i) => {
                  const toServer = seg.direction === 'c2s' || seg.direction === 'request' || seg.direction === 'out'
                  const color = toServer ? 'var(--ws-blue)' : 'var(--ws-red)'
                  return (
                    <div key={i} className="mb-1.5">
                      <span style={{ color }} className="inline-flex items-center gap-1 mr-1.5">
                        {toServer ? <ArrowRight size={11} /> : <ArrowLeft size={11} />}
                      </span>
                      <span style={{ color }}>{seg.data}</span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* protocol legend + events */}
        <div className="flex flex-wrap items-center gap-3 mt-3 text-[11px]" style={{ color: 'var(--ws-muted)' }}>
          <ArrowLeftRight size={12} />
          {['HTTP', 'DNS', 'TLS', 'SSH', 'TCP', 'UDP'].map(p => (
            <span key={p} className="inline-flex items-center gap-1">
              <span style={{ width: 9, height: 9, borderRadius: 2, background: protoColor(p), display: 'inline-block' }} /> {p}
            </span>
          ))}
        </div>

        {(state?.events || []).length > 0 && (
          <div className="mt-3 ws-card p-3">
            <div className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--ws-muted)' }}>Events</div>
            <div className="space-y-1.5">
              {(state.events || []).slice(-6).map((ev, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  {ev.severity === 'error' ? <XCircle size={13} className="mt-0.5 shrink-0" style={{ color: 'var(--ws-red)' }} />
                    : ev.severity === 'warning' ? <AlertTriangle size={13} className="mt-0.5 shrink-0" style={{ color: 'var(--ws-amber)' }} />
                    : <CheckCircle2 size={13} className="mt-0.5 shrink-0" style={{ color: 'var(--ws-green)' }} />}
                  <span style={{ color: 'var(--ws-text)' }}>{ev.message}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="ws-statusbar">
        <span>{inv.interface || 'Ethernet0'}</span>
        <span>Packets: {summary.wire_packets ?? packets.length}</span>
        <span>Displayed: {packets.length}</span>
        <span>Marked: {marked.size}</span>
        <span className="ml-auto">{displayInput ? `Display filter: ${displayInput}` : 'Ready'}</span>
      </div>

      {modal === 'stream' && (
        <ModalShell title={`Follow TCP Stream${followedStream != null ? ` #${followedStream}` : ''}`} onClose={() => setModal(null)}>
          <div className="flex items-center gap-2 mb-3 flex-wrap text-xs">
            <label className="flex items-center gap-1.5">
              <span className="text-slate-500">Show as</span>
              <select
                className="border border-slate-300 rounded px-2 py-1 bg-white"
                value={streamFormat}
                onChange={(e) => setStreamFormat(e.target.value)}
              >
                <option>ASCII</option><option>Hex Dump</option><option>Raw</option><option>UTF-8</option><option>C Arrays</option>
              </select>
            </label>
          </div>
          <div className="font-mono text-xs bg-white border border-slate-300 rounded p-3 max-h-[55vh] overflow-auto leading-6 whitespace-pre-wrap break-words">
            {streamPayload.length === 0 ? (
              <div className="text-slate-500">No stream selected. Choose a TCP packet and click follow.</div>
            ) : streamPayload.map((seg, i) => {
              const toServer = seg.direction === 'c2s' || seg.direction === 'request' || seg.direction === 'out'
              return (
                <div key={i} style={{ color: toServer ? '#c2410c' : '#2563eb' }}>
                  {formatStreamData(seg.data, streamFormat)}
                </div>
              )
            })}
          </div>
        </ModalShell>
      )}

      {modal === 'protocol-hierarchy' && (
        <ModalShell title="Protocol Hierarchy Statistics" onClose={() => setModal(null)}>
          <table className="ws-light-table">
            <thead><tr><th>Protocol</th><th>% Packets</th><th>Packets</th><th>Bytes</th><th>Mbit/s</th></tr></thead>
            <tbody>
              {stats.map((s) => (
                <tr key={s.proto}><td>{s.proto}</td><td>{s.pct}%</td><td>{s.count}</td><td>{s.bytes.toLocaleString()}</td><td>{((s.bytes * 8) / 1_000_000).toFixed(3)}</td></tr>
              ))}
            </tbody>
          </table>
        </ModalShell>
      )}

      {modal === 'conversations' && (
        <ModalShell title="Conversations" onClose={() => setModal(null)}>
          <table className="ws-light-table">
            <thead><tr><th>Address A</th><th>Address B</th><th>Protocol</th><th>Packets</th><th>Bytes</th><th>Duration</th><th></th></tr></thead>
            <tbody>
              {conversations.map((c) => {
                const convPkt = packets.find((p) => {
                  const a = `${p.src}${p.src_port ? `:${p.src_port}` : ''}`
                  const b = `${p.dst}${p.dst_port ? `:${p.dst_port}` : ''}`
                  return (a === c.a && b === c.b) || (a === c.b && b === c.a)
                })
                const canFollow = convPkt && ((c.proto || '').toUpperCase() === 'TCP' || convPkt.stream_id != null)
                return (
                  <tr key={`${c.a}-${c.b}`}>
                    <td>{c.a}</td><td>{c.b}</td><td>{c.proto}</td><td>{c.packets}</td><td>{c.bytes}</td><td>{c.duration.toFixed(3)}s</td>
                    <td>
                      {canFollow && (
                        <button type="button" className="text-blue-600" onClick={() => { setModal(null); follow(convPkt) }}>Follow Stream</button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </ModalShell>
      )}

      {modal === 'io-graph' && (
        <ModalShell title="I/O Graphs" onClose={() => setModal(null)}>
          <div className="grid gap-3">
            {stats.slice(0, 5).map((s, i) => (
              <div key={s.proto} className="ws-graph-row">
                <span className="font-mono text-xs">{s.proto}</span>
                <div className="bg-slate-200 rounded-full overflow-hidden">
                  <div className="ws-graph-bar" style={{ width: `${Math.max(8, s.pct)}%`, filter: `hue-rotate(${i * 35}deg)` }} />
                </div>
                <span className="text-right text-xs">{s.count} packets</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-slate-500 mt-4">Packet counts per protocol across the current capture{displayInput ? ` (display filter: ${displayInput})` : ''}.</p>
        </ModalShell>
      )}

      {modal === 'capture-options' && (
        <ModalShell title="Capture Options" onClose={() => setModal(null)}>
          <div className="grid lg:grid-cols-[1.2fr_.8fr] gap-4">
            <div>
              <div className="font-semibold mb-2">Interfaces</div>
              <table className="ws-light-table">
                <thead><tr><th></th><th>Interface</th><th>Traffic</th><th>Link-layer header</th><th>Promiscuous</th></tr></thead>
                <tbody>
                  {[
                    ['Ethernet0', '████████░░', 'Ethernet', true],
                    ['Wi-Fi', '███░░░░░░░', 'Ethernet', false],
                    ['Loopback', '█░░░░░░░░░', 'Null/Loopback', true],
                  ].map(([name, spark, ll, prom]) => {
                    const active = name === (inv.interface || 'Ethernet0')
                    return (
                      <tr key={name} style={active ? { background: '#e6f0ff' } : undefined}>
                        <td>
                          <span
                            title={active ? 'Active capture interface' : 'Inactive'}
                            style={{
                              display: 'inline-block', width: 9, height: 9, borderRadius: 999,
                              background: active ? '#2563eb' : '#cbd5e1',
                            }}
                          />
                        </td>
                        <td>{name}</td>
                        <td className="font-mono text-blue-600">{spark}</td>
                        <td>{ll}</td>
                        <td>{prom ? 'Yes' : 'No'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              <p className="text-xs text-slate-500 mt-2">Capturing on <span className="font-mono">{inv.interface || 'Ethernet0'}</span> (fixed for this lab).</p>
            </div>
            <div className="space-y-3">
              <label className="block text-xs font-semibold">Capture filter<input className="mt-1 w-full border rounded px-2 py-1 font-mono" value={captureInput} onChange={(e) => setCaptureInput(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { applyCaptureFilter(); setModal(null) } }} /></label>
              <div className="text-xs">
                <div className="font-semibold">Output file</div>
                <div className="mt-1 font-mono text-slate-600">/captures/fixitlab-session.pcapng</div>
              </div>
              <button className="ws-btn ws-btn-primary" onClick={() => { applyCaptureFilter(); setCapturing(true); setModal(null) }}><Radio size={13} /> Start</button>
            </div>
          </div>
        </ModalShell>
      )}

      {['about', 'saved', 'find'].includes(modal) && (
        <ModalShell title={modal === 'about' ? 'About Wireshark' : modal === 'saved' ? 'Save Capture File' : 'Find Packet'} onClose={() => setModal(null)}>
          {modal === 'about' && <p className="text-sm">Wireshark 4.2.0 for FixitLab packet analysis labs. Menus, filters, streams, statistics, and capture options are interactive capture analysis backed by lab state.</p>}
          {modal === 'saved' && <p className="text-sm">Capture saved as <span className="font-mono">fixitlab-session.pcapng</span>.</p>}
          {modal === 'find' && (
            <div>
              <div className="flex gap-2">
                <input
                  className="border rounded px-2 py-1 flex-1"
                  placeholder="Find by Info, Source, Destination, or Protocol"
                  value={findQuery}
                  autoFocus
                  onChange={(e) => { setFindQuery(e.target.value); setFindError('') }}
                  onKeyDown={(e) => { if (e.key === 'Enter') findPacket() }}
                />
                <button type="button" className="px-3 py-1 rounded bg-blue-600 text-white flex items-center gap-1" onClick={findPacket}><Eye size={13} /> Find</button>
              </div>
              {findError && <p className="text-xs text-red-600 mt-2">{findError}</p>}
              <p className="text-xs text-slate-500 mt-2">Selects the first displayed packet whose Info, addresses, or protocol contains your search text.</p>
            </div>
          )}
        </ModalShell>
      )}
    </div>
  )
}
