import { useState, useEffect, useRef, useCallback } from 'react'
import { Mic, MicOff, Video, VideoOff, Phone, Star, CheckCircle, Brain, Zap, Shield, ChevronRight, Volume2 } from 'lucide-react'
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
    avatarColor: 'from-accent-cyan to-accent-blue',
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
    avatarColor: 'from-accent-purple to-accent-pink',
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
    avatarColor: 'from-accent-amber to-accent-green',
    initials: 'AT',
  },
]

const PHASE_DURATION = 13000
const STEP = { INTRO: 0, ASKING: 2000, ANSWERING: 5500, EVALUATING: 9000, SCORED: 11000 }

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
      <div className="absolute -inset-4 rounded-3xl bg-gradient-to-br from-accent-purple/20 via-accent-cyan/10 to-accent-pink/15 blur-2xl pointer-events-none animate-pulse-glow" />

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

        {/* Phase label */}
        <div className="flex items-center justify-between px-4 pt-2.5 pb-0">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-widest border bg-accent-purple/10 border-accent-purple/30 text-accent-purple">
            <Brain size={9} /> {demo.phase}
          </div>
          <div className="flex gap-1.5">
            {DEMO_SCRIPT.map((_, i) => (
              <button
                key={i}
                onClick={() => { setScene(i); setStep(STEP.INTRO) }}
                className={`w-1.5 h-1.5 rounded-full transition-all ${i === scene ? 'bg-accent-cyan scale-125' : 'bg-surface-600 hover:bg-surface-400'}`}
              />
            ))}
          </div>
        </div>

        {/* VIDEO CALL GRID */}
        <div className="grid grid-cols-2 gap-2 p-3">
          {/* AI Interviewer tile */}
          <div className={`relative rounded-xl overflow-hidden bg-surface-950 aspect-[4/3] border-2 transition-all duration-500 ${
            interviewerSpeaking ? 'border-accent-cyan shadow-lg shadow-accent-cyan/20' : 'border-surface-700/50'
          }`}>
            {/* Gradient "face" background */}
            <div className={`absolute inset-0 bg-gradient-to-br ${demo.avatarColor} opacity-20`} />
            <div className="absolute inset-0 bg-surface-950/60" />

            {/* Avatar face */}
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
              <div className={`w-14 h-14 rounded-full bg-gradient-to-br ${demo.avatarColor} flex items-center justify-center shadow-xl border-2 border-white/20`}>
                <span className="text-white text-lg font-black">{demo.initials}</span>
              </div>
              {/* Face lines — simulated video feed effect */}
              <div className="space-y-1 text-center">
                <p className="text-[11px] font-semibold text-white">{demo.persona}</p>
                <p className="text-[9px] text-surface-400">{demo.role}</p>
              </div>
            </div>

            {/* Speaking indicator + voice wave */}
            {interviewerSpeaking && (
              <div className="absolute bottom-2 left-0 right-0 flex justify-center">
                <div className="bg-surface-950/90 rounded-full px-2 py-1 flex items-center gap-1.5">
                  <Volume2 size={9} className="text-accent-cyan" />
                  <VoiceWave active color="#06b6d4" bars={8} />
                </div>
              </div>
            )}

            {/* Name tag */}
            <div className="absolute bottom-2 left-2 text-[9px] text-white/70 font-medium bg-black/40 px-1.5 py-0.5 rounded">
              {demo.persona} — AI
            </div>
          </div>

          {/* User tile */}
          <div className={`relative rounded-xl overflow-hidden bg-surface-950 aspect-[4/3] border-2 transition-all duration-500 ${
            userSpeaking ? 'border-accent-purple shadow-lg shadow-accent-purple/20' : 'border-surface-700/50'
          }`}>
            {camOff ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-surface-900">
                <VideoOff size={24} className="text-surface-600" />
                <p className="text-[10px] text-surface-500">Camera off</p>
              </div>
            ) : (
              <>
                <div className="absolute inset-0 bg-gradient-to-br from-accent-blue/20 to-accent-purple/20" />
                <div className="absolute inset-0 bg-surface-950/50" />
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
                  <div className="w-14 h-14 rounded-full bg-gradient-to-br from-accent-blue/80 to-accent-purple/80 flex items-center justify-center shadow-xl border-2 border-white/20">
                    <span className="text-white text-lg font-black">ME</span>
                  </div>
                  <p className="text-[10px] text-surface-400">Candidate</p>
                </div>
              </>
            )}

            {/* Mic + speaking indicator */}
            {userSpeaking && (
              <div className="absolute bottom-2 left-0 right-0 flex justify-center">
                <div className="bg-surface-950/90 rounded-full px-2 py-1 flex items-center gap-1.5">
                  <Mic size={9} className="text-accent-purple animate-pulse" />
                  <VoiceWave active color="#8b5cf6" bars={8} />
                </div>
              </div>
            )}

            <div className="absolute bottom-2 left-2 text-[9px] text-white/70 font-medium bg-black/40 px-1.5 py-0.5 rounded">
              You
            </div>
          </div>
        </div>

        {/* Question / Answer transcript */}
        <div className="mx-3 mb-2 bg-surface-950/60 rounded-xl border border-surface-700/40 px-3 py-2.5 min-h-[56px]">
          {step === STEP.INTRO && (
            <p className="text-[11px] text-surface-500 italic text-center pt-1">Connecting to interview session…</p>
          )}
          {interviewerSpeaking && (
            <div>
              <p className="text-[9px] text-accent-cyan font-bold uppercase tracking-wider mb-1 flex items-center gap-1">
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

        {/* Evaluation / Score overlay */}
        {evaluating && !scored && (
          <div className="mx-3 mb-2 px-3 py-2 bg-accent-amber/8 border border-accent-amber/20 rounded-xl flex items-center gap-2 text-xs text-accent-amber">
            <div className="w-3 h-3 border-2 border-accent-amber border-t-transparent rounded-full animate-spin shrink-0" />
            Analyzing STAR framework, keywords, technical depth…
          </div>
        )}

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
                  <span key={kw} className="text-[9px] bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20 px-1.5 py-0.5 rounded-full">{kw}</span>
                ))}
              </div>
              <p className="text-[10px] text-surface-400 italic">{demo.feedback}</p>
            </div>
          </div>
        )}

        {/* Bottom controls bar */}
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
        Video Interview Live
      </div>
      <div className="absolute -bottom-3 -left-3 bg-surface-900/95 backdrop-blur-xl border border-accent-purple/30 rounded-xl px-3 py-1.5 text-xs text-accent-purple font-bold flex items-center gap-1.5 shadow-lg">
        <Star size={10} fill="currentColor" />
        STAR Scoring Engine
      </div>
    </div>
  )
}
