import { useEffect, useState } from 'react'
import { adminApi } from '../../api/admin'
import { AdminPageHeader } from '../../components/design'
import {
  BarChart3, Users, MessageSquare, CreditCard, Settings, CalendarClock, Mic,
  Gift, DollarSign, Eye,
} from 'lucide-react'
import toast from 'react-hot-toast'

const TABS = [
  { id: 'overview', label: 'Analytics', icon: BarChart3 },
  { id: 'live', label: 'Live & scheduled', icon: CalendarClock },
  { id: 'settings', label: 'Platform', icon: Settings },
  { id: 'pricing', label: 'Pricing', icon: DollarSign },
  { id: 'entitlements', label: 'Free access', icon: Gift },
  { id: 'voices', label: 'Voices', icon: Mic },
  { id: 'campaigns', label: 'Campaigns', icon: Users },
  { id: 'questions', label: 'Questions', icon: MessageSquare },
]

export default function AdminInterviews() {
  const [overview, setOverview] = useState(null)
  const [campaigns, setCampaigns] = useState([])
  const [questions, setQuestions] = useState([])
  const [settings, setSettings] = useState(null)
  const [tiers, setTiers] = useState([])
  const [voices, setVoices] = useState([])
  const [live, setLive] = useState({ live: [], scheduled: [] })
  const [joinRequests, setJoinRequests] = useState([])
  const [entitlements, setEntitlements] = useState([])
  const [tab, setTab] = useState('overview')
  const [grantEmail, setGrantEmail] = useState('')
  const [saving, setSaving] = useState(false)

  const reload = () => {
    adminApi.getInterviewOverview().then(setOverview).catch(() => {})
    adminApi.getInterviewCampaigns().then(d => setCampaigns(d.campaigns || [])).catch(() => {})
    adminApi.getInterviewQuestions().then(d => setQuestions(d.questions || [])).catch(() => {})
    adminApi.getInterviewSettings().then(setSettings).catch(() => {})
    adminApi.getInterviewTiers().then(d => setTiers(d.tiers || [])).catch(() => {})
    adminApi.getInterviewVoices().then(d => setVoices(d.voices || [])).catch(() => {})
    adminApi.getInterviewLiveSessions().then(setLive).catch(() => {})
    adminApi.getInterviewJoinRequests().then(d => setJoinRequests(d.requests || [])).catch(() => {})
    adminApi.getInterviewEntitlements().then(d => setEntitlements(d.entitlements || [])).catch(() => {})
  }

  useEffect(() => { reload() }, [])

  const saveSettings = async () => {
    if (!settings) return
    setSaving(true)
    try {
      const data = await adminApi.updateInterviewSettings(settings)
      setSettings(data)
      toast.success('Platform settings saved')
    } catch {
      toast.error('Could not save settings')
    } finally {
      setSaving(false)
    }
  }

  const saveTier = async (tier) => {
    try {
      await adminApi.updateInterviewTier(tier.id, tier)
      toast.success(`${tier.name} updated`)
      reload()
    } catch {
      toast.error('Could not update tier')
    }
  }

  const grantFree = async () => {
    if (!grantEmail.trim()) return
    try {
      await adminApi.grantInterviewEntitlement({ email: grantEmail.trim(), grant_free: true })
      toast.success('Free interview access granted')
      setGrantEmail('')
      reload()
    } catch (e) {
      toast.error(e.response?.data?.error || 'Grant failed')
    }
  }

  const requestJoin = async (roundId) => {
    try {
      const res = await adminApi.requestInterviewJoin(roundId, 'Admin would like to observe this session.')
      toast.success(res.already_pending ? 'Request already pending' : 'Join request sent to candidate')
      reload()
    } catch (e) {
      toast.error(e.response?.data?.error || 'Could not request join')
    }
  }

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="AI Interview Studio"
        subtitle="100% free platform — browser voice + FixitLab AI. Full admin control, pricing, analytics."
      />

      {overview?.uses_paid_apis === false && (
        <p className="text-xs text-emerald-400 -mt-4">No paid AI APIs — voice runs in the browser</p>
      )}

      <div className="flex flex-wrap gap-2 border-b border-surface-800 pb-2">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`px-3 py-1.5 text-xs rounded-lg flex items-center gap-1 ${
              tab === id ? 'bg-indigo-500/20 text-indigo-300' : 'text-surface-500 hover:text-surface-300'
            }`}
          >
            <Icon size={12} /> {label}
          </button>
        ))}
      </div>

      {tab === 'overview' && overview && (
        <div className="space-y-4">
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              { label: 'Campaigns (30d)', val: overview.campaigns_total },
              { label: 'In progress', val: overview.campaigns_in_progress },
              { label: 'Completed', val: overview.campaigns_completed },
              { label: 'Pass rate %', val: overview.pass_rate },
              { label: 'Rounds live', val: overview.rounds_in_progress },
              { label: 'Scheduled', val: overview.rounds_scheduled },
              { label: 'Certificates', val: overview.certificates_issued },
              { label: 'Free users', val: overview.complimentary_users },
              { label: 'Avg score', val: overview.avg_round_score?.toFixed?.(1) ?? '—' },
              { label: 'Questions', val: overview.questions_in_bank },
              { label: 'Active subs', val: overview.active_entitlements },
              { label: 'Reports', val: overview.reports_generated },
            ].map(({ label, val }) => (
              <div key={label} className="fx-stat-card p-4 border border-surface-800">
                <p className="text-2xl font-bold text-white">{val}</p>
                <p className="text-xs text-surface-500">{label}</p>
              </div>
            ))}
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="glass-card p-4 border border-surface-800">
              <p className="text-xs text-surface-500 mb-2">By experience level</p>
              {(overview.by_level || []).map(row => (
                <div key={row.experience_level} className="flex justify-between text-sm text-surface-300 py-1">
                  <span>{row.experience_level}</span>
                  <span>{row.count}</span>
                </div>
              ))}
            </div>
            <div className="glass-card p-4 border border-surface-800">
              <p className="text-xs text-surface-500 mb-2">By round type</p>
              {(overview.by_round_type || []).map(row => (
                <div key={row.round_type} className="flex justify-between text-sm text-surface-300 py-1">
                  <span>{row.round_type}</span>
                  <span>{row.count}</span>
                </div>
              ))}
            </div>
          </div>
          {overview.funnel && (
            <div className="glass-card p-5 border border-indigo-500/20">
              <h3 className="text-sm font-semibold text-indigo-300 mb-3">Sample → Subscribe funnel (30d)</h3>
              <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
                {[
                  { label: 'Sample started', val: overview.funnel.sample_started },
                  { label: 'Sample completed', val: overview.funnel.sample_completed },
                  { label: 'Paid conversions', val: overview.funnel.paid_conversions },
                  { label: 'Conversion %', val: `${overview.funnel.conversion_rate_pct}%` },
                  { label: 'Median days to convert', val: overview.funnel.median_days_to_convert || '—' },
                ].map(({ label, val }) => (
                  <div key={label} className="p-3 rounded-lg bg-surface-900/50 border border-surface-800">
                    <p className="text-lg font-bold text-white">{val}</p>
                    <p className="text-[10px] text-surface-500">{label}</p>
                  </div>
                ))}
              </div>
              <p className="text-xs text-surface-500">Marketing nudges sent (period): {overview.funnel.nudges_sent}</p>
            </div>
          )}
        </div>
      )}

      {tab === 'live' && (
        <div className="space-y-6">
          <section>
            <h2 className="text-sm font-semibold text-amber-400 mb-2 flex items-center gap-1">
              <CalendarClock size={14} /> Live interviews
            </h2>
            {!live.live?.length ? (
              <p className="text-xs text-surface-500">No live sessions right now</p>
            ) : (
              <table className="fx-admin-table">
                <thead>
                  <tr className="text-left text-surface-500 border-b border-surface-800">
                    <th className="py-2 pr-4">Candidate</th>
                    <th className="py-2 pr-4">Round</th>
                    <th className="py-2 pr-4">Type</th>
                    <th className="py-2">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {live.live.map(s => (
                    <tr key={s.round_id} className="border-b border-surface-800/50 text-surface-300">
                      <td className="py-2 pr-4 text-xs">{s.user?.email}</td>
                      <td className="py-2 pr-4">{s.title}</td>
                      <td className="py-2 pr-4">{s.round_type}</td>
                      <td className="py-2">
                        <button
                          type="button"
                          onClick={() => requestJoin(s.round_id)}
                          className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                        >
                          <Eye size={12} /> Request to join
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
          <section>
            <h2 className="text-sm font-semibold text-blue-400 mb-2">Scheduled</h2>
            {!live.scheduled?.length ? (
              <p className="text-xs text-surface-500">No upcoming scheduled rounds</p>
            ) : (
              <div className="space-y-2">
                {live.scheduled.map(s => (
                  <div key={s.round_id} className="glass-card p-3 border border-surface-800 text-xs text-surface-300">
                    <span className="text-white">{s.title}</span>
                    <span className="text-surface-600 mx-2">·</span>
                    {s.user?.email}
                    <span className="text-surface-600 mx-2">·</span>
                    {s.scheduled_at ? new Date(s.scheduled_at).toLocaleString() : 'TBD'}
                  </div>
                ))}
              </div>
            )}
          </section>
          {joinRequests.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-indigo-400 mb-2">Join requests</h2>
              <div className="space-y-2">
                {joinRequests.slice(0, 20).map(req => (
                  <div key={req.id} className="glass-card p-3 border border-surface-800 text-xs text-surface-300">
                    <span className="text-white">{req.round_title}</span>
                    <span className="text-surface-600 mx-2">·</span>
                    {req.status}
                    {req.status === 'approved' && req.observer_token && (
                      <a
                        href={`/interviews/round/${req.round_id}?observer=${req.observer_token}`}
                        className="ml-2 text-indigo-400 hover:underline"
                      >
                        Open observer view
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      )}

      {tab === 'settings' && settings && (
        <div className="glass-card p-4 border border-surface-800 space-y-4 max-w-xl">
          {[
            { key: 'enabled', label: 'Interview Studio enabled', type: 'checkbox' },
            { key: 'staff_free_by_default', label: 'Staff/admins free by default', type: 'checkbox' },
            { key: 'allow_admin_observer', label: 'Allow admin observer join requests', type: 'checkbox' },
            { key: 'free_campaigns_per_month', label: 'Free campaigns per month (non-subscribers)', type: 'number' },
            { key: 'sample_enabled', label: 'Enable free sample interview', type: 'boolean' },
            { key: 'sample_duration_minutes', label: 'Sample duration (minutes)', type: 'number' },
            { key: 'av_grace_seconds', label: 'AV grace seconds', type: 'number' },
            { key: 'schedule_window_hours', label: 'Schedule window (hours)', type: 'number' },
            { key: 'default_pass_threshold', label: 'Default pass threshold %', type: 'number' },
          ].map(({ key, label, type }) => (
            <label key={key} className="flex items-center justify-between gap-4 text-sm text-surface-300">
              <span>{label}</span>
              {type === 'checkbox' ? (
                <input
                  type="checkbox"
                  checked={!!settings[key]}
                  onChange={e => setSettings(s => ({ ...s, [key]: e.target.checked }))}
                  className="rounded"
                />
              ) : (
                <input
                  type="number"
                  value={settings[key]}
                  onChange={e => setSettings(s => ({ ...s, [key]: Number(e.target.value) }))}
                  className="input-field w-24 text-xs"
                />
              )}
            </label>
          ))}
          <p className="text-xs text-surface-500">Voice engine: browser (free Web Speech API)</p>
          {voices.length > 0 && (
            <label className="block text-xs text-surface-400">
              Default interviewer voice
              <select
                value={voices.find(v => v.is_default)?.code || voices[0]?.code || ''}
                onChange={async e => {
                  const voice = voices.find(v => v.code === e.target.value)
                  if (!voice) return
                  try {
                    await adminApi.updateInterviewVoice(voice.id, { ...voice, is_default: true })
                    toast.success('Default voice updated')
                    reload()
                  } catch {
                    toast.error('Could not update default voice')
                  }
                }}
                className="input-field block mt-1 w-full max-w-xs text-xs"
              >
                {voices.filter(v => v.is_active).map(v => (
                  <option key={v.id} value={v.code}>{v.label} ({v.region})</option>
                ))}
              </select>
            </label>
          )}
          <button type="button" onClick={saveSettings} disabled={saving} className="btn-primary text-sm">
            {saving ? 'Saving…' : 'Save settings'}
          </button>
        </div>
      )}

      {tab === 'pricing' && (
        <div className="space-y-4">
          <p className="text-xs text-surface-500">Set INR prices and interview limits per plan tier.</p>
          {tiers.length === 0 && (
            <p className="text-sm text-amber-400">No tiers loaded — run seed_interview_data on the server.</p>
          )}
          {tiers.map(tier => (
            <div key={tier.id} className="glass-card p-4 border border-surface-800">
              <div className="flex flex-wrap gap-3 items-end">
                <div>
                  <p className="text-xs text-surface-500">Plan</p>
                  <p className="text-white font-medium">{tier.name} ({tier.code})</p>
                </div>
                <label className="text-xs text-surface-400">
                  Price (₹)
                  <input
                    type="number"
                    value={tier.price_inr}
                    onChange={e => setTiers(ts => ts.map(t => t.id === tier.id ? { ...t, price_inr: e.target.value } : t))}
                    className="input-field block mt-1 w-28 text-xs"
                  />
                </label>
                <label className="text-xs text-surface-400">
                  Interviews/mo
                  <input
                    type="number"
                    value={tier.interviews_per_month}
                    onChange={e => setTiers(ts => ts.map(t => t.id === tier.id ? { ...t, interviews_per_month: Number(e.target.value) } : t))}
                    className="input-field block mt-1 w-20 text-xs"
                  />
                </label>
                <label className="text-xs text-surface-400 flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={tier.is_active}
                    onChange={e => setTiers(ts => ts.map(t => t.id === tier.id ? { ...t, is_active: e.target.checked } : t))}
                  />
                  Active
                </label>
                <button type="button" onClick={() => saveTier(tier)} className="btn-secondary text-xs">
                  Save
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'entitlements' && (
        <div className="space-y-4">
          <div className="glass-card p-4 border border-surface-800 flex gap-2 max-w-md">
            <input
              value={grantEmail}
              onChange={e => setGrantEmail(e.target.value)}
              placeholder="user@email.com"
              className="input-field flex-1 text-sm"
            />
            <button type="button" onClick={grantFree} className="btn-primary text-sm whitespace-nowrap">
              Grant free access
            </button>
          </div>
          <table className="fx-admin-table">
            <thead>
              <tr className="text-left text-surface-500 border-b border-surface-800">
                <th className="py-2 pr-4">Email</th>
                <th className="py-2 pr-4">Plan</th>
                <th className="py-2 pr-4">Remaining</th>
                <th className="py-2">Flags</th>
              </tr>
            </thead>
            <tbody>
              {entitlements.map(e => (
                <tr key={e.user_id} className="border-b border-surface-800/50 text-surface-300 text-xs">
                  <td className="py-2 pr-4">{e.email}</td>
                  <td className="py-2 pr-4">{e.plan || '—'}</td>
                  <td className="py-2 pr-4">{e.interviews_remaining}</td>
                  <td className="py-2">
                    {e.is_admin_granted_free && <span className="text-emerald-400 mr-2">admin-free</span>}
                    {e.is_complimentary && <span className="text-indigo-400">complimentary</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'voices' && (
        <div className="space-y-2">
          <p className="text-xs text-surface-500 mb-2">
            Browser voices — Indian, UK, US male/female. Set default accent for new interviews.
          </p>
          {voices.map(v => (
            <div key={v.id} className="glass-card p-3 border border-surface-800 text-xs flex flex-wrap gap-3 items-center">
              <span className="text-white font-medium">{v.label}</span>
              <span className="text-surface-500">{v.locale}</span>
              <span className="text-surface-500">{v.region} · {v.gender}</span>
              <span className="text-indigo-400 font-mono">{v.browser_voice_hint || 'auto'}</span>
              {v.is_default && <span className="text-emerald-400">default</span>}
              {!v.is_active && <span className="text-red-400">inactive</span>}
              <div className="ml-auto flex gap-2">
                {!v.is_default && (
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        await adminApi.updateInterviewVoice(v.id, { ...v, is_default: true })
                        toast.success(`${v.label} set as default`)
                        reload()
                      } catch {
                        toast.error('Could not set default voice')
                      }
                    }}
                    className="btn-secondary text-[10px] py-1 px-2"
                  >
                    Set default
                  </button>
                )}
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      await adminApi.updateInterviewVoice(v.id, { ...v, is_active: !v.is_active })
                      toast.success(v.is_active ? 'Voice disabled' : 'Voice enabled')
                      reload()
                    } catch {
                      toast.error('Could not update voice')
                    }
                  }}
                  className="btn-secondary text-[10px] py-1 px-2"
                >
                  {v.is_active ? 'Disable' : 'Enable'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'campaigns' && (
        <div className="overflow-x-auto">
          <table className="fx-admin-table">
            <thead>
              <tr className="text-left text-surface-500 border-b border-surface-800">
                <th className="py-2 pr-4">User</th>
                <th className="py-2 pr-4">Title</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2">Score</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map(c => (
                <tr key={c.id} className="border-b border-surface-800/50 text-surface-300">
                  <td className="py-2 pr-4 text-xs">{c.user?.email}</td>
                  <td className="py-2 pr-4">{c.title}</td>
                  <td className="py-2 pr-4">{c.status}</td>
                  <td className="py-2">{c.overall_score?.toFixed?.(0) ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'questions' && (
        <div className="space-y-2 max-h-[60vh] overflow-y-auto">
          {questions.map(q => (
            <div key={q.id} className="glass-card p-3 border border-surface-800 text-xs">
              <span className="text-indigo-400 font-mono">{q.slug}</span>
              <span className="text-surface-600 mx-2">·</span>
              <span className="text-surface-500">{q.category} / diff {q.difficulty}</span>
              <p className="text-surface-300 mt-1">{q.question_text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
