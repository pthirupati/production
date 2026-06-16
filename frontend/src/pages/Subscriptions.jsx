import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { subscriptionApi } from '../api/subscriptions'
import { interviewsApi } from '../api/interviews'
import {
  CreditCard, Calendar, Mic2, Layers, FileText, Download, RefreshCw,
  AlertTriangle, CheckCircle2, Clock, IndianRupee, Tag,
} from 'lucide-react'
import toast from 'react-hot-toast'
import PageHeader from '../components/PageHeader'

function StatusBadge({ active, expired, subscribed, label }) {
  if (subscribed) {
    return <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Subscribed</span>
  }
  if (expired) {
    return <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-red/10 text-accent-red border border-accent-red/20">Expired</span>
  }
  if (active) {
    return <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-green/10 text-accent-green border border-accent-green/20">{label || 'Active'}</span>
  }
  return <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-700 text-surface-400">Inactive</span>
}

function DaysLeft({ days }) {
  if (days == null) return null
  const urgent = days <= 14
  return (
    <p className={`text-xs flex items-center gap-1 mt-1 ${urgent ? 'text-accent-amber' : 'text-surface-500'}`}>
      <Clock size={10} /> {days} day{days !== 1 ? 's' : ''} left
    </p>
  )
}

export default function Subscriptions() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    subscriptionApi.getSubscriptionsOverview()
      .then(setData)
      .catch(() => toast.error('Could not load subscriptions'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

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
    } catch {
      toast.error('Download failed')
    }
  }

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto space-y-6">
        <SkeletonCard lines={2} />
        <SkeletonCard lines={4} />
      </div>
    )
  }

  const interview = data?.interview_subscription
  const techSubs = data?.technology_subscriptions || []
  const payments = data?.payment_history || []
  const invoices = data?.invoices || []

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-fade-in">
      <PageHeader
        title="My Subscriptions"
        subtitle="Technology access, interview plans, payment history, and invoices in one place."
        icon={CreditCard}
      >
        <button type="button" onClick={load} className="btn-secondary text-sm flex items-center gap-2 whitespace-nowrap">
          <RefreshCw size={14} /> Refresh
        </button>
      </PageHeader>

      {/* Interview subscription */}
      <section className="glass-card p-6 border border-indigo-500/20">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center">
              <Mic2 size={20} className="text-indigo-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">AI Interview Studio</h2>
              <p className="text-xs text-surface-500">1-year plan · interview attempts (full campaigns, not rounds)</p>
            </div>
          </div>
          <StatusBadge
            active={interview?.is_active}
            expired={interview?.expired}
            subscribed={interview?.is_subscribed}
            label={interview?.plan_code === 'free' ? 'Free access' : 'Active'}
          />
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-5">
          <div className="p-3 rounded-lg bg-surface-800/50">
            <p className="text-[10px] text-surface-500 uppercase">Plan</p>
            <p className="text-sm font-medium text-white mt-0.5">{interview?.plan_name || 'Free'}</p>
          </div>
          <div className="p-3 rounded-lg bg-surface-800/50">
            <p className="text-[10px] text-surface-500 uppercase">Attempts left</p>
            <p className="text-sm font-medium text-white mt-0.5">
              {interview?.interviews_remaining ?? 0} / {interview?.interviews_total ?? 0}
            </p>
            <p className="text-[10px] text-surface-600">{interview?.interviews_used ?? 0} used this period</p>
          </div>
          <div className="p-3 rounded-lg bg-surface-800/50">
            <p className="text-[10px] text-surface-500 uppercase">Expires</p>
            <p className="text-sm font-medium text-white mt-0.5">
              {interview?.period_end ? new Date(interview.period_end).toLocaleDateString() : '—'}
            </p>
            <DaysLeft days={interview?.days_remaining} />
          </div>
          <div className="p-3 rounded-lg bg-surface-800/50">
            <p className="text-[10px] text-surface-500 uppercase">Max rounds / attempt</p>
            <p className="text-sm font-medium text-white mt-0.5">{interview?.max_rounds || '—'}</p>
          </div>
        </div>

        {(interview?.renewal_required || interview?.expired) && (
          <div className="mt-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-start gap-2">
            <AlertTriangle size={16} className="text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-amber-200">
                {interview?.expired
                  ? 'Your interview subscription has expired.'
                  : 'You have used all interview attempts for this period.'}
              </p>
              <Link to="/interviews#interview-plans" className="text-xs text-indigo-300 hover:underline mt-1 inline-block">
                Renew subscription →
              </Link>
            </div>
          </div>
        )}

        {interview?.is_active && !interview?.renewal_required && (
          <Link to="/interviews" className="text-xs text-indigo-400 hover:underline mt-4 inline-block">
            Go to Interview Studio →
          </Link>
        )}
      </section>

      {/* Technology subscriptions */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Layers size={18} className="text-accent-cyan" /> Technology Subscriptions
        </h2>
        {techSubs.length === 0 ? (
          <div className="glass-card p-8 text-center border border-dashed border-surface-700">
            <p className="text-surface-400 text-sm">No technology subscriptions yet.</p>
            <Link to="/pricing" className="text-xs text-accent-cyan hover:underline mt-2 inline-block">Browse pricing →</Link>
          </div>
        ) : (
          <div className="space-y-3">
            {techSubs.map(sub => (
              <div key={sub.id} className="glass-card p-4 flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-medium text-white">{sub.technology}</p>
                    <StatusBadge
                      active={sub.is_active || sub.has_access}
                      expired={sub.is_expired}
                      subscribed={sub.is_active && sub.payment_verified}
                      label={sub.in_grace_period ? 'Grace period' : 'Active'}
                    />
                  </div>
                  <p className="text-xs text-surface-500 font-mono mt-0.5">{sub.subscription_id}</p>
                  <p className="text-xs text-surface-500 mt-1">
                    ₹{sub.amount} · {sub.payment_method || '—'} · Started {new Date(sub.created_at).toLocaleDateString()}
                  </p>
                  {sub.expires_at && (
                    <p className="text-xs text-surface-500">
                      Expires {new Date(sub.expires_at).toLocaleDateString()}
                      {sub.days_remaining != null && ` · ${sub.days_remaining} days left`}
                    </p>
                  )}
                </div>
                <Link to={`/technologies/${sub.technology_slug}`} className="text-xs text-accent-cyan hover:underline shrink-0">
                  Open →
                </Link>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Payment history */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <IndianRupee size={18} className="text-accent-green" /> Payment History
        </h2>
        {payments.length === 0 ? (
          <p className="text-sm text-surface-500">No payments recorded yet.</p>
        ) : (
          <div className="glass-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-700 text-left">
                    <th className="p-3 text-surface-400 font-medium">Date</th>
                    <th className="p-3 text-surface-400 font-medium">Product</th>
                    <th className="p-3 text-surface-400 font-medium">Amount</th>
                    <th className="p-3 text-surface-400 font-medium">Coupon</th>
                    <th className="p-3 text-surface-400 font-medium">Method</th>
                  </tr>
                </thead>
                <tbody>
                  {payments.map(p => (
                    <tr key={p.id} className="border-b border-surface-800/50">
                      <td className="p-3 text-xs text-surface-400">{new Date(p.paid_at).toLocaleDateString()}</td>
                      <td className="p-3">
                        <span className={`text-[10px] uppercase mr-1 ${p.product_type === 'interview' ? 'text-indigo-400' : 'text-accent-cyan'}`}>
                          {p.product_type}
                        </span>
                        <span className="text-white">{p.label}</span>
                      </td>
                      <td className="p-3 text-white font-medium">
                        {p.currency === 'INR' ? `₹${p.amount}` : `${p.currency} ${p.amount}`}
                        {p.discount_saved > 0 && (
                          <span className="text-[10px] text-accent-green block">−₹{p.discount_saved} saved</span>
                        )}
                      </td>
                      <td className="p-3 text-xs text-surface-500">{p.coupon_code || '—'}</td>
                      <td className="p-3 text-xs text-surface-500">{p.payment_method}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* Invoices */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <FileText size={18} className="text-accent-purple" /> Invoices
        </h2>
        {invoices.length === 0 ? (
          <p className="text-sm text-surface-500">Invoices appear here after successful payments.</p>
        ) : (
          <div className="space-y-2">
            {invoices.map(inv => (
              <div key={inv.id} className="glass-card p-3 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm text-white truncate">{inv.technology}</p>
                  <p className="text-xs text-surface-500 font-mono">{inv.invoice_number}</p>
                  <p className="text-xs text-surface-500">
                    {new Date(inv.created_at).toLocaleDateString()} · ₹{inv.amount}
                    {inv.product_type === 'interview' && (
                      <span className="ml-1 text-indigo-400">Interview</span>
                    )}
                  </p>
                </div>
                <button type="button" onClick={() => downloadInvoice(inv)} className="btn-secondary text-xs px-3 py-1.5 flex items-center gap-1 shrink-0">
                  <Download size={12} /> HTML
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Platform plan usage */}
      {data?.platform_plan && (
        <section className="glass-card p-5">
          <h2 className="text-sm font-semibold text-white mb-3">Platform plan (labs)</h2>
          <div className="flex items-center justify-between text-sm">
            <span className="text-surface-400">{data.platform_plan.plan?.name} plan</span>
            <span className="text-white">
              {data.platform_plan.usage?.labs_today} / {data.platform_plan.plan?.max_labs_per_day >= 999 ? '∞' : data.platform_plan.plan?.max_labs_per_day} labs today
            </span>
          </div>
          <Link to="/profile" className="text-xs text-surface-500 hover:text-accent-cyan mt-2 inline-block">
            Account settings →
          </Link>
        </section>
      )}
    </div>
  )
}
