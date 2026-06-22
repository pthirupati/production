import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { interviewsApi } from '../../api/interviews'
import { usePageTitle } from '../../hooks/usePageTitle'
import { PageHeader } from '../../components/design'
import { ChevronLeft, Users, Send, Loader2, Copy, Trash2, Plus } from 'lucide-react'
import toast from 'react-hot-toast'

const REC_STYLE = {
  strong_hire: 'text-emerald-300', hire: 'text-green-300',
  maybe: 'text-amber-300', no_hire: 'text-red-300', '': 'text-surface-500',
}

function scoreColor(s) {
  return s >= 75 ? 'text-emerald-400' : s >= 55 ? 'text-amber-400' : 'text-red-400'
}

export default function RecruiterCompare() {
  usePageTitle('Compare Candidates', 'Rank and compare interview candidates.')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [denied, setDenied] = useState(false)
  const [invites, setInvites] = useState([])
  const [templates, setTemplates] = useState([])
  const [form, setForm] = useState({ candidate_email: '', role_title: '', template: '', mode: 'live', message: '' })
  const [creating, setCreating] = useState(false)

  const loadInvites = () => {
    interviewsApi.listInvitations().then(d => setInvites(d.invitations || [])).catch(() => {})
  }

  useEffect(() => {
    interviewsApi.compareCandidates()
      .then(d => setData(d))
      .catch(e => { if (e.response?.status === 403) setDenied(true) })
      .finally(() => setLoading(false))
    loadInvites()
    interviewsApi.listTemplates().then(d => setTemplates(d.templates || [])).catch(() => {})
  }, [])

  const createInvite = async (e) => {
    e.preventDefault()
    setCreating(true)
    try {
      const payload = { ...form, send_email: !!form.candidate_email }
      if (!payload.template) delete payload.template
      const inv = await interviewsApi.createInvitation(payload)
      toast.success(form.candidate_email ? 'Invitation sent' : 'Invite link created')
      setForm({ candidate_email: '', role_title: '', template: '', mode: 'live', message: '' })
      setInvites(prev => [inv, ...prev])
      // First invite unlocks the comparison view.
      if (denied) { setDenied(false); setLoading(true); interviewsApi.compareCandidates().then(setData).finally(() => setLoading(false)) }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not create invitation')
    } finally {
      setCreating(false)
    }
  }

  const revoke = async (id) => {
    try {
      await interviewsApi.revokeInvitation(id)
      setInvites(prev => prev.map(i => i.id === id ? { ...i, status: 'revoked' } : i))
      toast.success('Invitation revoked')
    } catch {
      toast.error('Could not revoke')
    }
  }

  const copyLink = (url) => {
    navigator.clipboard?.writeText(url).then(() => toast.success('Link copied')).catch(() => {})
  }

  const dims = data?.dimensions || []

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-fade-in">
      <Link to="/interviews" className="text-xs text-surface-500 hover:text-white inline-flex items-center gap-1">
        <ChevronLeft size={14} /> Back to interviews
      </Link>
      <PageHeader
        eyebrow="Recruiter tools"
        title="Invite & compare candidates"
        subtitle="Send a shareable interview link, then rank candidates side by side once they complete."
      />

      {/* Invite builder */}
      <form onSubmit={createInvite} className="glass-card p-5 border border-surface-800 space-y-3">
        <p className="text-sm font-semibold text-white flex items-center gap-2"><Plus size={15} /> New invitation</p>
        <div className="grid sm:grid-cols-2 gap-3">
          <input
            type="email"
            placeholder="Candidate email (optional — leave blank for a link only)"
            value={form.candidate_email}
            onChange={e => setForm(f => ({ ...f, candidate_email: e.target.value }))}
            className="input-field text-sm"
          />
          <input
            type="text"
            placeholder="Role title (e.g. Senior SRE)"
            value={form.role_title}
            onChange={e => setForm(f => ({ ...f, role_title: e.target.value }))}
            className="input-field text-sm"
          />
          <select
            value={form.template}
            onChange={e => setForm(f => ({ ...f, template: e.target.value }))}
            className="input-field text-sm"
          >
            <option value="">No template (use candidate profile)</option>
            {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <select
            value={form.mode}
            onChange={e => setForm(f => ({ ...f, mode: e.target.value }))}
            className="input-field text-sm"
          >
            <option value="live">Live interview</option>
            <option value="async_video">One-way video</option>
          </select>
        </div>
        <textarea
          placeholder="Message to the candidate (optional)"
          value={form.message}
          onChange={e => setForm(f => ({ ...f, message: e.target.value }))}
          rows={2}
          className="input-field text-sm w-full"
        />
        <button type="submit" disabled={creating} className="btn-primary text-sm inline-flex items-center gap-2 disabled:opacity-50">
          {creating ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          {form.candidate_email ? 'Send invitation' : 'Create link'}
        </button>
      </form>

      {/* Sent invitations */}
      {invites.length > 0 && (
        <div className="glass-card p-4 border border-surface-800">
          <p className="text-sm font-semibold text-white mb-3">Your invitations</p>
          <div className="space-y-2">
            {invites.map(inv => (
              <div key={inv.id} className="flex items-center justify-between gap-3 p-2.5 rounded-lg bg-surface-800/40">
                <div className="min-w-0">
                  <p className="text-sm text-white truncate">{inv.candidate_email || inv.role_title || 'Shareable link'}</p>
                  <p className="text-[11px] text-surface-500">{inv.role_title} · {inv.mode === 'async_video' ? 'one-way' : 'live'} · {inv.status}</p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button type="button" onClick={() => copyLink(inv.invite_url)} title="Copy link" className="p-1.5 rounded-lg text-surface-400 hover:text-white hover:bg-surface-700">
                    <Copy size={14} />
                  </button>
                  {inv.status !== 'revoked' && (
                    <button type="button" onClick={() => revoke(inv.id)} title="Revoke" className="p-1.5 rounded-lg text-surface-500 hover:text-red-400 hover:bg-surface-700">
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Comparison table */}
      <div className="glass-card p-4 border border-surface-800">
        <p className="text-sm font-semibold text-white mb-3 flex items-center gap-2"><Users size={15} /> Candidate comparison</p>
        {loading ? (
          <p className="text-surface-500 text-sm">Loading…</p>
        ) : denied ? (
          <p className="text-surface-500 text-sm">Send an invitation above to unlock candidate comparison.</p>
        ) : !data?.candidates?.length ? (
          <p className="text-surface-500 text-sm">No completed candidates yet. Rankings appear once invitees finish.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-surface-500 border-b border-surface-800">
                  <th className="text-left py-2 pr-3">#</th>
                  <th className="text-left py-2 pr-3">Candidate</th>
                  <th className="text-right py-2 pr-3">Overall</th>
                  <th className="text-left py-2 pr-3">Verdict</th>
                  {dims.map(d => <th key={d.key} className="text-right py-2 pr-3 hidden md:table-cell">{d.label}</th>)}
                </tr>
              </thead>
              <tbody>
                {data.candidates.map(c => (
                  <tr key={c.campaign_id} className="border-b border-surface-800/50 hover:bg-surface-800/40">
                    <td className="py-2 pr-3 text-surface-400">{c.rank}</td>
                    <td className="py-2 pr-3">
                      <p className="text-white">{c.candidate.name}</p>
                      <p className="text-[10px] text-surface-500">{c.technology || c.template || c.experience_level}</p>
                    </td>
                    <td className={`py-2 pr-3 text-right font-bold ${scoreColor(c.overall_score)}`}>{Math.round(c.overall_score)}</td>
                    <td className={`py-2 pr-3 capitalize ${REC_STYLE[c.recommendation] || 'text-surface-500'}`}>
                      {(c.recommendation || '—').replace('_', ' ')}
                    </td>
                    {dims.map(d => (
                      <td key={d.key} className="py-2 pr-3 text-right text-surface-300 hidden md:table-cell">
                        {Math.round(c.dimensions?.[d.key] || 0)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
