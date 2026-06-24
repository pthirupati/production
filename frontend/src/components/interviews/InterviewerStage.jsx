/**
 * InterviewerStage.jsx
 *
 * The AI interviewer's video-call "panel" for the split-screen interview room
 * (FIX 4). Renders a persona avatar with:
 *   - an animated speaking ring / waveform that pulses ONLY while the AI is
 *     actually speaking (driven by the TTS `speaking` prop),
 *   - an idle "listening" state while it waits for the candidate,
 *   - a live caption strip showing the AI's current/last line.
 *
 * Designed to read like a real video-interview product (Zoom / HireVue style):
 * a name plate, a status pill, and an active-speaker glow handled by the parent
 * via the `.interview-tile-active` class. 100% CSS/SVG — no media, no paid APIs.
 */

import { Volume2, Sparkles } from 'lucide-react'

// Deterministic bar heights for the idle waveform so the layout is stable.
const _BARS = [38, 64, 52, 80, 46, 70, 58, 88, 50, 66, 42, 74]

function initials(name) {
  if (!name) return 'AI'
  const parts = name.trim().split(/\s+/)
  return ((parts[0]?.[0] || '') + (parts[1]?.[0] || '')).toUpperCase() || 'AI'
}

export default function InterviewerStage({
  personaName = 'Interviewer',
  roundTitle = '',
  speaking = false,
  listening = false,
  caption = '',
  live = false,
}) {
  const status = speaking ? 'Speaking' : listening ? 'Listening' : live ? 'Connected' : 'Ready'

  return (
    <div className="interview-stage-ai">
      {/* Ambient gradient backdrop */}
      <div className="interview-stage-ai-bg" aria-hidden />

      <div className="interview-stage-ai-center">
        {/* Avatar with pulsing rings while speaking */}
        <div className={`interview-avatar-wrap ${speaking ? 'is-speaking' : ''}`}>
          <span className="interview-avatar-ring interview-avatar-ring-1" aria-hidden />
          <span className="interview-avatar-ring interview-avatar-ring-2" aria-hidden />
          <div className="interview-avatar-core">
            <span className="interview-avatar-initials">{initials(personaName)}</span>
          </div>
        </div>

        {/* Waveform — animates while speaking, flat & dim while idle */}
        <div className={`interview-waveform ${speaking ? 'is-active' : ''}`} aria-hidden>
          {_BARS.map((h, i) => (
            <span
              key={i}
              className="interview-waveform-bar"
              style={{ '--h': `${h}%`, '--i': i }}
            />
          ))}
        </div>

        <p className="interview-stage-ai-name">{personaName}</p>
        {roundTitle && <p className="interview-stage-ai-round">{roundTitle}</p>}
      </div>

      {/* Status pill (top-left) */}
      <div className={`interview-status-pill ${speaking ? 'is-speaking' : listening ? 'is-listening' : ''}`}>
        {speaking ? <Volume2 size={12} /> : <Sparkles size={12} />}
        <span>{status}</span>
      </div>

      {/* Live call badge (top-right) */}
      <div className={`interview-freevoice-badge ${live ? 'is-live' : ''}`}>
        {live ? (
          <>
            <span className="interview-live-dot-sm" aria-hidden />
            <span>Live call</span>
          </>
        ) : (
          <>
            <Volume2 size={11} />
            <span>AI voice</span>
          </>
        )}
      </div>

      {/* Live caption strip */}
      {caption && (
        <div className="interview-caption interview-caption-ai">
          <span className="interview-caption-name">{personaName}</span>
          <p className="interview-caption-text">{caption}</p>
        </div>
      )}
    </div>
  )
}
