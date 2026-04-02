import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { Plus, Edit2, Trash2, X, Save, Cpu, Tag } from 'lucide-react'
import toast from 'react-hot-toast'

const COLOR_OPTIONS = [
  { value: 'cyan', label: 'Cyan', class: 'bg-accent-cyan' },
  { value: 'green', label: 'Green', class: 'bg-accent-green' },
  { value: 'amber', label: 'Amber', class: 'bg-accent-amber' },
  { value: 'purple', label: 'Purple', class: 'bg-accent-purple' },
  { value: 'red', label: 'Red', class: 'bg-accent-red' },
  { value: 'blue', label: 'Blue', class: 'bg-blue-500' },
]

export default function AdminTechnologies() {
  const [technologies, setTechnologies] = useState([])
  const [tags, setTags] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [activeTab, setActiveTab] = useState('technologies') // technologies | tags
  const [form, setForm] = useState({ name: '', slug: '', icon: '', description: '', color: 'cyan', price: 499, order: 0, is_active: true })
  const [tagForm, setTagForm] = useState({ name: '' })
  const [showTagForm, setShowTagForm] = useState(false)
  const [editingTagId, setEditingTagId] = useState(null)

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [t, tg] = await Promise.all([
        adminApi.getTechnologies(),
        adminApi.getTags().catch(() => []),
      ])
      setTechnologies(t)
      setTags(tg)
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
      setForm({ name: '', slug: '', icon: '', description: '', color: 'cyan', price: 499, order: 0, is_active: true })
      loadData()
    } catch (err) { toast.error(err.response?.data?.name?.[0] || 'Save failed') }
  }

  const handleEdit = (tech) => {
    setForm({ name: tech.name, slug: tech.slug || '', icon: tech.icon, description: tech.description, color: tech.color || 'cyan', price: tech.price || 499, order: tech.order || 0, is_active: tech.is_active })
    setEditingId(tech.id); setShowForm(true)
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this technology? This only works if it has no scenarios.')) return
    try { await adminApi.deleteTechnology(id); toast.success('Deleted'); loadData() }
    catch (err) { toast.error(err.response?.data?.error || 'Cannot delete') }
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
    catch (err) { toast.error('Cannot delete') }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Technologies & Tags</h1>
          <p className="text-surface-400 mt-1">Manage technology categories and scenario tags</p>
        </div>
      </div>

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
            <button onClick={() => { setForm({ name: '', slug: '', icon: '', description: '', color: 'cyan', price: 499, order: 0, is_active: true }); setEditingId(null); setShowForm(true) }}
              className="btn-primary flex items-center gap-2">
              <Plus size={16} /> Add Technology
            </button>
          </div>

          {showForm && (
            <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center">
              <div className="glass-card p-6 w-full max-w-lg mx-4">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-lg font-semibold text-white">{editingId ? 'Edit Technology' : 'New Technology'}</h2>
                  <button onClick={() => setShowForm(false)} className="text-surface-500 hover:text-white"><X size={20} /></button>
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
                    <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Icon URL</label>
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
                      <input type="number" min="0" step="1" value={form.price} onChange={(e) => setForm(f => ({ ...f, price: Number(e.target.value) }))} className="input-field pl-7" placeholder="499" />
                    </div>
                  </div>
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
                </div>
                <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-surface-800">
                  <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
                  <button onClick={handleSave} className="btn-primary flex items-center gap-2"><Save size={16} /> {editingId ? 'Update' : 'Create'}</button>
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
                <div key={tech.id} className="glass-card-hover p-5">
                  <div className="flex items-start justify-between mb-3">
                    <div className={`w-10 h-10 rounded-xl bg-accent-${tech.color || 'cyan'}/10 flex items-center justify-center`}>
                      <Cpu size={20} className={`text-accent-${tech.color || 'cyan'}`} />
                    </div>
                    <div className="flex gap-1">
                      <button onClick={() => handleEdit(tech)} className="p-1.5 text-surface-500 hover:text-accent-cyan"><Edit2 size={14} /></button>
                      <button onClick={() => handleDelete(tech.id)} className="p-1.5 text-surface-500 hover:text-accent-red"><Trash2 size={14} /></button>
                    </div>
                  </div>
                  <h3 className="text-lg font-semibold text-white">{tech.name}</h3>
                  {tech.slug && <p className="text-xs text-surface-600 font-mono">/{tech.slug}</p>}
                  <p className="text-sm text-surface-400 mt-1 line-clamp-2">{tech.description || 'No description'}</p>
                  <div className="mt-2">
                    <span className="text-sm font-semibold text-accent-green">₹{Number(tech.price || 0).toLocaleString('en-IN')}</span>
                    <span className="text-xs text-surface-500 ml-1">/ subscription</span>
                  </div>
                  <div className="flex items-center justify-between mt-4 pt-3 border-t border-surface-700/50">
                    <span className="text-xs text-surface-500">{tech.scenario_count} scenarios ({tech.active_scenarios} active)</span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${tech.is_active ? 'bg-accent-green/10 text-accent-green' : 'bg-surface-700 text-surface-400'}`}>{tech.is_active ? 'Active' : 'Inactive'}</span>
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
            <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center">
              <div className="glass-card p-6 w-full max-w-sm mx-4">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-white">{editingTagId ? 'Edit Tag' : 'New Tag'}</h2>
                  <button onClick={() => setShowTagForm(false)} className="text-surface-500 hover:text-white"><X size={20} /></button>
                </div>
                <div>
                  <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Name</label>
                  <input value={tagForm.name} onChange={(e) => setTagForm({ name: e.target.value })} className="input-field" placeholder="systemd, nginx, networking..." />
                </div>
                <div className="flex justify-end gap-3 mt-4">
                  <button onClick={() => setShowTagForm(false)} className="btn-secondary">Cancel</button>
                  <button onClick={handleSaveTag} className="btn-primary flex items-center gap-2"><Save size={16} /> {editingTagId ? 'Update' : 'Create'}</button>
                </div>
              </div>
            </div>
          )}

          <div className="glass-card p-6">
            {tags.length === 0 ? (
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
