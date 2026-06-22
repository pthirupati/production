import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { interviewsApi } from '../../api/interviews'
import { useAuthStore } from '../../store/authStore'
import { usePageTitle } from '../../hooks/usePageTitle'
import { PageHeader } from '../../components/design'
import { Mic, Video, Calendar, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react'
import toast from 'react-hot-toast'

export default function InterviewInvite() {
  const { token } = useParams()
  const navigate = useNavigate()
  const { isAuthenticated } = useAuthStore()
  usePageTitle('Interview Invitation', 'You have been invited to a FixitLab interview.')
  const [invite, setInvite] = useState(null)
  const [loading, setLoading] = useState(true)
  const [accepting, setAccepting] = useState(false)

  useEffect(() => {
    interviewsApi.getInvitation(token)
      .then(setInvite)
      .catch(() => setInvite({ valid: false, error: 'Invitation not found' }))
      .finally(() => setLoading(false))
  }, [token])

  const accept = async () => {
    if (!isAuthenticated) {
      // Send them to sign in and come back to this invite.
      navigate(`/login?next=${encodeURIComponent(`/interviews/invite/${token}`)}`)
      return
    }
    setAccepting(true)
    try {
      const campaign = await interviewsApi.acceptInvitation(token)
      toast.success('Interview ready — good luck!')
      navigate(`/interviews/campaign/${campaign.id}`)
    } catch (e) {
      toast.error(e.response?.data?.error || 'Could not accept invitation')
    } finally {
      setAccepting(false)
    }
  }

  if (loading) return <p className="text-surface-500 text-sm p-8">Loading invitation…</p>

  if (!invite?.valid) {
    return (
      <div className="max-w-lg mx-auto p-8 text-center space-y-3">
        <AlertCircle className="mx-auto text-amber-400" size={36} />
        <h1 className="text-xl font-bold text-white">Invitation unavailable</h1>
        <p className="text-sm text-surface-400">{invite?.error || 'This invitation link is not valid.'}</p>
      </div>
    )
  }

  const isAsync = invite.mode === 'async_video'

  return (
    <div className="max-w-lg mx-auto space-y-6 animate-fade-in py-4">
      <PageHeader
        eyebrow="You're invited"
        title={invite.role_title || 'Interview invitation'}
        subtitle={isAsync ? 'One-way video interview — record your answers on your own time.' : 'Live AI mock interview with voice and scoring.'}
      />

      <div className="glass-card p-6 border border-indigo-500/20 space-y-4">
        {invite.candidate_name && (
          <p className="text-sm text-surface-300">Hi {invite.candidate_name},</p>
        )}
        <p className="text-sm text-surface-300">
          You've been invited to take the <strong className="text-white">{invite.role_title || invite.template_name || 'interview'}</strong>
          {invite.round_count ? ` (${invite.round_count} round${invite.round_count > 1 ? 's' : ''})` : ''}.
        </p>
        {invite.message && (
          <p className="text-xs text-surface-400 italic border-l-2 border-surface-700 pl-3">{invite.message}</p>
        )}

        <div className="grid grid-cols-3 gap-2 pt-2">
          <div className="text-center p-2 rounded-lg bg-surface-800/60">
            {isAsync ? <Video size={16} className="mx-auto text-cyan-400 mb-1" /> : <Mic size={16} className="mx-auto text-cyan-400 mb-1" />}
            <p className="text-[10px] text-surface-400">{isAsync ? 'Record answers' : 'Voice + adaptive'}</p>
          </div>
          <div className="text-center p-2 rounded-lg bg-surface-800/60">
            <Video size={16} className="mx-auto text-cyan-400 mb-1" />
            <p className="text-[10px] text-surface-400">Camera on</p>
          </div>
          <div className="text-center p-2 rounded-lg bg-surface-800/60">
            <Calendar size={16} className="mx-auto text-cyan-400 mb-1" />
            <p className="text-[10px] text-surface-400">{isAsync ? 'Any time' : 'Schedule rounds'}</p>
          </div>
        </div>

        {invite.already_accepted ? (
          <div className="flex items-center gap-2 text-sm text-emerald-300">
            <CheckCircle2 size={16} /> You've already accepted this invitation.
          </div>
        ) : null}

        <button
          type="button"
          onClick={accept}
          disabled={accepting}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white font-semibold text-sm flex items-center justify-center gap-2 hover:opacity-90 disabled:opacity-50"
        >
          {accepting ? <Loader2 size={16} className="animate-spin" /> : null}
          {isAuthenticated ? (invite.already_accepted ? 'Go to my interview' : 'Accept & start') : 'Sign in to accept'}
        </button>
        {!isAuthenticated && (
          <p className="text-[11px] text-surface-500 text-center">You'll sign in (or create a free account) to take the interview.</p>
        )}
      </div>
    </div>
  )
}
