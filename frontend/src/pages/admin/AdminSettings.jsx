import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { AdminPageHeader } from '../../components/design'
import { Wrench, AlertTriangle, Save, ToggleLeft, ToggleRight, Mail, Trash2, Bot, Shield, Eye, EyeOff, RefreshCw, CheckCircle2, KeyRound, Database, Zap, CreditCard } from 'lucide-react'
import { IMAGE_UPLOAD_HINTS } from '../../utils/mediaUrl'
import toast from 'react-hot-toast'

export default function AdminSettings() {
  const [maintenance, setMaintenance] = useState({ maintenance_mode: false, maintenance_message: '' })
  const [config, setConfig] = useState(null)
  const [emailForm, setEmailForm] = useState({ primary_email: '', payment_email: '', support_email: '', admin_display_currency: 'INR' })
  const [themeColors, setThemeColors] = useState({ cyan: '#06b6d4', purple: '#a855f7', amber: '#f59e0b', green: '#22c55e' })
  const [promoDraft, setPromoDraft] = useState({ title: '', text: '', link: '/pricing', bg_color: 'linear-gradient(90deg,#1e3a5f,#0f766e)', active: true })
  const [inactiveUsers, setInactiveUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showInactive, setShowInactive] = useState(false)
  const [supportBot, setSupportBot] = useState({
    support_bot_enabled: true,
    support_bot_name: 'FixitLab Assistant',
    support_bot_welcome_message: '',
    support_bot_typing_delay_ms: 1200,
    support_bot_quick_topics: [],
    support_bot_custom_faq: [],
  })
  const [faqDraft, setFaqDraft] = useState({ keywords: '', answer: '' })
  const [envSecrets, setEnvSecrets] = useState(null)
  const [envEdits, setEnvEdits] = useState({})
  const [envVisible, setEnvVisible] = useState({})
  const [envSyncing, setEnvSyncing] = useState(false)

  useEffect(() => {
    loadData()
    adminApi.getEnvSecrets().then(setEnvSecrets).catch(() => {})
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
      if (configData?.theme_colors) {
        setThemeColors(prev => ({ ...prev, ...configData.theme_colors }))
      }
      setSupportBot({
        support_bot_enabled: configData?.support_bot_enabled !== false,
        support_bot_name: configData?.support_bot_name || 'FixitLab Assistant',
        support_bot_welcome_message: configData?.support_bot_welcome_message || '',
        support_bot_typing_delay_ms: configData?.support_bot_typing_delay_ms || 1200,
        support_bot_quick_topics: configData?.support_bot_quick_topics || [],
        support_bot_custom_faq: configData?.support_bot_custom_faq || [],
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

  const handleDeletePromo = async (bannerId) => {
    if (!confirm('Delete this promo banner?')) return
    const banners = (config?.promo_banners || []).filter(b => (b.id || b.title) !== bannerId)
    setSaving(true)
    try {
      const result = await adminApi.updateConfig({ ...emailForm, promo_banners: banners })
      setConfig(result)
      toast.success('Promo banner removed')
    } catch {
      toast.error('Failed to delete promo')
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

  const handleResetDefaults = async () => {
    if (!window.confirm('Reset platform settings to defaults? Maintenance will be turned off and theme colors restored.')) return
    setSaving(true)
    try {
      const result = await adminApi.resetPlatformSettings()
      setConfig(result)
      setEmailForm({
        primary_email: result.primary_email || '',
        payment_email: result.payment_email || '',
        support_email: result.support_email || '',
        admin_display_currency: result.admin_display_currency || 'INR',
      })
      if (result.theme_colors) setThemeColors(prev => ({ ...prev, ...result.theme_colors }))
      setMaintenance(m => ({ ...m, maintenance_mode: false, maintenance_message: '' }))
      toast.success('Settings reset to defaults')
    } catch {
      toast.error('Reset failed')
    } finally {
      setSaving(false)
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
      <AdminPageHeader
        title="Platform Settings"
        subtitle="Maintenance mode, email configuration, and user management"
        actions={
          <button type="button" onClick={handleResetDefaults} disabled={saving} className="btn-secondary text-sm flex items-center gap-2">
            <Wrench size={14} /> Reset settings to normal
          </button>
        }
      />

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
        <label className="flex items-center gap-2 text-sm text-surface-400">
          <input type="checkbox" checked={config?.maintenance_banner_enabled !== false}
            onChange={async e => {
              const result = await adminApi.updateConfig({ ...emailForm, maintenance_banner_enabled: e.target.checked })
              setConfig(result)
            }} />
          Show maintenance banner on site
        </label>
        <div className="flex flex-wrap gap-2 items-center">
          <input type="file" accept="image/png,image/jpeg,image/webp" className="text-xs text-surface-400"
            onChange={async e => {
              const file = e.target.files?.[0]
              if (!file) return
              setSaving(true)
              try {
                const { url } = await adminApi.uploadBanner(file, 'maintenance', 'maintenance_banner')
                setMaintenance(m => ({ ...m, maintenance_banner_image: url }))
                toast.success('Banner uploaded')
              } catch (err) {
                toast.error(err.response?.data?.error || 'Upload failed')
              }
              finally { setSaving(false); e.target.value = '' }
            }} />
          <span className="text-xs text-surface-500">Required size: {IMAGE_UPLOAD_HINTS.maintenance_banner}</span>
        </div>
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
        <button
          type="button"
          onClick={async () => {
            try {
              const result = await adminApi.sendTestEmail()
              toast.success(result.sent ? `Test email sent to ${result.to_email}` : 'Send failed')
            } catch (err) {
              toast.error(err.response?.data?.error || 'Test email failed')
            }
          }}
          className="btn-secondary text-sm flex items-center gap-1"
        >
          <Mail size={14} /> Send test email
        </button>
      </div>

      {/* Theme / accent colors */}
      <div className="glass-card p-6 space-y-4">
        <h2 className="font-semibold text-lg">Application theme colors</h2>
        <p className="text-sm text-surface-400">Override accent colors shown across the platform (CSS variables).</p>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Object.entries(themeColors).map(([key, value]) => (
            <label key={key} className="text-sm capitalize">
              {key}
              <div className="flex gap-2 mt-1 items-center">
                <input type="color" value={value} onChange={e => setThemeColors(c => ({ ...c, [key]: e.target.value }))} className="h-9 w-12 rounded cursor-pointer" />
                <input type="text" className="input-field flex-1 font-mono text-xs" value={value} onChange={e => setThemeColors(c => ({ ...c, [key]: e.target.value }))} />
              </div>
            </label>
          ))}
        </div>
        <button
          disabled={saving}
          onClick={async () => {
            setSaving(true)
            try {
              const result = await adminApi.updateConfig({ ...emailForm, theme_colors: themeColors })
              setConfig(result)
              Object.entries(themeColors).forEach(([k, v]) => {
                document.documentElement.style.setProperty(`--a-${k}`, v.replace('#', '').match(/.{2}/g).map(x => parseInt(x, 16)).join(', '))
              })
              toast.success('Theme colors saved')
            } catch {
              toast.error('Failed to save theme')
            } finally {
              setSaving(false)
            }
          }}
          className="btn-primary text-sm flex items-center gap-1"
        >
          <Save size={14} /> Save theme colors
        </button>
      </div>

      {/* Promo / discount banners */}
      <div className="glass-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-lg">Discount & promo banners</h2>
          <label className="flex items-center gap-2 text-sm text-surface-400">
            <input type="checkbox" checked={config?.promo_banners_enabled !== false}
              onChange={async e => {
                const result = await adminApi.updateConfig({ ...emailForm, promo_banners_enabled: e.target.checked })
                setConfig(result)
              }} />
            Enabled
          </label>
        </div>
        <p className="text-sm text-surface-400">Shown on home, pricing, and subscription pages only.</p>
        <div className="grid sm:grid-cols-2 gap-3">
          <input className="input-field" placeholder="Title" value={promoDraft.title} onChange={e => setPromoDraft({ ...promoDraft, title: e.target.value })} />
          <input className="input-field" placeholder="Link (/pricing)" value={promoDraft.link} onChange={e => setPromoDraft({ ...promoDraft, link: e.target.value })} />
          <input className="input-field sm:col-span-2" placeholder="Offer text" value={promoDraft.text} onChange={e => setPromoDraft({ ...promoDraft, text: e.target.value })} />
          <input className="input-field sm:col-span-2" placeholder="Image URL (optional)" value={promoDraft.image_url || ''} onChange={e => setPromoDraft({ ...promoDraft, image_url: e.target.value })} />
          <input type="file" accept="image/png,image/jpeg,image/webp" className="text-xs text-surface-400 sm:col-span-2"
            onChange={async e => {
              const file = e.target.files?.[0]
              if (!file) return
              try {
                const { url } = await adminApi.uploadBanner(file, 'promo', 'promo_banner')
                setPromoDraft(p => ({ ...p, image_url: url }))
                toast.success('Promo image uploaded')
              } catch (err) {
                toast.error(err.response?.data?.error || 'Upload failed')
              }
              e.target.value = ''
            }} />
          <p className="text-xs text-surface-500 sm:col-span-2">Banner image: {IMAGE_UPLOAD_HINTS.promo_banner}</p>
        </div>
        <button onClick={handleAddPromo} disabled={saving} className="btn-secondary text-sm">Add promo banner</button>
        {(config?.promo_banners || []).length > 0 && (
          <ul className="text-sm text-surface-300 space-y-2">
            {config.promo_banners.map(b => (
              <li key={b.id || b.title} className="flex items-center justify-between gap-2 border border-surface-800 rounded-lg px-3 py-2">
                <div className="min-w-0">
                  <span className="font-medium text-white">{b.title}</span>
                  <span className="text-surface-500 truncate block text-xs">{b.text}</span>
                </div>
                <button
                  type="button"
                  onClick={() => handleDeletePromo(b.id || b.title)}
                  disabled={saving}
                  className="shrink-0 p-1.5 text-surface-400 hover:text-red-400 rounded transition-colors"
                  title="Delete banner"
                >
                  <Trash2 size={16} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Support assistant bot */}
      <div className="glass-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Bot size={20} className="text-accent-cyan" />
            <div>
              <h2 className="font-semibold text-lg">FixitLab Assistant</h2>
              <p className="text-sm text-surface-400">Floating help bot — how to use labs, Jira, subscriptions, and contacts</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSupportBot(s => ({ ...s, support_bot_enabled: !s.support_bot_enabled }))}
            className="flex items-center gap-2"
          >
            {supportBot.support_bot_enabled ? (
              <ToggleRight size={36} className="text-accent-cyan" />
            ) : (
              <ToggleLeft size={36} className="text-surface-500" />
            )}
          </button>
        </div>

        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium mb-1">Bot name</label>
            <input
              className="input-field w-full"
              value={supportBot.support_bot_name}
              onChange={e => setSupportBot(s => ({ ...s, support_bot_name: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Typing delay (ms)</label>
            <input
              type="number"
              min={300}
              max={5000}
              className="input-field w-full"
              value={supportBot.support_bot_typing_delay_ms}
              onChange={e => setSupportBot(s => ({ ...s, support_bot_typing_delay_ms: Number(e.target.value) || 1200 }))}
            />
          </div>
          <div className="sm:col-span-2">
            <label className="block text-sm font-medium mb-1">Welcome message</label>
            <textarea
              className="input-field w-full min-h-[80px]"
              value={supportBot.support_bot_welcome_message}
              onChange={e => setSupportBot(s => ({ ...s, support_bot_welcome_message: e.target.value }))}
              placeholder="Leave empty for default welcome text"
            />
          </div>
        </div>

        <div>
          <h3 className="text-sm font-medium text-surface-300 mb-2">Custom FAQ entries</h3>
          <div className="grid sm:grid-cols-2 gap-2 mb-2">
            <input
              className="input-field"
              placeholder="Keywords (comma-separated)"
              value={faqDraft.keywords}
              onChange={e => setFaqDraft(d => ({ ...d, keywords: e.target.value }))}
            />
            <input
              className="input-field"
              placeholder="Answer text"
              value={faqDraft.answer}
              onChange={e => setFaqDraft(d => ({ ...d, answer: e.target.value }))}
            />
          </div>
          <button
            type="button"
            className="btn-secondary text-sm mb-3"
            onClick={() => {
              if (!faqDraft.answer.trim()) { toast.error('Answer required'); return }
              const keywords = faqDraft.keywords.split(',').map(k => k.trim()).filter(Boolean)
              setSupportBot(s => ({
                ...s,
                support_bot_custom_faq: [...(s.support_bot_custom_faq || []), { keywords, answer: faqDraft.answer.trim() }],
              }))
              setFaqDraft({ keywords: '', answer: '' })
            }}
          >
            Add FAQ entry
          </button>
          {(supportBot.support_bot_custom_faq || []).length > 0 && (
            <ul className="text-sm space-y-2">
              {supportBot.support_bot_custom_faq.map((entry, i) => (
                <li key={i} className="flex justify-between gap-2 p-2 rounded-lg bg-surface-800/40 border border-surface-700/40">
                  <span className="text-surface-400 truncate">{(entry.keywords || []).join(', ')} → {entry.answer?.slice(0, 60)}…</span>
                  <button
                    type="button"
                    className="text-surface-500 hover:text-red-400 shrink-0"
                    onClick={() => setSupportBot(s => ({
                      ...s,
                      support_bot_custom_faq: s.support_bot_custom_faq.filter((_, j) => j !== i),
                    }))}
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <button
          type="button"
          disabled={saving}
          onClick={async () => {
            setSaving(true)
            try {
              const result = await adminApi.updateConfig({ ...emailForm, ...supportBot })
              setConfig(result)
              toast.success('Support assistant settings saved')
              window.dispatchEvent(new CustomEvent('fixitlab-support-config-changed'))
            } catch {
              toast.error('Failed to save support bot settings')
            } finally {
              setSaving(false)
            }
          }}
          className="btn-primary text-sm flex items-center gap-1"
        >
          <Save size={14} /> Save assistant settings
        </button>
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
      {/* ── Environment Secrets & Vault Sync ── */}
      <div className="glass-card p-5 border border-surface-800 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield size={16} className="text-indigo-400" />
            <h2 className="text-sm font-semibold text-white">Environment Secrets</h2>
          </div>
          <div className="flex items-center gap-2">
            {envSecrets?.vault_enabled ? (
              <span className="text-xs text-emerald-400 flex items-center gap-1"><CheckCircle2 size={12} /> Vault connected</span>
            ) : (
              <span className="text-xs text-amber-400 flex items-center gap-1"><AlertTriangle size={12} /> Vault not configured</span>
            )}
            {envSecrets?.vault_last_updated && (
              <span className="text-xs text-surface-500">
                Vault updated {envSecrets.vault_secret_age_days != null ? `${envSecrets.vault_secret_age_days}d ago` : 'recently'}
              </span>
            )}
          </div>
        </div>
        <p className="text-xs text-surface-500">
          Edit values below and click Sync to push to Vault and apply immediately without downtime.
          Red rows need rotation — credentials older than their threshold or using weak values.
        </p>
        {envSecrets?.secrets ? (
          <div className="space-y-2">
            {envSecrets.secrets.map(s => {
              const catIcon = s.category === 'security' ? <KeyRound size={12} />
                : s.category === 'database' ? <Database size={12} />
                : s.category === 'cache' ? <Zap size={12} />
                : s.category === 'payments' ? <CreditCard size={12} />
                : <Shield size={12} />
              const needsRot = s.needs_rotation
              return (
                <div
                  key={s.key}
                  className={`rounded-lg border px-3 py-2.5 ${needsRot ? 'border-red-500/40 bg-red-500/5' : 'border-surface-700 bg-surface-900/50'}`}
                >
                  <div className="flex items-start gap-2 flex-wrap">
                    <div className="flex items-center gap-1.5 text-surface-400 min-w-[14px]">{catIcon}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-mono font-semibold text-white">{s.key}</span>
                        <span className="text-xs text-surface-500">{s.label}</span>
                        {needsRot && (
                          <span className="text-xs text-red-400 flex items-center gap-0.5">
                            <AlertTriangle size={10} /> {s.rotation_reason}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1.5">
                        <div className="relative flex-1 max-w-xs">
                          <input
                            type={envVisible[s.key] ? 'text' : 'password'}
                            placeholder={s.masked || (s.is_set ? '(set — enter new value to rotate)' : 'Not set')}
                            value={envEdits[s.key] || ''}
                            onChange={e => setEnvEdits(p => ({ ...p, [s.key]: e.target.value }))}
                            className={`w-full bg-surface-800 border text-xs rounded px-2.5 py-1.5 font-mono text-white placeholder-surface-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 ${needsRot ? 'border-red-500/40' : 'border-surface-700'}`}
                          />
                          <button
                            type="button"
                            onClick={() => setEnvVisible(p => ({ ...p, [s.key]: !p[s.key] }))}
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-500 hover:text-white"
                          >
                            {envVisible[s.key] ? <EyeOff size={12} /> : <Eye size={12} />}
                          </button>
                        </div>
                        {s.is_set && !envEdits[s.key] && (
                          <span className="text-xs font-mono text-surface-500">{s.masked}</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <p className="text-xs text-surface-500">Loading secrets…</p>
        )}
        <div className="flex items-center gap-3">
          <button
            type="button"
            disabled={envSyncing || Object.keys(envEdits).filter(k => envEdits[k]).length === 0}
            onClick={async () => {
              const updates = Object.fromEntries(Object.entries(envEdits).filter(([, v]) => v))
              if (!updates || !Object.keys(updates).length) return
              setEnvSyncing(true)
              try {
                const result = await adminApi.syncEnvSecrets(updates)
                toast.success(`Synced ${result.synced_keys?.length || 0} secret(s)${result.vault_updated ? ' to Vault' : ''}`)
                setEnvEdits({})
                adminApi.getEnvSecrets().then(setEnvSecrets).catch(() => {})
              } catch {
                toast.error('Sync failed')
              } finally {
                setEnvSyncing(false)
              }
            }}
            className="btn-primary text-xs py-1.5 px-4 flex items-center gap-1.5 disabled:opacity-50"
          >
            {envSyncing ? <RefreshCw size={13} className="animate-spin" /> : <RefreshCw size={13} />}
            Sync to Vault
          </button>
          <span className="text-xs text-surface-500">
            {Object.keys(envEdits).filter(k => envEdits[k]).length} change(s) pending
          </span>
        </div>
      </div>
    </div>
  )
}
