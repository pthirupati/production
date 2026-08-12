import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Mic2, Play } from '../../../ui/eagerIcons'

const WAVE_DELAYS = ['0s', '0.08s', '0.16s', '0.24s', '0.04s', '0.12s', '0.2s', '0.28s', '0.06s']
const STAR_SCORES = [
  { letter: 'S', width: '90%', val: 90, delay: '0.2s' },
  { letter: 'T', width: '78%', val: 78, delay: '0.32s' },
  { letter: 'A', width: '86%', val: 86, delay: '0.44s' },
  { letter: 'R', width: '82%', val: 82, delay: '0.56s' },
]

export default function InterviewShowcase() {
  const [seconds, setSeconds] = useState(18 * 60 + 42)

  useEffect(() => {
    const t = setInterval(() => setSeconds(s => s + 1), 1000)
    return () => clearInterval(t)
  }, [])

  const timer = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`

  return (
    <Link to="/mock-interviews" className="fx-interview-showcase-wrap block no-underline group" aria-label="Open AI interview studio">
      <div className="fx-interview-showcase-glow" aria-hidden="true" />
      <div className="fx-interview-showcase relative">
        <div className="absolute top-3 right-3 z-10 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-black/50 border border-white/15 text-[10px] font-semibold text-white/90 group-hover:bg-indigo-600/80 transition-colors">
          <Play size={10} fill="currentColor" stroke="none" /> Try now
        </div>
        <div className="fx-interview-showcase-header">
          <div className="fx-interview-rec">
            <span className="fx-rec-dot" />
            REC · Technical Round · Q3 of 8
          </div>
          <div className="fx-interview-timer">{timer}</div>
        </div>

        <div className="fx-interview-video">
          <span className="fx-interview-ring" aria-hidden="true" />
          <span className="fx-interview-ring fx-interview-ring-delay" aria-hidden="true" />
          <div className="fx-interview-avatar">
            <Mic2 size={32} strokeWidth={1.6} />
          </div>
          <div className="absolute top-[11px] left-[14px] text-[10px] tracking-widest text-white/45">
            AI INTERVIEWER
          </div>
          <div className="fx-wave-bars">
            {WAVE_DELAYS.map((delay, i) => (
              <span key={i} style={{ animationDelay: delay }} />
            ))}
          </div>
          <div className="fx-interview-you-pip">You · live</div>
        </div>

        <div className="fx-interview-question">
          <p>&ldquo;How would you design a rate limiter for 1M req/s across a distributed fleet?&rdquo;</p>
          <div className="fx-interview-typing">&gt; sharded token-bucket on Redis + burst cache…</div>
        </div>

        <div className="fx-star-row">
          <div className="fx-star-bars">
            {STAR_SCORES.map(({ letter, width, val, delay }) => (
              <div key={letter} className="fx-star-bar-row">
                <span className="fx-star-letter">{letter}</span>
                <div className="fx-star-track">
                  <div className="fx-star-fill" style={{ width, animationDelay: delay }} />
                </div>
                <span className="fx-star-val">{val}</span>
              </div>
            ))}
          </div>
          <div className="fx-score-ring-wrap">
            <svg width="60" height="60" viewBox="0 0 60 60" aria-hidden="true">
              <circle cx="30" cy="30" r="24" fill="none" stroke="rgba(255,255,255,.08)" strokeWidth="6" />
              <circle
                cx="30"
                cy="30"
                r="24"
                fill="none"
                stroke="#56e0b0"
                strokeWidth="6"
                strokeLinecap="round"
                strokeDasharray="151"
                transform="rotate(-90 30 30)"
                style={{ animation: 'fxRing 1.4s cubic-bezier(.2,.8,.2,1) .3s both' }}
              />
            </svg>
            <div className="fx-score-ring-label">
              <span className="fx-score-ring-val">88</span>
              <span className="fx-score-ring-sub">SCORE</span>
            </div>
          </div>
        </div>

        <div className="fx-interview-tabs">
          <span className="fx-interview-tab fx-interview-tab-active">Technical</span>
          <span className="fx-interview-tab">Behavioral</span>
          <span className="fx-interview-tab">System Design</span>
        </div>
      </div>
    </Link>
  )
}
