/**
 * useInterviewVoice.js
 *
 * Unified voice hook for FixitLab interview room.
 *
 * TTS priority:  ElevenLabs/Polly (server) → Browser SpeechSynthesis (fallback)
 * STT priority:  Whisper API (server, chunked) → Browser SpeechRecognition (fallback)
 *
 * Both paths are transparent to callers — the same speak() / listen() API
 * works regardless of which backend is active.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { interviewsApi } from '../api/interviews'

// ---------------------------------------------------------------------------
// Browser voice picker (used for browser TTS fallback)
//
// NATURALNESS (FIX 2): browsers expose a mix of voices of wildly different
// quality on the same OS — the old robotic eSpeak/"Microsoft David Desktop"
// engines sit in the same list as modern on-device NEURAL voices (e.g.
// "Microsoft Aria Online (Natural)", Google's "en-US" WaveNet voices, Apple's
// "Samantha"/"Ava"/Siri voices). We score the list so we always reach for the
// most human-sounding LOCAL/neural voice for the right accent instead of
// whatever the OS picked as #0 (often the worst one). This is the single
// biggest free win for sounding less robotic.
//
// NOTE: truly human-grade TTS needs a paid/local-neural model (ElevenLabs,
// Azure Neural, Piper, etc.) — that is explicitly out of scope / forbidden
// here. This gets as close as free in-browser voices allow.
// ---------------------------------------------------------------------------

// Names that signal a high-quality neural/natural voice, in rough rank order.
// These substrings appear in the voiceURI/name across Chrome, Edge, Safari.
const _NATURAL_NAME_HINTS = [
  'natural', 'neural', 'wavenet', 'premium', 'enhanced', 'siri',
  // Modern Edge/Windows neural voices.
  'aria', 'jenny', 'guy', 'libby', 'ryan', 'sonia', 'natasha', 'clara',
  'neerja', 'prabhat',
  // Apple's better voices (macOS/iOS) — far smoother than the legacy "Fred".
  'ava', 'samantha', 'allison', 'zoe', 'evan', 'nathan', 'serena', 'daniel',
  // Google's voices (Chrome/Android) are decent and usually contain "Google".
  'google',
]

// Names that are notably ROBOTIC — actively de-prioritise these even if the OS
// lists them first or they match the locale.
const _ROBOTIC_NAME_HINTS = [
  'espeak', 'pico', 'compact', 'david', 'mark', 'zira', 'hazel', 'fred',
  'albert', 'bad news', 'good news', 'bahh', 'bells', 'boing', 'bubbles',
  'cellos', 'deranged', 'eddy', 'flo', 'grandma', 'grandpa', 'jester',
  'organ', 'reed', 'rocko', 'sandy', 'shelley', 'superstar', 'trinoids',
  'whisper', 'wobble', 'zarvox', 'junior', 'kathy', 'ralph', 'novelty',
]

function _voiceNaturalnessScore(voice, locale) {
  if (!voice) return -Infinity
  const name = (voice.name || '').toLowerCase()
  const uri = (voice.voiceURI || '').toLowerCase()
  const hay = `${name} ${uri}`
  let score = 0

  // Strongly reward known-natural markers (earlier in the list = higher weight).
  _NATURAL_NAME_HINTS.forEach((hint, i) => {
    if (hay.includes(hint)) score += 40 - i
  })
  // "(Natural)" / "Neural" in the display name is the clearest signal of all.
  if (/\bnatural\b|\bneural\b/.test(hay)) score += 60

  // Penalise the legacy robotic engines hard.
  _ROBOTIC_NAME_HINTS.forEach((hint) => {
    if (hay.includes(hint)) score -= 50
  })
  // eSpeak "compact"/"desktop" variants are the worst.
  if (hay.includes('desktop') || hay.includes('compact')) score -= 25

  // Locale fit: exact match best, language-family match good, else mild penalty.
  const base = (locale || 'en-US').split('-')[0]
  if (voice.lang === locale) score += 30
  else if (voice.lang?.startsWith(base)) score += 18
  else score -= 20 // wrong language entirely — avoid unless nothing else.

  // localService voices play instantly & offline; "online" neural voices sound
  // best but can lag. Give a small nudge to local so the convo stays snappy,
  // but not enough to override a clearly-natural online voice.
  if (voice.localService) score += 6

  // Prefer English overall for these interviews.
  if (voice.lang?.startsWith('en')) score += 8

  return score
}

// Rank ALL voices for a locale, best-first. Exposed so the in-room voice picker
// can present the most natural options at the top of the dropdown.
function rankVoicesByNaturalness(voices, locale) {
  return [...(voices || [])]
    .map((v) => ({ v, s: _voiceNaturalnessScore(v, locale) }))
    .sort((a, b) => b.s - a.s)
    .map((x) => x.v)
}

function pickBrowserVoice(hint, locale, preferredURI) {
  if (!window.speechSynthesis) return null
  const voices = window.speechSynthesis.getVoices()
  if (!voices.length) return null
  // An explicit in-room user choice always wins — the candidate is in control.
  if (preferredURI) {
    const chosen = voices.find(v => v.voiceURI === preferredURI)
    if (chosen) return chosen
  }
  // An admin/persona hint (e.g. "Neerja", "Samantha") is a strong preference,
  // but only if that named voice exists; otherwise fall through to ranking.
  if (hint) {
    const match = voices.find(v => v.name.toLowerCase().includes(hint.toLowerCase()))
    if (match) return match
  }
  // No explicit choice → pick the most natural-sounding voice for this accent.
  const ranked = rankVoicesByNaturalness(voices, locale)
  return ranked[0] || voices[0]
}

// ---------------------------------------------------------------------------
// Sentence segmentation + natural pauses (FIX 2)
//
// Speaking a long paragraph as ONE utterance is what makes Web Speech sound
// monotone — there's no breath, no beat between thoughts. We split the reply
// into sentence-ish chunks and speak them as a queue with a short, slightly
// randomised gap between them. The result is a more conversational cadence
// (a tiny "thinking" beat after a question mark, a shorter beat after a comma
// clause) without any paid API.
// ---------------------------------------------------------------------------

function segmentForSpeech(text) {
  const clean = (text || '').replace(/\s+/g, ' ').trim()
  if (!clean) return []
  // Split on sentence terminators while KEEPING the punctuation, then also
  // break very long comma-spliced clauses so we still get a breath.
  const rough = clean.match(/[^.!?]+[.!?]+(?:["')\]]+)?|\S[^.!?]*$/g) || [clean]
  const out = []
  for (const seg of rough) {
    const s = seg.trim()
    if (!s) continue
    if (s.length <= 140) {
      out.push(s)
    } else {
      // Long sentence — break on a comma/semicolon/dash boundary near halves so
      // no single utterance runs on robotically.
      let buf = ''
      for (const part of s.split(/(?<=[,;:—-])\s+/)) {
        if ((buf + ' ' + part).trim().length > 140 && buf) {
          out.push(buf.trim())
          buf = part
        } else {
          buf = (buf ? buf + ' ' : '') + part
        }
      }
      if (buf.trim()) out.push(buf.trim())
    }
  }
  return out
}

// Pause (ms) AFTER a segment, derived from its trailing punctuation so the
// cadence feels human: a real beat after a question, a clear stop after a
// period, a light lilt after a comma.
function pauseAfter(segment) {
  const last = segment.trim().slice(-1)
  if (last === '?') return 340
  if (last === '!') return 280
  if (last === '.') return 240
  if (last === ',' || last === ';' || last === ':') return 150
  return 200
}

// ---------------------------------------------------------------------------
// "Still thinking" detection (WS1)
//
// People pause mid-thought right after a connector or filler word ("and…",
// "so…", "because…", "which means…"). Auto-submitting there cuts them off. If
// the captured utterance currently TRAILS OFF on one of these, treat the
// speaker as not-yet-done and extend the trailing-silence window.
// ---------------------------------------------------------------------------
const _CONNECTOR_WORDS = new Set([
  'and', 'so', 'um', 'uh', 'er', 'erm', 'hmm', 'like', 'because', 'cause',
  "'cause", 'then', 'but', 'or', 'with', 'to', 'the', 'a', 'of', 'for', 'that',
  'which', 'who', 'where', 'when', 'while', 'also', 'plus', 'basically',
  'actually', 'well', 'okay', 'right', 'means', 'is', 'are', 'was', 'were',
  'in', 'on', 'at', 'by', 'as', 'if', 'i', "i'm", "i'd", "it's", 'its',
])
// Two-word tails that clearly leave a thought open.
const _CONNECTOR_PHRASES = [
  'which means', 'so that', 'such as', 'as well', 'kind of', 'sort of',
  'i think', 'i mean', 'you know', 'for example', 'let me', 'going to',
  'want to', 'need to', 'trying to', 'in order', 'depends on',
]

function endsOnConnector(text) {
  const clean = (text || '').toLowerCase().replace(/[)\]"']+$/, '').trim()
  if (!clean) return false
  // If it ends on sentence-final punctuation, the thought is closed.
  if (/[.!?]$/.test(clean)) return false
  // Strip a trailing comma/dash (a clause break) before inspecting the word.
  const tail = clean.replace(/[,;:—-]+$/, '').trim()
  if (!tail) return false
  const words = tail.split(/\s+/)
  const lastWord = words[words.length - 1].replace(/[^a-z']/g, '')
  if (_CONNECTOR_WORDS.has(lastWord)) return true
  const lastTwo = words.slice(-2).join(' ').replace(/[^a-z' ]/g, '')
  return _CONNECTOR_PHRASES.includes(lastTwo)
}

import { userScopedKey } from '../utils/userScopedStorage'
import { useAuthStore } from '../store/authStore'

const VOICE_STORAGE_BASE = 'fixitlab.interview.voiceURI'

function voiceStorageKey() {
  const userId = useAuthStore.getState().user?.id
  return userScopedKey(VOICE_STORAGE_BASE, userId)
}

function loadPersistedVoiceURI() {
  try {
    return window.localStorage.getItem(voiceStorageKey()) || ''
  } catch {
    return ''
  }
}

function persistVoiceURI(uri) {
  try {
    const key = voiceStorageKey()
    if (uri) window.localStorage.setItem(key, uri)
    else window.localStorage.removeItem(key)
  } catch { /* storage unavailable — non-fatal */ }
}

