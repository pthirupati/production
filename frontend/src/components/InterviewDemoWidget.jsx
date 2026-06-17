import { useState, useEffect, useCallback } from 'react'
import { Mic, MicOff, Video, VideoOff, Phone, Star, CheckCircle, Brain, Shield, ChevronRight, Volume2 } from 'lucide-react'
import { Link } from 'react-router-dom'

const DEMO_SCRIPT = [
  {
    phase: 'Technical Round 1',
    persona: 'Aria',
    role: 'Senior SRE · Google',
    question: 'A production server is showing high load average but low CPU usage. Walk me through your diagnostic approach.',
    answer: 'I\'d check I/O wait with iostat -x. High load + low CPU usually means disk or NFS blocking — stale mounts, failing disk, or D-state processes.',
    scores: { situation: true, task: true, action: true, result: true },
    score: 91,
    keywords: ['iostat', 'I/O wait', 'D-state', 'dmesg'],
    feedback: 'Excellent systematic approach — technically precise.',
    glowColor: '#06b6d4',
    glowName: 'cyan',
    bgGrad: 'from-cyan-900/40 to-slate-950',
    initials: 'AR',
  },
  {
    phase: 'Behavioral Round',
    persona: 'Nova',
    role: 'Engineering Manager · AWS',
    question: 'Tell me about a critical production outage you fixed under pressure. What was your process?',
    answer: 'Black Friday — Redis cluster failed, 100% checkout errors. I formed a war room, rolled back the config change, restored in 8 minutes, then added sentinel failover.',
    scores: { situation: true, task: true, action: true, result: true },
    score: 88,
    keywords: ['war room', 'rollback', 'failover', 'sentinel'],
    feedback: 'Strong STAR with quantified impact and preventive follow-up.',
    glowColor: '#8b5cf6',
    glowName: 'purple',
    bgGrad: 'from-purple-900/40 to-slate-950',
    initials: 'NV',
  },
  {
    phase: 'System Design',
    persona: 'Atlas',
    role: 'Principal Engineer · Meta',
    question: 'How would you design a highly available NFS solution for 500+ Linux servers?',
    answer: 'Pacemaker + DRBD for HA, or AWS EFS. Key: active-passive failover under 30s, soft mount options, autofs for on-demand, and mount alerts.',
    scores: { situation: true, task: true, action: true, result: false },
    score: 79,
    keywords: ['Pacemaker', 'DRBD', 'EFS', 'autofs'],
    feedback: 'Good design — add recovery time objectives and capacity planning.',
    glowColor: '#f59e0b',
    glowName: 'amber',
    bgGrad: 'from-amber-900/30 to-slate-950',
    initials: 'AT',
  },
]

const PHASE_DURATION = 13000
const STEP = { INTRO: 0, ASKING: 2000, ANSWERING: 5500, EVALUATING: 9000, SCORED: 11000 }

/* ── Animated mouth hook ── */
function useMouthAnim(speaking) {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (!speaking) { setOpen(false); return }
    const t = setInterval(() => setOpen(o => !o), 200)
    return () => clearInterval(t)
  }, [speaking])
  return open
}

