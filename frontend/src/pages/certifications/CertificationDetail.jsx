import { useEffect, useState, useCallback } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import {
  Award, ArrowLeft, CheckCircle2, Circle, Clock, ShieldCheck, Timer, ExternalLink,
} from 'lucide-react'
import PublicLayout from '../../components/layout/PublicLayout'
import MarketingPageShell from '../../components/MarketingPageShell'
import { FixitPanel } from '../../components/design'
import { usePageTitle } from '../../hooks/usePageTitle'
import { useAuthStore } from '../../store/authStore'
import { certApi } from '../../api/certifications'

function ProgressBar({ percent }) {
  return (
    <div className="h-2 rounded-full bg-surface-800 overflow-hidden w-full">
      <div
        className="h-full bg-accent-cyan rounded-full transition-all"
        style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
      />
    </div>
  )
}

function fmt(seconds) {
  const s = Math.max(0, seconds | 0)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  return `${h > 0 ? `${h}:` : ''}${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

export default function CertificationDetail() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [exam, setExam] = useState(null)
  const [result, setResult] = useState(null)
  const [remaining, setRemaining] = useState(0)
  const [busy, setBusy] = useState(false)

  usePageTitle(detail ? `${detail.code} Certification Prep` : 'Certification Prep')

  const load = useCallback(() => {
    setLoading(true)
    certApi
      .detail(slug)
      .then((data) => setDetail(data))
      .catch(() => setDetail(null))
      .finally(() => setLoading(false))
  }, [slug])

  useEffect(() => {
    load()
  }, [load])

  // Resume an in-progress attempt surfaced by the detail payload.
  useEffect(() => {
    if (detail?.active_attempt?.id && !exam && !result) {
      certApi.exam(detail.active_attempt.id).then(setExam).catch(() => {})
    }
  }, [detail, exam, result])

  // Countdown tick for an active exam.
  useEffect(() => {
    if (!exam) return undefined
    setRemaining(exam.seconds_remaining || 0)
    const id = setInterval(() => {
      setRemaining((r) => Math.max(0, r - 1))
    }, 1000)
    return () => clearInterval(id)
  }, [exam])

  const startExam = async () => {
    if (!isAuthenticated) {
      navigate('/login', { state: { from: `/certifications/${slug}` } })
      return
    }
    setBusy(true)
    try {
      const data = await certApi.startExam(slug)
      setExam(data)
      setResult(null)
      toast.success('Timed mock exam started — complete the labs before time runs out.')
    } catch (err) {
      toast.error(err?.response?.data?.error || 'Could not start the exam.')
    } finally {
      setBusy(false)
    }
  }

  const submitExam = async () => {
    if (!exam) return
    setBusy(true)
    try {
      const data = await certApi.submitExam(exam.id)
      setResult(data)
      setExam(null)
      load()
      if (data.passed) toast.success(`Passed with ${data.score}% — certificate issued!`)
      else toast(`Scored ${data.score}% (need ${data.passing_score}%).`)
    } catch (err) {
      toast.error(err?.response?.data?.error || 'Could not submit the exam.')
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return (
      <PublicLayout>
        <MarketingPageShell title="Loading…">
          <div className="space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="fx-panel h-20 animate-pulse bg-surface-900/40" />
            ))}
          </div>
        </MarketingPageShell>
      </PublicLayout>
    )
  }

  if (!detail) {
    return (
      <PublicLayout>
        <MarketingPageShell title="Track not found">
          <Link to="/certifications" className="btn-secondary text-sm inline-flex items-center gap-2">
            <ArrowLeft size={14} /> Back to certifications
          </Link>
        </MarketingPageShell>
      </PublicLayout>
    )
  }

  const earned = detail.earned_certificate

  return (
    <PublicLayout>
      <MarketingPageShell eyebrow={detail.vendor || 'Certification'} title={detail.name} subtitle={detail.description}>
        <Link
          to="/certifications"
          className="text-sm text-surface-400 hover:text-accent-cyan inline-flex items-center gap-1.5 mb-6"
        >
          <ArrowLeft size={14} /> All certifications
        </Link>

        {/* Overall + exam control */}
        <FixitPanel className="mb-8" padding="p-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
            <div>
              <h2 className="font-display font-semibold text-white text-lg flex items-center gap-2">
                <Award size={18} className="text-accent-amber" /> {detail.code} readiness
              </h2>
              <p className="text-sm text-surface-400">
                {detail.overall_percent}% of objective labs complete · pass mark {detail.passing_score}% ·
                {' '}{detail.exam_duration_minutes} min exam
              </p>
            </div>
            <div className="shrink-0">
              {earned ? (
                <span className="inline-flex items-center gap-2 text-sm text-accent-green">
                  <ShieldCheck size={16} /> Certified · {earned.certificate_id}
                </span>
              ) : exam ? (
                <span className="inline-flex items-center gap-2 text-sm text-accent-amber font-medium">
                  <Timer size={16} /> {fmt(remaining)} remaining
                </span>
              ) : (
                <button onClick={startExam} disabled={busy} className="btn-primary text-sm disabled:opacity-60">
                  {busy ? 'Starting…' : 'Start timed mock exam'}
                </button>
              )}
            </div>
          </div>
          <ProgressBar percent={detail.overall_percent} />
        </FixitPanel>

        {/* Active exam panel */}
        {exam ? (
          <FixitPanel className="mb-8 border-accent-amber/30" padding="p-6">
            <div className="flex items-center justify-between gap-4 mb-4">
              <h3 className="font-display font-semibold text-white">Mock exam in progress</h3>
              <button onClick={submitExam} disabled={busy} className="btn-primary text-sm disabled:opacity-60">
                {busy ? 'Submitting…' : 'Submit exam'}
              </button>
            </div>
            <p className="text-sm text-surface-400 mb-4">
              Complete each lab below in a separate tab. When you finish (or time runs out), submit to be graded.
            </p>
            <ul className="space-y-2">
              {exam.scenarios.map((s) => (
                <li key={s.slug}>
                  <Link
                    to={`/scenarios/${s.slug}`}
                    className="flex items-center justify-between gap-3 px-3 py-2 rounded-lg bg-surface-900 border border-surface-800 hover:border-accent-cyan/40 text-sm"
                  >
                    <span className="text-surface-200">{s.title}</span>
                    <span className="text-accent-cyan inline-flex items-center gap-1 text-xs">
                      Open <ExternalLink size={12} />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </FixitPanel>
        ) : null}

        {/* Last result */}
        {result ? (
          <FixitPanel
            className={`mb-8 ${result.passed ? 'border-accent-green/30' : 'border-accent-red/30'}`}
            padding="p-6"
          >
            <h3 className="font-display font-semibold text-white mb-1">
              {result.passed ? 'Passed 🎉' : 'Not yet'}
            </h3>
            <p className="text-sm text-surface-400">
              You scored {result.score}% (pass mark {result.passing_score}%).
              {result.certificate ? ` Certificate ${result.certificate.certificate_id} issued.` : ' Complete more objective labs and try again.'}
            </p>
          </FixitPanel>
        ) : null}

        {/* Objectives */}
        <div className="space-y-4">
          {detail.objectives.map((o) => (
            <FixitPanel key={o.code} padding="p-5">
              <div className="flex items-center justify-between gap-3 mb-2">
                <h3 className="font-display font-semibold text-white">{o.title}</h3>
                <span className="text-xs text-surface-400 shrink-0">
                  {o.completed_scenarios}/{o.total_scenarios} · {o.percent}%
                </span>
              </div>
              <ProgressBar percent={o.percent} />
              <ul className="mt-3 grid sm:grid-cols-2 gap-x-6 gap-y-1.5">
                {o.scenarios.map((s) => (
                  <li key={s.slug}>
                    <Link
                      to={`/scenarios/${s.slug}`}
                      className="flex items-center gap-2 text-sm text-surface-300 hover:text-accent-cyan py-0.5"
                    >
                      {s.completed ? (
                        <CheckCircle2 size={14} className="text-accent-green shrink-0" />
                      ) : (
                        <Circle size={14} className="text-surface-600 shrink-0" />
                      )}
                      <span className="truncate">{s.title}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </FixitPanel>
          ))}
        </div>
      </MarketingPageShell>
    </PublicLayout>
  )
}
