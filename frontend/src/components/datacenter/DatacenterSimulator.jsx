import { useCallback, useMemo, useRef, useState } from 'react'
import { datacenterApi } from '../../api/datacenter'
import LabChromeBar from '../lab/LabChromeBar'
import {
  LogIn, Server, AlertTriangle, Terminal, X, Power, Network, HardDrive,
  CircuitBoard, Cpu, Zap, Wrench, RotateCcw, Snowflake, Gauge, Move,
  Building2, Router, Thermometer, Fuel, BatteryCharging, Plug, ShieldCheck,
  RefreshCw, MonitorCog, Database, Boxes,
} from 'lucide-react'
import { simPanelRoot } from '../../utils/simLayout'
import { useSimSession } from '../sim/shared'
import '../../styles/sim-products.css'
import './DatacenterSimulator.css'

const DC_LAB_USER = 'lab_datacenter'
const DC_LAB_PASS = 'lab_datacenter@123'
const ACCENT = '#f97316'

const COMPONENT_META = {
  power: { label: 'Power Supply', icon: Power },
  nic: { label: 'NIC', icon: Network },
  disk: { label: 'Disk', icon: HardDrive },
  motherboard: { label: 'Motherboard', icon: CircuitBoard },
  cpu: { label: 'CPU', icon: Cpu },
  gpu: { label: 'GPU', icon: Zap },
}

const ROOM_ICONS = { data_hall: Building2, network: Router, mechanical: Thermometer, electrical: Plug }

const ROLE_META = {
  esxi_host: { label: 'ESXi Host', icon: Boxes },
  gpu_node: { label: 'GPU Node', icon: Zap },
  storage: { label: 'Storage', icon: HardDrive },
  db: { label: 'Database', icon: Database },
}

function ComponentPill({ name, status }) {
  const meta = COMPONENT_META[name] || { label: name, icon: Wrench }
  const Icon = meta.icon
  const healthy = status === 'healthy'
  return (
    <div className={`dc-component-pill ${healthy ? 'dc-comp-ok' : 'dc-comp-fail'}`}>
      <Icon size={13} />
      <span>{meta.label}</span>
      <span className="dc-comp-dot" />
    </div>
  )
}

function RoleBadge({ role }) {
  const meta = ROLE_META[role]
  if (!meta) return null
  const Icon = meta.icon
  return (
    <span className="dc-role-badge">
      <Icon size={10} /> {meta.label}
    </span>
  )
}