/** Offline capability probe for preflight (no paid APIs). */
export function detectSpeechCapabilities() {
  if (typeof window === 'undefined') {
    return { stt: false, tts: false, any: false }
  }
  const stt = !!(window.SpeechRecognition || window.webkitSpeechRecognition)
  const tts = !!window.speechSynthesis
  return { stt, tts, any: stt || tts }
}

// ---------------------------------------------------------------------------
// Audio playback helper (for server TTS base64 audio)
// ---------------------------------------------------------------------------

let _currentAudio = null

async function playBase64Audio(base64, mime = 'audio/mpeg') {
  if (_currentAudio) {
    _currentAudio.pause()
    _currentAudio = null
  }
  const blob = await fetch(`data:${mime};base64,${base64}`).then(r => r.blob())
  const url = URL.createObjectURL(blob)
  const audio = new Audio(url)
  _currentAudio = audio
  return new Promise((resolve, reject) => {
    let done = false
    const finish = () => { if (done) return; done = true; URL.revokeObjectURL(url); resolve() }
    audio.onended = finish
    // A barge-in / cancelSpeech pauses the audio — treat that as "finished" so
    // the awaited speak() promise resolves instead of hanging mid-utterance.
    audio.onpause = finish
    audio.onerror = (e) => { if (done) return; done = true; URL.revokeObjectURL(url); reject(e) }
    audio.play().catch(reject)
  })
}

