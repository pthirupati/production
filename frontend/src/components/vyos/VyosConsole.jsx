import { useCallback, useEffect, useRef, useState } from 'react'
import { Network } from 'lucide-react'
import LabChromeBar from '../lab/LabChromeBar'
import { vyosApi } from '../../api/vyos'
import { simPanelRoot } from '../../utils/simLayout'
import './vyos.css'

const ACCENT = '#c8a84b'
const EMPTY = {
  interfaces: [],
  routes: [],
  bgp: [],
  ospf: {},
  firewall: { rules: [], counters: {} },
  nat: {},
  vrrp: {},
  dhcp_leases: [],
  revisions: {},
  uncommitted: false,
  diff: '',
  configure_mode: false,
  edit_path: [],
}

function bgpTone(state) {
  if (state === 'Established') return 'ok'
  if (state === 'Idle' || state === 'Active' || state === 'Connect') return 'warn'
  return 'err'
}

function promptFor(dash) {
  const host = 'vyos'
  if (dash.configure_mode) {
    return `${host}@vyos#`
  }
  return `${host}@vyos:~$`
}

export default function VyosConsole({
  sessionId,
  scenario,
  onExit,
  onStop,
  onHints,
  onCheck,
  onExtend,
  hintsLabel,
  checkDisabled,
  extendDisabled,
  embedded = false,
  onToggleTerminal,
  simTerminalOpen = false,
}) {
  const slug = scenario?.slug || ''
  const [dash, setDash] = useState(EMPTY)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [cliLine, setCliLine] = useState('')
  const [cliLog, setCliLog] = useState([])
  const [cliBusy, setCliBusy] = useState(false)
  const cliEndRef = useRef(null)
  const inputRef = useRef(null)

  const refresh = useCallback(async () => {
    if (!sessionId) return
    try {
      const data = await vyosApi.getState(sessionId, slug)
      if (data?.dashboard) setDash(data.dashboard)
      setError('')
    } catch (e) {
      setError(e?.response?.data?.error || e?.message || 'Unable to load VyOS state')
    } finally {
      setLoading(false)
    }
  }, [sessionId, slug])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 2000)
    return () => clearInterval(t)
  }, [refresh])

  useEffect(() => {
    cliEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [cliLog])

  const runCli = useCallback(async (raw) => {
    const line = (raw || '').trim()
    if (!line || !sessionId || cliBusy) return
    setCliBusy(true)
    const prompt = promptFor(dash)
    setCliLog((prev) => [...prev, { type: 'in', text: `${prompt} ${line}` }])
    try {
      const res = await vyosApi.applyCli(sessionId, line)
      const out = (res?.output || '').trimEnd()
      if (out) setCliLog((prev) => [...prev, { type: 'out', text: out }])
      if (res?.dashboard) setDash(res.dashboard)
      else await refresh()
    } catch (e) {
      setCliLog((prev) => [...prev, {
        type: 'err',
        text: e?.response?.data?.error || e?.message || 'Command failed',
      }])
    } finally {
      setCliBusy(false)
      setCliLine('')
      inputRef.current?.focus()
    }
  }, [sessionId, cliBusy, dash, refresh])

  const onCliKey = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      runCli(cliLine)
      return
    }
    if (e.key === '?' && !e.ctrlKey && !e.metaKey) {
      // Append ? and run help immediately (VyOS context help).
      e.preventDefault()
      runCli(`${cliLine}?`)
      return
    }
    if (e.key === 'Tab') {
      e.preventDefault()
      runCli(`${cliLine}<tab>`)
    }
  }

  const chromeProps = {
    onHints,
    onCheck,
    onExtend,
    onStop,
    onBackToTerminal: embedded ? (onToggleTerminal || undefined) : onExit,
    hintsLabel,
    checkDisabled,
    extendDisabled,
    backLabel: simTerminalOpen ? 'Hide terminal' : 'Terminal',
  }

  const ifaces = dash.interfaces || []
  const routes = dash.routes || []
  const bgp = dash.bgp || []
  const ospfNbs = dash.ospf?.neighbors || []
  const leases = dash.dhcp_leases || []
  const fwCounters = dash.firewall?.counters || {}
  const fwRules = dash.firewall?.rules || []
  const rev = dash.revisions || {}

  return (
    <div className={simPanelRoot(embedded, 'vyos-root')}>
      <LabChromeBar
        icon={Network}
        title="VyOS"
        subtitle={scenario?.title || slug || 'Router'}
        accent={ACCENT}
        {...chromeProps}
      />
      <div className="vyos-banner">
        <span>
          VyOS 1.4 · operational <code>{promptFor({ configure_mode: false })}</code>
          {' · '}configure → <code>vyos@vyos#</code>
          {' · '}Tab / <code>?</code> for completion
          {dash.uncommitted ? ' · uncommitted changes' : ''}
        </span>
      </div>

      {loading && <div className="vyos-banner">Loading router state…</div>}
      {error && <div className="vyos-banner" style={{ color: '#e06c6c' }}>{error}</div>}

      <div className="vyos-layout">
        <div className="vyos-cli-panel">
          <div className="vyos-cli-log">
            {cliLog.length === 0 && (
              <div className="vyos-cli-hint">
                Type VyOS commands here (configure, set, commit, show ip route, …).
                State is shared with the lab terminal.
              </div>
            )}
            {cliLog.map((row, i) => (
              <pre key={i} className={`vyos-cli-line vyos-cli-${row.type}`}>{row.text}</pre>
            ))}
            <div ref={cliEndRef} />
          </div>
          <div className="vyos-cli-input-row">
            <span className="vyos-cli-prompt">{promptFor(dash)}</span>
            <input
              ref={inputRef}
              className="vyos-cli-input"
              value={cliLine}
              disabled={cliBusy || !sessionId}
              onChange={(e) => setCliLine(e.target.value)}
              onKeyDown={onCliKey}
              spellCheck={false}
              autoCapitalize="off"
              autoComplete="off"
              placeholder="configure | set … | show ip route | commit"
            />
          </div>
        </div>

        <div className="vyos-grid">
          <section className="vyos-card">
            <h3>Interfaces</h3>
            {ifaces.length === 0 ? (
              <p className="vyos-empty">No interfaces</p>
            ) : (
              <table className="vyos-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Address</th>
                    <th>State</th>
                    <th>Desc</th>
                  </tr>
                </thead>
                <tbody>
                  {ifaces.map((iface) => (
                    <tr key={iface.name}>
                      <td>{iface.name}</td>
                      <td>{iface.address || '—'}</td>
                      <td>{iface.state || 'up'}</td>
                      <td>{iface.description || ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="vyos-card">
            <h3>Routes</h3>
            {routes.length === 0 ? (
              <p className="vyos-empty">No routes</p>
            ) : (
              <pre className="vyos-pre">{routes.join('\n')}</pre>
            )}
          </section>

          <section className="vyos-card">
            <h3>BGP neighbors</h3>
            {bgp.length === 0 ? (
              <p className="vyos-empty">No neighbors</p>
            ) : (
              <table className="vyos-table">
                <thead>
                  <tr>
                    <th>Neighbor</th>
                    <th>AS</th>
                    <th>State</th>
                    <th>Pfx</th>
                  </tr>
                </thead>
                <tbody>
                  {bgp.map((n) => (
                    <tr key={n.neighbor}>
                      <td>{n.neighbor}</td>
                      <td>{n.remote_as ?? '—'}</td>
                      <td>
                        <span className={`vyos-pill ${bgpTone(n.state)}`}>{n.state}</span>
                      </td>
                      <td>{n.prefixes ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="vyos-card">
            <h3>OSPF neighbors</h3>
            {!dash.ospf?.configured ? (
              <p className="vyos-empty">OSPFv2 is not running</p>
            ) : ospfNbs.length === 0 ? (
              <p className="vyos-empty">Configured — no adjacencies yet</p>
            ) : (
              <table className="vyos-table">
                <thead>
                  <tr>
                    <th>Neighbor ID</th>
                    <th>State</th>
                    <th>Interface</th>
                  </tr>
                </thead>
                <tbody>
                  {ospfNbs.map((n) => (
                    <tr key={`${n.neighbor_id}-${n.interface}`}>
                      <td>{n.neighbor_id}</td>
                      <td><span className="vyos-pill ok">{n.state}</span></td>
                      <td>{n.interface}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="vyos-card">
            <h3>Firewall</h3>
            {Object.keys(fwCounters).length === 0 && fwRules.length === 0 ? (
              <p className="vyos-empty">No firewall counters</p>
            ) : (
              <>
                <table className="vyos-table">
                  <thead>
                    <tr>
                      <th>Ruleset</th>
                      <th>Pkts</th>
                      <th>Bytes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(fwCounters).map(([name, c]) => (
                      <tr key={name}>
                        <td>{name}</td>
                        <td>{c.packets ?? 0}</td>
                        <td>{c.bytes ?? 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {fwRules.length > 0 && (
                  <pre className="vyos-pre" style={{ marginTop: '0.5rem' }}>
                    {fwRules.map((r) => `set ${r}`).join('\n')}
                  </pre>
                )}
              </>
            )}
          </section>

          <section className="vyos-card">
            <h3>VRRP</h3>
            {dash.vrrp?.configured ? (
              <pre className="vyos-pre">{dash.vrrp.summary || 'VRRP active'}</pre>
            ) : (
              <p className="vyos-empty">No VRRP groups</p>
            )}
          </section>

          <section className="vyos-card">
            <h3>DHCP leases</h3>
            {leases.length === 0 ? (
              <p className="vyos-empty">No leases</p>
            ) : (
              <table className="vyos-table">
                <thead>
                  <tr>
                    <th>IP</th>
                    <th>MAC</th>
                    <th>Client</th>
                  </tr>
                </thead>
                <tbody>
                  {leases.map((l) => (
                    <tr key={`${l.ip}-${l.mac}`}>
                      <td>{l.ip}</td>
                      <td>{l.mac}</td>
                      <td>{l.client || l.pool || ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="vyos-card" style={{ gridColumn: '1 / -1' }}>
            <h3>Config revisions</h3>
            <div className="vyos-meta">
              <span>rev {rev.current ?? 0}</span>
              <span>history {rev.history_count ?? 0}</span>
              <span className={`vyos-pill ${dash.uncommitted ? 'warn' : 'ok'}`}>
                {dash.uncommitted ? 'uncommitted changes' : 'clean'}
              </span>
              {dash.configure_mode && (
                <span className="vyos-pill warn">
                  [edit{(dash.edit_path || []).length ? ` ${(dash.edit_path || []).join(' ')}` : ''}]
                </span>
              )}
            </div>
            {dash.diff ? <pre className="vyos-pre" style={{ marginTop: '0.5rem' }}>{dash.diff}</pre> : null}
          </section>
        </div>
      </div>
    </div>
  )
}