/* ── AI interviewer face ── */
function AIFace({ speaking, glowColor = '#06b6d4' }) {
  const open = useMouthAnim(speaking)
  const [scan, setScan] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setScan(s => (s + 1) % 100), 80)
    return () => clearInterval(t)
  }, [])
  const scanY = 28 + (scan / 100) * 72

  return (
    <svg viewBox="0 0 120 130" xmlns="http://www.w3.org/2000/svg" className="w-full h-full" aria-hidden="true">
      <defs>
        <radialGradient id={`aiHead${glowColor.replace('#', '')}`} cx="50%" cy="38%" r="68%">
          <stop offset="0%" stopColor="#182c46" />
          <stop offset="100%" stopColor="#0b1220" />
        </radialGradient>
        <radialGradient id={`eyeG${glowColor.replace('#', '')}`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={glowColor} stopOpacity="1" />
          <stop offset="80%" stopColor={glowColor} stopOpacity="0.4" />
          <stop offset="100%" stopColor={glowColor} stopOpacity="0" />
        </radialGradient>
        <filter id="faceGlow" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur in="SourceAlpha" stdDeviation="2.5" result="blur" />
          <feFlood floodColor={glowColor} floodOpacity="0.6" result="color" />
          <feComposite in="color" in2="blur" operator="in" result="shadow" />
          <feMerge><feMergeNode in="shadow" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {/* Head shell */}
      <ellipse cx="60" cy="62" rx="46" ry="50" fill={`url(#aiHead${glowColor.replace('#', '')})`} />
      {/* Outer ring border glow */}
      <ellipse cx="60" cy="62" rx="46" ry="50" fill="none" stroke={glowColor} strokeWidth="1" opacity={speaking ? 0.6 : 0.2} />

      {/* Circuit traces */}
      <line x1="14" y1="46" x2="26" y2="46" stroke={glowColor} strokeWidth="0.8" opacity="0.25" />
      <line x1="26" y1="46" x2="26" y2="36" stroke={glowColor} strokeWidth="0.8" opacity="0.25" />
      <circle cx="26" cy="36" r="1.5" fill={glowColor} opacity="0.3" />
      <line x1="94" y1="50" x2="106" y2="50" stroke={glowColor} strokeWidth="0.8" opacity="0.25" />
      <line x1="94" y1="72" x2="110" y2="72" stroke={glowColor} strokeWidth="0.8" opacity="0.25" />
      <circle cx="110" cy="72" r="1.5" fill={glowColor} opacity="0.3" />
      <line x1="34" y1="28" x2="52" y2="28" stroke={glowColor} strokeWidth="0.6" opacity="0.15" />
      <line x1="68" y1="28" x2="86" y2="28" stroke={glowColor} strokeWidth="0.6" opacity="0.15" />

      {/* Eye sockets (hexagonal) */}
      <polygon points="36,52 42,46 52,46 58,52 52,58 42,58" fill="#0c1825" stroke={glowColor} strokeWidth="1.2" opacity="0.7" filter="url(#faceGlow)" />
      <polygon points="62,52 68,46 78,46 84,52 78,58 68,58" fill="#0c1825" stroke={glowColor} strokeWidth="1.2" opacity="0.7" filter="url(#faceGlow)" />

      {/* Eye irises */}
      <circle cx="47" cy="52" r="5" fill={`url(#eyeG${glowColor.replace('#', '')})`} />
      <circle cx="47" cy="52" r="2.5" fill={glowColor} opacity="0.95" />
      <circle cx="48.5" cy="50.5" r="1" fill="white" opacity="0.7" />

      <circle cx="73" cy="52" r="5" fill={`url(#eyeG${glowColor.replace('#', '')})`} />
      <circle cx="73" cy="52" r="2.5" fill={glowColor} opacity="0.95" />
      <circle cx="74.5" cy="50.5" r="1" fill="white" opacity="0.7" />

      {/* Scanning eye blink rings */}
      {speaking && (
        <>
          <circle cx="47" cy="52" r="7" fill="none" stroke={glowColor} strokeWidth="0.8" opacity="0.4" />
          <circle cx="73" cy="52" r="7" fill="none" stroke={glowColor} strokeWidth="0.8" opacity="0.4" />
        </>
      )}

      {/* Nose ridge */}
      <line x1="60" y1="62" x2="60" y2="69" stroke={glowColor} strokeWidth="1.2" opacity="0.35" />
      <circle cx="57" cy="70" r="1.2" fill={glowColor} opacity="0.3" />
      <circle cx="63" cy="70" r="1.2" fill={glowColor} opacity="0.3" />

      {/* Mouth */}
      {open ? (
        <>
          <path d="M 44 80 Q 60 90 76 80" fill="#091522" stroke={glowColor} strokeWidth="1.5" strokeLinecap="round" />
          <ellipse cx="60" cy="84" rx="10" ry="4.5" fill={glowColor} opacity="0.18" />
          <line x1="50" y1="83" x2="70" y2="83" stroke={glowColor} strokeWidth="0.6" opacity="0.5" />
        </>
      ) : (
        <path d="M 44 80 Q 60 85 76 80" fill="none" stroke={glowColor} strokeWidth="1.5" strokeLinecap="round" />
      )}

      {/* Chin data strip */}
      <rect x="45" y="100" width="30" height="4" rx="2" fill={glowColor} opacity="0.12" />
      <rect x="45" y="100" width={`${30 * (scan / 100)}`} height="4" rx="2" fill={glowColor} opacity="0.35" />

      {/* Moving scan line */}
      <line x1="14" y1={scanY} x2="106" y2={scanY} stroke={glowColor} strokeWidth="0.7" opacity={0.04 + (speaking ? 0.06 : 0)} />

      {/* Status ring at chin */}
      <circle cx="60" cy="116" r="4" fill={glowColor} opacity={speaking ? 0.9 : 0.5} />
      <circle cx="60" cy="116" r="7" fill="none" stroke={glowColor} strokeWidth="0.8" opacity={speaking ? 0.5 : 0.2} />
    </svg>
  )
}

