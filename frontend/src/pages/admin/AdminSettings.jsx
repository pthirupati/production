import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { Wrench, AlertTriangle, Save, ToggleLeft, ToggleRight, Mail, Settings } from 'lucide-react'
import toast from 'react-hot-toast'

export default function AdminSettings() {
  const [maintenance, setMaintenance] = useState({ maintenance_mode: false, maintenance_message: '' })
  const [config, setConfig] = useState(null)
  const [emailForm, setEmailForm] = useState({ primary_email: '', payment_email: '', support_email: '', admin_display_currency: 'INR' })
  const [promoDraft, setPromoDraft] = useState({ title: '', text: '', link: '/pricing', bg_color: 'linear-gradient(90deg,#1e3a5f,#0f766e)', active: true })
  const [inactiveUsers, setInactiveUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showInactive, setShowInactive] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [maintenanceData, configData] = await Promise.all([
        adminApi.getMaintenanceMode(),
        adminApi.getConfig(),
      ])
      setMaintenance(maintenanceData)
      setConfig(configData)
      setEmailForm({
        primary_email: configData?.primary_email || '',
        payment_email: configData?.payment_email || '',
        support_email: configData?.support_email || '',
        admin_display_currency: configData?.admin_display_currency || 'INR',
      })
    } catch {
      toast.error('Failed to load settings')
    } finally {
      setLoading(false)
    }
  }

  const handleToggleMaintenance = async () => {
    setSaving(true)
    try {
      const result = await adminApi.setMaintenanceMode({
        enabled: !maintenance.maintenance_mode,
        message: maintenance.maintenance_message,
        notify_users: maintenance.maintenance_notify_users !== false,
      })
      setMaintenance(result)
      toast.success(result.maintenance_mode ? 'Maintenance mode enabled' : 'Maintenance mode disabled')
    } catch {
      toast.error('Failed to update')
    } finally {
      setSaving(false)
    }
  }

  const handleSaveEmails = async () => {
    setSaving(true)
    try {
      const result = await adminApi.updateConfig(emailForm)
      setConfig(result)
      toast.success('Emails and currency saved (synced to platform config file)')
    } catch {
      toast.error('Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const handleAddPromo = async () => {
    if (!promoDraft.title) { toast.error('Title required'); return }
    const banners = [...(config?.promo_banners || []), { ...promoDraft, id: Date.now().toString() }]
    setSaving(true)
    try {
      const result = await adminApi.updateConfig({ ...emailForm, promo_banners: banners })
      setConfig(result)
      setPromoDraft({ title: '', text: '', link: '/pricing', bg_color: 'linear-gradient(90deg,#1e3a5f,#0f766e)', active: true })
      toast.success('Promo banner added')
    } catch {
      toast.error('Failed to add promo')
    } finally {
      setSaving(false)
    }
  }

  const handleUpdateMessage = async () => {
    setSaving(true)
    try {
      const result = await adminApi.setMaintenanceMode({
        enabled: maintenance.maintenance_mode,
        message: maintenance.maintenance_message,
        banner_image: maintenance.maintenance_banner_image,
        scheduled_start: maintenance.maintenance_scheduled_start,
        scheduled_end: maintenance.maintenance_scheduled_end,
        notify_users: maintenance.maintenance_notify_users !== false,
      })
      setMaintenance(result)
      toast.success('Maintenance settings updated')
    } catch {
      toast.error('Failed to update')
    } finally {
      setSaving(false)
    }
  }

  const loadInactiveUsers = async () => {
    try {
      const data = await adminApi.getInactiveUsers(90)
      setInactiveUsers(data.inactive_users || [])
      setShowInactive(true)
    } catch {
      toast.error('Failed to load inactive users')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Settings size={24} className="text-accent-cyan" />
          Platform Settings
        </h1>
        <p className="text-surface-400 mt-1">Maintenance mode, email configuration, and user management</p>
      </div>

      {/* Maintenance Mode */}
      <div className="glass-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertTriangle size={20} className={maintenance.maintenance_mode ? 'text-amber-400' : 'text-surface-400'} />
            <div>
              <h2 className="font-semibold text-lg">Maintenance Mode</h2>
              <p className="text-sm text-surface-400">Show a maintenance banner to all users</p>
            </div>
          </div>
          <button
            onClick={handleToggleMaintenance}
            disabled={saving}
            className="flex items-center gap-2"
          >
            {maintenance.maintenance_mode ? (
              <ToggleRight size={36} className="text-amber-400" />
            ) : (
              <ToggleLeft size={36} className="text-surface-500" />
            )}
          </button>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Banner Message</label>
          <div className="flex gap-2">
            <input
              type="text"
              className="input-field flex-1"
              value={maintenance.maintenance_message}
              onChange={(e) => setMaintenance({ ...maintenance, maintenance_message: e.target.value })}
            />
            <button onClick={handleUpdateMessage} disabled={saving} className="btn-primary flex items-center gap-1">
              <Save size={14} /> Save
            </button>
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-3">
          <label className="text-sm">
            Scheduled start
            <input type="datetime-local" className="input-field w-full mt-1"
              value={maintenance.maintenance_scheduled_start?.slice(0, 16) || ''}
              onChange={e => setMaintenance({ ...maintenance, maintenance_scheduled_start: e.target.value })} />
          </label>
          <label className="text-sm">
            Scheduled end
            <input type="datetime-local" className="input-field w-full mt-1"
              value={maintenance.maintenance_scheduled_end?.slice(0, 16) || ''}
              onChange={e => setMaintenance({ ...maintenance, maintenance_scheduled_end: e.target.value })} />
          </label>
        </div>
        <label className="flex items-center gap-2 text-sm text-surface-400">
          <input type="checkbox" checked={maintenance.maintenance_notify_users !== false}
            onChange={e => setMaintenance({ ...maintenance, maintenance_notify_users: e.target.checked })} />
          Email all registered users when maintenance is enabled
        </label>
        <input type="url" className="input-field w-full" placeholder="Banner image URL (optional)"
          value={maintenance.maintenance_banner_image || ''}
          onChange={e => setMaintenance({ ...maintenance, maintenance_banner_image: e.target.value })} />

        {maintenance.maintenance_mode && (
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 text-sm text-amber-400">
            Maintenance mode is currently ACTIVE. Users will see the banner.
          </div>
        )}
      </div>

      {/* Email Configuration */}
      <div className="glass-card p-6 space-y-4">
        <div className="flex items-center gap-3 mb-2">
          <Mail size={20} className="text-accent-cyan" />
          <h2 className="font-semibold text-lg">Email & Revenue Currency</h2>
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <label className="text-sm">Primary<input className="input-field w-full mt-1" value={emailForm.primary_email} onChange={e => setEmailForm({ ...emailForm, primary_email: e.target.value })} /></label>
          <label className="text-sm">Payment<input className="input-field w-full mt-1" value={emailForm.payment_email} onChange={e => setEmailForm({ ...emailForm, payment_email: e.target.value })} /></label>
          <label className="text-sm">Support<input className="input-field w-full mt-1" value={emailForm.support_email} onChange={e => setEmailForm({ ...emailForm, support_email: e.target.value })} /></label>
          <label className="text-sm">Admin revenue currency
            <select className="input-field w-full mt-1" value={emailForm.admin_display_currency} onChange={e => setEmailForm({ ...emailForm, admin_display_currency: e.target.value })}>
              <option value="INR">INR (₹)</option>
              <option value="USD">USD ($)</option>
            </select>
          </label>
        </div>
        <button onClick={handleSaveEmails} disabled={saving} className="btn-primary text-sm flex items-center gap-1">
          <Save size={14} /> Save emails & currency
        </button>
      </div>

      {/* Promo / discount banners */}
      <div className="glass-card p-6 space-y-4">
        <h2 className="font-semibold text-lg">Discount & promo banners</h2>
        <p className="text-sm text-surface-400">Shown on home and logged-in app (like storefront offers).</p>
        <div className="grid sm:grid-cols-2 gap-3">
          <input className="input-field" placeholder="Title" value={promoDraft.title} onChange={e => setPromoDraft({ ...promoDraft, title: e.target.value })} />
          <input className="input-field" placeholder="Link (/pricing)" value={promoDraft.link} onChange={e => setPromoDraft({ ...promoDraft, link: e.target.value })} />
          <input className="input-field sm:col-span-2" placeholder="Offer text" value={promoDraft.text} onChange={e => setPromoDraft({ ...promoDraft, text: e.target.value })} />
          <input className="input-field sm:col-span-2" placeholder="Image URL (optional)" value={promoDraft.image_url || ''} onChange={e => setPromoDraft({ ...promoDraft, image_url: e.target.value })} />
        </div>
        <button onClick={handleAddPromo} disabled={saving} className="btn-secondary text-sm">Add promo banner</button>
        {(config?.promo_banners || []).length > 0 && (
          <ul className="text-sm text-surface-300 space-y-1">
            {config.promo_banners.map(b => (
              <li key={b.id || b.title} className="flex justify-between gap-2 border-b border-surface-800 py-1">
                <span>{b.title}</span>
                <span className="text-surface-500 truncate">{b.text}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Inactive Users */}
      <div className="glass-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-lg">Inactive Users</h2>
            <p className="text-sm text-surface-400">Users who haven't logged in for 90+ days</p>
          </div>
          <button onClick={loadInactiveUsers} className="btn-secondary text-sm">
            Load Inactive Users
          </button>
        </div>

        {showInactive && (
          <div>
            <p className="text-sm text-surface-400 mb-3">{inactiveUsers.length} inactive users found</p>
            <div className="max-h-80 overflow-y-auto space-y-2">
              {inactiveUsers.map(user => (
                <div key={user.id} className="flex items-center justify-between p-3 bg-surface-800/30 rounded-lg">
                  <div>
                    <p className="font-medium text-sm">{user.username}</p>
                    <p className="text-xs text-surface-500">{user.email}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-surface-400">
                      {user.last_login ? `Last login: ${new Date(user.last_login).toLocaleDateString()}` : 'Never logged in'}
                    </p>
                    <p className="text-xs text-amber-400">
                      {typeof user.days_inactive === 'number' ? `${user.days_inactive} days inactive` : user.days_inactive}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
