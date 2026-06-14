import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { Building2, Plus, Users, Loader2, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'

export default function AdminTeams() {
  const [orgs, setOrgs] = useState([])
  const [technologies, setTechnologies] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', owner_id: '', seat_limit: 10, technology_ids: [], billing_email: '' })
  const [inviteEmail, setInviteEmail] = useState({})
  const [creating, setCreating] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [orgData, userData] = await Promise.all([
        adminApi.getOrganizations(),
        adminApi.getUsers({ page_size: 100 }),
      ])
      setOrgs(orgData.organizations || [])
      setTechnologies(orgData.technologies || [])
      setUsers(userData.results || userData.users || userData || [])
    } catch {
      toast.error('Failed to load teams')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    if (!form.name || !form.owner_id) {
      toast.error('Name and owner are required')
      return
    }
    setCreating(true)
    try {
      await adminApi.createOrganization(form)
      toast.success('Team created')
      setShowForm(false)
      setForm({ name: '', owner_id: '', seat_limit: 10, technology_ids: [], billing_email: '' })
      load()
    } catch (err) {
      toast.error(err.response?.data?.error || 'Create failed')
    } finally {
      setCreating(false)
    }
  }

  const handleInvite = async (orgId) => {
    const email = inviteEmail[orgId]
    if (!email) return
    try {
      await adminApi.addOrganizationMember(orgId, { email })
      toast.success('Member added')
      setInviteEmail(i => ({ ...i, [orgId]: '' }))
      load()
    } catch (err) {
      toast.error(err.response?.data?.error || 'Invite failed')
    }
  }

  const toggleTech = (id) => {
    setForm(f => ({
      ...f,
      technology_ids: f.technology_ids.includes(id)
        ? f.technology_ids.filter(x => x !== id)
        : [...f.technology_ids, id],
    }))
  }

  if (loading) {
    return <div className="flex justify-center py-20"><Loader2 className="animate-spin text-accent-cyan" size={32} /></div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Building2 size={24} className="text-accent-purple" /> Teams & Enterprise
          </h1>
          <p className="text-surface-400 text-sm mt-1">Shared technology access for organizations</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-2 text-sm">
          <Plus size={16} /> New Team
        </button>
      </div>

      {showForm && (
        <div className="glass-card p-6 space-y-4">
          <h2 className="font-semibold text-white">Create Organization</h2>
          <div className="grid md:grid-cols-2 gap-4">
            <input className="input-field" placeholder="Company name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            <select className="input-field" value={form.owner_id} onChange={e => setForm(f => ({ ...f, owner_id: e.target.value }))}>
              <option value="">Select owner...</option>
              {users.map(u => <option key={u.id} value={u.id}>{u.username} ({u.email})</option>)}
            </select>
            <input type="number" className="input-field" placeholder="Seat limit" value={form.seat_limit} onChange={e => setForm(f => ({ ...f, seat_limit: Number(e.target.value) }))} />
            <input className="input-field" placeholder="Billing email (optional)" value={form.billing_email} onChange={e => setForm(f => ({ ...f, billing_email: e.target.value }))} />
          </div>
          <div>
            <p className="text-xs text-surface-400 mb-2">Grant technology access</p>
            <div className="flex flex-wrap gap-2">
              {technologies.map(t => (
                <button key={t.id} type="button" onClick={() => toggleTech(t.id)}
                  className={`px-3 py-1 rounded-full text-xs border ${form.technology_ids.includes(t.id) ? 'border-accent-cyan text-accent-cyan bg-accent-cyan/10' : 'border-surface-700 text-surface-400'}`}>
                  {t.name}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
            <button onClick={handleCreate} disabled={creating} className="btn-primary">{creating ? 'Creating...' : 'Create'}</button>
          </div>
        </div>
      )}

      <div className="space-y-4">
        {orgs.map(org => (
          <div key={org.id} className="glass-card p-5">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="font-bold text-white">{org.name}</h3>
                <p className="text-xs text-surface-500">Owner: {org.owner} · {org.member_count}/{org.seat_limit} seats</p>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded-full ${org.is_active ? 'bg-accent-green/10 text-accent-green' : 'bg-surface-700 text-surface-400'}`}>
                {org.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
            {org.technologies?.length > 0 && (
              <p className="text-sm text-surface-400 mb-3">Access: {org.technologies.join(', ')}</p>
            )}
            <div className="flex gap-2">
              <input
                className="input-field flex-1 text-sm py-2"
                placeholder="Add member by email"
                value={inviteEmail[org.id] || ''}
                onChange={e => setInviteEmail(i => ({ ...i, [org.id]: e.target.value }))}
              />
              <button onClick={() => handleInvite(org.id)} className="btn-secondary text-xs flex items-center gap-1">
                <Users size={14} /> Add
              </button>
            </div>
          </div>
        ))}
        {orgs.length === 0 && (
          <p className="text-center text-surface-500 py-12">No teams yet. Create one for enterprise customers.</p>
        )}
      </div>
    </div>
  )
}
