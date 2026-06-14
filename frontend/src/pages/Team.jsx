import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { orgApi } from '../api/org'
import { subscriptionApi } from '../api/subscriptions'
import { Users, Building2, Mail, Shield, AlertCircle, BarChart3, CreditCard } from 'lucide-react'
import toast from 'react-hot-toast'

export default function Team() {
  const [orgs, setOrgs] = useState([])
  const [selected, setSelected] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviting, setInviting] = useState(false)
  const [checkoutSeats, setCheckoutSeats] = useState(10)
  const [checkingOut, setCheckingOut] = useState(false)

  useEffect(() => {
    orgApi.list()
      .then(d => setOrgs(d.organizations || []))
      .catch(() => toast.error('Failed to load teams'))
      .finally(() => setLoading(false))
  }, [])

  const loadOrg = async (slug) => {
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

  const handleInvite = async (e) => {
    e.preventDefault()
    if (!selected || !inviteEmail.trim()) return
    setInviting(true)
    try {
      const res = await orgApi.inviteMember(selected.slug, inviteEmail.trim())
      toast.success(res.message || 'Member added')
      setInviteEmail('')
      loadOrg(selected.slug)
    } catch (err) {
      const data = err.response?.data
      toast.error(data?.error || 'Invite failed')
    } finally {
      setInviting(false)
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

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Users size={24} className="text-accent-cyan" /> My Team
        </h1>
        <p className="text-surface-400 mt-1">Organization access, analytics, and seat billing</p>
      </div>

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
        <div className="glass-card p-6 space-y-6">
          <div>
            <h2 className="text-lg font-bold">{selected.name}</h2>
            <p className="text-sm text-surface-400">{selected.technologies?.length || 0} technology grants active</p>
          </div>

          {analytics && (
            <div className="border border-surface-800 rounded-xl p-4 space-y-3">
              <h3 className="font-medium flex items-center gap-2 text-white">
                <BarChart3 size={16} className="text-accent-cyan" /> Team analytics
              </h3>
              <div className="grid grid-cols-3 gap-3 text-center text-sm">
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
              </div>
              <ul className="text-xs space-y-1 max-h-40 overflow-y-auto">
                {analytics.members?.map(m => (
                  <li key={m.email} className="flex justify-between border-b border-surface-800/50 py-1.5">
                    <span className="text-surface-300">{m.email}</span>
                    <span className="text-surface-500">{m.scenarios_completed} done · {m.labs_started} labs</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {selected.technologies?.length > 0 && (
            <ul className="text-sm text-surface-300 space-y-1">
              {selected.technologies.map(t => (
                <li key={t.id} className="flex items-center gap-2">
                  <Shield size={14} className="text-accent-green" /> {t.name}
                </li>
              ))}
            </ul>
          )}

          <div>
            <h3 className="font-medium mb-2">Members</h3>
            <ul className="text-sm space-y-2">
              {selected.members?.map(m => (
                <li key={m.id} className="flex justify-between border-b border-surface-800 py-2">
                  <span>{m.email}</span>
                  <span className="text-surface-500 capitalize">{m.role}</span>
                </li>
              ))}
            </ul>
          </div>

          {['owner', 'admin'].includes(selected.role) && (
            <>
              <form onSubmit={handleInvite} className="space-y-3 border-t border-surface-800 pt-4">
                <p className="text-sm text-surface-400 flex items-center gap-2">
                  <AlertCircle size={14} /> Invite by email — existing users join immediately; new users receive a pending invite until they register.
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
                <div className="flex gap-2 items-center">
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
      )}
    </div>
  )
}
