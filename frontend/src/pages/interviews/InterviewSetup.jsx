import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { interviewsApi } from '../../api/interviews'
import api from '../../api/client'
import { Upload, ChevronRight, ChevronLeft, User, Briefcase, Plus, X, Sparkles } from 'lucide-react'
import toast from 'react-hot-toast'
import { LabelWithHint } from '../../components/FieldHint'
import { PageHeader } from '../../components/design'
import ResumeScoreCard from '../../components/interviews/ResumeScoreCard'

const LEVELS = [
  { id: 'junior', label: 'Junior (0–2 yrs)' },
  { id: 'mid', label: 'Mid (3–5 yrs)' },
  { id: 'senior', label: 'Senior (6–10 yrs)' },
  { id: 'lead', label: 'Lead / Principal' },
]

export default function InterviewSetup() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [technologies, setTechnologies] = useState([])
  const [resumeFile, setResumeFile] = useState(null)
  const [form, setForm] = useState({
    primary_technology: '',
    secondary_technologies: [],
    experience_level: 'mid',
    years_experience: 3,
    current_company: '',
    current_package_lpa: '',
    target_role: '',
    location: '',
    notice_period_days: '',
    voice_id: 'indian-female',
    round_count: 3,
  })
  const [voices, setVoices] = useState([])
  const [saving, setSaving] = useState(false)
  const [customTechInput, setCustomTechInput] = useState('')
  const [resumeScore, setResumeScore] = useState(null)
  const [scoringResume, setScoringResume] = useState(false)

  useEffect(() => {
    api.get('/technologies/').then(r => setTechnologies(r.data || [])).catch(() => {})
    interviewsApi.getVoices().then(d => setVoices(d.voices || [])).catch(() => {})
    interviewsApi.getProfile().then(p => {
      if (!p) return
      setForm(f => ({
        ...f,
        primary_technology: p.primary_technology || '',
        secondary_technologies: Array.isArray(p.secondary_technologies) ? p.secondary_technologies : [],
        experience_level: p.experience_level || f.experience_level,
        years_experience: p.years_experience ?? f.years_experience,
        current_company: p.current_company || '',
        current_package_lpa: p.current_package_lpa ?? '',
        target_role: p.target_role || '',
        location: p.location || '',
        notice_period_days: p.notice_period_days ?? '',
        voice_id: p.voice_id || f.voice_id,
        round_count: f.round_count,
      }))
      // Returning users with a saved resume see their score immediately.
      if (p.has_resume) {
        interviewsApi.scoreResume({}).then(r => { if (r) setResumeScore(r) }).catch(() => {})
      }
    }).catch(() => {})
  }, [])

  // Re-score on the final step only when a resume file is attached.
  useEffect(() => {
    if (step === 2 && resumeFile) {
      saveProfile()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step])

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const toggleSecondary = (name) => {
    setForm(f => {
      const list = f.secondary_technologies || []
      return {
        ...f,
        secondary_technologies: list.includes(name)
          ? list.filter(x => x !== name)
          : [...list, name].slice(0, 5),
      }
    })
  }

  const addCustomTech = () => {
    const name = customTechInput.trim()
    if (!name) return
    const list = form.secondary_technologies || []
    if (list.length >= 5) { toast.error('Maximum 5 technologies'); return }
    if (list.includes(name)) { setCustomTechInput(''); return }
    setForm(f => ({ ...f, secondary_technologies: [...(f.secondary_technologies || []), name] }))
    setCustomTechInput('')
  }

  const profilePayload = () => ({
    primary_technology: form.primary_technology || null,
    secondary_technologies: Array.isArray(form.secondary_technologies) ? form.secondary_technologies : [],
    experience_level: form.experience_level,
    years_experience: Number(form.years_experience) || 0,
    current_company: form.current_company || '',
    current_package_lpa: form.current_package_lpa || null,
    target_role: form.target_role || '',
    location: form.location || '',
    notice_period_days: form.notice_period_days || null,
    voice_id: form.voice_id || 'indian-female',
  })

  // Score the resume against the chosen technology/role/level. The profile PUT
  // already returns a fresh resume_score; this is for an explicit re-score
  // (e.g. the "Score my resume" button) using the latest career inputs.
  const runResumeScore = async () => {
    setScoringResume(true)
    try {
      const result = await interviewsApi.scoreResume({
        primary_technology: form.primary_technology || '',
        target_role: form.target_role || '',
        experience_level: form.experience_level || 'mid',
        years_experience: Number(form.years_experience) || 0,
      })
      if (result?.has_resume !== false && result?.overall_score != null) setResumeScore(result)
      else setResumeScore(null)
    } catch {
      /* silentError on the client; leave any prior score in place */
    } finally {
      setScoringResume(false)
    }
  }

  const saveProfile = async () => {
    setSaving(true)
    try {
      const saved = await interviewsApi.updateProfile(profilePayload(), resumeFile)
      if (saved && saved.resume_score?.has_resume !== false && saved.resume_score?.overall_score != null) {
        setResumeScore(saved.resume_score)
      } else if (!resumeFile) {
        setResumeScore(null)
      }
      toast.success('Profile saved')
      return true
    } catch (err) {
      const detail = err?.response?.data
      const msg = typeof detail === 'string'
        ? detail
        : detail && typeof detail === 'object'
          ? Object.values(detail).flat().join(', ').slice(0, 120)
          : 'Could not save profile'
      toast.error(msg)
      return false
    } finally {
      setSaving(false)
    }
  }

  const launch = async () => {
    if (!form.target_role?.trim() && !form.primary_technology) {
      toast.error('Add a target role or primary technology to personalize questions')
      return
    }
    if (!(await saveProfile())) return
    try {
      const campaign = await interviewsApi.createCampaign({
        round_count: form.round_count,
        title: `${form.target_role || 'Mock Interview'} — ${form.experience_level}`,
      })
      toast.success('Interview created — schedule round 1')
      navigate(`/interviews/campaign/${campaign.id}`)
    } catch (e) {
      toast.error(e.response?.data?.error || 'Could not create interview')
    }
  }

  const steps = ['Resume', 'Career', 'Rounds']

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in">
      <PageHeader
        eyebrow="AI Interview Studio"
        title="Interview setup"
        subtitle="Resume is optional — we personalize from your career inputs and technology selections."
      />

      <div className="flex gap-2">
        {steps.map((s, i) => (
          <div
            key={s}
            className={`flex-1 h-1 rounded-full ${i <= step ? 'bg-indigo-500' : 'bg-surface-800'}`}
          />
        ))}
      </div>

      {step === 0 && (
        <div className="glass-card p-6 space-y-4 border border-surface-800">
          <div className="block">
            <LabelWithHint
              label="Upload resume (optional — PDF preferred)"
              hint="PDF or DOCX up to 5MB. We extract skills and experience to tailor interview questions. You can skip this and rely on career fields instead."
              className="text-sm text-surface-300 flex items-center gap-2 mb-2"
            />
            <input
              type="file"
              accept=".pdf,.doc,.docx,.txt"
              onChange={e => { setResumeFile(e.target.files?.[0] || null); setResumeScore(null) }}
              className="text-sm text-surface-400 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-indigo-500/20 file:text-indigo-300"
            />
          </div>
          <p className="text-xs text-surface-500">
            Without a resume we analyze your role, experience level, and technology picks to tailor questions.{' '}
            <a href="/privacy" target="_blank" rel="noreferrer" className="text-indigo-400 hover:underline">Privacy policy</a>
          </p>

          {(resumeFile || resumeScore) ? (
            <div className="space-y-3">
              <button
                type="button"
                onClick={async () => { if (resumeFile) { await saveProfile() } else { await runResumeScore() } }}
                disabled={scoringResume || saving}
                className="btn-secondary text-xs inline-flex items-center gap-1.5 disabled:opacity-50"
              >
                <Sparkles size={13} /> {resumeScore ? 'Re-score resume' : 'Score my resume'}
              </button>
              <ResumeScoreCard score={resumeScore} loading={scoringResume} />
            </div>
          ) : (
            <ResumeScoreCard score={null} />
          )}
          {voices.length > 0 && (
            <label className="block">
              <LabelWithHint
                label="Interviewer voice accent"
                hint="Choose the AI interviewer accent for spoken questions. You can change this before each round."
                className="text-xs text-surface-400"
              />
              <select
                value={form.voice_id}
                onChange={e => set('voice_id', e.target.value)}
                className="input-field mt-1 w-full"
              >
                {voices.map(v => (
                  <option key={v.code} value={v.code}>{v.label} ({v.region})</option>
                ))}
              </select>
            </label>
          )}
        </div>
      )}

      {step === 1 && (
        <div className="glass-card p-6 space-y-4 border border-surface-800">
          <div className="grid sm:grid-cols-2 gap-4">
            <label className="block sm:col-span-2">
              <LabelWithHint
                label="Target role"
                hint="Job title you're preparing for, e.g. Senior DevOps Engineer. Used to generate role-specific questions."
                className="text-xs text-surface-400"
              />
              <input
                value={form.target_role}
                onChange={e => set('target_role', e.target.value)}
                placeholder="e.g. Senior DevOps Engineer"
                className="input-field mt-1 w-full"
              />
            </label>
            <label className="block">
              <LabelWithHint
                label="Primary technology"
                hint="Main stack for technical rounds. Select from your subscribed technologies or leave empty for general questions."
                className="text-xs text-surface-400"
              />
              <select
                value={form.primary_technology}
                onChange={e => set('primary_technology', e.target.value)}
                className="input-field mt-1 w-full"
              >
                <option value="">Select…</option>
                {technologies.map(t => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <LabelWithHint
                label="Experience level"
                hint="Junior (0–2 yrs), Mid (3–5), Senior (6–10), or Lead. Adjusts question depth and expectations."
                className="text-xs text-surface-400"
              />
              <select
                value={form.experience_level}
                onChange={e => set('experience_level', e.target.value)}
                className="input-field mt-1 w-full"
              >
                {LEVELS.map(l => (
                  <option key={l.id} value={l.id}>{l.label}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <LabelWithHint
                label="Years of experience"
                hint="Total professional years in your field. Number only, e.g. 5."
                className="text-xs text-surface-400"
              />
              <input
                type="number"
                min={0}
                max={40}
                value={form.years_experience}
                onChange={e => set('years_experience', +e.target.value)}
                className="input-field mt-1 w-full"
              />
            </label>
            <label className="block">
              <span className="text-xs text-surface-400">Current company</span>
              <input
                value={form.current_company}
                onChange={e => set('current_company', e.target.value)}
                className="input-field mt-1 w-full"
              />
            </label>
            <label className="block">
              <LabelWithHint
                label="Package (LPA, optional)"
                hint="Current CTC in Lakhs Per Annum (India). Optional — helps calibrate seniority. Format: 18 or 24.5"
                className="text-xs text-surface-400"
              />
              <input
                value={form.current_package_lpa}
                onChange={e => set('current_package_lpa', e.target.value)}
                placeholder="e.g. 18"
                className="input-field mt-1 w-full"
              />
            </label>
            <label className="block">
              <LabelWithHint
                label="Notice period (days)"
                hint="Days until you can join a new role. Optional number, e.g. 30 or 90."
                className="text-xs text-surface-400"
              />
              <input
                value={form.notice_period_days}
                onChange={e => set('notice_period_days', e.target.value)}
                className="input-field mt-1 w-full"
              />
            </label>
          </div>
          <div>
            <p className="text-xs text-surface-400 mb-2">
              Other technologies (up to 5){' '}
              <span className="text-surface-600">— {form.secondary_technologies?.length || 0}/5 selected</span>
            </p>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {technologies.slice(0, 12).map(t => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => toggleSecondary(t.name)}
                  className={`px-2 py-1 rounded text-xs border ${
                    form.secondary_technologies?.includes(t.name)
                      ? 'border-indigo-500 bg-indigo-500/20 text-indigo-300'
                      : 'border-surface-700 text-surface-500'
                  }`}
                >
                  {t.name}
                </button>
              ))}
            </div>
            {/* Custom selected tags */}
            {form.secondary_technologies?.filter(name => !technologies.some(t => t.name === name)).map(name => (
              <span key={name} className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs border border-cyan-500/40 bg-cyan-500/10 text-cyan-300 mr-1 mb-1">
                {name}
                <button type="button" onClick={() => toggleSecondary(name)}><X size={10} /></button>
              </span>
            ))}
            {/* Free-text input for custom technologies */}
            {(form.secondary_technologies?.length || 0) < 5 && (
              <div className="flex gap-2 mt-2">
                <input
                  value={customTechInput}
                  onChange={e => setCustomTechInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addCustomTech())}
                  placeholder="Type a technology (e.g. Ansible, Terraform…)"
                  className="input-field text-xs flex-1"
                />
                <button
                  type="button"
                  onClick={addCustomTech}
                  className="btn-secondary text-xs inline-flex items-center gap-1 px-3"
                >
                  <Plus size={12} /> Add
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="glass-card p-6 space-y-4 border border-surface-800">
          <p className="text-sm text-surface-300 flex items-center gap-2">
            <Briefcase size={16} /> Choose interview length
          </p>
          {[3, 4, 5].map(n => (
            <button
              key={n}
              type="button"
              onClick={() => set('round_count', n)}
              className={`w-full text-left p-4 rounded-xl border transition-colors ${
                form.round_count === n
                  ? 'border-indigo-500 bg-indigo-500/10'
                  : 'border-surface-700 hover:border-surface-600'
              }`}
            >
              <p className="text-sm font-medium text-white">{n} rounds</p>
              <p className="text-xs text-surface-500 mt-1">
                {n === 3 && 'Technical 45m · Manager 30m · HR 20m'}
                {n === 4 && 'Adds deep-dive round'}
                {n === 5 && 'Adds leadership round'}
              </p>
            </button>
          ))}
          <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-3 text-xs text-amber-200/90">
            <User size={14} className="inline mr-1" />
            Before each round: enable microphone and camera. Interview exits after 5 minutes if either stays off.
          </div>

          {resumeFile || (resumeScore?.has_resume !== false && resumeScore?.overall_score != null) ? (
            <div className="pt-2 border-t border-surface-800">
              <p className="text-xs text-surface-400 mb-2">
                Resume fit for {form.target_role || 'this role'} — questions adapt to your uploaded resume.
              </p>
              <ResumeScoreCard score={resumeScore} loading={scoringResume} />
            </div>
          ) : (
            <div className="pt-2 border-t border-surface-800">
              <ResumeScoreCard score={null} />
            </div>
          )}
        </div>
      )}

      <div className="flex justify-between">
        <button
          type="button"
          disabled={step === 0}
          onClick={() => setStep(s => s - 1)}
          className="btn-secondary text-sm inline-flex items-center gap-1 disabled:opacity-40"
        >
          <ChevronLeft size={16} /> Back
        </button>
        {step < 2 ? (
          <button
            type="button"
            onClick={async () => {
              if (step === 0) await saveProfile()
              setStep(s => s + 1)
            }}
            className="btn-primary text-sm inline-flex items-center gap-1"
          >
            Next <ChevronRight size={16} />
          </button>
        ) : (
          <button
            type="button"
            disabled={saving}
            onClick={launch}
            className="btn-primary text-sm inline-flex items-center gap-1"
          >
            Create interview <ChevronRight size={16} />
          </button>
        )}
      </div>
    </div>
  )
}
