import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Bot, Zap, Sparkles, Wrench, Plug, Shuffle, GitBranch, Flag,
  Play, RefreshCw, ArrowLeft, StopCircle, Lightbulb, XCircle, AlertTriangle,
  CheckCircle2, Target, Trash2, Plus, Link2, Settings2, Activity, X, ChevronRight,
} from 'lucide-react'
import { aimlApi } from '../../api/aiml'
import LabChromeBar from '../lab/LabChromeBar'
import { renderAimlV2Page } from '../sim/V3PlatformPanels'
import '../../styles/sim-products.css'

/* ── scoped, self-contained n8n-style automation chrome (no shared CSS) ── */
const SCOPED_CSS = `
.agent-sim {
  --ag-bg: #0c0a14;
  --ag-panel: #14111f;
  --ag-panel-2: #1a1626;
  --ag-border: #2a2440;
  --ag-text: #e6e1f5;
  --ag-muted: #9a90c0;
  --ag-purple: #a78bfa;
  --ag-purple-2: #8b5cf6;
  --ag-cyan: #38e0d0;
  --ag-green: #4ade80;
  --ag-amber: #f5c451;
  --ag-red: #ff6b6b;
  --ag-pink: #f472b6;
  color: var(--ag-text);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  background: var(--ag-bg);
  min-height: 100%;
}
.agent-sim .ag-topbar {
  display: flex; align-items: center; justify-content: space-between; gap: 0.75rem;
  padding: 0.6rem 1rem; background: #0a0810; border-bottom: 1px solid var(--ag-border);
  position: sticky; top: 0; z-index: 20;
}
.agent-sim .ag-btn {
  display: inline-flex; align-items: center; gap: 0.4rem; border-radius: 6px;
  padding: 0.45rem 0.8rem; font-size: 0.8rem; font-weight: 600; cursor: pointer;
  border: 1px solid var(--ag-border); background: #1c1830; color: var(--ag-text);
  transition: background 0.12s, filter 0.12s;
}
.agent-sim .ag-btn:hover { background: #241f3a; }
.agent-sim .ag-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.agent-sim .ag-btn-primary {
  border: none; background: linear-gradient(135deg, var(--ag-purple-2), var(--ag-pink)); color: #fff;
}
.agent-sim .ag-btn-primary:hover { filter: brightness(1.08); }
.agent-sim .ag-input, .agent-sim .ag-select {
  background: #0d0a16; border: 1px solid var(--ag-border); border-radius: 6px;
  padding: 0.5rem 0.65rem; color: var(--ag-text); font-size: 0.82rem; outline: none; width: 100%;
}
.agent-sim .ag-input:focus, .agent-sim .ag-select:focus {
  border-color: var(--ag-purple); box-shadow: 0 0 0 2px rgba(167,139,250,.2);
}
.agent-sim textarea.ag-input { font-family: 'JetBrains Mono', ui-monospace, monospace; resize: vertical; }
.agent-sim .ag-card {
  background: var(--ag-panel); border: 1px solid var(--ag-border); border-radius: 10px;
}
.agent-sim .ag-label {
  font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
  color: var(--ag-muted); display: block; margin-bottom: 0.25rem;
}
.agent-sim .ag-banner {
  display: flex; align-items: flex-start; gap: 0.5rem; font-size: 0.82rem;
  padding: 0.6rem 0.85rem; border-radius: 8px; margin-bottom: 0.85rem;
}
.agent-sim .ag-banner-goal { background: rgba(167,139,250,.1); border: 1px solid rgba(167,139,250,.3); color: #d7c9ff; }
.agent-sim .ag-banner-err { background: rgba(255,107,107,.1); border: 1px solid rgba(255,107,107,.3); color: #ffb4b4; }
.agent-sim .ag-banner-ok { background: rgba(74,222,128,.1); border: 1px solid rgba(74,222,128,.3); color: #b7f5cd; }

/* canvas */
.agent-sim .ag-canvas {
  position: relative; overflow: auto; border-radius: 12px;
  background:
    radial-gradient(circle at 1px 1px, rgba(167,139,250,.12) 1px, transparent 0);
  background-size: 22px 22px;
  background-color: #0a0810;
  border: 1px solid var(--ag-border);
  min-height: 460px;
}
.agent-sim .ag-canvas-inner { position: relative; width: 1280px; height: 560px; }
.agent-sim .ag-edges { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }

/* node card */
.agent-sim .ag-node {
  position: absolute; width: 184px; border-radius: 10px; cursor: grab;
  background: var(--ag-panel-2); border: 1.5px solid var(--ag-border);
  box-shadow: 0 6px 18px rgba(0,0,0,.4); user-select: none; z-index: 2;
  transition: border-color 0.12s, box-shadow 0.12s;
}
.agent-sim .ag-node:hover { border-color: var(--ag-purple); }
.agent-sim .ag-node.ag-node-sel { border-color: var(--ag-purple); box-shadow: 0 0 0 2px rgba(167,139,250,.4), 0 8px 22px rgba(0,0,0,.5); z-index: 5; }
.agent-sim .ag-node.ag-node-connect-src { border-color: var(--ag-cyan); box-shadow: 0 0 0 2px rgba(56,224,208,.45); }
.agent-sim .ag-node.ag-node-run-ok { box-shadow: 0 0 0 2px rgba(74,222,128,.4), 0 6px 18px rgba(0,0,0,.4); }
.agent-sim .ag-node.ag-node-run-err { box-shadow: 0 0 0 2px rgba(255,107,107,.45), 0 6px 18px rgba(0,0,0,.4); }
.agent-sim .ag-node-head {
  display: flex; align-items: center; gap: 0.45rem; padding: 0.5rem 0.6rem;
  border-bottom: 1px solid var(--ag-border); border-radius: 9px 9px 0 0;
}
.agent-sim .ag-node-title { font-size: 0.8rem; font-weight: 700; line-height: 1.1; flex: 1; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.agent-sim .ag-node-type { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ag-muted); }
.agent-sim .ag-node-body { padding: 0.4rem 0.6rem 0.55rem; font-size: 0.7rem; color: var(--ag-muted);
  font-family: 'JetBrains Mono', ui-monospace, monospace; word-break: break-word; }
.agent-sim .ag-node-icon {
  width: 26px; height: 26px; border-radius: 7px; display: grid; place-items: center; flex: none;
}
.agent-sim .ag-port {
  position: absolute; width: 12px; height: 12px; border-radius: 50%; background: var(--ag-panel);
  border: 2px solid var(--ag-purple); top: 50%; transform: translateY(-50%); z-index: 3;
}
.agent-sim .ag-port-in { left: -7px; }
.agent-sim .ag-port-out { right: -7px; cursor: crosshair; }
.agent-sim .ag-port-out:hover { background: var(--ag-cyan); border-color: var(--ag-cyan); }

/* palette chips */
.agent-sim .ag-pchip {
  display: flex; align-items: center; gap: 0.5rem; width: 100%; text-align: left;
  padding: 0.5rem 0.6rem; border-radius: 8px; cursor: pointer; margin-bottom: 0.4rem;
  border: 1px solid var(--ag-border); background: var(--ag-panel-2); color: var(--ag-text);
  transition: border-color 0.12s, background 0.12s;
}
.agent-sim .ag-pchip:hover { border-color: var(--ag-purple); background: #221d34; }

/* trace */
.agent-sim .ag-trace-row {
  display: flex; gap: 0.55rem; padding: 0.5rem 0.65rem; border-radius: 8px;
  background: #0d0a16; border: 1px solid var(--ag-border); margin-bottom: 0.4rem;
}
.agent-sim .ag-step-num {
  width: 22px; height: 22px; border-radius: 50%; flex: none; display: grid; place-items: center;
  font-size: 0.7rem; font-weight: 700; background: rgba(167,139,250,.18); color: var(--ag-purple);
}
.agent-sim .ag-code {
  font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 0.72rem;
  background: #07050d; border: 1px solid var(--ag-border); border-radius: 8px;
  padding: 0.6rem 0.75rem; color: #c9bdf0; white-space: pre-wrap; word-break: break-word; line-height: 1.5;
}
.agent-sim .ag-badge {
  display: inline-flex; align-items: center; gap: 0.25rem; font-size: 0.64rem; font-weight: 700;
  padding: 0.12rem 0.45rem; border-radius: 999px;
}
.agent-sim .ag-b-ok { background: rgba(74,222,128,.16); color: var(--ag-green); }
.agent-sim .ag-b-err { background: rgba(255,107,107,.16); color: var(--ag-red); }
.agent-sim .ag-b-branch { background: rgba(56,224,208,.16); color: var(--ag-cyan); }
.agent-sim .ag-scroll { max-height: 60vh; overflow-y: auto; }
.agent-sim .ag-scroll::-webkit-scrollbar, .agent-sim .ag-canvas::-webkit-scrollbar { width: 9px; height: 9px; }
.agent-sim .ag-scroll::-webkit-scrollbar-thumb, .agent-sim .ag-canvas::-webkit-scrollbar-thumb {
  background: #2f2848; border-radius: 6px;
}
`

