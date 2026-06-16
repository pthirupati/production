import { useState, useEffect, useRef, useCallback } from 'react'
import { Mic, Star, CheckCircle, Brain, Zap, Shield, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

const DEMO_SCRIPT = [
  {
    phase: 'Technical Round',
    persona: 'Aria',
    question: 'A production server is showing high load average but low CPU usage. Walk me through your diagnostic approach.',
    answer: 'I\'d start by running uptime to check load numbers, then iostat -x to check I/O wait. High load with low CPU usually points to I/O blocking — stale NFS mounts, failing disk, or a process stuck in D state. I\'d use ps aux to find D-state processes and dmesg for hardware errors.',
    scores: { situation: true, task: true, action: true, result: true },
    score: 91,
    keywords: ['iostat', 'I/O wait', 'D-state', 'dmesg', 'NFS'],
    feedback: 'Excellent systematic approach — STAR-structured and technically precise.',
  },
  {
    phase: 'Behavioral Round',
    persona: 'Nova',
    question: 'Tell me about a time you had to fix a critical production outage under pressure. What was your process?',
    answer: 'During a black Friday event, our Redis cluster went down causing 100% checkout failures. I immediately formed a war room, rolled back the recent config change, and restored service in 8 minutes. We then implemented proper sentinel failover to prevent recurrence.',
    scores: { situation: true, task: true, action: true, result: true },
    score: 88,
    keywords: ['war room', 'rollback', 'failover', 'sentinel', 'incident'],
    feedback: 'Strong STAR response with quantified impact and preventive follow-up.',
  },
  {
    phase: 'System Design',
    persona: 'Atlas',
    question: 'How would you design a highly available NFS solution for 500+ Linux servers?',
    answer: 'I\'d use a clustered NFS with Pacemaker and DRBD for HA, or leverage cloud-native solutions like AWS EFS or Azure Files. Key considerations: active-passive failover under 30s, client-side _netdev and soft mount options, monitoring with alerting on stale mounts, and autofs for on-demand mounting.',
    scores: { situation: true, task: true, action: true, result: false },
    score: 79,
    keywords: ['Pacemaker', 'DRBD', 'EFS', 'autofs', '_netdev', 'failover'],
    feedback: 'Good design — add specifics on recovery time objectives and capacity planning.',
  },
]

const BOT_AVATARS = {
  Aria:  { color: 'from-accent-cyan to-accent-blue',   initials: 'AR', ring: 'border-accent-cyan/50' },
  Nova:  { color: 'from-accent-purple to-accent-pink', initials: 'NV', ring: 'border-accent-purple/50' },
  Atlas: { color: 'from-accent-amber to-accent-green', initials: 'AT', ring: 'border-accent-amber/50' },
}

function VoiceWave({ active, color = '#06b6d4' }) {
  const bars = [3, 5, 4, 7, 6, 8, 5, 4, 6, 3, 7, 5]
  return (
    <div className="flex items-center gap-[2px] h-6">
      {bars.map((h, i) => (
        <div
          key={i}
          className="rounded-full transition-all"
          style={{
            width: 3,
            height: active ? `${h * 3}px` : '3px',
            background: color,
            opacity: active ? 0.85 : 0.3,
            animation: active ? `voice-bar 0.8s ease-in-out infinite alternate` : 'none',
            animationDelay: `${i * 0.07}s`,
          }}
        />
      ))}
    </div>
  )
}

function ScoreBar({ label, value, color, delay = 0 }) {
  const [w, setW] = useState(0)
  useEffect(() => {
    const t = setTimeout(() => setW(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-surface-400 w-14 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-surface-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${w}%`, background: color }} />
      </div>
      <span className="text-surface-300 w-6 text-right font-mono">{Math.round(w)}</span>
    </div>
  )
}

function StarIndicator({ label, present }) {
  return (
    <div className={`flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
      present
        ? 'bg-accent-green/15 border-accent-green/30 text-accent-green'
        : 'bg-surface-800 border-surface-700 text-surface-500'
    }`}>
      {present ? <CheckCircle size={9} /> : <div className="w-2 h-2 rounded-full border border-surface-500" />}
      {label}
    </div>
  )
}

// Typewriter hook
function useTypewriter(text, speed = 22, active = false) {
  const [displayed, setDisplayed] = useState('')
  useEffect(() => {
    if (!active) { setDisplayed(''); return }
    setDisplayed('')
    let i = 0
    const interval = setInterval(() => {
      i++
      setDisplayed(text.slice(0, i))
      if (i >= text.length) clearInterval(interval)
    }, speed)
    return () => clearInterval(interval)
  }, [text, speed, active])
  return displayed
}

const PHASE_DURATION = 12000 // ms per interview exchange
const STEP = { BOT_SPEAKING: 0, USER_ANSWERING: 2500, EVALUATING: 6500, SCORED: 8500 }

export default function InterviewDemoWidget() {
  const [scene, setScene] = useState(0)
  const [step, setStep] = useState(STEP.BOT_SPEAKING)
  const [hovered, setHovered] = useState(false)
  const [playing, setPlaying] = useState(true)
  const phaseRef = useRef(null)
  const stepRef = useRef(null)

  const advance = useCallback(() => {
    setScene(s => (s + 1) % DEMO_SCRIPT.length)
    setStep(STEP.BOT_SPEAKING)
  }, [])

  useEffect(() => {
    if (!playing) return
    const steps = [
      { at: STEP.USER_ANSWERING, fn: () => setStep(STEP.USER_ANSWERING) },
      { at: STEP.EVALUATING,     fn: () => setStep(STEP.EVALUATING) },
      { at: STEP.SCORED,         fn: () => setStep(STEP.SCORED) },
      { at: PHASE_DURATION,      fn: advance },
    ]
    const timers = steps.map(({ at, fn }) => setTimeout(fn, at))
    return () => timers.forEach(clearTimeout)
  }, [scene, playing, advance])

  const demo = DEMO_SCRIPT[scene]
  const avatar = BOT_AVATARS[demo.persona]
  const botSpeaking = step === STEP.BOT_SPEAKING
  const userAnswering = step === STEP.USER_ANSWERING
  const evaluating = step === STEP.EVALUATING
  const scored = step === STEP.SCORED

  const questionText = useTypewriter(demo.question, 18, botSpeaking || userAnswering || evaluating || scored)
  const answerText   = useTypewriter(demo.answer, 12, userAnswering || evaluating || scored)

  const scoreColor = demo.score >= 85 ? '#10b981' : demo.score >= 70 ? '#f59e0b' : '#ef4444'

  return (
    <div
      className="relative rounded-2xl overflow-hidden"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Glow halo */}
      <div className="absolute -inset-4 rounded-3xl bg-gradient-to-br from-accent-purple/20 via-accent-cyan/10 to-accent-pink/15 blur-2xl pointer-events-none animate-pulse-glow" />

      <div className="relative glass-card gradient-border card-3d overflow-hidden">
        {/* Header bar */}
        <div className="flex items-center justify-between px-4 py-3 bg-surface-900/80 border-b border-surface-700/50">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-accent-red/80" />
            <div className="w-2.5 h-2.5 rounded-full bg-accent-amber/80" />
            <div className="w-2.5 h-2.5 rounded-full bg-accent-green/80" />
            <span className="ml-2 text-xs text-surface-400 font-mono">FixitLab AI Interview Studio</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs">
              {DEMO_SCRIPT.map((_, i) => (
                <button
                  key={i}
                  onClick={() => { setScene(i); setStep(STEP.BOT_SPEAKING) }}
                  className={`w-2 h-2 rounded-full transition-all duration-300 ${i === scene ? 'bg-accent-cyan scale-125' : 'bg-surface-600 hover:bg-surface-400'}`}
                />
              ))}
            </div>
            <button
              onClick={() => setPlaying(p => !p)}
              className="text-xs text-surface-400 hover:text-white transition-colors px-2 py-0.5 rounded border border-surface-700 hover:border-accent-cyan/50"
            >
              {playing ? '⏸' : '▶'}
            </button>
          </div>
        </div>

        {/* Phase badge */}
        <div className="px-4 pt-3 pb-0">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border"
            style={{ background: 'rgb(139 92 246 / 0.12)', borderColor: 'rgb(139 92 246 / 0.3)', color: 'rgb(139 92 246)' }}>
            <Brain size={10} /> {demo.phase}
          </div>
        </div>

        {/* Chat area */}
        <div className="p-4 space-y-4 min-h-[260px]">
          {/* Bot message */}
          <div className={`flex gap-3 transition-all duration-500 ${botSpeaking || userAnswering || evaluating || scored ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
            <div className="shrink-0">
              <div className={`w-9 h-9 rounded-xl bg-gradient-to-br ${avatar.color} flex items-center justify-center text-white text-xs font-bold border-2 ${avatar.ring} shadow-lg`}>
                {avatar.initials}
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-semibold text-white">{demo.persona}</span>
                <span className="text-[10px] text-surface-500">AI Interviewer</span>
                {botSpeaking && (
                  <div className="flex items-center gap-1 text-[9px] text-accent-cyan bg-accent-cyan/10 px-1.5 py-0.5 rounded-full border border-accent-cyan/20">
                    <div className="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-pulse" /> Speaking
                  </div>
                )}
              </div>
              <div className="bg-surface-800/60 rounded-xl rounded-tl-sm px-3 py-2.5 text-sm text-surface-200 leading-relaxed border border-surface-700/40">
                {questionText}
                {botSpeaking && questionText.length < demo.question.length && (
                  <span className="inline-block w-0.5 h-4 bg-accent-cyan ml-0.5 animate-pulse" />
                )}
              </div>
              {botSpeaking && <VoiceWave active className="mt-2 ml-1" color="rgb(6 182 212)" />}
            </div>
          </div>

          {/* User response */}
          {(userAnswering || evaluating || scored) && (
            <div className="flex gap-3 flex-row-reverse transition-all duration-500 animate-slide-up">
              <div className="shrink-0">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent-blue/80 to-accent-purple/80 flex items-center justify-center text-white text-xs font-bold border-2 border-accent-blue/40 shadow-lg">
                  ME
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-row-reverse">
                  <span className="text-xs font-semibold text-white">You</span>
                  {userAnswering && !evaluating && (
                    <div className="flex items-center gap-1 text-[9px] text-accent-purple bg-accent-purple/10 px-1.5 py-0.5 rounded-full border border-accent-purple/20">
                      <Mic size={8} className="animate-pulse" /> Recording
                    </div>
                  )}
                </div>
                <div className="bg-surface-800/40 rounded-xl rounded-tr-sm px-3 py-2.5 text-sm text-surface-300 leading-relaxed border border-surface-700/30">
                  {answerText}
                  {userAnswering && answerText.length < demo.answer.length && (
                    <span className="inline-block w-0.5 h-4 bg-accent-purple ml-0.5 animate-pulse" />
                  )}
                </div>
                {userAnswering && (
                  <div className="mt-2 flex justify-end mr-1">
                    <VoiceWave active color="rgb(139 92 246)" />
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Evaluation in progress */}
          {evaluating && !scored && (
            <div className="flex items-center gap-2 px-3 py-2 bg-accent-amber/8 border border-accent-amber/20 rounded-xl text-xs text-accent-amber animate-slide-up">
              <div className="w-3 h-3 border-2 border-accent-amber border-t-transparent rounded-full animate-spin" />
              Analyzing STAR framework, keywords, and technical depth…
            </div>
          )}

          {/* Score card */}
          {scored && (
            <div className="glass-card p-4 border border-surface-700/50 space-y-3 animate-slide-up">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm font-semibold text-white">
                  <Zap size={14} className="text-accent-cyan" /> AI Evaluation
                </div>
                <div className="flex items-center gap-2">
                  <div
                    className="text-2xl font-black tabular-nums"
                    style={{ color: scoreColor }}
                  >
                    {demo.score}
                  </div>
                  <span className="text-surface-500 text-xs">/100</span>
                </div>
              </div>

              {/* STAR badges */}
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(demo.scores).map(([k, v]) => (
                  <StarIndicator key={k} label={k.charAt(0).toUpperCase() + k.slice(1)} present={v} />
                ))}
              </div>

              {/* Keyword hits */}
              <div className="flex flex-wrap gap-1">
                {demo.keywords.map(kw => (
                  <span key={kw} className="text-[10px] bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20 px-2 py-0.5 rounded-full">{kw}</span>
                ))}
              </div>

              {/* Score bars */}
              <div className="space-y-1.5 pt-1">
                <ScoreBar label="Depth"    value={demo.score - 3}  color="#06b6d4" delay={100} />
                <ScoreBar label="Evidence" value={demo.score - 5}  color="#8b5cf6" delay={200} />
                <ScoreBar label="STAR"     value={Object.values(demo.scores).filter(Boolean).length * 25} color="#10b981" delay={300} />
              </div>

              <p className="text-xs text-surface-400 italic border-t border-surface-700/40 pt-2">{demo.feedback}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-surface-700/30 bg-surface-900/40 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-surface-500">
            <Shield size={11} className="text-accent-green" />
            100% Free · No API keys · Browser-native AI
          </div>
          <Link
            to="/interview-hub"
            className="flex items-center gap-1 text-xs text-accent-cyan hover:text-white font-semibold transition-colors group"
          >
            Try Live <ChevronRight size={12} className="group-hover:translate-x-0.5 transition-transform" />
          </Link>
        </div>
      </div>

      {/* Floating badges */}
      <div className="absolute -top-3 -right-3 bg-surface-900/95 backdrop-blur-xl border border-accent-green/30 rounded-xl px-3 py-1.5 text-xs text-accent-green font-bold flex items-center gap-1.5 shadow-lg shadow-accent-green/10">
        <div className="w-2 h-2 rounded-full bg-accent-green animate-pulse" />
        AI Interview Live
      </div>
      <div className="absolute -bottom-3 -left-3 bg-surface-900/95 backdrop-blur-xl border border-accent-purple/30 rounded-xl px-3 py-1.5 text-xs text-accent-purple font-bold flex items-center gap-1.5 shadow-lg">
        <Star size={10} fill="currentColor" />
        STAR Scoring Engine
      </div>
    </div>
  )
}
