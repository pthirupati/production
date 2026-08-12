import { useState, useEffect } from 'react'
import { certAdminApi } from '../../api/certifications'
import { AdminPageHeader } from '../../components/design'
import { useModalA11y } from '../../components/ConfirmModal'
import {
  Edit2, X, Save, Award, WrenchIcon, Layers, ListChecks, ChevronRight, BookOpen,
} from 'lucide-react'
import toast from 'react-hot-toast'

const EMPTY_FORM = {
  name: '', vendor: '', description: '',
  price: 0, addon_price: 0, is_free: true, coming_soon: false, is_active: true,
  passing_score: 70, exam_duration_minutes: 180, validity_months: 36,
  maintenance_enabled: false, maintenance_message: '',
  maintenance_scheduled_start: '', maintenance_scheduled_end: '',
}

export default function AdminCertifications() {
  const [tracks, setTracks] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingTrack, setEditingTrack] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)

  // Scenario drawer state — shows the labs mapped into a track, grouped by objective.
  const [scenarioTrack, setScenarioTrack] = useState(null)
  const [scenarioData, setScenarioData] = useState(null)
  const [scenarioLoading, setScenarioLoading] = useState(false)

  const closeEdit = () => setEditingTrack(null)
  const closeScenarios = () => { setScenarioTrack(null); setScenarioData(null) }
  const editDialogRef = useModalA11y(!!editingTrack, closeEdit)
  const scenarioDialogRef = useModalA11y(!!scenarioTrack, closeScenarios)

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const res = await certAdminApi.getTracks()
      setTracks(res.tracks || [])
    } catch { toast.error('Failed to load certification tracks') }
    finally { setLoading(false) }
  }

  const openEdit = (track) => {
    setEditingTrack(track)
    setForm({
      name: track.name || '',
      vendor: track.vendor || '',
      description: track.description || '',
      price: track.price ?? 0,
      addon_price: track.addon_price ?? 0,
      is_free: track.is_free ?? true,
      coming_soon: track.coming_soon ?? false,
      is_active: track.is_active ?? true,
      passing_score: track.passing_score ?? 70,
      exam_duration_minutes: track.exam_duration_minutes ?? 180,
      validity_months: track.validity_months ?? 36,
      maintenance_enabled: track.maintenance_enabled ?? false,
      maintenance_message: track.maintenance_message || '',
      maintenance_scheduled_start: track.maintenance_scheduled_start ? track.maintenance_scheduled_start.slice(0, 16) : '',
      maintenance_scheduled_end: track.maintenance_scheduled_end ? track.maintenance_scheduled_end.slice(0, 16) : '',
    })
  }

  const handleSave = async () => {
    if (!editingTrack) return
    setSaving(true)
    try {
      const payload = {
        ...form,
        // A free track is, by definition, ₹0.
        price: form.is_free ? 0 : Number(form.price) || 0,
        addon_price: form.is_free ? 0 : Number(form.addon_price) || 0,
        passing_score: Number(form.passing_score) || 0,
        exam_duration_minutes: Number(form.exam_duration_minutes) || 0,
        validity_months: Number(form.validity_months) || 0,
        maintenance_scheduled_start: form.maintenance_scheduled_start || null,
        maintenance_scheduled_end: form.maintenance_scheduled_end || null,
      }
      await certAdminApi.updateTrack(editingTrack.id, payload)
      toast.success('Certification track updated')
      setEditingTrack(null)
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Save failed')
    } finally { setSaving(false) }
  }

  // Quick inline toggles (free / maintenance) straight from the card.
  const quickToggle = async (track, field) => {
    try {
      const payload = { [field]: !track[field] }
      if (field === 'is_free' && !track.is_free) payload.price = 0
      await certAdminApi.updateTrack(track.id, payload)
      toast.success(
        field === 'maintenance_enabled'
          ? (!track.maintenance_enabled ? 'Maintenance enabled' : 'Maintenance disabled')
          : (!track.is_free ? 'Marked free' : 'Marked paid'),
      )
      loadData()
    } catch { toast.error('Update failed') }
  }

  const openScenarios = async (track) => {
    setScenarioTrack(track)
    setScenarioData(null)
    setScenarioLoading(true)
    try {
      const data = await certAdminApi.getTrackScenarios(track.id)
      setScenarioData(data)
    } catch { toast.error('Failed to load scenarios') }
    finally { setScenarioLoading(false) }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <AdminPageHeader
        title="Certifications"
        subtitle="Manage certification tracks the same way as technologies — pricing, free/maintenance toggles, exam settings, and mapped scenarios"
      />

      {/* Edit modal */}
      {editingTrack && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center"
          onMouseDown={(e) => { if (e.target === e.currentTarget) closeEdit() }}
        >
          <div
            ref={editDialogRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-label={`Edit ${editingTrack.code}`}
            className="glass-card p-6 w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto outline-none"
          >
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-semibold text-white">Edit {editingTrack.code}</h2>
                <p className="text-xs text-surface-500 font-mono">/{editingTrack.slug}</p>
              </div>
              <button type="button" onClick={closeEdit} aria-label="Close certification editor" className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-surface-500 hover:text-white"><X size={20} /></button>
            </div>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Name</label>
                  <input value={form.name} onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} className="input-field" />
                </div>
                <div>
                  <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Vendor</label>
                  <input value={form.vendor} onChange={(e) => setForm(f => ({ ...f, vendor: e.target.value }))} className="input-field" placeholder="Red Hat" />
                </div>
              </div>
              <div>
                <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Description</label>
                <textarea value={form.description} onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))} className="input-field h-20 resize-y" />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Standalone price (INR)</label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500">₹</span>
                    <input
                      type="number" min="0" step="1"
                      value={form.price}
                      disabled={form.is_free}
                      onChange={(e) => setForm(f => ({ ...f, price: Number(e.target.value) }))}
                      className="input-field pl-7 disabled:opacity-50"
                      placeholder="0"
                    />
                  </div>
                  <p className="text-[10px] text-surface-500 mt-1">Full cert prep without buying the base technology separately.</p>
                </div>
                <div>
                  <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Addon on technology (INR)</label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500">₹</span>
                    <input
                      type="number" min="0" step="1"
                      value={form.addon_price}
                      disabled={form.is_free}
                      onChange={(e) => setForm(f => ({ ...f, addon_price: Number(e.target.value) }))}
                      className="input-field pl-7 disabled:opacity-50"
                      placeholder="0"
                    />
                  </div>
                  <p className="text-[10px] text-surface-500 mt-1">
                    Added to {editingTrack.technology_name || 'linked technology'} price for learners who already subscribe.
                    {editingTrack.technology_price != null && !form.is_free && (
                      <span className="text-surface-400"> Bundle ≈ ₹{(Number(editingTrack.technology_price) || 0) + (Number(form.addon_price) || 0)}</span>
                    )}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Passing Score (%)</label>
                  <input type="number" min="0" max="100" value={form.passing_score} onChange={(e) => setForm(f => ({ ...f, passing_score: Number(e.target.value) }))} className="input-field" />
                </div>
                <div>
                  <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Exam Duration (min)</label>
                  <input type="number" min="0" value={form.exam_duration_minutes} onChange={(e) => setForm(f => ({ ...f, exam_duration_minutes: Number(e.target.value) }))} className="input-field" />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4">
                <div>
                  <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Certificate validity (months)</label>
                  <input type="number" min="0" value={form.validity_months} onChange={(e) => setForm(f => ({ ...f, validity_months: Number(e.target.value) }))} className="input-field" />
                </div>
              </div>

              <div className="flex flex-wrap gap-4 pt-1">
                <label className="flex items-center gap-2 text-sm text-surface-300 cursor-pointer">
                  <input type="checkbox" checked={form.is_active} onChange={(e) => setForm(f => ({ ...f, is_active: e.target.checked }))} /> Active
                </label>
                <label className="flex items-center gap-2 text-sm text-surface-300 cursor-pointer">
                  <input type="checkbox" checked={form.is_free} onChange={(e) => setForm(f => ({ ...f, is_free: e.target.checked, price: e.target.checked ? 0 : f.price }))} /> Free
                </label>
                <label className="flex items-center gap-2 text-sm text-surface-300 cursor-pointer">
                  <input type="checkbox" checked={form.coming_soon} onChange={(e) => setForm(f => ({ ...f, coming_soon: e.target.checked }))} /> Coming soon
                </label>
              </div>

              {/* Maintenance */}
              <div className="border-t border-surface-800 pt-4 space-y-3">
                <label className="flex items-center justify-between p-3 rounded-xl bg-surface-800/60 border border-surface-700/40 cursor-pointer">
                  <div>
                    <p className="text-sm font-medium text-white flex items-center gap-2"><WrenchIcon size={14} className="text-amber-400" /> Maintenance Mode</p>
                    <p className="text-xs text-surface-500 mt-0.5">Pauses the track for learners and shows a message</p>
                  </div>
                  <div className={`relative w-11 h-6 rounded-full transition-all ${form.maintenance_enabled ? 'bg-amber-500' : 'bg-surface-700'}`}
                    onClick={() => setForm(f => ({ ...f, maintenance_enabled: !f.maintenance_enabled }))}>
                    <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all ${form.maintenance_enabled ? 'left-5' : 'left-0.5'}`} />
                  </div>
                </label>
                {form.maintenance_enabled && (
                  <>
                    <div>
                      <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Maintenance Message</label>
                      <textarea value={form.maintenance_message} onChange={(e) => setForm(f => ({ ...f, maintenance_message: e.target.value }))} className="input-field h-16 resize-y" placeholder="e.g. Exam pool being refreshed — back shortly." />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Scheduled Start</label>
                        <input type="datetime-local" value={form.maintenance_scheduled_start} onChange={(e) => setForm(f => ({ ...f, maintenance_scheduled_start: e.target.value }))} className="input-field" />
                      </div>
                      <div>
                        <label className="block text-xs text-surface-400 mb-1 uppercase tracking-wider">Scheduled End</label>
                        <input type="datetime-local" value={form.maintenance_scheduled_end} onChange={(e) => setForm(f => ({ ...f, maintenance_scheduled_end: e.target.value }))} className="input-field" />
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-surface-800">
              <button type="button" onClick={closeEdit} className="btn-secondary">Cancel</button>
              <button type="button" onClick={handleSave} disabled={saving} className="btn-primary flex items-center gap-2"><Save size={16} /> {saving ? 'Saving…' : 'Save'}</button>
            </div>
          </div>
        </div>
      )}

      {/* Scenarios drawer */}
      {scenarioTrack && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center"
          onMouseDown={(e) => { if (e.target === e.currentTarget) closeScenarios() }}
        >
          <div
            ref={scenarioDialogRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-label={`${scenarioTrack.code} — Certification scenarios`}
            className="glass-card p-6 w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto outline-none"
          >
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-accent-cyan/10 flex items-center justify-center">
                  <ListChecks size={18} className="text-accent-cyan" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-white">{scenarioTrack.code} — Certification scenarios</h2>
                  <p className="text-xs text-surface-400">Labs mapped into this track, grouped by exam objective</p>
                </div>
              </div>
              <button type="button" onClick={closeScenarios} aria-label="Close certification scenarios" className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-surface-500 hover:text-white"><X size={20} /></button>
            </div>

            {scenarioLoading ? (
              <div className="flex items-center justify-center h-32">
                <div className="w-7 h-7 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
              </div>
            ) : scenarioData ? (
              <div className="space-y-4">
                <p className="text-xs text-surface-500">{scenarioData.scenario_count} scenario(s) across {scenarioData.objectives.length} objective(s)</p>
                {scenarioData.objectives.length === 0 ? (
                  <div className="text-center py-8 text-surface-500">No scenarios mapped to this track yet.</div>
                ) : scenarioData.objectives.map((o) => (
                  <div key={o.code} className="rounded-xl bg-surface-900/60 border border-surface-800 p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-semibold text-white flex items-center gap-2"><BookOpen size={14} className="text-accent-purple" /> {o.title}</h3>
                      <span className="text-xs text-surface-500">weight {o.weight} · {o.scenario_count} lab(s)</span>
                    </div>
                    <ul className="space-y-1.5">
                      {o.scenarios.map((s) => (
                        <li key={s.slug} className="flex items-center justify-between gap-3 text-sm">
                          <span className="text-surface-300 truncate">{s.title}</span>
                          <span className="flex items-center gap-2 shrink-0">
                            {s.technology && <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-800 text-surface-400">{s.technology}</span>}
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-800 text-surface-400 capitalize">{s.difficulty}</span>
                            {s.in_exam_pool && <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-amber/10 text-accent-amber">exam pool</span>}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-surface-500">Could not load scenarios.</div>
            )}
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <div className="w-8 h-8 border-2 border-accent-purple border-t-transparent rounded-full animate-spin" />
        </div>
      ) : tracks.length === 0 ? (
        <div className="glass-card p-10 text-center">
          <Award size={32} className="text-surface-700 mx-auto mb-2" />
          <p className="text-surface-500">No certification tracks yet. Seed tracks via <span className="font-mono text-surface-400">manage.py seed_certifications</span>.</p>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {tracks.map((track) => (
            <div key={track.id} className={`glass-card-hover p-5 relative ${track.maintenance_enabled ? 'border-amber-500/30' : ''}`}>
              {track.maintenance_enabled && (
                <div className="absolute top-2 right-2">
                  <span className="flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30">
                    <WrenchIcon size={9} /> Maintenance
                  </span>
                </div>
              )}
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-xl bg-accent-amber/10 flex items-center justify-center">
                  <Award size={20} className="text-accent-amber" />
                </div>
                <div className="flex gap-1">
                  <button onClick={() => openScenarios(track)} className="p-1.5 text-surface-500 hover:text-accent-cyan" title="Scenarios"><Layers size={14} /></button>
                  <button onClick={() => quickToggle(track, 'maintenance_enabled')} className="p-1.5 text-surface-500 hover:text-amber-400" title="Toggle maintenance"><WrenchIcon size={14} /></button>
                  <button onClick={() => openEdit(track)} className="p-1.5 text-surface-500 hover:text-accent-cyan" title="Edit"><Edit2 size={14} /></button>
                </div>
              </div>
              <h3 className="text-lg font-semibold text-white">{track.code}</h3>
              <p className="text-xs text-surface-600">{track.name}{track.vendor ? ` · ${track.vendor}` : ''}</p>
              <p className="text-sm text-surface-400 mt-1 line-clamp-2">{track.description || 'No description'}</p>
              <div className="mt-2 flex items-center gap-3">
                {track.is_free ? (
                  <span className="text-sm font-semibold text-accent-green">Free</span>
                ) : (
                  <span className="text-sm font-semibold text-accent-green">₹{Number(track.price || 0).toLocaleString('en-IN')}</span>
                )}
                <button onClick={() => quickToggle(track, 'is_free')} className="text-[10px] px-2 py-0.5 rounded-full bg-surface-800 text-surface-400 hover:text-white">
                  {track.is_free ? 'Make paid' : 'Make free'}
                </button>
              </div>
              <div className="mt-3 text-xs text-surface-500 flex flex-wrap gap-x-3 gap-y-1">
                <span>Pass {track.passing_score}%</span>
                <span>{track.exam_duration_minutes} min</span>
                <span>{track.objective_count} objectives</span>
              </div>
              <div className="flex items-center justify-between mt-4 pt-3 border-t border-surface-700/50">
                <button onClick={() => openScenarios(track)} className="text-xs text-surface-400 hover:text-accent-cyan inline-flex items-center gap-1">
                  {track.scenario_count} scenarios <ChevronRight size={12} />
                </button>
                <div className="flex gap-1">
                  {track.coming_soon && (
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400">Coming soon</span>
                  )}
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${track.is_active ? 'bg-accent-green/10 text-accent-green' : 'bg-surface-700 text-surface-400'}`}>{track.is_active ? 'Active' : 'Inactive'}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
