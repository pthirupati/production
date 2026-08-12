import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { AdminPageHeader } from '../../components/design'
import { useModalA11y } from '../../components/ConfirmModal'
import { Plus, Edit2, Trash2, X, Save, Cpu, Tag, WrenchIcon, AlertTriangle } from 'lucide-react'
import toast from 'react-hot-toast'

const COLOR_OPTIONS = [
  { value: 'cyan', label: 'Cyan', class: 'bg-accent-cyan' },
  { value: 'green', label: 'Green', class: 'bg-accent-green' },
  { value: 'amber', label: 'Amber', class: 'bg-accent-amber' },
  { value: 'purple', label: 'Purple', class: 'bg-accent-purple' },
  { value: 'red', label: 'Red', class: 'bg-accent-red' },
  { value: 'blue', label: 'Blue', class: 'bg-blue-500' },
]

const EMPTY_FORM = { name: '', slug: '', icon: '', description: '', color: 'cyan', price: 499, is_free: false, order: 0, is_active: true, coming_soon: false }

export default function AdminTechnologies() {
  const [technologies, setTechnologies] = useState([])
  const [tags, setTags] = useState([])
  const [tagsFailed, setTagsFailed] = useState(false)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [activeTab, setActiveTab] = useState('technologies')
  const [form, setForm] = useState(EMPTY_FORM)
  const [tagForm, setTagForm] = useState({ name: '' })
  const [showTagForm, setShowTagForm] = useState(false)
  const [editingTagId, setEditingTagId] = useState(null)

  // Force-delete modal state
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteConfirmName, setDeleteConfirmName] = useState('')
  const [deleteLoading, setDeleteLoading] = useState(false)

  // Maintenance panel state
  const [maintenanceTech, setMaintenanceTech] = useState(null)
  const [maintenanceForm, setMaintenanceForm] = useState({ enabled: false, message: '', scheduled_start: '', scheduled_end: '' })
  const [maintenanceLoading, setMaintenanceLoading] = useState(false)

  const closeForm = () => setShowForm(false)
  const closeDelete = () => { setDeleteTarget(null); setDeleteConfirmName('') }
  const closeMaintenance = () => setMaintenanceTech(null)
  const closeTagForm = () => setShowTagForm(false)
  const formDialogRef = useModalA11y(showForm, closeForm)
  const deleteDialogRef = useModalA11y(!!deleteTarget, closeDelete)
  const maintenanceDialogRef = useModalA11y(!!maintenanceTech, closeMaintenance)
  const tagDialogRef = useModalA11y(showTagForm, closeTagForm)

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [tSettled, tgSettled] = await Promise.allSettled([
        adminApi.getTechnologies(),
        adminApi.getTags(),
      ])
      if (tSettled.status === 'fulfilled') setTechnologies(tSettled.value)
      else console.error(tSettled.reason)
      if (tgSettled.status === 'fulfilled') {
        setTags(tgSettled.value || [])
        setTagsFailed(false)
      } else {
        setTags([])
        setTagsFailed(true)
      }
    } catch { console.error } finally { setLoading(false) }
  }

  // Technology CRUD
  const handleSave = async () => {
    try {
      if (editingId) {
        await adminApi.updateTechnology(editingId, form)
        toast.success('Technology updated')
      } else {
        await adminApi.createTechnology(form)
        toast.success('Technology created')
      }
      setShowForm(false); setEditingId(null)
      setForm(EMPTY_FORM)
      loadData()
    } catch (err) { toast.error(err.response?.data?.name?.[0] || 'Save failed') }
  }

  const handleEdit = (tech) => {
    setForm({ name: tech.name, slug: tech.slug || '', icon: tech.icon, description: tech.description, color: tech.color || 'cyan', price: tech.is_free ? 0 : (tech.price || 499), is_free: tech.is_free || false, order: tech.order || 0, is_active: tech.is_active, coming_soon: tech.coming_soon || false })
    setEditingId(tech.id); setShowForm(true)
  }

  const handleDelete = async (tech) => {
    setDeleteTarget(tech)
    setDeleteConfirmName('')
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    setDeleteLoading(true)
    try {
      const count = deleteTarget.scenario_count ?? deleteTarget.active_scenarios ?? 0
      const subCount = deleteTarget.subscriber_count || 0
      const payload = { cascade: count > 0 }
      if (subCount > 0) {
        payload.force = true
        payload.confirm_name = deleteConfirmName
      }
      const res = await adminApi.deleteTechnology(deleteTarget.id, payload)
      toast.success(res.scenarios_deleted
        ? `Deleted ${deleteTarget.name} and ${res.scenarios_deleted} scenario(s)`
        : 'Technology deleted')
      setDeleteTarget(null)
      setDeleteConfirmName('')
      loadData()
    } catch (err) {
      const errData = err.response?.data
      if (errData?.error === 'subscribers_active') {
        // Backend told us about subscribers — already showing the right modal
        toast.error(errData.message || 'Active subscribers exist')
      } else {
        toast.error(errData?.error || 'Cannot delete')
      }
    } finally { setDeleteLoading(false) }
  }

  const openMaintenance = async (tech) => {
    setMaintenanceTech(tech)
    try {
      const data = await adminApi.getTechMaintenance(tech.id)
      setMaintenanceForm({
        enabled: data.maintenance_enabled || false,
        message: data.maintenance_message || '',
        scheduled_start: data.maintenance_scheduled_start ? data.maintenance_scheduled_start.slice(0, 16) : '',
        scheduled_end: data.maintenance_scheduled_end ? data.maintenance_scheduled_end.slice(0, 16) : '',
      })
    } catch { setMaintenanceForm({ enabled: tech.maintenance_enabled || false, message: '', scheduled_start: '', scheduled_end: '' }) }
  }

  const saveMaintenance = async () => {
    if (!maintenanceTech) return
    setMaintenanceLoading(true)
    try {
      await adminApi.setTechMaintenance(maintenanceTech.id, {
        enabled: maintenanceForm.enabled,
        message: maintenanceForm.message,
        scheduled_start: maintenanceForm.scheduled_start || null,
        scheduled_end: maintenanceForm.scheduled_end || null,
      })
      toast.success(maintenanceForm.enabled ? 'Maintenance enabled — subscribers notified' : 'Maintenance disabled')
      setMaintenanceTech(null)
      loadData()
    } catch { toast.error('Failed to save maintenance settings') } finally { setMaintenanceLoading(false) }
  }

  // Tag CRUD
  const handleSaveTag = async () => {
    try {
      if (editingTagId) {
        await adminApi.updateTag(editingTagId, tagForm)
        toast.success('Tag updated')
      } else {
        await adminApi.createTag(tagForm)
        toast.success('Tag created')
      }
      setShowTagForm(false); setEditingTagId(null); setTagForm({ name: '' }); loadData()
    } catch (err) { toast.error(err.response?.data?.name?.[0] || 'Save failed') }
  }

  const handleDeleteTag = async (id) => {
    if (!confirm('Delete this tag?')) return
    try { await adminApi.deleteTag(id); toast.success('Deleted'); loadData() }
    catch { toast.error('Cannot delete') }
  }

  // Determine if we need name confirmation for delete
  const needsNameConfirm = deleteTarget && (deleteTarget.subscriber_count || 0) > 0
  const canConfirmDelete = !needsNameConfirm || deleteConfirmName === deleteTarget?.name

  return (
    <div className="space-y-6 animate-fade-in">
      <AdminPageHeader
        title="Technologies & Tags"
        subtitle="Manage technology categories, maintenance, and scenario tags"
      />

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-800/50 rounded-lg p-1 w-fit">
        {[{ key: 'technologies', label: 'Technologies', icon: Cpu }, { key: 'tags', label: 'Tags', icon: Tag }].map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setActiveTab(key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === key ? 'bg-surface-700 text-white' : 'text-surface-400 hover:text-white'
            }`}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {/* Technologies tab */}
      {activeTab === 'technologies' && (
        <>
          <div className="flex justify-end">
            <button onClick={() => { setForm(EMPTY_FORM); setEditingId(null); setShowForm(true) }}
              className="btn-primary flex items-center gap-2">
              <Plus size={16} /> Add Technology
            </button>
          </div>

          {/* Add/Edit form modal */}
          {showForm && (
            <div
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center"
              onMouseDown={(e) => { if (e.target === e.currentTarget) closeForm() }}
            >
              <div
                ref={formDialogRef}
                tabIndex={-1}
                role="dialog"
                aria-modal="true"
                aria-label={editingId ? 'Edit Technology' : 'New Technology'}
                className="glass-card p-6 w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto outline-none"
              >
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-lg font-semibold text-white">{editingId ? 'Edit Technology' : 'New Technology'}</h2>
                  <button type="button" onClick={closeForm} aria-label="Close technology form" className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-surface-500 hover:text-white"><X size={20} /></button>
                </div>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Name</label>
                      <input value={form.name} onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} className="input-field" placeholder="Linux" />
                    </div>
                    <div>
                      <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Slug</label>
                      <input value={form.slug} onChange={(e) => setForm(f => ({ ...f, slug: e.target.value }))} className="input-field" placeholder="linux" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Icon</label>
                    <input value={form.icon} onChange={(e) => setForm(f => ({ ...f, icon: e.target.value }))} className="input-field" />
                  </div>
                  <div>
                    <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Description</label>
                    <textarea value={form.description} onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))} className="input-field h-20 resize-y" />
                  </div>
                  <div>
                    <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Price (INR)</label>
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500">₹</span>
                      <input type="number" min="0" step="1" value={form.price} disabled={form.is_free}
                        onChange={(e) => setForm(f => ({ ...f, price: Number(e.target.value) }))}
                        className="input-field pl-7 disabled:opacity-50 disabled:cursor-not-allowed" placeholder="499" />
                    </div>
                    {form.is_free && <p className="text-[11px] text-accent-green mt-1">Free — no subscription required</p>}
                  </div>
                  <label className="flex items-center justify-between p-3 rounded-xl bg-surface-800/60 border border-surface-700/40 cursor-pointer">
                    <div>
                      <p className="text-sm font-medium text-white">Make technology free</p>
                      <p className="text-xs text-surface-500 mt-0.5">All labs in this technology open to everyone (forces price to ₹0)</p>
                    </div>
                    <div className={`relative w-11 h-6 rounded-full transition-all ${form.is_free ? 'bg-accent-green' : 'bg-surface-700'}`}
                      onClick={() => setForm(f => ({ ...f, is_free: !f.is_free, price: !f.is_free ? 0 : (f.price || 499) }))}>
                      <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all ${form.is_free ? 'left-5' : 'left-0.5'}`} />
                    </div>
                  </label>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Color</label>
                      <div className="flex gap-2">
                        {COLOR_OPTIONS.map(c => (
                          <button key={c.value} type="button" onClick={() => setForm(f => ({ ...f, color: c.value }))}
                            className={`w-8 h-8 rounded-lg ${c.class} ${form.color === c.value ? 'ring-2 ring-white ring-offset-2 ring-offset-surface-900' : 'opacity-50 hover:opacity-100'} transition-all`}
                            title={c.label} />
                        ))}
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Sort Order</label>
                      <input type="number" value={form.order} onChange={(e) => setForm(f => ({ ...f, order: Number(e.target.value) }))} className="input-field" />
                    </div>
                  </div>
                  <label className="flex items-center gap-2 text-sm text-surface-300 cursor-pointer">
                    <input type="checkbox" checked={form.is_active} onChange={(e) => setForm(f => ({ ...f, is_active: e.target.checked }))} /> Active
                  </label>
                  <label className="flex items-center gap-2 text-sm text-surface-300 cursor-pointer">
                    <input type="checkbox" checked={form.coming_soon} onChange={(e) => setForm(f => ({ ...f, coming_soon: e.target.checked }))} /> Coming soon
                  </label>
                </div>
                <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-surface-800">
                  <button type="button" onClick={closeForm} className="btn-secondary">Cancel</button>
                  <button type="button" onClick={handleSave} className="btn-primary flex items-center gap-2"><Save size={16} /> {editingId ? 'Update' : 'Create'}</button>
                </div>
              </div>
            </div>
          )}

          {/* Force-delete confirmation modal */}
          {deleteTarget && (
            <div
              className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center"
              onMouseDown={(e) => { if (e.target === e.currentTarget) closeDelete() }}
            >
              <div
                ref={deleteDialogRef}
                tabIndex={-1}
                role="dialog"
                aria-modal="true"
                aria-label="Delete Technology"
                className="glass-card p-6 w-full max-w-md mx-4 border border-accent-red/30 outline-none"
              >                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-xl bg-accent-red/10 flex items-center justify-center flex-shrink-0">
                    <AlertTriangle size={20} className="text-accent-red" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold text-white">Delete Technology</h2>
                    <p className="text-xs text-surface-400">This action cannot be undone</p>
                  </div>
                </div>

                {needsNameConfirm ? (
                  <>
                    <div className="bg-accent-red/5 border border-accent-red/20 rounded-xl p-4 mb-4">
                      <p className="text-sm text-accent-red font-medium mb-1">
                        {deleteTarget.subscriber_count} active subscriber(s) will lose access immediately.
                      </p>
                      <p className="text-xs text-surface-400">All scenarios under this technology will also be deleted.</p>
                    </div>
                    <p className="text-sm text-surface-300 mb-3">
                      Type <span className="font-mono font-bold text-white bg-surface-700 px-1.5 py-0.5 rounded">{deleteTarget.name}</span> to confirm:
                    </p>
                    <input
                      type="text"
                      value={deleteConfirmName}
                      onChange={e => setDeleteConfirmName(e.target.value)}
                      placeholder={deleteTarget.name}
                      className="input-field w-full mb-4 font-mono"
                      autoFocus
                    />
                  </>
                ) : (
                  <p className="text-sm text-surface-300 mb-4">
                    Delete <span className="font-semibold text-white">"{deleteTarget.name}"</span>
                    {(deleteTarget.scenario_count || 0) > 0 && (
                      <> and all {deleteTarget.scenario_count} scenario(s)</>
                    )}?
                  </p>
                )}

                <div className="flex justify-end gap-3">
                  <button type="button" onClick={closeDelete} className="btn-secondary" disabled={deleteLoading}>Cancel</button>
                  <button
                    type="button"
                    onClick={confirmDelete}
                    disabled={!canConfirmDelete || deleteLoading}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-red/90 hover:bg-accent-red text-white text-sm font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <Trash2 size={14} /> {deleteLoading ? 'Deleting…' : 'Delete'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Maintenance panel modal */}
          {maintenanceTech && (
            <div
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center"
              onMouseDown={(e) => { if (e.target === e.currentTarget) closeMaintenance() }}
            >
              <div
                ref={maintenanceDialogRef}
                tabIndex={-1}
                role="dialog"
                aria-modal="true"
                aria-label={`${maintenanceTech.name} — Maintenance`}
                className="glass-card p-6 w-full max-w-lg mx-4 border border-amber-500/20 outline-none"
              >
                <div className="flex items-center justify-between mb-5">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-amber-500/10 flex items-center justify-center">
                      <WrenchIcon size={18} className="text-amber-400" />
                    </div>
                    <div>
                      <h2 className="text-base font-semibold text-white">{maintenanceTech.name} — Maintenance</h2>
                      <p className="text-xs text-surface-400">Subscribers will be emailed when maintenance is toggled on</p>
                    </div>
                  </div>
                  <button type="button" onClick={closeMaintenance} aria-label="Close maintenance panel" className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-surface-500 hover:text-white"><X size={20} /></button>
                </div>

                <div className="space-y-4">
                  <label className="flex items-center justify-between p-3 rounded-xl bg-surface-800/60 border border-surface-700/40 cursor-pointer">
                    <div>
                      <p className="text-sm font-medium text-white">Enable Maintenance Mode</p>
                      <p className="text-xs text-surface-500 mt-0.5">Blocks labs and shows message to users</p>
                    </div>
                    <div className={`relative w-11 h-6 rounded-full transition-all ${maintenanceForm.enabled ? 'bg-amber-500' : 'bg-surface-700'}`}
                      onClick={() => setMaintenanceForm(f => ({ ...f, enabled: !f.enabled }))}>
                      <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all ${maintenanceForm.enabled ? 'left-5' : 'left-0.5'}`} />
                    </div>
                  </label>

                  <div>
                    <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Maintenance Message</label>
                    <textarea
                      value={maintenanceForm.message}
                      onChange={e => setMaintenanceForm(f => ({ ...f, message: e.target.value }))}
                      className="input-field h-20 resize-y"
                      placeholder="e.g. Scheduled maintenance for database upgrades. Expected downtime: 2 hours."
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Scheduled Start</label>
                      <input type="datetime-local" value={maintenanceForm.scheduled_start} onChange={e => setMaintenanceForm(f => ({ ...f, scheduled_start: e.target.value }))} className="input-field" />
                    </div>
                    <div>
                      <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Scheduled End</label>
                      <input type="datetime-local" value={maintenanceForm.scheduled_end} onChange={e => setMaintenanceForm(f => ({ ...f, scheduled_end: e.target.value }))} className="input-field" />
                    </div>
                  </div>
                </div>

                <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-surface-800">
                  <button onClick={() => setMaintenanceTech(null)} className="btn-secondary">Cancel</button>
                  <button onClick={saveMaintenance} disabled={maintenanceLoading} className="btn-primary flex items-center gap-2">
                    <Save size={16} /> {maintenanceLoading ? 'Saving…' : 'Save'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center h-40">
              <div className="w-8 h-8 border-2 border-accent-purple border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {technologies.map((tech) => (
                <div key={tech.id} className={`glass-card-hover p-5 relative ${tech.maintenance_enabled ? 'border-amber-500/30' : ''}`}>
                  {tech.maintenance_enabled && (
                    <div className="absolute top-2 right-2">
                      <span className="flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30">
                        <WrenchIcon size={9} /> Maintenance
                      </span>
                    </div>
                  )}
                  <div className="flex items-start justify-between mb-3">
                    <div className={`w-10 h-10 rounded-xl bg-accent-${tech.color || 'cyan'}/10 flex items-center justify-center`}>
                      <Cpu size={20} className={`text-accent-${tech.color || 'cyan'}`} />
                    </div>
                    <div className="flex gap-1">
                      <button onClick={() => openMaintenance(tech)} className="p-1.5 text-surface-500 hover:text-amber-400" title="Maintenance"><WrenchIcon size={14} /></button>
                      <button onClick={() => handleEdit(tech)} className="p-1.5 text-surface-500 hover:text-accent-cyan" title="Edit"><Edit2 size={14} /></button>
                      <button onClick={() => handleDelete(tech)} className="p-1.5 text-surface-500 hover:text-accent-red" title="Delete"><Trash2 size={14} /></button>
                    </div>
                  </div>
                  <h3 className="text-lg font-semibold text-white">{tech.name}</h3>
                  {tech.slug && <p className="text-xs text-surface-600 font-mono">/{tech.slug}</p>}
                  <p className="text-sm text-surface-400 mt-1 line-clamp-2">{tech.description || 'No description'}</p>
                  <div className="mt-2">
                    {tech.is_free ? (
                      <span className="text-sm font-semibold text-accent-green">Free</span>
                    ) : (
                      <>
                        <span className="text-sm font-semibold text-accent-green">₹{Number(tech.price || 0).toLocaleString('en-IN')}</span>
                        <span className="text-xs text-surface-500 ml-1">/ subscription</span>
                      </>
                    )}
                  </div>
                  <div className="flex items-center justify-between mt-4 pt-3 border-t border-surface-700/50">
                    <span className="text-xs text-surface-500">{tech.scenario_count} scenarios ({tech.active_scenarios} active)</span>
                    <div className="flex gap-1">
                      {tech.coming_soon && (
                        <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400">Coming soon</span>
                      )}
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${tech.is_active ? 'bg-accent-green/10 text-accent-green' : 'bg-surface-700 text-surface-400'}`}>{tech.is_active ? 'Active' : 'Inactive'}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Tags tab */}
      {activeTab === 'tags' && (
        <>
          <div className="flex justify-end">
            <button onClick={() => { setTagForm({ name: '' }); setEditingTagId(null); setShowTagForm(true) }}
              className="btn-primary flex items-center gap-2">
              <Plus size={16} /> Add Tag
            </button>
          </div>

          {showTagForm && (
            <div
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center"
              onMouseDown={(e) => { if (e.target === e.currentTarget) closeTagForm() }}
            >
              <div
                ref={tagDialogRef}
                tabIndex={-1}
                role="dialog"
                aria-modal="true"
                aria-label={editingTagId ? 'Edit Tag' : 'New Tag'}
                className="glass-card p-6 w-full max-w-sm mx-4 outline-none"
              >
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-white">{editingTagId ? 'Edit Tag' : 'New Tag'}</h2>
                  <button type="button" onClick={closeTagForm} aria-label="Close tag form" className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-surface-500 hover:text-white"><X size={20} /></button>
                </div>
                <div>
                  <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Name</label>
                  <input value={tagForm.name} onChange={(e) => setTagForm({ name: e.target.value })} className="input-field" placeholder="systemd, nginx, networking..." />
                </div>
                <div className="flex justify-end gap-3 mt-4">
                  <button type="button" onClick={closeTagForm} className="btn-secondary">Cancel</button>
                  <button type="button" onClick={handleSaveTag} className="btn-primary flex items-center gap-2"><Save size={16} /> {editingTagId ? 'Update' : 'Create'}</button>
                </div>
              </div>
            </div>
          )}

          <div className="glass-card p-6">
            {tagsFailed ? (
              <div className="text-center py-8">
                <Tag size={32} className="text-amber-500/70 mx-auto mb-2" />
                <p className="text-amber-300/90">Couldn&apos;t load tags. Technologies above are still available.</p>
              </div>
            ) : tags.length === 0 ? (
              <div className="text-center py-8">
                <Tag size={32} className="text-surface-700 mx-auto mb-2" />
                <p className="text-surface-500">No tags yet. Add tags to categorize scenarios.</p>
              </div>
            ) : (
              <div className="flex flex-wrap gap-3">
                {tags.map(tag => (
                  <div key={tag.id} className="group flex items-center gap-2 bg-surface-800 rounded-full px-4 py-2 border border-surface-700 hover:border-surface-600 transition-all">
                    <Tag size={12} className="text-accent-cyan" />
                    <span className="text-sm text-surface-200">{tag.name}</span>
                    <span className="text-xs text-surface-600">({tag.scenario_count ?? 0})</span>
                    <div className="hidden group-hover:flex items-center gap-1 ml-1">
                      <button onClick={() => { setTagForm({ name: tag.name }); setEditingTagId(tag.id); setShowTagForm(true) }}
                        className="text-surface-500 hover:text-accent-cyan"><Edit2 size={11} /></button>
                      <button onClick={() => handleDeleteTag(tag.id)}
                        className="text-surface-500 hover:text-accent-red"><Trash2 size={11} /></button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
