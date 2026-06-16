import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { orgApi } from '../api/org'
import { subscriptionApi } from '../api/subscriptions'
import {
  Users, Building2, Mail, Shield, AlertCircle, BarChart3, CreditCard,
  Clock, Trash2, UserMinus, ChevronRight, X, BookOpen, FlaskConical
} from 'lucide-react'
import toast from 'react-hot-toast'
import StickyPageToolbar from '../components/StickyPageToolbar'

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function Team() {
  const [orgs, setOrgs] = useState([])
  const [selected, setSelected] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [memberDetail, setMemberDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviting, setInviting] = useState(false)
  const [checkoutSeats, setCheckoutSeats] = useState(10)
  const [checkingOut, setCheckingOut] = useState(false)
  const [removingId, setRemovingId] = useState(null)

  useEffect(() => {
    orgApi.list()
      .then(d => setOrgs(d.organizations || []))
      .catch(() => toast.error('Failed to load teams'))
      .finally(() => setLoading(false))
  }, [])

  const loadOrg = async (slug) => {
    setMemberDetail(null)
    try {
      const data = await orgApi.get(slug)
      setSelected(data)
      setCheckoutSeats(data.seat_limit || 10)
      if (['owner', 'admin'].includes(data.role)) {
        const stats = await orgApi.getAnalytics(slug).catch(() => null)
        setAnalytics(stats)
      } else {
        setAnalytics(null)
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
    if (!selected || !window.confirm(`Remove ${email} from the team?`)) return
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
      <div className="max-w-lg mx-auto text-center py-16">
        <Building2 size={48} className="mx-auto text-surface-600 mb-4" />
        <h1 className="text-xl font-bold text-white mb-2">No team membership</h1>
        <p className="text-surface-400 text-sm mb-6">
          You are not part of an organization yet. Ask your admin to invite you — they can invite your email before you register.
        </p>
        <Link to="/technologies" className="btn-primary">Browse technologies</Link>
      </div>
    )
  }

  const canManage = selected && ['owner', 'admin'].includes(selected.role)
  const pendingInvites = selected?.pending_invites || analytics?.pending_invites || []

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <StickyPageToolbar>
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Users size={24} className="text-accent-cyan shrink-0" /> My Team
        </h1>
        <p className="text-surface-400 mt-1 text-sm">Organization access, member analytics, invites, and seat billing</p>
      </div>
      </StickyPageToolbar>

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
  )
}