/* per-type visual treatment (icon + accent color) */
const TYPE_META = {
  trigger:  { Icon: Zap,       color: '#f5c451', label: 'Trigger' },
  llm:      { Icon: Sparkles,  color: '#a78bfa', label: 'LLM' },
  tool:     { Icon: Wrench,    color: '#38e0d0', label: 'Tool' },
  mcp_tool: { Icon: Plug,      color: '#f472b6', label: 'MCP Tool' },
  transform:{ Icon: Shuffle,   color: '#60a5fa', label: 'Transform' },
  condition:{ Icon: GitBranch, color: '#fb923c', label: 'Condition' },
  output:   { Icon: Flag,      color: '#4ade80', label: 'Output' },
}

/* lucide map for the palette icon names the engine sends */
const PALETTE_ICON = {
  bolt: Zap, sparkles: Sparkles, wrench: Wrench, plug: Plug,
  shuffle: Shuffle, 'git-branch': GitBranch, flag: Flag,
}

function metaFor(type) { return TYPE_META[type] || { Icon: Bot, color: '#9a90c0', label: type } }

/* one-line summary of a node's config for the card body */
function configSummary(node) {
  const c = node?.config || {}
  switch (node?.type) {
    case 'trigger': return `kind: ${c.kind || 'manual'}`
    case 'llm': return `mode: ${c.mode || 'classify'}`
    case 'tool': return c.kind === 'http_get' ? `http_get` : c.kind === 'db_query' ? `db: ${c.query_id || c.query || '?'}` : c.kind === 'send_notification' ? `notify: ${c.channel || 'default'}` : (c.kind || 'tool')
    case 'mcp_tool': return `${c.server || '?'}.${c.tool || '?'}`
    case 'transform': return `op: ${c.op || 'set'}`
    case 'condition': return `${c.field || '?'} ${c.op || '=='} ${c.value ?? ''}`
    case 'output': return 'captures result'
    default: return ''
  }
}

