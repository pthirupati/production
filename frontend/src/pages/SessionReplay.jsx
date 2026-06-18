import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { labApi } from '../api/labs'
import { Play, Pause, RotateCcw, Clock, Terminal, ChevronLeft, FastForward, Sparkles, CheckCircle2, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'

export default function SessionReplay() {
  const { sessionId } = useParams()
  const [replay, setReplay] = useState(null)
  const [commands, setCommands] = useState(null)
  const [loading, setLoading] = useState(true)
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [speed, setSpeed] = useState(1)
  const [tab, setTab] = useState('replay') // replay | commands | review
  const [aiReview, setAiReview] = useState(null)
  const [reviewLoading, setReviewLoading] = useState(false)

  const terminalRef = useRef(null)
  const outputRef = useRef('')
  const timerRef = useRef(null)

  useEffect(() => {
    Promise.all([
      labApi.getSessionReplay(sessionId).catch(() => null),
      labApi.getCommandHistory(sessionId).catch(() => null),
    ]).then(([rep, cmds]) => {
      setReplay(rep)
      setCommands(cmds)
    }).catch(() => toast.error('Failed to load session data'))
      .finally(() => setLoading(false))
  }, [sessionId])

  const handleLoadReview = async () => {
    if (aiReview) return
    setReviewLoading(true)
    try {
      const res = await labApi.getAiReview(sessionId)
      if (res.review) {
        setAiReview(res.review)
      } else {
        const generated = await labApi.generateAiReview(sessionId)
        setAiReview(generated.review)
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Review unavailable for this session')
    } finally {
      setReviewLoading(false)
    }
  }

  const renderUpToTime = useCallback((targetTime) => {
    if (!replay?.events || !terminalRef.current) return
    let text = ''
    for (const evt of replay.events) {
      if (evt[0] > targetTime) break
      if (evt[1] === 'o') {
        text += evt[2]
      }
    }
    outputRef.current = text
    let pre = terminalRef.current.querySelector('pre')
    if (!pre) {
      pre = document.createElement('pre')
      pre.style.margin = '0'
      pre.style.whiteSpace = 'pre-wrap'
      pre.style.wordBreak = 'break-all'
      pre.style.fontFamily = 'monospace'
      pre.style.fontSize = '13px'
      pre.style.lineHeight = '1.5'
      pre.style.color = '#e2e8f0'
      terminalRef.current.textContent = ''
      terminalRef.current.appendChild(pre)
    }
    pre.textContent = text
    terminalRef.current.scrollTop = terminalRef.current.scrollHeight
  }, [replay])

  const handlePlay = () => {
    if (!replay?.events?.length) return
    setPlaying(true)
    const startTime = currentTime
    const startReal = Date.now()

    timerRef.current = setInterval(() => {
      const elapsed = (Date.now() - startReal) / 1000 * speed
      const newTime = startTime + elapsed
      if (newTime >= replay.total_duration) {
        setCurrentTime(replay.total_duration)
        setPlaying(false)
        clearInterval(timerRef.current)
        renderUpToTime(replay.total_duration)
      } else {
        setCurrentTime(newTime)
        renderUpToTime(newTime)
      }
    }, 50)
  }

  const handlePause = () => {
    setPlaying(false)
    if (timerRef.current) clearInterval(timerRef.current)
  }

  const handleReset = () => {
    handlePause()
    setCurrentTime(0)
    if (terminalRef.current) terminalRef.current.innerHTML = ''
    outputRef.current = ''
  }

  const handleSeek = (e) => {
    const time = parseFloat(e.target.value)
    setCurrentTime(time)
    renderUpToTime(time)
  }

  useEffect(() => {
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [])

  const formatTime = (s) => {
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`
  }

  if (loading) return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="w-8 h-8 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
    </div>
  )

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/lab-history" className="text-sm text-surface-500 hover:text-accent-cyan flex items-center gap-1 mb-2">
            <ChevronLeft size={14} /> Back to History
          </Link>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Terminal size={22} className="text-accent-cyan" />
            Session Replay
          </h1>
          <p className="text-surface-400 text-sm mt-0.5">{replay?.scenario_title || commands?.scenario_title || 'Lab Session'}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-900 rounded-lg p-1 w-fit">
        {[
          { key: 'replay', label: 'Terminal Replay', icon: Play },
          { key: 'commands', label: 'Command Log', icon: Terminal },
          { key: 'review', label: 'AI Review', icon: Sparkles },
        ].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => { setTab(key); if (key === 'review') handleLoadReview() }}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === key ? 'bg-surface-700 text-white' : 'text-surface-500 hover:text-surface-300'
            }`}
          >
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {/* Replay tab */}
      {tab === 'replay' && (
        <div className="glass-card overflow-hidden">
          {replay ? (
            <>
              {/* Terminal output */}
              <div
                ref={terminalRef}
                className="bg-surface-950 p-4 h-[400px] overflow-y-auto font-mono text-sm"
              />

              {/* Playback controls */}
              <div className="p-4 border-t border-surface-800 space-y-3">
                {/* Seek bar */}
                <input
                  type="range"
                  min={0}
                  max={replay.total_duration || 1}
                  step={0.1}
                  value={currentTime}
                  onChange={handleSeek}
                  className="w-full h-1.5 bg-surface-800 rounded-full appearance-none cursor-pointer accent-accent-cyan"
                />
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {playing ? (
                      <button onClick={handlePause} className="p-2 rounded-lg bg-surface-800 text-white hover:bg-surface-700" title="Pause">
                        <Pause size={16} />
                      </button>
                    ) : (
                      <button onClick={handlePlay} className="p-2 rounded-lg bg-accent-cyan text-surface-950 hover:bg-accent-cyan/80" title="Play">
                        <Play size={16} />
                      </button>
                    )}
                    <button onClick={handleReset} className="p-2 rounded-lg bg-surface-800 text-surface-400 hover:text-white" title="Reset">
                      <RotateCcw size={16} />
                    </button>

                    {/* Speed control */}
                    <div className="flex items-center gap-1 ml-2">
                      <FastForward size={14} className="text-surface-500" />
                      {[0.5, 1, 2, 4].map(s => (
                        <button
                          key={s}
                          onClick={() => setSpeed(s)}
                          className={`px-2 py-0.5 rounded text-xs font-mono ${
                            speed === s ? 'bg-accent-cyan/20 text-accent-cyan' : 'text-surface-500 hover:text-white'
                          }`}
                        >{s}x</button>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-surface-500">
                    <Clock size={12} />
                    {formatTime(currentTime)} / {formatTime(replay.total_duration)}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="p-12 text-center">
              <Terminal size={32} className="mx-auto text-surface-700 mb-3" />
              <p className="text-surface-500">No terminal recording available for this session</p>
            </div>
          )}
        </div>
      )}

      {/* Commands tab */}
      {tab === 'commands' && (
        <div className="glass-card">
          {commands?.commands?.length > 0 ? (
            <div className="divide-y divide-surface-800">
              <div className="px-4 py-3 bg-surface-900/50 text-xs text-surface-500 flex items-center justify-between">
                <span>{commands.total_commands} commands recorded</span>
              </div>
              {commands.commands.map((cmd, i) => (
                <div key={i} className="px-4 py-3 hover:bg-surface-800/30 transition-colors">
                  <div className="flex items-center justify-between gap-4">
                    <code className="text-sm text-accent-green font-mono flex-1 break-all">
                      $ {cmd.command}
                    </code>
                    <span className="text-[10px] text-surface-600 shrink-0">
                      {new Date(cmd.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-12 text-center">
              <Terminal size={32} className="mx-auto text-surface-700 mb-3" />
              <p className="text-surface-500">No command history recorded for this session</p>
            </div>
          )}
        </div>
      )}

      {/* AI Review tab */}
      {tab === 'review' && (
        <div className="glass-card p-6">
          {reviewLoading ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <div className="w-8 h-8 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
              <p className="text-surface-400 text-sm">Analyzing your session…</p>
            </div>
          ) : aiReview ? (
            <div className="space-y-6">
              <div className="flex items-center gap-2">
                <Sparkles size={18} className="text-accent-cyan" />
                <h3 className="text-white font-semibold">AI Performance Review</h3>
              </div>
              <p className="text-surface-300 text-sm bg-surface-800/50 rounded-xl px-4 py-3 border border-surface-700">{aiReview.overall}</p>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: 'Commands', value: aiReview.stats.total_commands },
                  { label: 'Errors', value: aiReview.stats.error_commands },
                  { label: 'Hints Used', value: aiReview.stats.hints_used },
                  { label: 'Solved', value: aiReview.stats.solved ? 'Yes' : 'No' },
                ].map(({ label, value }) => (
                  <div key={label} className="bg-surface-800/50 rounded-xl p-3 text-center border border-surface-700">
                    <div className="text-lg font-bold text-white">{value}</div>
                    <div className="text-xs text-surface-500 mt-0.5">{label}</div>
                  </div>
                ))}
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <h4 className="text-accent-green text-sm font-medium mb-2 flex items-center gap-1.5">
                    <CheckCircle2 size={14} /> Strengths
                  </h4>
                  <ul className="space-y-1.5">
                    {aiReview.strengths.map((s, i) => (
                      <li key={i} className="text-sm text-surface-300 flex items-start gap-2">
                        <span className="text-accent-green mt-0.5 shrink-0">·</span> {s}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4 className="text-accent-amber text-sm font-medium mb-2 flex items-center gap-1.5">
                    <AlertCircle size={14} /> Areas to Improve
                  </h4>
                  <ul className="space-y-1.5">
                    {aiReview.improvements.map((s, i) => (
                      <li key={i} className="text-sm text-surface-300 flex items-start gap-2">
                        <span className="text-accent-amber mt-0.5 shrink-0">·</span> {s}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-12 text-center">
              <Sparkles size={32} className="mx-auto text-surface-700 mb-3" />
              <p className="text-surface-500">Could not load review for this session.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
