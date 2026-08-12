import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { orgApi } from '../api/org'
import { subscriptionApi } from '../api/subscriptions'
import api from '../api/client'
import {
  Building2, Mail, Shield, AlertCircle, BarChart3, CreditCard,
  Clock, Trash2, UserMinus, ChevronRight, X, BookOpen, FlaskConical, Webhook, Paintbrush,
  Plus, Sparkles
} from 'lucide-react'
import toast from 'react-hot-toast'
import { useConfirm } from '../hooks/useConfirm'
import { PageHeader } from '../components/design'

// NOTE: api/org.js is owned by another task; once it gains a `create(payload)`
// method this can switch to `orgApi.create`. Until then we call the endpoint
// directly through the shared axios client so the create-team flow works.
async function createTeam(payload) {
  const { data } = await api.post('/org/create/', payload)
  return data
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function Team() {
  const { confirm, ConfirmPortal } = useConfirm()
  const [orgs, setOrgs] = useState([])
  const [selected, setSelected] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [analyticsFailed, setAnalyticsFailed] = useState(false)
  const [memberDetail, setMemberDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviting, setInviting] = useState(false)
  const [checkoutSeats, setCheckoutSeats] = useState(10)
  const [checkingOut, setCheckingOut] = useState(false)
  const [removingId, setRemovingId] = useState(null)
  const [webhookUrl, setWebhookUrl] = useState('')
  const [webhookSecret, setWebhookSecret] = useState('')
  const [logoUrl, setLogoUrl] = useState('')
  const [primaryColor, setPrimaryColor] = useState('')
  const [savingSettings, setSavingSettings] = useState(false)
  // Team creation
  const [canCreate, setCanCreate] = useState(false)
  const [defaultSeats, setDefaultSeats] = useState(10)
  const [showCreate, setShowCreate] = useState(false)
  const [newTeamName, setNewTeamName] = useState('')
  const [creating, setCreating] = useState(false)

  const refreshOrgs = (selectSlug) => {
    return orgApi.list()
      .then(d => {
        setOrgs(d.organizations || [])
        setCanCreate(!!d.can_create_team)
        setDefaultSeats(d.default_seat_limit || 10)
        if (selectSlug) loadOrg(selectSlug)
      })
      .catch(() => toast.error('Failed to load teams'))
  }

  useEffect(() => {
    refreshOrgs().finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleCreateTeam = async (e) => {
    e.preventDefault()
    if (!newTeamName.trim()) return
    setCreating(true)
    try {
      const org = await createTeam({ name: newTeamName.trim() })
      toast.success(`Team "${org.name}" created`)
      setNewTeamName('')
      setShowCreate(false)
      await refreshOrgs(org.slug)
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not create team')
    } finally {
      setCreating(false)
    }
  }

  const loadOrg = async (slug) => {
    setMemberDetail(null)
    try {
      const data = await orgApi.get(slug)
      setSelected(data)
      setCheckoutSeats(data.seat_limit || 10)
      setWebhookUrl(data.webhook_url || '')
      setWebhookSecret(data.webhook_secret || '')
      setLogoUrl(data.logo_url || '')
      setPrimaryColor(data.primary_color || '')
      if (['owner', 'admin'].includes(data.role)) {
        // The analytics block renders under `analytics &&`, so a swallowed
        // failure made the whole team overview silently vanish — an owner sees
        // no numbers and no reason why. It also backstops pending_invites
        // below, so a silent failure can under-report outstanding invites.
        try {
          setAnalytics(await orgApi.getAnalytics(slug))
          setAnalyticsFailed(false)
        } catch {
          setAnalytics(null)
          setAnalyticsFailed(true)
        }
      } else {
        setAnalytics(null)
        setAnalyticsFailed(false)
      }
    } catch {
      toast.error('Could not load team details')
    }
  }

  const openMember = async (userId) => {
    if (!selected || !['owner', 'admin'].includes(selected.role)) return
    try {
      const detail = await orgApi.getMember(selected.slug, userId)
      setMemberDetail(detail)
    } catch {
      toast.error('Could not load member details')
    }
  }

  const handleInvite = async (e) => {
    e.preventDefault()
    if (!selected || !inviteEmail.trim()) return
    setInviting(true)
    try {
      const res = await orgApi.inviteMember(selected.slug, inviteEmail.trim())
      toast.success(res.message || 'Invite sent')
      setInviteEmail('')
      loadOrg(selected.slug)
    } catch (err) {
      toast.error(err.response?.data?.error || 'Invite failed')
    } finally {
      setInviting(false)
    }
  }

  const handleRemoveMember = async (userId, email) => {
    if (!selected || !await confirm({ message: `Remove ${email} from the team?`, danger: true, confirmLabel: 'Remove' })) return
    setRemovingId(userId)
    try {
      await orgApi.removeMember(selected.slug, userId)
      toast.success('Member removed')
      setMemberDetail(null)
      loadOrg(selected.slug)
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not remove member')
    } finally {
      setRemovingId(null)
    }
  }

  const handleLeaveTeam = async () => {
    if (!selected) return
    if (!await confirm({
      message: `Leave "${selected.name}"? You'll lose access to shared technologies and will need to be re-invited to rejoin.`,
      danger: true,
      confirmLabel: 'Leave team',
    })) return
    try {
      await orgApi.leaveTeam(selected.slug)
      toast.success(`You have left ${selected.name}`)
      setSelected(null)
      setAnalytics(null)
      setMemberDetail(null)
      await refreshOrgs()
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not leave team')
    }
  }

  const handleDeleteTeam = async () => {
    if (!selected) return
    if (!await confirm({
      message: `Delete "${selected.name}"? This permanently removes the team, all memberships and pending invites. This cannot be undone.`,
      danger: true,
      confirmLabel: 'Delete team',
    })) return
    try {
      await orgApi.deleteTeam(selected.slug)
      toast.success(`Team "${selected.name}" deleted`)
      setSelected(null)
      setAnalytics(null)
      setMemberDetail(null)
      await refreshOrgs()
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not delete team')
    }
  }

  const handleSaveSettings = async (e) => {
    e.preventDefault()
    if (!selected) return
    setSavingSettings(true)
    try {
      await orgApi.updateSettings(selected.slug, {
        webhook_url: webhookUrl,
        webhook_secret: webhookSecret,
        logo_url: logoUrl,
        primary_color: primaryColor,
      })
      toast.success('Settings saved')
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to save settings')
    } finally {
      setSavingSettings(false)
    }
  }

  const handleCancelInvite = async (inviteId, email) => {
    if (!selected) return
    try {
      await orgApi.cancelInvite(selected.slug, inviteId)
      toast.success(`Cancelled invite for ${email}`)
      loadOrg(selected.slug)
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not cancel invite')
    }
  }

  const handleOrgCheckout = async () => {
    if (!selected) return
    setCheckingOut(true)
    try {
      const order = await subscriptionApi.createOrgCheckout(selected.slug, checkoutSeats)
      if (!order.order_id) {
        toast.error(order.error || 'Checkout unavailable')
        return
      }
      const params = new URLSearchParams({
        token: order.order_id,
        tech: selected.name,
        amount: String(order.amount),
        org_slug: selected.slug,
        order_id: order.order_id,
        razorpay_key: order.razorpay_key_id || '',
        currency: 'INR',
      })
      window.location.href = `/payment?${params.toString()}`
    } catch (err) {
      toast.error(err.response?.data?.error || 'Org checkout failed')
    } finally {
      setCheckingOut(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!orgs.length) {
    return (
      <div className="max-w-lg mx-auto py-16">
        {canCreate ? (
          <div className="glass-card p-8 text-center">
            <div className="w-14 h-14 rounded-2xl bg-accent-cyan/10 flex items-center justify-center mx-auto mb-4">
              <Sparkles size={26} className="text-accent-cyan" />
            </div>
            <h1 className="text-xl font-bold text-white mb-2">Create your team</h1>
            <p className="text-surface-400 text-sm mb-6">
              Your plan includes team seats. Create a team to invite colleagues, share technology
              access, and track their progress. You'll be the team owner.
            </p>
            <form onSubmit={handleCreateTeam} className="space-y-3 text-left">
              <label className="block text-xs font-medium text-surface-400">Team name</label>
              <input
                type="text"
                className="input-field"
                placeholder="Acme Engineering"
                value={newTeamName}
                onChange={e => setNewTeamName(e.target.value)}
                maxLength={200}
                required
                autoFocus
              />
              <p className="text-[11px] text-surface-500">
                Up to {defaultSeats} seats included. You can purchase more seats later.
              </p>
              <button type="submit" disabled={creating} className="btn-primary w-full">
                {creating ? 'Creating…' : 'Create team'}
              </button>
            </form>
          </div>
        ) : (
          <div className="text-center">
            <Building2 size={48} className="mx-auto text-surface-600 mb-4" />
            <h1 className="text-xl font-bold text-white mb-2">No team yet</h1>
            <p className="text-surface-400 text-sm mb-6">
              Creating a team requires a team or enterprise plan. Upgrade your plan or contact sales
              to get seats for your organization. If a teammate already has a team, ask them to
              invite your email — they can invite you before you even register.
            </p>
            <div className="flex items-center justify-center gap-3">
              <Link to="/pricing" className="btn-primary">View plans</Link>
              <Link to="/contact-sales" className="btn-secondary">Contact sales</Link>
            </div>
          </div>
        )}
      </div>
    )
  }

  const canManage = selected && ['owner', 'admin'].includes(selected.role)
  const pendingInvites = selected?.pending_invites || analytics?.pending_invites || []

  return (
    <>
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <PageHeader
          eyebrow="Collaboration"
          title="My Team"
          subtitle="Organization access, member analytics, invites, and seat billing"
        />
        {canCreate && (
          <button
            type="button"
            onClick={() => setShowCreate(v => !v)}
            className="btn-secondary shrink-0 flex items-center gap-2 mt-1"
          >
            <Plus size={16} /> {showCreate ? 'Cancel' : 'Create team'}
          </button>
        )}
      </div>

      {canCreate && showCreate && (
        <form onSubmit={handleCreateTeam} className="glass-card p-5 flex flex-col sm:flex-row gap-3 sm:items-end">
          <div className="flex-1">
            <label className="block text-xs font-medium text-surface-400 mb-1.5">New team name</label>
            <input
              type="text"
              className="input-field"
              placeholder="Acme Engineering"
              value={newTeamName}
              onChange={e => setNewTeamName(e.target.value)}
              maxLength={200}
              required
              autoFocus
            />
          </div>
          <button type="submit" disabled={creating} className="btn-primary shrink-0">
            {creating ? 'Creating…' : 'Create team'}
          </button>
        </form>
      )}

      <div className="grid sm:grid-cols-2 gap-4">
        {orgs.map(org => (
          <button
            key={org.id}
            type="button"
            onClick={() => loadOrg(org.slug)}
            className={`glass-card p-5 text-left transition-all ${selected?.slug === org.slug ? 'ring-2 ring-accent-cyan' : ''}`}
          >
            <h2 className="font-semibold text-white">{org.name}</h2>
            <p className="text-xs text-surface-500 mt-1 capitalize">Role: {org.role}</p>
            <p className="text-xs text-surface-400 mt-2">{org.member_count}/{org.seat_limit} seats</p>
          </button>
        ))}
      </div>

      {selected && (
        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 glass-card p-6 space-y-6">
            <div>
              <h2 className="text-lg font-bold">{selected.name}</h2>
              <p className="text-sm text-surface-400">{selected.technologies?.length || 0} technology grants active</p>
            </div>

            {analyticsFailed && (
              <div
                data-testid="team-analytics-error"
                className="border border-accent-red/25 bg-accent-red/[0.05] rounded-xl p-4"
              >
                <h3 className="font-medium flex items-center gap-2 text-white">
                  <BarChart3 size={16} className="text-accent-red/80" /> Team overview unavailable
                </h3>
                <p className="text-xs text-surface-500 mt-1">
                  Couldn't load team analytics. Member and invite counts below may be incomplete.
                </p>
                <button
                  onClick={() => loadOrg(selected.slug)}
                  className="btn-secondary text-xs px-3 py-1.5 mt-3"
                >
                  Retry
                </button>
              </div>
            )}

            {analytics && (
              <div className="border border-surface-800 rounded-xl p-4 space-y-3">
                <h3 className="font-medium flex items-center gap-2 text-white">
                  <BarChart3 size={16} className="text-accent-cyan" /> Team overview
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center text-sm">
                  <div className="bg-surface-900/50 rounded-lg p-3">
                    <p className="text-2xl font-bold text-white">{analytics.total_completions}</p>
                    <p className="text-surface-500 text-xs">Completions</p>
                  </div>
                  <div className="bg-surface-900/50 rounded-lg p-3">
                    <p className="text-2xl font-bold text-white">{analytics.total_labs}</p>
                    <p className="text-surface-500 text-xs">Labs started</p>
                  </div>
                  <div className="bg-surface-900/50 rounded-lg p-3">
                    <p className="text-2xl font-bold text-white">{analytics.member_count}</p>
                    <p className="text-surface-500 text-xs">Members</p>
                  </div>
                  <div className="bg-surface-900/50 rounded-lg p-3">
                    <p className="text-2xl font-bold text-white">{analytics.pending_invite_count || 0}</p>
                    <p className="text-surface-500 text-xs">Pending invites</p>
                  </div>
                </div>
              </div>
            )}

            {selected.technologies?.length > 0 && (
              <div>
                <h3 className="font-medium mb-2 text-sm text-surface-400">Shared technologies</h3>
                <ul className="text-sm text-surface-300 space-y-1">
                  {selected.technologies.map(t => (
                    <li key={t.id} className="flex items-center gap-2">
                      <Shield size={14} className="text-accent-green" /> {t.name}
                      {t.expires_at && (
                        <span className="text-xs text-surface-500">· until {formatDate(t.expires_at)}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div>
              <h3 className="font-medium mb-3">Members</h3>
              <ul className="text-sm space-y-1">
                {selected.members?.map(m => (
                  <li key={m.id} className="flex items-center gap-2 border-b border-surface-800 py-2.5 group">
                    <button
                      type="button"
                      onClick={() => canManage && openMember(m.id)}
                      className={`flex-1 flex items-center justify-between text-left ${canManage ? 'hover:text-accent-cyan' : ''}`}
                    >
                      <div>
                        <span className="text-white">{m.email}</span>
                        <span className="text-surface-500 capitalize ml-2 text-xs">{m.role}</span>
                        {m.joined_at && (
                          <span className="text-surface-600 text-xs ml-2">joined {formatDate(m.joined_at)}</span>
                        )}
                      </div>
                      {canManage && (
                        <span className="text-xs text-surface-500">
                          {m.scenarios_completed ?? 0} done · {m.labs_started ?? 0} labs
                          <ChevronRight size={12} className="inline ml-1 opacity-0 group-hover:opacity-100" />
                        </span>
                      )}
                    </button>
                    {canManage && m.role !== 'owner' && (
                      <button
                        type="button"
                        title="Remove member"
                        disabled={removingId === m.id}
                        onClick={() => handleRemoveMember(m.id, m.email)}
                        className="p-1.5 text-surface-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <UserMinus size={15} />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </div>

            {canManage && pendingInvites.length > 0 && (
              <div>
                <h3 className="font-medium mb-2 flex items-center gap-2">
                  <Clock size={14} className="text-accent-amber" /> Pending invites
                </h3>
                <ul className="text-sm space-y-2">
                  {pendingInvites.map(inv => (
                    <li key={inv.id} className="flex items-center justify-between border border-surface-800 rounded-lg px-3 py-2">
                      <div>
                        <span className="text-surface-300">{inv.email}</span>
                        <span className="text-surface-500 capitalize ml-2 text-xs">{inv.role}</span>
                        <p className="text-xs text-surface-600 mt-0.5">
                          Invited {formatDate(inv.created_at)} · expires {formatDate(inv.expires_at)}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleCancelInvite(inv.id, inv.email)}
                        className="text-surface-500 hover:text-red-400 p-1"
                        title="Cancel invite"
                      >
                        <X size={16} />
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {canManage && (
              <>
                <form onSubmit={handleInvite} className="space-y-3 border-t border-surface-800 pt-4">
                  <p className="text-sm text-surface-400 flex items-center gap-2">
                    <AlertCircle size={14} /> Invite by email — existing users join immediately; new users receive an email invite until they register.
                  </p>
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
                      <input
                        type="email"
                        className="input-field pl-10"
                        placeholder="colleague@company.com"
                        value={inviteEmail}
                        onChange={e => setInviteEmail(e.target.value)}
                        required
                      />
                    </div>
                    <button type="submit" disabled={inviting} className="btn-primary shrink-0">
                      {inviting ? 'Sending…' : 'Invite'}
                    </button>
                  </div>
                </form>

                {selected.role === 'owner' && (
                  <form onSubmit={handleSaveSettings} className="border-t border-surface-800 pt-4 space-y-3">
                    <h3 className="font-medium flex items-center gap-2">
                      <Webhook size={16} className="text-accent-cyan" /> Webhook &amp; Branding
                    </h3>
                    <p className="text-xs text-surface-500">Receive org events (member joined, lab completed) at your endpoint.</p>
                    <input
                      type="url"
                      className="input-field text-sm"
                      placeholder="https://your-server.com/webhook"
                      value={webhookUrl}
                      onChange={e => setWebhookUrl(e.target.value)}
                    />
                    <input
                      type="text"
                      className="input-field text-sm"
                      placeholder="Webhook secret (HMAC SHA-256)"
                      value={webhookSecret}
                      onChange={e => setWebhookSecret(e.target.value)}
                    />
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <Paintbrush size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
                        <input
                          type="url"
                          className="input-field pl-9 text-sm"
                          placeholder="Logo URL"
                          value={logoUrl}
                          onChange={e => setLogoUrl(e.target.value)}
                        />
                      </div>
                      <input
                        type="text"
                        className="input-field w-28 text-sm"
                        placeholder="#6366f1"
                        value={primaryColor}
                        onChange={e => setPrimaryColor(e.target.value)}
                      />
                    </div>
                    <button type="submit" disabled={savingSettings} className="btn-secondary text-sm">
                      {savingSettings ? 'Saving…' : 'Save settings'}
                    </button>
                  </form>
                )}

                <div className="border-t border-surface-800 pt-4 space-y-3">
                  <h3 className="font-medium flex items-center gap-2">
                    <CreditCard size={16} className="text-accent-amber" /> Purchase seats
                  </h3>
                  <div className="flex gap-2 items-center flex-wrap">
                    <input
                      type="number"
                      min={selected.member_count || 1}
                      className="input-field w-24"
                      value={checkoutSeats}
                      onChange={e => setCheckoutSeats(parseInt(e.target.value, 10) || selected.seat_limit)}
                    />
                    <span className="text-sm text-surface-400">seats (min {selected.member_count})</span>
                    <button type="button" onClick={handleOrgCheckout} disabled={checkingOut} className="btn-primary ml-auto">
                      {checkingOut ? 'Creating order…' : 'Checkout via Razorpay'}
                    </button>
                  </div>
                </div>
              </>
            )}

            <div className="border-t border-surface-800 pt-4 space-y-3">
              <h3 className="font-medium flex items-center gap-2 text-red-400">
                <AlertCircle size={16} /> Danger zone
              </h3>
              {selected.role === 'owner' ? (
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <p className="text-xs text-surface-500 flex-1 min-w-[12rem]">
                    Permanently delete this team, its memberships and pending invites. This cannot be undone.
                  </p>
                  <button
                    type="button"
                    onClick={handleDeleteTeam}
                    className="flex items-center gap-2 text-sm text-red-400 hover:text-red-300 border border-red-500/30 rounded-lg px-3 py-2 shrink-0"
                  >
                    <Trash2 size={14} /> Delete team
                  </button>
                </div>
              ) : (
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <p className="text-xs text-surface-500 flex-1 min-w-[12rem]">
                    Leave this team. You'll lose access to shared technologies and need a new invite to rejoin.
                  </p>
                  <button
                    type="button"
                    onClick={handleLeaveTeam}
                    className="flex items-center gap-2 text-sm text-red-400 hover:text-red-300 border border-red-500/30 rounded-lg px-3 py-2 shrink-0"
                  >
                    <UserMinus size={14} /> Leave team
                  </button>
                </div>
              )}
            </div>
          </div>

          {memberDetail && (
            <div className="glass-card p-5 space-y-4 h-fit sticky top-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-bold text-white">{memberDetail.username || memberDetail.email}</h3>
                  <p className="text-xs text-surface-500">{memberDetail.email}</p>
                </div>
                <button type="button" onClick={() => setMemberDetail(null)} className="text-surface-500 hover:text-white">
                  <X size={16} />
                </button>
              </div>

              <div className="text-xs space-y-2 text-surface-400">
                <p><span className="text-surface-500">Role:</span> <span className="capitalize text-surface-300">{memberDetail.role}</span></p>
                <p><span className="text-surface-500">Joined:</span> {formatDate(memberDetail.joined_at)}</p>
                <p><span className="text-surface-500">Last active:</span> {formatDate(memberDetail.last_active)}</p>
              </div>

              <div className="grid grid-cols-3 gap-2 text-center text-xs">
                <div className="bg-surface-900/50 rounded-lg p-2">
                  <p className="text-lg font-bold text-white">{memberDetail.scenarios_completed}</p>
                  <p className="text-surface-500 flex items-center justify-center gap-1"><BookOpen size={10} /> Done</p>
                </div>
                <div className="bg-surface-900/50 rounded-lg p-2">
                  <p className="text-lg font-bold text-white">{memberDetail.total_attempts}</p>
                  <p className="text-surface-500">Attempts</p>
                </div>
                <div className="bg-surface-900/50 rounded-lg p-2">
                  <p className="text-lg font-bold text-white">{memberDetail.labs_started}</p>
                  <p className="text-surface-500 flex items-center justify-center gap-1"><FlaskConical size={10} /> Labs</p>
                </div>
              </div>

              {memberDetail.subscriptions?.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-surface-400 mb-2 uppercase tracking-wide">Subscriptions</h4>
                  <ul className="text-xs space-y-1.5">
                    {memberDetail.subscriptions.map((s, i) => (
                      <li key={i} className="flex justify-between text-surface-300">
                        <span>{s.technology}</span>
                        <span className="text-surface-500">{s.expires_at ? formatDate(s.expires_at) : 'Active'}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {memberDetail.role !== 'owner' && (
                <button
                  type="button"
                  disabled={removingId === memberDetail.id}
                  onClick={() => handleRemoveMember(memberDetail.id, memberDetail.email)}
                  className="w-full flex items-center justify-center gap-2 text-sm text-red-400 hover:text-red-300 border border-red-500/20 rounded-lg py-2"
                >
                  <Trash2 size={14} /> Remove from team
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
    <ConfirmPortal />
    </>
  )
}
