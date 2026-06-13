import { useState, useEffect, useMemo } from 'react'
import { adminApi } from '../../api/admin'
import { Search, UserPlus, Ban, Trash2, Shield, X, Save, Key, Eye, Phone, Mail, Activity, Download, CheckSquare, Square, MinusSquare, Users, ShieldOff, UserCheck, UserX, Crown, MapPin, AlertTriangle } from 'lucide-react'
import toast from 'react-hot-toast'
import { SkeletonTable } from '../../components/Skeleton'
import { ConfirmDialog } from '../../components/ConfirmModal'
import ConfirmModal from '../../components/ConfirmModal'
import { validators } from '../../utils/validators'
import JiraTicketLink from '../../components/JiraTicketLink'

export default function AdminUsers() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [showDetail, setShowDetail] = useState(null)
  const [showPasswordReset, setShowPasswordReset] = useState(null)
  const [newPassword, setNewPassword] = useState('')
  const [form, setForm] = useState({ email: '', password: '', is_staff: false, phone_number: '' })
  const [deleteConfirm, setDeleteConfirm] = useState(null)
  const [exporting, setExporting] = useState(false)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [bulkConfirm, setBulkConfirm] = useState(null)
  const [bulkProcessing, setBulkProcessing] = useState(false)

  useEffect(() => { loadData() }, [search])

  const loadData = async () => {
    setLoading(true)
    try {
      const data = await adminApi.getUsers(search ? { search } : {})
      setUsers(data)
    } catch { console.error } finally { setLoading(false) }
  }

  // ── Selection helpers ──
  const selectableUsers = useMemo(() => users.filter(u => !u.is_superuser), [users])
  const allSelected = selectableUsers.length > 0 && selectableUsers.every(u => selectedIds.has(u.id))
  const someSelected = selectableUsers.some(u => selectedIds.has(u.id))

  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(selectableUsers.map(u => u.id)))
    }
  }

  const clearSelection = () => setSelectedIds(new Set())

  // ── Bulk actions ──
  const bulkActions = [
    { action: 'delete', label: 'Delete Selected', icon: Trash2, danger: true, confirm: 'Permanently delete {n} user(s)? This cannot be undone.' },
    { action: 'activate', label: 'Activate', icon: UserCheck, confirm: 'Activate {n} user(s)?' },
    { action: 'deactivate', label: 'Deactivate', icon: UserX, confirm: 'Deactivate {n} user(s)?' },
    { action: 'make_staff', label: 'Grant Admin', icon: Shield, confirm: 'Grant admin role to {n} user(s)?' },
    { action: 'grant_free', label: 'Grant Free Access', icon: Crown, confirm: 'Grant complimentary free access to {n} user(s)?' },
    { action: 'revoke_free', label: 'Revoke Free Access', icon: ShieldOff, confirm: 'Revoke complimentary access from {n} user(s)?' },
  ]

  const handleBulkAction = async () => {
    if (!bulkConfirm) return
    setBulkProcessing(true)
    try {
      const res = await adminApi.bulkUserAction([...selectedIds], bulkConfirm.action)
      toast.success(res.message)
      clearSelection()
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.error || 'Bulk action failed')
    } finally {
      setBulkProcessing(false)
      setBulkConfirm(null)
    }
  }

  const handleCreate = async () => {
    // Validate form
    const emailV = validators.email(form.email)
    if (!emailV.valid) { toast.error(emailV.error); return }
    const passV = validators.password(form.password)
    if (!passV.valid) { toast.error(passV.error); return }
    if (form.phone_number) {
      const phoneV = validators.phone(form.phone_number)
      if (!phoneV.valid) { toast.error(phoneV.error); return }
    }
    try {
      await adminApi.createUser(form)
      toast.success('User created')
      setShowForm(false)
      setForm({ email: '', password: '', is_staff: false, phone_number: '' })
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.error || 'Create failed')
    }
  }

  const handleToggleActive = async (user) => {
    try {
      await adminApi.updateUser(user.id, { is_active: !user.is_active })
      toast.success(user.is_active ? 'User disabled' : 'User enabled')
      loadData()
    } catch {
      toast.error('Update failed')
    }
  }

  const handleToggleComplimentary = async (user) => {
    try {
      await adminApi.updateUser(user.id, { complimentary_access: !user.complimentary_access })
      toast.success(user.complimentary_access ? 'Free access revoked' : 'Free access granted')
      loadData()
    } catch {
      toast.error('Update failed')
    }
  }

  const handleToggleStaff = async (user) => {
    try {
      await adminApi.updateUser(user.id, { is_staff: !user.is_staff })
      toast.success(user.is_staff ? 'Admin removed' : 'Admin granted')
      loadData()
    } catch {
      toast.error('Update failed')
    }
  }

  const handleResetPassword = async () => {
    if (!newPassword || newPassword.length < 8) {
      toast.error('Password must be at least 8 characters')
      return
    }
    try {
      await adminApi.updateUser(showPasswordReset.id, { new_password: newPassword })
      toast.success('Password reset successfully')
      setShowPasswordReset(null)
      setNewPassword('')
    } catch (err) {
      toast.error(err.response?.data?.error || 'Reset failed')
    }
  }

  const handleViewDetail = async (userId) => {
    try {
      const data = await adminApi.getUserDetail(userId)
      setShowDetail(data)
    } catch {
      toast.error('Failed to load user details')
    }
  }

  const handleDelete = async (id) => {
    try {
      await adminApi.deleteUser(id)
      toast.success('User deleted')
      setDeleteConfirm(null)
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.error || 'Cannot delete')
    }
  }

  const handleExportCSV = async () => {
    setExporting(true)
    try {
      await adminApi.exportUsers()
      toast.success('Users exported')
    } catch {
      toast.error('Export failed')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Users</h1>
          <p className="text-surface-400 mt-1">Manage platform users ({users.length} total)</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleExportCSV} disabled={exporting}
            className="btn-secondary flex items-center gap-2 text-sm">
            <Download size={14} /> {exporting ? 'Exporting...' : 'Export CSV'}
          </button>
          <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-2">
            <UserPlus size={16} /> Add User
          </button>
        </div>
      </div>

      {/* Bulk Action Bar */}
      {selectedIds.size > 0 && (
        <div className="glass-card p-3 flex items-center justify-between animate-slide-up border border-accent-cyan/20 bg-accent-cyan/5">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-white">
              {selectedIds.size} user{selectedIds.size > 1 ? 's' : ''} selected
            </span>
            <button onClick={clearSelection} className="text-xs text-surface-400 hover:text-white transition-colors">
              Clear
            </button>
          </div>
          <div className="flex items-center gap-2">
            {bulkActions.map(({ action, label, icon: Icon, danger }) => (
              <button
                key={action}
                onClick={() => setBulkConfirm(bulkActions.find(a => a.action === action))}
                className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors ${
                  danger
                    ? 'bg-accent-red/10 text-accent-red hover:bg-accent-red/20 border border-accent-red/20'
                    : 'bg-surface-700/50 text-surface-300 hover:bg-surface-600/50 border border-surface-600/30'
                }`}
              >
                <Icon size={12} /> {label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="relative max-w-md">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
        <input type="text" placeholder="Search by email or username..." value={search}
          onChange={(e) => setSearch(e.target.value)} className="input-field pl-10" />
      </div>

      {/* Create User Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="glass-card p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-white">Create User</h2>
              <button onClick={() => setShowForm(false)} className="text-surface-500 hover:text-white"><X size={20} /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-surface-300 mb-1">Email</label>
                <input type="email" value={form.email} onChange={(e) => setForm(f => ({ ...f, email: e.target.value }))}
                  className="input-field" />
              </div>
              <div>
                <label className="block text-sm text-surface-300 mb-1">Password</label>
                <input type="password" value={form.password} onChange={(e) => setForm(f => ({ ...f, password: e.target.value }))}
                  className="input-field" placeholder="Min. 8 characters" />
              </div>
              <div>
                <label className="block text-sm text-surface-300 mb-1">Phone Number</label>
                <input type="tel" value={form.phone_number} onChange={(e) => setForm(f => ({ ...f, phone_number: e.target.value }))}
                  className="input-field" placeholder="+1234567890 (optional)" />
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" checked={form.is_staff} onChange={(e) => setForm(f => ({ ...f, is_staff: e.target.checked }))} />
                <label className="text-sm text-surface-300">Admin user</label>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
              <button onClick={handleCreate} className="btn-primary flex items-center gap-2">
                <Save size={16} /> Create
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Password Reset Modal */}
      {showPasswordReset && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="glass-card p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-white">Reset Password</h2>
              <button onClick={() => { setShowPasswordReset(null); setNewPassword('') }} className="text-surface-500 hover:text-white"><X size={20} /></button>
            </div>
            <p className="text-sm text-surface-400 mb-4">
              Reset password for <strong className="text-white">{showPasswordReset.email}</strong>
            </p>
            <div>
              <label className="block text-sm text-surface-300 mb-1">New Password</label>
              <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
                className="input-field" placeholder="Min. 8 characters" />
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => { setShowPasswordReset(null); setNewPassword('') }} className="btn-secondary">Cancel</button>
              <button onClick={handleResetPassword} className="btn-primary flex items-center gap-2">
                <Key size={16} /> Reset Password
              </button>
            </div>
          </div>
        </div>
      )}

      {/* User Detail Modal */}
      {showDetail && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="glass-card p-6 w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-white">User Details</h2>
              <button onClick={() => setShowDetail(null)} className="text-surface-500 hover:text-white"><X size={20} /></button>
            </div>

            <div className="space-y-4">
              {/* Basic Info */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-surface-500 uppercase">Username</p>
                  <p className="text-sm text-white font-medium">{showDetail.username}</p>
                </div>
                <div>
                  <p className="text-xs text-surface-500 uppercase">Status</p>
                  <span className={`badge text-xs ${showDetail.is_active
                    ? 'bg-accent-green/10 text-accent-green border border-accent-green/20'
                    : 'bg-accent-red/10 text-accent-red border border-accent-red/20'
                  }`}>{showDetail.is_active ? 'Active' : 'Disabled'}</span>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <Mail size={14} className="text-surface-500" />
                  <span className="text-surface-300">{showDetail.email}</span>
                </div>
                {showDetail.phone_number && (
                  <div className="flex items-center gap-2 text-sm">
                    <Phone size={14} className="text-surface-500" />
                    <span className="text-surface-300">{showDetail.phone_number}</span>
                  </div>
                )}
              </div>

              <div className="border-t border-surface-700 pt-4">
                <p className="text-xs text-surface-500 uppercase mb-3">Statistics</p>
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                    <p className="text-lg font-bold text-white">{showDetail.stats?.total_labs || 0}</p>
                    <p className="text-[10px] text-surface-500 uppercase">Total Labs</p>
                  </div>
                  <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                    <p className="text-lg font-bold text-accent-green">{showDetail.stats?.labs_completed || 0}</p>
                    <p className="text-[10px] text-surface-500 uppercase">Completed</p>
                  </div>
                  <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                    <p className="text-lg font-bold text-accent-amber">{showDetail.stats?.avg_score || 0}</p>
                    <p className="text-[10px] text-surface-500 uppercase">Avg Score</p>
                  </div>
                </div>
              </div>

              {showDetail.recent_labs?.length > 0 && (
                <div className="border-t border-surface-700 pt-4">
                  <p className="text-xs text-surface-500 uppercase mb-3">Recent Labs</p>
                  <div className="space-y-2">
                    {showDetail.recent_labs.map((lab) => (
                      <div key={lab.id} className="flex items-center justify-between text-sm bg-surface-800/30 rounded px-3 py-2">
                        <span className="text-surface-300">{lab.scenario}</span>
                        <div className="flex items-center gap-2">
                          <span className={`text-xs ${
                            lab.status === 'COMPLETED' ? 'text-accent-green'
                            : lab.status === 'TERMINATED' ? 'text-surface-500'
                            : 'text-accent-amber'
                          }`}>{lab.status}</span>
                          {lab.score > 0 && <span className="text-xs text-accent-amber">{lab.score}pts</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {showDetail.jira_tickets?.length > 0 && (
                <div className="border-t border-surface-700 pt-4">
                  <p className="text-xs text-surface-500 uppercase mb-3">Jira Tickets</p>
                  <div className="space-y-2">
                    {showDetail.jira_tickets.map((t) => (
                      <div key={t.issue_key} className="flex items-center justify-between text-sm bg-blue-500/5 border border-blue-500/10 rounded px-3 py-2">
                        <div className="min-w-0">
                          <p className="text-surface-300 truncate">{t.scenario?.title}</p>
                          <p className="text-xs text-surface-500">{t.jira_status || (t.is_closed ? 'Closed' : 'Open')}</p>
                        </div>
                        <JiraTicketLink issueKey={t.issue_key} issueUrl={t.issue_url} allowExternalLink className="text-xs shrink-0 ml-2" />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="text-xs text-surface-600 space-y-1 border-t border-surface-700 pt-4">
                <p>Joined: {new Date(showDetail.date_joined).toLocaleString()}</p>
                <p>Last Login: {showDetail.last_login ? new Date(showDetail.last_login).toLocaleString() : 'Never'}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="glass-card overflow-hidden">
        {loading ? (
          <SkeletonTable rows={6} cols={6} />
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-700/50 text-left">
                <th className="px-4 py-3 w-10">
                  <button onClick={toggleSelectAll} className="text-surface-400 hover:text-white transition-colors">
                    {allSelected ? <CheckSquare size={16} className="text-accent-cyan" /> : someSelected ? <MinusSquare size={16} className="text-accent-cyan" /> : <Square size={16} />}
                  </button>
                </th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase">User</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase">Phone</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase">Status</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase">Role</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase text-right">Labs</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase">Joined</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className={`border-b border-surface-800/50 hover:bg-surface-800/30 transition-colors ${selectedIds.has(u.id) ? 'bg-accent-cyan/5' : ''}`}>
                  <td className="px-4 py-3">
                    {u.is_superuser ? (
                      <span className="text-surface-600" title="Superuser (protected)"><Shield size={14} /></span>
                    ) : (
                      <button onClick={() => toggleSelect(u.id)} className="text-surface-400 hover:text-white transition-colors">
                        {selectedIds.has(u.id) ? <CheckSquare size={16} className="text-accent-cyan" /> : <Square size={16} />}
                      </button>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <p className="text-sm font-medium text-white">{u.first_name ? `${u.first_name} ${u.last_name || ''}`.trim() : u.username}</p>
                      {u.is_paid && <Crown size={13} className="text-accent-amber" title="Paid subscriber" />}
                      {u.complimentary_access && <span className="text-[10px] bg-accent-green/10 text-accent-green px-1.5 py-0.5 rounded font-medium">Free</span>}
                      {u.is_inactive_90d && <AlertTriangle size={13} className="text-accent-red" title="Inactive 90+ days" />}
                    </div>
                    <p className="text-xs text-surface-500">{u.email}</p>
                    {u.country && <p className="text-[10px] text-surface-600 flex items-center gap-0.5"><MapPin size={9} />{u.country}</p>}
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-xs text-surface-400">{u.phone_number || '—'}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`badge ${u.is_active
                      ? 'bg-accent-green/10 text-accent-green border border-accent-green/20'
                      : 'bg-accent-red/10 text-accent-red border border-accent-red/20'
                    }`}>
                      {u.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`badge ${u.is_staff
                      ? 'bg-accent-purple/10 text-accent-purple border border-accent-purple/20'
                      : 'bg-surface-700 text-surface-400'
                    }`}>
                      {u.is_staff ? 'Admin' : 'User'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-surface-400 text-right">{u.labs_completed}/{u.total_labs}</td>
                  <td className="px-4 py-3 text-xs text-surface-500">
                    {new Date(u.date_joined).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => handleViewDetail(u.id)} title="View Details"
                        className="p-1.5 text-surface-500 hover:text-accent-cyan transition-colors">
                        <Eye size={14} />
                      </button>
                      <button onClick={() => setShowPasswordReset(u)} title="Reset Password"
                        className="p-1.5 text-surface-500 hover:text-accent-green transition-colors">
                        <Key size={14} />
                      </button>
                      <button onClick={() => handleToggleActive(u)} title={u.is_active ? 'Disable' : 'Enable'}
                        className="p-1.5 text-surface-500 hover:text-accent-amber transition-colors">
                        <Ban size={14} />
                      </button>
                      <button onClick={() => handleToggleComplimentary(u)} title={u.complimentary_access ? 'Revoke free access' : 'Grant free access'}
                        className={`p-1.5 transition-colors ${u.complimentary_access ? 'text-accent-green hover:text-accent-green/80' : 'text-surface-500 hover:text-accent-green'}`}>
                        <Crown size={14} />
                      </button>
                      <button onClick={() => handleToggleStaff(u)} title={u.is_staff ? 'Remove admin' : 'Make admin'}
                        className="p-1.5 text-surface-500 hover:text-accent-purple transition-colors">
                        <Shield size={14} />
                      </button>
                      <button onClick={() => setDeleteConfirm(u)}
                        className="p-1.5 text-surface-500 hover:text-accent-red transition-colors" aria-label="Delete user">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Delete confirmation dialog */}
      <ConfirmDialog
        open={!!deleteConfirm}
        onClose={() => setDeleteConfirm(null)}
        title="Delete User?"
        message={`Permanently delete ${deleteConfirm?.email}? This action cannot be undone.`}
        confirmLabel="Delete"
        danger
        onConfirm={() => handleDelete(deleteConfirm?.id)}
      />

      {/* Bulk action confirmation dialog */}
      <ConfirmDialog
        open={!!bulkConfirm}
        onClose={() => setBulkConfirm(null)}
        title={bulkConfirm?.label || 'Confirm'}
        message={bulkConfirm?.confirm?.replace('{n}', String(selectedIds.size)) || ''}
        confirmLabel={bulkProcessing ? 'Processing...' : bulkConfirm?.label}
        danger={bulkConfirm?.danger}
        onConfirm={handleBulkAction}
      />
    </div>
  )
}
