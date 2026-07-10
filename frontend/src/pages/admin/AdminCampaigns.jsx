import { useState, useEffect, useCallback } from 'react'
import { adminApi } from '../../api/admin'
import { AdminPageHeader } from '../../components/design'
import { CampaignRender } from '../../components/CampaignBanner'
import {
  Megaphone, Plus, Eye, Save, Trash2, Power, PowerOff, Pencil, X,
  Share2, Copy, ExternalLink, Image as ImageIcon, Video, Sparkles,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { useConfirm } from '../../hooks/useConfirm'

const EMPTY_FORM = {
  kind: 'campaign',
  title: '',
  body: '',
  media_type: 'none',
  media_url: '',
  placement: 'banner_top',
  bg_color: '',
  text_color: '',
  text_style: { font_size: '', font_weight: '', text_align: 'left' },
  cta_label: '',
  cta_url: '',
  audience: 'all',
  dismissible: true,
  starts_at: '',
  ends_at: '',
}

const KINDS = [
  { value: 'campaign', label: 'Campaign (ad)' },
  { value: 'announcement', label: 'Announcement' },
  { value: 'offer', label: 'Offer' },
]
const PLACEMENTS = [
  { value: 'banner_top', label: 'Top banner' },
  { value: 'dashboard', label: 'Dashboard card' },
  { value: 'modal', label: 'Modal' },
  { value: 'pricing', label: 'Pricing strip' },
]
const AUDIENCES = [
  { value: 'all', label: 'Everyone' },
  { value: 'free', label: 'Free users' },
  { value: 'paid', label: 'Paid users' },
]

const STATUS_BADGE = {
  enabled: 'bg-green-500/15 text-green-300 border-green-500/30',
  draft: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  cancelled: 'bg-surface-500/15 text-surface-400 border-surface-500/30',
}

// Helpers to convert ISO <-> datetime-local input value
function toLocalInput(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
function fromLocalInput(val) {
  if (!val) return null
  const d = new Date(val)
  return Number.isNaN(d.getTime()) ? null : d.toISOString()
}

function Field({ label, children, hint }) {
  return (
    <label className="block">
      <span className="block text-[12px] font-semibold text-surface-300 mb-1.5">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-surface-500 mt-1">{hint}</span>}
    </label>
  )
}

export default function AdminCampaigns() {
  const { confirm, ConfirmPortal } = useConfirm()
  const [tab, setTab] = useState('campaigns') // 'campaigns' | 'social'
  const [campaigns, setCampaigns] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [editingId, setEditingId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await adminApi.getCampaigns()
      setCampaigns(Array.isArray(data) ? data : [])
    } catch {
      toast.error('Failed to load campaigns')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const set = (patch) => setForm((f) => ({ ...f, ...patch }))
  const setStyle = (patch) => setForm((f) => ({ ...f, text_style: { ...f.text_style, ...patch } }))

  const resetForm = () => { setForm(EMPTY_FORM); setEditingId(null) }

  const startEdit = (c) => {
    setEditingId(c.id)
    setForm({
      ...EMPTY_FORM,
      ...c,
      text_style: { ...EMPTY_FORM.text_style, ...(c.text_style || {}) },
      starts_at: toLocalInput(c.starts_at),
      ends_at: toLocalInput(c.ends_at),
    })
    setTab('campaigns')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const buildPayload = () => ({
    ...form,
    starts_at: fromLocalInput(form.starts_at),
    ends_at: fromLocalInput(form.ends_at),
  })

  const handleSave = async () => {
    if (!form.title.trim()) { toast.error('Title is required'); return }
    setSaving(true)
    try {
      if (editingId) {
        await adminApi.updateCampaign(editingId, buildPayload())
        toast.success('Campaign updated')
      } else {
        await adminApi.createCampaign(buildPayload())
        toast.success('Campaign created as draft')
      }
      resetForm()
      load()
    } catch (e) {
      toast.error(e?.response?.data?.error || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleStatus = async (c, action) => {
    try {
      await adminApi.setCampaignStatus(c.id, action)
      toast.success(action === 'enable' ? 'Campaign is now live' : action === 'cancel' ? 'Campaign cancelled' : 'Moved to draft')
      load()
    } catch {
      toast.error('Action failed')
    }
  }

  const handleDelete = async (c) => {
    if (!await confirm({ message: `Delete "${c.title}"? This cannot be undone.`, danger: true, confirmLabel: 'Delete' })) return
    try {
      await adminApi.deleteCampaign(c.id)
      toast.success('Deleted')
      if (editingId === c.id) resetForm()
      load()
    } catch {
      toast.error('Delete failed')
    }
  }

  const handleUpload = async (file) => {
    if (!file) return
    try {
      const res = await adminApi.uploadBanner(file, 'campaigns')
      const url = res?.url || res?.media_url || ''
      if (url) {
        set({ media_url: url, media_type: file.type.startsWith('video') ? 'video' : 'image' })
        toast.success('Uploaded')
      }
    } catch {
      toast.error('Upload failed (you can also paste a URL)')
    }
  }

  return (
    <>
    <div className="space-y-6">
      <AdminPageHeader
        title="Ads & Campaigns"
        subtitle="Run in-platform marketing banners, announcements and offers. Generate social posts to share manually."
        onRefresh={load}
        refreshing={loading}
        actions={
          editingId && (
            <button type="button" onClick={resetForm} className="btn-secondary flex items-center gap-2 text-sm py-2 px-3">
              <Plus size={14} /> New campaign
            </button>
          )
        }
      />

      {/* Tabs */}
      <div className="flex gap-2 border-b border-white/[0.07]">
        {[
          { id: 'campaigns', label: 'Campaigns', icon: Megaphone },
          { id: 'social', label: 'Social post', icon: Share2 },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 -mb-px transition-colors ${
              tab === id ? 'border-accent-purple text-white' : 'border-transparent text-surface-400 hover:text-surface-200'
            }`}
          >
            <Icon size={15} /> {label}
          </button>
        ))}
      </div>

      {tab === 'campaigns' ? (
        <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_0.9fr] gap-6">
          {/* ── Editor ── */}
          <div className="fx-admin-card p-5 space-y-4">
            <h2 className="font-display font-bold text-lg text-white flex items-center gap-2">
              <Pencil size={17} className="text-accent-purple" />
              {editingId ? 'Edit campaign' : 'Create campaign'}
            </h2>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Type">
                <select className="input-field" value={form.kind} onChange={(e) => set({ kind: e.target.value })}>
                  {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
                </select>
              </Field>
              <Field label="Placement">
                <select className="input-field" value={form.placement} onChange={(e) => set({ placement: e.target.value })}>
                  {PLACEMENTS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
              </Field>
            </div>

            <Field label="Title">
              <input className="input-field" value={form.title} maxLength={200}
                onChange={(e) => set({ title: e.target.value })} placeholder="New: Kubernetes break/fix labs are live" />
            </Field>

            <Field label="Body / content">
              <textarea className="input-field min-h-[80px]" value={form.body}
                onChange={(e) => set({ body: e.target.value })}
                placeholder="Short supporting copy. Markdown / plain text." />
            </Field>

            {/* Media */}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Media type">
                <select className="input-field" value={form.media_type} onChange={(e) => set({ media_type: e.target.value })}>
                  <option value="none">None</option>
                  <option value="image">Image</option>
                  <option value="video">Video</option>
                </select>
              </Field>
              {form.media_type !== 'none' && (
                <Field label="Upload (optional)">
                  <input type="file" accept={form.media_type === 'video' ? 'video/*' : 'image/*'}
                    onChange={(e) => handleUpload(e.target.files?.[0])}
                    className="block w-full text-[12px] text-surface-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-accent-purple/20 file:text-accent-purple file:text-xs file:font-semibold" />
                </Field>
              )}
            </div>
            {form.media_type !== 'none' && (
              <Field label="Media URL" hint="Paste an image/video URL, or upload above.">
                <div className="flex items-center gap-2">
                  {form.media_type === 'video' ? <Video size={15} className="text-surface-500" /> : <ImageIcon size={15} className="text-surface-500" />}
                  <input className="input-field" value={form.media_url}
                    onChange={(e) => set({ media_url: e.target.value })} placeholder="https://…" />
                </div>
              </Field>
            )}

            {/* Colors */}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Background" hint="CSS color or gradient">
                <div className="flex items-center gap-2">
                  <input type="color" value={/^#/.test(form.bg_color) ? form.bg_color : '#1e3a5f'}
                    onChange={(e) => set({ bg_color: e.target.value })}
                    className="h-9 w-10 rounded border border-white/10 bg-transparent cursor-pointer" />
                  <input className="input-field" value={form.bg_color}
                    onChange={(e) => set({ bg_color: e.target.value })}
                    placeholder="linear-gradient(90deg,#1e3a5f,#0f766e)" />
                </div>
              </Field>
              <Field label="Text color">
                <div className="flex items-center gap-2">
                  <input type="color" value={/^#/.test(form.text_color) ? form.text_color : '#ffffff'}
                    onChange={(e) => set({ text_color: e.target.value })}
                    className="h-9 w-10 rounded border border-white/10 bg-transparent cursor-pointer" />
                  <input className="input-field" value={form.text_color}
                    onChange={(e) => set({ text_color: e.target.value })} placeholder="#ffffff" />
                </div>
              </Field>
            </div>

            {/* Text style */}
            <div className="grid grid-cols-3 gap-3">
              <Field label="Font size">
                <input className="input-field" value={form.text_style.font_size}
                  onChange={(e) => setStyle({ font_size: e.target.value })} placeholder="15px" />
              </Field>
              <Field label="Weight">
                <select className="input-field" value={form.text_style.font_weight}
                  onChange={(e) => setStyle({ font_weight: e.target.value })}>
                  <option value="">Default</option>
                  <option value="400">Normal</option>
                  <option value="600">Semibold</option>
                  <option value="700">Bold</option>
                  <option value="800">Extrabold</option>
                </select>
              </Field>
              <Field label="Align">
                <select className="input-field" value={form.text_style.text_align}
                  onChange={(e) => setStyle({ text_align: e.target.value })}>
                  <option value="left">Left</option>
                  <option value="center">Center</option>
                  <option value="right">Right</option>
                </select>
              </Field>
            </div>

            {/* CTA */}
            <div className="grid grid-cols-2 gap-3">
              <Field label="CTA label">
                <input className="input-field" value={form.cta_label}
                  onChange={(e) => set({ cta_label: e.target.value })} placeholder="Try it now" />
              </Field>
              <Field label="CTA link">
                <input className="input-field" value={form.cta_url}
                  onChange={(e) => set({ cta_url: e.target.value })} placeholder="/technologies or https://…" />
              </Field>
            </div>

            {/* Audience + schedule */}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Audience">
                <select className="input-field" value={form.audience} onChange={(e) => set({ audience: e.target.value })}>
                  {AUDIENCES.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
                </select>
              </Field>
              <Field label="Dismissible">
                <select className="input-field" value={form.dismissible ? '1' : '0'}
                  onChange={(e) => set({ dismissible: e.target.value === '1' })}>
                  <option value="1">Yes — users can close it</option>
                  <option value="0">No — always shown</option>
                </select>
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Starts at" hint="Optional">
                <input type="datetime-local" className="input-field" value={form.starts_at}
                  onChange={(e) => set({ starts_at: e.target.value })} />
              </Field>
              <Field label="Ends at" hint="Optional">
                <input type="datetime-local" className="input-field" value={form.ends_at}
                  onChange={(e) => set({ ends_at: e.target.value })} />
              </Field>
            </div>

            <div className="flex items-center gap-2 pt-1">
              <button type="button" onClick={handleSave} disabled={saving}
                className="btn-primary flex items-center gap-2 text-sm">
                <Save size={15} /> {saving ? 'Saving…' : editingId ? 'Save changes' : 'Create draft'}
              </button>
              {editingId && (
                <button type="button" onClick={resetForm} className="btn-secondary flex items-center gap-2 text-sm">
                  <X size={15} /> Cancel
                </button>
              )}
            </div>
          </div>

          {/* ── Live preview + list ── */}
          <div className="space-y-6">
            <div className="fx-admin-card p-5">
              <h2 className="font-display font-bold text-lg text-white flex items-center gap-2 mb-3">
                <Eye size={17} className="text-accent-cyan" /> Live preview
              </h2>
              <p className="text-[12px] text-surface-500 mb-3">Exactly how this renders on the platform. Toggle the app theme to preview light/dark.</p>
              <div className="rounded-xl overflow-hidden border border-white/10">
                <CampaignRender campaign={form} preview onDismiss={() => {}} />
              </div>
              {!form.title && <p className="text-[12px] text-surface-500 mt-3 text-center">Add a title to see the preview.</p>}
            </div>

            <div className="fx-admin-card p-5">
              <h2 className="font-display font-bold text-lg text-white mb-3">All campaigns</h2>
              {loading ? (
                <p className="text-sm text-surface-500">Loading…</p>
              ) : campaigns.length === 0 ? (
                <p className="text-sm text-surface-500">No campaigns yet. Create one on the left.</p>
              ) : (
                <div className="space-y-2.5">
                  {campaigns.map((c) => (
                    <div key={c.id} className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-semibold text-white truncate">{c.title}</span>
                          <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full border ${STATUS_BADGE[c.status] || STATUS_BADGE.draft}`}>
                            {c.status}{c.status === 'enabled' && !c.is_live ? ' (scheduled)' : ''}
                          </span>
                        </div>
                        <p className="text-[11px] text-surface-500 mt-0.5">
                          {c.kind} · {c.placement} · {c.audience}
                        </p>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <button type="button" onClick={() => startEdit(c)} title="Edit"
                          className="p-2 rounded-lg text-surface-400 hover:text-white hover:bg-white/10"><Pencil size={15} /></button>
                        {c.status !== 'enabled' ? (
                          <button type="button" onClick={() => handleStatus(c, 'enable')} title="Enable"
                            className="p-2 rounded-lg text-green-400 hover:bg-green-500/15"><Power size={15} /></button>
                        ) : (
                          <button type="button" onClick={() => handleStatus(c, 'cancel')} title="Cancel"
                            className="p-2 rounded-lg text-amber-400 hover:bg-amber-500/15"><PowerOff size={15} /></button>
                        )}
                        <button type="button" onClick={() => handleDelete(c)} title="Delete"
                          className="p-2 rounded-lg text-surface-400 hover:text-accent-red hover:bg-red-500/10"><Trash2 size={15} /></button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <SocialTab campaigns={campaigns} />
      )}
    </div>
    <ConfirmPortal />
    </>
  )
}

// ── Social post generator tab ──

const DEFAULT_CURRENT = [
  'VMware vSphere break/fix simulator (vMotion, HA, datastores)',
  'Linux, Kubernetes & Docker troubleshooting labs',
  'AI mock interviews with live feedback',
]
const DEFAULT_UPCOMING = [
  'GPU & bare-metal labs',
  'More cloud (AWS/Azure/GCP) scenarios',
]

function SocialTab({ campaigns }) {
  const [campaignId, setCampaignId] = useState('')
  const [current, setCurrent] = useState(DEFAULT_CURRENT.join('\n'))
  const [upcoming, setUpcoming] = useState(DEFAULT_UPCOMING.join('\n'))
  const [posts, setPosts] = useState(null)
  const [loading, setLoading] = useState(false)

  const generate = async () => {
    setLoading(true)
    try {
      const data = await adminApi.generateSocialPosts({
        campaign_id: campaignId || undefined,
        current_features: current.split('\n').map((s) => s.trim()).filter(Boolean),
        upcoming_features: upcoming.split('\n').map((s) => s.trim()).filter(Boolean),
      })
      setPosts(data)
    } catch {
      toast.error('Failed to generate posts')
    } finally {
      setLoading(false)
    }
  }

  const copy = async (text) => {
    try {
      await navigator.clipboard.writeText(text)
      toast.success('Copied to clipboard')
    } catch {
      toast.error('Copy failed')
    }
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[0.8fr_1.2fr] gap-6">
      <div className="fx-admin-card p-5 space-y-4">
        <h2 className="font-display font-bold text-lg text-white flex items-center gap-2">
          <Sparkles size={17} className="text-accent-purple" /> Generate posts
        </h2>
        <div className="rounded-lg bg-accent-cyan/[0.06] border border-accent-cyan/20 p-3 text-[12px] text-surface-300 leading-relaxed">
          This <strong>generates &amp; copies</strong> ready-to-paste posts — it does <strong>not</strong> auto-post.
          Free, no API keys. Click a share link to open the network with the post (paste where needed), or copy the text.
        </div>

        <Field label="Seed from campaign (optional)">
          <select className="input-field" value={campaignId} onChange={(e) => setCampaignId(e.target.value)}>
            <option value="">Generic product update</option>
            {campaigns.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
        </Field>
        <Field label="Current features (one per line)">
          <textarea className="input-field min-h-[120px]" value={current} onChange={(e) => setCurrent(e.target.value)} />
        </Field>
        <Field label="Upcoming features (one per line)">
          <textarea className="input-field min-h-[90px]" value={upcoming} onChange={(e) => setUpcoming(e.target.value)} />
        </Field>
        <button type="button" onClick={generate} disabled={loading} className="btn-primary flex items-center gap-2 text-sm">
          <Share2 size={15} /> {loading ? 'Generating…' : 'Generate posts'}
        </button>
      </div>

      <div className="space-y-4">
        {!posts ? (
          <div className="fx-admin-card p-8 text-center text-surface-500 text-sm">
            Generate to preview LinkedIn, Twitter/X and Reddit posts.
          </div>
        ) : (
          [
            { key: 'twitter', label: 'Twitter / X', text: posts.twitter?.text, share: posts.twitter?.share_url, meta: `${posts.twitter?.char_count || 0} chars` },
            { key: 'linkedin', label: 'LinkedIn', text: posts.linkedin?.text, share: posts.linkedin?.share_url, note: posts.linkedin?.note },
            { key: 'reddit', label: 'Reddit', text: posts.reddit?.text, share: posts.reddit?.share_url, title: posts.reddit?.title },
          ].map((p) => (
            <div key={p.key} className="fx-admin-card p-5">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-bold text-white flex items-center gap-2">{p.label}
                  {p.meta && <span className="text-[11px] font-normal text-surface-500">({p.meta})</span>}
                </h3>
                <div className="flex items-center gap-2">
                  <button type="button" onClick={() => copy(p.title ? `${p.title}\n\n${p.text}` : p.text)}
                    className="btn-secondary flex items-center gap-1.5 text-xs py-1.5 px-2.5">
                    <Copy size={13} /> Copy
                  </button>
                  <a href={p.share} target="_blank" rel="noopener noreferrer"
                    className="btn-secondary flex items-center gap-1.5 text-xs py-1.5 px-2.5 no-underline">
                    <ExternalLink size={13} /> Share
                  </a>
                </div>
              </div>
              {p.title && <p className="text-[13px] font-semibold text-accent-cyan mb-1">{p.title}</p>}
              <pre className="whitespace-pre-wrap text-[12.5px] text-surface-200 bg-black/20 rounded-lg p-3 border border-white/[0.06] font-sans leading-relaxed">{p.text}</pre>
              {p.note && <p className="text-[11px] text-amber-300/80 mt-2">{p.note}</p>}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
