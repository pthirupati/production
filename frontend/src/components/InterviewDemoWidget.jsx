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

/* ── Voice wave bars ── */
const CANDIDATE_PORTRAIT =
  'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=640&h=480&q=80'
const AI_BOT_AVATAR =
  'https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=400&h=400&q=80'

/* ── AI interviewer tile — distinct from human video feed ── */
function AIBotVideoTile({ speaking, label, sublabel, accentColor }) {
  return (
    <div
      className="relative rounded-xl overflow-hidden aspect-[4/3] border-2 transition-all duration-500 bg-surface-950"
      style={{
        borderColor: speaking ? accentColor : 'rgba(71,85,105,0.45)',
        boxShadow: speaking ? `0 0 32px ${accentColor}40` : undefined,
      }}
    >
      <div
        className="absolute inset-0 transition-opacity duration-700"
        style={{
          background: `radial-gradient(ellipse at 50% 35%, ${accentColor}28 0%, rgb(15 23 42) 55%, rgb(4 8 26) 100%)`,
        }}
      />
      <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImciIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTTAgNDBINDAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjAzKSIvPjwvcGF0dGVybj48L2RlZnM+PHJlY3Qgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIgZmlsbD0idXJsKCNnKSIvPjwvc3ZnPg==')] opacity-40 pointer-events-none" />
      {[1, 2, 3].map((ring) => (
        <div
          key={ring}
          className="absolute left-1/2 top-[42%] -translate-x-1/2 -translate-y-1/2 rounded-full border pointer-events-none"
          style={{
            width: `${48 + ring * 28}%`,
            height: `${48 + ring * 28}%`,
            borderColor: `${accentColor}${speaking ? '35' : '18'}`,
            animation: speaking ? `ai-ring-pulse ${1.8 + ring * 0.4}s ease-in-out infinite` : 'none',
            animationDelay: `${ring * 0.25}s`,
          }}
        />
      ))}
      <div className="absolute inset-0 flex flex-col items-center justify-center pt-2">
        <div
          className={`relative transition-transform duration-[900ms] ease-out ${speaking ? 'scale-105' : 'scale-100'}`}
        >
          <div
            className="absolute -inset-3 rounded-full blur-xl opacity-60 pointer-events-none"
            style={{ background: accentColor }}
          />
          <div className="relative w-[72px] h-[72px] sm:w-[84px] sm:h-[84px] rounded-full overflow-hidden ring-2 ring-white/20 shadow-2xl">
            <img src={AI_BOT_AVATAR} alt="AI interviewer avatar" className="w-full h-full object-cover" loading="lazy" />
            <div
              className="absolute inset-0 mix-blend-color pointer-events-none"
              style={{ background: `${accentColor}55` }}
            />
          </div>
          <div className="absolute -bottom-1 -right-1 w-7 h-7 rounded-full bg-surface-950 border border-white/20 flex items-center justify-center shadow-lg">
            <Brain size={14} style={{ color: accentColor }} />
          </div>
        </div>
        {speaking && (
          <div className="mt-4 flex items-center gap-1.5 px-3 py-1 rounded-full bg-black/45 backdrop-blur-sm border border-white/10">
            <Volume2 size={10} style={{ color: accentColor }} />
            <VoiceWave active color={accentColor} bars={5} />
          </div>
        )}
      </div>
      <div className="absolute top-2 left-2 flex items-center gap-1 px-2 py-0.5 rounded-md bg-black/55 backdrop-blur-md border border-cyan-500/30 text-[9px] font-semibold text-cyan-300">
        <Brain size={9} />
        <span>AI Interviewer</span>
      </div>
      <div className="absolute top-2 right-2 text-[8px] font-medium px-1.5 py-0.5 rounded bg-black/45 text-cyan-300/90 backdrop-blur-sm">
        LIVE AI
      </div>
      <div className="absolute bottom-2 left-2 right-2">
        <p className="text-[10px] font-semibold text-white truncate drop-shadow">{label}</p>
        {sublabel && <p className="text-[8px] text-white/60 truncate">{sublabel}</p>}
      </div>
      <div
        className="absolute inset-0 opacity-[0.05] pointer-events-none mix-blend-overlay interview-scanlines"
        aria-hidden="true"
      />
    </div>
  )
}
/* ── Human video-call participant tile ── */
function VideoParticipant({ src, alt, speaking, label, sublabel, accentColor, badge }) {
  return (
    <div
      className="relative rounded-xl overflow-hidden aspect-[4/3] border-2 transition-all duration-500 bg-surface-950"
      style={{
        borderColor: speaking ? accentColor : 'rgba(71,85,105,0.45)',
        boxShadow: speaking ? `0 0 28px ${accentColor}35` : undefined,
      }}
    >
      <img
        src={src}
        alt={alt}
        className={`absolute inset-0 w-full h-full object-cover transition-transform duration-[1200ms] ease-out ${
          speaking ? 'scale-[1.08] interview-speaking-drift' : 'scale-100'
        }`}
        loading="lazy"
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-black/25 pointer-events-none" />
      <div
        className="absolute inset-0 opacity-[0.06] pointer-events-none mix-blend-overlay"
        style={{
          backgroundImage:
            'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.9) 2px, rgba(255,255,255,0.9) 3px)',
        }}
      />
      {badge && (
        <div className="absolute top-2 left-2 flex items-center gap-1 px-2 py-0.5 rounded-md bg-black/55 backdrop-blur-md border border-white/10 text-[9px] font-semibold text-white">
          {badge}
        </div>
      )}
      <div className="absolute bottom-2 left-2 right-2 flex items-end justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold text-white truncate drop-shadow">{label}</p>
          {sublabel && <p className="text-[8px] text-white/60 truncate">{sublabel}</p>}
        </div>
        {speaking && (
          <div className="shrink-0 bg-black/50 rounded-full px-2 py-1 flex items-center gap-1 backdrop-blur-sm">
            <Volume2 size={9} style={{ color: accentColor }} />
            <VoiceWave active color={accentColor} bars={6} />
          </div>
        )}
      </div>
      <div className="absolute top-2 right-2 text-[8px] font-medium px-1.5 py-0.5 rounded bg-black/45 text-white/80 backdrop-blur-sm">
        HD
      </div>
    </div>
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
          <AIBotVideoTile
            speaking={interviewerSpeaking}
            label={demo.persona}
            sublabel={demo.role}
            accentColor={demo.glowColor}
          />
          {camOff ? (
            <div className="relative rounded-xl overflow-hidden aspect-[4/3] border-2 border-surface-700/50 bg-surface-900 flex flex-col items-center justify-center gap-2">
              <VideoOff size={24} className="text-surface-600" />
              <p className="text-[10px] text-surface-500">Camera off</p>
            </div>
          ) : (
            <VideoParticipant
              src={CANDIDATE_PORTRAIT}
              alt="Candidate on video call"
              speaking={userSpeaking}
              label="You"
              sublabel="Candidate"
              accentColor="#8b5cf6"
            />
          )}
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