/* ── Human candidate face ── */
function HumanFace({ speaking }) {
  const open = useMouthAnim(speaking)
  return (
    <svg viewBox="0 0 120 140" xmlns="http://www.w3.org/2000/svg" className="w-full h-full" aria-hidden="true">
      <defs>
        <radialGradient id="skinGrad" cx="50%" cy="38%" r="68%">
          <stop offset="0%" stopColor="#d4956a" />
          <stop offset="100%" stopColor="#b36e42" />
        </radialGradient>
        <radialGradient id="hairGrad" cx="50%" cy="30%" r="70%">
          <stop offset="0%" stopColor="#4a2c17" />
          <stop offset="100%" stopColor="#2d1a0e" />
        </radialGradient>
      </defs>

      {/* Shoulders / clothing */}
      <path d="M -5 145 Q 22 118 50 122 Q 60 124 70 122 Q 98 118 125 145 Z" fill="#1e3a8a" />
      {/* Collar */}
      <path d="M 48 124 L 55 134 L 60 131 L 65 134 L 72 124" fill="#1d3580" stroke="#2a4ca8" strokeWidth="0.8" />
      {/* Neck */}
      <rect x="49" y="110" width="22" height="16" rx="5" fill="#c2855a" />

      {/* Ears */}
      <ellipse cx="15" cy="70" rx="8" ry="10" fill="#c2855a" />
      <ellipse cx="15" cy="70" rx="5" ry="7" fill="#b5714a" opacity="0.6" />
      <ellipse cx="105" cy="70" rx="8" ry="10" fill="#c2855a" />
      <ellipse cx="105" cy="70" rx="5" ry="7" fill="#b5714a" opacity="0.6" />

      {/* Head */}
      <ellipse cx="60" cy="66" rx="45" ry="53" fill="url(#skinGrad)" />

      {/* Hair top */}
      <path d="M 15 60 Q 15 14 60 13 Q 105 14 105 60 L 100 42 Q 96 17 60 17 Q 24 17 20 42 Z" fill="url(#hairGrad)" />
      {/* Hair sides */}
      <path d="M 15 60 Q 12 40 17 28 Q 22 18 20 42 Z" fill="url(#hairGrad)" />
      <path d="M 105 60 Q 108 40 103 28 Q 98 18 100 42 Z" fill="url(#hairGrad)" />

      {/* Eyebrows */}
      <path d="M 35 54 Q 44 50 54 53" fill="none" stroke="#3d2010" strokeWidth="2.8" strokeLinecap="round" />
      <path d="M 66 53 Q 76 50 85 54" fill="none" stroke="#3d2010" strokeWidth="2.8" strokeLinecap="round" />

      {/* Eye whites */}
      <ellipse cx="44" cy="65" rx="9.5" ry="7.5" fill="white" />
      <ellipse cx="76" cy="65" rx="9.5" ry="7.5" fill="white" />
      {/* Eyelid shadow */}
      <ellipse cx="44" cy="62" rx="9.5" ry="4" fill="#c2855a" opacity="0.25" />
      <ellipse cx="76" cy="62" rx="9.5" ry="4" fill="#c2855a" opacity="0.25" />
      {/* Irises */}
      <circle cx="45" cy="65" r="5.5" fill="#3d2010" />
      <circle cx="77" cy="65" r="5.5" fill="#3d2010" />
      {/* Pupils */}
      <circle cx="46" cy="65" r="3" fill="#0d0705" />
      <circle cx="78" cy="65" r="3" fill="#0d0705" />
      {/* Eye shine */}
      <circle cx="48" cy="62.5" r="1.8" fill="white" opacity="0.75" />
      <circle cx="80" cy="62.5" r="1.8" fill="white" opacity="0.75" />
      {/* Lower lash line */}
      <path d="M 35 69 Q 44 72 53 69" fill="none" stroke="#3d2010" strokeWidth="0.8" opacity="0.4" />
      <path d="M 67 69 Q 76 72 85 69" fill="none" stroke="#3d2010" strokeWidth="0.8" opacity="0.4" />

      {/* Nose */}
      <path d="M 57 74 L 54 83 Q 60 87 66 83 L 63 74" fill="none" stroke="#a0614a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <ellipse cx="55.5" cy="84" rx="3" ry="2" fill="#b5714a" opacity="0.4" />
      <ellipse cx="64.5" cy="84" rx="3" ry="2" fill="#b5714a" opacity="0.4" />

      {/* Lips */}
      {open ? (
        <>
          {/* Upper lip */}
          <path d="M 45 96 Q 52 93 60 95 Q 68 93 75 96 Q 68 98 60 97 Q 52 98 45 96 Z" fill="#c26050" />
          {/* Mouth opening */}
          <ellipse cx="60" cy="100" rx="12" ry="5.5" fill="#7a2020" />
          {/* Teeth */}
          <ellipse cx="60" cy="97" rx="10" ry="3" fill="#f5f0ec" opacity="0.9" />
          {/* Lower lip */}
          <path d="M 45 96 Q 60 108 75 96" fill="#d4705a" opacity="0.7" />
        </>
      ) : (
        <>
          <path d="M 45 96 Q 52 93 60 95 Q 68 93 75 96 Q 68 100 60 99 Q 52 100 45 96 Z" fill="#c26050" />
          <path d="M 45 96 Q 60 104 75 96" fill="none" stroke="#a04038" strokeWidth="1.2" />
        </>
      )}

      {/* Cheek blush */}
      <ellipse cx="30" cy="76" rx="11" ry="7" fill="#ff6644" opacity="0.14" />
      <ellipse cx="90" cy="76" rx="11" ry="7" fill="#ff6644" opacity="0.14" />
    </svg>
  )
}

