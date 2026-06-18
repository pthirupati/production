import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { interviewsApi } from '../../api/interviews'
import { adminApi } from '../../api/admin'
import { useInterviewVoice } from '../../hooks/useInterviewVoice'
import {
  getMediaErrorMessage,
  isMediaDevicesSupported,
  queryMediaPermission,
  requestUserMedia,
  stopMediaStream,
} from '../../utils/mediaDevices'
import MediaPermissionDialog from '../../components/interviews/MediaPermissionDialog'
import InterviewVideoPreview from '../../components/interviews/InterviewVideoPreview'
import {
  Mic, MicOff, Video, VideoOff, PhoneOff, Clock, MessageSquare, Terminal,
  Volume2, Plus, ExternalLink, Loader2, ArrowLeft, Calendar, X,
} from 'lucide-react'
import toast from 'react-hot-toast'

export default function InterviewRoom() {
  const { roundId } = useParams()
  const [searchParams] = useSearchParams()
  const observerToken = searchParams.get('observer')
  const navigate = useNavigate()
  const streamRef = useRef(null)
  const [mediaStream, setMediaStream] = useState(null)
  const { speak, listen, config: voiceConfig, resolveVoiceProfile } = useInterviewVoice()

  const [round, setRound] = useState(null)
  const [messages, setMessages] = useState([])
  const [answer, setAnswer] = useState('')
  const [micOn, setMicOn] = useState(false)
  const [cameraOn, setCameraOn] = useState(false)
  const [listening, setListening] = useState(false)
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
  const [permissionRequest, setPermissionRequest] = useState(null)
  const [backgroundId, setBackgroundId] = useState('none')

  const endsAt = round?.ends_at ? new Date(round.ends_at).getTime() : null

  useEffect(() => {
    return () => {
      stopMediaStream(streamRef.current)
      streamRef.current = null
      setMediaStream(null)
    }
  }, [])

  const syncMediaState = (stream) => {
    streamRef.current = stream
    setMediaStream(stream || null)
    const audioTrack = stream?.getAudioTracks()[0]
    const videoTrack = stream?.getVideoTracks()[0]
    setMicOn(!!audioTrack?.enabled)
    setCameraOn(!!videoTrack?.enabled)
  }

  const runEnableMic = async () => {
    const { stream } = await requestUserMedia({ audio: true, video: false }, streamRef.current)
    streamRef.current = stream
    stream.getAudioTracks().forEach((t) => { t.enabled = true })
    syncMediaState(stream)
    toast.success('Microphone enabled')
  }

  const runEnableCamera = async () => {
    const { stream } = await requestUserMedia({ audio: false, video: true }, streamRef.current)
    streamRef.current = stream
    stream.getVideoTracks().forEach((t) => { t.enabled = true })
    syncMediaState(stream)
    toast.success('Camera enabled')
  }

  const runEnableBoth = async () => {
    const { stream } = await requestUserMedia({ audio: true, video: true }, streamRef.current)
    streamRef.current = stream
    stream.getAudioTracks().forEach((t) => { t.enabled = true })
    stream.getVideoTracks().forEach((t) => { t.enabled = true })
    syncMediaState(stream)
    toast.success('Camera and microphone ready')
  }

  const executeMediaRequest = async (type) => {
    if (!isMediaDevicesSupported()) {
      const msg = getMediaErrorMessage({ name: 'NotSupportedError' })
      setMediaError(msg)
      toast.error(msg)
      return
    }
    setMediaLoading(true)
    setMediaError('')
    try {
      if (type === 'audio') await runEnableMic()
      else if (type === 'video') await runEnableCamera()
      else await runEnableBoth()
    } catch (err) {
      const msg = getMediaErrorMessage(err)
      setMediaError(msg)
      toast.error(msg)
      if (type === 'both') {
        try {
          if (!streamRef.current?.getAudioTracks().length) await runEnableMic()
          if (!streamRef.current?.getVideoTracks().length) await runEnableCamera()
          if (streamRef.current?.getAudioTracks().length && streamRef.current?.getVideoTracks().length) {
            setMediaError('')
          }
        } catch {
          /* partial failure already surfaced */
        }
      }
    } finally {
      setMediaLoading(false)
      setPermissionRequest(null)
    }
  }

  const requestMediaAccess = async (type) => {
    if (!isMediaDevicesSupported()) {
      const msg = getMediaErrorMessage({ name: 'NotSupportedError' })
      setMediaError(msg)
      toast.error(msg)
      return
    }
    setMediaError('')
    // Call getUserMedia directly on click so the browser shows Allow/Deny (Meet-style).
    await executeMediaRequest(type)
  }

  const enableMic = () => requestMediaAccess('audio')
  const enableCamera = () => requestMediaAccess('video')
  const enableMedia = () => requestMediaAccess('both')

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
      const introText = data.intro?.content || ''
      if (introText) speak(introText, data.persona_voice_id)
      setTimeout(() => {
        if (data.first_question?.content) speak(data.first_question.content, data.persona_voice_id)
        if (data.first_question?.message_type === 'practical') {
          setPracticalMode(true)
          if (data.practical_lab_session_id) {
            setPracticalLab({ session_id: data.practical_lab_session_id, lab_url: `/lab/${data.practical_lab_session_id}` })
          }
        }
      }, introText.length * 40)
    } catch (e) {
      toast.error(e.response?.data?.error || 'Could not start')
    }
  }

  const submitAnswer = async (text) => {
    const ans = (text || answer).trim()
    if (!ans) return
    setAnswer('')
    try {
      const res = await interviewsApi.sendMessage(roundId, ans, {
        input_type: listening ? 'voice' : 'text',
      })
      setMessages(m => [
        ...m,
        res.candidate_message,
        res.interviewer_reply,
        ...(res.next_question ? [res.next_question] : []),
      ])
      speak(res.interviewer_reply.content, round?.persona_voice_id)
      if (res.next_question?.message_type === 'practical') {
        setPracticalMode(true)
        setPracticalLab(null)
      } else {
        setPracticalMode(false)
        setPracticalLab(null)
      }
    } catch {
      toast.error('Could not send answer')
    }
  }

  const voiceAnswer = async () => {
    setListening(true)
    const profile = resolveVoiceProfile(round?.persona_voice_id)
    const text = await listen(profile.locale || 'en-IN')
    setListening(false)
    if (text) {
      setAnswer(text)
      await submitAnswer(text)
    }
  }

  const endInterview = async () => {
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

  const fmt = (s) => {
    if (s == null) return '--:--'
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  const permissionDialog = (
    <MediaPermissionDialog
      open={!!permissionRequest}
      type={permissionRequest || 'both'}
      loading={mediaLoading}
      onAllow={() => executeMediaRequest(permissionRequest || 'both')}
      onBlock={() => {
        setPermissionRequest(null)
        setMediaError('Camera and microphone are required for interviews. Click Enable when you are ready.')
      }}
    />
  )

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
          <Link to={`/interviews/campaign/${round.campaign_id || ''}`} className="text-xs text-surface-500 hover:text-white inline-flex items-center gap-1">
            <ArrowLeft size={14} /> Back
          </Link>
          <button type="button" onClick={cancelInterview} className="text-xs text-red-400 hover:text-red-300 inline-flex items-center gap-1">
            <X size={14} /> Cancel
          </button>
        </div>
        <h1 className="text-xl font-bold text-white">Pre-interview check</h1>
        {round.is_sample && (
          <p className="text-xs text-cyan-400 font-medium">Free sample — {round.duration_minutes} minutes only</p>
        )}
        <p className="text-sm text-surface-400">{round.title} with {round.persona_name}</p>
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
        {mediaError && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
            {mediaError}
          </div>
        )}
        <div className="flex flex-wrap gap-2">
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
      {permissionDialog}
      </>
    )
  }

  return (
    <>
    <div className="h-[calc(100vh-4rem)] flex flex-col bg-surface-950">
      <header className="flex items-center justify-between px-4 py-2 border-b border-surface-800 bg-surface-900/80 gap-2 overflow-x-auto">
        <div className="min-w-0 shrink">
          <Link to={`/interviews/campaign/${round.campaign_id || ''}`} className="text-[10px] text-surface-500 hover:text-white inline-flex items-center gap-1">
            <ArrowLeft size={12} /> Back
          </Link>
          <p className="text-xs text-indigo-400">{round.persona_name}</p>
          <p className="text-sm font-medium text-white truncate">{round.title}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
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
                    await requestMediaAccess('audio')
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
                    await requestMediaAccess('video')
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
                Lab opens in a new tab. Describe what you did in the answer box when finished.
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
              disabled={listening}
              className="btn-secondary px-3"
              title="Voice answer"
            >
              <Mic size={16} />
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
    {permissionDialog}
    </>
  )
}