function stopAudio({ cancelSynth = true } = {}) {
  if (_currentAudio) {
    _currentAudio.pause()
    _currentAudio = null
  }
  // Never cancel the synth while a Join→startRound hold is keeping Chrome's
  // user-gesture unlock alive — that is the #1 cause of post-join silence.
  if (cancelSynth && window.speechSynthesis && !_speechHoldActive) {
    window.speechSynthesis.cancel()
  }
}

// Keep one AudioContext alive — creating+closing on every unlock can leave
// Chrome/Safari without a primed audio graph after an await (startRound).
let _unlockAudioCtx = null
let _primeCooldownUntil = 0
// True while speak() owns the synthesis queue — skip silent primes that steal
// the queue / cancel race with the real interviewer line.
let _speakInFlight = false
// Set during a real user gesture (Test / Join / Hear interviewer). Survives
// awaits so post-startRound TTS does not call cancel() and drop the unlock.
let _speechGestureUnlocked = false
// Keep a near-silent utterance queued across long awaits (startRound API).
let _speechHoldActive = false
let _speechHoldTimer = null

/**
 * Hold Chrome's speech unlock across an await that leaves the user-gesture
 * stack (e.g. interviewsApi.startRound). Call from Join / Begin click, then
 * releaseSpeechHold() immediately before the real interviewer speak().
 */
export function holdSpeechUnlock() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  _speechGestureUnlocked = true
  _speechHoldActive = true
  const tick = () => {
    if (!_speechHoldActive || !window.speechSynthesis) return
    try {
      if (window.speechSynthesis.paused) window.speechSynthesis.resume()
      // Never inject a prime while speak() owns the queue — that races the
      // gesture warm-up / interviewer line and is a common silence cause.
      if (_speakInFlight || window.speechSynthesis.speaking || window.speechSynthesis.pending) {
        _speechHoldTimer = setTimeout(tick, 1800)
        return
      }
      // Chrome ignores volume=0 primes for autoplay unlock — use a barely
      // audible tick so the gesture grant survives the startRound() await.
      const u = new SpeechSynthesisUtterance('.')
      u.volume = 0.02
      u.rate = 2
      u.pitch = 1
      window.speechSynthesis.speak(u)
    } catch { /* non-fatal */ }
    _speechHoldTimer = setTimeout(tick, 1800)
  }
  if (_speechHoldTimer) clearTimeout(_speechHoldTimer)
  tick()
}

export function releaseSpeechHold() {
  _speechHoldActive = false
  if (_speechHoldTimer) {
    clearTimeout(_speechHoldTimer)
    _speechHoldTimer = null
  }
}

function ensureAudioGraph() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (!Ctx) return
    if (!_unlockAudioCtx || _unlockAudioCtx.state === 'closed') {
      _unlockAudioCtx = new Ctx()
    }
    if (_unlockAudioCtx.state === 'suspended') {
      _unlockAudioCtx.resume().catch(() => {})
    }
    // Silent tick keeps the graph "used" under autoplay policy.
    const osc = _unlockAudioCtx.createOscillator()
    const gain = _unlockAudioCtx.createGain()
    gain.gain.value = 0.0001
    osc.connect(gain)
    gain.connect(_unlockAudioCtx.destination)
    osc.start()
    osc.stop(_unlockAudioCtx.currentTime + 0.02)
  } catch { /* non-fatal */ }
}

/**
 * Chrome/Safari often start with speechSynthesis paused until a user gesture.
 * Call on Join / Begin / Test (during the gesture). Prefer this over resume-only
 * so the AudioContext unlock survives the startRound() await.
 *
 * Soft mode (during speak): resume + audio graph only — never enqueue a silent
 * SpeechSynthesis utterance that would race with the real line.
 */
export function unlockSpeech({ soft = false } = {}) {
  if (typeof window === 'undefined') return
  try {
    if (window.speechSynthesis?.paused) window.speechSynthesis.resume()
  } catch { /* non-fatal */ }
  ensureAudioGraph()
  if (!soft) _speechGestureUnlocked = true
  if (soft || _speakInFlight) return
  try {
    if (window.speechSynthesis) {
      // Avoid stacking silent primes — that fills Chrome's queue and starves
      // the real interviewer utterance.
      const now = Date.now()
      if (now < _primeCooldownUntil) return
      _primeCooldownUntil = now + 800
      // Non-zero volume required — Chrome does not treat volume=0 as unlock.
      const u = new SpeechSynthesisUtterance('.')
      u.volume = 0.02
      u.rate = 2
      u.pitch = 1
      window.speechSynthesis.speak(u)
    }
  } catch { /* non-fatal */ }
}

