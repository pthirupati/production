import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { interviewsApi } from '../../api/interviews'
import { Calendar, Play, CheckCircle2, Lock, Award, ChevronRight, ChevronLeft, Trash2, X } from 'lucide-react'
import toast from 'react-hot-toast'
import { useConfirm } from '../../hooks/useConfirm'
import { PageHeader } from '../../components/design'

export default function InterviewCampaign() {
  const { confirm, ConfirmPortal } = useConfirm()
  const { campaignId } = useParams()
  const navigate = useNavigate()
  const [campaign, setCampaign] = useState(null)
  const [loading, setLoading] = useState(true)

  const [rescheduleRoundId, setRescheduleRoundId] = useState(null)
  const [rescheduleAt, setRescheduleAt] = useState('')
  const [confirmDeleteRoundId, setConfirmDeleteRoundId] = useState(null)
  const [deletingRoundId, setDeletingRoundId] = useState(null)

  const DELETABLE_ROUND_STATUSES = ['completed', 'passed', 'failed', 'abandoned', 'locked', 'schedulable', 'ready']

  const deleteRound = async (roundId) => {
    setDeletingRoundId(roundId)
    try {
      await interviewsApi.deleteRound(roundId)
      setCampaign(prev => ({
        ...prev,
        rounds: (prev.rounds || []).filter(r => r.id !== roundId),
      }))
      toast.success('Round deleted')
    } catch (e) {
      toast.error(e.response?.data?.error || 'Could not delete round')
    } finally {
      setDeletingRoundId(null)
      setConfirmDeleteRoundId(null)
    }
  }

  const load = () => {
    interviewsApi.getCampaign(campaignId)
      .then(setCampaign)
      .catch(() => toast.error('Interview not found'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [campaignId])

  const scheduleRound = async (round, at) => {
    try {
      const dt = at || new Date(Date.now() + 3600000).toISOString()
      await interviewsApi.scheduleRound(round.id, dt)
      toast.success('Round scheduled — check your email')
      setRescheduleRoundId(null)
      load()
    } catch (e) {
      toast.error(e.response?.data?.error || 'Could not schedule')
    }
  }

  const cancelCampaign = async () => {
    if (!await confirm({ message: 'Cancel this entire interview campaign?', danger: true, confirmLabel: 'Cancel campaign' })) return
    try {
      await interviewsApi.cancelCampaign(campaignId)
      toast.success('Interview cancelled')
      navigate('/interviews')
    } catch (e) {
      toast.error(e.response?.data?.error || 'Could not cancel')
    }
  }

  const startRound = async (round) => {
    // One-way async video rounds use the recording room; live rounds use the
    // real-time interview room.
    if (round.mode === 'async_video' || campaign?.mode === 'async_video') {
      navigate(`/interviews/async/${round.id}`)
    } else {
      navigate(`/interviews/room/${round.id}`)
    }
  }

  if (loading) return <p className="text-surface-500 text-sm p-8">Loading…</p>
  if (!campaign) return null

  return (
    <>
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">
      <Link
        to="/interviews"
        className="text-xs text-surface-500 hover:text-white inline-flex items-center gap-1"
      >
        <ChevronLeft size={14} /> Back to interviews
      </Link>
      <PageHeader
        eyebrow="AI Interview Studio"
        title={campaign.title}
        subtitle={`${campaign.is_sample ? 'Free sample' : `${campaign.round_count} rounds`} · ${campaign.experience_level}`}
      />
      {!campaign.is_sample && campaign.status !== 'cancelled' && campaign.status !== 'completed' && (
        <button type="button" onClick={cancelCampaign} className="text-xs text-red-400 hover:text-red-300 -mt-4">
          Cancel interview
        </button>
      )}
      {campaign.is_sample && (
        <p className="text-xs text-cyan-400 -mt-4">
          One-time preview — start the room when ready. No scheduling needed.
        </p>
      )}

      {campaign.certificate_id && (
        <div className="glass-card p-4 border border-emerald-500/30 bg-emerald-500/10 flex items-center gap-3">
          <Award className="text-emerald-400" size={24} />
          <div>
            <p className="text-sm font-medium text-emerald-300">All rounds cleared!</p>
            <p className="text-xs text-surface-400">Certificate: {campaign.certificate_id}</p>
            <Link
              to={`/verify-certificate?certificate_id=${campaign.certificate_id}`}
              className="text-xs text-indigo-400 hover:underline mt-1 inline-block"
            >
              Verify & share →
            </Link>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {(campaign.rounds || []).map((round, i) => {
          const locked = round.status === 'locked'
          const passed = round.status === 'passed'
          const canSchedule = ['schedulable', 'scheduled'].includes(round.status)
          const canStart = ['scheduled', 'ready', 'schedulable'].includes(round.status)
          const isSample = campaign.is_sample

          return (
            <div
              key={round.id}
              className={`glass-card p-4 border ${
                passed ? 'border-emerald-500/30' : locked ? 'border-surface-800 opacity-60' : 'border-surface-700'
              }`}
            >
              {confirmDeleteRoundId === round.id ? (
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm text-surface-300">Delete this interview round? This cannot be undone.</p>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      disabled={deletingRoundId === round.id}
                      onClick={() => deleteRound(round.id)}
                      className="px-3 py-1.5 rounded-lg bg-red-500/20 border border-red-500/40 text-red-300 text-xs font-medium hover:bg-red-500/30 disabled:opacity-50"
                    >
                      {deletingRoundId === round.id ? 'Deleting…' : 'Yes, delete'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmDeleteRoundId(null)}
                      className="p-1.5 rounded-lg hover:bg-surface-700 text-surface-400"
                    >
                      <X size={14} />
                    </button>
                  </div>
                </div>
              ) : (
              <>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs text-indigo-400 font-semibold uppercase">Round {round.round_number}</p>
                  <p className="text-sm font-medium text-white">{round.title}</p>
                  <p className="text-xs text-surface-500 mt-1">
                    {round.duration_minutes} min · {round.persona_name} · {round.status}
                  </p>
                  {round.schedule_deadline && round.status === 'schedulable' && (
                    <p className="text-xs text-amber-400 mt-1">
                      Schedule within 48h (by {new Date(round.schedule_deadline).toLocaleString()})
                    </p>
                  )}
                  {round.overall_score != null && (
                    <p className="text-xs text-surface-400 mt-1">Score: {round.overall_score.toFixed(0)}/100</p>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {locked && <Lock size={18} className="text-surface-600" />}
                  {passed && <CheckCircle2 size={18} className="text-emerald-400" />}
                  {DELETABLE_ROUND_STATUSES.includes(round.status) && (
                    <button
                      type="button"
                      title="Delete round"
                      onClick={() => setConfirmDeleteRoundId(round.id)}
                      className="p-1.5 rounded-lg text-surface-600 hover:text-red-400 hover:bg-surface-800 transition-colors"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap gap-2 mt-3">
                {canSchedule && round.status === 'schedulable' && !isSample && (
                  <>
                    <button
                      type="button"
                      onClick={() => scheduleRound(round)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border border-surface-600 text-surface-300 hover:bg-surface-800"
                    >
                      <Calendar size={12} /> Schedule (+1h)
                    </button>
                    <button
                      type="button"
                      onClick={() => setRescheduleRoundId(rescheduleRoundId === round.id ? null : round.id)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border border-surface-600 text-surface-300 hover:bg-surface-800"
                    >
                      <Calendar size={12} /> Pick time
                    </button>
                  </>
                )}
                {rescheduleRoundId === round.id && (
                  <div className="w-full flex gap-2 items-center mt-2">
                    <input
                      type="datetime-local"
                      value={rescheduleAt}
                      onChange={e => setRescheduleAt(e.target.value)}
                      className="input-field text-xs flex-1"
                    />
                    <button
                      type="button"
                      onClick={() => scheduleRound(round, rescheduleAt ? new Date(rescheduleAt).toISOString() : null)}
                      className="btn-primary text-xs"
                    >
                      Save
                    </button>
                  </div>
                )}
                {round.status === 'scheduled' && round.scheduled_at && !isSample && (
                  <button
                    type="button"
                    onClick={() => setRescheduleRoundId(rescheduleRoundId === round.id ? null : round.id)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border border-amber-500/40 text-amber-300"
                  >
                    <Calendar size={12} /> Reschedule
                  </button>
                )}
                {canStart && !locked && (
                  <button
                    type="button"
                    onClick={() => startRound(round)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg bg-indigo-500/20 border border-indigo-500/40 text-indigo-300"
                  >
                    <Play size={12} /> Enter room
                  </button>
                )}
                {round.report && (
                  <Link
                    to={`/interviews/round/${round.id}/report`}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border border-surface-600 text-surface-400"
                  >
                    Report <ChevronRight size={12} />
                  </Link>
                )}
              </div>
              </>
              )}
            </div>
          )
        })}
      </div>
    </div>
    <ConfirmPortal />
    </>
  )
}