/* deterministic geometric center for an edge endpoint */
const NODE_W = 184
function portPos(node, side) {
  // node bodies are ~ 78px tall; we anchor at vertical mid (y + 39)
  const cy = (node.y || 0) + 39
  return { x: side === 'out' ? (node.x || 0) + NODE_W : (node.x || 0), y: cy }
}

/* ── connection lines (SVG bezier) ── */
function Edges({ nodes, edges, traceVisited }) {
  const byId = useMemo(() => Object.fromEntries(nodes.map(n => [n.id, n])), [nodes])
  return (
    <svg className="ag-edges">
      <defs>
        <marker id="ag-arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L8,3 L0,6 Z" fill="#6d62a0" />
        </marker>
        <marker id="ag-arrow-true" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L8,3 L0,6 Z" fill="#4ade80" />
        </marker>
        <marker id="ag-arrow-false" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L8,3 L0,6 Z" fill="#fb923c" />
        </marker>
      </defs>
      {edges.map((e, i) => {
        const a = byId[e.from], b = byId[e.to]
        if (!a || !b) return null
        const p1 = portPos(a, 'out'), p2 = portPos(b, 'in')
        const dx = Math.max(40, Math.abs(p2.x - p1.x) * 0.5)
        const d = `M ${p1.x} ${p1.y} C ${p1.x + dx} ${p1.y}, ${p2.x - dx} ${p2.y}, ${p2.x} ${p2.y}`
        const branch = e.branch
        const stroke = branch === 'true' ? '#4ade80' : branch === 'false' ? '#fb923c' : '#6d62a0'
        const marker = branch === 'true' ? 'ag-arrow-true' : branch === 'false' ? 'ag-arrow-false' : 'ag-arrow'
        const lit = traceVisited?.has(e.from) && traceVisited?.has(e.to)
        const midX = (p1.x + p2.x) / 2, midY = (p1.y + p2.y) / 2
        return (
          <g key={`${e.from}-${e.to}-${branch || 'x'}-${i}`}>
            <path d={d} fill="none" stroke={stroke} strokeWidth={lit ? 3 : 1.8}
                  markerEnd={`url(#${marker})`} opacity={lit ? 1 : 0.8} />
            {branch && (
              <>
                <rect x={midX - 16} y={midY - 9} width="32" height="16" rx="8"
                      fill="#0a0810" stroke={stroke} strokeWidth="1" />
                <text x={midX} y={midY + 3} textAnchor="middle" fontSize="9" fill={stroke}
                      fontWeight="700" fontFamily="monospace">{branch === 'true' ? 'T' : 'F'}</text>
              </>
            )}
          </g>
        )
      })}
    </svg>
  )
}

/* ── a single draggable node card ── */
function NodeCard({ node, selected, connectSrc, runStatus, onSelect, onDragStart, onStartConnect, onDelete }) {
  const { Icon, color, label } = metaFor(node.type)
  const runClass = runStatus === 'ok' ? 'ag-node-run-ok' : runStatus === 'error' ? 'ag-node-run-err' : ''
  return (
    <div
      className={`ag-node ${selected ? 'ag-node-sel' : ''} ${connectSrc ? 'ag-node-connect-src' : ''} ${runClass}`}
      style={{ left: node.x || 0, top: node.y || 0 }}
      onMouseDown={(e) => onDragStart(e, node)}
      onClick={(e) => { e.stopPropagation(); onSelect(node.id) }}
    >
      {/* input port (hidden on triggers) */}
      {node.type !== 'trigger' && <span className="ag-port ag-port-in" />}
      {/* output port (hidden on outputs) */}
      {node.type !== 'output' && (
        <span
          className="ag-port ag-port-out"
          title="Drag a connection from here"
          onMouseDown={(e) => { e.stopPropagation(); onStartConnect(e, node) }}
          onClick={(e) => e.stopPropagation()}
        />
      )}
      <div className="ag-node-head">
        <span className="ag-node-icon" style={{ background: `${color}22`, color }}><Icon size={15} /></span>
        <div className="min-w-0 flex-1">
          <div className="ag-node-title">{node.label || node.id}</div>
          <div className="ag-node-type">{label}</div>
        </div>
        {node.type !== 'trigger' && (
          <button
            className="text-[var(--ag-muted)] hover:text-[var(--ag-red)]"
            title="Delete node"
            onClick={(e) => { e.stopPropagation(); onDelete(node.id) }}
          ><Trash2 size={13} /></button>
        )}
      </div>
      <div className="ag-node-body">{configSummary(node)}</div>
    </div>
  )
}