/** Resume TTS that Chrome paused while the tab was backgrounded / after awaits. */
export function resumeSpeechSynthesis() {
  if (typeof window === 'undefined') return
  try {
    if (window.speechSynthesis?.paused) window.speechSynthesis.resume()
  } catch { /* non-fatal */ }
  try {
    if (_unlockAudioCtx?.state === 'suspended') {
      _unlockAudioCtx.resume().catch(() => {})
    }
  } catch { /* non-fatal */ }
}

async function waitForBrowserVoices(maxMs = 2400) {
  if (!window.speechSynthesis) return
  const start = Date.now()
  while (Date.now() - start < maxMs) {
    if (window.speechSynthesis.getVoices().length) return
    await new Promise((r) => setTimeout(r, 80))
  }
}

function speakBrowserUtterance(seg, { voice, locale, rate, pitch }) {
  return new Promise((resolve) => {
    let settled = false
    let started = false
    const done = () => {
      if (settled) return
      settled = true
      clearTimeout(stuckTimer)
      clearInterval(speakingPoll)
      if (!started && window.speechSynthesis && (window.speechSynthesis.speaking || window.speechSynthesis.pending)) {
        started = true
      }
      resolve(started)
    }
    const u = new SpeechSynthesisUtterance(seg)
    u.lang = (voice && voice.lang) || locale || 'en-US'
    u.rate = rate
    u.pitch = pitch
    u.volume = 1
    if (voice) u.voice = voice
    u.onstart = () => { started = true }
    u.onend = done
    u.onerror = () => { started = started || !!(window.speechSynthesis?.speaking || window.speechSynthesis?.pending); done() }
    const speakingPoll = setInterval(() => {
      if (window.speechSynthesis?.speaking || window.speechSynthesis?.pending) started = true
    }, 80)
    const stuckMs = Math.min(20000, Math.max(2500, 1200 + seg.length * 65))
    const stuckTimer = setTimeout(() => {
      if (!started && window.speechSynthesis?.paused) {
        try { window.speechSynthesis.resume() } catch { /* */ }
        try { window.speechSynthesis.speak(u) } catch { done() }
        return
      }
      if (window.speechSynthesis?.speaking || window.speechSynthesis?.pending) {
        started = true
      }
      done()
    }, stuckMs)
    try {
      window.speechSynthesis.resume?.()
      window.speechSynthesis.speak(u)
    } catch {
      done()
    }
  })
}

// ---------------------------------------------------------------------------
// Server TTS call
// ---------------------------------------------------------------------------

async function serverSpeak(text, voiceCode) {
  const res = await fetch('/api/interviews/tts/synthesize/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify({ text, voice_code: voiceCode }),
  })
  if (!res.ok) throw new Error('TTS server error')
  return res.json()
}

function getCsrfToken() {
  return document.cookie
    .split('; ')
    .find(r => r.startsWith('csrftoken='))
    ?.split('=')[1] || ''
}

// ---------------------------------------------------------------------------
// MediaRecorder-based audio capture (for Whisper STT)
// ---------------------------------------------------------------------------

class AudioRecorder {
  constructor() {
    this.mediaRecorder = null
    this.chunks = []
    this.stream = null
  }

  async start(stream) {
    this.stream = stream
    this.chunks = []

    // Prefer webm/opus for best compression + quality
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : 'audio/ogg'

    this.mimeType = mimeType.split(';')[0]
    this.mediaRecorder = new MediaRecorder(stream, { mimeType })
    this.mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) this.chunks.push(e.data)
    }
    this.mediaRecorder.start()
  }

  stop() {
    return new Promise((resolve) => {
      if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
        resolve(null)
        return
      }
      this.mediaRecorder.onstop = () => {
        const blob = new Blob(this.chunks, { type: this.mimeType })
        this.chunks = []
        resolve({ blob, mimeType: this.mimeType })
      }
      this.mediaRecorder.stop()
    })
  }
}

// ---------------------------------------------------------------------------
// Server STT (Whisper)
// ---------------------------------------------------------------------------

async function serverTranscribe(blob, mimeType, prompt = '') {
  const form = new FormData()
  form.append('audio_blob', blob, `recording.${mimeType.split('/')[1]}`)
  form.append('mime_type', mimeType)
  if (prompt) form.append('prompt', prompt)

  const res = await fetch('/api/interviews/stt/transcribe/', {
    method: 'POST',
    headers: { 'X-CSRFToken': getCsrfToken() },
    body: form,
  })
  if (!res.ok) throw new Error('STT server error')
  return res.json()
}

// ---------------------------------------------------------------------------
// Main hook
// ---------------------------------------------------------------------------

