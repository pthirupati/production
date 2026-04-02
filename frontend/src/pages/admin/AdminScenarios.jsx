import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { Plus, Edit2, Trash2, Search, X, Save, Tag, Eye, ShieldAlert } from 'lucide-react'
import toast from 'react-hot-toast'

const SCENARIO_TYPES = [
  { value: 'fix', label: 'Fix the Issue' },
  { value: 'do', label: 'Do the Task' },
  { value: 'hack', label: 'Hack the System' },
]

const INFRA_TYPES = [
  { value: 'docker', label: 'Docker Container' },
  { value: 'aws_ec2', label: 'AWS EC2 Instance' },
  { value: 'digitalocean', label: 'DigitalOcean Droplet' },
]

export default function AdminScenarios() {
  const [scenarios, setScenarios] = useState([])
  const [technologies, setTechnologies] = useState([])
  const [tags, setTags] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [search, setSearch] = useState('')
  const [form, setForm] = useState({
    title: '', slug: '', subtitle: '', description: '', objectives: '',
    initial_state: '', validation_script: '', category: '', difficulty: 'easy',
    technology_id: '', scenario_type: 'fix', infrastructure_type: 'docker',
    cloud_setup_script: '', blocked_commands: [], tag_ids: [], time_limit: 900,
    max_score: 100, is_active: true, is_free: true, solution_explanation: '',
  })
  const [newBlockedCmd, setNewBlockedCmd] = useState('')

  useEffect(() => { loadData() }, [search])

  const loadData = async () => {
    setLoading(true)
    try {
      const [s, t, tg] = await Promise.all([
        adminApi.getScenarios(search ? { search } : {}),
        adminApi.getTechnologies(),
        adminApi.getTags().catch(() => []),
      ])
      setScenarios(s)
      setTechnologies(t)
      setTags(tg)
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  const handleSave = async () => {
    try {
      const payload = {
        ...form,
        objectives: typeof form.objectives === 'string' && form.objectives.includes('\n')
          ? form.objectives.split('\n').filter(Boolean)
          : form.objectives,
        blocked_commands: Array.isArray(form.blocked_commands) ? form.blocked_commands : [],
      }
      if (editingId) {
        await adminApi.updateScenario(editingId, payload)
        toast.success('Scenario updated')
      } else {
        await adminApi.createScenario(payload)
        toast.success('Scenario created')
      }
      setShowForm(false)
      setEditingId(null)
      resetForm()
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.slug?.[0] || 'Save failed')
    }
  }

  const handleEdit = (scenario) => {
    setForm({
      title: scenario.title,
      slug: scenario.slug,
      subtitle: scenario.subtitle || '',
      description: scenario.description,
      objectives: Array.isArray(scenario.objectives) ? scenario.objectives.join('\n') : (scenario.objectives || ''),
      initial_state: scenario.initial_state || '',
      validation_script: scenario.validation_script || '',
      category: scenario.category,
      difficulty: scenario.difficulty,
      technology_id: scenario.technology?.id || '',
      scenario_type: scenario.scenario_type || 'fix',
      infrastructure_type: scenario.infrastructure_type || 'docker',
      cloud_setup_script: scenario.cloud_setup_script || '',
      blocked_commands: Array.isArray(scenario.blocked_commands) ? scenario.blocked_commands : [],
      tag_ids: scenario.tags?.map(t => t.id) || [],
      time_limit: scenario.time_limit || 900,
      max_score: scenario.max_score || 100,
      is_active: scenario.is_active,
      is_free: scenario.is_free ?? true,
      solution_explanation: scenario.solution_explanation || '',
    })
    setEditingId(scenario.id)
    setShowForm(true)
  }

  const handleDelete = async (id) => {
    if (!confirm('Deactivate this scenario?')) return
    try {
      await adminApi.deleteScenario(id)
      toast.success('Scenario deactivated')
      loadData()
    } catch { toast.error('Delete failed') }
  }

  const resetForm = () => {
    setForm({
      title: '', slug: '', subtitle: '', description: '', objectives: '',
      initial_state: '', validation_script: '', category: '', difficulty: 'easy',
      technology_id: '', scenario_type: 'fix', infrastructure_type: 'docker',
      cloud_setup_script: '', blocked_commands: [], tag_ids: [], time_limit: 900,
      max_score: 100, is_active: true, is_free: true, solution_explanation: '',
    })
    setNewBlockedCmd('')
  }

  const toggleTag = (tagId) => {
    setForm(f => ({
      ...f,
      tag_ids: f.tag_ids.includes(tagId) ? f.tag_ids.filter(id => id !== tagId) : [...f.tag_ids, tagId],
    }))
  }

  const typeLabel = (t) => SCENARIO_TYPES.find(s => s.value === t)?.label || t

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Scenarios</h1>
          <p className="text-surface-400 mt-1">Manage challenge scenarios</p>
        </div>
        <button onClick={() => { resetForm(); setEditingId(null); setShowForm(true) }}
          className="btn-primary flex items-center gap-2">
          <Plus size={16} /> Add Scenario
        </button>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
        <input type="text" placeholder="Search scenarios..." value={search}
          onChange={(e) => setSearch(e.target.value)} className="input-field pl-10" />
      </div>

      {/* Form Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-start justify-center pt-10 overflow-y-auto">
          <div className="glass-card p-6 w-full max-w-3xl mx-4 mb-8">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-white">
                {editingId ? 'Edit Scenario' : 'New Scenario'}
              </h2>
              <button onClick={() => setShowForm(false)} className="text-surface-500 hover:text-white">
                <X size={20} />
              </button>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2">
                <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Title</label>
                <input value={form.title} onChange={(e) => setForm(f => ({ ...f, title: e.target.value }))} className="input-field" />
              </div>
              <div>
                <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Slug</label>
                <input value={form.slug} onChange={(e) => setForm(f => ({ ...f, slug: e.target.value }))} className="input-field" placeholder="broken-nginx" />
              </div>
              <div className="col-span-3">
                <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Subtitle</label>
                <input value={form.subtitle} onChange={(e) => setForm(f => ({ ...f, subtitle: e.target.value }))} className="input-field" placeholder="A brief subtitle shown in listings" />
              </div>
              <div>
                <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Technology</label>
                <select value={form.technology_id} onChange={(e) => setForm(f => ({ ...f, technology_id: e.target.value }))} className="input-field">
                  <option value="">Select...</option>
                  {technologies.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Type</label>
                <select value={form.scenario_type} onChange={(e) => setForm(f => ({ ...f, scenario_type: e.target.value }))} className="input-field">
                  {SCENARIO_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Infrastructure</label>
                <select value={form.infrastructure_type} onChange={(e) => setForm(f => ({ ...f, infrastructure_type: e.target.value }))} className="input-field">
                  {INFRA_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Category</label>
                <input value={form.category} onChange={(e) => setForm(f => ({ ...f, category: e.target.value }))} className="input-field" placeholder="Web Server" />
              </div>
              <div>
                <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Difficulty</label>
                <select value={form.difficulty} onChange={(e) => setForm(f => ({ ...f, difficulty: e.target.value }))} className="input-field">
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Time Limit (sec)</label>
                <input type="number" value={form.time_limit} onChange={(e) => setForm(f => ({ ...f, time_limit: Number(e.target.value) }))} className="input-field" />
              </div>
              <div>
                <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Max Score</label>
                <input type="number" value={form.max_score} onChange={(e) => setForm(f => ({ ...f, max_score: Number(e.target.value) }))} className="input-field" />
              </div>

              {/* Tags */}
              {tags.length > 0 && (
                <div className="col-span-3">
                  <label className="block text-xs text-surface-400 mb-2 uppercase tracking-wider">Tags</label>
                  <div className="flex flex-wrap gap-2">
                    {tags.map(tag => (
                      <button key={tag.id} type="button" onClick={() => toggleTag(tag.id)}
                        className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                          form.tag_ids.includes(tag.id)
                            ? 'bg-accent-cyan/20 text-accent-cyan border border-accent-cyan/30'
                            : 'bg-surface-800 text-surface-400 border border-surface-700 hover:border-surface-600'
                        }`}>
                        <Tag size={10} className="inline mr-1" />{tag.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="col-span-3">
                <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Description</label>
                <textarea value={form.description} onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))} className="input-field h-24 resize-y" />
              </div>
              <div className="col-span-3">
                <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Objectives (one per line)</label>
                <textarea value={form.objectives} onChange={(e) => setForm(f => ({ ...f, objectives: e.target.value }))} className="input-field h-20 resize-y" placeholder="Objective 1&#10;Objective 2" />
              </div>
              <div className="col-span-3">
                <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Validation Script (bash)</label>
                <textarea value={form.validation_script} onChange={(e) => setForm(f => ({ ...f, validation_script: e.target.value }))} className="input-field h-20 resize-y font-mono text-sm" placeholder="#!/bin/bash&#10;curl -s http://localhost | grep -q 'Welcome'" />
              </div>
              {form.infrastructure_type !== 'docker' && (
                <div className="col-span-3">
                  <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Cloud Setup Script (bash — creates the broken state on the server)</label>
                  <textarea value={form.cloud_setup_script} onChange={(e) => setForm(f => ({ ...f, cloud_setup_script: e.target.value }))} className="input-field h-24 resize-y font-mono text-sm" placeholder="#!/bin/bash&#10;# Commands to set up the broken state on the cloud instance" />
                </div>
              )}
              <div className="col-span-3">
                <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Solution Explanation (shown after solving)</label>
                <textarea value={form.solution_explanation} onChange={(e) => setForm(f => ({ ...f, solution_explanation: e.target.value }))} className="input-field h-20 resize-y" placeholder="Explain the solution step by step..." />
              </div>

              {/* Blocked Commands */}
              <div className="col-span-3">
                <label className="block text-xs text-surface-400 mb-2 uppercase tracking-wider flex items-center gap-1.5">
                  <ShieldAlert size={12} /> Blocked Commands
                </label>
                <p className="text-xs text-surface-500 mb-2">Commands users cannot run in this scenario. Plain text matches as substring, patterns starting with ^ are treated as regex.</p>
                <div className="flex gap-2 mb-2">
                  <input
                    value={newBlockedCmd}
                    onChange={(e) => setNewBlockedCmd(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && newBlockedCmd.trim()) {
                        e.preventDefault()
                        if (!form.blocked_commands.includes(newBlockedCmd.trim())) {
                          setForm(f => ({ ...f, blocked_commands: [...f.blocked_commands, newBlockedCmd.trim()] }))
                        }
                        setNewBlockedCmd('')
                      }
                    }}
                    className="input-field flex-1 font-mono text-sm"
                    placeholder="e.g. reboot, shutdown, ^rm\s+-rf\s+/"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      if (newBlockedCmd.trim() && !form.blocked_commands.includes(newBlockedCmd.trim())) {
                        setForm(f => ({ ...f, blocked_commands: [...f.blocked_commands, newBlockedCmd.trim()] }))
                        setNewBlockedCmd('')
                      }
                    }}
                    className="btn-secondary px-3 py-2 flex items-center gap-1 text-xs"
                  >
                    <Plus size={14} /> Add
                  </button>
                </div>
                {form.blocked_commands.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {form.blocked_commands.map((cmd, i) => (
                      <span key={i} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 text-xs font-mono">
                        <ShieldAlert size={10} />
                        {cmd}
                        <button type="button" onClick={() => setForm(f => ({ ...f, blocked_commands: f.blocked_commands.filter((_, j) => j !== i) }))}
                          className="ml-0.5 hover:text-red-300 transition-colors">
                          <X size={12} />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
                {form.blocked_commands.length === 0 && (
                  <p className="text-xs text-surface-600 italic">No commands blocked — users can run anything.</p>
                )}
              </div>

              <div className="col-span-3 flex items-center gap-6">
                <label className="flex items-center gap-2 text-sm text-surface-300 cursor-pointer">
                  <input type="checkbox" checked={form.is_active} onChange={(e) => setForm(f => ({ ...f, is_active: e.target.checked }))} className="rounded" />
                  Active
                </label>
                <label className="flex items-center gap-2 text-sm text-surface-300 cursor-pointer">
                  <input type="checkbox" checked={form.is_free} onChange={(e) => setForm(f => ({ ...f, is_free: e.target.checked }))} className="rounded" />
                  Free (no subscription required)
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-surface-800">
              <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
              <button onClick={handleSave} className="btn-primary flex items-center gap-2">
                <Save size={16} /> {editingId ? 'Update' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="glass-card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-40">
            <div className="w-8 h-8 border-2 border-accent-purple border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-700/50 text-left">
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase">Title</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase">Tech</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase">Type</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase">Infra</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase">Difficulty</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase">Status</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase text-right">Attempts</th>
                <th className="px-4 py-3 text-xs font-medium text-surface-400 uppercase text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {scenarios.map((s) => (
                <tr key={s.id} className="border-b border-surface-800/50 hover:bg-surface-800/30 transition-colors">
                  <td className="px-4 py-3">
                    <p className="text-sm font-medium text-white">{s.title}</p>
                    {s.subtitle && <p className="text-xs text-surface-500 mt-0.5">{s.subtitle}</p>}
                  </td>
                  <td className="px-4 py-3 text-sm text-surface-400">{s.technology?.name}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                      s.scenario_type === 'fix' ? 'bg-accent-green/10 text-accent-green' :
                      s.scenario_type === 'hack' ? 'bg-accent-red/10 text-accent-red' :
                      'bg-accent-cyan/10 text-accent-cyan'
                    }`}>{typeLabel(s.scenario_type || 'fix')}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                      s.infrastructure_type === 'aws_ec2' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                      s.infrastructure_type === 'digitalocean' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' :
                      'bg-surface-700 text-surface-400'
                    }`}>{
                      s.infrastructure_type === 'aws_ec2' ? 'EC2' :
                      s.infrastructure_type === 'digitalocean' ? 'DO' : 'Docker'
                    }</span>
                  </td>
                  <td className="px-4 py-3"><span className={`badge-${s.difficulty}`}>{s.difficulty}</span></td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${s.is_active
                      ? 'bg-accent-green/10 text-accent-green border border-accent-green/20'
                      : 'bg-surface-700 text-surface-400'
                    }`}>{s.is_active ? 'Active' : 'Draft'}</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-surface-400 text-right">{s.total_attempts}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => handleEdit(s)} className="p-1.5 text-surface-500 hover:text-accent-cyan transition-colors" title="Edit">
                        <Edit2 size={14} />
                      </button>
                      <button onClick={() => handleDelete(s.id)} className="p-1.5 text-surface-500 hover:text-accent-red transition-colors" title="Deactivate">
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
    </div>
  )
}
