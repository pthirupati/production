import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Server, Play, ChevronRight } from 'lucide-react'

/* ─── Animated VMware infrastructure scenes ─────────────────────────── */
const SCENES = [
  {
    id: 'datacenter',
    title: 'vCenter Datacenter',
    subtitle: 'Manage your entire virtual infrastructure from one pane of glass',
    glowColor: '#5b9bd5',
    glowName: 'blue',
    bg: 'from-[#0d1b2e] to-[#1a2f4e]',
    render: ({ tick }) => (
      <div className="relative w-full h-full flex items-center justify-center">
        {/* Central vCenter */}
        <div className="absolute flex flex-col items-center" style={{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}>
          <div className="w-20 h-14 rounded-lg bg-[#1e3a5f] border-2 border-[#5b9bd5] flex flex-col items-center justify-center shadow-lg shadow-[#5b9bd5]/30">
            <div className="text-[8px] font-bold text-[#5b9bd5]">vmware</div>
            <div className="text-[7px] text-[#8ab4d4]">vCenter</div>
          </div>
        </div>
        {/* ESXi hosts in orbit */}
        {[0, 1, 2].map(i => {
          const angle = (i * 120 + tick * 0.3) * (Math.PI / 180)
          const r = 90
          const x = 50 + r * Math.cos(angle) * 0.5
          const y = 50 + r * Math.sin(angle) * 0.35
          return (
            <div key={i} className="absolute flex flex-col items-center" style={{ left: `${x}%`, top: `${y}%`, transform: 'translate(-50%, -50%)' }}>
              <div className="w-14 h-10 rounded-md bg-[#0d1b2e] border border-[#3a5a7f] flex flex-col items-center justify-center">
                <Server size={10} className="text-[#8ab4d4]" />
                <span className="text-[7px] text-[#8ab4d4] mt-0.5">ESXi-0{i + 1}</span>
              </div>
              {/* VMs on host */}
              <div className="flex gap-0.5 mt-0.5">
                {[0, 1].map(j => (
                  <div key={j} className={`w-3 h-2 rounded-sm border text-[5px] flex items-center justify-center ${j === 0 ? 'bg-[#2db52d]/30 border-[#2db52d]/60 text-[#2db52d]' : 'bg-[#888]/20 border-[#888]/40 text-[#888]'}`}>▪</div>
                ))}
              </div>
            </div>
          )
        })}
        {/* Connection lines */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ opacity: 0.3 }}>
          <circle cx="50%" cy="50%" r="45%" fill="none" stroke="#5b9bd5" strokeWidth="0.5" strokeDasharray="4,4" />
        </svg>
        {/* Stats overlay */}
        <div className="absolute bottom-2 left-2 right-2 flex justify-between">
          {[{ label: '3 Hosts', color: '#2db52d' }, { label: '8 VMs', color: '#5b9bd5' }, { label: 'HA On', color: '#f5a623' }].map(({ label, color }) => (
            <div key={label} className="text-[9px] font-bold px-1.5 py-0.5 rounded" style={{ color, background: `${color}20`, border: `1px solid ${color}40` }}>{label}</div>
          ))}
        </div>
      </div>
    ),
  },
  {
    id: 'vmotion',
    title: 'Live vMotion Migration',
    subtitle: 'Move running VMs between hosts with zero downtime',
    glowColor: '#27ae60',
    glowName: 'green',
    bg: 'from-[#0a1e12] to-[#0d2a1a]',
    render: ({ tick }) => {
      const progress = (tick % 120) / 120
      const vmX = 12 + progress * 58
      return (
        <div className="relative w-full h-full flex items-center justify-center">
          {/* Source host */}
          <div className="absolute flex flex-col items-center" style={{ left: '10%', top: '50%', transform: 'translateY(-50%)' }}>
            <div className="w-20 h-14 rounded-lg bg-[#0d1b2e] border border-[#5b9bd5] flex flex-col items-center justify-center p-1">
              <Server size={12} className="text-[#5b9bd5] mb-1" />
              <span className="text-[8px] text-[#8ab4d4]">ESXi-01</span>
              <div className="text-[7px] text-[#666] mt-0.5">CPU 42%</div>
            </div>
          </div>
          {/* Arrow track */}
          <div className="absolute left-1/4 right-1/4" style={{ top: '50%', height: 2, background: 'linear-gradient(90deg, #5b9bd5, #27ae60)', opacity: 0.4 }} />
          {/* Moving VM */}
          <div className="absolute transition-none" style={{ left: `${vmX}%`, top: '42%', transform: 'translate(-50%, -50%)' }}>
            <div className="w-14 h-10 rounded-md border-2 border-[#27ae60] bg-[#0a1e12] flex flex-col items-center justify-center shadow-lg shadow-[#27ae60]/40">
              <div className="w-2 h-2 rounded-full bg-[#27ae60] mb-0.5 animate-pulse" />
              <span className="text-[7px] text-[#27ae60]">web-prod-01</span>
              <span className="text-[6px] text-[#888]">RUNNING</span>
            </div>
          </div>
          {/* Destination host */}
          <div className="absolute flex flex-col items-center" style={{ right: '10%', top: '50%', transform: 'translateY(-50%)' }}>
            <div className="w-20 h-14 rounded-lg bg-[#0d1b2e] border border-[#27ae60] flex flex-col items-center justify-center p-1">
              <Server size={12} className="text-[#27ae60] mb-1" />
              <span className="text-[8px] text-[#8ab4d4]">ESXi-02</span>
              <div className="text-[7px] text-[#666] mt-0.5">CPU 15%</div>
            </div>
          </div>
          {/* Progress */}
          <div className="absolute bottom-2 left-2 right-2">
            <div className="flex justify-between text-[9px] text-[#8ab4d4] mb-1">
              <span>VMotion in progress</span>
              <span>{Math.floor(progress * 100)}%</span>
            </div>
            <div className="h-1.5 bg-[#1a3a2a] rounded-full overflow-hidden">
              <div className="h-full bg-[#27ae60] rounded-full transition-none" style={{ width: `${progress * 100}%` }} />
            </div>
          </div>
        </div>
      )
    },
  },
  {
    id: 'ha',
    title: 'High Availability (HA)',
    subtitle: 'Automatic VM restart when a host fails — zero manual intervention',
    glowColor: '#e0412b',
    glowName: 'red',
    bg: 'from-[#1e0a0a] to-[#2a0d0d]',
    render: ({ tick }) => {
      const phase = tick % 180
      const hostFailing = phase < 60
      const migrating = phase >= 60 && phase < 120
      const recovered = phase >= 120
      return (
        <div className="relative w-full h-full flex items-center justify-center">
          {/* Cluster label */}
          <div className="absolute top-2 left-2 text-[9px] text-[#888] border border-[#333] rounded px-1.5 py-0.5">Cluster-01 · HA Enabled</div>
          {/* Host 1 — failing */}
          <div className="absolute" style={{ left: '10%', top: '35%' }}>
            <div className={`w-20 h-14 rounded-lg border-2 flex flex-col items-center justify-center transition-all ${hostFailing ? 'border-[#e0412b] bg-[#3a0a0a] shadow-lg shadow-[#e0412b]/30' : 'border-[#888]/40 bg-[#0d1b2e]'}`}>
              <Server size={12} className={hostFailing ? 'text-[#e0412b]' : 'text-[#888]'} />
              <span className={`text-[8px] mt-0.5 ${hostFailing ? 'text-[#e0412b]' : 'text-[#888]'}`}>ESXi-01</span>
              <span className={`text-[7px] ${hostFailing ? 'text-[#e0412b] animate-pulse' : recovered ? 'text-[#888]' : 'text-[#888]'}`}>
                {hostFailing ? '⚠ FAILED' : 'OFFLINE'}
              </span>
            </div>
          </div>
          {/* HA arrow */}
          {(migrating) && (
            <div className="absolute" style={{ left: '35%', top: '45%', width: '30%', height: 2, background: '#f5a623' }}>
              <div className="absolute right-0 top-[-4px] text-[#f5a623] text-xs">→</div>
            </div>
          )}
          {/* Host 2 — receiving */}
          <div className="absolute" style={{ right: '10%', top: '35%' }}>
            <div className={`w-20 h-14 rounded-lg border-2 flex flex-col items-center justify-center transition-all ${recovered ? 'border-[#27ae60] bg-[#0a1e12] shadow-lg shadow-[#27ae60]/20' : 'border-[#5b9bd5] bg-[#0d1b2e]'}`}>
              <Server size={12} className={recovered ? 'text-[#27ae60]' : 'text-[#5b9bd5]'} />
              <span className="text-[8px] text-[#8ab4d4] mt-0.5">ESXi-02</span>
              <span className={`text-[7px] ${recovered ? 'text-[#27ae60]' : 'text-[#5b9bd5]'}`}>{recovered ? '✓ +2 VMs' : 'RUNNING'}</span>
            </div>
          </div>
          {/* Status message */}
          <div className="absolute bottom-2 left-2 right-2 text-center">
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${hostFailing ? 'text-[#e0412b] bg-[#e0412b]/10' : migrating ? 'text-[#f5a623] bg-[#f5a623]/10' : 'text-[#27ae60] bg-[#27ae60]/10'}`}>
              {hostFailing ? '⚠ Host failure detected — HA triggering restart' : migrating ? '⟳ Restarting VMs on surviving host…' : '✓ VMs recovered — zero data loss'}
            </span>
          </div>
        </div>
      )
    },
  },
  {
    id: 'resources',
    title: 'Real-time Resource Management',
    subtitle: 'Monitor CPU, memory, storage, and networking across your entire infrastructure',
    glowColor: '#9b59b6',
    glowName: 'purple',
    bg: 'from-[#130a1e] to-[#1a0f2a]',
    render: ({ tick }) => {
      const cpuPct = 42 + Math.sin(tick * 0.05) * 15
      const memPct = 68 + Math.sin(tick * 0.03 + 1) * 10
      const diskPct = 58 + Math.sin(tick * 0.02 + 2) * 8
      const netMbps = 120 + Math.sin(tick * 0.07) * 40
      return (
        <div className="relative w-full h-full p-3 flex flex-col gap-2">
          <div className="text-[9px] text-[#8ab4d4] font-bold mb-1">esxi-01.fixitlab.local</div>
          {[
            { label: 'CPU', val: cpuPct, max: '2×8 cores @ 2.9GHz', color: '#4c9be8' },
            { label: 'Memory', val: memPct, max: '64 GB total', color: '#9b59b6' },
            { label: 'Storage', val: diskPct, max: '2.5 TB total', color: '#e67e22' },
          ].map(({ label, val, max, color }) => (
            <div key={label}>
              <div className="flex justify-between text-[9px] mb-0.5">
                <span className="font-bold" style={{ color }}>{label}</span>
                <span className="text-[#8ab4d4]">{val.toFixed(0)}%</span>
              </div>
              <div className="h-3 rounded-sm overflow-hidden" style={{ background: '#1a1a2e', border: '1px solid #333' }}>
                <div className="h-full rounded-sm transition-none" style={{ width: `${val}%`, background: color }} />
              </div>
              <div className="text-[8px] text-[#555] mt-0.5">{max}</div>
            </div>
          ))}
          <div className="mt-1 grid grid-cols-2 gap-2">
            {[
              { label: 'Network', val: `${netMbps.toFixed(0)} Mbps`, color: '#27ae60' },
              { label: 'VMs Running', val: '4 / 4', color: '#2db52d' },
            ].map(({ label, val, color }) => (
              <div key={label} className="border rounded p-1.5 text-center" style={{ borderColor: `${color}40`, background: `${color}10` }}>
                <div className="text-[8px] text-[#888]">{label}</div>
                <div className="text-[11px] font-bold mt-0.5" style={{ color }}>{val}</div>
              </div>
            ))}
          </div>
        </div>
      )
    },
  },
]

export default function VMwareDemoWidget() {
  const [sceneIdx, setSceneIdx] = useState(0)
  const [tick, setTick] = useState(0)
  const [isPlaying, setIsPlaying] = useState(true)
  const intervalRef = useRef(null)

  useEffect(() => {
    if (!isPlaying) return
    intervalRef.current = setInterval(() => {
      setTick(t => t + 1)
    }, 50)
    return () => clearInterval(intervalRef.current)
  }, [isPlaying])

  useEffect(() => {
    if (!isPlaying) return
    const timer = setInterval(() => {
      setSceneIdx(i => (i + 1) % SCENES.length)
    }, 5000)
    return () => clearInterval(timer)
  }, [isPlaying])

  const scene = SCENES[sceneIdx]

  return (
    <div className="relative rounded-2xl overflow-hidden border border-surface-700 shadow-2xl" style={{ background: '#0d1117' }}>
      {/* VMware header bar */}
      <div className="flex items-center h-8 px-3 gap-2" style={{ background: '#1e3a5f' }}>
        <span className="text-white font-bold text-xs tracking-tight">
          <span style={{ color: '#5b9bd5' }}>vm</span>ware ESXi
        </span>
        <div className="flex-1" />
        <div className="flex gap-1">
          {['', '', ''].map((_, i) => (
            <div key={i} className="w-2.5 h-2.5 rounded-full" style={{ background: i === 0 ? '#e04' : i === 1 ? '#f5a623' : '#2db52d', opacity: 0.8 }} />
          ))}
        </div>
      </div>

      {/* Scene area */}
      <div className={`relative bg-gradient-to-br ${scene.bg}`} style={{ height: 220 }}>
        <scene.render tick={tick} />

        {/* Play/pause */}
        <button
          onClick={() => setIsPlaying(v => !v)}
          className="absolute top-2 right-2 w-6 h-6 rounded-full bg-black/40 flex items-center justify-center hover:bg-black/60 transition-colors"
        >
          {isPlaying ? (
            <span className="text-white text-[8px]">⏸</span>
          ) : (
            <Play size={8} className="text-white ml-0.5" />
          )}
        </button>
      </div>

      {/* Scene info */}
      <div className="px-4 py-3" style={{ background: '#111827' }}>
        <div className="flex items-start gap-2 mb-2">
          <div className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{ background: scene.glowColor }} />
          <div>
            <p className="text-sm font-bold text-white">{scene.title}</p>
            <p className="text-xs text-surface-400 mt-0.5">{scene.subtitle}</p>
          </div>
        </div>

        {/* Scene selector dots */}
        <div className="flex items-center gap-1.5 mt-2">
          {SCENES.map((s, i) => (
            <button
              key={s.id}
              onClick={() => { setSceneIdx(i); setIsPlaying(true) }}
              className="rounded-full transition-all"
              style={{
                width: sceneIdx === i ? 20 : 6,
                height: 6,
                background: sceneIdx === i ? scene.glowColor : '#3a4a5a',
              }}
            />
          ))}
          <Link
            to="/scenarios?technology=vmware"
            className="ml-auto flex items-center gap-1 text-xs font-semibold px-3 py-1 rounded-lg"
            style={{ background: `${scene.glowColor}20`, color: scene.glowColor, border: `1px solid ${scene.glowColor}40` }}
          >
            Try VMware Lab <ChevronRight size={12} />
          </Link>
        </div>
      </div>
    </div>
  )
}