export default function DatacenterSimulator({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
  onToggleTerminal, simTerminalOpen = false, vmwareHref = null,
}) {
  const slug = scenario?.slug || ''
  const { state, loading, busy, run } = useSimSession(sessionId, slug, datacenterApi)
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')
  const [expandedRack, setExpandedRack] = useState(null)
  const [selectedServerId, setSelectedServerId] = useState(null)
  const [flashId, setFlashId] = useState(null)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const dragRef = useRef(null)
  const movedRef = useRef(false)

  const st = state?.state || {}
  const loggedIn = st?.session?.logged_in
  const goal = st?.goal || {}
  const broken = st?.broken || {}
  const racks = st.racks || []
  const servers = st.servers || []
  const pdus = st.pdus || []
  const cooling = st.cooling || []
  const rooms = st.rooms || []
  const network = st.network || { switches: [], topology: [] }
  const powerChain = st.power_chain || {}
  const facility = st.facility || {}
  const currentRoomId = st.current_room || 'data-hall-a'
  const currentRoom = rooms.find((r) => r.id === currentRoomId) || rooms[0] || { type: 'data_hall', racks: [] }

  const serversByRack = useMemo(() => {
    const m = {}
    for (const s of servers) { (m[s.rack] ||= []).push(s) }
    for (const rid of Object.keys(m)) m[rid].sort((a, b) => b.u_slot - a.u_slot)
    return m
  }, [servers])

  const roomRacks = useMemo(
    () => racks.filter((r) => (currentRoom.racks || []).includes(r.id)),
    [racks, currentRoom],
  )

  const selectedServer = selectedServerId ? servers.find((s) => s.id === selectedServerId) : null

  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: embedded ? (onToggleTerminal || undefined) : onExit,
    hintsLabel, checkDisabled, extendDisabled,
    backLabel: simTerminalOpen ? 'Hide terminal' : 'Terminal',
    vmwareHref,
  }

  const onFloorMouseDown = useCallback((e) => {
    dragRef.current = { startX: e.clientX, startY: e.clientY, panX: pan.x, panY: pan.y }
    movedRef.current = false
  }, [pan])
  const onFloorMouseMove = useCallback((e) => {
    if (!dragRef.current) return
    const dx = e.clientX - dragRef.current.startX
    const dy = e.clientY - dragRef.current.startY
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) movedRef.current = true
    setPan({
      x: Math.max(-260, Math.min(260, dragRef.current.panX + dx)),
      y: Math.max(-90, Math.min(90, dragRef.current.panY + dy)),
    })
  }, [])
  const onFloorMouseUp = useCallback(() => { dragRef.current = null }, [])

  const flash = (assetId) => {
    setFlashId(assetId)
    setTimeout(() => setFlashId(null), 900)
  }

  const doAction = (fn, okMsg, assetId) => {
    run(fn, okMsg).then(() => { if (assetId) flash(assetId) })
  }

  const enterRoom = (room) => {
    if (room.id === currentRoomId) return
    run(() => datacenterApi.enterRoom(sessionId, room.id), `Entered ${room.name}`)
  }

  if (!loading && state && !loggedIn) {
    const submitLogin = (e) => {
      e.preventDefault()
      if (busy) return
      const u = loginUser.trim().toLowerCase()
      const ok = (u === DC_LAB_USER && loginPass === DC_LAB_PASS) || (u === 'tech' && loginPass === 'tech')
      if (ok) {
        setLoginError('')
        run(() => datacenterApi.login(sessionId), 'Signed in')
      } else {
        setLoginError(`Invalid credentials. Use ${DC_LAB_USER} / ${DC_LAB_PASS} for training labs.`)
      }
    }
    return (
      <div className={simPanelRoot(embedded, 'bg-[#0b0e14]')}>
        <LabChromeBar title="Data Center Console" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-2xl w-[400px] overflow-hidden">
            <div className="px-6 py-4 text-white font-semibold flex items-center gap-2" style={{ background: '#1a1d2b' }}>
              <Server size={18} /> DCIM Field Console
            </div>
            <form onSubmit={submitLogin} className="p-6 space-y-4">
              <p className="text-sm text-slate-600">Badge in to the fixitlab-dc1 datacenter floor console.</p>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Username</label>
                <input value={loginUser} onChange={(e) => setLoginUser(e.target.value)} autoFocus autoComplete="username"
                  placeholder={DC_LAB_USER}
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none" />
              </div>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Password</label>
                <input type="password" value={loginPass} onChange={(e) => setLoginPass(e.target.value)} autoComplete="current-password"
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none" />
              </div>
              {loginError && (
                <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{loginError}</p>
              )}
              <button type="submit" disabled={busy}
                className="dc-btn-primary w-full py-2 flex items-center justify-center gap-2">
                <LogIn size={16} /> Badge In
              </button>
              <button type="button"
                onClick={() => { setLoginUser(DC_LAB_USER); setLoginPass(DC_LAB_PASS); setLoginError('') }}
                className="w-full py-1.5 text-xs text-slate-600 border border-slate-300 rounded hover:bg-slate-50">
                Use lab credentials (autofill)
              </button>
              <p className="text-[10px] text-slate-500 text-center pt-2 border-t border-slate-100">
                Training credentials: <span className="font-mono text-slate-700">{DC_LAB_USER}</span> / <span className="font-mono text-slate-700">{DC_LAB_PASS}</span>
              </p>
            </form>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={simPanelRoot(embedded, 'dc-shell sim-product')}>
      <LabChromeBar title="Data Center Console" subtitle={scenario?.title || slug}
        accent={ACCENT} className="lab-chrome-bar !bg-[#1a1d2b]" {...chromeProps}>
        {onToggleTerminal && (
          <button type="button" className="lab-chrome-btn flex items-center gap-1" onClick={onToggleTerminal}>
            <Terminal size={13} /> {simTerminalOpen ? 'Hide terminal' : 'Terminal'}
          </button>
        )}
      </LabChromeBar>

      {goal.objective && (
        <div className="px-4 py-2 text-sm bg-amber-50 border-b border-amber-200 flex items-center gap-2">
          <AlertTriangle size={14} className="text-amber-600 shrink-0" />
          <span><strong>{goal.title}:</strong> {goal.objective}</span>
        </div>
      )}

      {/* Room switcher */}
      <div className="dc-room-tabs">
        {rooms.map((room) => {
          const RoomIcon = ROOM_ICONS[room.type] || Building2
          const active = room.id === currentRoomId
          return (
            <button key={room.id} type="button"
              className={`dc-room-tab ${active ? 'dc-room-tab-active' : ''}`}
              onClick={() => enterRoom(room)}>
              <RoomIcon size={13} /> {room.name}
            </button>
          )
        })}
        <span className="dc-pue-pill">
          <Gauge size={12} /> PUE {facility.pue ?? '—'}
          <span className={`dc-ashrae-dot ${facility.ashrae_ok === false ? 'dc-ashrae-bad' : 'dc-ashrae-ok'}`} />
        </span>
      </div>

      {/* PDU / cooling status strip */}
      <div className="dc-status-strip">
        <div className="dc-status-group">
          <Gauge size={13} className="opacity-70" />
          {pdus.slice(0, 6).map((p) => (
            <span key={p.id} className={`dc-status-chip ${p.status === 'online' ? 'dc-chip-ok' : 'dc-chip-bad'}`}>
              {p.id} · {p.load_pct}%
            </span>
          ))}
        </div>
        <div className="dc-status-group">
          <Snowflake size={13} className="opacity-70" />
          {cooling.map((c) => (
            <span key={c.id} className={`dc-status-chip ${c.status === 'running' ? 'dc-chip-ok' : 'dc-chip-bad'}`}>
              {c.id} · {c.temp_c}°C
            </span>
          ))}
        </div>
        <div className="dc-status-hint"><Move size={12} /> Drag floor to pan</div>
      </div>

      {currentRoom.type === 'data_hall' && (
        <div
          className="dc-floor-viewport"
          onMouseDown={onFloorMouseDown}
          onMouseMove={onFloorMouseMove}
          onMouseUp={onFloorMouseUp}
          onMouseLeave={onFloorMouseUp}
        >
          <div className="dc-floor-plane" style={{ transform: `translate(${pan.x * 0.4}px, ${pan.y * 0.4}px) rotateX(55deg) rotateZ(-45deg)` }} />
          <div className="dc-racks-row" style={{ transform: `translate(${pan.x}px, ${pan.y}px)` }}>
            {roomRacks.map((rack) => {
              const rackServers = serversByRack[rack.id] || []
              const anyFailed = rackServers.some((s) => Object.values(s.components).some((c) => c !== 'healthy'))
              const isOpen = expandedRack === rack.id
              return (
                <div key={rack.id} className={`dc-rack ${isOpen ? 'dc-rack-open' : ''}`}
                  onClick={() => { if (!movedRef.current) setExpandedRack(isOpen ? null : rack.id) }}>
                  <div className="dc-rack-top" />
                  <div className={`dc-rack-front ${anyFailed ? 'dc-rack-alert' : ''}`}>
                    <div className="dc-rack-head">
                      <span className="dc-rack-id">{rack.id}</span>
                      <span className={`dc-rack-led ${anyFailed ? 'dc-led-red' : 'dc-led-green'}`} />
                    </div>
                    <div className="dc-rack-pdu">{rack.pdu}</div>
                    {!isOpen && (
                      <div className="dc-rack-mini">
                        {rackServers.length === 0 && <span className="dc-rack-empty">empty</span>}
                        {rackServers.map((s) => (
                          <span key={s.id} className={`dc-mini-slot ${s.power_state === 'on' ? 'dc-mini-on' : 'dc-mini-off'} ${Object.values(s.components).some((c) => c !== 'healthy') ? 'dc-mini-fail' : ''}`} />
                        ))}
                      </div>
                    )}
                    {isOpen && (
                      <div className="dc-rack-uslots">
                        {rackServers.length === 0 && <div className="dc-rack-empty">No servers installed</div>}
                        {rackServers.map((s) => {
                          const hasFailure = Object.values(s.components).some((c) => c !== 'healthy')
                          return (
                            <button key={s.id} type="button"
                              className={`dc-server-card ${flashId === s.id ? 'dc-flash' : ''} ${hasFailure ? 'dc-server-alert' : ''}`}
                              onClick={(e) => { e.stopPropagation(); setSelectedServerId(s.id) }}>
                              <span className="dc-server-u">U{s.u_slot}</span>
                              <span className="dc-server-host">{s.hostname}</span>
                              <span className={`dc-server-power ${s.power_state === 'on' ? 'dc-power-on' : 'dc-power-off'}`}>
                                <Power size={10} /> {s.power_state}
                              </span>
                              {hasFailure && <AlertTriangle size={12} className="dc-server-warn" />}
                            </button>
                          )
                        })}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {currentRoom.type === 'network' && (
        <div className="dc-room-body">
          <NetworkRoomView network={network} servers={servers} onSelectServer={setSelectedServerId} />
        </div>
      )}

      {currentRoom.type === 'mechanical' && (
        <div className="dc-room-body">
          <MechanicalRoomView cooling={cooling} busy={busy}
            onRestore={(cracId) => doAction(() => datacenterApi.restoreCrac(sessionId, cracId), 'CRAC restored')} />
        </div>
      )}

      {currentRoom.type === 'electrical' && (
        <div className="dc-room-body">
          <ElectricalRoomView powerChain={powerChain} facility={facility} busy={busy}
            onTrip={(pduId) => doAction(() => datacenterApi.tripPduBreaker(sessionId, pduId), 'Breaker tripped')}
            onRestore={(pduId) => doAction(() => datacenterApi.restorePdu(sessionId, pduId), 'Breaker restored')} />
        </div>
      )}

      {selectedServer && (
        <div className="dc-drawer-backdrop" onClick={() => setSelectedServerId(null)}>
          <div className="dc-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="dc-drawer-head">
              <div>
                <div className="dc-drawer-title">
                  {selectedServer.hostname} <RoleBadge role={selectedServer.role} />
                </div>
                <div className="dc-drawer-sub">{selectedServer.rack} · U{selectedServer.u_slot} · power {selectedServer.power_state}</div>
              </div>
              <button type="button" onClick={() => setSelectedServerId(null)} className="dc-drawer-close"><X size={16} /></button>
            </div>

            <div className="dc-drawer-section">
              <div className="dc-drawer-label">Component health</div>
              <div className="dc-component-grid">
                {Object.entries(selectedServer.components).map(([name, status]) => (
                  <ComponentPill key={name} name={name} status={status} />
                ))}
              </div>
            </div>

            <div className="dc-drawer-section">
              <div className="dc-drawer-label">Replace failed component</div>
              <div className="dc-action-row">
                {Object.entries(selectedServer.components).filter(([, s]) => s !== 'healthy').map(([name]) => (
                  <button key={name} type="button" disabled={busy} className="dc-btn-danger"
                    onClick={() => doAction(() => datacenterApi.replaceComponent(sessionId, name, selectedServer.id), `${COMPONENT_META[name]?.label || name} replaced`, selectedServer.id)}>
                    <Wrench size={13} /> Replace {COMPONENT_META[name]?.label || name}
                  </button>
                ))}
                {Object.values(selectedServer.components).every((s) => s === 'healthy') && (
                  <span className="dc-all-healthy">All components healthy</span>
                )}
              </div>
            </div>

            <div className="dc-drawer-section">
              <div className="dc-drawer-label">Field actions</div>
              <div className="dc-action-row">
                <button type="button" disabled={busy} className="dc-btn-outline"
                  onClick={() => doAction(() => datacenterApi.powerCycle(sessionId, selectedServer.id), 'Power cycle issued', selectedServer.id)}>
                  <Power size={13} /> Power Cycle
                </button>
                <button type="button" disabled={busy} className="dc-btn-outline"
                  onClick={() => doAction(() => datacenterApi.reseatCable(sessionId, selectedServer.id), 'Cable reseated', selectedServer.id)}>
                  <RotateCcw size={13} /> Reseat Cable
                </button>
                <button type="button" disabled={busy} className="dc-btn-outline"
                  onClick={() => doAction(() => datacenterApi.updateFirmware(sessionId, selectedServer.id, '2.14.0'), 'Firmware updated', selectedServer.id)}>
                  <Zap size={13} /> Update Firmware
                </button>
              </div>
              {broken.server === selectedServer.id && (
                <div className="dc-objective-note">
                  <AlertTriangle size={12} /> This server is the scenario target — resolve the <strong>{broken.component}</strong> issue.
                </div>
              )}
            </div>

            {selectedServer.bmc && (
              <div className="dc-drawer-section">
                <div className="dc-drawer-label"><MonitorCog size={12} className="inline mr-1" />BMC remote console</div>
                <div className="dc-bmc-panel">
                  <div className="dc-bmc-row">
                    <span className="dc-bmc-key">Endpoint</span>
                    <span className="dc-bmc-val dc-bmc-mono">{selectedServer.bmc.endpoint}</span>
                  </div>
                  <div className="dc-bmc-row">
                    <span className="dc-bmc-key">Protocol</span>
                    <span className="dc-bmc-val">{selectedServer.bmc.protocol?.toUpperCase()}</span>
                  </div>
                  <div className="dc-bmc-sensors">
                    <span>Inlet {selectedServer.bmc.sensors?.inlet_c}°C</span>
                    <span>Exhaust {selectedServer.bmc.sensors?.exhaust_c}°C</span>
                    <span>Fans {selectedServer.bmc.sensors?.fans_rpm} RPM</span>
                  </div>
                  <div className="dc-action-row">
                    <button type="button" disabled={busy} className="dc-btn-outline"
                      onClick={() => doAction(() => datacenterApi.bmcPower(sessionId, selectedServer.id, 'on'), 'BMC power on', selectedServer.id)}>
                      <Power size={13} /> Power On
                    </button>
                    <button type="button" disabled={busy} className="dc-btn-outline"
                      onClick={() => doAction(() => datacenterApi.bmcPower(sessionId, selectedServer.id, 'off'), 'BMC power off', selectedServer.id)}>
                      <Power size={13} /> Power Off
                    </button>
                    <button type="button" disabled={busy} className="dc-btn-outline"
                      onClick={() => doAction(() => datacenterApi.bmcPower(sessionId, selectedServer.id, 'reset'), 'BMC reset issued', selectedServer.id)}>
                      <RefreshCw size={13} /> Reset
                    </button>
                    <button type="button" disabled={busy} className="dc-btn-outline"
                      onClick={() => doAction(() => datacenterApi.bmcPower(sessionId, selectedServer.id, 'cycle'), 'BMC power cycle issued', selectedServer.id)}>
                      <RotateCcw size={13} /> Cycle
                    </button>
                  </div>
                  {selectedServer.bmc.sel?.length > 0 && (
                    <div className="dc-bmc-sel">
                      {selectedServer.bmc.sel.slice(0, 3).map((entry, i) => (
                        <div key={i} className="dc-bmc-sel-row">
                          <span className="dc-bmc-sel-time">{entry.time}</span> {entry.message}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function NetworkRoomView({ network, servers, onSelectServer }) {
  const hostnameById = useMemo(() => {
    const m = {}
    for (const s of servers) m[s.id] = s.hostname
    return m
  }, [servers])

  return (
    <div className="dc-network-room">
      {(network.switches || []).map((sw) => (
        <div key={sw.id} className="dc-switch-card">
          <div className="dc-switch-head">
            <Router size={14} />
            <span className="dc-switch-name">{sw.hostname}</span>
            <span className="dc-switch-loc">{sw.rack} · U{sw.u_slot}</span>
            <span className="dc-switch-model">{sw.model}</span>
          </div>
          <table className="dc-port-table">
            <thead>
              <tr><th>Port</th><th>Status</th><th>Speed</th><th>VLAN</th><th>Connected to</th></tr>
            </thead>
            <tbody>
              {(sw.ports || []).map((p) => (
                <tr key={p.port}>
                  <td>{p.port}</td>
                  <td><span className={`dc-port-badge ${p.status === 'up' ? 'dc-port-up' : 'dc-port-down'}`}>{p.status}</span></td>
                  <td>{p.speed}</td>
                  <td>{p.vlan ?? '—'}</td>
                  <td>
                    {p.connected_to ? (
                      <button type="button" className="dc-port-link"
                        onClick={() => hostnameById[p.connected_to] && onSelectServer(p.connected_to)}>
                        {hostnameById[p.connected_to] || p.connected_to}
                      </button>
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
      {(network.topology || []).length > 0 && (
        <div className="dc-topology-strip">
          <span className="dc-topology-label">Uplinks:</span>
          {network.topology.map((link, i) => (
            <span key={i} className="dc-topology-chip">{link.from} → {link.to} ({link.speed})</span>
          ))}
        </div>
      )}
    </div>
  )
}

function MechanicalRoomView({ cooling, busy, onRestore }) {
  return (
    <div className="dc-crac-grid">
      {(cooling || []).map((c) => (
        <div key={c.id} className={`dc-crac-card ${c.status !== 'running' ? 'dc-crac-alert' : ''}`}>
          <div className="dc-crac-head">
            <Thermometer size={14} />
            <span className="dc-crac-id">{c.id}</span>
            <span className={`dc-ashrae-badge ${c.ashrae_ok ? 'dc-ashrae-badge-ok' : 'dc-ashrae-badge-bad'}`}>
              {c.ashrae_ok ? 'ASHRAE OK' : 'OUT OF RANGE'}
            </span>
          </div>
          <div className="dc-crac-zone">{c.zone}</div>
          <div className="dc-crac-metrics">
            <div><span className="dc-crac-metric-label">Temp</span><span className="dc-crac-metric-val">{c.temp_c}°C</span></div>
            <div><span className="dc-crac-metric-label">Humidity</span><span className="dc-crac-metric-val">{c.humidity_pct}%</span></div>
            <div><span className="dc-crac-metric-label">Load</span><span className="dc-crac-metric-val">{c.load_kw}/{c.capacity_kw} kW</span></div>
          </div>
          <div className="dc-crac-status">
            Status: <span className={c.status === 'running' ? 'dc-text-ok' : 'dc-text-bad'}>{c.status}</span>
          </div>
          {c.status !== 'running' && (
            <button type="button" disabled={busy} className="dc-btn-outline w-full justify-center mt-2"
              onClick={() => onRestore(c.id)}>
              <RefreshCw size={13} /> Restore unit
            </button>
          )}
        </div>
      ))}
    </div>
  )
}

function ElectricalRoomView({ powerChain, facility, busy, onTrip, onRestore }) {
  const ups = powerChain.ups || []
  const rackPdus = powerChain.rack_pdus || []
  return (
    <div className="dc-electrical-room">
      <div className="dc-power-diagram">
        <div className="dc-power-node">
          <ShieldCheck size={16} />
          <span>Utility</span>
          <span className={`dc-power-node-status ${powerChain.utility?.status === 'online' ? 'dc-text-ok' : 'dc-text-bad'}`}>
            {powerChain.utility?.status} · {powerChain.utility?.voltage_v}V
          </span>
        </div>
        <div className="dc-power-arrow">→</div>
        <div className="dc-power-node">
          <Plug size={16} />
          <span>ATS</span>
          <span className="dc-power-node-status dc-text-ok">{powerChain.ats?.status}</span>
        </div>
        <div className="dc-power-arrow">→</div>
        <div className="dc-power-node">
          <Fuel size={16} />
          <span>Generator</span>
          <span className="dc-power-node-status">{powerChain.generator?.status} · {powerChain.generator?.fuel_pct}% fuel</span>
        </div>
        <div className="dc-power-arrow">→</div>
        <div className="dc-power-node">
          <BatteryCharging size={16} />
          <span>UPS ({ups.length})</span>
          <span className="dc-power-node-status dc-text-ok">
            {ups.length ? `${Math.round(ups.reduce((a, u) => a + u.load_pct, 0) / ups.length)}% load` : '—'}
          </span>
        </div>
        <div className="dc-power-arrow">→</div>
        <div className="dc-power-node">
          <Power size={16} />
          <span>Floor PDUs</span>
          <span className="dc-power-node-status dc-text-ok">
            {(powerChain.floor_pdus || []).reduce((a, p) => a + (p.load_kw || 0), 0).toFixed(1)} kW
          </span>
        </div>
      </div>

      <div className="dc-facility-metrics">
        <div className="dc-facility-metric"><span>IT Load</span><strong>{facility.it_kw} kW</strong></div>
        <div className="dc-facility-metric"><span>Cooling Load</span><strong>{facility.cooling_kw} kW</strong></div>
        <div className="dc-facility-metric"><span>Total Facility</span><strong>{facility.total_kw} kW</strong></div>
        <div className="dc-facility-metric dc-facility-pue"><span>PUE</span><strong>{facility.pue}</strong></div>
      </div>

      <div className="dc-drawer-label mt-2">Rack PDUs</div>
      <div className="dc-pdu-grid">
        {rackPdus.map((p) => (
          <div key={p.id} className={`dc-pdu-card ${p.status !== 'online' ? 'dc-pdu-tripped' : ''}`}>
            <div className="dc-pdu-card-head">
              <span className="dc-pdu-id">{p.id}</span>
              <span className={`dc-status-chip ${p.status === 'online' ? 'dc-chip-ok' : 'dc-chip-bad'}`}>{p.status}</span>
            </div>
            <div className="dc-pdu-card-meta">{p.rack} · breaker {p.breaker} · {p.load_kw} kW</div>
            <button type="button" disabled={busy} className="dc-btn-outline w-full justify-center mt-1"
              onClick={() => (p.status === 'online' ? onTrip(p.id) : onRestore(p.id))}>
              {p.status === 'online' ? 'Trip breaker' : 'Close breaker'}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
