import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { orgApi } from '../api/org'
import { Users, Building2, Mail, Shield, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'

export default function Team() {
  const [orgs, setOrgs] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviting, setInviting] = useState(false)

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
    } catch {
      toast.error('Could not load team details')
    }
  }

  const handleInvite = async (e) => {
    e.preventDefault()
    if (!selected || !inviteEmail.trim()) return
    setInviting(true)
    try {
      await orgApi.inviteMember(selected.slug, inviteEmail.trim())
      toast.success('Member added')
      setInviteEmail('')
      loadOrg(selected.slug)
    } catch (err) {
      const data = err.response?.data
      toast.error(data?.error || 'Invite failed')
    } finally {
      setInviting(false)
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
          You are not part of an organization yet. Ask your admin to invite you after you register.
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
        <p className="text-surface-400 mt-1">Organization access and seat management</p>
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
            <form onSubmit={handleInvite} className="space-y-3 border-t border-surface-800 pt-4">
              <p className="text-sm text-surface-400 flex items-center gap-2">
                <AlertCircle size={14} /> User must already have a FixitLab account before you invite them.
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
                  {inviting ? 'Adding…' : 'Add member'}
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  )
}
