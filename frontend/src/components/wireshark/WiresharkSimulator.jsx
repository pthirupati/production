import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Waves, Filter, Search, ArrowLeft, StopCircle, Lightbulb, RefreshCw,
  XCircle, AlertTriangle, CheckCircle2, GitBranch, Flag, Eraser, Target,
  ArrowRight, ArrowLeftRight,
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
  const pollRef = useRef(null)
  const hydrated = useRef(false)

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
      setError('Could not load the Wireshark simulator')
    }
  }, [sessionId, slug])

  useEffect(() => {
    load()
    pollRef.current = setInterval(load, 20000)
    return () => clearInterval(pollRef.current)
  }, [load])

  const inv = state?.inventory || {}
  const summary = state?.summary || {}
  const packets = inv.packets || []
  const selected = inv.selected_packet
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
    } catch { /* ignore */ }
    finally { setBusy(false) }
  }, [sessionId, displayInput, load])

  const DISPLAY_SAMPLES = ['http', 'dns', 'tls', 'ssh', 'tcp.flags.reset==1', 'tcp.analysis.retransmission', 'tcp.port==443']
  const CAPTURE_SAMPLES = ['tcp', 'udp', 'port 80', 'tcp port 443', 'host 10.0.0.5']

  const selPkt = packets.find(p => p.no === selected) || null

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

      <div className="p-4 max-w-[1200px] mx-auto">
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
    </div>
  )
}