export function useInterviewVoice() {
  const [config, setConfig] = useState({
    stt_provider: 'browser',
    tts_provider: 'browser',
    voices: [],
    default_voice_code: 'US_F_ZIRA',
    uses_paid_apis: false,
    uses_server_stt: false,
    uses_server_tts: false,
  })
  const configRef = useRef(config)
  configRef.current = config
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [interimTranscript, setInterimTranscript] = useState('')
  // Live list of browser TTS voices for the in-room voice switcher.
  const [browserVoices, setBrowserVoices] = useState([])
  // User-selected voiceURI (persisted). '' = use the profile/admin default.
  const [selectedVoiceURI, setSelectedVoiceURI] = useState(loadPersistedVoiceURI)

  const audioRecorder = useRef(new AudioRecorder())
  // Active browser SpeechRecognition instance (so stopListening can finalize it).
  const recognizerRef = useRef(null)
  // Monotonic token: bumped on every cancelSpeech() so an in-flight segmented
  // utterance queue knows to abort mid-paragraph (barge-in / next turn).
  const speakTokenRef = useRef(0)
  // Pending inter-sentence pause timer, so cancelSpeech can clear it instantly.
  const speakPauseTimerRef = useRef(null)
  // Keep the latest selection in a ref so speak() always reads the current
  // value without needing to be re-created (and without stale closures).
  const selectedVoiceRef = useRef(selectedVoiceURI)
  useEffect(() => { selectedVoiceRef.current = selectedVoiceURI }, [selectedVoiceURI])

  // Load voice + capability config from server
  useEffect(() => {
    Promise.all([
      interviewsApi.getVoiceConfig().catch(() => ({})),
      fetch('/api/interviews/tts/config/').then(r => r.json()).catch(() => ({})),
      fetch('/api/interviews/stt/config/').then(r => r.json()).catch(() => ({})),
    ]).then(([voiceConfig, ttsConfig, sttConfig]) => {
      setConfig(prev => ({
        ...prev,
        ...voiceConfig,
        ...ttsConfig,
        ...sttConfig,
      }))
    })

    // SpeechSynthesis populates voices asynchronously; refresh on the event and
    // also poll once shortly after mount (some browsers never fire the event).
    if (window.speechSynthesis) {
      const refresh = () => {
        const v = window.speechSynthesis.getVoices() || []
        if (v.length) setBrowserVoices(v)
      }
      window.speechSynthesis.onvoiceschanged = refresh
      refresh()
      const timers = [400, 1200, 2800].map((ms) => setTimeout(refresh, ms))
      return () => { timers.forEach(clearTimeout) }
    }
  }, [])

  const selectVoice = useCallback((voiceURI) => {
    setSelectedVoiceURI(voiceURI || '')
    persistVoiceURI(voiceURI || '')
  }, [])

  const resolveVoiceProfile = useCallback((voiceCode) => {
    const cfg = configRef.current
    const code = voiceCode || cfg.default_voice_code
    return (
      cfg.voices?.find(v => v.code === code) ||
      cfg.voices?.[0] || {
        code: 'US_F_ZIRA',
        locale: 'en-US',
        browser_voice_hint: '',
        pitch: 1,
        rate: 0.95,
      }
    )
  }, [])

  // ------------------------------------------------------------------
  // speak() — server TTS with browser fallback
  // ------------------------------------------------------------------
  const speak = useCallback(async (text, voiceCode, speechOverrides = {}) => {
    if (!text) return { spoken: false }
    setIsSpeaking(true)
    _speakInFlight = true
    let spoken = false

    try {
      // Soft unlock only — a silent priming utterance here races with the real
      // line and is a common cause of "Voice unavailable" after Join.
      unlockSpeech({ soft: true })
      resumeSpeechSynthesis()

      // Optional server TTS (paid providers). Fully guarded — any failure here
      // must NEVER throw out of speak() or the hands-free loop stalls silently.
      // FixitLab runs free by default (no keys → uses_server_tts is false), so
      // this branch is skipped and we always use free browser SpeechSynthesis.
      if (configRef.current.uses_server_tts) {
        try {
          const profile = resolveVoiceProfile(voiceCode)
          const result = await serverSpeak(text, profile.code).catch(() => null)
          if (result?.audio_b64) {
            await playBase64Audio(result.audio_b64, 'audio/mpeg')
            return { spoken: true }
          }
        } catch { /* fall through to free browser TTS */ }
      }

      // Browser SpeechSynthesis fallback — segmented for a natural cadence.
      if (!window.speechSynthesis) return { spoken: false }
      const profile = resolveVoiceProfile(voiceCode)
      // Voices are usually already loaded after preflight Test. Only wait briefly
      // when empty — long awaits after Join drop Chrome's user-gesture unlock.
      if (!window.speechSynthesis.getVoices().length) {
        await waitForBrowserVoices(600)
      }

      // Chrome: cancel() after an await often kills the gesture unlock and the
      // next utterance never starts. If Join/Test already unlocked speech, leave
      // the queue alone — EXCEPT clear near-silent hold primes so they cannot
      // starve the real interviewer line (holdSpeechUnlock ticks every ~1.8s).
      const synth = window.speechSynthesis
      if (_speechHoldActive && (synth.speaking || synth.pending)) {
        try { synth.cancel() } catch { /* */ }
        await new Promise((r) => setTimeout(r, 40))
      } else if (!_speechGestureUnlocked && (synth.speaking || synth.pending)) {
        try { synth.cancel() } catch { /* */ }
        await new Promise((r) => setTimeout(r, 35))
      }
      resumeSpeechSynthesis()

      const voice = pickBrowserVoice(
        profile.browser_voice_hint, profile.locale, selectedVoiceRef.current,
      )
      const rate = Math.min(1.08, Math.max(0.88, speechOverrides.rate ?? profile.rate ?? 0.98))
      const pitch = Math.min(1.15, Math.max(0.88, speechOverrides.pitch ?? profile.pitch ?? 1))
      const utterOpts = { voice, locale: profile.locale, rate, pitch }
      const pauseOverrides = {
        question: speechOverrides.pauseQuestionMs,
        period: speechOverrides.pausePeriodMs,
      }

      const segments = segmentForSpeech(text)
      const myToken = ++speakTokenRef.current

      // Chrome silences speech after ~15s and sometimes pauses the queue between
      // utterances. A low-frequency resume() keep-alive guarantees every segment
      // actually plays. Cleared in finally.
      const keepAlive = setInterval(() => {
        try {
          if (window.speechSynthesis?.paused) window.speechSynthesis.resume()
        } catch { /* non-fatal */ }
      }, 2500)

      try {
        for (let i = 0; i < segments.length; i++) {
          if (speakTokenRef.current !== myToken) break
          const seg = segments[i]
          const started = await speakBrowserUtterance(seg, utterOpts)
          if (started) spoken = true
          if (i < segments.length - 1 && speakTokenRef.current === myToken) {
            const last = seg.trim().slice(-1)
            let gap = pauseAfter(seg)
            if (last === '?' && pauseOverrides.question) gap = pauseOverrides.question
            else if (last === '.' && pauseOverrides.period) gap = pauseOverrides.period
            await new Promise((resolve) => {
              speakPauseTimerRef.current = setTimeout(() => {
                speakPauseTimerRef.current = null
                resolve()
              }, gap)
            })
          }
        }

        // Chrome sometimes resolves utterances instantly without onstart — retry
        // once as a single block so the candidate still hears the interviewer.
        if (!spoken && speakTokenRef.current === myToken) {
          const clean = (text || '').replace(/\s+/g, ' ').trim()
          if (clean) {
            unlockSpeech({ soft: true })
            resumeSpeechSynthesis()
            spoken = await speakBrowserUtterance(clean.slice(0, 500), utterOpts)
          }
        }
      } finally {
        clearInterval(keepAlive)
      }

      return { spoken }
    } finally {
      _speakInFlight = false
      setIsSpeaking(false)
    }
  }, [resolveVoiceProfile])

  const cancelSpeech = useCallback(() => {
    // Invalidate any in-flight segmented queue so it stops between sentences.
    speakTokenRef.current += 1
    if (speakPauseTimerRef.current) {
      clearTimeout(speakPauseTimerRef.current)
      speakPauseTimerRef.current = null
    }
    stopAudio()
    setIsSpeaking(false)
  }, [])

  // ------------------------------------------------------------------
  // listen() — Whisper (server) with browser SpeechRecognition fallback
  // Returns { transcript, filteredText, confidence, provider }
  // ------------------------------------------------------------------
  const listen = useCallback(async (mediaStream, options = {}) => {
    const {
      locale = 'en-US',
      maxDuration = 60000,       // ms — max recording time
      onInterim = null,          // callback(text) for live transcript display
      techPrompt = '',           // hint for Whisper vocabulary
    } = options

    setIsListening(true)
    setInterimTranscript('')

    try {
      // --- Server-side Whisper path ---
      if (configRef.current.uses_server_stt && mediaStream) {
        await audioRecorder.current.start(mediaStream)

        // Show browser interim results while recording (best effort)
        let browserRecognizer = null
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition
        if (SR && onInterim) {
          browserRecognizer = new SR()
          browserRecognizer.lang = locale
          browserRecognizer.continuous = true
          browserRecognizer.interimResults = true
          browserRecognizer.onresult = (e) => {
            const interim = Array.from(e.results)
              .map(r => r[0].transcript)
              .join(' ')
            setInterimTranscript(interim)
            onInterim(interim)
          }
          try { browserRecognizer.start() } catch { /* */ }
        }

        // Wait for stop signal (caller calls stopListening or timeout)
        await new Promise(r => {
          audioRecorder.current._resolve = r
          setTimeout(r, maxDuration)
        })

        if (browserRecognizer) {
          try { browserRecognizer.stop() } catch { /* */ }
        }

        const recording = await audioRecorder.current.stop()
        setInterimTranscript('')

        if (recording?.blob?.size > 500) {
          const result = await serverTranscribe(
            recording.blob,
            recording.mimeType,
            techPrompt,
          )
          return result
        }
      }

      // --- Browser SpeechRecognition fallback ---
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition
      if (!SR) return { transcript: '', filtered_text: '', confidence: 0, provider: 'none' }

      return new Promise((resolve) => {
        const r = new SR()
        r.lang = locale
        // Continuous so a multi-sentence answer (with natural pauses) is captured
        // as one turn. The room decides when to finalize — on the explicit Stop
        // button, on skip-on-silence, or on the maxDuration safety timeout.
        r.continuous = true
        r.interimResults = true

        let finalText = ''           // accumulated finalized speech
        let lastConfidence = 0.8
        let settled = false
        recognizerRef.current = r

        const finish = () => {
          if (settled) return
          settled = true
          recognizerRef.current = null
          clearTimeout(timer)
          setInterimTranscript('')
          const text = finalText.trim()
          resolve({
            transcript: text,
            filtered_text: text,
            confidence: lastConfidence,
            provider: 'browser',
            is_final: true,
            word_count: text ? text.split(/\s+/).length : 0,
          })
        }

        r.onresult = (e) => {
          let interim = ''
          for (let i = e.resultIndex; i < e.results.length; i++) {
            const res = e.results[i]
            const chunk = res[0].transcript
            if (res.isFinal) {
              finalText += (finalText ? ' ' : '') + chunk.trim()
              lastConfidence = res[0].confidence || lastConfidence
            } else {
              interim += chunk
            }
          }
          const display = (finalText + ' ' + interim).trim()
          setInterimTranscript(display)
          if (onInterim) onInterim(display)
        }

        // A transient no-speech / aborted error shouldn't throw away what we
        // already captured — just finalize with whatever we have.
        r.onerror = finish
        r.onend = finish

        try { r.start() } catch { finish() }
        // Safety cap so a stuck recognizer can never listen forever.
        const timer = setTimeout(() => { try { r.stop() } catch { finish() } }, maxDuration)
      })
    } finally {
      setIsListening(false)
      setInterimTranscript('')
    }
  }, [])

  // ------------------------------------------------------------------
  // listenLive() — TRUE hands-free turn (FIX 1 / WS1)
  //
  // Continuous browser SpeechRecognition + interim results + a DYNAMIC
  // trailing-SILENCE timer that AUTO-FINALIZES the turn after the candidate
  // stops talking. This is what removes the send button: the candidate just
  // speaks, stops, and their answer submits itself — but only once we're
  // confident they're actually done, not mid-thought.
  //
  // WS1 — don't cut people off:
  //   * The silence window is NOT armed until we've both landed at least one
  //     FINAL result AND heard >~1.2s of real speech. A short "uh, well…" or a
  //     single early interim never self-submits.
  //   * The window GROWS with the answer: base + ~400ms per sentence boundary,
  //     capped at ~4500ms, so a long multi-sentence reply gets more breathing
  //     room than a one-liner.
  //   * If the captured utterance currently ENDS on a connector/filler word
  //     ('and', 'so', 'um', 'because', 'which means', 'then', 'like', …) the
  //     speaker is still mid-thought, so we EXTEND the window instead of
  //     settling.
  //   * onSilenceCountdown(remainingMs, totalMs) fires while the window runs so
  //     the room can show a "still listening — take your time" affordance with a
  //     small countdown; it's cancelled (remainingMs=null) on any new speech.
  //
  // Other robustness rules (unchanged):
  //   * The timer is RESET on every new token, so a natural mid-sentence pause
  //     never auto-submits — only a real trailing window of quiet after speech.
  //   * We only auto-finalize-by-silence once REAL speech has been heard AND we
  //     have a non-empty transcript. An empty/no-speech turn never resolves via
  //     the silence path (it waits for the caller's stop or the safety cap).
  //   * Chrome ends continuous recognition itself after a pause; we transparently
  //     restart it until the caller stops or silence fires, so one long answer
  //     with pauses is captured as a single turn.
  //
  // Resolves with { transcript, filtered_text, confidence, provider, reason,
  // had_speech }. ``reason`` is 'silence' | 'manual' | 'timeout' | 'error' |
  // 'unsupported' so the room can decide whether to submit.
  //
  // 100% browser-native — no paid STT.
  // ------------------------------------------------------------------
  const listenLive = useCallback((mediaStream, options = {}) => {
    const {
      locale = 'en-US',
      maxDuration = 90000,        // hard safety cap
      silenceMs = 2800,           // BASE trailing quiet after speech → auto-submit
      minSpeechMs = 1200,         // require this much speech before we arm silence
      maxSilenceMs = 4500,        // upper bound on the dynamic window
      perSentenceMs = 400,        // window growth per sentence boundary
      minWordsForSilence = 3,     // minimum words before trailing silence auto-submits
      onInterim = null,
      onSilenceCountdown = null,  // (remainingMs|null, totalMs) for the affordance
    } = options

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) {
      return Promise.resolve({
        transcript: '', filtered_text: '', confidence: 0,
        provider: 'none', reason: 'unsupported', had_speech: false,
      })
    }

    setIsListening(true)
    setInterimTranscript('')

    return new Promise((resolve) => {
      const r = new SR()
      r.lang = locale
      r.continuous = true
      r.interimResults = true

      let finalText = ''
      let lastInterim = ''           // most recent interim — Chrome can be slow
                                     // to promote it to final on a pause.
      let lastConfidence = 0.8
      let hadSpeech = false
      let hadFinal = false           // at least one finalized result has landed
      let speechStartedAt = 0        // first real speech (ms) — gates min duration
      let settled = false
      let stopRequested = false      // caller asked us to finalize now (manual)
      let silenceTimer = null
      let countdownInterval = null
      let restartGuard = false
      recognizerRef.current = r

      const clearSilence = () => {
        if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null }
        if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null }
      }

      // Best transcript we currently hold: finalized speech, plus any trailing
      // interim that Chrome hasn't promoted yet (so a short answer ending on a
      // pause isn't lost just because the engine was slow to finalize).
      const bestText = () => (finalText + ' ' + (lastInterim || '')).trim()

      // Compute the dynamic trailing-silence window for the answer captured so
      // far. Longer / multi-sentence answers earn a wider window; an utterance
      // that trails off on a connector earns the widest (they're still thinking).
      const computeSilenceWindow = () => {
        const text = bestText()
        const sentences = (text.match(/[.!?]+/g) || []).length
        let win = silenceMs + sentences * perSentenceMs
        if (endsOnConnector(text)) win += perSentenceMs * 2
        return Math.min(maxSilenceMs, win)
      }

      const settle = (reason) => {
        if (settled) return
        settled = true
        clearSilence()
        clearTimeout(capTimer)
        recognizerRef.current = null
        // Detach handlers so a late onend/onresult can't fire after we resolve.
        r.onresult = null
        r.onend = null
        r.onerror = null
        r.onspeechstart = null
        try { r.stop() } catch { /* already stopping */ }
        try { r.abort?.() } catch { /* */ }
        setInterimTranscript('')
        setIsListening(false)
        if (onSilenceCountdown) onSilenceCountdown(null, 0)
        const text = bestText()
        resolve({
          transcript: text,
          filtered_text: text,
          confidence: lastConfidence,
          provider: 'browser',
          reason,
          had_speech: hadSpeech,
          is_final: true,
          word_count: text ? text.split(/\s+/).length : 0,
        })
      }

      // Arm the trailing-silence auto-submit. Only meaningful once we've heard
      // real speech, landed a FINAL result, captured some text, AND the speaker
      // has talked for at least minSpeechMs — otherwise it's a no-op so an
      // idle/empty/too-brief turn never self-submits on a mid-sentence pause.
      const armSilence = () => {
        clearSilence()
        if (!hadSpeech || !hadFinal || !bestText()) return
        // Require a minimum answer length before auto-submitting on pause — a
        // brief "um" or mid-thought breath should not end the turn.
        const words = bestText().split(/\s+/).filter(Boolean).length
        if (words < minWordsForSilence && Date.now() - speechStartedAt < minSpeechMs * 2) return
        if (speechStartedAt && Date.now() - speechStartedAt < minSpeechMs) return
        const total = computeSilenceWindow()
        const startedAt = Date.now()
        silenceTimer = setTimeout(() => settle('silence'), total)
        if (onSilenceCountdown) {
          onSilenceCountdown(total, total)
          // Tick the visible countdown so the affordance counts down smoothly.
          countdownInterval = setInterval(() => {
            const remaining = Math.max(0, total - (Date.now() - startedAt))
            onSilenceCountdown(remaining, total)
            if (remaining <= 0 && countdownInterval) {
              clearInterval(countdownInterval); countdownInterval = null
            }
          }, 150)
        }
      }

      r.onspeechstart = () => {
        hadSpeech = true
        if (!speechStartedAt) speechStartedAt = Date.now()
      }

      r.onresult = (e) => {
        hadSpeech = true
        if (!speechStartedAt) speechStartedAt = Date.now()
        let interim = ''
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const res = e.results[i]
          const chunk = res[0].transcript
          if (res.isFinal) {
            finalText += (finalText ? ' ' : '') + chunk.trim()
            lastConfidence = res[0].confidence || lastConfidence
            hadFinal = true
          } else {
            interim += chunk
          }
        }
        lastInterim = interim.trim()
        const display = bestText()
        setInterimTranscript(display)
        if (onInterim) onInterim(display)
        // New tokens → cancel any visible countdown and reset the trailing-silence
        // window. A pause only counts once tokens STOP arriving for the full
        // (dynamic) window.
        if (onSilenceCountdown) onSilenceCountdown(null, 0)
        armSilence()
      }

      r.onerror = (ev) => {
        // 'no-speech' / 'aborted' are transient — don't trash a captured answer.
        if (ev?.error === 'no-speech' || ev?.error === 'aborted') {
          // Let onend handle the restart/settle decision.
          return
        }
        settle('error')
      }

      // Chrome fires onend whenever it pauses recognition (after silence) or on
      // stop(). If the caller hasn't asked to stop and we're under the cap,
      // transparently restart so a long, pause-laden answer is one turn. If the
      // caller stopped (manual/barge-in), finalize.
      r.onend = () => {
        if (settled) return
        if (stopRequested) { settle('manual'); return }
        // If silence already captured a real answer, the timer will settle; if
        // not, keep listening by restarting (guard against tight restart loops).
        if (!restartGuard) {
          restartGuard = true
          setTimeout(() => { restartGuard = false }, 250)
          try { r.start(); return } catch { /* fall through to settle */ }
        }
        // Couldn't restart — finalize with whatever we have (silence if we have
        // speech+text, else manual so the caller treats it as "nothing said").
        settle(hadSpeech && bestText() ? 'silence' : 'manual')
      }

      // Expose a finalize hook for stopListening()/barge-in to end this turn.
      r._finishLive = () => { stopRequested = true; try { r.stop() } catch { settle('manual') } }

      try { r.start() } catch { settle('error') }
      const capTimer = setTimeout(() => settle('timeout'), maxDuration)
    })
  }, [])

  // Stop the active capture and finalize it. Works for the live hands-free turn
  // (listenLive), the server-Whisper path (resolves the recorder), and the
  // explicit browser path (stops the recognizer so its onend resolves with the
  // accumulated transcript). Called by the Stop button, skip-on-silence, and
  // barge-in handling.
  const stopListening = useCallback(() => {
    if (audioRecorder.current._resolve) {
      audioRecorder.current._resolve()
      audioRecorder.current._resolve = null
    }
    if (recognizerRef.current) {
      // listenLive instances carry a finalize hook so we end the turn cleanly
      // and report it as a manual stop (vs an auto silence-submit).
      if (recognizerRef.current._finishLive) {
        recognizerRef.current._finishLive()
      } else {
        try { recognizerRef.current.stop() } catch { /* already stopped */ }
      }
    }
  }, [])

  // Ranked browser voices (most natural first) for the in-room/preflight picker.
  // Falls back to the raw list if ranking yields nothing.
  const naturalVoices = useCallback((locale = 'en-US') => {
    return rankVoicesByNaturalness(browserVoices, locale)
  }, [browserVoices])

  return {
    config,
    isSpeaking,
    isListening,
    interimTranscript,
    speak,
    unlockSpeech,
    holdSpeechUnlock,
    releaseSpeechHold,
    resumeSpeechSynthesis,
    cancelSpeech,
    listen,
    listenLive,
    stopListening,
    resolveVoiceProfile,
    // In-room voice switching (P2.1)
    browserVoices,
    naturalVoices,
    selectedVoiceURI,
    selectVoice,
  }
}
