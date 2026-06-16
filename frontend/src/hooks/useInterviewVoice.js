import { useCallback, useEffect, useRef, useState } from 'react'
import { interviewsApi } from '../api/interviews'

function pickBrowserVoice(hint, locale) {
  if (!window.speechSynthesis) return null
  const voices = window.speechSynthesis.getVoices()
  if (!voices.length) return null
  if (hint) {
    const match = voices.find(v => v.name.toLowerCase().includes(hint.toLowerCase()))
    if (match) return match
  }
  const localeMatch = voices.find(v => v.lang === locale || v.lang?.startsWith(locale?.split('-')[0]))
  return localeMatch || voices[0]
}

/**
 * Free browser voice: SpeechSynthesis + SpeechRecognition (no paid APIs).
 */
export function useInterviewVoice() {
  const [config, setConfig] = useState({
    stt_provider: 'browser',
    tts_provider: 'browser',
    voices: [],
    default_voice_code: 'indian-female',
    uses_paid_apis: false,
  })
  const voicesReady = useRef(false)

  useEffect(() => {
    interviewsApi.getVoiceConfig().then(setConfig).catch(() => {})
    const loadVoices = () => { voicesReady.current = true }
    if (window.speechSynthesis) {
      window.speechSynthesis.onvoiceschanged = loadVoices
      loadVoices()
    }
  }, [])

  const resolveVoiceProfile = useCallback((voiceCode) => {
    const code = voiceCode || config.default_voice_code
    return config.voices?.find(v => v.code === code)
      || config.voices?.[0]
      || { locale: 'en-IN', browser_voice_hint: '', pitch: 1, rate: 0.95 }
  }, [config])

  const speak = useCallback((text, voiceCode) => {
    if (!text || !window.speechSynthesis) return
    const profile = resolveVoiceProfile(voiceCode)
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = profile.locale || 'en-IN'
    u.rate = profile.rate ?? 0.95
    u.pitch = profile.pitch ?? 1
    const voice = pickBrowserVoice(profile.browser_voice_hint, profile.locale)
    if (voice) u.voice = voice
    window.speechSynthesis.speak(u)
  }, [resolveVoiceProfile])

  const listen = useCallback((locale = 'en-IN') => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return Promise.resolve('')
    return new Promise((resolve) => {
      const r = new SR()
      r.lang = locale
      r.continuous = false
      r.interimResults = false
      r.onresult = (e) => resolve(e.results[0]?.[0]?.transcript || '')
      r.onerror = () => resolve('')
      r.onend = () => {}
      r.start()
      setTimeout(() => { try { r.stop() } catch { /* */ } }, 15000)
    })
  }, [])

  return { config, speak, listen, resolveVoiceProfile }
}