/* ── Voice wave bars ── */
function VoiceWave({ active, color = '#06b6d4', bars = 8 }) {
  const heights = [3, 5, 7, 9, 8, 6, 4, 5, 7, 6, 8, 4]
  return (
    <div className="flex items-center gap-[2px] h-5">
      {Array.from({ length: bars }).map((_, i) => (
        <div
          key={i}
          className="rounded-full transition-all"
          style={{
            width: 3,
            height: active ? `${heights[i % heights.length] * 2.5}px` : '3px',
            background: color,
            opacity: active ? 0.9 : 0.25,
            animation: active ? `voice-bar 0.7s ease-in-out infinite alternate` : 'none',
            animationDelay: `${i * 0.08}s`,
          }}
        />
      ))}
    </div>
  )
}

/* ── Circular score badge ── */
function ScoreBadge({ score }) {
  const color = score >= 85 ? '#10b981' : score >= 70 ? '#f59e0b' : '#ef4444'
  return (
    <div className="flex items-center gap-1.5">
      <div className="relative w-10 h-10">
        <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
          <circle cx="18" cy="18" r="15" fill="none" stroke="rgb(30 41 59)" strokeWidth="3" />
          <circle
            cx="18" cy="18" r="15" fill="none"
            stroke={color} strokeWidth="3"
            strokeDasharray={`${(score / 100) * 94} 94`}
            strokeLinecap="round"
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-[10px] font-black" style={{ color }}>{score}</span>
      </div>
    </div>
  )
}

