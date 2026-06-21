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
// ---------------------------------------------------------------------------

function pickBrowserVoice(hint, locale, preferredURI) {
  if (!window.speechSynthesis) return null
  const voices = window.speechSynthesis.getVoices()
  if (!voices.length) return null
  // An explicit in-room user choice always wins.
  if (preferredURI) {
    const chosen = voices.find(v => v.voiceURI === preferredURI)
    if (chosen) return chosen
  }
  if (hint) {
    const match = voices.find(v => v.name.toLowerCase().includes(hint.toLowerCase()))
    if (match) return match
  }
  const localeMatch = voices.find(
    v => v.lang === locale || v.lang?.startsWith(locale?.split('-')[0])
  )
  return localeMatch || voices[0]
}

const VOICE_STORAGE_KEY = 'fixitlab.interview.voiceURI'

function loadPersistedVoiceURI() {
  try {
    return window.localStorage.getItem(VOICE_STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

function persistVoiceURI(uri) {
  try {
    if (uri) window.localStorage.setItem(VOICE_STORAGE_KEY, uri)
    else window.localStorage.removeItem(VOICE_STORAGE_KEY)
  } catch { /* storage unavailable — non-fatal */ }
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

function stopAudio() {
  if (_currentAudio) {
    _currentAudio.pause()
    _currentAudio = null
  }
  if (window.speechSynthesis) window.speechSynthesis.cancel()
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
      const t = setTimeout(refresh, 400)
      return () => { clearTimeout(t) }
    }
  }, [])

  const selectVoice = useCallback((voiceURI) => {
    setSelectedVoiceURI(voiceURI || '')
    persistVoiceURI(voiceURI || '')
  }, [])

  const resolveVoiceProfile = useCallback((voiceCode) => {
    const code = voiceCode || config.default_voice_code
    return (
      config.voices?.find(v => v.code === code) ||
      config.voices?.[0] || {
        code: 'US_F_ZIRA',
        locale: 'en-US',
        browser_voice_hint: '',
        pitch: 1,
        rate: 0.95,
      }
    )
  }, [config])

  // ------------------------------------------------------------------
  // speak() — server TTS with browser fallback
  // ------------------------------------------------------------------
  const speak = useCallback(async (text, voiceCode) => {
    if (!text) return
    setIsSpeaking(true)

    try {
      if (config.uses_server_tts) {
        const profile = resolveVoiceProfile(voiceCode)
        const result = await serverSpeak(text, profile.code).catch(() => null)

        if (result?.audio_b64) {
          await playBase64Audio(result.audio_b64, 'audio/mpeg')
          return
        }
        // Fall through to browser TTS
      }

      // Browser SpeechSynthesis fallback
      if (!window.speechSynthesis) return
      const profile = resolveVoiceProfile(voiceCode)
      window.speechSynthesis.cancel()
      const u = new SpeechSynthesisUtterance(text)
      u.lang = profile.locale || 'en-US'
      u.rate = profile.rate ?? 0.95
      u.pitch = profile.pitch ?? 1
      // Honor the user's in-room voice choice over the admin hint.
      const voice = pickBrowserVoice(
        profile.browser_voice_hint, profile.locale, selectedVoiceRef.current,
      )
      if (voice) {
        u.voice = voice
        if (voice.lang) u.lang = voice.lang
      }

      await new Promise((resolve) => {
        u.onend = resolve
        u.onerror = resolve
        window.speechSynthesis.speak(u)
      })
    } finally {
      setIsSpeaking(false)
    }
  }, [config.uses_server_tts, resolveVoiceProfile])

  const cancelSpeech = useCallback(() => {
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
      if (config.uses_server_stt && mediaStream) {
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
  }, [config.uses_server_stt])

  // Stop the active capture and finalize it. Works for BOTH the server-Whisper
  // path (resolves the recorder) and the browser path (stops the recognizer so
  // its onend resolves with the accumulated transcript). Called by the Stop
  // button, by skip-on-silence, and by barge-in handling.
  const stopListening = useCallback(() => {
    if (audioRecorder.current._resolve) {
      audioRecorder.current._resolve()
      audioRecorder.current._resolve = null
    }
    if (recognizerRef.current) {
      try { recognizerRef.current.stop() } catch { /* already stopped */ }
    }
  }, [])

  return {
    config,
    isSpeaking,
    isListening,
    interimTranscript,
    speak,
    cancelSpeech,
    listen,
    stopListening,
    resolveVoiceProfile,
    // In-room voice switching (P2.1)
    browserVoices,
    selectedVoiceURI,
    selectVoice,
  }
}
