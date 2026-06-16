import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { authApi } from '../api/auth'
import { labApi } from '../api/labs'
import { subscriptionApi } from '../api/subscriptions'
import api from '../api/client'
import { User, Lock, Save, Phone, Mail, Shield, CreditCard, Zap, ArrowUpRight, MapPin, Bell, BellOff, Calendar, AlertTriangle, FileText, Download, Github, Users, Trash2, Mic2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { startOAuth } from '../utils/oauth'
import { validators } from '../utils/validators'
import { SkeletonCard } from '../components/Skeleton'
import { interviewsApi } from '../api/interviews'

export default function Profile() {
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const [username, setUsername] = useState(user?.username || '')
  const [firstName, setFirstName] = useState(user?.first_name || '')
  const [lastName, setLastName] = useState(user?.last_name || '')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [country, setCountry] = useState('')
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)
  const [errors, setErrors] = useState({})
  const [planInfo, setPlanInfo] = useState(null)
  const [notifPrefs, setNotifPrefs] = useState(null)
  const [techSubscriptions, setTechSubscriptions] = useState([])
  const [complimentaryAccess, setComplimentaryAccess] = useState(false)
  const [invoices, setInvoices] = useState([])
  const [organizations, setOrganizations] = useState([])
  const [socialAccounts, setSocialAccounts] = useState([])
  const [socialConfig, setSocialConfig] = useState(null)
  const [interviewProfile, setInterviewProfile] = useState(null)
  const [gdprBusy, setGdprBusy] = useState(null)
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [deletePassword, setDeletePassword] = useState('')
  const [deletingAccount, setDeletingAccount] = useState(false)
  const [hasUsablePassword, setHasUsablePassword] = useState(true)

  // Load full profile data including phone number
  useEffect(() => {
    authApi.getSocialConfig().then(setSocialConfig).catch(() => {})
    Promise.all([
      authApi.getProfile(),
      labApi.getUserPlan().catch(() => null),
      api.get('/notifications/preferences/').then(r => r.data).catch(() => null),
      subscriptionApi.getMySubscriptions().catch(() => ({ subscriptions: [] })),
      subscriptionApi.getMyInvoices().catch(() => ({ invoices: [] })),
      subscriptionApi.getUnifiedBilling().catch(() => null),
      interviewsApi.getProfile().catch(() => null),
    ]).then(([profileData, plan, prefs, subsData, invData, unified, intProfile]) => {
      setUsername(profileData.username || '')
      setFirstName(profileData.first_name || '')
      setLastName(profileData.last_name || '')
      setPhoneNumber(profileData.phone_number || '')
      setCountry(profileData.country || '')
      if (plan) setPlanInfo(plan)
      if (prefs) setNotifPrefs(prefs)
      setTechSubscriptions(subsData?.subscriptions || [])
      setComplimentaryAccess(subsData?.complimentary_access || false)
      setInvoices(invData?.invoices || [])
      setSocialAccounts(profileData.social_accounts || [])
      setHasUsablePassword(profileData.has_usable_password !== false)
      setOrganizations(unified?.organizations || [])
      setInterviewProfile(intProfile)
    }).catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const validateProfile = () => {
    const e = {}
    const uv = validators.username(username)
    if (!uv.valid) e.username = uv.error
    const pv = validators.phone(phoneNumber)
    if (!pv.valid) e.phone = pv.error
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleUpdateProfile = async (e) => {
    e.preventDefault()
    if (!validateProfile()) return
    setSaving(true)
    try {
      await authApi.updateProfile({ username, phone_number: phoneNumber, first_name: firstName, last_name: lastName, country })
      toast.success('Profile updated')
      setErrors({})
    } catch (err) {
      toast.error('Update failed')
    } finally {
      setSaving(false)
    }
  }

  const handleChangePassword = async (e) => {
    e.preventDefault()
    const pv = validators.password(newPassword)
    if (!pv.valid) {
      setErrors(prev => ({ ...prev, newPassword: pv.error }))
      return
    }
    setSaving(true)
    try {
      await authApi.changePassword(oldPassword, newPassword)
      toast.success('Password changed')
      setOldPassword('')
      setNewPassword('')
      setErrors({})
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to change password')
    } finally {
      setSaving(false)
    }
  }

  const pwStrength = validators.passwordStrength(newPassword)

  const handleSocialLink = (provider) => {
    if (!socialConfig?.[provider]?.enabled) {
      toast.error(`${provider === 'github' ? 'GitHub' : 'Google'} is not configured on this server.`)
      return
    }
    startOAuth(provider, 'link')
  }

  const downloadInvoice = async (inv) => {
    try {
      const res = await subscriptionApi.downloadInvoice(inv.id)
      const blob = new Blob([res.data], { type: 'text/html' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${inv.invoice_number}.html`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('Invoice downloaded')
    } catch {
      toast.error('Failed to download invoice')
    }
  }

  if (loading) return (
    <div className="max-w-2xl mx-auto space-y-6">
      <SkeletonCard lines={4} />
      <SkeletonCard lines={3} />
    </div>
  )

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in">
      <div className="relative overflow-hidden glass-card p-8 mb-6">
        <div className="absolute inset-0 bg-gradient-to-r from-accent-cyan/8 via-transparent to-accent-purple/8" />
        <div className="absolute inset-0 bg-dots-pattern opacity-20" />
        <div className="relative">
          <h1 className="text-3xl font-black text-white tracking-tight">
            <span className="bg-gradient-to-r from-accent-cyan to-accent-purple bg-clip-text text-transparent">Profile Settings</span>
          </h1>
        </div>
      </div>

      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <User size={18} className="text-accent-cyan" /> Profile
        </h2>
        <form onSubmit={handleUpdateProfile} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1.5 flex items-center gap-1.5">
              <Mail size={14} /> Email
            </label>
            <input type="text" value={user?.email || ''} disabled className="input-field opacity-50 cursor-not-allowed" />
            <p className="text-xs text-surface-600 mt-1">Email cannot be changed</p>
          </div>
          <div>
            <label htmlFor="profile-username" className="block text-sm font-medium text-surface-300 mb-1.5 flex items-center gap-1.5">
              <User size={14} /> Username
            </label>
            <input id="profile-username" type="text" value={username} onChange={(e) => setUsername(e.target.value)}
              className={`input-field ${errors.username ? 'border-accent-red' : ''}`}
              aria-invalid={!!errors.username} aria-describedby={errors.username ? 'username-error' : undefined} />
            {errors.username && <p id="username-error" className="text-xs text-accent-red mt-1">{errors.username}</p>}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1.5 flex items-center gap-1.5">
                <User size={14} /> First Name
              </label>
              <input type="text" value={firstName} onChange={(e) => setFirstName(e.target.value)}
                className="input-field" placeholder="John" autoComplete="given-name" />
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1.5 flex items-center gap-1.5">
                <User size={14} /> Last Name
              </label>
              <input type="text" value={lastName} onChange={(e) => setLastName(e.target.value)}
                className="input-field" placeholder="Doe" autoComplete="family-name" />
            </div>
          </div>
          <div>
            <label htmlFor="profile-phone" className="block text-sm font-medium text-surface-300 mb-1.5 flex items-center gap-1.5">
              <Phone size={14} /> Phone Number
            </label>
            <input
              id="profile-phone"
              type="tel"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              className={`input-field ${errors.phone ? 'border-accent-red' : ''}`}
              placeholder="+1234567890"
              aria-invalid={!!errors.phone}
            />
            {errors.phone
              ? <p className="text-xs text-accent-red mt-1">{errors.phone}</p>
              : <p className="text-xs text-surface-600 mt-1">International format (e.g., +1234567890)</p>
            }
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1.5 flex items-center gap-1.5">
              <MapPin size={14} /> Country / Location
            </label>
            <input
              type="text"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              className="input-field"
              placeholder="e.g., United States, India, Germany"
            />
          </div>
          <button type="submit" disabled={saving} className="btn-primary flex items-center gap-2">
            <Save size={16} /> Save Changes
          </button>
        </form>
      </div>

      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Lock size={18} className="text-accent-amber" /> Change Password
        </h2>
        <form onSubmit={handleChangePassword} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1.5">Current Password</label>
            <input type="password" value={oldPassword} onChange={(e) => setOldPassword(e.target.value)}
              className="input-field" required />
          </div>
          <div>
            <label htmlFor="new-password" className="block text-sm font-medium text-surface-300 mb-1.5">New Password</label>
            <input id="new-password" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
              className={`input-field ${errors.newPassword ? 'border-accent-red' : ''}`}
              placeholder="Min. 8 characters" required
              aria-invalid={!!errors.newPassword} />
            {errors.newPassword && <p className="text-xs text-accent-red mt-1">{errors.newPassword}</p>}
            {/* Password strength meter */}
            {newPassword && (
              <div className="mt-2">
                <div className="flex items-center gap-1.5 mb-1">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className={`h-1.5 flex-1 rounded-full transition-colors ${
                      i < pwStrength.score ? pwStrength.color : 'bg-surface-700'
                    }`} />
                  ))}
                </div>
                <p className={`text-xs ${pwStrength.score >= 3 ? 'text-accent-green' : pwStrength.score >= 2 ? 'text-accent-amber' : 'text-accent-red'}`}>
                  {pwStrength.label}
                </p>
              </div>
            )}
          </div>
          <button type="submit" disabled={saving} className="btn-primary flex items-center gap-2">
            <Lock size={16} /> Update Password
          </button>
        </form>
      </div>

      {/* Account Info */}
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Shield size={18} className="text-accent-green" /> Account Info
        </h2>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-surface-400">Account Type</span>
            <span className="text-white font-medium">{user?.is_staff ? 'Admin' : 'User'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-surface-400">Member Since</span>
            <span className="text-white font-medium">
              {user?.date_joined ? new Date(user.date_joined).toLocaleDateString() : 'N/A'}
            </span>
          </div>
        </div>
      </div>

      {/* Linked accounts */}
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Github size={18} className="text-accent-cyan" /> Linked Accounts
        </h2>
        <p className="text-sm text-surface-400 mb-4">Connect GitHub or Google for faster sign-in after OTP registration.</p>
        <div className="space-y-3">
          {['github', 'google'].map(provider => {
            const linked = socialAccounts.some(s => s.provider === provider)
            const label = provider === 'github' ? 'GitHub' : 'Google'
            return (
              <div key={provider} className="flex items-center justify-between p-3 rounded-lg bg-surface-800/50">
                <span className="text-white font-medium">{label}</span>
                {linked ? (
                  <span className="text-xs text-accent-green px-2 py-1 rounded-full bg-accent-green/10">Linked</span>
                ) : (
                  <button type="button" onClick={() => handleSocialLink(provider)} className="btn-secondary text-xs px-3 py-1.5">
                    Link {label}
                  </button>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Notification Preferences */}
      {notifPrefs && (
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Bell size={18} className="text-accent-amber" /> Notification Preferences
          </h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xs font-semibold text-surface-400 uppercase tracking-wider mb-3">Email Notifications</h3>
              <div className="space-y-3">
                {[
                  { key: 'email_achievements', label: 'Achievement unlocked', desc: 'Get notified when you earn badges' },
                  { key: 'email_lab_completed', label: 'Lab completed', desc: 'Off by default — use in-app notifications instead' },
                  { key: 'email_lab_expired', label: 'Lab expired', desc: 'Off by default — use in-app notifications instead' },
                  { key: 'email_subscription', label: 'Subscription updates', desc: 'Confirmation and billing emails' },
                  { key: 'email_marketing', label: 'Subscribe reminders & tips', desc: 'Interview/technology benefits and product updates. Use the Unsubscribe link in any email, or toggle here.' },
                ].map(({ key, label, desc }) => (
                  <label key={key} className="flex items-center justify-between p-3 rounded-lg bg-surface-800/50 hover:bg-surface-800 transition-colors cursor-pointer group">
                    <div>
                      <p className="text-sm text-white font-medium">{label}</p>
                      <p className="text-xs text-surface-500">{desc}</p>
                    </div>
                    <div className="relative">
                      <input
                        type="checkbox"
                        checked={notifPrefs[key]}
                        onChange={async () => {
                          const updated = { ...notifPrefs, [key]: !notifPrefs[key] }
                          setNotifPrefs(updated)
                          try {
                            await api.patch('/notifications/preferences/', { [key]: !notifPrefs[key] })
                          } catch {
                            setNotifPrefs(notifPrefs)
                            toast.error('Failed to update preference')
                          }
                        }}
                        className="sr-only peer"
                      />
                      <div className="w-10 h-5 bg-surface-700 peer-checked:bg-accent-cyan rounded-full transition-colors" />
                      <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-5" />
                    </div>
                  </label>
                ))}
              </div>
            </div>
            <div className="border-t border-surface-800 pt-4">
              <h3 className="text-xs font-semibold text-surface-400 uppercase tracking-wider mb-3">In-App Notifications</h3>
              <div className="space-y-3">
                {[
                  { key: 'inapp_achievements', label: 'Achievements & streaks' },
                  { key: 'inapp_lab_events', label: 'Lab events' },
                  { key: 'inapp_system', label: 'System messages' },
                ].map(({ key, label }) => (
                  <label key={key} className="flex items-center justify-between p-3 rounded-lg bg-surface-800/50 hover:bg-surface-800 transition-colors cursor-pointer">
                    <p className="text-sm text-white font-medium">{label}</p>
                    <div className="relative">
                      <input
                        type="checkbox"
                        checked={notifPrefs[key]}
                        onChange={async () => {
                          const updated = { ...notifPrefs, [key]: !notifPrefs[key] }
                          setNotifPrefs(updated)
                          try {
                            await api.patch('/notifications/preferences/', { [key]: !notifPrefs[key] })
                          } catch {
                            setNotifPrefs(notifPrefs)
                            toast.error('Failed to update preference')
                          }
                        }}
                        className="sr-only peer"
                      />
                      <div className="w-10 h-5 bg-surface-700 peer-checked:bg-accent-cyan rounded-full transition-colors" />
                      <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-5" />
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Technology Subscriptions */}
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <CreditCard size={18} className="text-accent-amber" /> Technology Subscriptions
        </h2>
        {complimentaryAccess ? (
          <div className="p-4 rounded-lg bg-accent-green/10 border border-accent-green/20 text-sm text-accent-green">
            You have complimentary free access to all technologies.
          </div>
        ) : techSubscriptions.filter(s => s.is_active).length === 0 ? (
          <div className="text-center py-6">
            <p className="text-surface-400 text-sm mb-3">No active technology subscriptions</p>
            <p className="text-xs text-surface-500 mb-3">Pay securely with Razorpay/Stripe at checkout — invoices appear below.</p>
            <Link to="/pricing" className="btn-primary text-sm inline-flex items-center gap-1.5">
              <Zap size={14} /> View Pricing
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {techSubscriptions.filter(s => s.is_active || s.is_expired).map(sub => (
              <div key={sub.id} className="p-4 rounded-lg bg-surface-800/50 border border-surface-700/40">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-white font-medium">{sub.technology?.name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    sub.is_active ? 'bg-accent-green/10 text-accent-green' : 'bg-accent-red/10 text-accent-red'
                  }`}>{sub.is_active ? 'Active' : 'Expired'}</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs text-surface-400">
                  {sub.created_at && (
                    <div className="flex items-center gap-1">
                      <Calendar size={12} /> Started: {new Date(sub.created_at).toLocaleDateString()}
                    </div>
                  )}
                  {sub.expires_at && (
                    <div className={`flex items-center gap-1 ${sub.needs_renewal ? 'text-accent-amber' : ''}`}>
                      <Calendar size={12} /> Expires: {new Date(sub.expires_at).toLocaleDateString()}
                    </div>
                  )}
                </div>
                {(sub.needs_renewal || sub.is_expired || sub.in_grace_period) && (
                  <Link
                    to={`/payment?technology=${sub.technology?.slug}&renew=1`}
                    className="mt-3 inline-flex items-center gap-1.5 text-sm text-accent-amber hover:text-accent-amber/80 font-medium"
                  >
                    <CreditCard size={14} /> {sub.in_grace_period ? 'Renew to restore lab access' : `Renew for ₹${sub.amount}`}
                  </Link>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {organizations.length > 0 && (
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Users size={18} className="text-accent-cyan" /> Organizations
          </h2>
          <ul className="space-y-2 text-sm">
            {organizations.map(org => (
              <li key={org.slug} className="flex justify-between border-b border-surface-800 py-2">
                <span className="text-white">{org.name}</span>
                <span className="text-surface-500 capitalize">{org.role} · {org.seat_limit} seats</span>
              </li>
            ))}
          </ul>
          <Link to="/team" className="text-accent-cyan text-sm mt-3 inline-block hover:underline">Manage team →</Link>
        </div>
      )}

      {/* Interview data & GDPR */}
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Mic2 size={18} className="text-indigo-400" /> Interview Data & Privacy
        </h2>
        <p className="text-sm text-surface-400 mb-4">
          Manage resume and transcript data stored for AI mock interviews.
        </p>
        <div className="space-y-3">
          <div className="flex items-center justify-between p-3 rounded-lg bg-surface-800/50 border border-surface-700/40 gap-3">
            <div>
              <p className="text-sm text-white">Uploaded resume</p>
              <p className="text-xs text-surface-500">
                {interviewProfile?.has_resume ? 'On file — used to personalize questions' : 'No resume stored'}
              </p>
            </div>
            {interviewProfile?.has_resume && (
              <button
                type="button"
                disabled={gdprBusy === 'resume'}
                onClick={async () => {
                  if (!window.confirm('Delete your stored resume and parsed data? This cannot be undone.')) return
                  setGdprBusy('resume')
                  try {
                    await interviewsApi.deleteResume()
                    setInterviewProfile(p => ({ ...p, has_resume: false, resume_text: '' }))
                    toast.success('Resume removed')
                  } catch {
                    toast.error('Could not delete resume')
                  } finally {
                    setGdprBusy(null)
                  }
                }}
                className="btn-secondary text-xs px-3 py-1.5 flex items-center gap-1 text-accent-red border-accent-red/30 shrink-0"
              >
                <Trash2 size={12} /> Delete resume
              </button>
            )}
          </div>
          <div className="flex items-center justify-between p-3 rounded-lg bg-surface-800/50 border border-surface-700/40 gap-3">
            <div>
              <p className="text-sm text-white">Interview transcripts</p>
              <p className="text-xs text-surface-500">Export all Q&A from mock interviews as JSON</p>
            </div>
            <button
              type="button"
              disabled={gdprBusy === 'export'}
              onClick={async () => {
                setGdprBusy('export')
                try {
                  const blob = await interviewsApi.exportTranscripts(true)
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = 'fixitlab-interview-transcripts.json'
                  a.click()
                  URL.revokeObjectURL(url)
                  toast.success('Transcripts exported')
                } catch {
                  toast.error('Export failed')
                } finally {
                  setGdprBusy(null)
                }
              }}
              className="btn-secondary text-xs px-3 py-1.5 flex items-center gap-1 shrink-0"
            >
              <Download size={12} /> Export JSON
            </button>
          </div>
        </div>
      </div>

      {/* Subscriptions shortcut */}
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white mb-2 flex items-center gap-2">
          <CreditCard size={18} className="text-accent-cyan" /> Subscriptions & Billing
        </h2>
        <p className="text-sm text-surface-400 mb-4">
          View technology and interview subscriptions, expiry dates, payment history, coupons, and invoices.
        </p>
        <Link to="/subscriptions" className="btn-primary text-sm inline-flex items-center gap-2">
          <CreditCard size={14} /> Open subscriptions
        </Link>
      </div>

      {/* Plan & Usage (labs only) */}
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Zap size={18} className="text-accent-purple" /> Daily Lab Usage
        </h2>
        {planInfo ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-white font-semibold text-lg">{planInfo.plan.name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    planInfo.plan.code === 'free'
                      ? 'bg-surface-700 text-surface-300'
                      : planInfo.plan.code === 'pro'
                      ? 'bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20'
                      : 'bg-accent-purple/10 text-accent-purple border border-accent-purple/20'
                  }`}>
                    {planInfo.plan.code === 'free' ? 'Current Plan' : 'Active'}
                  </span>
                </div>
                <p className="text-xs text-surface-500 mt-0.5">
                  {planInfo.plan.code === 'free' ? 'Limited access' : 'Full access to all features'}
                </p>
              </div>
              {planInfo.plan.code === 'free' && (
                <Link to="/pricing" className="btn-primary text-sm px-4 py-2 flex items-center gap-1.5">
                  <Zap size={14} /> Upgrade
                </Link>
              )}
            </div>

            <div className="border-t border-surface-800 pt-4">
              <h3 className="text-xs font-semibold text-surface-400 uppercase tracking-wider mb-3">Today's Usage</h3>
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className="text-surface-300">Labs Used</span>
                    <span className="text-white font-medium">
                      {planInfo.usage.labs_today}
                      <span className="text-surface-500">
                        {' '}/ {planInfo.plan.max_labs_per_day >= 999 ? '∞' : planInfo.plan.max_labs_per_day}
                      </span>
                    </span>
                  </div>
                  <div className="w-full h-2 bg-surface-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        planInfo.usage.labs_remaining === 0
                          ? 'bg-accent-red'
                          : planInfo.usage.labs_remaining <= 1
                          ? 'bg-accent-amber'
                          : 'bg-accent-green'
                      }`}
                      style={{
                        width: `${Math.min(100, (planInfo.usage.labs_today / Math.min(planInfo.plan.max_labs_per_day, 10)) * 100)}%`
                      }}
                    />
                  </div>
                  {planInfo.usage.labs_remaining === 0 && (
                    <p className="text-xs text-accent-red mt-1.5 flex items-center gap-1">
                      <Zap size={10} /> Limit reached — resets at midnight UTC
                    </p>
                  )}
                </div>
              </div>
            </div>

            <div className="border-t border-surface-800 pt-4 grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-surface-400">Labs per Day</span>
                <p className="text-white font-medium mt-0.5">
                  {planInfo.plan.max_labs_per_day >= 999 ? 'Unlimited' : planInfo.plan.max_labs_per_day}
                </p>
              </div>
              <div>
                <span className="text-surface-400">Time per Lab</span>
                <p className="text-white font-medium mt-0.5">{planInfo.plan.max_lab_duration_minutes} minutes</p>
              </div>
            </div>

            {planInfo.plan.code === 'free' && (
              <div className="bg-accent-cyan/5 border border-accent-cyan/10 rounded-lg p-4 mt-2">
                <div className="flex items-start gap-3">
                  <ArrowUpRight size={18} className="text-accent-cyan mt-0.5 shrink-0" />
                  <div>
                    <p className="text-sm text-white font-medium">Want unlimited access?</p>
                    <p className="text-xs text-surface-400 mt-0.5">
                      Upgrade to Pro for unlimited challenges, longer time limits, and all technologies.
                    </p>
                    <Link to="/pricing" className="text-xs text-accent-cyan hover:underline mt-2 inline-block font-medium">
                      View plans →
                    </Link>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-4 text-surface-500 text-sm">
            <p>Unable to load plan info</p>
          </div>
        )}
      </div>

      {/* Delete account */}
      <div id="delete-account" className="glass-card p-6 border border-accent-red/20">
        <h2 className="text-lg font-semibold text-white mb-2 flex items-center gap-2">
          <AlertTriangle size={18} className="text-accent-red" /> Delete account
        </h2>
        <p className="text-sm text-surface-400 mb-4">
          Permanently delete your account and all data (labs, interviews, subscriptions metadata, profile).
          This cannot be undone. You may create a new account later.
        </p>
        <div className="space-y-3 max-w-md">
          <div>
            <label className="text-xs text-surface-400 block mb-1.5">
              Type <span className="text-accent-red font-mono">DELETE MY ACCOUNT</span> to confirm
            </label>
            <input
              type="text"
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
              className="input-field w-full text-sm"
              placeholder="DELETE MY ACCOUNT"
              autoComplete="off"
            />
          </div>
          {hasUsablePassword && (
            <div>
              <label className="text-xs text-surface-400 block mb-1.5">Current password</label>
              <input
                type="password"
                value={deletePassword}
                onChange={(e) => setDeletePassword(e.target.value)}
                className="input-field w-full text-sm"
                autoComplete="current-password"
              />
            </div>
          )}
          <button
            type="button"
            disabled={deletingAccount || deleteConfirm !== 'DELETE MY ACCOUNT'}
            onClick={async () => {
              if (!window.confirm('This permanently deletes your account and all data. Continue?')) return
              setDeletingAccount(true)
              try {
                const refresh = useAuthStore.getState().refreshToken
                await authApi.deleteAccount({
                  confirm: deleteConfirm,
                  password: deletePassword,
                  refresh,
                })
                await authApi.logout()
                toast.success('Account deleted')
                navigate('/')
              } catch (e) {
                toast.error(e.response?.data?.error || 'Could not delete account')
              } finally {
                setDeletingAccount(false)
              }
            }}
            className="btn-secondary text-sm px-4 py-2 border-accent-red/40 text-accent-red hover:bg-accent-red/10 disabled:opacity-40 flex items-center gap-2"
          >
            <Trash2 size={14} />
            {deletingAccount ? 'Deleting…' : 'Permanently delete my account'}
          </button>
        </div>
      </div>
    </div>
  )
}
