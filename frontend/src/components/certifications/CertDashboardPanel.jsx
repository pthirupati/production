import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Award, Timer, Play, Send, ExternalLink } from 'lucide-react'
import toast from 'react-hot-toast'
import { certApi } from '../../api/certifications'
import { FixitPanel } from '../design'

function fmt(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export default function CertDashboardPanel() {
  const [tracks, setTracks] = useState([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState(null)

  const load = () => {
    certApi.dashboard()
      .then((d) => setTracks(d?.tracks || []))
      .catch(() => setTracks([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const startExam = async (slug) => {
    setBusyId(slug)
    try {
      await certApi.startExam(slug)
      toast.success('Exam started — open labs from the track page.')
      load()
    } catch (err) {
      const data = err?.response?.data
      if (data?.code === 'CERT_SUBSCRIPTION_REQUIRED') {
        toast.error('Purchase cert track access first')
        window.location.href = data.payment_url || `/payment?cert=${slug}`
      } else {
        toast.error(data?.error || 'Could not start exam')
      }
    } finally {
      setBusyId(null)
    }
  }

  const submitExam = async (attemptId, _slug) => {
    setBusyId(attemptId)
    try {
      const result = await certApi.submitExam(attemptId)
      toast.success(
        result.passed
          ? `Passed — ${result.score}%`
          : `Submitted — ${result.score}% (need ${result.passing_score}%)`,
      )
      load()
    } catch (err) {
      toast.error(err?.response?.data?.error || 'Submit failed')
    } finally {
      setBusyId(null)
    }
  }

  if (loading) {
    return (
      <FixitPanel padding="p-5" className="animate-pulse">
        <div className="h-5 w-48 bg-surface-800 rounded mb-3" />
        <div className="h-16 bg-surface-900 rounded" />
      </FixitPanel>
    )
  }

  if (!tracks.length) return null

  return (
    <FixitPanel padding="p-5">
      <div className="flex items-center justify-between gap-3 mb-4">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Award size={18} className="text-accent-amber" /> Certification prep
        </h2>
        <Link to="/certifications" className="text-xs text-accent-cyan hover:underline">All tracks</Link>
      </div>
      <div className="space-y-3">
        {tracks.map((t) => (
          <div
            key={t.slug}
            className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-xl bg-surface-800/40 border border-surface-700/40"
          >
            <div className="min-w-0">
              <p className="font-semibold text-white text-sm">{t.code} · {t.name}</p>
              <p className="text-xs text-surface-400 mt-0.5">
                Readiness {t.overall_percent}% · pass {t.passing_score}%
                {t.active_exam && (
                  <span className="text-accent-amber ml-2 inline-flex items-center gap-1">
                    <Timer size={12} /> {fmt(t.active_exam.seconds_remaining)} left
                  </span>
                )}
                {t.earned_certificate && (
                  <span className="text-accent-green ml-2">Certified</span>
                )}
              </p>
            </div>
            <div className="flex flex-wrap gap-2 shrink-0">
              <Link to={`/certifications/${t.slug}`} className="btn-secondary text-xs inline-flex items-center gap-1">
                <ExternalLink size={12} /> Track
              </Link>
              {t.active_exam ? (
                <>
                  <Link to={`/certifications/${t.slug}`} className="btn-secondary text-xs inline-flex items-center gap-1">
                    <Play size={12} /> Continue exam
                  </Link>
                  <button
                    type="button"
                    disabled={busyId === t.active_exam.id}
                    onClick={() => submitExam(t.active_exam.id, t.slug)}
                    className="btn-primary text-xs inline-flex items-center gap-1 disabled:opacity-60"
                  >
                    <Send size={12} /> {busyId === t.active_exam.id ? 'Submitting…' : 'Submit exam'}
                  </button>
                </>
              ) : !t.earned_certificate ? (
                <button
                  type="button"
                  disabled={busyId === t.slug}
                  onClick={() => startExam(t.slug)}
                  className="btn-primary text-xs inline-flex items-center gap-1 disabled:opacity-60"
                >
                  <Play size={12} /> {busyId === t.slug ? 'Starting…' : 'Start timed exam'}
                </button>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </FixitPanel>
  )
}
