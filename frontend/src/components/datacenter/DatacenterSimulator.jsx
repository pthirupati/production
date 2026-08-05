import { Component, useCallback, useMemo, useRef, useState, Suspense } from 'react'
import { datacenterApi } from '../../api/datacenter'
import LabChromeBar from '../lab/LabChromeBar'
import {
  LogIn, Server, AlertTriangle, Terminal, X, Power, Network, HardDrive,
  CircuitBoard, Cpu, Zap, Wrench, RotateCcw, Snowflake, Gauge, Move,
  Building2, Router, Thermometer, Fuel, BatteryCharging, Plug, ShieldCheck,
  RefreshCw, MonitorCog, Database, Boxes, Ticket, Monitor, Box,
} from 'lucide-react'
import { simPanelRoot } from '../../utils/simLayout'
import { useSimSession, GlobalSearch, indexDatacenterState } from '../sim/shared'
import { lazyWithRetry } from '../../utils/lazyWithRetry'
import {
  MotherboardPanel, RaidPanel, BiosPanel, BmcPanel, CampusRoomView,
  ServiceModePanel, InventoryPanel, FailureInjectBar,
} from './ServerTwinPanels'
import {
  NetworkRoomPhase3, CableOpsPanel, StorageStackPanel,
} from './NetworkStoragePanels'
import {
  RackPhysicsFruPanel, MonitoringPanel, OpsTicketsPanel, TrainingPanel, ComputeAiPanel,
  LiquidCoolingPanel, PxeMaasPanel, FireSafetyPanel, EnvironmentalPanel, OpticalPanel, CapacityPdmPanel,
  DrFailoverPanel, AccessControlPanel, AutomationReportPanel,
  ChangeCabPanel, SustainabilityPanel, ContainmentPanel, CablePlantPanel,
  BurninPanel, ExportersPanel, DocsEvidencePanel,
} from './OpsPhysicsPanels'
import '../../styles/sim-products.css'
import './DatacenterSimulator.css'
import DcAmbientAudio from './DcAmbientAudio'

const LazyDatacenterTwin3D = lazyWithRetry(() => import('./DatacenterTwin3D'))

/** If WebGL/R3F throws, drop to 2D floor instead of the whole-lab error banner. */
class Twin3DSafe extends Component {
  constructor(props) {
    super(props)
    this.state = { failed: false }
  }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error, info) {
    console.error('Datacenter 3D twin failed — falling back to 2D floor', error, info)
    try { this.props.onFallback?.() } catch { /* ignore */ }
  }

  render() {
    if (this.state.failed) return null
    return this.props.children
  }
}

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
  fan: { label: 'Fan', icon: Snowflake },
  dimm: { label: 'DIMM', icon: CircuitBoard },
  pcie: { label: 'PCIe', icon: Boxes },
  raid: { label: 'RAID', icon: HardDrive },
  hba: { label: 'HBA', icon: Network },
}

const ROOM_ICONS = {
  data_hall: Building2, network: Router, mechanical: Thermometer, electrical: Plug,
  campus: Building2, security: ShieldCheck, office: Building2, ops: MonitorCog,
  logistics: Boxes, safety: AlertTriangle,
}

