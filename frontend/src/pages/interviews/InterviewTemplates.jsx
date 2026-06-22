import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { interviewsApi } from '../../api/interviews'
import { usePageTitle } from '../../hooks/usePageTitle'
import { PageHeader } from '../../components/design'
import { Briefcase, ChevronLeft, Play, Video, Layers, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'

export default function InterviewTemplates() {
  usePageTitle('Interview Templates', 'Job-role interview templates — launch a tailored mock in one click.')
  const navigate = useNavigate()
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [launching, setLaunching] = useState(null)

  useEffect(() => {
    interviewsApi.listTemplates()
      .then(d => setTemplates(d.templates || []))
      .catch(() => setTemplates([]))
      .finally(() => setLoading(false))
  }, [])

  const launch = async (tmpl, mode) => {
    setLaunching(`${tmpl.id}:${mode}`)
    try {
      const campaign = await interviewsApi.launchTemplate(tmpl.id, mode)
      toast.success(`${tmpl.name} interview created`)
      navigate(`/interviews/campaign/${campaign.id}`)
    } catch (e) {
      const code = e.response?.data?.code
      if (code === 'SUBSCRIPTION_REQUIRED') {
        toast.error('Subscribe to launch a full interview')
        navigate('/interviews')
      } else {
        toast.error(e.response?.data?.error || 'Could not launch interview')
      }
    } finally {
      setLaunching(null)
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in">
      <Link to="/interviews" className="text-xs text-surface-500 hover:text-white inline-flex items-center gap-1">
        <ChevronLeft size={14} /> Back to interviews
      </Link>
      <PageHeader
        eyebrow="AI Interview Studio"
        title="Job-role templates"
        subtitle="Pick a role to launch a tailored multi-round mock — resume-aware questions, scoring, and a scorecard."
      />

      {loading ? (
        <p className="text-surface-500 text-sm">Loading templates…</p>
      ) : templates.length === 0 ? (
        <div className="glass-card p-8 text-center border border-dashed border-surface-700">
          <Layers className="mx-auto text-surface-600 mb-3" size={32} />
          <p className="text-surface-400 text-sm">No templates available yet.</p>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 gap-3">
          {templates.map(t => (
            <div key={t.id} className="glass-card p-5 border border-surface-800 flex flex-col hover:border-indigo-500/30 transition-colors">
              <div className="flex items-start gap-2">
                <Briefcase size={18} className="text-indigo-400 shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-white">{t.name}</p>
                  <p className="text-[11px] text-surface-500">
                    {t.round_count} rounds · {t.experience_level}
                    {t.primary_technology_name ? ` · ${t.primary_technology_name}` : ''}
                  </p>
                </div>
              </div>
              <p className="text-xs text-surface-400 mt-3 flex-1">{t.description}</p>
              {(t.competencies || []).length > 0 && (
                <div className="flex flex-wrap gap-1 mt-3">
                  {t.competencies.slice(0, 4).map((c, i) => (
                    <span key={i} className="text-[10px] px-2 py-0.5 rounded-md bg-surface-800 text-surface-400 border border-surface-700">{c}</span>
                  ))}
                </div>
              )}
              <div className="mt-4 flex gap-2">
                <button
                  type="button"
                  disabled={!!launching}
                  onClick={() => launch(t, 'live')}
                  className="flex-1 inline-flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium bg-indigo-500/20 border border-indigo-500/40 text-indigo-300 hover:bg-indigo-500/30 disabled:opacity-50"
                >
                  {launching === `${t.id}:live` ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
                  Live interview
                </button>
                <button
                  type="button"
                  disabled={!!launching}
                  onClick={() => launch(t, 'async_video')}
                  className="flex-1 inline-flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium border border-surface-600 text-surface-300 hover:bg-surface-800 disabled:opacity-50"
                  title="Record answers on your own time"
                >
                  {launching === `${t.id}:async_video` ? <Loader2 size={13} className="animate-spin" /> : <Video size={13} />}
                  One-way video
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
