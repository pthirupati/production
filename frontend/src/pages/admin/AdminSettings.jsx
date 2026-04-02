import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { Wrench, AlertTriangle, Save, ToggleLeft, ToggleRight, Mail, Settings } from 'lucide-react'
import toast from 'react-hot-toast'

export default function AdminSettings() {
  const [maintenance, setMaintenance] = useState({ maintenance_mode: false, maintenance_message: '' })
  const [config, setConfig] = useState(null)
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
    } catch {
      toast.error('Failed to load settings')
    } finally {
      setLoading(false)
    }
  }

  const handleToggleMaintenance = async () => {
    setSaving(true)
    try {
      const result = await adminApi.setMaintenanceMode(
        !maintenance.maintenance_mode,
        maintenance.maintenance_message
      )
      setMaintenance(result)
      toast.success(result.maintenance_mode ? 'Maintenance mode enabled' : 'Maintenance mode disabled')
    } catch {
      toast.error('Failed to update')
    } finally {
      setSaving(false)
    }
  }

  const handleUpdateMessage = async () => {
    setSaving(true)
    try {
      const result = await adminApi.setMaintenanceMode(
        maintenance.maintenance_mode,
        maintenance.maintenance_message
      )
      setMaintenance(result)
      toast.success('Message updated')
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

        {maintenance.maintenance_mode && (
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 text-sm text-amber-400">
            Maintenance mode is currently ACTIVE. Users will see the banner.
          </div>
        )}
      </div>

      {/* Email Configuration (read-only) */}
      <div className="glass-card p-6 space-y-4">
        <div className="flex items-center gap-3 mb-2">
          <Mail size={20} className="text-accent-cyan" />
          <h2 className="font-semibold text-lg">Email Configuration</h2>
        </div>
        <p className="text-sm text-surface-400">Configured via environment variables (.env file)</p>
        <div className="grid sm:grid-cols-3 gap-4">
          <div className="p-3 bg-surface-800/50 rounded-lg">
            <p className="text-xs text-surface-500 mb-1">Primary Email</p>
            <p className="text-sm font-mono">{config?.primary_email}</p>
          </div>
          <div className="p-3 bg-surface-800/50 rounded-lg">
            <p className="text-xs text-surface-500 mb-1">Payment Email</p>
            <p className="text-sm font-mono">{config?.payment_email}</p>
          </div>
          <div className="p-3 bg-surface-800/50 rounded-lg">
            <p className="text-xs text-surface-500 mb-1">Support Email</p>
            <p className="text-sm font-mono">{config?.support_email}</p>
          </div>
        </div>
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
