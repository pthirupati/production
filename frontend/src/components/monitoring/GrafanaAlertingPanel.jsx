import { useMemo, useState } from 'react'
import {
  Bell, BellOff, Radio, GitBranch, Layers, ListChecks,
  AlertTriangle, CheckCircle2, Clock, ChevronRight, Mail, MessageSquare, Plus,
} from 'lucide-react'
import { monitoringApi } from '../../api/monitoring'

/* ── helpers ───────────────────────────────────────────────────────────── */

const ACCENT = '#f7913b'

// Stable fallbacks for absent alerting state. The `: []` arm of the Array.isArray
// guards below minted a new identity every render, so `firing`/`pending` — and
// the `silences`/`alertGroups` memos that chain off them — never hit. Frozen so
// an accidental in-place mutation throws rather than corrupting the fallback.
const EMPTY_OBJ = Object.freeze({})
const EMPTY_ARR = Object.freeze([])

// Map a Grafana rule/alert state string to one of the shared badge classes.
function stateBadgeClass(state) {
  const s = String(state || '').toLowerCase()
  if (s === 'alerting' || s === 'firing' || s === 'error') return 'mon-badge-down'
  if (s === 'pending' || s === 'nodata' || s === 'no data') return 'mon-badge-warn'
  return 'mon-badge-up' // Normal / OK / Inactive
}

// Pick a stable-ish label color for a severity so the synthesized views read well.
function severityClass(sev) {
  const s = String(sev || '').toLowerCase()
  if (s === 'critical' || s === 'page') return 'mon-badge-down'
  if (s === 'warning' || s === 'warn') return 'mon-badge-warn'
  return 'mon-badge-up'
}

function icoForType(type) {
  const t = String(type || '').toLowerCase()
  if (t.includes('mail') || t.includes('email')) return Mail
  if (t.includes('slack') || t.includes('teams') || t.includes('chat')) return MessageSquare
  return Radio
}

const SUB_TABS = [
  ['rules', 'Alert rules', ListChecks],
  ['contacts', 'Contact points', Radio],
  ['policies', 'Notification policies', GitBranch],
  ['silences', 'Silences', BellOff],
  ['groups', 'Alert groups', Layers],
]

/* ── main component ─────────────────────────────────────────────────────── */

/**
 * GrafanaAlertingPanel — an ORIGINAL functional emulation of Grafana's unified
 * "Alerting" section for the FixitLab monitoring sim. Pure presentational:
 * renders alert_rules / contact_points / notification_policies straight from
 * `graf`, and synthesizes original sample data for Silences + Alert groups
 * derived from the rules so every tab is populated and educational.
 *
 * Props: { graf }
 *   graf.alert_rules:[{uid,title,folder,for,severity,contact_point,state}]
 *   graf.contact_points:[{name,type,address,configured}]
 *   graf.notification_policies:{ root:{ receiver, ... } }
 */
