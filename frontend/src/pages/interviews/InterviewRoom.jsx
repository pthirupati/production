import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { interviewsApi } from '../../api/interviews'
import { adminApi } from '../../api/admin'
import { useInterviewVoice, unlockSpeech, detectSpeechCapabilities } from '../../hooks/useInterviewVoice'
import {
  getMediaErrorMessage,
  isMediaDevicesSupported,
  isPermissionDeniedError,
  requestUserMedia,
  stopMediaStream,
  streamHasLiveTrack,
} from '../../utils/mediaDevices'
import InterviewVideoPreview from '../../components/interviews/InterviewVideoPreview'
import InterviewerStage from '../../components/interviews/InterviewerStage'
import PracticalAnswerPanel from '../../components/interviews/PracticalAnswerPanel'
import CoachingTip from '../../components/interviews/CoachingTip'
import { PageHeader } from '../../components/design'
import {
  Mic, MicOff, Video, VideoOff, PhoneOff, Clock, MessageSquare, Terminal,
  Volume2, VolumeX, Plus, ExternalLink, Loader2, ArrowLeft, Calendar, X, SkipForward,
  CheckCircle2, HelpCircle, RotateCcw, Star,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { useConfirm } from '../../hooks/useConfirm'
import { usePageTitle } from '../../hooks/usePageTitle'

// How long (ms) of continuous silence on an open question before the bot moves
// on, so the fixed round time covers the planned material (skip-on-silence).
const SILENCE_SKIP_MS = 45000
// BASE trailing silence (ms) after the candidate stops talking before we
// AUTO-SUBMIT their answer (FIX 1 — no send button). WS1: raised so a normal
// between-sentence breath never cuts the candidate off; listenLive GROWS this
// dynamically for longer/multi-sentence answers (up to ~8s) and extends further
// when they trail off on a connector ("and…", "so…").
const TURN_SILENCE_MS = 2200
// Mic energy (0–1, same scale as the preflight meter) that counts as "speaking"
// for barge-in. Above this while the bot is talking → interrupt the bot.
const BARGE_IN_LEVEL = 0.18
// Mic energy that counts as the candidate actively speaking, used to glow their
// tile as the active speaker (FIX 4). Lower than barge-in: any clear voice.
const CANDIDATE_SPEAKING_LEVEL = 0.1

// WS5 — lightweight client-side question classifier. The backend is the source
// of truth for intent, but tagging input_type:'question' up front (e.g. on a
// barge-in interruption) makes the engine's clarification path deterministic.
// Matches a trailing '?', leading interrogatives, and common ask/repeat phrasing.
const _QUESTION_LEADS = /^(what|why|how|when|where|which|who|whom|whose|can|could|would|should|do|does|did|is|are|was|were|will|may|might|shall|sorry|pardon|wait)\b/i
const _QUESTION_PHRASES = /\b(repeat that|say that again|come again|can you repeat|could you repeat|what do you mean|what does that mean|can you clarify|could you clarify|not sure i (?:understand|follow)|didn'?t (?:catch|hear|understand)|rephrase|one more time|ask that again)\b/i
function looksLikeQuestion(text) {
  const t = (text || '').trim()
  if (!t) return false
  const words = t.split(/\s+/).length
  // Explicit meta-phrases always count.
  if (_QUESTION_PHRASES.test(t)) return true
  // Long spoken answers are answers — not interruptions — even if they end with '?'.
  if (words > 20) return false
  if (/^(what is |what's |what are )/i.test(t)) return true
  if (t.endsWith('?') && words <= 16 && _QUESTION_LEADS.test(t)) return true
  return _QUESTION_LEADS.test(t) && words <= 12
}

function assessTranscriptClarity(text, result) {
  const t = (text || '').trim()
  if (!t) {
    return result?.had_speech ? 'unclear' : 'empty'
  }
  const conf = result?.confidence
  if (typeof conf === 'number' && conf > 0 && conf < 0.42) return 'unclear'
  const words = t.split(/\s+/).filter(Boolean)
  if (result?.had_speech && words.length <= 1 && !/^(yes|no|ok|okay)$/i.test(t)) return 'unclear'
  if (result?.reason === 'error' && result?.had_speech) return 'unclear'
  const alpha = (t.match(/[a-zA-Z]/g) || []).length
  if (t.length > 8 && alpha / t.length < 0.55) return 'unclear'
  return 'ok'
}

export default function InterviewRoom() {
  const { roundId } = useParams()
  const [searchParams] = useSearchParams()
  const observerToken = searchParams.get('observer')
  const observerTokenRef = useRef(observerToken)
  const processedHostMsgRef = useRef(new Set())
  const navigate = useNavigate()
  const { confirm, ConfirmPortal } = useConfirm()

  usePageTitle('Interview room', 'Live technical interview on FixitLab', { noIndex: true })

  // Strip sensitive observer token from URL immediately to avoid leaking via
  // browser history, server logs, or Referer headers.
  useEffect(() => {
    if (observerToken) {
      const url = new URL(window.location.href)
      url.searchParams.delete('observer')
      window.history.replaceState({}, '', url.toString())
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  const streamRef = useRef(null)
  const audioCtxRef = useRef(null)
  const rafRef = useRef(null)
  // Serializes media requests so the proactive prompt, the buttons, and
  // "Try again" never run getUserMedia concurrently (concurrent calls race and
  // one rejects with NotReadable/NotAllowed even though access was granted).
  const mediaInFlightRef = useRef(null)
  const recorderRef = useRef(null)
  const recChunksRef = useRef([])
  // Live VAD (barge-in + skip-on-silence) — its own AudioContext so it runs
  // during the interview, independent of the preflight mic meter.
  const vadCtxRef = useRef(null)
  const vadRafRef = useRef(null)
  // Mutable mirrors of speaking/listening so the VAD rAF loop reads fresh values
  // without re-subscribing every frame.
  const isSpeakingRef = useRef(false)
  const isListeningRef = useRef(false)
  const bargedInRef = useRef(false)        // guard: only barge in once per utterance
  const silenceTimerRef = useRef(null)     // skip-on-silence countdown
  const awaitingAnswerRef = useRef(false)  // true while a question is open
  const answerRef = useRef('')             // live mirror of the answer box
  const bargeInHandlerRef = useRef(null)   // latest barge-in action (set below)
  const [mediaStream, setMediaStream] = useState(null)
  const [recordingReady, setRecordingReady] = useState(false)
  const [micLevel, setMicLevel] = useState(0)
  // Active-speaker highlight for the candidate tile (FIX 4): true while the live
  // mic VAD hears the candidate's voice. Drives the green glow + caption.
  const [candidateSpeaking, setCandidateSpeaking] = useState(false)
  // The AI's most recent spoken line, shown as a live caption on its tile.
  const [aiCaption, setAiCaption] = useState('')
  const {
    speak, listenLive, stopListening, cancelSpeech,
    resolveVoiceProfile,
    isSpeaking, isListening, interimTranscript,
    browserVoices, naturalVoices, selectedVoiceURI, selectVoice,
  } = useInterviewVoice()
  const speakRef = useRef(speak)
  const cancelSpeechRef = useRef(cancelSpeech)
  const speakThenListenRef = useRef(null)
  // Stable handle to the LATEST voiceAnswer closure. The hands-free loop and
  // barge-in handler call through this ref so they never capture a stale
  // closure AND never need voiceAnswer in their dependency arrays (which would
  // otherwise re-subscribe every render — the churn that cancelled in-flight
  // TTS/STT each cycle and made the room feel like it was "refreshing").
  const voiceAnswerRef = useRef(null)
  speakRef.current = speak
  cancelSpeechRef.current = cancelSpeech

  const [round, setRound] = useState(null)
  const [messages, setMessages] = useState([])
  const [answer, setAnswer] = useState('')
  const [micOn, setMicOn] = useState(false)
  const [cameraOn, setCameraOn] = useState(false)
  // "Mute interviewer" — silences TTS output while keeping the live caption and
  // the hands-free loop intact (candidate reads the question, then answers).
  const [interviewerMuted, setInterviewerMuted] = useState(false)
  const interviewerMutedRef = useRef(false)
  const [timeLeft, setTimeLeft] = useState(null)
  const [started, setStarted] = useState(false)
  const [practicalMode, setPracticalMode] = useState(false)
  const [practicalLab, setPracticalLab] = useState(null)
  const [labLoading, setLabLoading] = useState(false)
  const [preflight, setPreflight] = useState(true)
  const [joinRequests, setJoinRequests] = useState([])
  const [observerMode, setObserverMode] = useState(!!observerToken)
  const [hostState, setHostState] = useState(null)
  const [adminQuestion, setAdminQuestion] = useState('')
  const [hostBusy, setHostBusy] = useState(false)
  const [observerJoined, setObserverJoined] = useState(false)
  const [rateTarget, setRateTarget] = useState(null)
  const [hostFeedback, setHostFeedback] = useState('')
  const [consentAccepted, setConsentAccepted] = useState(false)
  const [showReschedule, setShowReschedule] = useState(false)
  const [rescheduleAt, setRescheduleAt] = useState('')
  const [mediaError, setMediaError] = useState('')
  const [mediaLoading, setMediaLoading] = useState(false)
  const [backgroundId, setBackgroundId] = useState('none')
  // Practice/coaching mode (parity: interviewai.io practice mode): when on, the
  // engine returns an instant coaching tip after each answer.
  const [practiceMode, setPracticalCoaching] = useState(false)
  const [coaching, setCoaching] = useState(null)
  const [typingAnswer, setTypingAnswer] = useState(false)
  const [mobileTranscriptOpen, setMobileTranscriptOpen] = useState(false)
  const [speechSupported, setSpeechSupported] = useState(true)
  const [ttsSupported, setTtsSupported] = useState(true)
  const voiceUnavailableToastRef = useRef(false)
  const audioCutoutToastAtRef = useRef(0)
  const [audioDevices, setAudioDevices] = useState([])
  const [videoDevices, setVideoDevices] = useState([])
  const [selectedAudioId, setSelectedAudioId] = useState('')
  const [selectedVideoId, setSelectedVideoId] = useState('')
  useEffect(() => {
    const caps = detectSpeechCapabilities()
    setSpeechSupported(caps.stt)
    setTtsSupported(caps.tts)
    if (!caps.stt) setTypingAnswer(true)
  }, [])

  useEffect(() => {
    if (!isMediaDevicesSupported()) return
    const refresh = async () => {
      try {
        const devices = await navigator.mediaDevices.enumerateDevices()
        setAudioDevices(devices.filter(d => d.kind === 'audioinput'))
        setVideoDevices(devices.filter(d => d.kind === 'videoinput'))
      } catch { /* ignore */ }
    }
    refresh()
    navigator.mediaDevices?.addEventListener?.('devicechange', refresh)
    return () => navigator.mediaDevices?.removeEventListener?.('devicechange', refresh)
  }, [micOn, cameraOn])

  // WS1 — visible "still listening — take your time" countdown. When the
  // trailing-silence window is running, this holds { remaining, total } in ms so
  // the candidate sees they have a beat before auto-submit; null when idle.
  const [silenceCountdown, setSilenceCountdown] = useState(null)
  // WS5 — when true, the NEXT captured utterance is sent as a candidate question
  // (input_type:'question') rather than an answer: the engine clarifies/repeats
  // and re-asks the SAME question instead of scoring + advancing.
  const askModeRef = useRef(false)
  const [askMode, setAskMode] = useState(false)
  const unclearAudioCountRef = useRef(0)
  const speechProfileRef = useRef(null)
  const [personaTitle, setPersonaTitle] = useState('')
  const [isThinking, setIsThinking] = useState(false)

  // Keep refs in sync so the VAD loop and timers see current speaking/listening.
  useEffect(() => { isSpeakingRef.current = isSpeaking }, [isSpeaking])
  useEffect(() => { isListeningRef.current = isListening }, [isListening])
  useEffect(() => { answerRef.current = answer }, [answer])
  // Mirror practical mode + the persona voice so the host-sync poll can read the
  // latest value WITHOUT listing them as effect deps. Previously `practicalMode`
  // (which toggles mid-interview) was a dependency of the 3s poll, so every
  // practical question tore down and rebuilt the interval — and each rebuild
  // fired an extra immediate getRound + could cancel/re-speak the current line.
  const practicalModeRef = useRef(false)
  useEffect(() => { practicalModeRef.current = practicalMode }, [practicalMode])
  const personaVoiceIdRef = useRef(round?.persona_voice_id)
  useEffect(() => { personaVoiceIdRef.current = round?.persona_voice_id }, [round?.persona_voice_id])
  // WS1 — never leave a stale "still listening" countdown on screen once the
  // mic closes (skip, end, barge-in, or a finalized turn).
  useEffect(() => { if (!isListening) setSilenceCountdown(null) }, [isListening])

  const endsAt = round?.ends_at ? new Date(round.ends_at).getTime() : null

  // Proactively request permissions when preflight loads — triggers the browser
  // dialog immediately (like Google Meet), before the user clicks any button.
  // Goes through the same acquireMedia() path as the buttons so a grant attaches
  // the stream and clears any error automatically (no manual re-click needed).
  useEffect(() => {
    if (observerMode && !preflight && isMediaDevicesSupported()) {
      acquireMedia('both', { silent: true })
    }
  }, [observerMode]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!preflight || observerMode || !isMediaDevicesSupported()) return
    acquireMedia('both', { silent: true })
  }, [preflight]) // eslint-disable-line react-hooks/exhaustive-deps

  // Recover automatically when a device is plugged in or permission is granted
  useEffect(() => {
    if ((!preflight && !observerMode) || !navigator.mediaDevices?.addEventListener) return
    const onDeviceChange = () => {
      if (!micOn || !cameraOn) acquireMedia('both', { silent: true })
    }
    navigator.mediaDevices.addEventListener('devicechange', onDeviceChange)
    return () => navigator.mediaDevices.removeEventListener('devicechange', onDeviceChange)
  }, [preflight, observerMode, micOn, cameraOn]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    return () => {
      stopMediaStream(streamRef.current)
      streamRef.current = null
      setMediaStream(null)
      cancelAnimationFrame(rafRef.current)
      cancelAnimationFrame(vadRafRef.current)
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
      if (audioCtxRef.current) {
        audioCtxRef.current.close()
        audioCtxRef.current = null
      }
      if (vadCtxRef.current) {
        vadCtxRef.current.close()
        vadCtxRef.current = null
      }
      // Stop any in-flight TTS/STT so it doesn't keep running after we leave.
      cancelSpeech()
      stopListening()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!preflight || !micOn || !mediaStream) {
      cancelAnimationFrame(rafRef.current)
      setMicLevel(0)
      return
    }
    let ctx
    try {
      ctx = new (window.AudioContext || window.webkitAudioContext)()
      audioCtxRef.current = ctx
      const source = ctx.createMediaStreamSource(mediaStream)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      source.connect(analyser)
      const data = new Uint8Array(analyser.frequencyBinCount)
      const tick = () => {
        analyser.getByteFrequencyData(data)
        const avg = data.reduce((s, v) => s + v, 0) / data.length
        setMicLevel(Math.min(1, avg / 80))
        rafRef.current = requestAnimationFrame(tick)
      }
      rafRef.current = requestAnimationFrame(tick)
    } catch {
      // AudioContext not available
    }
    return () => {
      cancelAnimationFrame(rafRef.current)
      if (ctx) ctx.close()
    }
  }, [preflight, micOn, mediaStream])

  // Live VAD for barge-in: while the interview is running, watch mic energy.
  // If the candidate starts talking while the bot is speaking, cancel the bot
  // and start listening (the loop's auto-listen then captures the answer).
  // Reuses the same AudioContext-analyser technique as the preflight meter.
  useEffect(() => {
    if (preflight || !started || observerMode || !micOn || !mediaStream) {
      cancelAnimationFrame(vadRafRef.current)
      setCandidateSpeaking(false)
      return
    }
    let ctx
    try {
      ctx = new (window.AudioContext || window.webkitAudioContext)()
      vadCtxRef.current = ctx
      const source = ctx.createMediaStreamSource(mediaStream)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      source.connect(analyser)
      const data = new Uint8Array(analyser.frequencyBinCount)
      let loudFrames = 0
      let speakingFrames = 0   // hysteresis for the active-speaker glow
      let quietFrames = 0
      const tick = () => {
        analyser.getByteFrequencyData(data)
        const avg = data.reduce((s, v) => s + v, 0) / data.length
        const level = Math.min(1, avg / 80)
        // Barge-in: require a few consecutive loud frames to avoid a single
        // pop/echo cancelling the bot mid-sentence.
        if (isSpeakingRef.current && !bargedInRef.current && level > BARGE_IN_LEVEL) {
          loudFrames += 1
          if (loudFrames >= 3) {
            bargedInRef.current = true
            bargeInHandlerRef.current?.()
          }
        } else if (level <= BARGE_IN_LEVEL) {
          loudFrames = 0
        }
        // Active-speaker highlight (FIX 4): glow the candidate tile while they
        // talk. Don't light it for the bot's own audio bleeding into the mic —
        // only when we're NOT speaking (or they've barged in). Hysteresis
        // (a few frames each way) keeps the glow steady, not flickery.
        const candidateVoice =
          level > CANDIDATE_SPEAKING_LEVEL && (!isSpeakingRef.current || bargedInRef.current)
        if (candidateVoice) {
          speakingFrames += 1
          quietFrames = 0
          if (speakingFrames >= 2) setCandidateSpeaking(true)
        } else {
          quietFrames += 1
          speakingFrames = 0
          if (quietFrames >= 8) setCandidateSpeaking(false)
        }
        vadRafRef.current = requestAnimationFrame(tick)
      }
      vadRafRef.current = requestAnimationFrame(tick)
    } catch {
      // AudioContext not available — barge-in simply disabled.
    }
    return () => {
      cancelAnimationFrame(vadRafRef.current)
      setCandidateSpeaking(false)
      if (ctx) ctx.close()
      vadCtxRef.current = null
    }
  }, [preflight, started, observerMode, micOn, mediaStream])

  const syncMediaState = (stream) => {
    streamRef.current = stream
    setMediaStream(stream || null)
    const audioTrack = stream?.getAudioTracks()[0]
    const videoTrack = stream?.getVideoTracks()[0]
    setMicOn(!!audioTrack?.enabled)
    setCameraOn(!!videoTrack?.enabled)
  }

  // Single, serialized media-acquisition path used by the proactive prompt, the
  // Enable/Mic/Camera buttons, the in-room toggles, and "Try again". Centralizing
  // it guarantees: (1) only one getUserMedia runs at a time, (2) a successful
  // stream is authoritative — we attach it and clear any error, and (3) the
  // "blocked" error is only shown after a real getUserMedia rejection, never
  // because of a race with another in-flight request.
  const acquireMedia = (type = 'both', { silent = false } = {}) => {
    // Coalesce concurrent callers onto the in-flight promise.
    if (mediaInFlightRef.current) return mediaInFlightRef.current

    const constraints =
      type === 'audio' ? { audio: selectedAudioId ? { deviceId: { exact: selectedAudioId } } : true, video: false } :
      type === 'video' ? { audio: false, video: selectedVideoId ? { deviceId: { exact: selectedVideoId } } : true } :
      {
        audio: selectedAudioId ? { deviceId: { exact: selectedAudioId } } : true,
        video: selectedVideoId ? { deviceId: { exact: selectedVideoId } } : true,
      }

    const run = async () => {
      // Camera/microphone access requires HTTPS (or localhost).
      const host = window.location.hostname
      if (window.location.protocol !== 'https:' && host !== 'localhost' && host !== '127.0.0.1') {
        const msg = 'Camera and microphone access requires a secure (HTTPS) connection. Please open this page over HTTPS and try again.'
        setMediaError(msg)
        if (!silent) toast.error(msg)
        return
      }
      if (!isMediaDevicesSupported()) {
        const msg = getMediaErrorMessage({ name: 'NotSupportedError' })
        setMediaError(msg)
        if (!silent) toast.error(msg)
        return
      }

      setMediaLoading(true)
      try {
        // requestUserMedia falls back gracefully (e.g. video fails -> audio-only)
        // and merges into the existing stream.
        const { stream, audio, video } = await requestUserMedia(constraints, streamRef.current)
        stream.getAudioTracks().forEach((t) => { t.enabled = true })
        stream.getVideoTracks().forEach((t) => { t.enabled = true })
        syncMediaState(stream)
        // Success is authoritative: clear any stale "blocked" banner.
        setMediaError('')
        if (!silent) {
          if (audio && video) toast.success('Camera and microphone ready')
          else if (video) toast.success('Camera enabled')
          else if (audio) toast.success('Microphone enabled')
        }
      } catch (err) {
        // If a working track already exists (e.g. a concurrent/prior request
        // succeeded, or video failed but audio is live), do NOT paint an error.
        if (streamHasLiveTrack(streamRef.current, constraints) ||
            streamHasLiveTrack(streamRef.current)) {
          syncMediaState(streamRef.current)
          setMediaError('')
          return
        }
        const msg = getMediaErrorMessage(err)
        setMediaError(msg)
        // Only nag with a toast for a genuine permission denial, and never on
        // the silent auto-prompt (the user may simply not have answered yet).
        if (!silent && isPermissionDeniedError(err)) toast.error(msg)
      } finally {
        setMediaLoading(false)
      }
    }

    const promise = run().finally(() => { mediaInFlightRef.current = null })
    mediaInFlightRef.current = promise
    return promise
  }

  const enableMic = () => acquireMedia('audio')
  const enableCamera = () => acquireMedia('video')
  const enableMedia = () => acquireMedia('both')

  useEffect(() => {
    if (observerToken) {
      setObserverMode(true)
      setPreflight(false)
      setStarted(true)
      const token = observerTokenRef.current || observerToken
      adminApi.getInterviewObserverSession(token).then(data => {
        setRound(data.round)
        setMessages(data.messages || [])
        setHostState(data.host_state || null)
        setObserverJoined(!!data.host_state?.joined)
      }).catch(() => {
        toast.error('Observer session unavailable')
        navigate('/admin/interviews')
      })
      return
    }
    interviewsApi.getRound(roundId).then(setRound).catch(() => {
      toast.error('Round not found')
      navigate('/interviews')
    })
  }, [roundId, observerToken, navigate])

  // Prime browser TTS on the first user gesture (Chrome/Safari autoplay policy).
  useEffect(() => {
    if (observerMode) return
    const prime = () => unlockSpeech()
    window.addEventListener('pointerdown', prime, { once: true, capture: true })
    window.addEventListener('keydown', prime, { once: true, capture: true })
    return () => {
      window.removeEventListener('pointerdown', prime, { capture: true })
      window.removeEventListener('keydown', prime, { capture: true })
    }
  }, [observerMode])

  // Admin host: poll transcript while observing.
  useEffect(() => {
    if (!observerMode || !observerTokenRef.current) return
    const token = observerTokenRef.current
    const poll = () => {
      adminApi.getInterviewObserverSession(token).then(data => {
        setMessages(data.messages || [])
        setHostState((prev) => {
          const hs = data.host_state || null
          const a = JSON.stringify(prev ?? null)
          const b = JSON.stringify(hs ?? null)
          return a === b ? prev : hs
        })
        setObserverJoined(!!data.host_state?.joined)
        setRateTarget(data.rate_target || null)
      }).catch(() => {})
    }
    poll()
    const iv = setInterval(poll, 2500)
    return () => clearInterval(iv)
  }, [observerMode])

  const joinAsHost = async () => {
    const token = observerTokenRef.current
    if (!token) return
    if (!micOn) {
      toast.error('Enable microphone before joining live')
      await acquireMedia('both')
      if (!streamRef.current?.getAudioTracks?.().some(t => t.readyState === 'live')) return
    }
    setHostBusy(true)
    try {
      const res = await adminApi.observerJoinSession(token, 'Founder')
      setHostState(res.host_state)
      setObserverJoined(true)
      if (res.messages?.length) {
        setMessages(m => [...m, ...res.messages.filter(x => !m.some(y => y.id === x.id))])
      }
      toast.success('You joined live — AI is paused while you host')
    } catch {
      toast.error('Could not join session')
    } finally {
      setHostBusy(false)
    }
  }

  const sendAdminQuestion = async (textOverride, { spoken = false } = {}) => {
    const token = observerTokenRef.current
    const q = (textOverride ?? adminQuestion).trim()
    if (!token || !q) return
    if (spoken && !micOn) {
      toast.error('Enable your microphone to ask by voice')
      await acquireMedia('audio')
      return
    }
    setHostBusy(true)
    try {
      const res = await adminApi.observerAskQuestion(token, q, { spoken })
      setAdminQuestion('')
      if (res.message) setMessages(m => [...m, res.message])
      setHostState(res.host_state)
      toast.success(spoken ? 'Question sent (from your voice)' : 'Question sent to candidate')
    } catch {
      toast.error('Could not send question')
    } finally {
      setHostBusy(false)
    }
  }

  const adminVoiceAsk = async () => {
    if (hostBusy) return
    if (!micOn || !mediaStream) {
      toast.error('Allow microphone access to ask by voice')
      await acquireMedia('both')
      return
    }
    if (isListening) {
      stopListening()
      return
    }
    unlockSpeech()
    try {
      const result = await listenLive(mediaStream, {
        locale: 'en-US',
        silenceMs: 1600,
        minSpeechMs: 500,
        maxSilenceMs: 4000,
        onInterim: (txt) => setAdminQuestion(txt),
      })
      const text = (result?.transcript || result?.filtered_text || '').trim()
      if (text) {
        setAdminQuestion(text)
        await sendAdminQuestion(text, { spoken: true })
      } else {
        toast('No speech detected — try again or type your question', { icon: '🎤' })
      }
    } catch {
      toast.error('Could not capture your voice')
    }
  }

  const toggleHostMic = async () => {
    if (micOn) {
      mediaStream?.getAudioTracks().forEach(t => { t.enabled = false })
      setMicOn(false)
      return
    }
    await acquireMedia('audio')
  }

  const toggleHostCamera = async () => {
    if (cameraOn) {
      mediaStream?.getVideoTracks().forEach(t => { t.enabled = false })
      setCameraOn(false)
      return
    }
    await acquireMedia('video')
  }

  const submitAdminRating = async ({ quality, score, useAi = true } = {}) => {
    const token = observerTokenRef.current
    if (!token || !rateTarget?.candidate_message_id) return
    setHostBusy(true)
    try {
      const res = await adminApi.observerRateAnswer(token, {
        candidate_message_id: rateTarget.candidate_message_id,
        quality,
        score,
        use_ai: useAi,
        feedback: hostFeedback.trim() || undefined,
      })
      if (res.candidate_message) {
        setMessages(m => m.map(x => x.id === res.candidate_message.id ? res.candidate_message : x))
      }
      if (res.feedback_message) setMessages(m => [...m, res.feedback_message])
      setRateTarget(res.rate_target || null)
      setHostFeedback('')
      toast.success(`Rated ${Math.round(res.score_result?.score || 0)}/100`)
    } catch {
      toast.error('Could not save rating')
    } finally {
      setHostBusy(false)
    }
  }

  const toggleHostAi = async (enabled) => {
    const token = observerTokenRef.current
    if (!token) return
    setHostBusy(true)
    try {
      const res = await adminApi.observerSetAi(token, enabled)
      setHostState(res.host_state)
      if (res.messages?.length) {
        setMessages(m => {
          const ids = new Set(m.map(x => x.id))
          return [...m, ...res.messages.filter(x => !ids.has(x.id))]
        })
      }
      toast.success(enabled ? 'AI resumed — next question sent' : 'AI paused — you are hosting')
    } catch {
      toast.error('Could not update AI mode')
    } finally {
      setHostBusy(false)
    }
  }

  useEffect(() => {
    if (observerMode || !started) return
    const poll = () => {
      interviewsApi.getPendingJoinRequests(roundId)
        .then(d => setJoinRequests(d.requests || []))
        .catch(() => {})
    }
    poll()
    const iv = setInterval(poll, 12000)
    return () => clearInterval(iv)
  }, [roundId, started, observerMode])

  useEffect(() => {
    if (!endsAt || round?.paused_at) return
    const t = setInterval(() => {
      const left = Math.max(0, Math.floor((endsAt - Date.now()) / 1000))
      setTimeLeft(left)
    }, 1000)
    return () => clearInterval(t)
  }, [endsAt, round?.paused_at])

  // Pause timer when tab is hidden; resume (extends ends_at) when user returns.
  useEffect(() => {
    if (!roundId || !started || observerMode) return
    const onVis = () => {
      if (document.hidden) {
        interviewsApi.pauseRound(roundId).then((r) => setRound((prev) => ({ ...prev, ...r }))).catch(() => {})
      } else {
        interviewsApi.resumeRound(roundId).then((r) => setRound((prev) => ({ ...prev, ...r }))).catch(() => {})
      }
    }
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [roundId, started, observerMode])

  const cancelInterview = async () => {
    if (!await confirm({ message: 'Cancel this interview round?', danger: true, confirmLabel: 'Cancel round' })) return
    stopMediaStream(streamRef.current)
    streamRef.current = null
    setMediaStream(null)
    try {
      if (round?.campaign_id) {
        await interviewsApi.cancelCampaign(round.campaign_id)
        toast.success('Interview cancelled — confirmation email sent')
      }
    } catch {
      toast.error('Could not cancel interview')
    }
    navigate('/interviews')
  }

  // Visible "Back" exit. While a round is live, confirm first (the round keeps
  // running on the server — the candidate can resume from the campaign page).
  // Always releases the camera/mic so the device light turns off on exit.
  const exitToList = async (dest = '/interviews') => {
    if (started && !observerMode) {
      const ok = await confirm({
        title: 'Leave interview?',
        message:
          'Leave the interview? The round stays in progress — you can resume it from your interviews page. ' +
          'To finish and get your report, use "End round" instead.',
        confirmLabel: 'Leave',
      })
      if (!ok) return
    }
    stopRecording()
    stopMediaStream(streamRef.current)
    streamRef.current = null
    setMediaStream(null)
    navigate(dest)
  }

  const rescheduleRound = async () => {
    if (!rescheduleAt) {
      toast.error('Pick a date and time')
      return
    }
    try {
      await interviewsApi.scheduleRound(roundId, new Date(rescheduleAt).toISOString())
      toast.success('Round rescheduled — check your email')
      setShowReschedule(false)
      const updated = await interviewsApi.getRound(roundId)
      setRound(updated)
    } catch (e) {
      toast.error(e.response?.data?.error || 'Could not reschedule')
    }
  }

  useEffect(() => {
    if (!started || preflight) return
    const iv = setInterval(() => {
      interviewsApi.reportAv(roundId, micOn, cameraOn).then(res => {
        if (res.ended) {
          toast.error('Interview ended — camera/mic required')
          navigate(`/interviews/round/${roundId}/report`)
        } else if (res.action === 'warn') {
          toast('Enable mic and camera within 5 minutes', { icon: '⚠️' })
        }
      }).catch(() => {})
    }, 30000)
    return () => clearInterval(iv)
  }, [started, preflight, micOn, cameraOn, roundId, navigate])

  const beginInterview = async () => {
    if (!micOn || !cameraOn) {
      toast.error('Enable microphone and camera first')
      return
    }
    // User gesture — prime audio/TTS so the first interviewer line is heard.
    unlockSpeech()
    setPreflight(false)
    try {
      const data = await interviewsApi.startRound(roundId)
      setRound(data)
      const msgs = [...(data.messages || [])]
      if (data.intro) msgs.push(data.intro)
      if (data.first_question) msgs.push(data.first_question)
      setMessages(msgs)
      setStarted(true)
      if (data.speech_profile) {
        speechProfileRef.current = data.speech_profile
        setPersonaTitle(data.speech_profile.persona_title || '')
      }
      // Start recording once the interview is live
      if (streamRef.current) startRecording(streamRef.current)
      const voiceId = data.persona_voice_id
      const introText = data.intro?.content || ''
      const firstQ = data.first_question
      if (isPracticalMessage(firstQ)) {
        setPracticalMode(true)
        if (data.practical_lab_session_id) {
          setPracticalLab({ session_id: data.practical_lab_session_id, lab_url: `/lab/${data.practical_lab_session_id}` })
        } else {
          startPracticalLabInline().catch(() => {})
        }
      }
      // startRound() is async — the original click gesture is gone. Re-prime TTS
      // immediately before the first spoken line or Chrome stays silent.
      unlockSpeech()
      if (introText) await speakThenListen(introText, { autoListen: false, voiceId })
      if (firstQ?.content) {
        unlockSpeech()
        await speakThenListen(firstQ.content, {
          autoListen: !isPracticalMessage(firstQ), voiceId,
        })
      }
    } catch (e) {
      toast.error(e.response?.data?.error || 'Could not start')
    }
  }

  // text === '' (explicit, e.g. skip-on-silence) submits an empty answer the
  // engine scores as "skipped" and advances. A null/undefined text falls back
  // to the typed box and must be non-empty.
  //
  // WS5: pass { asQuestion: true } when the candidate is ASKING the interviewer
  // (Ask a question / Repeat that, or a barge-in classified as a question). The
  // backend then replies with a clarification and re-asks the SAME question
  // (res.advanced === false) instead of scoring + advancing. We read res.advanced
  // to decide whether a new question landed: when it's false we keep the current
  // question on screen and don't treat the turn as progress.
  const submitAnswer = async (text, {
    asQuestion = false,
    forceAdvance = false,
    audioUnclear = false,
    transcriptionConfidence = null,
    bargeIn = false,
  } = {}) => {
    const isSkip = text === '' && !forceAdvance
    const ans = (text === '' && forceAdvance) ? '' : (isSkip ? '' : (text ?? answer).trim())
    if (!forceAdvance && !audioUnclear && !isSkip && !ans) return
    // A candidate question is never a skip — guard so '' can't be sent as one.
    const isQuestion = asQuestion && !isSkip && !!ans
    // An answer (or skip) arrived — stop the silence countdown for this turn.
    clearSilenceTimer()
    awaitingAnswerRef.current = false
    setAnswer('')
    // Reset ask-mode now that we've consumed it for this turn.
    askModeRef.current = false
    setAskMode(false)
    if (audioUnclear) {
      unclearAudioCountRef.current += 1
    } else if (ans) {
      unclearAudioCountRef.current = 0
    }
    try {
      const res = await interviewsApi.sendMessage(roundId, ans, {
        input_type: isQuestion ? 'question' : 'answer',
        practice: practiceMode,
        force_advance: forceAdvance,
        user_skip: forceAdvance,
        audio_unclear: audioUnclear,
        transcription_confidence: transcriptionConfidence,
        barge_in: bargeIn,
      })
      if (res.host_mode || res.ai_paused) {
        setHostState(prev => ({ ...(prev || {}), joined: true, ai_enabled: false }))
      }
      if (res.speech_profile) {
        speechProfileRef.current = res.speech_profile
        setPersonaTitle(res.speech_profile.persona_title || '')
      }
      const thinkingDelayMs = res.thinking_delay_ms
      // advanced === false → the interviewer clarified / re-asked the SAME
      // question (a candidate question, a re-ask of a thin answer, or no new
      // question). Don't append a duplicate next_question or flip practical mode
      // in that case — the question already on screen still stands.
      const advanced = res.advanced !== false && !!res.next_question
      setCoaching(res.coaching || null)
      setMessages(m => [
        ...m,
        res.candidate_message,
        res.interviewer_reply,
        ...(advanced ? [res.next_question] : []),
      ].filter(Boolean))
      for (const m of [res.candidate_message, res.interviewer_reply, res.next_question].filter(Boolean)) {
        if (m?.id) processedHostMsgRef.current.add(m.id)
      }
      if (res.host_mode || res.ai_paused) {
        if (res.interviewer_reply?.content) {
          await speakThenListen(res.interviewer_reply.content, { autoListen: !practicalMode, thinkingDelayMs })
        } else {
          awaitingAnswerRef.current = true
          if (micOn && !practicalMode && !typingAnswer) {
            setTimeout(() => voiceAnswer(), 400)
          }
        }
        return
      }
      if (advanced) {
        const nextIsPractical = isPracticalMessage(res.next_question)
        setPracticalMode(nextIsPractical)
        if (nextIsPractical) {
          setPracticalLab(null)
          startPracticalLabInline().catch(() => {})
        } else {
          setPracticalLab(null)
        }
        // Speak the interviewer reply, then the new question, then re-open the
        // mic so the candidate can answer — continuing the hands-free loop.
        // Practical questions don't auto-listen (the candidate works in the lab).
        await speakThenListen(res.interviewer_reply?.content, {
          autoListen: false,
          thinkingDelayMs,
        })
        if (res.next_question?.content) {
          await speakThenListen(res.next_question.content, {
            autoListen: !nextIsPractical,
            thinkingDelayMs: res.thinking_delay_ms,
          })
        }
      } else {
        // Same question stands. Speak the clarification/reply, then re-open the
        // mic so the candidate can now answer the (unchanged) question — but
        // only when we're not in a practical question (they work in the lab).
        if (audioUnclear && unclearAudioCountRef.current >= 4 && !typingAnswer) {
          const now = Date.now()
          if (now - audioCutoutToastAtRef.current > 90_000) {
            audioCutoutToastAtRef.current = now
            toast('Audio keeps cutting out — try Type mode below if that\'s easier.', { icon: '⌨️', duration: 6000 })
          }
          if (unclearAudioCountRef.current >= 6) setTypingAnswer(true)
        }
        await speakThenListen(
          res.reply || res.interviewer_reply?.content,
          { autoListen: !practicalMode, thinkingDelayMs },
        )
      }
    } catch {
      toast.error('Could not send answer')
    }
  }

  // TRUE hands-free turn (FIX 1 — no send button). Opens the mic and lets the
  // candidate just SPEAK; when they STOP (DYNAMIC trailing silence detected by
  // the hook) the turn AUTO-SUBMITS and the AI responds. A second click of the
  // mic button (or Enter / the Done button) finalizes early as an accessibility
  // fallback. Uses browser SpeechRecognition only — zero paid STT.
  const voiceAnswer = async () => {
    if (isListening) {
      // Manual "done" affordance — finalize the current capture immediately.
      stopListening()
      return
    }
    // If the bot is mid-sentence, stop it first so STT doesn't transcribe TTS.
    cancelSpeech()
    const profile = resolveVoiceProfile(round?.persona_voice_id)
    // Arm the long skip-on-silence safety net for THIS turn: if the candidate
    // stays totally silent (never speaks at all), submit an empty (skipped)
    // answer so the round keeps moving. The SHORT trailing-silence window inside
    // listenLive handles the normal "they finished talking" auto-submit.
    armSilenceSkip()
    // Remember whether this turn was explicitly opened as a question (Ask /
    // Repeat). A barge-in also opens a turn; we additionally classify the
    // captured text below so an interrupting question still routes correctly.
    const openedAsQuestion = askModeRef.current
    // listenLive flips isListening itself and resolves on trailing silence.
    // WS1 — the silence window is now dynamic (grows with the answer, extends on
    // connector endings) and surfaces a countdown via onSilenceCountdown.
    const result = await listenLive(streamRef.current, {
      locale: profile.locale || 'en-IN',
      silenceMs: TURN_SILENCE_MS,
      minSpeechMs: 900,
      maxSilenceMs: 5000,
      perSentenceMs: 500,
      minWordsForSilence: 1,
      onInterim: (txt) => setAnswer(txt),
      onSilenceCountdown: (remaining, total) => {
        setSilenceCountdown(remaining == null ? null : { remaining, total })
      },
    })
    setSilenceCountdown(null)
    if (result?.reason === 'unsupported') {
      setTypingAnswer(true)
      toast('Voice input is not supported in this browser — switched to Type mode', { icon: '⌨️' })
      return
    }
    const text = (result?.transcript || result?.filtered_text || '').trim()
    // If the skip-silence timer (or a manual skip / barge-in) already resolved
    // this turn, awaitingAnswerRef is false — don't submit again even if late
    // STT text arrives. Closes the double-submit race.
    if (!awaitingAnswerRef.current) {
      setAnswer('')
      return
    }
    if (text) {
      const clarity = assessTranscriptClarity(text, result)
      if (clarity === 'unclear' && !openedAsQuestion) {
        await submitAnswer(text, {
          audioUnclear: true,
          transcriptionConfidence: result?.confidence ?? null,
          bargeIn: bargedInRef.current,
        })
        bargedInRef.current = false
        return
      }
      const asQuestion = openedAsQuestion || looksLikeQuestion(text)
      await submitAnswer(text, { asQuestion, bargeIn: bargedInRef.current })
      bargedInRef.current = false
    } else if (result?.reason === 'silence' || result?.reason === 'manual') {
      setAnswer('')
    } else {
      // Recognizer ended with nothing captured (e.g. the candidate clicked Done
      // before speaking). Don't submit an empty answer here — leave the
      // skip-silence timer running so a truly idle turn still advances the round.
      setAnswer('')
    }
  }
  voiceAnswerRef.current = voiceAnswer

  // WS5 — explicit "Ask a question" / "Repeat that" control. Arms ask-mode and
  // opens the mic; the captured utterance is sent with input_type:'question'.
  // For "Repeat that" we can submit immediately without waiting for speech.
  const askQuestion = (prefill) => {
    if (observerMode) return
    cancelSpeech()
    if (prefill) {
      // One-tap "Repeat that" — no need to speak; ask the engine to repeat.
      awaitingAnswerRef.current = true
      submitAnswer(prefill, { asQuestion: true })
      return
    }
    askModeRef.current = true
    setAskMode(true)
    if (isListening) {
      // Already capturing — just let the in-flight turn finalize as a question.
      return
    }
    voiceAnswer()
  }

  // Speak a bot line, then automatically open the mic for the candidate's reply.
  // This is the heart of the hands-free voice loop.
  const speakThenListen = async (text, { autoListen = true, voiceId, thinking = true, thinkingDelayMs } = {}) => {
    if (!text) {
      if (autoListen && !observerMode && !practicalMode && !isListeningRef.current) {
        voiceAnswer()
      }
      return
    }
    bargedInRef.current = false
    const sp = speechProfileRef.current
    if (thinking) {
      const base = thinkingDelayMs ?? sp?.thinking_base_ms ?? 400
      const jitter = 120 + Math.random() * 200
      setIsThinking(true)
      setAiCaption(`${round?.persona_name || 'Interviewer'} is thinking…`)
      await new Promise(r => setTimeout(r, base + jitter))
      setIsThinking(false)
    }
    setAiCaption(text)
    // Interviewer muted — skip TTS entirely, but keep the loop human: show the
    // caption, give the candidate a beat to read it, then open the mic.
    if (interviewerMutedRef.current) {
      await new Promise(r => setTimeout(r, Math.min(4000, 900 + text.length * 28)))
      if (autoListen && !observerMode && !isListeningRef.current && !bargedInRef.current) {
        voiceAnswer()
      }
      return
    }
    const speechOpts = sp ? {
      rate: sp.rate,
      pitch: sp.pitch,
      pauseQuestionMs: sp.pause_question_ms,
      pausePeriodMs: sp.pause_period_ms,
    } : {}
    // Re-prime before every speak — long thinking delays / awaits drop the
    // browser's user-gesture unlock and leave speechSynthesis paused.
    unlockSpeech()
    const { spoken } = await speak(text, voiceId ?? round?.persona_voice_id, speechOpts) || {}
    if (spoken === false && !voiceUnavailableToastRef.current) {
      voiceUnavailableToastRef.current = true
      toast('Voice unavailable — read the caption, then tap the mic when ready.', { icon: '🔊' })
    }
    if (autoListen && !observerMode && !isListeningRef.current && !bargedInRef.current) {
      voiceAnswer()
    }
  }
  speakThenListenRef.current = speakThenListen

  // Candidate: sync admin/host messages (founder join, manual questions, AI resume).
  useEffect(() => {
    if (!started || observerMode || !roundId) return
    const syncHost = async () => {
      try {
        const data = await interviewsApi.getRound(roundId, { silent: true })
        const hs = data.host_state || null
        setHostState((prev) => {
          const a = JSON.stringify(prev ?? null)
          const b = JSON.stringify(hs ?? null)
          return a === b ? prev : hs
        })
        const incoming = data.messages || []
        setMessages(prev => {
          const ids = new Set(prev.map(m => m.id))
          const added = incoming.filter(m => !ids.has(m.id))
          return added.length ? [...prev, ...added] : prev
        })
        for (const m of incoming) {
          if (!m?.id || processedHostMsgRef.current.has(m.id)) continue
          const meta = m.metadata || {}
          const isAdminLine = meta.admin_host
          const isNewQuestion = m.message_type === 'question' && m.role === 'interviewer'
          const isWelcome = meta.event === 'admin_welcome'
          const isHandoff = meta.event === 'ai_resume'
          if (!isWelcome && !isHandoff && !(isNewQuestion && m.content)) continue
          processedHostMsgRef.current.add(m.id)
          if (isWelcome && m.content) {
            cancelSpeechRef.current()
            setAiCaption((prev) => (prev === m.content ? prev : m.content))
            await speakRef.current(m.content, personaVoiceIdRef.current)
          } else if (isHandoff && m.content) {
            cancelSpeechRef.current()
            setAiCaption((prev) => (prev === m.content ? prev : m.content))
            await speakThenListenRef.current?.(m.content, { autoListen: false, voiceId: personaVoiceIdRef.current })
          } else if (isNewQuestion && m.content) {
            cancelSpeechRef.current()
            const hostLabel = hs?.display_name || meta.asked_by || 'Guest interviewer'
            if (isAdminLine) setPersonaTitle(hostLabel)
            const caption = isAdminLine ? `${hostLabel}: ${m.content}` : m.content
            setAiCaption((prev) => (prev === caption ? prev : caption))
            awaitingAnswerRef.current = true
            await speakThenListenRef.current?.(m.content, {
              autoListen: !practicalModeRef.current,
              voiceId: personaVoiceIdRef.current,
            })
          }
        }
      } catch {
        /* polling best-effort */
      }
    }
    syncHost()
    const iv = setInterval(syncHost, 3000)
    return () => clearInterval(iv)
    // Deps are intentionally minimal: the poll interval is created ONCE per
    // interview and reads the latest practicalMode / persona voice from refs, so
    // it never tears down + double-fires mid-interview (the "refresh" symptom).
  }, [started, observerMode, roundId])

  // Toggle interviewer TTS. When muting mid-sentence, cut the current utterance.
  const toggleInterviewerMute = () => {
    setInterviewerMuted((prev) => {
      const next = !prev
      interviewerMutedRef.current = next
      if (next) cancelSpeechRef.current()
      toast(next ? 'Interviewer muted — captions still show' : 'Interviewer voice on', {
        icon: next ? '🔇' : '🔊',
      })
      return next
    })
  }

  // ---- skip-on-silence -------------------------------------------------
  const clearSilenceTimer = () => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current)
      silenceTimerRef.current = null
    }
  }

  // Arm a timer: if the candidate produces no speech within the window, submit
  // an empty answer so the engine marks it "skipped" and moves on, keeping the
  // round on pace to use the fixed time.
  const armSilenceSkip = () => {
    clearSilenceTimer()
    awaitingAnswerRef.current = true
    silenceTimerRef.current = setTimeout(() => {
      // Only skip if they truly stayed silent (no interim text captured yet).
      if (!awaitingAnswerRef.current) return
      const captured = (answerRef.current || '').trim()
      if (captured) return // they're mid-answer — let it finish naturally
      stopListening()
      toast('No response — moving on', { icon: '⏭️' })
      submitAnswer('', { forceAdvance: true })
    }, SILENCE_SKIP_MS)
  }

  const nextQuestion = () => {
    if (observerMode) return
    clearSilenceTimer()
    stopListening()
    cancelSpeech()
    toast('Moving to next question', { icon: '⏭️' })
    submitAnswer('', { forceAdvance: true })
  }

  // In-room voice switch: persist the choice (handled by the hook) and give a
  // short spoken preview so the candidate hears the new voice immediately.
  const changeVoice = (voiceURI) => {
    cancelSpeech()
    selectVoice(voiceURI)
    // Preview only when idle so we don't talk over an open question/answer.
    if (!isListeningRef.current && !awaitingAnswerRef.current) {
      // speak() reads the latest selection via a ref, so the preview already
      // uses the just-picked voice.
      setTimeout(() => speak("Okay, I'll use this voice from now on.", round?.persona_voice_id), 0)
    }
  }

  // Keep the barge-in action pointing at the latest closure. When the VAD
  // detects the candidate talking over the bot, stop the bot and start
  // capturing their answer immediately.
  useEffect(() => {
    bargeInHandlerRef.current = () => {
      cancelSpeechRef.current()
      if (!isListeningRef.current) {
        voiceAnswerRef.current?.() // self-arms skip-on-silence
      }
    }
  })

  useEffect(() => {
    if (!started || !practicalMode || practicalLab?.session_id || labLoading) return
    startPracticalLabInline().catch(() => {})
  }, [started, practicalMode, practicalLab?.session_id, labLoading]) // eslint-disable-line react-hooks/exhaustive-deps

  // Hands-free loop: when the interview is live and idle, keep the mic open so
  // the candidate never needs a Send button — speak, pause, auto-submit.
  useEffect(() => {
    if (!started || preflight || observerMode || practicalMode || typingAnswer) return
    if (isSpeaking || isListening) return
    if (!awaitingAnswerRef.current || !micOn) return
    const t = setTimeout(() => {
      if (!isSpeakingRef.current && !isListeningRef.current && awaitingAnswerRef.current) {
        voiceAnswerRef.current?.()
      }
    }, 400)
    return () => clearTimeout(t)
    // voiceAnswer is called via voiceAnswerRef (always latest), so it is
    // deliberately not a dependency — listing it would re-arm this timer every
    // render and fight the hands-free loop.
  }, [started, preflight, observerMode, practicalMode, typingAnswer, isSpeaking, isListening, micOn])

  const startRecording = (stream) => {
    if (!stream || !window.MediaRecorder) return
    try {
      const mimeType = ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm', 'audio/webm'].find(
        t => MediaRecorder.isTypeSupported(t)
      )
      if (!mimeType) return
      recChunksRef.current = []
      const rec = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 500_000 })
      rec.ondataavailable = e => { if (e.data?.size > 0) recChunksRef.current.push(e.data) }
      rec.onstop = () => {
        if (recChunksRef.current.length > 0) setRecordingReady(true)
      }
      rec.start(5000) // collect in 5-second chunks
      recorderRef.current = rec
    } catch { /* MediaRecorder not supported — silently skip */ }
  }

  const stopRecording = () => {
    try { recorderRef.current?.stop() } catch { /* ignore */ }
  }

  const downloadRecording = () => {
    const chunks = recChunksRef.current
    if (!chunks.length) return
    const blob = new Blob(chunks, { type: chunks[0].type || 'video/webm' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `interview-${roundId}-recording.webm`
    a.click()
    URL.revokeObjectURL(url)
  }

  const endInterview = async (opts = {}) => {
    const { goNextRound = false } = opts
    clearSilenceTimer()
    awaitingAnswerRef.current = false
    stopListening()
    cancelSpeech()
    stopRecording()
    stopMediaStream(streamRef.current)
    streamRef.current = null
    setMediaStream(null)
    try {
      const res = await interviewsApi.endRound(roundId)
      if (res.closing_remark) {
        setIsThinking(false)
        setAiCaption(res.closing_remark)
        const sp = speechProfileRef.current
        await speak(res.closing_remark, round?.persona_voice_id, sp ? {
          rate: sp.rate, pitch: sp.pitch,
          pauseQuestionMs: sp.pause_question_ms,
          pausePeriodMs: sp.pause_period_ms,
        } : {})
      }
      if (goNextRound && res.next_round?.id) {
        toast.success('Moving to the next interview round')
        navigate(`/interviews/room/${res.next_round.id}`)
        return
      }
      toast.success(res.passed ? 'Round passed!' : 'Round complete — see report')
      navigate(`/interviews/round/${roundId}/report`, { state: { report: res.report } })
    } catch {
      navigate(`/interviews/campaign/${round?.campaign_id || ''}`)
    }
  }

  const finishAndNextRound = async () => {
    if (observerMode) return
    if (!await confirm({ message: 'End this round and go to the next one in your campaign?', confirmLabel: 'End & next' })) return
    endInterview({ goNextRound: true })
  }

  const extend = async () => {
    try {
      const data = await interviewsApi.extendRound(roundId, 10)
      setRound(data)
      toast.success('+10 minutes for Q&A')
    } catch {
      toast.error('Extension not available')
    }
  }

  const launchPracticalLab = async () => {
    if (practicalLab?.lab_url) {
      window.open(practicalLab.lab_url, '_blank', 'noopener,noreferrer')
      return
    }
    setLabLoading(true)
    try {
      const lab = await interviewsApi.startPracticalLab(roundId)
      if (lab.error) {
        toast.error(lab.error)
        return
      }
      setPracticalLab(lab)
      toast.success('Lab environment ready')
      window.open(lab.lab_url, '_blank', 'noopener,noreferrer')
    } catch (e) {
      toast.error(e.response?.data?.error || 'Could not start lab')
    } finally {
      setLabLoading(false)
    }
  }

  // Validate an inline practical command/code answer. The backend grades it with
  // the same free engines the labs use and returns { validated, feedback }. We
  // surface the verdict in the live transcript as the interviewer's response so
  // the candidate sees real feedback; on a pass, their next answer is scored with
  // the practical credit automatically (the backend stamps the round).
  const validatePracticalAnswer = async (answer) => {
    try {
      const res = await interviewsApi.validatePractical(roundId, answer)
      if (res?.error) {
        toast.error(res.error)
        return res
      }
      if (res?.feedback) {
      setMessages((m) => [
        ...m,
        {
          id: `practical-cmd-${Date.now()}`,
          role: 'candidate',
          message_type: 'command',
          content: answer,
        },
        {
          id: `practical-fb-${Date.now() + 1}`,
          role: 'interviewer',
          message_type: 'practical_feedback',
          content: res.feedback,
        },
      ])
      // Speak the feedback so the loop stays conversational (browser TTS, free).
      speakThenListen(res.feedback, { autoListen: false })
      }
      return res
    } catch (e) {
      toast.error(e.response?.data?.error || 'Could not validate practical answer')
      throw e
    }
  }

  const fmt = (s) => {
    if (s == null) return '--:--'
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  const isPracticalMessage = (m) => {
    if (!m) return false
    if (m.message_type === 'practical') return true
    const k = m.metadata?.kind
    if (k === 'live_coding' || k === 'live_coding_followup') return true
    return Boolean(m.practical_config?.kind)
  }

  const activePracticalConfig = practicalMode
    ? [...messages].reverse().find(isPracticalMessage)?.practical_config || null
    : null

  const startPracticalLabInline = async () => {
    try {
      const lab = await interviewsApi.startPracticalLab(roundId)
      if (lab?.error) {
        toast.error(lab.error)
        return lab
      }
      if (lab?.inline_only) return lab
      setPracticalLab(lab)
      return lab
    } catch (e) {
      toast.error(e.response?.data?.error || 'Could not start practical lab')
      throw e
    }
  }

  if (!round) return <p className="text-surface-500 p-8">Loading room…</p>

  if (observerMode) {
    const aiOn = hostState?.ai_enabled !== false
    return (
      <div className="h-[calc(100vh-4rem)] flex flex-col bg-surface-950">
        <header className="px-4 py-3 border-b border-surface-800 bg-amber-500/10 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-amber-300 font-medium">
              Live host — {round.title}
            </p>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={toggleHostMic}
                disabled={mediaLoading}
                className={`text-xs px-2 py-1 rounded-lg border inline-flex items-center gap-1 ${
                  micOn ? 'border-emerald-500/40 text-emerald-300' : 'border-surface-700 text-surface-400'
                }`}
                title="Microphone"
              >
                {micOn ? <Mic size={12} /> : <MicOff size={12} />}
                Mic
              </button>
              <button
                type="button"
                onClick={toggleHostCamera}
                disabled={mediaLoading}
                className={`text-xs px-2 py-1 rounded-lg border inline-flex items-center gap-1 ${
                  cameraOn ? 'border-emerald-500/40 text-emerald-300' : 'border-surface-700 text-surface-400'
                }`}
                title="Camera (optional)"
              >
                {cameraOn ? <Video size={12} /> : <VideoOff size={12} />}
                Cam
              </button>
              {!micOn && !cameraOn && (
                <button
                  type="button"
                  onClick={() => acquireMedia('both')}
                  disabled={mediaLoading}
                  className="btn-primary text-[10px] py-1 px-2"
                >
                  Allow mic & camera
                </button>
              )}
            </div>
          </div>
          {mediaError && (
            <p className="text-[10px] text-amber-200 bg-amber-500/10 rounded px-2 py-1">{mediaError}</p>
          )}
          {!observerJoined ? (
            <button
              type="button"
              disabled={hostBusy || !micOn}
              onClick={joinAsHost}
              className="btn-primary text-xs py-1.5 px-3 disabled:opacity-50"
            >
              Join session & welcome candidate
            </button>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300">
                Hosting as {hostState?.display_name || 'Founder'}
              </span>
              <span className={`text-[10px] px-2 py-0.5 rounded-full ${aiOn ? 'bg-indigo-500/20 text-indigo-300' : 'bg-surface-700 text-surface-400'}`}>
                AI {aiOn ? 'on' : 'paused'}
              </span>
              <button
                type="button"
                disabled={hostBusy}
                onClick={() => toggleHostAi(!aiOn)}
                className="btn-secondary text-[10px] py-1 px-2"
              >
                {aiOn ? 'Pause AI — I will ask' : 'Hand back to AI'}
              </button>
            </div>
          )}
          {!micOn && (
            <p className="text-[10px] text-surface-400">
              Allow microphone access to join and ask questions by voice (same as the candidate flow).
            </p>
          )}
        </header>
        {cameraOn && mediaStream && (
          <div className="px-4 pt-3">
            <div className="aspect-video max-h-36 rounded-lg overflow-hidden border border-surface-800">
              <InterviewVideoPreview
                stream={mediaStream}
                cameraOn={cameraOn}
                backgroundId="none"
                className="w-full h-full"
                mirror
              />
            </div>
          </div>
        )}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
          {messages.map(m => (
            <div
              key={m.id}
              className={`text-xs rounded-lg p-2 border ${
                m.role === 'interviewer'
                  ? 'bg-indigo-500/10 border-indigo-500/20 text-indigo-100'
                  : m.role === 'candidate'
                    ? 'bg-surface-900 border-surface-800 text-surface-200 ml-6'
                    : 'bg-amber-500/10 border-amber-500/20 text-amber-200 text-center'
              }`}
            >
              <span className="text-[10px] uppercase opacity-60">
                {m.metadata?.admin_host ? (m.metadata?.asked_by || 'host') : m.role}
              </span>
              <p className="mt-0.5 whitespace-pre-wrap">{m.content}</p>
              {m.score != null && (
                <p className="text-[10px] text-surface-500 mt-1">
                  Score: {Math.round(m.score)}
                  {m.metadata?.admin_rated && m.metadata?.admin_rater && (
                    <span className="text-amber-400 ml-1">· rated by {m.metadata.admin_rater}</span>
                  )}
                </p>
              )}
            </div>
          ))}
        </div>
        {observerJoined && rateTarget && (
          <div className="px-4 py-3 border-t border-indigo-500/30 bg-indigo-500/5 space-y-2">
            <div className="flex items-center gap-1.5 text-xs text-indigo-200 font-medium">
              <Star size={13} className="text-amber-400" />
              Rate latest answer — same scoring model as AI
            </div>
            {rateTarget.question_preview && (
              <p className="text-[10px] text-surface-500 line-clamp-2">
                Q: {rateTarget.question_preview}
              </p>
            )}
            <p className="text-xs text-surface-300 bg-surface-950/60 rounded-lg px-2 py-1.5 line-clamp-3">
              {rateTarget.answer_preview}
            </p>
            {rateTarget.ai_suggestion && (
              <p className="text-[10px] text-indigo-300">
                AI suggests{' '}
                <span className="font-semibold">{Math.round(rateTarget.ai_suggestion.score || 0)}/100</span>
                {' '}({rateTarget.ai_suggestion.quality || 'adequate'})
                {rateTarget.ai_suggestion.feedback && (
                  <span className="text-surface-400"> — {rateTarget.ai_suggestion.feedback.slice(0, 120)}</span>
                )}
              </p>
            )}
            <textarea
              value={hostFeedback}
              onChange={e => setHostFeedback(e.target.value)}
              rows={2}
              placeholder="Optional feedback to candidate (defaults to AI wording)"
              className="w-full text-xs rounded-lg bg-surface-950 border border-surface-700 px-2 py-1.5 text-white"
            />
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                disabled={hostBusy}
                onClick={() => submitAdminRating({ quality: 'strong', useAi: false })}
                className="text-[10px] py-1.5 px-2.5 rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
              >
                Strong
              </button>
              <button
                type="button"
                disabled={hostBusy}
                onClick={() => submitAdminRating({ quality: 'adequate', useAi: false })}
                className="text-[10px] py-1.5 px-2.5 rounded-lg bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
              >
                Adequate
              </button>
              <button
                type="button"
                disabled={hostBusy}
                onClick={() => submitAdminRating({ quality: 'brief', useAi: false })}
                className="text-[10px] py-1.5 px-2.5 rounded-lg bg-surface-700/50 text-surface-300 border border-surface-600"
              >
                Brief
              </button>
              <button
                type="button"
                disabled={hostBusy}
                onClick={() => submitAdminRating({ quality: 'weak', useAi: false })}
                className="text-[10px] py-1.5 px-2.5 rounded-lg bg-red-500/15 text-red-300 border border-red-500/25"
              >
                Weak
              </button>
              <button
                type="button"
                disabled={hostBusy}
                onClick={() => submitAdminRating({ useAi: true })}
                className="text-[10px] py-1.5 px-2.5 rounded-lg btn-primary"
              >
                Accept AI score
              </button>
            </div>
          </div>
        )}
        {observerJoined && (
          <div className="p-4 border-t border-surface-800 space-y-2 bg-surface-900/80">
            {(isListening || interimTranscript) && (
              <p className="text-[10px] text-emerald-400 flex items-center gap-1">
                <Mic size={11} className="animate-pulse" /> Listening… {interimTranscript}
              </p>
            )}
            <textarea
              value={adminQuestion}
              onChange={e => setAdminQuestion(e.target.value)}
              rows={2}
              placeholder="Type a question — or tap the mic and speak"
              className="w-full text-sm rounded-lg bg-surface-950 border border-surface-700 px-3 py-2 text-white"
            />
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={hostBusy || !micOn}
                onClick={adminVoiceAsk}
                className={`text-xs py-2 px-4 inline-flex items-center gap-1.5 ${
                  isListening ? 'btn-secondary ring-2 ring-emerald-500/50' : 'btn-primary'
                }`}
              >
                {isListening ? <Loader2 size={14} className="animate-spin" /> : <Mic size={14} />}
                {isListening ? 'Done speaking' : 'Ask by voice'}
              </button>
              <button
                type="button"
                disabled={hostBusy || !adminQuestion.trim()}
                onClick={() => sendAdminQuestion()}
                className="btn-secondary text-xs py-2 px-4"
              >
                Send typed question
              </button>
            </div>
            {aiOn && (
              <p className="text-[10px] text-surface-500">Your question pauses the AI until you hand back control.</p>
            )}
          </div>
        )}
      </div>
    )
  }

  if (preflight) {
    return (
      <>
      <div className="max-w-lg mx-auto p-8 space-y-6 animate-fade-in">
        <div className="flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => exitToList(round.campaign_id ? `/interviews/campaign/${round.campaign_id}` : '/interviews')}
            className="text-xs text-surface-500 hover:text-white inline-flex items-center gap-1"
          >
            <ArrowLeft size={14} /> Back
          </button>
          <button type="button" onClick={cancelInterview} className="text-xs text-red-400 hover:text-red-300 inline-flex items-center gap-1">
            <X size={14} /> Cancel
          </button>
        </div>
        <PageHeader
          eyebrow="AI Interview Studio"
          title="Pre-interview check"
          subtitle={`${round.title} with ${round.persona_name}`}
        />
        {round.is_sample && (
          <p className="text-xs text-cyan-400 font-medium -mt-4">Free sample — {round.duration_minutes} minutes only</p>
        )}
        {!speechSupported && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100" role="status">
            <strong>Voice input unavailable</strong> — Firefox, Safari, and some mobile browsers do not support
            live speech recognition. Type mode is enabled automatically; you can still read the interviewer captions.
          </div>
        )}
        {speechSupported && !ttsSupported && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100" role="status">
            <strong>Interviewer audio unavailable</strong> — your browser cannot play synthesized speech.
            Questions appear as on-screen captions; answer with the mic or Type mode.
          </div>
        )}
        <ul className="text-xs text-surface-400 space-y-2 list-disc pl-4">
          <li>Quiet room, headphones recommended</li>
          <li>Microphone and camera must stay on</li>
          <li>5-minute grace if either is disabled — then session ends</li>
          <li>
            Round duration: {round.duration_minutes} minutes
            {!round.is_sample && ' (+10 optional extension)'}
          </li>
          {round.is_sample && (
            <li>This is a one-time preview — subscribe for full multi-round interviews</li>
          )}
          <li>Transcripts are stored for feedback; video is not recorded on our servers</li>
        </ul>
        <label className="flex items-start gap-2 text-xs text-surface-400 cursor-pointer">
          <input
            type="checkbox"
            checked={consentAccepted}
            onChange={e => setConsentAccepted(e.target.checked)}
            className="mt-0.5 rounded"
          />
          <span>
            I agree to camera/mic use, transcript processing, and the{' '}
            <a href="/terms" target="_blank" rel="noreferrer" className="text-indigo-400 hover:underline">Terms</a>
            {' '}and{' '}
            <a href="/privacy" target="_blank" rel="noreferrer" className="text-indigo-400 hover:underline">Privacy Policy</a>
            {' '}for AI Interview Studio.
          </span>
        </label>
        <div className="aspect-video rounded-xl overflow-hidden border border-surface-700">
          <InterviewVideoPreview
            stream={mediaStream}
            cameraOn={cameraOn}
            backgroundId={backgroundId}
            onBackgroundChange={setBackgroundId}
            className="w-full h-full min-h-[200px]"
            mirror
            placeholder="Click Allow below — your browser will ask to use camera & mic"
          />
        </div>
        {micOn && mediaStream && (
          <div className="space-y-1.5">
            <p className="text-xs text-surface-400 flex items-center gap-1.5">
              <Mic size={12} className="text-emerald-400" />
              Microphone level — speak to test
            </p>
            <div className="flex items-end gap-1 h-6">
              {Array.from({ length: 8 }, (_, i) => {
                const threshold = i / 8
                const active = micLevel > threshold
                return (
                  <div
                    key={i}
                    style={{ height: `${50 + i * 7}%` }}
                    className={`flex-1 rounded-sm transition-colors duration-75 ${
                      active
                        ? i < 5 ? 'bg-emerald-400' : i < 7 ? 'bg-amber-400' : 'bg-red-400'
                        : 'bg-surface-700'
                    }`}
                  />
                )
              })}
            </div>
          </div>
        )}
        {(audioDevices.length > 1 || videoDevices.length > 1) && (
          <div className="grid sm:grid-cols-2 gap-2">
            {audioDevices.length > 1 && (
              <label className="text-xs text-surface-400 space-y-1">
                <span className="flex items-center gap-1"><Mic size={12} /> Microphone</span>
                <select
                  value={selectedAudioId}
                  onChange={e => { setSelectedAudioId(e.target.value); if (micOn) acquireMedia('audio') }}
                  className="input-field text-xs w-full"
                >
                  <option value="">System default</option>
                  {audioDevices.map(d => (
                    <option key={d.deviceId} value={d.deviceId}>{d.label || `Mic ${d.deviceId.slice(0, 6)}`}</option>
                  ))}
                </select>
              </label>
            )}
            {videoDevices.length > 1 && (
              <label className="text-xs text-surface-400 space-y-1">
                <span className="flex items-center gap-1"><Video size={12} /> Camera</span>
                <select
                  value={selectedVideoId}
                  onChange={e => { setSelectedVideoId(e.target.value); if (cameraOn) acquireMedia('video') }}
                  className="input-field text-xs w-full"
                >
                  <option value="">System default</option>
                  {videoDevices.map(d => (
                    <option key={d.deviceId} value={d.deviceId}>{d.label || `Camera ${d.deviceId.slice(0, 6)}`}</option>
                  ))}
                </select>
              </label>
            )}
          </div>
        )}
        {mediaError && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100 space-y-1.5">
            <p>{mediaError}</p>
            {(mediaError.includes('blocked') || mediaError.includes('Allow')) && (
              <p className="text-amber-300/80">
                Chrome/Edge: click the <strong>lock icon</strong> in the address bar → Site settings → Camera/Microphone → Allow → reload.
                Safari: Settings → Safari → Camera &amp; Microphone → Allow.
              </p>
            )}
            <button
              type="button"
              onClick={enableMedia}
              disabled={mediaLoading}
              className="text-amber-300 underline hover:text-amber-100 disabled:opacity-50 inline-flex items-center gap-1"
            >
              {mediaLoading && <Loader2 size={12} className="animate-spin" />}
              Try again
            </button>
          </div>
        )}
        {ttsSupported && (
          <div className="space-y-1.5">
            <p className="text-xs text-surface-400 flex items-center gap-1.5">
              <Volume2 size={12} className="text-indigo-400" />
              Interviewer voice — most natural voices first. You can also change this mid-interview.
            </p>
            <div className="flex items-center gap-2">
              <select
                value={selectedVoiceURI}
                onChange={e => selectVoice(e.target.value)}
                className="input-field text-xs flex-1"
              >
                <option value="">Recommended ({round.persona_name}'s accent)</option>
                {naturalVoices('en-US').map(v => (
                  <option key={v.voiceURI} value={v.voiceURI}>{v.name} ({v.lang})</option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => {
                  // ALWAYS produce sound on Test — even before the async
                  // voiceschanged event has populated getVoices(). unlockSpeech()
                  // primes the (possibly paused) engine after this user gesture,
                  // and speak() falls back to the browser default voice when the
                  // list is still empty, so the candidate always hears something.
                  unlockSpeech()
                  speak('Hi, this is how I will sound during your interview.', round.persona_voice_id)
                }}
                className="btn-secondary text-xs whitespace-nowrap inline-flex items-center gap-1"
                title="Preview voice"
              >
                <Volume2 size={12} /> Test
              </button>
            </div>
            <p className="text-[10px] text-surface-600">
              {browserVoices.length > 0
                ? 'Voices are free and run in your browser. Pick a “Natural”/“Neural” one if available — they sound the most human.'
                : 'Voices are free and run in your browser. Tap Test to hear your device’s default voice — more options appear here once your browser finishes loading them.'}
            </p>
          </div>
        )}
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={enableMedia}
            disabled={mediaLoading}
            className="interview-media-btn interview-media-btn-primary flex-1 min-w-[160px]"
          >
            {mediaLoading ? <Loader2 size={16} className="animate-spin" /> : <Video size={16} />}
            Enable camera & mic
          </button>
          <button
            type="button"
            onClick={enableMic}
            disabled={mediaLoading || micOn}
            className={`interview-media-btn ${micOn ? 'interview-media-btn-active' : ''}`}
          >
            {micOn ? <Mic size={16} /> : <MicOff size={16} />}
            {micOn ? 'Mic on' : 'Mic only'}
          </button>
          <button
            type="button"
            onClick={enableCamera}
            disabled={mediaLoading || cameraOn}
            className={`interview-media-btn ${cameraOn ? 'interview-media-btn-active' : ''}`}
          >
            {cameraOn ? <Video size={16} /> : <VideoOff size={16} />}
            {cameraOn ? 'Camera on' : 'Camera only'}
          </button>
          {!round.is_sample && (
            <button type="button" onClick={() => setShowReschedule(s => !s)} className="interview-media-btn">
              <Calendar size={16} /> Reschedule
            </button>
          )}
        </div>
        {showReschedule && (
          <div className="flex gap-2 items-center">
            <input
              type="datetime-local"
              value={rescheduleAt}
              onChange={e => setRescheduleAt(e.target.value)}
              className="input-field text-xs flex-1"
            />
            <button type="button" onClick={rescheduleRound} className="btn-secondary text-xs whitespace-nowrap">
              Save
            </button>
          </div>
        )}
        <button
          type="button"
          disabled={!micOn || !cameraOn || !consentAccepted}
          onClick={beginInterview}
          className="w-full interview-media-btn interview-media-btn-primary py-3.5 text-base disabled:opacity-40"
        >
          I'm ready — start interview
        </button>
      </div>
      </>
    )
  }

  return (
    <>
    <div className="h-[calc(100vh-4rem)] flex flex-col bg-surface-950">
      <header className="flex items-center justify-between px-4 py-2 border-b border-surface-800 bg-surface-900/80 gap-2 overflow-x-auto">
        <div className="min-w-0 shrink">
          <button
            type="button"
            onClick={() => exitToList('/interviews')}
            className="text-[10px] text-surface-500 hover:text-white inline-flex items-center gap-1"
          >
            <ArrowLeft size={12} /> Back to interviews
          </button>
          <p className="text-xs text-indigo-400">{round.persona_name}</p>
          <p className="text-sm font-medium text-white truncate">{round.title}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <label className="flex items-center gap-1 text-[10px] text-surface-400" title="Change interviewer voice anytime">
            <Volume2 size={12} className="text-indigo-400" />
            <select
              value={selectedVoiceURI}
              onChange={e => changeVoice(e.target.value)}
              className="bg-surface-800 border border-surface-700 rounded text-[11px] text-surface-200 py-1 px-1.5 max-w-[160px]"
            >
              <option value="">Recommended voice</option>
              {(naturalVoices('en-US').length ? naturalVoices('en-US') : browserVoices).map(v => (
                <option key={v.voiceURI} value={v.voiceURI}>
                  {v.name} ({v.lang})
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => {
                unlockSpeech()
                speak('Voice check — I will use this voice for the rest of the interview.', round?.persona_voice_id)
              }}
              className="text-[10px] text-indigo-300 hover:text-white px-1"
              title="Test voice"
            >
              Test
            </button>
          </label>
          <span className="text-sm font-mono text-amber-400 flex items-center gap-1">
            <Clock size={14} /> {fmt(timeLeft)}
          </span>
          <div
            className={`interview-live-call-badge ${isListening ? 'is-your-turn' : isSpeaking ? 'is-speaking' : ''}`}
            title="Live two-way voice interview"
          >
            <span className="interview-live-dot" aria-hidden />
            <span>Live</span>
            {isListening && <span className="interview-live-sub">Your turn</span>}
            {isSpeaking && !isListening && <span className="interview-live-sub">Speaking</span>}
          </div>
          {!round.is_sample && (
            <>
              <button
                type="button"
                onClick={nextQuestion}
                disabled={observerMode}
                className="text-xs text-surface-300 hover:text-white flex items-center gap-1 px-2 py-1 rounded-lg bg-surface-800/80 border border-surface-700"
                title="Skip to the next question (won't affect your score negatively)"
              >
                <SkipForward size={12} /> Next question
              </button>
              <button type="button" onClick={() => setShowReschedule(s => !s)} className="text-xs text-surface-400 hover:text-white flex items-center gap-1">
                <Calendar size={12} /> Reschedule
              </button>
              <button type="button" onClick={extend} className="text-xs text-surface-400 hover:text-white flex items-center gap-1">
                <Plus size={12} /> 10m
              </button>
            </>
          )}
          <button
            type="button"
            onClick={toggleInterviewerMute}
            className={`text-xs flex items-center gap-1 px-2 py-1 rounded-lg border transition-colors ${
              interviewerMuted
                ? 'bg-red-500/20 text-red-300 border-red-500/30'
                : 'bg-surface-800/80 text-surface-300 border-surface-700 hover:text-white'
            }`}
            title={interviewerMuted ? 'Unmute interviewer voice' : 'Mute interviewer voice (captions stay on)'}
          >
            {interviewerMuted ? <VolumeX size={12} /> : <Volume2 size={12} />}
            {interviewerMuted ? 'Unmute' : 'Mute'} interviewer
          </button>
          <button type="button" onClick={cancelInterview} className="p-2 rounded-lg bg-surface-800 text-surface-400 hover:text-white" title="Cancel interview">
            <X size={16} />
          </button>
          <button type="button" onClick={finishAndNextRound} className="text-xs text-indigo-300 hover:text-white flex items-center gap-1 px-2 py-1 rounded-lg bg-indigo-500/15 border border-indigo-500/25" title="End this round and open the next one">
            <SkipForward size={12} /> Next round
          </button>
          <button type="button" onClick={() => endInterview()} className="px-2 py-1 rounded-lg bg-red-500/20 text-red-400 text-xs inline-flex items-center gap-1" title="End this round and view report">
            <PhoneOff size={14} /> Finish round
          </button>
          {recordingReady && (
            <button type="button" onClick={downloadRecording}
              className="px-2 py-1 rounded-lg bg-accent-cyan/20 text-accent-cyan text-xs font-medium hover:bg-accent-cyan/30 transition-colors"
              title="Download interview recording">
              ⬇ Recording
            </button>
          )}
        </div>
      </header>
      {showReschedule && (
        <div className="px-4 py-2 border-b border-surface-800 bg-surface-900/50 flex gap-2 items-center">
          <input
            type="datetime-local"
            value={rescheduleAt}
            onChange={e => setRescheduleAt(e.target.value)}
            className="input-field text-xs flex-1 max-w-xs"
          />
          <button type="button" onClick={rescheduleRound} className="btn-secondary text-xs">Save schedule</button>
        </div>
      )}

      <div className="flex-1 grid lg:grid-cols-3 gap-0 min-h-0">
        <div className="lg:col-span-2 flex flex-col min-h-0 border-r border-surface-800">
          {/* ── Split-screen: AI interviewer tile + candidate webcam tile ── */}
          <div className="interview-stage-grid flex-1 p-3 sm:p-4">
            {/* AI interviewer tile — glows while the AI is speaking */}
            <div className={`interview-tile ${isSpeaking ? 'interview-tile-active' : ''}`}>
              <InterviewerStage
                personaName={round.persona_name}
                personaTitle={personaTitle}
                roundTitle={round.title}
                speaking={isSpeaking}
                listening={isListening}
                thinking={isThinking}
                caption={aiCaption}
                live
              />
            </div>

            {/* Candidate webcam tile — glows green while they speak */}
            <div className={`interview-tile ${candidateSpeaking ? 'interview-tile-active-candidate' : ''}`}>
              <InterviewVideoPreview
                stream={mediaStream}
                cameraOn={cameraOn}
                backgroundId={backgroundId}
                onBackgroundChange={setBackgroundId}
                className="absolute inset-0 w-full h-full"
                mirror
                placeholder=""
              />
              {/* In-tile mic/camera toggles */}
              <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-2 z-20">
                <button
                  type="button"
                  onClick={async () => {
                    const t = streamRef.current?.getAudioTracks()[0]
                    if (!t) { await acquireMedia('audio'); return }
                    t.enabled = !t.enabled
                    setMicOn(t.enabled)
                  }}
                  className={`p-2.5 rounded-full transition-colors ${micOn ? 'bg-surface-800/90 text-white hover:bg-surface-700' : 'bg-red-500/90 text-white'}`}
                  title={micOn ? 'Mute' : 'Unmute'}
                >
                  {micOn ? <Mic size={18} /> : <MicOff size={18} />}
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    const t = streamRef.current?.getVideoTracks()[0]
                    if (!t) { await acquireMedia('video'); return }
                    t.enabled = !t.enabled
                    setCameraOn(t.enabled)
                  }}
                  className={`p-2.5 rounded-full transition-colors ${cameraOn ? 'bg-surface-800/90 text-white hover:bg-surface-700' : 'bg-red-500/90 text-white'}`}
                  title={cameraOn ? 'Turn camera off' : 'Turn camera on'}
                >
                  {cameraOn ? <Video size={18} /> : <VideoOff size={18} />}
                </button>
              </div>
              {/* Candidate name plate */}
              <div className="interview-nameplate">
                <span className={`interview-nameplate-dot ${candidateSpeaking ? 'is-on' : ''}`} />
                You
              </div>
              {/* Live candidate caption (interim STT) */}
              {isListening && interimTranscript && (
                <div className="interview-caption interview-caption-candidate">
                  <span className="interview-caption-name">You</span>
                  <p className="interview-caption-text">{interimTranscript}</p>
                </div>
              )}
            </div>
          </div>

          {/* Hands-free status line (replaces the old send-button-centric bar) */}
          <div className="px-4 pb-1">
            {isSpeaking ? (
              <p className="interview-handsfree-hint text-indigo-300">
                <Volume2 size={13} /> {round.persona_name} is speaking — just start talking to jump in
              </p>
            ) : isListening ? (
              silenceCountdown ? (
                // WS1 — the trailing-silence window is running. Reassure the
                // candidate they still have a beat; any new speech cancels it.
                <p className="interview-handsfree-hint text-amber-300">
                  <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                  Still listening — take your time
                  <span className="font-mono text-amber-200/90">
                    ({Math.ceil(silenceCountdown.remaining / 1000)}s)
                  </span>
                  {askMode && <span className="text-amber-200/70 italic">— asking</span>}
                </p>
              ) : (
                <p className="interview-handsfree-hint text-emerald-300">
                  <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  {askMode
                    ? "Go ahead — ask your question, I'll answer and repeat."
                    : "Listening — answer naturally, then pause. I'll pick it up."}
                  {interimTranscript ? <span className="text-emerald-200/80 italic">“{interimTranscript.slice(0, 50)}”</span> : null}
                </p>
              )
            ) : (
              <p className="interview-handsfree-hint text-surface-500">
                <Mic size={13} /> Hands-free — speak when you're ready, or type below.
              </p>
            )}
          </div>

          {practicalMode && activePracticalConfig?.kind === 'command' && (
            <div className="px-4 py-2 border-t border-surface-800 bg-surface-900/50 space-y-2 mt-1">
              <p className="text-xs text-cyan-400 flex items-center gap-1">
                <Terminal size={12} /> Command lab — run commands in the terminal below or grade inline
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={launchPracticalLab}
                  disabled={labLoading || observerMode}
                  className="btn-primary text-xs py-1.5 px-3 inline-flex items-center gap-1.5"
                >
                  {labLoading ? <Loader2 size={12} className="animate-spin" /> : <ExternalLink size={12} />}
                  {practicalLab ? 'Reopen lab' : 'Launch lab'}
                </button>
                {practicalLab?.scenario_title && (
                  <span className="text-[10px] text-surface-500">{practicalLab.scenario_title}</span>
                )}
              </div>
            </div>
          )}
          {practicalMode && activePracticalConfig?.kind === 'code' && (
            <p className="text-[10px] text-surface-500 px-4 py-2 border-t border-surface-800">
              Live coding — paste your solution below. I&apos;ll grade it inline (no separate lab needed).
            </p>
          )}

          {practicalMode && (
            <PracticalAnswerPanel
              onValidate={validatePracticalAnswer}
              disabled={observerMode}
              practicalConfig={activePracticalConfig}
              labSession={practicalLab}
              onStartLab={startPracticalLabInline}
              onOpenLab={launchPracticalLab}
              onValidated={() => {
                toast.success('Verified — nicely done')
              }}
            />
          )}

          {practiceMode && coaching && (
            <div className="px-4 pt-2">
              <CoachingTip coaching={coaching} />
            </div>
          )}

          {/* Control bar — hands-free is the default; these are fallbacks for
              accessibility (manual mic toggle, type-to-answer, Done, Skip). */}
          <div className="p-3 border-t border-surface-800 flex flex-wrap gap-2 items-center">
            <button
              type="button"
              onClick={() => setMobileTranscriptOpen((v) => !v)}
              className={`lg:hidden px-2.5 py-1.5 rounded-lg text-[11px] font-medium shrink-0 inline-flex items-center gap-1 ${
                mobileTranscriptOpen ? 'bg-indigo-500/20 text-indigo-200' : 'btn-secondary'
              }`}
            >
              <MessageSquare size={14} /> Transcript
            </button>
            <button
              type="button"
              onClick={() => setPracticalCoaching(v => !v)}
              title="Practice mode — instant coaching tips after each answer"
              className={`px-2.5 py-1.5 rounded-lg text-[11px] font-medium shrink-0 transition-colors ${
                practiceMode
                  ? 'bg-amber-500/20 text-amber-300 ring-1 ring-amber-400/40'
                  : 'btn-secondary'
              }`}
            >
              Coach {practiceMode ? 'on' : 'off'}
            </button>
            <button
              type="button"
              onClick={voiceAnswer}
              className={`px-3 py-2 rounded-lg transition-colors shrink-0 ${
                isListening
                  ? 'bg-emerald-500/30 text-emerald-200 ring-1 ring-emerald-400 animate-pulse'
                  : 'btn-secondary opacity-60'
              }`}
              title={isListening ? 'Listening…' : 'Voice (automatic)'}
              aria-hidden={!typingAnswer}
              tabIndex={typingAnswer ? 0 : -1}
            >
              {isListening ? <CheckCircle2 size={16} /> : <Mic size={16} />}
            </button>
            {/* WS5 — interactive: ask the interviewer a question / get a repeat.
                The captured speech is sent as input_type:'question', so the bot
                clarifies and re-asks the SAME question instead of advancing. */}
            <button
              type="button"
              onClick={() => askQuestion()}
              disabled={observerMode}
              className={`px-2.5 py-1.5 rounded-lg text-[11px] font-medium shrink-0 inline-flex items-center gap-1 transition-colors ${
                askMode
                  ? 'bg-indigo-500/25 text-indigo-200 ring-1 ring-indigo-400/50'
                  : 'btn-secondary'
              }`}
              title="Ask the interviewer a question (won't be scored)"
            >
              <HelpCircle size={14} /> Ask
            </button>
            <button
              type="button"
              onClick={() => askQuestion('Could you repeat the question, please?')}
              disabled={observerMode}
              className="px-2.5 py-1.5 rounded-lg text-[11px] font-medium shrink-0 inline-flex items-center gap-1 btn-secondary"
              title="Ask the interviewer to repeat the question"
            >
              <RotateCcw size={14} /> Repeat
            </button>
            <button
              type="button"
              onClick={() => { setTypingAnswer(true); setTimeout(() => document.getElementById('interview-answer-input')?.focus(), 0) }}
              className={`px-2.5 py-1.5 rounded-lg text-[11px] font-medium shrink-0 ${typingAnswer ? 'bg-indigo-500/20 text-indigo-200' : 'btn-secondary'}`}
              title="Type your answer instead of speaking"
            >
              Type
            </button>
            <input
              id="interview-answer-input"
              value={answer}
              readOnly={started && !typingAnswer}
              onChange={e => { setAnswer(e.target.value); if (e.target.value.trim()) setTypingAnswer(true) }}
              onKeyDown={e => e.key === 'Enter' && typingAnswer && submitAnswer()}
              placeholder={isListening ? 'Listening… speak naturally' : (typingAnswer ? 'Type your answer…' : 'Live call — speak naturally')}
              className={`input-field flex-1 text-sm ${isListening ? 'ring-1 ring-emerald-500/40' : ''}`}
            />
            {typingAnswer && answer.trim() && (
              <button type="button" onClick={() => submitAnswer()} className="btn-primary px-4 text-sm shrink-0" title="Send typed answer">
                Send
              </button>
            )}
            <button
              type="button"
              onClick={nextQuestion}
              disabled={observerMode}
              className="btn-secondary px-3 shrink-0 inline-flex items-center gap-1.5 text-xs"
              title="Skip to the next question"
            >
              <SkipForward size={16} /> Next
            </button>
          </div>
        </div>

        <div className={`flex flex-col min-h-0 bg-surface-900/30 ${
          mobileTranscriptOpen
            ? 'fixed inset-x-0 bottom-0 z-40 h-[55vh] border-t border-surface-700 lg:relative lg:inset-auto lg:h-auto lg:z-auto'
            : 'hidden lg:flex'
        }`}>
          {hostState?.joined && (
            <div className="p-3 border-b border-indigo-500/30 bg-indigo-500/10 text-xs text-indigo-100">
              <p className="font-medium">
                {hostState.display_name || 'FixitLab team'} joined live
                {hostState.ai_enabled === false ? ' — answering your questions now' : ' — AI will continue shortly'}
              </p>
              <p className="text-[10px] text-indigo-200/80 mt-1">Take your time — jump in anytime if you need to clarify.</p>
            </div>
          )}
          {joinRequests.length > 0 && (
            <div className="p-3 border-b border-amber-500/30 bg-amber-500/10 space-y-2">
              {joinRequests.map(req => (
                <div key={req.id} className="text-xs text-amber-100">
                  <p>{req.admin?.email} requests to observe: {req.message}</p>
                  <div className="flex gap-2 mt-2">
                    <button
                      type="button"
                      onClick={() => interviewsApi.respondJoinRequest(req.id, true).then(() => {
                        toast.success('Admin can now observe')
                        setJoinRequests(j => j.filter(x => x.id !== req.id))
                      })}
                      className="btn-primary text-[10px] py-1 px-2"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => interviewsApi.respondJoinRequest(req.id, false).then(() => {
                        setJoinRequests(j => j.filter(x => x.id !== req.id))
                      })}
                      className="btn-secondary text-[10px] py-1 px-2"
                    >
                      Decline
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="text-xs text-surface-500 px-3 py-2 border-b border-surface-800 flex items-center gap-1">
            <MessageSquare size={12} /> Live transcript
          </p>
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {messages.map(m => (
              <div
                key={m.id}
                className={`text-xs rounded-lg p-2 ${
                  m.role === 'interviewer'
                    ? 'bg-indigo-500/10 border border-indigo-500/20 text-indigo-100'
                    : m.role === 'candidate'
                      ? 'bg-surface-800 text-surface-200 ml-4'
                      : 'bg-amber-500/10 text-amber-200 text-center'
                }`}
              >
                <span className="text-[10px] uppercase opacity-60">{m.role}</span>
                <p className="mt-0.5 whitespace-pre-wrap">{m.content}</p>
                {m.score != null && (
                  <p className="text-[10px] text-surface-500 mt-1">Score: {m.score}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
    <ConfirmPortal />
    </>
  )
}
