import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { interviewsApi } from '../../api/interviews'
import { adminApi } from '../../api/admin'
import { useInterviewVoice } from '../../hooks/useInterviewVoice'
import {
  getMediaErrorMessage,
  isMediaDevicesSupported,
  isPermissionDeniedError,
  requestUserMedia,
  stopMediaStream,
  streamHasLiveTrack,
} from '../../utils/mediaDevices'
import InterviewVideoPreview from '../../components/interviews/InterviewVideoPreview'
import PracticalAnswerPanel from '../../components/interviews/PracticalAnswerPanel'
import { PageHeader } from '../../components/design'
import {
  Mic, MicOff, Video, VideoOff, PhoneOff, Clock, MessageSquare, Terminal,
  Volume2, Plus, ExternalLink, Loader2, ArrowLeft, Calendar, X, SkipForward,
} from 'lucide-react'
import toast from 'react-hot-toast'

// How long (ms) of continuous silence on an open question before the bot moves
// on, so the fixed round time covers the planned material (skip-on-silence).
const SILENCE_SKIP_MS = 20000
// Mic energy (0–1, same scale as the preflight meter) that counts as "speaking"
// for barge-in. Above this while the bot is talking → interrupt the bot.
const BARGE_IN_LEVEL = 0.18

export default function InterviewRoom() {
  const { roundId } = useParams()
  const [searchParams] = useSearchParams()
  const observerToken = searchParams.get('observer')
  const navigate = useNavigate()

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
  const {
    speak, listen, stopListening, cancelSpeech,
    resolveVoiceProfile,
    isSpeaking, isListening, interimTranscript,
    browserVoices, selectedVoiceURI, selectVoice,
  } = useInterviewVoice()

  const [round, setRound] = useState(null)
  const [messages, setMessages] = useState([])
  const [answer, setAnswer] = useState('')
  const [micOn, setMicOn] = useState(false)
  const [cameraOn, setCameraOn] = useState(false)
  const [timeLeft, setTimeLeft] = useState(null)
  const [started, setStarted] = useState(false)
  const [practicalMode, setPracticalMode] = useState(false)
  const [practicalLab, setPracticalLab] = useState(null)
  const [labLoading, setLabLoading] = useState(false)
  const [preflight, setPreflight] = useState(true)
  const [joinRequests, setJoinRequests] = useState([])
  const [observerMode, setObserverMode] = useState(!!observerToken)
  const [consentAccepted, setConsentAccepted] = useState(false)
  const [showReschedule, setShowReschedule] = useState(false)
  const [rescheduleAt, setRescheduleAt] = useState('')
  const [mediaError, setMediaError] = useState('')
  const [mediaLoading, setMediaLoading] = useState(false)
  const [backgroundId, setBackgroundId] = useState('none')

  // Keep refs in sync so the VAD loop and timers see current speaking/listening.
  useEffect(() => { isSpeakingRef.current = isSpeaking }, [isSpeaking])
  useEffect(() => { isListeningRef.current = isListening }, [isListening])
  useEffect(() => { answerRef.current = answer }, [answer])

  const endsAt = round?.ends_at ? new Date(round.ends_at).getTime() : null

  // Proactively request permissions when preflight loads — triggers the browser
  // dialog immediately (like Google Meet), before the user clicks any button.
  // Goes through the same acquireMedia() path as the buttons so a grant attaches
  // the stream and clears any error automatically (no manual re-click needed).
  useEffect(() => {
    if (!preflight || !isMediaDevicesSupported()) return
    // Silent: don't surface an error banner on the auto-prompt. If the user
    // dismisses the native dialog they can still click Enable / Try again.
    acquireMedia('both', { silent: true })
  }, [preflight]) // eslint-disable-line react-hooks/exhaustive-deps

  // Recover automatically when a device is plugged in or permission is granted
  // after the fact — re-attempt acquisition so video/mic turn on without a reload.
  useEffect(() => {
    if (!preflight || !navigator.mediaDevices?.addEventListener) return
    const onDeviceChange = () => {
      if (!micOn || !cameraOn) acquireMedia('both', { silent: true })
    }
    navigator.mediaDevices.addEventListener('devicechange', onDeviceChange)
    return () => navigator.mediaDevices.removeEventListener('devicechange', onDeviceChange)
  }, [preflight, micOn, cameraOn]) // eslint-disable-line react-hooks/exhaustive-deps

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
        vadRafRef.current = requestAnimationFrame(tick)
      }
      vadRafRef.current = requestAnimationFrame(tick)
    } catch {
      // AudioContext not available — barge-in simply disabled.
    }
    return () => {
      cancelAnimationFrame(vadRafRef.current)
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
      type === 'audio' ? { audio: true, video: false } :
      type === 'video' ? { audio: false, video: true } :
      { audio: true, video: true }

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
      adminApi.getInterviewObserverSession(observerToken).then(data => {
        setRound(data.round)
        setMessages(data.messages || [])
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
    if (!endsAt) return
    const t = setInterval(() => {
      const left = Math.max(0, Math.floor((endsAt - Date.now()) / 1000))
      setTimeLeft(left)
    }, 1000)
    return () => clearInterval(t)
  }, [endsAt])

  const cancelInterview = async () => {
    if (!window.confirm('Cancel this interview round?')) return
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
  const exitToList = (dest = '/interviews') => {
    if (started && !observerMode) {
      const ok = window.confirm(
        'Leave the interview? The round stays in progress — you can resume it from your interviews page. ' +
        'To finish and get your report, use "End round" instead.'
      )
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
    setPreflight(false)
    try {
      const data = await interviewsApi.startRound(roundId)
      setRound(data)
      const msgs = [...(data.messages || [])]
      if (data.intro) msgs.push(data.intro)
      if (data.first_question) msgs.push(data.first_question)
      setMessages(msgs)
      setStarted(true)
      // Start recording once the interview is live
      if (streamRef.current) startRecording(streamRef.current)
      const voiceId = data.persona_voice_id
      const introText = data.intro?.content || ''
      const firstQ = data.first_question
      if (firstQ?.message_type === 'practical') {
        setPracticalMode(true)
        if (data.practical_lab_session_id) {
          setPracticalLab({ session_id: data.practical_lab_session_id, lab_url: `/lab/${data.practical_lab_session_id}` })
        }
      }
      // Speak the intro (no listen), then the first question and auto-open the
      // mic. speakThenListen awaits TTS completion, so the mic opens exactly
      // when the bot stops talking — no brittle length*40ms guess.
      if (introText) await speakThenListen(introText, { autoListen: false, voiceId })
      if (firstQ?.content) {
        await speakThenListen(firstQ.content, {
          autoListen: firstQ.message_type !== 'practical', voiceId,
        })
      }
    } catch (e) {
      toast.error(e.response?.data?.error || 'Could not start')
    }
  }

  // text === '' (explicit, e.g. skip-on-silence) submits an empty answer the
  // engine scores as "skipped" and advances. A null/undefined text falls back
  // to the typed box and must be non-empty.
  const submitAnswer = async (text) => {
    const isSkip = text === ''
    const ans = isSkip ? '' : (text ?? answer).trim()
    if (!isSkip && !ans) return
    // An answer (or skip) arrived — stop the silence countdown for this turn.
    clearSilenceTimer()
    awaitingAnswerRef.current = false
    setAnswer('')
    try {
      const res = await interviewsApi.sendMessage(roundId, ans, {
        input_type: isListeningRef.current ? 'voice' : 'text',
      })
      setMessages(m => [
        ...m,
        res.candidate_message,
        res.interviewer_reply,
        ...(res.next_question ? [res.next_question] : []),
      ])
      const nextIsPractical = res.next_question?.message_type === 'practical'
      setPracticalMode(nextIsPractical)
      setPracticalLab(null)
      // Speak the interviewer reply, then the next question, then re-open the
      // mic so the candidate can answer — continuing the hands-free loop.
      // Practical questions don't auto-listen (the candidate works in the lab).
      await speakThenListen(res.interviewer_reply?.content, { autoListen: false })
      if (res.next_question?.content) {
        await speakThenListen(res.next_question.content, { autoListen: !nextIsPractical })
      }
    } catch {
      toast.error('Could not send answer')
    }
  }

  // Start STT and capture one answer. Passes the live mic stream + correct
  // options so the recognizer actually receives audio (this was the bug:
  // listen(profile.locale) sent a string where the hook expects a MediaStream).
  // listen() resolves with { transcript, filtered_text, ... } — not a string.
  const voiceAnswer = async () => {
    if (isListening) {
      // Second click acts as "done" — finalize the current capture.
      stopListening()
      return
    }
    // If the bot is mid-sentence, stop it first so STT doesn't transcribe TTS.
    cancelSpeech()
    const profile = resolveVoiceProfile(round?.persona_voice_id)
    // Arm skip-on-silence for THIS listening turn: if no speech arrives within
    // the window, the timer stops the recognizer and posts an empty (skipped)
    // answer so the round keeps moving and uses the fixed time.
    armSilenceSkip()
    // listen() flips the hook's isListening flag itself; no local state needed.
    const result = await listen(streamRef.current, {
      locale: profile.locale || 'en-IN',
      techPrompt: round?.technology_name || '',
      onInterim: (txt) => setAnswer(txt),
    })
    const text = (result?.transcript || result?.filtered_text || '').trim()
    // If the silence-skip timer (or a manual skip) already resolved this turn,
    // awaitingAnswerRef is false — don't submit again, even if late STT text
    // arrives. This closes the double-submit race.
    if (!awaitingAnswerRef.current) {
      setAnswer('')
      return
    }
    if (text) {
      await submitAnswer(text)
    } else {
      // Stopped with nothing captured — clear and wait (no skip was triggered).
      clearSilenceTimer()
      setAnswer('')
    }
  }

  // Speak a bot line, then automatically open the mic for the candidate's reply.
  // This is the heart of the hands-free voice loop.
  const speakThenListen = async (text, { autoListen = true, voiceId } = {}) => {
    if (!text) return
    bargedInRef.current = false
    await speak(text, voiceId ?? round?.persona_voice_id)
    // speak() resolves when TTS finishes (or was cancelled). If the candidate
    // barged in, voiceAnswer() is already listening — don't double-start.
    if (autoListen && !observerMode && !isListeningRef.current && !bargedInRef.current) {
      voiceAnswer()
    }
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
      submitAnswer('') // engine treats empty as skipped and advances
    }, SILENCE_SKIP_MS)
  }

  const skipQuestion = () => {
    clearSilenceTimer()
    stopListening()
    cancelSpeech()
    submitAnswer('')
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
      cancelSpeech()
      if (!isListeningRef.current) {
        voiceAnswer() // self-arms skip-on-silence
      }
    }
  }) // eslint-disable-line react-hooks/exhaustive-deps

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

  const endInterview = async () => {
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
      toast.success(res.passed ? 'Round passed!' : 'Round complete — see report')
      navigate(`/interviews/round/${roundId}/report`, { state: { report: res.report } })
    } catch {
      navigate(`/interviews/campaign/${round?.campaign_id || ''}`)
    }
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
    const res = await interviewsApi.validatePractical(roundId, answer)
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
  }

  const fmt = (s) => {
    if (s == null) return '--:--'
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  if (!round) return <p className="text-surface-500 p-8">Loading room…</p>

  if (observerMode) {
    return (
      <div className="h-[calc(100vh-4rem)] flex flex-col bg-surface-950">
        <header className="px-4 py-2 border-b border-surface-800 bg-amber-500/10">
          <p className="text-xs text-amber-300">Observer mode — read-only transcript</p>
          <p className="text-sm font-medium text-white">{round.title}</p>
        </header>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.map(m => (
            <div key={m.id} className="text-xs rounded-lg p-2 bg-surface-900 border border-surface-800 text-surface-200">
              <span className="text-[10px] uppercase opacity-60">{m.role}</span>
              <p className="mt-0.5 whitespace-pre-wrap">{m.content}</p>
            </div>
          ))}
        </div>
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
        {browserVoices.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs text-surface-400 flex items-center gap-1.5">
              <Volume2 size={12} className="text-indigo-400" />
              Interviewer voice — you can also change this during the interview
            </p>
            <div className="flex items-center gap-2">
              <select
                value={selectedVoiceURI}
                onChange={e => selectVoice(e.target.value)}
                className="input-field text-xs flex-1"
              >
                <option value="">Default ({round.persona_name}'s accent)</option>
                {browserVoices.map(v => (
                  <option key={v.voiceURI} value={v.voiceURI}>{v.name} ({v.lang})</option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => speak('Hi, this is how I will sound during your interview.', round.persona_voice_id)}
                className="btn-secondary text-xs whitespace-nowrap inline-flex items-center gap-1"
                title="Preview voice"
              >
                <Volume2 size={12} /> Test
              </button>
            </div>
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
          {browserVoices.length > 0 && (
            <label className="flex items-center gap-1 text-[10px] text-surface-400" title="Change interviewer voice">
              <Volume2 size={12} className="text-indigo-400" />
              <select
                value={selectedVoiceURI}
                onChange={e => changeVoice(e.target.value)}
                className="bg-surface-800 border border-surface-700 rounded text-[11px] text-surface-200 py-1 px-1.5 max-w-[140px]"
              >
                <option value="">Default voice</option>
                {browserVoices.map(v => (
                  <option key={v.voiceURI} value={v.voiceURI}>
                    {v.name} ({v.lang})
                  </option>
                ))}
              </select>
            </label>
          )}
          <span className="text-sm font-mono text-amber-400 flex items-center gap-1">
            <Clock size={14} /> {fmt(timeLeft)}
          </span>
          {!round.is_sample && (
            <>
              <button type="button" onClick={() => setShowReschedule(s => !s)} className="text-xs text-surface-400 hover:text-white flex items-center gap-1">
                <Calendar size={12} /> Reschedule
              </button>
              <button type="button" onClick={extend} className="text-xs text-surface-400 hover:text-white flex items-center gap-1">
                <Plus size={12} /> 10m
              </button>
            </>
          )}
          <button type="button" onClick={cancelInterview} className="p-2 rounded-lg bg-surface-800 text-surface-400 hover:text-white" title="Cancel interview">
            <X size={16} />
          </button>
          <button type="button" onClick={endInterview} className="p-2 rounded-lg bg-red-500/20 text-red-400" title="End round">
            <PhoneOff size={16} />
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
          <div className="relative flex-1 bg-black min-h-[200px]">
            <InterviewVideoPreview
              stream={mediaStream}
              cameraOn={cameraOn}
              backgroundId={backgroundId}
              onBackgroundChange={setBackgroundId}
              className="absolute inset-0 w-full h-full"
              mirror={false}
              placeholder=""
            />
            <div className="absolute bottom-3 left-3 flex gap-2">
              <button
                type="button"
                onClick={async () => {
                  const t = streamRef.current?.getAudioTracks()[0]
                  if (!t) {
                    await acquireMedia('audio')
                    return
                  }
                  t.enabled = !t.enabled
                  setMicOn(t.enabled)
                }}
                className={`p-2 rounded-full ${micOn ? 'bg-surface-800/90 text-white' : 'bg-red-500/90 text-white'}`}
              >
                {micOn ? <Mic size={18} /> : <MicOff size={18} />}
              </button>
              <button
                type="button"
                onClick={async () => {
                  const t = streamRef.current?.getVideoTracks()[0]
                  if (!t) {
                    await acquireMedia('video')
                    return
                  }
                  t.enabled = !t.enabled
                  setCameraOn(t.enabled)
                }}
                className={`p-2 rounded-full ${cameraOn ? 'bg-surface-800/90 text-white' : 'bg-red-500/90 text-white'}`}
              >
                {cameraOn ? <Video size={18} /> : <VideoOff size={18} />}
              </button>
            </div>
            <div className="absolute top-3 right-3 w-24 h-24 rounded-xl bg-indigo-500/20 border border-indigo-500/40 flex flex-col items-center justify-center">
              <Volume2 className="text-indigo-300 mb-1" size={20} />
              <span className="text-[10px] text-indigo-200 text-center px-1">
                Browser voice (free)
              </span>
            </div>
          </div>

          {practicalMode && (
            <div className="p-3 border-t border-surface-800 bg-surface-900/50 space-y-2">
              <p className="text-xs text-cyan-400 flex items-center gap-1">
                <Terminal size={12} /> Hands-on lab — complete the scenario in a real FixitLab environment
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
              <p className="text-[10px] text-surface-500">
                Open the full lab in a new tab, or just type the command/code below and I'll check it inline.
              </p>
            </div>
          )}

          {practicalMode && (
            <PracticalAnswerPanel
              onValidate={validatePracticalAnswer}
              disabled={observerMode}
              onValidated={() => {
                toast.success('Verified — nicely done')
              }}
            />
          )}

          {(isListening || isSpeaking) && (
            <div className="px-3 pt-2 -mb-1">
              <p className={`text-[10px] flex items-center gap-1.5 ${isSpeaking ? 'text-indigo-300' : 'text-emerald-300'}`}>
                {isSpeaking ? (
                  <><Volume2 size={11} /> Interviewer speaking — start talking any time to interrupt</>
                ) : (
                  <><span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> Listening… {interimTranscript ? `“${interimTranscript.slice(0, 60)}”` : 'speak your answer'}</>
                )}
              </p>
            </div>
          )}
          <div className="p-3 border-t border-surface-800 flex gap-2">
            <input
              value={answer}
              onChange={e => setAnswer(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && submitAnswer()}
              placeholder="Type your answer or use voice…"
              className="input-field flex-1 text-sm"
            />
            <button
              type="button"
              onClick={voiceAnswer}
              className={`px-3 rounded-lg transition-colors ${
                isListening
                  ? 'bg-emerald-500/30 text-emerald-200 ring-1 ring-emerald-400 animate-pulse'
                  : 'btn-secondary'
              }`}
              title={isListening ? 'Stop & send (or just stop talking)' : 'Voice answer'}
            >
              {isListening ? <MicOff size={16} /> : <Mic size={16} />}
            </button>
            <button
              type="button"
              onClick={skipQuestion}
              className="btn-secondary px-3"
              title="Skip this question"
            >
              <SkipForward size={16} />
            </button>
            <button type="button" onClick={() => submitAnswer()} className="btn-primary px-4 text-sm">
              Send
            </button>
          </div>
        </div>

        <div className="flex flex-col min-h-0 bg-surface-900/30">
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
    </>
  )
}