/**
 * AI Agent / Workflow simulator. Rendered INLINE by LabRunner for agent labs
 * (simulation_type 'ai-agent') — no new route. The learner builds/fixes an
 * n8n-style node graph (palette → canvas), configures the selected node, then
 * runs the workflow to see a deterministic execution trace + final output, and
 * runs Check Solution in the lab (graded via validate_aiml_lab on the engine).
 */
export default function AgentWorkflowSimulator({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
}) {
  const slug = scenario?.slug || ''
  const [state, setState] = useState(null)
  const [error, setError] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const [running, setRunning] = useState(false)
  const [tab, setTab] = useState('trace') // trace | output
  const [busy, setBusy] = useState(false)
  const [platformView, setPlatformView] = useState('workflow') // workflow | experiments | registry | rag
  const [ragQuery, setRagQuery] = useState('What is the refund policy for digital products?')

  // drag + connect interaction state
  const dragRef = useRef(null)        // {id, offsetX, offsetY, moved}
  const connectRef = useRef(null)     // {id} while dragging a new edge from an out-port
  const [connectSrc, setConnectSrc] = useState(null)
  const canvasRef = useRef(null)
  const pollRef = useRef(null)

  const load = useCallback(async () => {
    try {
      const data = await aimlApi.getState(sessionId, slug)
      if (data) { setState(data); setError('') }
      else setError('Could not load the agent workflow console')
    } catch {
      setError('Could not load the agent workflow console')
    }
  }, [sessionId, slug])

  useEffect(() => {
    load()
    pollRef.current = setInterval(load, 25000)
    return () => clearInterval(pollRef.current)
  }, [load])

  const graph = state?.graph || { nodes: [], edges: [] }
  const nodes = graph.nodes || []
  const edges = graph.edges || []
  const palette = state?.palette || []
  const catalog = state?.catalog || {}
  const goal = state?.goal || {}
  const summary = state?.summary || {}
  const lastRun = state?.last_run || null
  const selected = nodes.find(n => n.id === selectedId) || null
  const validationPassed = !!summary.validation_passed

  // map node_id -> run status for the canvas glow
  const runStatusById = useMemo(() => {
    const m = {}
    for (const t of (lastRun?.trace || [])) m[t.node_id] = t.status
    return m
  }, [lastRun])
  const traceVisited = useMemo(() => new Set((lastRun?.visited) || []), [lastRun])

  /* ── action helpers (optimistic refresh from the action response state) ── */
  const applyResult = useCallback((res) => {
    if (res?.state) setState(res.state)
    if (res?.ok === false) setError(res.error || res.message || 'Action rejected')
    else setError('')
    return res
  }, [])

  const addNode = useCallback(async (type, defaultConfig) => {
    setBusy(true)
    // drop new nodes in an open spot near the canvas center
    const x = 360 + (nodes.length % 4) * 60
    const y = 60 + (nodes.length % 5) * 70
    const res = await aimlApi.addNode(sessionId, type, defaultConfig || {}, { x, y })
    applyResult(res)
    if (res?.node?.id) setSelectedId(res.node.id)
    setBusy(false)
  }, [sessionId, nodes.length, applyResult])

  const removeNode = useCallback(async (id) => {
    setBusy(true)
    const res = await aimlApi.removeNode(sessionId, id)
    applyResult(res)
    if (selectedId === id) setSelectedId(null)
    setBusy(false)
  }, [sessionId, selectedId, applyResult])

  const connect = useCallback(async (from, to, branch) => {
    if (from === to) { setError('Cannot connect a node to itself'); return }
    setBusy(true)
    const res = await aimlApi.connect(sessionId, from, to, branch)
    applyResult(res)
    setBusy(false)
  }, [sessionId, applyResult])

  const disconnect = useCallback(async (from, to, branch) => {
    setBusy(true)
    const res = await aimlApi.disconnect(sessionId, from, to, branch)
    applyResult(res)
    setBusy(false)
  }, [sessionId, applyResult])

  const configureNode = useCallback(async (id, patch) => {
    setBusy(true)
    const res = await aimlApi.configureNode(sessionId, id, patch, true)
    applyResult(res)
    setBusy(false)
  }, [sessionId, applyResult])

  const runWorkflow = useCallback(async () => {
    setRunning(true)
    setError('')
    const res = await aimlApi.runWorkflow(sessionId)
    applyResult(res)
    setTab('trace')
    setRunning(false)
  }, [sessionId, applyResult])

  const resetGraph = useCallback(async () => {
    setBusy(true)
    const res = await aimlApi.reset(sessionId)
    applyResult(res)
    setSelectedId(null)
    setBusy(false)
  }, [sessionId, applyResult])

  /* ── drag a node around the canvas (local position; persisted optimistically) ── */
  const onDragStart = useCallback((e, node) => {
    if (e.button !== 0) return
    const rect = canvasRef.current?.getBoundingClientRect()
    const scrollL = canvasRef.current?.scrollLeft || 0
    const scrollT = canvasRef.current?.scrollTop || 0
    dragRef.current = {
      id: node.id,
      offsetX: e.clientX - rect.left + scrollL - (node.x || 0),
      offsetY: e.clientY - rect.top + scrollT - (node.y || 0),
      moved: false,
    }
  }, [])

  const onStartConnect = useCallback((e, node) => {
    connectRef.current = { id: node.id }
    setConnectSrc(node.id)
  }, [])

  useEffect(() => {
    const onMove = (e) => {
      if (!dragRef.current) return
      const rect = canvasRef.current?.getBoundingClientRect()
      if (!rect) return
      const scrollL = canvasRef.current?.scrollLeft || 0
      const scrollT = canvasRef.current?.scrollTop || 0
      const nx = Math.max(0, Math.round(e.clientX - rect.left + scrollL - dragRef.current.offsetX))
      const ny = Math.max(0, Math.round(e.clientY - rect.top + scrollT - dragRef.current.offsetY))
      dragRef.current.moved = true
      setState(prev => {
        if (!prev) return prev
        const g = prev.graph || {}
        return {
          ...prev,
          graph: { ...g, nodes: (g.nodes || []).map(n => n.id === dragRef.current.id ? { ...n, x: nx, y: ny } : n) },
        }
      })
    }
    const onUp = (e) => {
      // finish a connect-drag: if released over a node, wire from->to
      if (connectRef.current) {
        const target = e.target?.closest?.('.ag-node')
        const fromId = connectRef.current.id
        connectRef.current = null
        setConnectSrc(null)
        if (target) {
          const toId = target.getAttribute('data-node-id')
          if (toId && toId !== fromId) {
            const fromNode = nodes.find(n => n.id === fromId)
            // a condition's outgoing edge needs a branch — default to 'true',
            // the learner can flip it from the config panel edge list.
            const branch = fromNode?.type === 'condition' ? 'true' : undefined
            connect(fromId, toId, branch)
          }
        }
      }
      dragRef.current = null
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  }, [nodes, connect])

  const finalOutput = lastRun?.final_output || {}
  const notifications = lastRun?.notifications || []

  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: embedded ? undefined : onExit,
    hintsLabel, checkDisabled, extendDisabled,
  }

  return (
    <div className={`agent-sim sim-product ${embedded ? 'h-full min-h-0 flex flex-col overflow-hidden' : 'min-h-screen flex flex-col'}`}>
      <style>{SCOPED_CSS}</style>

      <LabChromeBar title="n8n · Agent Workflow" subtitle={scenario?.title || slug} accent="#a78bfa" icon={Bot} {...chromeProps}>
        {[
          ['workflow', 'Workflow'],
          ['experiments', 'Experiments'],
          ['registry', 'Registry'],
          ['rag', 'RAG'],
          ['playground', 'Playground'],
        ].map(([k, label]) => (
          <button
            key={k}
            type="button"
            className={`lab-chrome-btn ${platformView === k ? 'lab-chrome-btn-active' : ''}`}
            onClick={() => setPlatformView(k)}
          >
            {label}
          </button>
        ))}
        {platformView === 'workflow' && (
          <>
            <button type="button" className="lab-chrome-btn" disabled={running} onClick={runWorkflow}>
              {running ? <RefreshCw size={13} className="animate-spin" /> : <Play size={13} />} Run
            </button>
            <button type="button" className="lab-chrome-btn" onClick={load}><RefreshCw size={13} /></button>
            <button type="button" className="lab-chrome-btn" onClick={resetGraph} disabled={busy}>Reset</button>
          </>
        )}
      </LabChromeBar>

      {platformView !== 'workflow' ? (
        <div className="flex-1 min-h-0 overflow-y-auto">
          {renderAimlV2Page({
            nav: platformView,
            st: state || {},
            sessionId,
            busy,
            run: async (fn) => { setBusy(true); try { await fn(); await load() } finally { setBusy(false) } },
            ragQuery,
            setRagQuery,
          })}
        </div>
      ) : (
      <div className="flex-1 min-h-0 overflow-y-auto p-4 max-w-[1320px] mx-auto w-full">
        {error && (
          <div className="ag-banner ag-banner-err">
            <XCircle size={15} className="shrink-0 mt-0.5" /> {error}
          </div>
        )}

        {/* objective banner */}
        {(goal.objective || goal.title) && (
          <div className="ag-banner ag-banner-goal">
            <Target size={15} className="shrink-0 mt-0.5" style={{ color: 'var(--ag-purple)' }} />
            <span><b>{goal.title || 'Objective'}:</b> {goal.objective}</span>
          </div>
        )}

        {/* validation status from the engine's live grader */}
        <div className={`ag-banner ${validationPassed ? 'ag-banner-ok' : ''}`}
             style={validationPassed ? undefined : { background: 'rgba(154,144,192,.08)', border: '1px solid var(--ag-border)', color: 'var(--ag-muted)' }}>
          {validationPassed
            ? <CheckCircle2 size={15} className="shrink-0 mt-0.5" style={{ color: 'var(--ag-green)' }} />
            : <Activity size={15} className="shrink-0 mt-0.5" />}
          <span>{summary.validation_message || (validationPassed ? 'Goal met.' : 'Build/fix the graph, then run it. Use Check Solution in the lab to grade.')}</span>
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          {[
            ['Nodes', summary.node_count ?? nodes.length, 'var(--ag-purple)'],
            ['Connections', summary.edge_count ?? edges.length, 'var(--ag-cyan)'],
            ['Last run', summary.has_run ? (summary.last_run_ok ? 'ok' : 'errored') : '—',
              summary.has_run ? (summary.last_run_ok ? 'var(--ag-green)' : 'var(--ag-red)') : 'var(--ag-muted)'],
            ['Goal', validationPassed ? 'passed' : 'open', validationPassed ? 'var(--ag-green)' : 'var(--ag-amber)'],
          ].map(([label, val, color]) => (
            <div key={label} className="ag-card p-3">
              <div className="text-[11px]" style={{ color: 'var(--ag-muted)' }}>{label}</div>
              <div className="text-lg font-bold mt-0.5" style={{ color }}>{val}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[180px_1fr_300px] gap-3">
          {/* ── PALETTE ── */}
          <div className="ag-card p-3 h-max">
            <div className="ag-label flex items-center gap-1.5"><Plus size={12} /> Add node</div>
            {(palette.length ? palette : Object.keys(TYPE_META).map(t => ({ type: t, label: metaFor(t).label, default_config: {} }))).map(p => {
              const meta = metaFor(p.type)
              const PIcon = PALETTE_ICON[p.icon] || meta.Icon
              return (
                <button key={p.type} className="ag-pchip" disabled={busy}
                        title={p.description || ''}
                        onClick={() => addNode(p.type, p.default_config)}>
                  <span className="ag-node-icon" style={{ background: `${meta.color}22`, color: meta.color }}>
                    <PIcon size={14} />
                  </span>
                  <span className="text-xs font-semibold">{p.label || meta.label}</span>
                </button>
              )
            })}
            <div className="mt-3 pt-3 border-t text-[11px] leading-relaxed" style={{ borderColor: 'var(--ag-border)', color: 'var(--ag-muted)' }}>
              Drag a node's right dot onto another node to connect them. Click a node to configure it.
            </div>
          </div>

          {/* ── CANVAS ── */}
          <div className="ag-canvas" ref={canvasRef} onClick={() => setSelectedId(null)}>
            <div className="ag-canvas-inner">
              <Edges nodes={nodes} edges={edges} traceVisited={traceVisited} />
              {nodes.map(n => (
                <div key={n.id} data-node-id={n.id} style={{ display: 'contents' }}>
                  <NodeCard
                    node={n}
                    selected={n.id === selectedId}
                    connectSrc={connectSrc === n.id}
                    runStatus={runStatusById[n.id]}
                    onSelect={setSelectedId}
                    onDragStart={onDragStart}
                    onStartConnect={onStartConnect}
                    onDelete={removeNode}
                  />
                </div>
              ))}
              {nodes.length === 0 && (
                <div className="absolute inset-0 grid place-items-center text-sm" style={{ color: 'var(--ag-muted)' }}>
                  <div className="text-center">
                    <Bot size={28} className="mx-auto mb-2 opacity-50" />
                    Add nodes from the palette to start building your agent.
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ── CONFIG PANEL ── */}
          <div className="ag-card p-3 h-max">
            {!selected ? (
              <div className="text-sm" style={{ color: 'var(--ag-muted)' }}>
                <div className="ag-label flex items-center gap-1.5"><Settings2 size={12} /> Inspector</div>
                Select a node to edit its configuration and connections.
              </div>
            ) : (
              <ConfigPanel
                node={selected}
                edges={edges}
                nodes={nodes}
                catalog={catalog}
                onConfigure={configureNode}
                onDisconnect={disconnect}
                onConnect={connect}
                onClose={() => setSelectedId(null)}
              />
            )}
          </div>
        </div>

        {/* ── RUN OUTPUT / TRACE ── */}
        <div className="mt-4">
          <div className="flex items-center gap-2 mb-3">
            {[['trace', 'Execution trace', Activity], ['output', 'Final output', Flag]].map(([k, label, Icon]) => (
              <button key={k} onClick={() => setTab(k)}
                      className={`ag-btn ${tab === k ? '' : ''}`}
                      style={tab === k ? { borderColor: 'var(--ag-purple)', color: 'var(--ag-purple)' } : undefined}>
                <Icon size={13} /> {label}
              </button>
            ))}
          </div>

          {!lastRun ? (
            <div className="ag-card p-10 text-center text-sm" style={{ color: 'var(--ag-muted)' }}>
              <Play size={24} className="mx-auto mb-2 opacity-50" />
              Press <b>Run workflow</b> to execute the graph and see the step-by-step trace + final output.
            </div>
          ) : tab === 'trace' ? (
            <div className="ag-scroll">
              {(lastRun.errors || []).length > 0 && (
                <div className="ag-banner ag-banner-err mb-2">
                  <AlertTriangle size={15} className="shrink-0 mt-0.5" />
                  <span>{(lastRun.errors || []).join(' · ')}</span>
                </div>
              )}
              {(lastRun.trace || []).map((t, i) => {
                const meta = metaFor(t.type)
                return (
                  <div key={`${t.node_id}-${i}`} className="ag-trace-row">
                    <span className="ag-step-num">{i + 1}</span>
                    <span className="ag-node-icon shrink-0" style={{ background: `${meta.color}22`, color: meta.color }}>
                      <meta.Icon size={14} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold">{t.label || t.node_id}</span>
                        <span className="ag-node-type">{meta.label}</span>
                        <span className={`ag-badge ${t.status === 'error' ? 'ag-b-err' : 'ag-b-ok'}`}>
                          {t.status === 'error' ? <XCircle size={11} /> : <CheckCircle2 size={11} />} {t.status}
                        </span>
                        {t.branch && <span className="ag-badge ag-b-branch"><GitBranch size={10} /> {t.branch}</span>}
                      </div>
                      <div className="text-[11px] mt-0.5" style={{ color: 'var(--ag-muted)' }}>{t.note}</div>
                      {t.output && Object.keys(t.output).length > 0 && (
                        <pre className="ag-code mt-1.5 !text-[11px] !py-1.5">{JSON.stringify(t.output, null, 2)}</pre>
                      )}
                    </div>
                  </div>
                )
              })}
              {(lastRun.trace || []).length === 0 && (
                <div className="ag-card p-6 text-center text-sm" style={{ color: 'var(--ag-muted)' }}>
                  No nodes executed — make sure a trigger is connected to the rest of the graph.
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {notifications.length > 0 && (
                <div className="ag-card p-3">
                  <div className="ag-label">Notifications sent</div>
                  {notifications.map((n, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs mb-1">
                      <span className="ag-badge ag-b-ok"><CheckCircle2 size={11} /> {n.channel}</span>
                      <span style={{ color: 'var(--ag-text)' }}>{n.message}</span>
                    </div>
                  ))}
                </div>
              )}
              <div>
                <div className="ag-label mb-1">Final output payload</div>
                <pre className="ag-code">{Object.keys(finalOutput).length ? JSON.stringify(finalOutput, null, 2) : '(empty — wire an output node and run)'}</pre>
              </div>
            </div>
          )}
        </div>
      </div>
      )}
    </div>
  )
}

/* ── per-node config editor + outgoing-edge manager ── */
function ConfigPanel({ node, edges, nodes, catalog, onConfigure, onDisconnect, onConnect, onClose }) {
  const c = node.config || {}
  const set = (patch) => onConfigure(node.id, patch)
  const byId = Object.fromEntries(nodes.map(n => [n.id, n]))
  const outgoing = edges.filter(e => e.from === node.id)
  const meta = metaFor(node.type)

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="ag-label !mb-0 flex items-center gap-1.5">
          <span className="ag-node-icon !w-5 !h-5" style={{ background: `${meta.color}22`, color: meta.color }}>
            <meta.Icon size={12} />
          </span>
          {meta.label} · {node.id}
        </div>
        <button className="text-[var(--ag-muted)] hover:text-white" onClick={onClose}><X size={14} /></button>
      </div>

      <div className="space-y-2.5">
        {node.type === 'trigger' && (
          <>
            <Field label="Kind">
              <input className="ag-input" value={c.kind || ''} onChange={e => set({ kind: e.target.value })} placeholder="ticket / webhook / chat" />
            </Field>
            <Field label="Seed input (JSON)">
              <JsonField value={c.input} onCommit={(v) => set({ input: v })} rows={5} />
            </Field>
          </>
        )}

        {node.type === 'llm' && (
          <>
            <Field label="Mode">
              <Select value={c.mode || 'classify'} options={catalog.llm_modes || ['classify', 'extract', 'summarize']}
                      onChange={v => set({ mode: v })} />
            </Field>
            <Field label="Input field">
              <input className="ag-input" value={c.input_field || ''} onChange={e => set({ input_field: e.target.value })} placeholder="text" />
            </Field>
          </>
        )}

        {node.type === 'tool' && (
          <>
            <Field label="Tool kind">
              <Select value={c.kind || 'http_get'} options={catalog.tool_kinds || ['http_get', 'db_query', 'send_notification']}
                      onChange={v => set({ kind: v })} />
            </Field>
            {(c.kind || 'http_get') === 'http_get' && (
              <Field label="URL">
                <Select value={c.url || ''} options={['', ...(catalog.http_urls || [])]} onChange={v => set({ url: v })} freeText
                        onText={v => set({ url: v })} />
              </Field>
            )}
            {c.kind === 'db_query' && (
              <Field label="Query id">
                <Select value={c.query_id || ''} options={['', ...(catalog.db_queries || [])]} onChange={v => set({ query_id: v })} />
              </Field>
            )}
            {c.kind === 'send_notification' && (
              <>
                <Field label="Channel"><input className="ag-input" value={c.channel || ''} onChange={e => set({ channel: e.target.value })} placeholder="ops / billing-team" /></Field>
                <Field label="Message (supports {field})"><input className="ag-input" value={c.message || ''} onChange={e => set({ message: e.target.value })} placeholder="Escalating {ticket_id}" /></Field>
              </>
            )}
          </>
        )}

        {node.type === 'mcp_tool' && (
          <>
            <Field label="MCP server">
              <Select value={c.server || ''} options={['', ...Object.keys(catalog.mcp_servers || {})]} onChange={v => set({ server: v, tool: '' })} />
            </Field>
            <Field label="MCP tool">
              <Select value={c.tool || ''}
                      options={['', ...((catalog.mcp_servers?.[c.server]?.tools) || [])]}
                      onChange={v => set({ tool: v })} />
            </Field>
          </>
        )}

        {node.type === 'transform' && (
          <>
            <Field label="Operation">
              <Select value={c.op || 'set'} options={catalog.transform_ops || ['set', 'template', 'pick', 'json_parse']} onChange={v => set({ op: v })} />
            </Field>
            {(c.op || 'set') === 'set' && (
              <>
                <Field label="Field"><input className="ag-input" value={c.field || ''} onChange={e => set({ field: e.target.value })} /></Field>
                <Field label="Value"><input className="ag-input" value={c.value || ''} onChange={e => set({ value: e.target.value })} /></Field>
              </>
            )}
            {c.op === 'template' && (
              <>
                <Field label="Field"><input className="ag-input" value={c.field || ''} onChange={e => set({ field: e.target.value })} /></Field>
                <Field label="Template (supports {field})"><input className="ag-input" value={c.template || ''} onChange={e => set({ template: e.target.value })} /></Field>
              </>
            )}
            {c.op === 'json_parse' && (
              <Field label="Source field"><input className="ag-input" value={c.field || 'body'} onChange={e => set({ field: e.target.value })} placeholder="body" /></Field>
            )}
            {c.op === 'pick' && (
              <Field label="Fields (comma-separated)">
                <input className="ag-input" value={(c.fields || []).join(',')}
                       onChange={e => set({ fields: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })} />
              </Field>
            )}
          </>
        )}

        {node.type === 'condition' && (
          <>
            <Field label="Field"><input className="ag-input" value={c.field || ''} onChange={e => set({ field: e.target.value })} placeholder="priority / category" /></Field>
            <Field label="Operator">
              <Select value={c.op || 'equals'} options={catalog.condition_ops || ['equals', 'not_equals', 'contains', 'gt', 'lt', 'exists', 'in']} onChange={v => set({ op: v })} />
            </Field>
            <Field label="Value"><input className="ag-input" value={c.value ?? ''} onChange={e => set({ value: e.target.value })} placeholder="high" /></Field>
          </>
        )}

        {node.type === 'output' && (
          <div className="text-xs" style={{ color: 'var(--ag-muted)' }}>
            This node captures the final payload of the run. No configuration needed — just wire it as the last step.
          </div>
        )}

        {/* outgoing connections — manage / flip branch / remove */}
        <div className="pt-2 mt-1 border-t" style={{ borderColor: 'var(--ag-border)' }}>
          <div className="ag-label flex items-center gap-1.5"><Link2 size={12} /> Connections out</div>
          {outgoing.length === 0 ? (
            <div className="text-[11px]" style={{ color: 'var(--ag-muted)' }}>
              {node.type === 'output' ? 'Output is terminal — no outgoing edges.' : 'None yet. Drag this node’s right dot onto another node.'}
            </div>
          ) : (
            outgoing.map((e, i) => (
              <div key={i} className="flex items-center gap-1.5 text-xs mb-1.5">
                <ChevronRight size={12} style={{ color: 'var(--ag-muted)' }} />
                <span className="flex-1 min-w-0 truncate">{byId[e.to]?.label || e.to}</span>
                {node.type === 'condition' && (
                  <button
                    className="ag-badge ag-b-branch"
                    title="Flip the branch this edge fires on"
                    onClick={() => {
                      const next = e.branch === 'true' ? 'false' : 'true'
                      onDisconnect(node.id, e.to, e.branch)
                      onConnect(node.id, e.to, next)
                    }}
                  ><GitBranch size={10} /> {e.branch || 'any'}</button>
                )}
                <button className="text-[var(--ag-muted)] hover:text-[var(--ag-red)]"
                        title="Remove this connection"
                        onClick={() => onDisconnect(node.id, e.to, e.branch)}>
                  <Trash2 size={12} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="ag-label">{label}</span>
      {children}
    </label>
  )
}

function Select({ value, options, onChange, freeText = false, onText }) {
  // The canned URL/query lists are finite; for http_get URL we also allow free
  // text in case a learner wants to type one (it will simply 404 in the run).
  const inList = options.includes(value)
  if (freeText && !inList) {
    return (
      <div className="space-y-1">
        <input className="ag-input" value={value || ''} onChange={e => (onText || onChange)(e.target.value)} placeholder="type or pick below" />
        <select className="ag-select" value="" onChange={e => e.target.value && onChange(e.target.value)}>
          <option value="">— pick a known value —</option>
          {options.filter(Boolean).map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      </div>
    )
  }
  return (
    <select className="ag-select" value={value || ''} onChange={e => onChange(e.target.value)}>
      {options.map(o => <option key={o} value={o}>{o === '' ? '— select —' : o}</option>)}
    </select>
  )
}

/* JSON textarea that only commits valid JSON on blur (keeps the engine happy) */
function JsonField({ value, onCommit, rows = 4 }) {
  const [text, setText] = useState(() => JSON.stringify(value ?? {}, null, 2))
  const [err, setErr] = useState('')
  useEffect(() => { setText(JSON.stringify(value ?? {}, null, 2)) }, [value])
  return (
    <div>
      <textarea
        className="ag-input" rows={rows} spellCheck={false} value={text}
        onChange={e => setText(e.target.value)}
        onBlur={() => {
          try { onCommit(JSON.parse(text || '{}')); setErr('') }
          catch { setErr('Invalid JSON — not saved') }
        }}
      />
      {err && <div className="text-[11px] mt-1" style={{ color: 'var(--ag-red)' }}>{err}</div>}
    </div>
  )
}
