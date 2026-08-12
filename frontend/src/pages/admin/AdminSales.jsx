import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { AdminPageHeader } from '../../components/design'
import { useModalA11y } from '../../components/ConfirmModal'
import { X, Save, Building2, Mail, Phone, Users, Tag, ChevronDown } from 'lucide-react'
import toast from 'react-hot-toast'

const STATUSES = [
  { value: 'new', label: 'New', cls: 'bg-blue-500/15 text-blue-400' },
  { value: 'contacted', label: 'Contacted', cls: 'bg-amber-500/15 text-amber-400' },
  { value: 'quoted', label: 'Quoted', cls: 'bg-purple-500/15 text-purple-400' },
  { value: 'won', label: 'Won', cls: 'bg-green-500/15 text-green-400' },
  { value: 'lost', label: 'Lost', cls: 'bg-surface-700 text-surface-400' },
]
const STATUS_MAP = Object.fromEntries(STATUSES.map(s => [s.value, s]))
const CURRENCIES = ['USD', 'INR', 'EUR', 'GBP', 'AUD', 'CAD', 'SGD', 'AED']

export default function AdminSales() {
  const [inquiries, setInquiries] = useState([])
  const [counts, setCounts] = useState({})
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [editing, setEditing] = useState(null) // the inquiry being quoted
  const [form, setForm] = useState({
    status: 'new', custom_quote_amount: '', custom_quote_currency: 'USD',
    custom_quote_notes: '', custom_quote_valid_until: '',
  })
  const [saving, setSaving] = useState(false)

  const closeEdit = () => setEditing(null)
  const editDialogRef = useModalA11y(!!editing, closeEdit)

  useEffect(() => { loadData() }, [filter])

  const loadData = async () => {
    setLoading(true)
    try {
      const data = await adminApi.getSalesInquiries(filter)
      setInquiries(data.inquiries || [])
      setCounts(data.counts || {})
    } catch { toast.error('Failed to load inquiries') }
    finally { setLoading(false) }
  }

  const openEditor = (inq) => {
    setForm({
      status: inq.status,
      custom_quote_amount: inq.custom_quote_amount ?? '',
      custom_quote_currency: inq.custom_quote_currency || 'USD',
      custom_quote_notes: inq.custom_quote_notes || '',
      custom_quote_valid_until: inq.custom_quote_valid_until || '',
    })
    setEditing(inq)
  }

  const quickStatus = async (inq, status) => {
    try {
      await adminApi.updateSalesInquiry(inq.id, { status })
      toast.success(`Marked ${STATUS_MAP[status]?.label || status}`)
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.error || 'Update failed')
    }
  }

  const handleSave = async () => {
    if (!editing) return
    const payload = {
      status: form.status,
      custom_quote_amount: form.custom_quote_amount === '' ? null : form.custom_quote_amount,
      custom_quote_currency: form.custom_quote_currency,
      custom_quote_notes: form.custom_quote_notes,
      custom_quote_valid_until: form.custom_quote_valid_until || null,
    }
    setSaving(true)
    try {
      await adminApi.updateSalesInquiry(editing.id, payload)
      toast.success('Inquiry updated')
      setEditing(null)
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.error || 'Save failed')
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
    <div className="space-y-6 animate-fade-in">
      <AdminPageHeader
        title="Sales Inquiries"
        subtitle="Teams / Org Contact Sales requests — triage and set custom quotes"
      />

      {/* Status filter pills */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setFilter('')}
          className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${filter === '' ? 'border-accent-cyan/50 bg-accent-cyan/10 text-accent-cyan' : 'border-surface-700 text-surface-400 hover:text-surface-200'}`}
        >
          All
        </button>
        {STATUSES.map(s => (
          <button
            key={s.value}
            onClick={() => setFilter(s.value)}
            className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${filter === s.value ? 'border-accent-cyan/50 bg-accent-cyan/10 text-accent-cyan' : 'border-surface-700 text-surface-400 hover:text-surface-200'}`}
          >
            {s.label} {counts[s.value] ? <span className="opacity-70">({counts[s.value]})</span> : null}
          </button>
        ))}
      </div>

      <div className="glass-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="fx-admin-table">
            <thead className="bg-surface-900/50 text-surface-400 text-left">
              <tr>
                <th className="px-4 py-3">Organization</th>
                <th className="px-4 py-3">Contact</th>
                <th className="px-4 py-3">Team size</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Quote</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-800">
              {inquiries.map(inq => {
                const st = STATUS_MAP[inq.status] || STATUSES[0]
                return (
                  <tr key={inq.id} className="hover:bg-surface-800/30 align-top">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-white flex items-center gap-1.5">
                        <Building2 size={14} className="text-surface-500" /> {inq.organization}
                      </div>
                      {inq.company && <div className="text-xs text-surface-500 mt-0.5">{inq.company}</div>}
                      <div className="text-[11px] text-surface-600 mt-0.5">{new Date(inq.created_at).toLocaleDateString()}</div>
                    </td>
                    <td className="px-4 py-3 text-surface-300">
                      <div>{inq.full_name}</div>
                      <a href={`mailto:${inq.work_email}`} className="text-xs text-accent-cyan hover:underline flex items-center gap-1 mt-0.5">
                        <Mail size={11} /> {inq.work_email}
                      </a>
                      {inq.phone && (
                        <div className="text-xs text-surface-500 flex items-center gap-1 mt-0.5">
                          <Phone size={11} /> {inq.phone}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-surface-400">
                      <span className="flex items-center gap-1"><Users size={13} /> {inq.team_size || '—'}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded ${st.cls}`}>{st.label}</span>
                    </td>
                    <td className="px-4 py-3 text-surface-300">
                      {inq.custom_quote_amount != null ? (
                        <span className="font-semibold text-accent-green">
                          {inq.custom_quote_currency} {inq.custom_quote_amount}
                        </span>
                      ) : (
                        <span className="text-surface-600">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <div className="inline-flex items-center gap-2">
                        {inq.status === 'new' && (
                          <button onClick={() => quickStatus(inq, 'contacted')} className="text-xs text-surface-400 hover:text-white">
                            Mark contacted
                          </button>
                        )}
                        <button onClick={() => openEditor(inq)} className="btn-secondary text-xs px-3 py-1.5 inline-flex items-center gap-1">
                          <Tag size={13} /> Quote
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
              {inquiries.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-10 text-center text-surface-500">No inquiries yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quote / status editor modal */}
      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={closeEdit} />
          <div
            ref={editDialogRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-label={`Edit inquiry ${editing.organization}`}
            className="relative w-full max-w-lg glass-card p-6 space-y-4 max-h-[90vh] overflow-y-auto outline-none"
          >
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-white">{editing.organization}</h2>
                <p className="text-xs text-surface-500">{editing.full_name} &middot; {editing.work_email}</p>
              </div>
              <button type="button" onClick={closeEdit} aria-label="Close inquiry editor" className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-surface-400 hover:text-white"><X size={18} /></button>
            </div>

            {editing.message && (
              <div className="bg-surface-900/60 border border-surface-800 rounded-lg p-3">
                <p className="text-xs text-surface-500 mb-1">Their message</p>
                <p className="text-sm text-surface-300 whitespace-pre-wrap">{editing.message}</p>
              </div>
            )}

            <div>
              <label className="text-xs text-surface-400">Status</label>
              <div className="relative mt-1">
                <select
                  className="input-field w-full appearance-none pr-8"
                  value={form.status}
                  onChange={e => setForm(f => ({ ...f, status: e.target.value }))}
                >
                  {STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
                <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-1">
                <label className="text-xs text-surface-400">Currency</label>
                <select
                  className="input-field w-full mt-1"
                  value={form.custom_quote_currency}
                  onChange={e => setForm(f => ({ ...f, custom_quote_currency: e.target.value }))}
                >
                  {CURRENCIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs text-surface-400">Quote amount (blank = none)</label>
                <input
                  type="number" min="0" step="0.01"
                  className="input-field w-full mt-1"
                  placeholder="e.g. 4999"
                  value={form.custom_quote_amount}
                  onChange={e => setForm(f => ({ ...f, custom_quote_amount: e.target.value }))}
                />
              </div>
            </div>

            <div>
              <label className="text-xs text-surface-400">Valid until</label>
              <input
                type="date"
                className="input-field w-full mt-1"
                value={form.custom_quote_valid_until}
                onChange={e => setForm(f => ({ ...f, custom_quote_valid_until: e.target.value }))}
              />
            </div>

            <div>
              <label className="text-xs text-surface-400">Quote notes</label>
              <textarea
                className="input-field w-full mt-1 h-24 resize-none"
                placeholder="What's included, seats, terms…"
                value={form.custom_quote_notes}
                onChange={e => setForm(f => ({ ...f, custom_quote_notes: e.target.value }))}
              />
            </div>

            <div className="flex items-center justify-between pt-2">
              <a href={`mailto:${editing.work_email}`} className="text-xs text-accent-cyan hover:underline inline-flex items-center gap-1">
                <Mail size={12} /> Email this contact
              </a>
              <button onClick={handleSave} disabled={saving} className="btn-primary flex items-center gap-2 disabled:opacity-50">
                <Save size={16} /> {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
