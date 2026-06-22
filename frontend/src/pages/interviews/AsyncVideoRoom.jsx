import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { interviewsApi } from '../../api/interviews'
import { useInterviewVoice } from '../../hooks/useInterviewVoice'
import {
  getMediaErrorMessage,
  isMediaDevicesSupported,
  requestUserMedia,
  stopMediaStream,
} from '../../utils/mediaDevices'
import { PageHeader } from '../../components/design'
import {
  Video, Circle, Square, ChevronRight, CheckCircle2, Loader2, RotateCcw, Play, AlertCircle,
} from 'lucide-react'
import toast from 'react-hot-toast'

/**
 * One-way (async) video interview room (parity: one-way video interviews).
 * The candidate records a video answer to each prompt with the browser
 * MediaRecorder; clips upload to existing storage; a browser transcript is
 * captured for free scoring. Review playback at the end.
 */
export default function AsyncVideoRoom() {
  const { roundId } = useParams()
  const navigate = useNavigate()
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const recorderRef = useRef(null)
  const chunksRef = useRef([])
  const startTsRef = useRef(0)
  const { listen, stopListening, isListening, interimTranscript } = useInterviewVoice()

  const [prompts, setPrompts] = useState([])
  const [idx, setIdx] = useState(0)
  const [recording, setRecording] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState({})      // { questionIndex: true }
  const [mediaError, setMediaError] = useState('')
  const [loading, setLoading] = useState(true)
  const [finalizing, setFinalizing] = useState(false)
  const transcriptRef = useRef('')

  // --- Set up camera + load prompts on mount ---
  useEffect(() => {
    let cancelled = false
    const init = async () => {
      try {
        const start = await interviewsApi.startAsyncRound(roundId)
        if (cancelled) return
        setPrompts(start.prompts || [])
      } catch (e) {
        toast.error(e.response?.data?.error || 'Could not start the video interview')
      }
      if (!isMediaDevicesSupported()) {
        setMediaError('Your browser does not support camera recording.')
        setLoading(false)
        return
      }
      try {
        const result = await requestUserMedia({ audio: true, video: true })
        if (cancelled) { stopMediaStream(result.stream); return }
        streamRef.current = result.stream
        if (videoRef.current) {
          videoRef.current.srcObject = result.stream
          videoRef.current.muted = true
          videoRef.current.play().catch(() => {})
        }
      } catch (e) {
        setMediaError(getMediaErrorMessage(e))
      }
      setLoading(false)
    }
    init()
    return () => {
      cancelled = true
      try { recorderRef.current?.stop() } catch { /* ignore */ }
      stopMediaStream(streamRef.current)
    }
  }, [roundId])

  const pickMime = () =>
    ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm'].find(
      t => window.MediaRecorder && MediaRecorder.isTypeSupported(t)
    )

  const startRecording = async () => {
    if (!streamRef.current || !window.MediaRecorder) {
      toast.error('Recording not supported on this device')
      return
    }
    const mimeType = pickMime()
    if (!mimeType) { toast.error('Recording format not supported'); return }
    chunksRef.current = []
    transcriptRef.current = ''
    try {
      const rec = new MediaRecorder(streamRef.current, { mimeType, videoBitsPerSecond: 700_000 })
      rec.ondataavailable = e => { if (e.data?.size > 0) chunksRef.current.push(e.data) }
      rec.start(1000)
      recorderRef.current = rec
      startTsRef.current = Date.now()
      setRecording(true)
      // Capture a free browser transcript in parallel (best-effort).
      listen(streamRef.current, {
        maxDuration: 180000,
        onInterim: (t) => { transcriptRef.current = t },
      }).then(res => {
        if (res?.transcript) transcriptRef.current = res.transcript
      }).catch(() => {})
    } catch {
      toast.error('Could not start recording')
    }
  }

  const stopAndSubmit = async () => {
    if (!recorderRef.current) return
    const rec = recorderRef.current
    const durationSeconds = (Date.now() - startTsRef.current) / 1000
    setRecording(false)
    setSubmitting(true)
    try { stopListening() } catch { /* ignore */ }

    await new Promise(resolve => {
      rec.onstop = resolve
      try { rec.stop() } catch { resolve() }
    })

    const blob = chunksRef.current.length
      ? new Blob(chunksRef.current, { type: chunksRef.current[0].type || 'video/webm' })
      : null

    try {
      await interviewsApi.submitAsyncResponse(roundId, {
        questionIndex: prompts[idx]?.index ?? idx,
        transcript: transcriptRef.current || '',
        durationSeconds,
        blob,
      })
      setDone(d => ({ ...d, [idx]: true }))
      toast.success('Answer saved')
      if (idx < prompts.length - 1) {
        setIdx(idx + 1)
      }
    } catch (e) {
      toast.error(e.response?.data?.error || 'Could not save answer')
    } finally {
      setSubmitting(false)
    }
  }

  const finalize = async () => {
    setFinalizing(true)
    try {
      const res = await interviewsApi.finalizeAsyncRound(roundId)
      toast.success('Interview submitted — view your scorecard')
      navigate(`/interviews/round/${roundId}/report`, { state: { report: res.report } })
    } catch (e) {
      toast.error(e.response?.data?.error || 'Could not submit interview')
      setFinalizing(false)
    }
  }

  if (loading) return <p className="text-surface-500 text-sm p-8">Preparing your video interview…</p>

  const answeredCount = Object.keys(done).length
  const allAnswered = prompts.length > 0 && answeredCount >= prompts.length
  const current = prompts[idx]

  return (
    <div className="max-w-3xl mx-auto space-y-5 animate-fade-in py-2">
      <PageHeader
        eyebrow="One-way video interview"
        title="Record your answers"
        subtitle="Read each prompt, record your answer, and move on. You can re-record before submitting."
      />

      {mediaError ? (
        <div className="glass-card p-5 border border-red-500/30 flex items-start gap-3">
          <AlertCircle className="text-red-400 shrink-0 mt-0.5" size={18} />
          <div>
            <p className="text-sm text-white font-medium">Camera unavailable</p>
            <p className="text-xs text-surface-400 mt-1">{mediaError}</p>
          </div>
        </div>
      ) : (
        <>
          {/* Progress */}
          <div className="flex items-center gap-1.5">
            {prompts.map((p, i) => (
              <div
                key={i}
                className={`h-1.5 flex-1 rounded-full ${done[i] ? 'bg-emerald-500' : i === idx ? 'bg-indigo-500' : 'bg-surface-700'}`}
              />
            ))}
          </div>

          {/* Prompt */}
          <div className="glass-card p-5 border border-indigo-500/20">
            <p className="text-[11px] uppercase tracking-wide text-indigo-400 font-semibold mb-1">
              Question {idx + 1} of {prompts.length}
            </p>
            <p className="text-sm text-white">{current?.text}</p>
          </div>

          {/* Video preview */}
          <div className="relative rounded-xl overflow-hidden border border-surface-800 bg-black aspect-video">
            <video ref={videoRef} className="w-full h-full object-cover" playsInline />
            {recording && (
              <div className="absolute top-3 left-3 flex items-center gap-1.5 px-2 py-1 rounded-full bg-red-600/90 text-white text-xs">
                <Circle size={8} className="fill-current animate-pulse" /> REC
              </div>
            )}
            {isListening && interimTranscript && (
              <div className="absolute bottom-0 inset-x-0 bg-black/70 p-2 text-[11px] text-surface-200 max-h-20 overflow-hidden">
                {interimTranscript}
              </div>
            )}
          </div>

          {/* Controls */}
          <div className="flex flex-wrap items-center gap-2">
            {!recording ? (
              <button
                type="button"
                onClick={startRecording}
                disabled={submitting}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-red-500/20 border border-red-500/40 text-red-300 text-sm font-medium hover:bg-red-500/30 disabled:opacity-50"
              >
                {done[idx] ? <RotateCcw size={15} /> : <Video size={15} />}
                {done[idx] ? 'Re-record' : 'Start recording'}
              </button>
            ) : (
              <button
                type="button"
                onClick={stopAndSubmit}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-500/20 border border-indigo-500/40 text-indigo-300 text-sm font-medium hover:bg-indigo-500/30"
              >
                <Square size={15} /> Stop & save
              </button>
            )}

            {submitting && <Loader2 size={16} className="animate-spin text-surface-400" />}

            {!recording && idx < prompts.length - 1 && (
              <button
                type="button"
                onClick={() => setIdx(idx + 1)}
                className="inline-flex items-center gap-1.5 px-3 py-2.5 rounded-xl border border-surface-700 text-surface-300 text-sm hover:bg-surface-800"
              >
                Skip <ChevronRight size={14} />
              </button>
            )}

            <div className="ml-auto text-xs text-surface-500">{answeredCount}/{prompts.length} answered</div>
          </div>

          {/* Finalize */}
          {answeredCount > 0 && (
            <button
              type="button"
              onClick={finalize}
              disabled={finalizing || recording}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-semibold text-sm flex items-center justify-center gap-2 hover:opacity-90 disabled:opacity-50"
            >
              {finalizing ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
              {allAnswered ? 'Submit interview & see scorecard' : `Submit ${answeredCount} answer(s) & finish`}
            </button>
          )}

          <p className="text-[11px] text-surface-600 flex items-center gap-1.5">
            <Play size={11} /> Your clips are stored privately for review. A free browser transcript is used to score your answers.
          </p>
        </>
      )}
    </div>
  )
}
