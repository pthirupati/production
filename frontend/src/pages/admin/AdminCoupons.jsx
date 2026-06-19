import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { AdminPageHeader } from '../../components/design'
import { Plus, Edit2, Trash2, X, Save, Tag, Percent } from 'lucide-react'
import toast from 'react-hot-toast'

export default function AdminCoupons() {
  const [coupons, setCoupons] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState({
    code: '', description: '', discount_type: 'percent', discount_value: 20,
    is_active: true, max_uses: '', valid_from: '', valid_until: '',
  })

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const data = await adminApi.getCoupons()
      setCoupons(data.coupons || [])
    } catch { toast.error('Failed to load coupons') }
    finally { setLoading(false) }
  }

  const resetForm = () => {
    setForm({
      code: '', description: '', discount_type: 'percent', discount_value: 20,
      is_active: true, max_uses: '', valid_from: '', valid_until: '',
    })
  }

  const handleSave = async () => {
    if (!form.code.trim()) { toast.error('Code required'); return }
    const payload = {
      ...form,
      max_uses: form.max_uses ? parseInt(form.max_uses, 10) : null,
      valid_from: form.valid_from || null,
      valid_until: form.valid_until || null,
    }
    try {
      if (editingId) {
        await adminApi.updateCoupon(editingId, payload)
        toast.success('Coupon updated')
      } else {
        await adminApi.createCoupon(payload)
        toast.success('Coupon created')
      }
      setShowForm(false)
      setEditingId(null)
      resetForm()
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.error || 'Save failed')
    }
  }

  const handleEdit = (c) => {
    setForm({
      code: c.code,
      description: c.description || '',
      discount_type: c.discount_type,
      discount_value: parseFloat(c.discount_value),
      is_active: c.is_active,
      max_uses: c.max_uses ?? '',
      valid_from: c.valid_from ? c.valid_from.slice(0, 16) : '',
      valid_until: c.valid_until ? c.valid_until.slice(0, 16) : '',
    })
    setEditingId(c.id)
    setShowForm(true)
  }

  const handleToggle = async (c) => {
    try {
      await adminApi.updateCoupon(c.id, { is_active: !c.is_active })
      toast.success(c.is_active ? 'Coupon disabled' : 'Coupon enabled')
      loadData()
    } catch { toast.error('Update failed') }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this coupon?')) return
    try {
      await adminApi.deleteCoupon(id)
      toast.success('Deleted')
      loadData()
    } catch { toast.error('Delete failed') }
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
        title="Coupons"
        subtitle="Create and manage promo codes (e.g. LINUX20)"
        actions={
          <button onClick={() => { resetForm(); setEditingId(null); setShowForm(true) }}
            className="btn-primary flex items-center gap-2">
            <Plus size={16} /> Add Coupon
          </button>
        }
      />

      {showForm && (
        <div className="glass-card p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">{editingId ? 'Edit' : 'New'} Coupon</h2>
            <button onClick={() => { setShowForm(false); setEditingId(null) }} className="text-surface-400 hover:text-white"><X size={18} /></button>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-surface-400">Code</label>
              <input className="input-field w-full mt-1" value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value.toUpperCase() }))} disabled={!!editingId} placeholder="LINUX20" />
            </div>
            <div>
              <label className="text-xs text-surface-400">Description</label>
              <input className="input-field w-full mt-1" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs text-surface-400">Discount type</label>
              <select className="input-field w-full mt-1" value={form.discount_type} onChange={e => setForm(f => ({ ...f, discount_type: e.target.value }))}>
                <option value="percent">Percentage</option>
                <option value="fixed">Fixed INR</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-surface-400">Discount value</label>
              <input type="number" className="input-field w-full mt-1" value={form.discount_value} onChange={e => setForm(f => ({ ...f, discount_value: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs text-surface-400">Max uses (blank = unlimited)</label>
              <input type="number" className="input-field w-full mt-1" value={form.max_uses} onChange={e => setForm(f => ({ ...f, max_uses: e.target.value }))} />
            </div>
            <div className="flex items-center gap-2 pt-6">
              <input type="checkbox" id="coupon-active" checked={form.is_active} onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))} />
              <label htmlFor="coupon-active" className="text-sm text-surface-300">Active</label>
            </div>
          </div>
          <button onClick={handleSave} className="btn-primary flex items-center gap-2"><Save size={16} /> Save</button>
        </div>
      )}

      <div className="glass-card overflow-hidden">
        <table className="fx-admin-table">
          <thead className="bg-surface-900/50 text-surface-400 text-left">
            <tr>
              <th className="px-4 py-3">Code</th>
              <th className="px-4 py-3">Discount</th>
              <th className="px-4 py-3">Uses</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-800">
            {coupons.map(c => (
              <tr key={c.id} className="hover:bg-surface-800/30">
                <td className="px-4 py-3 font-mono text-accent-cyan">{c.code}</td>
                <td className="px-4 py-3 text-surface-300">
                  {c.discount_type === 'percent' ? `${c.discount_value}%` : `₹${c.discount_value}`}
                </td>
                <td className="px-4 py-3 text-surface-400">{c.used_count}{c.max_uses ? ` / ${c.max_uses}` : ''}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded ${c.is_active ? 'bg-green-500/15 text-green-400' : 'bg-surface-700 text-surface-400'}`}>
                    {c.is_active ? 'Active' : 'Disabled'}
                  </span>
                </td>
                <td className="px-4 py-3 text-right space-x-2">
                  <button onClick={() => handleToggle(c)} className="text-xs text-surface-400 hover:text-white">{c.is_active ? 'Disable' : 'Enable'}</button>
                  <button onClick={() => handleEdit(c)} className="text-surface-400 hover:text-accent-cyan"><Edit2 size={14} /></button>
                  <button onClick={() => handleDelete(c.id)} className="text-surface-400 hover:text-red-400"><Trash2 size={14} /></button>
                </td>
              </tr>
            ))}
            {coupons.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-surface-500">No coupons yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