export default function GrafanaAlertingPanel({ graf = EMPTY_OBJ, sessionId, silences: liveSilences, onReload }) {
  const [sub, setSub] = useState('rules')
  const [busy, setBusy] = useState(false)

  const rules = Array.isArray(graf.alert_rules) ? graf.alert_rules : EMPTY_ARR
  const contacts = Array.isArray(graf.contact_points) ? graf.contact_points : EMPTY_ARR
  const policies = graf.notification_policies || EMPTY_OBJ
  const root = policies.root || EMPTY_OBJ

  // firing rules drive the synthesized Silences + Alert groups views
  const firing = useMemo(
    () => rules.filter(r => String(r.state || '').toLowerCase() === 'alerting'),
    [rules],
  )
  const pending = useMemo(
    () => rules.filter(r => String(r.state || '').toLowerCase() === 'pending'),
    [rules],
  )

  // Prefer lab-server silences; fall back to synthesized samples for empty labs.
  const silences = useMemo(() => {
    if (Array.isArray(liveSilences) && liveSilences.length) {
      return liveSilences.map((s) => ({
        id: s.id,
        matchers: (s.matchers || EMPTY_ARR).map((m) => (
          typeof m === 'string' ? m : `${m.name}${m.isRegex ? '=~' : '='}"${m.value}"`
        )),
        comment: s.comment || '',
        createdBy: s.created_by || s.createdBy || 'labuser',
        starts: s.starts_at || s.starts || 'now',
        ends: s.ends_at || s.ends || '',
        state: s.state || 'active',
      }))
    }
    const out = []
    const muted = firing[0] || pending[0] || rules[0]
    if (muted) {
      out.push({
        id: 'sil-2f9c-mute-firing',
        matchers: [`alertname="${muted.title}"`, `severity="${muted.severity || 'critical'}"`],
        comment: `Muting "${muted.title}" during the maintenance window — investigating root cause`,
        createdBy: 'oncall@fixitlab.io',
        starts: 'now',
        ends: 'in 1h 45m',
        state: 'active',
      })
    }
    out.push({
      id: 'sil-7a01-deploy',
      matchers: ['team="platform"', 'env="staging"'],
      comment: 'Silencing staging alerts during the v2.4 rollout',
      createdBy: 'release-bot',
      starts: 'in 30m',
      ends: 'in 4h',
      state: 'pending',
    })
    out.push({
      id: 'sil-4c88-expired',
      matchers: ['alertname="DiskWillFillSoon"', 'instance=~"node-0[1-3].*"'],
      comment: 'Expanded the volume — alert resolved',
      createdBy: 'sre@fixitlab.io',
      starts: 'expired',
      ends: '12m ago',
      state: 'expired',
    })
    return out
  }, [liveSilences, firing, pending, rules])

  // ── synthesized Alert groups, grouped by severity (original sample data) ──
  const alertGroups = useMemo(() => {
    const active = firing.length ? firing : rules
    const bySeverity = new Map()
    active.forEach(r => {
      const sev = r.severity || 'none'
      if (!bySeverity.has(sev)) bySeverity.set(sev, [])
      bySeverity.get(sev).push(r)
    })
    return Array.from(bySeverity.entries()).map(([sev, items]) => ({
      label: `severity = ${sev}`,
      severity: sev,
      receiver: root.receiver || items[0]?.contact_point || 'default',
      alerts: items.map(r => ({
        title: r.title,
        instance: `instance="${(r.title || 'svc').toLowerCase().replace(/[^a-z0-9]+/g, '-')}:9100"`,
        state: r.state,
        for: r.for,
      })),
    }))
  }, [firing, rules, root.receiver])

  const summary = useMemo(() => ({
    total: rules.length,
    firing: firing.length,
    pending: pending.length,
    normal: rules.length - firing.length - pending.length,
  }), [rules.length, firing.length, pending.length])

  return (
    <div className="space-y-3">
      {/* header / KPIs */}
      <div className="mon-card flex items-center justify-between flex-wrap gap-3">
        <div className="mon-panel-title flex items-center gap-2">
          <Bell size={15} style={{ color: ACCENT }} /> Alerting
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="mon-badge mon-badge-down">{summary.firing} firing</span>
          <span className="mon-badge mon-badge-warn">{summary.pending} pending</span>
          <span className="mon-badge mon-badge-up">{summary.normal} normal</span>
        </div>
      </div>

      {/* sub-tabs */}
      <div className="flex items-center gap-2 flex-wrap">
        {SUB_TABS.map(([k, label, Icon]) => (
          <button
            key={k}
            onClick={() => setSub(k)}
            className={`mon-tab flex items-center gap-2 ${sub === k ? 'mon-tab-active' : ''}`}
          >
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {/* ── Alert rules ── */}
      {sub === 'rules' && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button
              type="button"
              className="mon-btn-primary flex items-center gap-1.5"
              style={{ background: ACCENT }}
              disabled={busy || !sessionId}
              onClick={async () => {
                if (!sessionId) return
                setBusy(true)
                try {
                  await monitoringApi.createGrafanaAlertRule(sessionId, {
                    title: `Lab rule ${Date.now().toString(36).slice(-4)}`,
                    severity: 'warning',
                  })
                  onReload?.()
                } finally {
                  setBusy(false)
                }
              }}
            >
              <Plus size={14} /> New alert rule
            </button>
          </div>
          <div className="mon-card !p-0 overflow-hidden">
            {rules.length === 0 ? (
              <div className="text-[#8a93b2] text-xs p-6 text-center">No alert rules configured.</div>
            ) : (
              <table className="mon-table">
                <thead>
                  <tr>
                    <th>Alert rule</th><th>Folder</th><th>For</th>
                    <th>Severity</th><th>Contact point</th><th>State</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map((r, i) => (
                    <tr key={r.uid || `${r.title}-${i}`}>
                      <td className="font-medium text-[#d8def0]">{r.title}</td>
                      <td>{r.folder || '—'}</td>
                      <td className="font-mono">{r.for || '0s'}</td>
                      <td><span className={`mon-badge ${severityClass(r.severity)}`}>{r.severity || 'none'}</span></td>
                      <td className="font-mono opacity-80">{r.contact_point || '—'}</td>
                      <td>
                        <span className={`mon-badge ${stateBadgeClass(r.state)}`}>
                          {String(r.state || '').toLowerCase() === 'alerting' && <AlertTriangle size={12} />}
                          {r.state || 'Normal'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* ── Contact points ── */}
      {sub === 'contacts' && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button
              type="button"
              className="mon-btn-primary flex items-center gap-1.5"
              style={{ background: ACCENT }}
              disabled={busy || !sessionId}
              onClick={async () => {
                if (!sessionId) return
                setBusy(true)
                try {
                  await monitoringApi.createContactPoint(sessionId, {
                    name: `cp-${Date.now().toString(36).slice(-4)}`,
                    type: 'email',
                  })
                  onReload?.()
                } finally {
                  setBusy(false)
                }
              }}
            >
              <Plus size={14} /> New contact point
            </button>
          </div>
          <div className="mon-card !p-0 overflow-hidden">
            {contacts.length === 0 ? (
              <div className="text-[#8a93b2] text-xs p-6 text-center">No contact points configured.</div>
            ) : (
              <table className="mon-table">
                <thead>
                  <tr><th>Name</th><th>Type</th><th>Address</th><th>Status</th></tr>
                </thead>
                <tbody>
                  {contacts.map((c, i) => {
                    const Ico = icoForType(c.type)
                    return (
                      <tr key={c.name || i}>
                        <td className="font-medium text-[#d8def0] flex items-center gap-2">
                          <Ico size={13} style={{ color: ACCENT }} /> {c.name}
                        </td>
                        <td>{c.type || '—'}</td>
                        <td className="font-mono opacity-80">{c.address || '—'}</td>
                        <td>
                          <span className={`mon-badge ${c.configured ? 'mon-badge-up' : 'mon-badge-down'}`}>
                            {c.configured
                              ? <><CheckCircle2 size={12} /> Configured</>
                              : <><AlertTriangle size={12} /> Not configured</>}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* ── Notification policies ── */}
      {sub === 'policies' && (
        <div className="space-y-3">
          <div className="mon-card">
            <div className="mon-panel-title flex items-center gap-2 mb-1">
              <GitBranch size={14} style={{ color: ACCENT }} /> Root policy
            </div>
            <div className="mon-panel-sub mb-2">
              Default route — every alert that doesn&apos;t match a nested policy goes here.
            </div>
            <div className="flex items-center gap-2 flex-wrap text-xs">
              <span className="mon-panel-sub">Default contact point</span>
              <span className="mon-badge mon-badge-up">{root.receiver || 'default'}</span>
              {root.group_by && (
                <>
                  <span className="mon-panel-sub ml-2">Group by</span>
                  <span className="font-mono text-[#d8def0]">
                    {Array.isArray(root.group_by) ? root.group_by.join(', ') : String(root.group_by)}
                  </span>
                </>
              )}
            </div>
          </div>

          {/* nested routes: render real ones if present, else a derived illustrative tree */}
          <div className="mon-card">
            <div className="mon-panel-sub mb-2">Specific routing</div>
            <div className="space-y-2">
              {(Array.isArray(root.routes) && root.routes.length > 0
                ? root.routes.map((rt, i) => ({
                    match: rt.matchers || rt.object_matchers || rt.match || ['—'],
                    receiver: rt.receiver || root.receiver || 'default',
                    key: i,
                  }))
                : [
                    { match: ['severity = critical'], receiver: 'pagerduty-critical', key: 'd0' },
                    { match: ['team = platform'], receiver: 'slack-platform', key: 'd1' },
                  ]
              ).map(rt => (
                <div key={rt.key} className="flex items-center gap-2 text-xs">
                  <ChevronRight size={13} className="text-[#8a93b2] shrink-0" />
                  <span className="mon-code !py-1 !text-[11px]">
                    {Array.isArray(rt.match)
                      ? rt.match.map(m => (Array.isArray(m) ? m.join(' ') : String(m))).join(' AND ')
                      : String(rt.match)}
                  </span>
                  <ChevronRight size={13} className="text-[#8a93b2] shrink-0" />
                  <span className="mon-badge mon-badge-up">{rt.receiver}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="mon-card">
            <div className="mon-panel-sub mb-1">Raw policy</div>
            <div className="mon-code">{JSON.stringify(root, null, 2)}</div>
          </div>
        </div>
      )}

      {/* ── Silences ── */}
      {sub === 'silences' && (
        <div className="space-y-3">
          <div className="mon-banner">
            <BellOff size={15} className="shrink-0 mt-0.5" style={{ color: ACCENT }} />
            <span>
              Silences mute notifications for alerts matching a set of label matchers.
              Create or expire silences against the lab Alertmanager state.
            </span>
          </div>
          <div className="flex justify-end">
            <button type="button" className="mon-btn-primary !text-xs" disabled={busy || !sessionId}
              onClick={async () => {
                setBusy(true)
                try {
                  const alertname = firing[0]?.title || pending[0]?.title || rules[0]?.title || 'NodeDown'
                  await monitoringApi.createSilence(sessionId, { alertname, comment: `Lab silence for ${alertname}` })
                  await onReload?.()
                } finally { setBusy(false) }
              }}>
              Create silence
            </button>
          </div>
          <div className="mon-card !p-0 overflow-hidden">
            <table className="mon-table">
              <thead>
                <tr><th>Matchers</th><th>Comment</th><th>Created by</th><th>Schedule</th><th>State</th><th /></tr>
              </thead>
              <tbody>
                {silences.map(s => (
                  <tr key={s.id}>
                    <td className="font-mono text-xs">
                      {s.matchers.map((m, i) => (
                        <span key={i} className="text-[#8a93b2]">
                          {m}{i < s.matchers.length - 1 ? ', ' : ''}
                        </span>
                      ))}
                    </td>
                    <td className="text-[#d8def0]">{s.comment}</td>
                    <td className="font-mono opacity-80">{s.createdBy}</td>
                    <td className="font-mono opacity-70 flex items-center gap-1">
                      <Clock size={12} /> {s.starts} → {s.ends}
                    </td>
                    <td>
                      <span className={`mon-badge ${
                        s.state === 'active' ? 'mon-badge-up'
                          : s.state === 'pending' ? 'mon-badge-warn'
                            : 'mon-badge-down'}`}>
                        {s.state}
                      </span>
                    </td>
                    <td>
                      {s.state === 'active' && sessionId && (
                        <button type="button" className="text-xs text-[#f7913b]" disabled={busy}
                          onClick={async () => {
                            setBusy(true)
                            try {
                              await monitoringApi.expireSilence(sessionId, s.id)
                              await onReload?.()
                            } finally { setBusy(false) }
                          }}>
                          Expire
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Alert groups (synthesized, grouped by severity) ── */}
      {sub === 'groups' && (
        <div className="space-y-3">
          <div className="mon-banner">
            <Layers size={15} className="shrink-0 mt-0.5" style={{ color: ACCENT }} />
            <span>
              Alert groups collapse related instances into a single notification.
              These groups are derived from the active rules, grouped by severity.
            </span>
          </div>
          {alertGroups.length === 0 ? (
            <div className="mon-card text-[#8a93b2] text-xs text-center py-6">
              No active alerts — nothing to group.
            </div>
          ) : (
            alertGroups.map(g => (
              <div key={g.label} className="mon-card">
                <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
                  <div className="mon-panel-title flex items-center gap-2">
                    <span className={`mon-badge ${severityClass(g.severity)}`}>{g.label}</span>
                    <span className="mon-panel-sub">{g.alerts.length} alert{g.alerts.length === 1 ? '' : 's'}</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs">
                    <span className="mon-panel-sub">routed to</span>
                    <span className="mon-badge mon-badge-up">{g.receiver}</span>
                  </div>
                </div>
                <table className="mon-table">
                  <thead>
                    <tr><th>Alert</th><th>Instance</th><th>For</th><th>State</th></tr>
                  </thead>
                  <tbody>
                    {g.alerts.map((a, i) => (
                      <tr key={`${a.title}-${i}`}>
                        <td className="font-medium text-[#d8def0]">{a.title}</td>
                        <td className="font-mono opacity-80">{a.instance}</td>
                        <td className="font-mono">{a.for || '0s'}</td>
                        <td>
                          <span className={`mon-badge ${stateBadgeClass(a.state)}`}>{a.state || 'Normal'}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
