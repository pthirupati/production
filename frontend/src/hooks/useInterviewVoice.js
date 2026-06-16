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

function pickBrowserVoice(hint, locale) {
  if (!window.speechSynthesis) return null
  const voices = window.speechSynthesis.getVoices()
  if (!voices.length) return null
  if (hint) {
    const match = voices.find(v => v.name.toLowerCase().includes(hint.toLowerCase()))
    if (match) return match
  }
  const localeMatch = voices.find(
    v => v.lang === locale || v.lang?.startsWith(locale?.split('-')[0])
  )
  return localeMatch || voices[0]
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
    audio.onended = () => { URL.revokeObjectURL(url); resolve() }
    audio.onerror = (e) => { URL.revokeObjectURL(url); reject(e) }
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

  const voicesReady = useRef(false)
  const audioRecorder = useRef(new AudioRecorder())

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

    const loadVoices = () => { voicesReady.current = true }
    if (window.speechSynthesis) {
      window.speechSynthesis.onvoiceschanged = loadVoices
      if (window.speechSynthesis.getVoices().length) loadVoices()
    }
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
      const voice = pickBrowserVoice(profile.browser_voice_hint, profile.locale)
      if (voice) u.voice = voice

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
      if (!SR) return { transcript: '', filteredText: '', confidence: 0, provider: 'none' }

      return new Promise((resolve) => {
        const r = new SR()
        r.lang = locale
        r.continuous = false
        r.interimResults = true

        r.onresult = (e) => {
          const results = Array.from(e.results)
          const interimText = results.map(res => res[0].transcript).join(' ')
          setInterimTranscript(interimText)
          if (onInterim) onInterim(interimText)

          if (e.results[e.results.length - 1].isFinal) {
            const finalText = results
              .filter(res => res.isFinal)
              .map(res => res[0].transcript)
              .join(' ')
            const confidence = e.results[e.results.length - 1][0].confidence || 0.8
            setInterimTranscript('')
            resolve({
              transcript: finalText,
              filtered_text: finalText,
              confidence,
              provider: 'browser',
              is_final: true,
              word_count: finalText.split(' ').length,
            })
          }
        }

        r.onerror = () => resolve({ transcript: '', filtered_text: '', confidence: 0, provider: 'browser' })
        r.onend = () => resolve({ transcript: '', filtered_text: '', confidence: 0, provider: 'browser' })

        r.start()
        setTimeout(() => { try { r.stop() } catch { /* */ } }, maxDuration)
      })
    } finally {
      setIsListening(false)
      setInterimTranscript('')
    }
  }, [config.uses_server_stt])

  // Called by UI "stop recording" button to finalize Whisper capture
  const stopListening = useCallback(() => {
    if (audioRecorder.current._resolve) {
      audioRecorder.current._resolve()
      audioRecorder.current._resolve = null
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
  }
}
