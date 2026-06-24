import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Radar, Terminal, Play, RefreshCw, ArrowLeft, StopCircle, Lightbulb,
  XCircle, AlertTriangle, Server, ShieldAlert, Target, CheckCircle2,
  History, Network, Crosshair,
} from 'lucide-react'
import { nmapApi } from '../../api/nmap'
import { LabChromeControls } from '../lab/LabChromeBar'

/* ── scoped, self-contained "security tool" chrome (no shared CSS) ── */
const SCAN_PROFILES = [
  { id: 'quick', label: 'Quick scan', flags: ['-T4'], ports: '22,80,443', desc: 'Fast top ports' },
  { id: 'intense', label: 'Intense scan', flags: ['-T4', '-A', '-v'], ports: '', desc: 'OS, version, scripts' },
  { id: 'ping', label: 'Ping scan', flags: ['-sn'], ports: '', desc: 'Host discovery only' },
  { id: 'comprehensive', label: 'Comprehensive', flags: ['-sS', '-sV', '-O'], ports: '1-1024', desc: 'SYN + versions + OS' },
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
`

function StateBadge({ state }) {
  const cls = state === 'open' ? 'nm-b-open' : state === 'filtered' ? 'nm-b-filtered' : 'nm-b-closed'
  return <span className={`nm-badge ${cls}`}>{(state || 'closed').toUpperCase()}</span>
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
  const [tab, setTab] = useState('results') // results | history
  const [selectedHost, setSelectedHost] = useState(null)
  const pollRef = useRef(null)

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
    pollRef.current = setInterval(load, 20000)
    return () => clearInterval(pollRef.current)
  }, [load])

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

  const runScan = useCallback(async () => {
    if (scanning) return
    if (!targets.trim()) { setError('Enter a target (IP, CIDR, range, hostname, or "all")'); return }
    setScanning(true)
    setError('')
    try {
      const res = await nmapApi.scan(sessionId, {
        targets: targets.trim(),
        flags: Array.from(flags),
        ports: ports.trim() || undefined,
        sudo,
      })
      if (res?.ok === false) {
        setError(res.error || res.message || 'Scan rejected')
      } else if (res?.scan) {
        setLastScan(res.scan)
        setTab('results')
        const firstUp = (res.scan.hosts || []).find(h => h.state === 'up') || res.scan.hosts?.[0]
        setSelectedHost(firstUp?.ip || null)
      }
      // Refresh aggregate state so summary / scan history update.
      load()
    } catch {
      setError('Scan failed — try again')
    } finally {
      setScanning(false)
    }
  }, [scanning, targets, flags, ports, sudo, sessionId, load])

  const resetSession = useCallback(async () => {
    try { await nmapApi.action(sessionId, 'reset', {}) } catch { /* ignore */ }
    setLastScan(null)
    setSelectedHost(null)
    load()
  }, [sessionId, load])

  const summary = state?.summary || {}
  const inventory = state?.inventory || {}
  const goal = state?.goal || {}
  const firewall = inventory.firewall
  const scanHosts = lastScan?.hosts || []
  const activeHost = scanHosts.find(h => h.ip === selectedHost) || scanHosts[0] || null

  const FLAG_OPTS = [
    ['-sn', 'Ping sweep'], ['-sS', 'SYN (sudo)'], ['-sT', 'Connect'],
    ['-sV', 'Version'], ['-O', 'OS (sudo)'], ['-A', 'Aggressive'], ['-Pn', 'Skip discovery'],
  ]

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
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--nm-muted)' }}>Profile</span>
            {SCAN_PROFILES.map((p) => (
              <button key={p.id} type="button" title={p.desc}
                onClick={() => { setProfile(p.id); setFlags(new Set(p.flags)); setPorts(p.ports) }}
                className={`nm-chip ${profile === p.id ? 'nm-chip-active' : ''}`}>{p.label}</button>
            ))}
          </div>
          <div className="flex flex-col lg:flex-row gap-3">
            <div className="flex-1 min-w-0">
              <label className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--nm-muted)' }}>Target(s)</label>
              <input
                className="nm-input w-full mt-1"
                value={targets}
                spellCheck={false}
                placeholder="10.10.10.0/24  ·  10.10.10.20  ·  10.10.10.1-50  ·  all"
                onChange={e => setTargets(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') runScan() }}
              />
            </div>
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
            <button className="nm-btn nm-btn-primary justify-center" disabled={scanning} onClick={runScan}>
              {scanning ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />} Scan
            </button>
          </div>
        </div>

        {/* tabs */}
        <div className="flex items-center gap-2 mb-3">
          {[['results', 'Scan results', Crosshair], ['history', 'History', History]].map(([k, label, Icon]) => (
            <button key={k} onClick={() => setTab(k)} className={`nm-tab flex items-center gap-1.5 ${tab === k ? 'nm-tab-active' : ''}`}>
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>

        {tab === 'results' && (
          !lastScan ? (
            <div className="nm-card p-10 text-center text-sm" style={{ color: 'var(--nm-muted)' }}>
              <Radar size={26} className="mx-auto mb-2 opacity-50" />
              Build a scan above and press <b>Scan</b> to discover the network.
            </div>
          ) : (
            <div className="space-y-3">
              {/* scan summary line */}
              <div className="nm-console">
                <span style={{ color: 'var(--nm-green)' }}># {lastScan.command}</span>
                {'\n'}{lastScan.summary || `${lastScan.hosts_up ?? scanHosts.length} host(s) up, ${lastScan.addresses_scanned ?? '?'} address(es) scanned`}
                {lastScan.warning ? `\n! ${lastScan.warning}` : ''}
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-3">
                {/* hosts list */}
                <div className="nm-card overflow-hidden">
                  <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider border-b" style={{ color: 'var(--nm-muted)', borderColor: 'var(--nm-border)' }}>
                    Hosts ({scanHosts.length})
                  </div>
                  <div className="max-h-[420px] overflow-y-auto">
                    {scanHosts.length === 0 ? (
                      <div className="p-4 text-xs" style={{ color: 'var(--nm-muted)' }}>No hosts responded.</div>
                    ) : scanHosts.map(h => {
                      const open = (h.ports || []).filter(p => p.state === 'open').length
                      return (
                        <button
                          key={h.ip}
                          onClick={() => setSelectedHost(h.ip)}
                          className="w-full text-left px-3 py-2.5 border-b flex items-center justify-between gap-2"
                          style={{
                            borderColor: '#152015',
                            background: h.ip === selectedHost ? '#132013' : 'transparent',
                          }}
                        >
                          <div className="min-w-0">
                            <div className="nm-mono text-sm" style={{ color: 'var(--nm-text)' }}>{h.ip}</div>
                            <div className="text-[11px] truncate" style={{ color: 'var(--nm-muted)' }}>
                              {h.hostname || (h.os ? h.os : 'unknown host')}
                            </div>
                          </div>
                          <div className="flex flex-col items-end gap-1 shrink-0">
                            <span className={`nm-badge ${h.state === 'up' ? 'nm-b-up' : 'nm-b-closed'}`}>{(h.state || 'down').toUpperCase()}</span>
                            {open > 0 && <span className="text-[10px] nm-mono" style={{ color: 'var(--nm-green)' }}>{open} open</span>}
                          </div>
                        </button>
                      )
                    })}
                  </div>
                </div>

                {/* selected host detail / ports table */}
                <div className="nm-card overflow-hidden">
                  {!activeHost ? (
                    <div className="p-6 text-sm text-center" style={{ color: 'var(--nm-muted)' }}>Select a host to view ports.</div>
                  ) : (
                    <>
                      <div className="px-4 py-3 border-b flex flex-wrap items-center gap-x-4 gap-y-1" style={{ borderColor: 'var(--nm-border)' }}>
                        <span className="nm-mono text-base font-semibold text-white">{activeHost.ip}</span>
                        {activeHost.hostname && <span className="text-xs" style={{ color: 'var(--nm-muted)' }}>{activeHost.hostname}</span>}
                        {activeHost.mac && <span className="text-[11px] nm-mono" style={{ color: 'var(--nm-muted)' }}>{activeHost.mac}{activeHost.vendor ? ` (${activeHost.vendor})` : ''}</span>}
                        {activeHost.os && (
                          <span className="nm-badge nm-b-up">OS: {activeHost.os}{activeHost.os_accuracy ? ` ${activeHost.os_accuracy}%` : ''}</span>
                        )}
                      </div>
                      {(activeHost.ports || []).length === 0 ? (
                        <div className="p-6 text-sm text-center" style={{ color: 'var(--nm-muted)' }}>
                          No ports reported. Add <span className="nm-mono">-p</span> / a service scan (<span className="nm-mono">-sV</span>).
                        </div>
                      ) : (
                        <div className="max-h-[420px] overflow-y-auto">
                          <table className="nm-table">
                            <thead>
                              <tr><th>Port</th><th>State</th><th>Service</th><th>Version</th></tr>
                            </thead>
                            <tbody>
                              {activeHost.ports.map(p => (
                                <tr key={`${p.port}/${p.proto}`}>
                                  <td className="nm-mono">{p.port}/{p.proto || 'tcp'}</td>
                                  <td><StateBadge state={p.state} /></td>
                                  <td>{p.service || '—'}</td>
                                  <td className="nm-mono text-[11px]" style={{ color: 'var(--nm-muted)' }}>
                                    {[p.product, p.version].filter(Boolean).join(' ') || '—'}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          )
        )}

        {tab === 'history' && (
          <div className="nm-card overflow-hidden">
            {(state?.scan_log || []).length === 0 ? (
              <div className="p-8 text-sm text-center" style={{ color: 'var(--nm-muted)' }}>No scans run yet.</div>
            ) : (
              <div className="max-h-[460px] overflow-y-auto p-3 space-y-2">
                {(state.scan_log || []).slice().reverse().map((entry, i) => {
                  const text = typeof entry === 'string' ? entry : (entry.command || entry.summary || JSON.stringify(entry))
                  return (
                    <div key={i} className="nm-console !py-2 !text-[12px] flex items-start gap-2">
                      <span style={{ color: 'var(--nm-green)' }}>$</span>
                      <span className="flex-1">{text}</span>
                    </div>
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
    </div>
  )
}
