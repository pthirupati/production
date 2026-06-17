import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { interviewsApi } from '../../api/interviews'
import api from '../../api/client'
import { Upload, ChevronRight, ChevronLeft, User, Briefcase, Plus, X } from 'lucide-react'
import toast from 'react-hot-toast'

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

  useEffect(() => {
    api.get('/technologies/').then(r => setTechnologies(r.data || [])).catch(() => {})
    interviewsApi.getVoices().then(d => setVoices(d.voices || [])).catch(() => {})
    interviewsApi.getProfile().then(p => {
      if (p) setForm(f => ({ ...f, ...p, primary_technology: p.primary_technology || '' }))
    }).catch(() => {})
  }, [])

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

  const saveProfile = async () => {
    setSaving(true)
    try {
      const payload = {
        ...form,
        secondary_technologies: JSON.stringify(form.secondary_technologies),
        primary_technology: form.primary_technology || null,
        current_package_lpa: form.current_package_lpa || null,
        notice_period_days: form.notice_period_days || null,
      }
      await interviewsApi.updateProfile(payload, resumeFile)
      toast.success('Profile saved')
      return true
    } catch {
      toast.error('Could not save profile')
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
      <div>
        <Link to="/interviews" className="text-xs text-surface-500 hover:text-white">← Interview Studio</Link>
        <h1 className="text-2xl font-bold text-white mt-2">Interview setup</h1>
        <p className="text-sm text-surface-400 mt-1">
          Resume is optional — we personalize from your career inputs and technology selections.
        </p>
      </div>

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
          <label className="block">
            <span className="text-sm text-surface-300 flex items-center gap-2 mb-2">
              <Upload size={16} /> Upload resume (optional — PDF preferred)
            </span>
            <input
              type="file"
              accept=".pdf,.doc,.docx,.txt"
              onChange={e => setResumeFile(e.target.files?.[0] || null)}
              className="text-sm text-surface-400 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-indigo-500/20 file:text-indigo-300"
            />
          </label>
          <p className="text-xs text-surface-500">
            Without a resume we analyze your role, experience level, and technology picks to tailor questions.{' '}
            <a href="/privacy" target="_blank" rel="noreferrer" className="text-indigo-400 hover:underline">Privacy policy</a>
          </p>
          {voices.length > 0 && (
            <label className="block">
              <span className="text-xs text-surface-400">Interviewer voice accent</span>
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
              <span className="text-xs text-surface-400">Target role</span>
              <input
                value={form.target_role}
                onChange={e => set('target_role', e.target.value)}
                placeholder="e.g. Senior DevOps Engineer"
                className="input-field mt-1 w-full"
              />
            </label>
            <label className="block">
              <span className="text-xs text-surface-400">Primary technology</span>
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
              <span className="text-xs text-surface-400">Experience level</span>
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
              <span className="text-xs text-surface-400">Years of experience</span>
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
              <span className="text-xs text-surface-400">Package (LPA, optional)</span>
              <input
                value={form.current_package_lpa}
                onChange={e => set('current_package_lpa', e.target.value)}
                placeholder="e.g. 18"
                className="input-field mt-1 w-full"
              />
            </label>
            <label className="block">
              <span className="text-xs text-surface-400">Notice period (days)</span>
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