const ROLE_META = {
  esxi_host: { label: 'ESXi Host', icon: Boxes },
  gpu_node: { label: 'GPU Node', icon: Zap },
  storage: { label: 'Storage', icon: HardDrive },
  db: { label: 'Database', icon: Database },
  app: { label: 'App', icon: Boxes },
  cache: { label: 'Cache', icon: Database },
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
  if (!role) return null
  const meta = ROLE_META[role] || { label: String(role).replace(/_/g, ' '), icon: Server }
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
  const { state, setState, loading, busy, error, run, refresh } = useSimSession(sessionId, slug, datacenterApi)
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')
  const [expandedRack, setExpandedRack] = useState(null)
  const [selectedServerId, setSelectedServerId] = useState(null)
  const [flashId, setFlashId] = useState(null)
  const [drawerTab, setDrawerTab] = useState('overview')
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [floorView, setFloorView] = useState(() => {
    // Steam-class default: immersive 3D hall. Fall back to 2D on phones /
    // reduced-motion so Twin3DSafe never bricks the lab chrome.
    try {
      if (typeof window !== 'undefined') {
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return '2d'
        if (window.matchMedia('(max-width: 900px)').matches) return '2d'
      }
    } catch { /* ignore */ }
    return '3d'
  })
  const dragRef = useRef(null)
  const movedRef = useRef(false)
  const liveTickInFlight = useRef(false)
  const busyRef = useRef(busy)
  busyRef.current = busy

  const onLiveTick = useCallback(() => {
    if (!sessionId || busyRef.current || liveTickInFlight.current) return
    liveTickInFlight.current = true
    datacenterApi.liveTick(sessionId)
      .then((res) => { if (res?.state) setState(res.state) })
      .catch(() => {})
      .finally(() => { liveTickInFlight.current = false })
  }, [sessionId, setState])

  const st = state?.state || {}
  const loggedIn = st?.session?.logged_in
  const goal = st?.goal || {}
  const broken = st?.broken || {}
  const racks = st.racks || []
  const servers = st.servers || []
  const pdus = st.pdus || []
  const cooling = st.cooling || []
  const liquidCooling = st.liquid_cooling || null
  const pxeMaas = st.pxe_maas || null
  const fireSafety = st.fire_safety || null
  const environmental = st.environmental || null
  const optical = st.optical || null
  const capacity = st.capacity || null
  const predictive = st.predictive || null
  const dr = st.dr || null
  const accessControl = st.access_control || null
  const automation = st.automation || null
  const opsReport = st.ops_report || null
  const changeCalendar = st.change_calendar || null
  const sustainability = st.sustainability || null
  const containment = st.containment || null
  const cablePlant = st.cable_plant || null
  const burnin = st.burnin || null
  const exporters = st.exporters || null
  const docLibrary = st.doc_library || null
  const evidencePack = st.evidence_pack || null
  const rooms = st.rooms || []
  const network = st.network || { switches: [], topology: [] }
  const powerChain = st.power_chain || {}
  const facility = st.facility || {}
  const campus = st.campus || {}
  const hardwareCatalog = st.hardware_catalog || {}
  const monitoring = st.monitoring || {}
  const training = st.training || {}
  const hypervisors = st.hypervisors || {}
  const aiPlatform = st.ai_platform || {}
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
  const searchServices = useMemo(() => ([
    { key: 'floor', label: 'Data hall floor', keywords: 'rack server 3d' },
    { key: 'rooms', label: 'Campus rooms', keywords: 'mdf noc mechanical electrical' },
    { key: 'tickets', label: 'Ops tickets', keywords: 'rma work order' },
  ]), [])
  const searchResources = useMemo(() => indexDatacenterState(st), [st])

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

  if (loading) {
    return (
      <div className={simPanelRoot(embedded, 'bg-[#0b0e14]')}>
        <LabChromeBar title="Data Center Console" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
        <div className="flex-1 flex items-center justify-center p-6 text-sm text-slate-400">
          Loading datacenter floor…
        </div>
      </div>
    )
  }

  if (error || !state) {
    return (
      <div className={simPanelRoot(embedded, 'bg-[#0b0e14]')}>
        <LabChromeBar title="Data Center Console" subtitle={scenario?.title || slug} accent={ACCENT} {...chromeProps} />
        <div className="flex-1 flex flex-col items-center justify-center gap-3 p-6 text-center">
          <AlertTriangle className="text-amber-400" size={32} aria-hidden />
          <p className="text-sm text-slate-300 max-w-md">
            {error || 'Could not load datacenter state. Check that the lab session is running, then retry.'}
          </p>
          <button
            type="button"
            onClick={() => refresh()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-orange-500/40 text-orange-300 text-sm hover:bg-orange-500/10"
          >
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      </div>
    )
  }

  if (!loggedIn) {
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
        <GlobalSearch
          services={searchServices}
          resources={searchResources}
          placeholder="Search racks, servers, rooms… (/)"
          onSelect={(hit) => {
            if (hit.navKey === 'rooms' || hit.meta?.type) {
              const room = rooms.find((r) => r.id === hit.id) || hit.meta
              if (room?.id) enterRoom(room)
              return
            }
            if (hit.meta?.hostname || hit.navKey === 'floor') {
              const srv = servers.find((s) => s.id === hit.id) || hit.meta
              if (srv?.rack || srv?.rack_id) {
                const rack = racks.find((r) => r.id === (srv.rack || srv.rack_id))
                const room = rooms.find((r) => (r.racks || []).includes(rack?.id))
                if (room) enterRoom(room)
              }
              if (srv?.id) {
                setSelectedServerId(srv.id)
                setDrawerTab('overview')
              }
            }
          }}
        />
        {onToggleTerminal && (
          <button type="button" className="lab-chrome-btn flex items-center gap-1" onClick={onToggleTerminal}>
            <Terminal size={13} /> {simTerminalOpen ? 'Hide terminal' : 'Terminal'}
          </button>
        )}
      </LabChromeBar>

      {goal.objective && (
        <div className="sim-goal-banner">
          <AlertTriangle size={14} className="shrink-0" />
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
          <Gauge size={12} /> PUE {facility.pue ?? sustainability?.pue ?? '—'} · WUE {sustainability?.wue_l_per_kwh ?? '—'} · CO₂ {sustainability?.carbon_kg_hr ?? '—'} kg/h
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
        <div className="dc-status-hint">
          {currentRoom.type === 'data_hall' && (
            <span className="dc-view-toggle">
              <button
                type="button"
                className={`dc-btn-outline dc-btn-xs ${floorView === '2d' ? 'dc-view-active' : ''}`}
                onClick={() => setFloorView('2d')}
                title="Isometric 2D floor plan"
              >
                <Move size={11} /> 2D floor
              </button>
              <button
                type="button"
                className={`dc-btn-outline dc-btn-xs ${floorView === '3d' ? 'dc-view-active' : ''}`}
                onClick={() => setFloorView('3d')}
                title="Steam-class animated 3D hall — Walk (WASD) · falls back to 2D on GPU errors"
              >
                <Box size={11} /> 3D hall
              </button>
            </span>
          )}
          <DcAmbientAudio
            enabled={floorView === '3d'}
            alert={Boolean(
              (st?.tickets || []).some((t) => /thermal|overheat|hot.?aisle/i.test(`${t?.title || ''} ${t?.status || ''}`))
              || cooling.some((c) => Number(c?.temp_c) >= 27),
            )}
          />
          {currentRoom.type === 'data_hall' && floorView === '3d'
            ? <><Box size={12} /> 3D twin · Walk (WASD) · Replay enter · Motions on</>
            : <><Move size={12} /> 2D floor · switch to 3D hall for Steam immersion</>}
        </div>
      </div>

      {currentRoom.type === 'data_hall' && floorView === '3d' && (
        <Twin3DSafe onFallback={() => setFloorView('2d')}>
          <Suspense fallback={<div className="dc-3d-loading">Loading 3D twin…</div>}>
            <LazyDatacenterTwin3D
              racks={roomRacks}
              serversByRack={serversByRack}
              network={network}
              cooling={cooling}
              pdus={pdus.length ? pdus : (powerChain.rack_pdus || [])}
              tickets={st?.tickets || []}
              selectedServerId={selectedServerId}
              expandedRack={expandedRack}
              onSelectServer={(id) => { setSelectedServerId(id); setDrawerTab('overview') }}
              onSelectRack={(id) => setExpandedRack((cur) => (cur === id ? null : id))}
              onOpenBmc={(id) => { setSelectedServerId(id); setDrawerTab('bmc') }}
              onUnplugCable={({ serverId, cableId } = {}) => {
                const srv = (serverId && servers.find((s) => s.id === serverId))
                  || (selectedServerId && servers.find((s) => s.id === selectedServerId))
                  || servers.find((s) => (s.hardware?.cables || []).some((c) => ['loose', 'damaged', 'seated'].includes(c.status)))
                if (!srv) return
                const targetId = cableId
                  || (srv.hardware?.cables || []).find((c) => c.status === 'seated')?.id
                  || (srv.hardware?.cables || [])[0]?.id
                doAction(
                  () => datacenterApi.unplugCable(sessionId, srv.id, targetId),
                  `Unplugged ${targetId || 'cable'} on ${srv.hostname || srv.id}`,
                  srv.id,
                )
              }}
              onPlugCable={({ serverId, cableId } = {}) => {
                const srv = (serverId && servers.find((s) => s.id === serverId))
                  || (selectedServerId && servers.find((s) => s.id === selectedServerId))
                  || servers.find((s) => (s.hardware?.cables || []).some((c) => ['loose', 'damaged', 'unseated'].includes(c.status)))
                if (!srv) return
                const targetId = cableId
                  || (srv.hardware?.cables || []).find((c) => ['loose', 'damaged', 'unseated'].includes(c.status))?.id
                  || (srv.hardware?.cables || [])[0]?.id
                doAction(
                  () => datacenterApi.plugCable(sessionId, srv.id, targetId),
                  `Plugged ${targetId || 'cable'} on ${srv.hostname || srv.id}`,
                  srv.id,
                )
              }}
            />
          </Suspense>
        </Twin3DSafe>
      )}

      {currentRoom.type === 'data_hall' && floorView === '2d' && (
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
                      {rack.physics?.tip_risk === 'high' && <span className="dc-tip-badge">TIP</span>}
                      {rack.physics?.mass_kg && <span className="dc-mass-badge">{rack.physics.mass_kg}kg</span>}
                    </div>
                    <div className="dc-rack-pdu">{rack.pdu} · {rack.physics?.outlet_c ?? '—'}°C out · {rack.physics?.airflow_cfm ?? '—'} CFM</div>
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
                              onClick={(e) => { e.stopPropagation(); setSelectedServerId(s.id); setDrawerTab('overview') }}>
                              <span className="dc-server-u">U{s.u_slot}</span>
                              <span className="dc-server-host">{s.hostname}</span>
                              <span className={`dc-server-power ${s.power_state === 'on' ? 'dc-power-on' : 'dc-power-off'}`}>
                                <Power size={10} /> {s.power_state}
                              </span>
                              {hasFailure && <AlertTriangle size={12} className="dc-server-warn" />}
                            </button>
                          )
                        })}
                        <RackPhysicsFruPanel
                          rack={rack}
                          busy={busy}
                          onToggleCasters={(id) => doAction(() => datacenterApi.toggleRackCasters(sessionId, id), 'Casters toggled')}
                          onBlanking={(id, u) => doAction(() => datacenterApi.installBlanking(sessionId, id, u), `Blanking U${u}`)}
                          onOutlet={(id, oid) => doAction(() => datacenterApi.pduOutletToggle(sessionId, id, oid), 'Outlet toggled')}
                          onFruOp={(id, op, extra) => doAction(
                            () => datacenterApi.rackFruOps(sessionId, id, op, extra),
                            `FRU ${op}`,
                          )}
                        />
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {currentRoom.type === 'network' && currentRoom.id === 'mdf' && (
        <div className="dc-room-body">
          <NetworkRoomPhase3
            network={network}
            servers={servers}
            busy={busy}
            onSelectServer={(id) => { setSelectedServerId(id); setDrawerTab('overview') }}
            onCli={async (switchId, command) => {
              const res = await run(() => datacenterApi.switchCli(sessionId, switchId, command), `CLI ${command}`)
              return res
            }}
            onPing={async (host) => run(() => datacenterApi.netPing(sessionId, host), `ping ${host}`)}
            onTrace={async (dest) => run(() => datacenterApi.netTraceroute(sessionId, dest), `traceroute ${dest}`)}
            onIperf={async (src, dst) => run(() => datacenterApi.netIperf(sessionId, src, dst), 'iperf')}
            onFixProtocol={(protocol) => doAction(() => datacenterApi.netFixProtocol(sessionId, protocol), `Restored ${protocol}`)}
          />
        </div>
      )}

      {currentRoom.type === 'mechanical' && currentRoom.id === 'mechanical' && (
        <div className="dc-room-body">
          <MechanicalRoomView cooling={cooling} busy={busy}
            onRestore={(cracId) => doAction(() => datacenterApi.restoreCrac(sessionId, cracId), 'CRAC restored')} />
          <div style={{ marginTop: '1rem' }}>
            <LiquidCoolingPanel
              liquid={liquidCooling}
              busy={busy}
              onOp={(op, extra) => doAction(
                () => datacenterApi.liquidCoolingOps(sessionId, op, extra),
                `Liquid ${op}`,
              )}
            />
            <div style={{ marginTop: '1rem' }}>
              <ContainmentPanel
                containment={containment}
                busy={busy}
                onOp={(op, extra) => doAction(() => datacenterApi.containmentOps(sessionId, op, extra), `Containment ${op}`)}
              />
            </div>
          </div>
        </div>
      )}

      {currentRoom.type === 'electrical' && currentRoom.id === 'electrical' && (
        <div className="dc-room-body">
          <ElectricalRoomView powerChain={powerChain} facility={facility} busy={busy}
            onTrip={(pduId) => doAction(() => datacenterApi.tripPduBreaker(sessionId, pduId), 'Breaker tripped')}
            onRestore={(pduId) => doAction(() => datacenterApi.restorePdu(sessionId, pduId), 'Breaker restored')} />
          <div style={{ marginTop: '1rem' }}>
            <DrFailoverPanel
              dr={dr}
              powerChain={powerChain}
              busy={busy}
              onOp={(op, extra) => doAction(() => datacenterApi.drOps(sessionId, op, extra), `DR ${op}`)}
            />
          </div>
        </div>
      )}

      {currentRoom.id === 'generator-yard' && (
        <div className="dc-room-body">
          <CampusRoomView
            room={currentRoom}
            campus={campus}
            access={accessControl}
            rooms={rooms}
            busy={busy}
            selectedServerId={selectedServerId}
            onEnterRoom={enterRoom}
            onOp={(op, extra) => {
              if (op === 'badge_in') {
                return doAction(() => datacenterApi.accessOps(sessionId, op, extra), `Access ${op}`)
              }
              return doAction(() => datacenterApi.campusPlantOps(sessionId, op, extra), `Campus ${op}`)
            }}
          />
          <div style={{ marginTop: '1rem' }}>
            <DrFailoverPanel
              dr={dr}
              powerChain={powerChain}
              busy={busy}
              onOp={(op, extra) => doAction(() => datacenterApi.drOps(sessionId, op, extra), `DR ${op}`)}
            />
          </div>
        </div>
      )}

      {currentRoom.id === 'security-gate' && (
        <div className="dc-room-body">
          <AccessControlPanel
            access={accessControl}
            busy={busy}
            onOp={(op, extra) => doAction(() => datacenterApi.accessOps(sessionId, op, extra), `Access ${op}`)}
          />
        </div>
      )}

      {currentRoom.type === 'ops' && (currentRoom.id === 'noc' || currentRoom.id === 'soc') && (
        <div className="dc-room-body dc-ops-room">
          <MonitoringPanel
            monitoring={monitoring}
            twinJournal={st.digital_twin}
            busy={busy}
            onRefresh={() => doAction(() => datacenterApi.refreshMonitoring(sessionId), 'Metrics refreshed')}
            onLiveTick={onLiveTick}
            onReplay={() => doAction(() => datacenterApi.replayTwinJournal(sessionId), 'Twin journal replayed')}
          />
          <OpsTicketsPanel
            tickets={st.tickets}
            busy={busy}
            onCreate={(vendor, ticketType) => doAction(
              () => datacenterApi.opsTicketCreate(sessionId, vendor, ticketType, {
                asset_id: selectedServerId || broken.server,
                component: broken.component || 'hardware',
              }),
              `${vendor} ${ticketType} opened`,
            )}
            onAdvance={(ticketId, advance) => doAction(
              () => datacenterApi.opsTicketAdvance(sessionId, ticketId, advance),
              `Ticket ${advance}`,
            )}
          />
          <TrainingPanel
            training={training}
            busy={busy}
            broken={broken}
            onStart={(id) => doAction(() => datacenterApi.trainingStart(sessionId, id), `Training ${id}`)}
            onStep={(step) => doAction(() => datacenterApi.trainingStep(sessionId, step), `Step: ${step}`)}
            onClearFault={() => doAction(() => datacenterApi.clearFailure(sessionId), 'Fault cleared')}
          />
          <div style={{ marginTop: '1rem' }}>
            <FailureInjectBar
              presets={hardwareCatalog.failure_presets}
              busy={busy}
              broken={broken}
              assetId={selectedServerId}
              onInject={(preset, assetId) => doAction(
                () => datacenterApi.injectFailure(sessionId, preset, assetId),
                `Injected ${preset}`,
              )}
              onClear={() => doAction(() => datacenterApi.clearFailure(sessionId), 'Fault cleared')}
            />
          </div>
          <div style={{ marginTop: '1rem' }}>
            <CapacityPdmPanel
              capacity={capacity}
              predictive={predictive}
              busy={busy}
              onRefresh={() => doAction(() => datacenterApi.refreshCapacity(sessionId), 'Capacity refreshed')}
            />
          </div>
          <div style={{ marginTop: '1rem' }}>
            <EnvironmentalPanel
              environmental={environmental}
              busy={busy}
              onOp={(op, extra) => doAction(() => datacenterApi.environmentalOps(sessionId, op, extra), `Env ${op}`)}
            />
          </div>
          {currentRoom.id === 'noc' && (
            <div style={{ marginTop: '1rem' }}>
              <AutomationReportPanel
                automation={automation}
                opsReport={opsReport}
                busy={busy}
                onRun={(runbookId) => doAction(
                  () => datacenterApi.automationOps(sessionId, 'run', { runbook_id: runbookId }),
                  `Runbook ${runbookId}`,
                )}
                onReport={() => doAction(() => datacenterApi.generateOpsReport(sessionId), 'Ops report')}
              />
              <div style={{ marginTop: '1rem' }}>
                <ChangeCabPanel
                  calendar={changeCalendar}
                  busy={busy}
                  onOp={(op, extra) => doAction(() => datacenterApi.changeOps(sessionId, op, extra), `Change ${op}`)}
                />
              </div>
              <div style={{ marginTop: '1rem' }}>
                <SustainabilityPanel sustainability={sustainability} />
              </div>
              <div style={{ marginTop: '1rem' }}>
                <ExportersPanel
                  exporters={exporters}
                  busy={busy}
                  onOp={(op, extra) => doAction(() => datacenterApi.exporterOps(sessionId, op, extra), `Exporter ${op}`)}
                />
              </div>
              <div style={{ marginTop: '1rem' }}>
                <DocsEvidencePanel
                  docs={docLibrary}
                  evidence={evidencePack}
                  busy={busy}
                  onEvidence={() => doAction(() => datacenterApi.generateEvidence(sessionId), 'Evidence pack')}
                />
              </div>
            </div>
          )}
          {currentRoom.id === 'soc' && (
            <div style={{ marginTop: '1rem' }}>
              <AccessControlPanel
                access={accessControl}
                busy={busy}
                onOp={(op, extra) => doAction(() => datacenterApi.accessOps(sessionId, op, extra), `Access ${op}`)}
              />
            </div>
          )}
        </div>
      )}

      {currentRoom.id === 'fire-suppression' && (
        <div className="dc-room-body">
          <FireSafetyPanel
            fire={fireSafety}
            busy={busy}
            onOp={(op, extra) => doAction(() => datacenterApi.fireSafetyOps(sessionId, op, extra), `Fire ${op}`)}
          />
        </div>
      )}

      {(currentRoom.id === 'fef' || currentRoom.id === 'mmr' || currentRoom.id === 'cable-room' || currentRoom.id === 'idf') && (
        <div className="dc-room-body">
          <OpticalPanel
            optical={optical}
            busy={busy}
            onOp={(op, extra) => doAction(() => datacenterApi.opticalOps(sessionId, op, extra), `Optical ${op}`)}
          />
          {(currentRoom.id === 'cable-room' || currentRoom.id === 'mmr') && (
            <div style={{ marginTop: '1rem' }}>
              <CablePlantPanel
                plant={cablePlant}
                busy={busy}
                onOp={(op, extra) => doAction(() => datacenterApi.cablePlantOps(sessionId, op, extra), `Tray ${op}`)}
              />
            </div>
          )}
        </div>
      )}

      {(currentRoom.id === 'burn-in' || currentRoom.id === 'staging') && (
        <div className="dc-room-body">
          <ComputeAiPanel
            hypervisors={hypervisors}
            aiPlatform={aiPlatform}
            busy={busy}
            onHv={(op, extra) => doAction(() => datacenterApi.hypervisorOps(sessionId, op, extra), `HV ${op}`)}
            onAi={(op, extra) => doAction(() => datacenterApi.aiOps(sessionId, op, extra), `AI ${op}`)}
          />
          <div style={{ marginTop: '1rem' }}>
            <PxeMaasPanel
              pxeMaas={pxeMaas}
              busy={busy}
              selectedServerId={selectedServerId}
              onOp={(op, extra) => doAction(
                () => datacenterApi.pxeMaasOps(sessionId, op, extra),
                `MAAS ${op}`,
                extra?.machine_id,
              )}
            />
          </div>
          {currentRoom.id === 'burn-in' && (
            <div style={{ marginTop: '1rem' }}>
              <BurninPanel
                burnin={burnin}
                busy={busy}
                onOp={(op, extra) => doAction(
                  () => datacenterApi.burninOps(sessionId, op, extra),
                  `Burnin ${op}`,
                  extra?.machine_id,
                )}
              />
            </div>
          )}
        </div>
      )}

      {currentRoom.type !== 'data_hall'
        && !(currentRoom.type === 'network' && currentRoom.id === 'mdf')
        && !(currentRoom.type === 'mechanical' && currentRoom.id === 'mechanical')
        && !(currentRoom.type === 'electrical' && currentRoom.id === 'electrical')
        && !(currentRoom.type === 'ops' && (currentRoom.id === 'noc' || currentRoom.id === 'soc'))
        && currentRoom.id !== 'burn-in'
        && currentRoom.id !== 'staging'
        && currentRoom.id !== 'fire-suppression'
        && currentRoom.id !== 'fef'
        && currentRoom.id !== 'mmr'
        && currentRoom.id !== 'cable-room'
        && currentRoom.id !== 'idf'
        && currentRoom.id !== 'generator-yard'
        && currentRoom.id !== 'security-gate' && (
        <div className="dc-room-body">
          <CampusRoomView
            room={currentRoom}
            campus={campus}
            access={accessControl}
            rooms={rooms}
            busy={busy}
            selectedServerId={selectedServerId}
            onEnterRoom={enterRoom}
            onOp={(op, extra) => {
              if (op === 'badge_in') {
                return doAction(() => datacenterApi.accessOps(sessionId, op, extra), `Access ${op}`)
              }
              return doAction(() => datacenterApi.campusPlantOps(sessionId, op, extra), `Campus ${op}`)
            }}
          />
        </div>
      )}

      {selectedServer && (
        <div className="dc-drawer-backdrop" onClick={() => setSelectedServerId(null)}>
          <div className="dc-drawer dc-drawer-wide" onClick={(e) => e.stopPropagation()}>
            <div className="dc-drawer-head">
              <div>
                <div className="dc-drawer-title">
                  {selectedServer.hostname} <RoleBadge role={selectedServer.role} />
                </div>
                <div className="dc-drawer-sub">{selectedServer.vendor} {selectedServer.model} · {selectedServer.rack} U{selectedServer.u_slot} · {selectedServer.power_state}</div>
              </div>
              <button type="button" onClick={() => setSelectedServerId(null)} className="dc-drawer-close"><X size={16} /></button>
            </div>

            <div className="dc-drawer-tabs">
              {[
                ['overview', 'Overview'],
                ['motherboard', 'Motherboard'],
                ['raid', 'RAID'],
                ['bios', 'BIOS/UEFI'],
                ['bmc', selectedServer.bmc?.product || 'iDRAC/iLO'],
                ['service', 'Service'],
                ['inventory', 'CMDB'],
                ['storage', 'Storage'],
                ['pxe', 'PXE/MAAS'],
              ].map(([key, label]) => (
                <button key={key} type="button"
                  className={`dc-drawer-tab ${drawerTab === key ? 'dc-drawer-tab-active' : ''}`}
                  onClick={() => setDrawerTab(key)}>{label}</button>
              ))}
            </div>

            {drawerTab === 'motherboard' && (
              <div className="dc-drawer-section">
                <MotherboardPanel
                  motherboard={selectedServer.motherboard}
                  busy={busy}
                  onToggleCover={() => doAction(() => datacenterApi.toggleChassisCover(sessionId, selectedServer.id), 'Chassis cover toggled', selectedServer.id)}
                  onReplaceDimm={(slotId) => doAction(() => datacenterApi.replaceDimmSlot(sessionId, selectedServer.id, slotId), `DIMM ${slotId} replaced`, selectedServer.id)}
                  onApplyPaste={(socketId) => doAction(() => datacenterApi.applyThermalPaste(sessionId, selectedServer.id, socketId), `Paste on ${socketId}`, selectedServer.id)}
                  onMbOp={(op, extra = {}) => doAction(
                    () => datacenterApi.motherboardOps(sessionId, selectedServer.id, op, extra),
                    `MB ${op}`,
                    selectedServer.id,
                  )}
                />
              </div>
            )}

            {drawerTab === 'raid' && (
              <div className="dc-drawer-section">
                <RaidPanel
                  raid={selectedServer.raid}
                  busy={busy}
                  onFailDisk={(diskId) => doAction(() => datacenterApi.raidFailDisk(sessionId, selectedServer.id, diskId), `${diskId} failed`, selectedServer.id)}
                  onRebuild={(vdId) => doAction(() => datacenterApi.raidRebuild(sessionId, selectedServer.id, vdId), `${vdId} rebuild started`, selectedServer.id)}
                  onSetCache={(mode) => doAction(() => datacenterApi.raidSetCache(sessionId, selectedServer.id, mode), `Cache ${mode}`, selectedServer.id)}
                  onCreateVd={(payload) => doAction(() => datacenterApi.raidCreateVd(sessionId, selectedServer.id, payload), 'VD created', selectedServer.id)}
                  onDeleteVd={(vdId) => doAction(() => datacenterApi.raidDeleteVd(sessionId, selectedServer.id, vdId), `${vdId} deleted`, selectedServer.id)}
                  onPatrol={() => doAction(() => datacenterApi.raidPatrolRead(sessionId, selectedServer.id), 'Patrol read', selectedServer.id)}
                  onConsistency={() => doAction(() => datacenterApi.raidConsistencyCheck(sessionId, selectedServer.id), 'Consistency check', selectedServer.id)}
                  onImportForeign={() => doAction(() => datacenterApi.raidImportForeign(sessionId, selectedServer.id), 'Foreign import', selectedServer.id)}
                  onAssignHotspare={(diskId) => doAction(() => datacenterApi.raidAssignHotspare(sessionId, selectedServer.id, diskId), `${diskId} hot spare`, selectedServer.id)}
                  onExpandVd={(vdId, addGb) => doAction(() => datacenterApi.raidExpandVd(sessionId, selectedServer.id, vdId, addGb), `${vdId} expanded`, selectedServer.id)}
                  onInitializeVd={(vdId, mode) => doAction(() => datacenterApi.raidInitializeVd(sessionId, selectedServer.id, vdId, mode), `${vdId} init`, selectedServer.id)}
                />
              </div>
            )}

            {drawerTab === 'bios' && (
              <div className="dc-drawer-section">
                <BiosPanel
                  bios={selectedServer.bios}
                  busy={busy}
                  onEnter={() => doAction(() => datacenterApi.biosEnterSetup(sessionId, selectedServer.id), 'BIOS setup', selectedServer.id)}
                  onExit={() => doAction(() => datacenterApi.biosExitSetup(sessionId, selectedServer.id), 'BIOS exit', selectedServer.id)}
                  onSet={(key, value) => doAction(() => datacenterApi.biosSet(sessionId, selectedServer.id, key, value), `BIOS ${key}`, selectedServer.id)}
                  onCmosReset={() => doAction(() => datacenterApi.biosCmosReset(sessionId, selectedServer.id), 'CMOS reset', selectedServer.id)}
                  onPost={() => doAction(() => datacenterApi.biosRunPost(sessionId, selectedServer.id), 'POST', selectedServer.id)}
                  onFlash={(v) => doAction(() => datacenterApi.biosFlash(sessionId, selectedServer.id, v), `BIOS ${v}`, selectedServer.id)}
                  onSetPassword={(p) => doAction(() => datacenterApi.biosSetPassword(sessionId, selectedServer.id, p), 'BIOS password', selectedServer.id)}
                />
              </div>
            )}

            {drawerTab === 'bmc' && (
              <div className="dc-drawer-section">
                <BmcPanel
                  bmc={selectedServer.bmc}
                  vendor={selectedServer.vendor}
                  busy={busy}
                  onLogin={(username, password) => run(
                    () => datacenterApi.bmcLogin(sessionId, selectedServer.id, username, password),
                    `Signed into ${selectedServer.bmc?.product || 'BMC'}`,
                  )}
                  onLogout={() => doAction(
                    () => datacenterApi.bmcLogout(sessionId, selectedServer.id),
                    'BMC logged out',
                    selectedServer.id,
                  )}
                  onPower={(mode) => doAction(() => datacenterApi.bmcPower(sessionId, selectedServer.id, mode), `BMC ${mode}`, selectedServer.id)}
                  onMountIso={(image) => doAction(() => datacenterApi.bmcMountIso(sessionId, selectedServer.id, image), 'ISO mounted', selectedServer.id)}
                  onDiag={(suite) => doAction(() => datacenterApi.bmcRunDiagnostics(sessionId, selectedServer.id, suite), `${suite} diagnostics`, selectedServer.id)}
                  onUpdateNet={(payload) => doAction(() => datacenterApi.bmcUpdateNetwork(sessionId, selectedServer.id, payload), 'BMC network', selectedServer.id)}
                  onNmi={() => doAction(() => datacenterApi.bmcNmi(sessionId, selectedServer.id), 'NMI', selectedServer.id)}
                  onFlash={(t, v) => doAction(() => datacenterApi.bmcFlashTarget(sessionId, selectedServer.id, t, v), `Flash ${t}`, selectedServer.id)}
                  onKvm={() => doAction(() => datacenterApi.bmcOpenKvm(sessionId, selectedServer.id), 'KVM open', selectedServer.id)}
                  onSetGeneration={(g) => doAction(() => datacenterApi.bmcSetGeneration(sessionId, selectedServer.id, g), `BMC ${g}`, selectedServer.id)}
                />
              </div>
            )}

            {drawerTab === 'service' && (
              <div className="dc-drawer-section">
                <ServiceModePanel
                  serviceMode={selectedServer.service_mode}
                  busy={busy}
                  onOp={(op, extra) => doAction(
                    () => datacenterApi.serviceMode(sessionId, selectedServer.id, op, extra),
                    `Service ${op}`,
                    selectedServer.id,
                  )}
                />
              </div>
            )}

            {drawerTab === 'inventory' && (
              <div className="dc-drawer-section">
                <InventoryPanel inventory={selectedServer.inventory} />
                <FailureInjectBar
                  presets={hardwareCatalog.failure_presets}
                  busy={busy}
                  broken={broken}
                  assetId={selectedServer.id}
                  onInject={(preset, assetId) => doAction(
                    () => datacenterApi.injectFailure(sessionId, preset, assetId),
                    `Injected ${preset}`,
                    assetId,
                  )}
                  onClear={() => doAction(() => datacenterApi.clearFailure(sessionId), 'Fault cleared')}
                />
                {(hardwareCatalog.server_oems || []).length > 0 && (
                  <div className="dc-muted mt-2">
                    Catalog OEMs: {(hardwareCatalog.server_oems || []).join(', ')}
                  </div>
                )}
              </div>
            )}

            {drawerTab === 'storage' && (
              <div className="dc-drawer-section">
                <StorageStackPanel
                  storage={selectedServer.storage_stack}
                  busy={busy}
                  onOp={(op, extra) => doAction(
                    () => datacenterApi.storageOps(sessionId, selectedServer.id, op, extra),
                    `Storage ${op}`,
                    selectedServer.id,
                  )}
                />
              </div>
            )}

            {drawerTab === 'pxe' && (
              <div className="dc-drawer-section">
                <PxeMaasPanel
                  pxeMaas={pxeMaas}
                  busy={busy}
                  selectedServerId={selectedServer.id}
                  onOp={(op, extra) => doAction(
                    () => datacenterApi.pxeMaasOps(sessionId, op, { machine_id: selectedServer.id, ...extra }),
                    `MAAS ${op}`,
                    selectedServer.id,
                  )}
                />
              </div>
            )}

            {drawerTab === 'overview' && (
              <>
            <div className="dc-drawer-section">
              <div className="dc-drawer-label">Component health</div>
              <div className="dc-component-grid">
                {Object.entries(selectedServer.components).map(([name, status]) => (
                  <ComponentPill key={name} name={name} status={status} />
                ))}
              </div>
            </div>

            {selectedServer.hardware && (
              <div className="dc-drawer-section">
                <div className="dc-drawer-label">Hardware inventory</div>
                <div className="dc-hw-meta">
                  <div><span className="dc-hw-k">Vendor</span> — {selectedServer.vendor || '—'} · {selectedServer.model || '—'} · ST {selectedServer.service_tag || '—'}</div>
                  <div><span className="dc-hw-k">Motherboard</span> — {selectedServer.hardware.motherboard?.model} · BIOS {selectedServer.hardware.motherboard?.bios} · TPM {selectedServer.hardware.motherboard?.tpm}</div>
                  <div><span className="dc-hw-k">CPUs</span> — {(selectedServer.hardware.cpus || []).map((c) => `S${c.socket} ${c.cores}c/${c.threads}t`).join(' · ')}</div>
                  <div><span className="dc-hw-k">PCIe</span> — {(selectedServer.hardware.pcie || []).map((p) => `${p.slot}: ${p.model}`).join(' · ')}</div>
                  <div><span className="dc-hw-k">Storage</span> — {(selectedServer.hardware.storage || []).map((d) => `Bay${d.bay} ${d.size_gb}G ${d.bus}`).join(' · ')}</div>
                  <div><span className="dc-hw-k">Power/Cooling</span> — {(selectedServer.hardware.psus || []).map((p) => p.id).join('/')} · {(selectedServer.hardware.fans || []).length} fans</div>
                  <div><span className="dc-hw-k">Firmware</span> — {selectedServer.firmware_version || '—'}</div>
                </div>
              </div>
            )}

            {selectedServer.hardware?.cables?.length > 0 && (
              <div className="dc-drawer-section">
                <div className="dc-drawer-label">Cables &amp; ports</div>
                <CableOpsPanel
                  cables={selectedServer.hardware.cables}
                  busy={busy}
                  catalog={hardwareCatalog.cable_catalog}
                  onOp={(op, cableId, extra) => doAction(
                    () => datacenterApi.cableOps(sessionId, selectedServer.id, op, { cable_id: cableId, ...extra }),
                    `Cable ${op}`,
                    selectedServer.id,
                  )}
                />
                <div className="dc-action-row mt-2">
                  {selectedServer.hardware.cables.map((c) => {
                    const seated = c.status === 'seated'
                    return seated ? (
                      <button key={`u-${c.id}`} type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                        onClick={() => doAction(() => datacenterApi.unplugCable(sessionId, selectedServer.id, c.id), `Unplugged ${c.id}`, selectedServer.id)}>
                        Unplug {c.id}
                      </button>
                    ) : (
                      <button key={`p-${c.id}`} type="button" disabled={busy} className="dc-btn-danger dc-btn-xs"
                        onClick={() => doAction(() => datacenterApi.plugCable(sessionId, selectedServer.id, c.id), `Plugged ${c.id}`, selectedServer.id)}>
                        Plug {c.id}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

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
              <div className="dc-drawer-label">Vendor support ticket</div>
              <p className="dc-ticket-hint">
                Raise a part-replacement / troubleshooting ticket to{' '}
                <strong>{selectedServer.vendor || 'Dell'}</strong> for this chassis (service tag{' '}
                {selectedServer.service_tag || '—'}).
              </p>
              <div className="dc-action-row" style={{ flexWrap: 'wrap' }}>
                <button type="button" disabled={busy} className="dc-btn-outline"
                  onClick={() => {
                    const failed = Object.entries(selectedServer.components).find(([, s]) => s !== 'healthy')
                    const component = failed?.[0] || broken.component || 'hardware'
                    doAction(
                      () => datacenterApi.openVendorTicket(sessionId, selectedServer.id, component, selectedServer.vendor),
                      `${selectedServer.vendor || 'Vendor'} ticket opened`,
                      selectedServer.id,
                    )
                  }}>
                  <Ticket size={13} /> Open {selectedServer.vendor || 'OEM'} ticket
                </button>
                {['Dell', 'HPE', 'Lenovo', 'Supermicro', 'Cisco', 'NVIDIA']
                  .filter((v) => v !== selectedServer.vendor)
                  .slice(0, 3)
                  .map((v) => (
                    <button key={v} type="button" disabled={busy} className="dc-btn-outline dc-btn-xs"
                      onClick={() => doAction(
                        () => datacenterApi.openVendorTicket(sessionId, selectedServer.id, broken.component || 'hardware', v),
                        `${v} ticket opened`,
                        selectedServer.id,
                      )}>
                      Ticket → {v}
                    </button>
                  ))}
              </div>
              {(st.tickets || []).filter((t) => t.asset_id === selectedServer.id).slice(0, 4).map((t) => (
                <div key={t.id} className="dc-ticket-card">
                  <div className="dc-ticket-id">{t.id} · {t.vendor}</div>
                  <div className="dc-ticket-sum">{t.summary} · {t.status}</div>
                  {t.status === 'open' && (
                    <button type="button" disabled={busy} className="dc-btn-outline dc-btn-xs mt-1"
                      onClick={() => doAction(() => datacenterApi.resolveVendorTicket(sessionId, t.id), `Ticket ${t.id} advanced`)}>
                      Authorize FRU / ship parts
                    </button>
                  )}
                </div>
              ))}
            </div>

            <div className="dc-drawer-section">
              <div className="dc-drawer-label">Field actions</div>
              <div className="dc-action-row">
                <button type="button" disabled={busy} className="dc-btn-outline"
                  onClick={() => doAction(() => datacenterApi.powerCycle(sessionId, selectedServer.id), 'Power cycle issued', selectedServer.id)}>
                  <Power size={13} /> Power Cycle
                </button>
                <button type="button" disabled={busy} className="dc-btn-outline"
                  onClick={() => doAction(() => datacenterApi.openSerialConsole(sessionId, selectedServer.id), 'Serial console open', selectedServer.id)}>
                  <Monitor size={13} /> Attach monitor / serial
                </button>
                <button type="button" disabled={busy} className="dc-btn-outline"
                  onClick={() => doAction(() => datacenterApi.reseatCable(sessionId, selectedServer.id), 'Cable reseated', selectedServer.id)}>
                  <RotateCcw size={13} /> Reseat all loose
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

            {st.console?.open && st.console?.asset_id === selectedServer.id && (
              <div className="dc-drawer-section">
                <div className="dc-drawer-label"><Monitor size={12} className="inline mr-1" />KVM / serial console</div>
                <div className="dc-serial-console">
                  {(st.console.lines || []).map((line, i) => (
                    <div key={i} className="dc-serial-line">{line}</div>
                  ))}
                  <span className="dc-serial-cursor">█</span>
                </div>
              </div>
            )}

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
            </>
            )}
          </div>
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