/* ── Main widget ── */
export default function InterviewDemoWidget() {
  const [scene, setScene] = useState(0)
  const [step, setStep] = useState(STEP.INTRO)
  const [playing, setPlaying] = useState(true)
  const [camOff, setCamOff] = useState(false)

  const advance = useCallback(() => {
    setScene(s => (s + 1) % DEMO_SCRIPT.length)
    setStep(STEP.INTRO)
  }, [])

  useEffect(() => {
    if (!playing) return
    const steps = [
      { at: STEP.ASKING,     fn: () => setStep(STEP.ASKING) },
      { at: STEP.ANSWERING,  fn: () => setStep(STEP.ANSWERING) },
      { at: STEP.EVALUATING, fn: () => setStep(STEP.EVALUATING) },
      { at: STEP.SCORED,     fn: () => setStep(STEP.SCORED) },
      { at: PHASE_DURATION,  fn: advance },
    ]
    const timers = steps.map(({ at, fn }) => setTimeout(fn, at))
    return () => timers.forEach(clearTimeout)
  }, [scene, playing, advance])

  const demo = DEMO_SCRIPT[scene]
  const interviewerSpeaking = step === STEP.ASKING
  const userSpeaking = step === STEP.ANSWERING
  const evaluating = step === STEP.EVALUATING
  const scored = step === STEP.SCORED

  return (
    <div className="relative rounded-2xl overflow-hidden">
      {/* Ambient glow */}
      <div
        className="absolute -inset-4 rounded-3xl blur-2xl pointer-events-none opacity-60"
        style={{ background: `radial-gradient(ellipse at 50% 50%, ${demo.glowColor}25 0%, transparent 70%)` }}
      />

      <div className="relative glass-card gradient-border overflow-hidden">
        {/* Title bar */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-surface-950/80 border-b border-surface-700/50">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-accent-red/80" />
            <div className="w-2.5 h-2.5 rounded-full bg-accent-amber/80" />
            <div className="w-2.5 h-2.5 rounded-full bg-accent-green/80" />
            <span className="ml-2 text-xs text-surface-400 font-mono">FixitLab · AI Interview Studio</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent-red/15 border border-accent-red/30">
              <div className="w-1.5 h-1.5 rounded-full bg-accent-red animate-pulse" />
              <span className="text-[9px] text-accent-red font-bold uppercase">Live</span>
            </div>
            <button
              onClick={() => setPlaying(p => !p)}
              className="text-xs text-surface-500 hover:text-white transition-colors px-2 py-0.5 rounded border border-surface-700 hover:border-surface-500"
            >
              {playing ? '⏸' : '▶'}
            </button>
          </div>
        </div>

        {/* Phase label + scene dots */}
        <div className="flex items-center justify-between px-4 pt-2.5 pb-0">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-widest border" style={{
            background: `${demo.glowColor}15`,
            borderColor: `${demo.glowColor}40`,
            color: demo.glowColor,
          }}>
            <Brain size={9} /> {demo.phase}
          </div>
          <div className="flex gap-1.5">
            {DEMO_SCRIPT.map((d, i) => (
              <button
                key={i}
                onClick={() => { setScene(i); setStep(STEP.INTRO) }}
                className="w-1.5 h-1.5 rounded-full transition-all"
                style={{
                  background: i === scene ? d.glowColor : undefined,
                  transform: i === scene ? 'scale(1.3)' : undefined,
                  backgroundColor: i === scene ? undefined : '#475569',
                }}
              />
            ))}
          </div>
        </div>

        {/* VIDEO CALL GRID */}
        <div className="grid grid-cols-2 gap-2 p-3">
          {/* AI Interviewer tile */}
          <div
            className="relative rounded-xl overflow-hidden aspect-[4/3] border-2 transition-all duration-500"
            style={{
              background: 'linear-gradient(135deg, #0f1f35 0%, #0b1220 100%)',
              borderColor: interviewerSpeaking ? demo.glowColor : 'rgba(71,85,105,0.5)',
              boxShadow: interviewerSpeaking ? `0 0 20px ${demo.glowColor}40` : undefined,
            }}
          >
            {/* Hex grid overlay */}
            <div className="absolute inset-0 opacity-[0.04]" style={{
              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='28'%3E%3Cpath d='M12 1 L23 7 L23 21 L12 27 L1 21 L1 7 Z' fill='none' stroke='%2306b6d4' stroke-width='0.5'/%3E%3C/svg%3E")`,
              backgroundSize: '24px 28px',
            }} />

            {/* AI face SVG */}
            <div className="absolute inset-0 flex items-center justify-center p-2">
              <AIFace speaking={interviewerSpeaking} glowColor={demo.glowColor} />
            </div>

            {/* Speaking glow overlay */}
            {interviewerSpeaking && (
              <div className="absolute inset-0 pointer-events-none rounded-xl"
                style={{ boxShadow: `inset 0 0 20px ${demo.glowColor}20` }} />
            )}

            {/* Voice wave */}
            {interviewerSpeaking && (
              <div className="absolute bottom-2 left-0 right-0 flex justify-center">
                <div className="bg-surface-950/90 rounded-full px-2 py-1 flex items-center gap-1.5">
                  <Volume2 size={9} style={{ color: demo.glowColor }} />
                  <VoiceWave active color={demo.glowColor} bars={8} />
                </div>
              </div>
            )}

            {/* Name tag */}
            <div className="absolute bottom-2 left-2 text-[9px] text-white/70 font-medium bg-black/50 px-1.5 py-0.5 rounded backdrop-blur-sm">
              {demo.persona} · AI
            </div>
            <div className="absolute top-2 right-2 text-[8px] font-medium px-1.5 py-0.5 rounded"
              style={{ background: `${demo.glowColor}25`, color: demo.glowColor }}>
              HD
            </div>
          </div>

          {/* Candidate tile */}
          <div
            className="relative rounded-xl overflow-hidden aspect-[4/3] border-2 transition-all duration-500"
            style={{
              background: 'linear-gradient(135deg, #1a2035 0%, #111827 100%)',
              borderColor: userSpeaking ? '#8b5cf6' : 'rgba(71,85,105,0.5)',
              boxShadow: userSpeaking ? `0 0 20px #8b5cf640` : undefined,
            }}
          >
            {camOff ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-surface-900">
                <VideoOff size={24} className="text-surface-600" />
                <p className="text-[10px] text-surface-500">Camera off</p>
              </div>
            ) : (
              <>
                {/* Bokeh bg */}
                <div className="absolute inset-0 opacity-30"
                  style={{ background: 'radial-gradient(ellipse at 60% 30%, #3730a320 0%, transparent 60%), radial-gradient(ellipse at 30% 70%, #7c3aed20 0%, transparent 50%)' }} />

                {/* Human face */}
                <div className="absolute inset-0 flex items-center justify-center p-1">
                  <HumanFace speaking={userSpeaking} />
                </div>
              </>
            )}

            {/* Voice wave */}
            {userSpeaking && (
              <div className="absolute bottom-2 left-0 right-0 flex justify-center">
                <div className="bg-surface-950/90 rounded-full px-2 py-1 flex items-center gap-1.5">
                  <Mic size={9} className="text-accent-purple animate-pulse" />
                  <VoiceWave active color="#8b5cf6" bars={8} />
                </div>
              </div>
            )}

            <div className="absolute bottom-2 left-2 text-[9px] text-white/70 font-medium bg-black/50 px-1.5 py-0.5 rounded backdrop-blur-sm">
              You
            </div>
            <div className="absolute top-2 right-2 text-[8px] font-medium px-1.5 py-0.5 rounded bg-accent-green/20 text-accent-green">
              {userSpeaking ? 'MIC ON' : 'READY'}
            </div>
          </div>
        </div>

        {/* Transcript area */}
        <div className="mx-3 mb-2 bg-surface-950/60 rounded-xl border border-surface-700/40 px-3 py-2.5 min-h-[56px]">
          {step === STEP.INTRO && (
            <p className="text-[11px] text-surface-500 italic text-center pt-1">Connecting to interview session…</p>
          )}
          {interviewerSpeaking && (
            <div>
              <p className="text-[9px] font-bold uppercase tracking-wider mb-1 flex items-center gap-1" style={{ color: demo.glowColor }}>
                <Volume2 size={8} /> {demo.persona} is asking
              </p>
              <p className="text-[11px] text-surface-200 leading-relaxed line-clamp-2">{demo.question}</p>
            </div>
          )}
          {(userSpeaking || evaluating || scored) && (
            <div>
              <p className="text-[9px] text-accent-purple font-bold uppercase tracking-wider mb-1 flex items-center gap-1">
                <Mic size={8} /> {userSpeaking ? 'You are answering' : 'Your answer'}
              </p>
              <p className="text-[11px] text-surface-300 leading-relaxed line-clamp-2">{demo.answer}</p>
            </div>
          )}
        </div>

        {/* Evaluation spinner */}
        {evaluating && !scored && (
          <div className="mx-3 mb-2 px-3 py-2 bg-accent-amber/8 border border-accent-amber/20 rounded-xl flex items-center gap-2 text-xs text-accent-amber">
            <div className="w-3 h-3 border-2 border-accent-amber border-t-transparent rounded-full animate-spin shrink-0" />
            Analyzing STAR framework, keywords, technical depth…
          </div>
        )}

        {/* Score card */}
        {scored && (
          <div className="mx-3 mb-2 glass-card p-3 border border-surface-700/50 flex items-start gap-3 animate-slide-up">
            <ScoreBadge score={demo.score} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 flex-wrap mb-1.5">
                {Object.entries(demo.scores).map(([k, v]) => (
                  <span key={k} className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full border flex items-center gap-0.5 ${
                    v ? 'bg-accent-green/10 border-accent-green/30 text-accent-green' : 'bg-surface-800 border-surface-700 text-surface-500'
                  }`}>
                    {v && <CheckCircle size={7} />}{k.charAt(0).toUpperCase() + k.slice(1)}
                  </span>
                ))}
              </div>
              <div className="flex flex-wrap gap-1 mb-1.5">
                {demo.keywords.map(kw => (
                  <span key={kw} className="text-[9px] border px-1.5 py-0.5 rounded-full" style={{
                    background: `${demo.glowColor}12`,
                    borderColor: `${demo.glowColor}30`,
                    color: demo.glowColor,
                  }}>{kw}</span>
                ))}
              </div>
              <p className="text-[10px] text-surface-400 italic">{demo.feedback}</p>
            </div>
          </div>
        )}

        {/* Bottom controls */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-surface-700/30 bg-surface-950/60">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCamOff(v => !v)}
              title="Toggle camera"
              className={`w-7 h-7 rounded-full flex items-center justify-center transition-colors ${
                camOff ? 'bg-accent-red/20 text-accent-red border border-accent-red/30' : 'bg-surface-800 text-surface-400 border border-surface-700 hover:text-white'
              }`}
            >
              {camOff ? <VideoOff size={12} /> : <Video size={12} />}
            </button>
            <div className={`w-7 h-7 rounded-full flex items-center justify-center border ${
              userSpeaking ? 'bg-accent-purple/20 text-accent-purple border-accent-purple/30' : 'bg-surface-800 text-surface-400 border-surface-700'
            }`}>
              {userSpeaking ? <Mic size={12} className="animate-pulse" /> : <MicOff size={12} />}
            </div>
            <div className="w-7 h-7 rounded-full bg-accent-red flex items-center justify-center">
              <Phone size={12} className="text-white rotate-[135deg]" />
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-surface-500">
            <Shield size={10} className="text-accent-green" />
            <span className="text-[10px]">Free · No API</span>
          </div>
          <Link
            to="/interviews"
            className="flex items-center gap-1 text-xs text-accent-cyan hover:text-white font-semibold transition-colors group"
          >
            Try Live <ChevronRight size={12} className="group-hover:translate-x-0.5 transition-transform" />
          </Link>
        </div>
      </div>

      {/* Floating badges */}
      <div className="absolute -top-3 -right-3 bg-surface-900/95 backdrop-blur-xl border border-accent-green/30 rounded-xl px-3 py-1.5 text-xs text-accent-green font-bold flex items-center gap-1.5 shadow-lg shadow-accent-green/10">
        <div className="w-2 h-2 rounded-full bg-accent-green animate-pulse" />
        Face-to-Face AI
      </div>
      <div className="absolute -bottom-3 -left-3 bg-surface-900/95 backdrop-blur-xl border border-accent-purple/30 rounded-xl px-3 py-1.5 text-xs text-accent-purple font-bold flex items-center gap-1.5 shadow-lg">
        <Star size={10} fill="currentColor" />
        STAR Scoring Engine
      </div>
    </div>
  )
}
