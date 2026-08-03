/**
 * P2.R2 — client-side backchannel choreography (mirrors realism/backchannel.py).
 * No API calls — uses interim STT duration only.
 */

const CUES = ['mm-hmm', 'okay', 'right', 'sure', 'got it', 'uh-huh', 'yeah', 'I see']
export const BACKCHANNEL_MIN_SPEECH_MS = 4000
export const BACKCHANNEL_THROTTLE_MS = 15000

/**
 * @param {{ lastCue?: string, lastFiredAt?: number, speechStartedAt?: number }} state
 * @param {{ now?: number, speechActive: boolean, speechStartedAt?: number }} opts
 * @returns {{ cue: string|null, state: object }}
 */
export function pickBackchannel(state = {}, { now = Date.now(), speechActive, speechStartedAt } = {}) {
  const next = {
    lastCue: state.lastCue || '',
    lastFiredAt: state.lastFiredAt || 0,
    speechStartedAt: speechStartedAt ?? state.speechStartedAt ?? 0,
  }

  if (!speechActive) {
    next.speechStartedAt = 0
    return { cue: null, state: next }
  }

  if (!next.speechStartedAt) {
    next.speechStartedAt = now
    return { cue: null, state: next }
  }

  if (now - next.speechStartedAt < BACKCHANNEL_MIN_SPEECH_MS) {
    return { cue: null, state: next }
  }

  if (next.lastFiredAt && now - next.lastFiredAt < BACKCHANNEL_THROTTLE_MS) {
    return { cue: null, state: next }
  }

  const pool = CUES.filter((c) => c !== next.lastCue)
  const cue = (pool.length ? pool : CUES)[Math.floor(Math.random() * (pool.length || CUES.length))]
  next.lastCue = cue
  next.lastFiredAt = now
  return { cue, state: next }
}
