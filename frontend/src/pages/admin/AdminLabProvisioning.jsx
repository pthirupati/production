import { useState, useEffect, useMemo } from 'react'
import { adminApi } from '../../api/admin'
import { AdminPageHeader } from '../../components/design'
import { CheckSquare, Square, Copy, PlayCircle, Layers, Terminal, AlertTriangle, CheckCircle2 } from 'lucide-react'
import toast from 'react-hot-toast'

/**
 * Admin Lab Provisioning — pick technologies with checkboxes to (re)seed instead
 * of typing comma-separated slugs into the GitHub workflow input.
 *
 *  - Lists every scenario-folder technology as a checkbox (select-all / clear-all).
 *  - Shows the resulting comma-separated slug string (copy into the GitHub
 *    workflow `technologies` input — this method also stays supported).
 *  - "Provision / Re-seed selected" runs the SAFE in-app path:
 *    seed_scenarios --merge-only --technologies <slugs>.
 *  - Renders the exact `gh workflow run production.yml ...` command to copy
 *    (no GitHub token is configured server-side, so we never dispatch from the API).
 */
export default function AdminLabProvisioning() {
  const [techs, setTechs] = useState([])
  const [selected, setSelected] = useState(() => new Set())
  const [loading, setLoading] = useState(true)
  const [provisioning, setProvisioning] = useState(false)
  const [result, setResult] = useState(null)
  const [meta, setMeta] = useState({ workflow_input: 'technologies', workflow_file: 'production.yml', github_dispatch_available: false })

  const loadData = async () => {
    setLoading(true)
    try {
      const data = await adminApi.getProvisioningTechnologies()
      setTechs(data.technologies || [])
      setMeta({
        workflow_input: data.workflow_input || 'technologies',
        workflow_file: data.workflow_file || 'production.yml',
        github_dispatch_available: !!data.github_dispatch_available,
        scenarios_dir: data.scenarios_dir,
      })
    } catch {
      toast.error('Failed to load technologies')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [])

  const toggle = (slug) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(slug)) next.delete(slug)
      else next.add(slug)
      return next
    })
  }

  const selectAll = () => setSelected(new Set(techs.map(t => t.slug)))
  const clearAll = () => setSelected(new Set())

  // Comma-separated slug string — paste this into the GitHub workflow input.
  const slugCsv = useMemo(
    () => techs.filter(t => selected.has(t.slug)).map(t => t.slug).join(','),
    [techs, selected],
  )

  const ghCommand = useMemo(() => {
    const csv = slugCsv || '<slugs>'
    return `gh workflow run ${meta.workflow_file} -f action=deploy -f technologies=${csv} -f merge_seed_only=true`
  }, [slugCsv, meta.workflow_file])

  const copy = async (text, label = 'Copied to clipboard') => {
    if (!text) { toast.error('Nothing to copy — select at least one technology'); return }
    try {
      await navigator.clipboard.writeText(text)
      toast.success(label)
    } catch {
      toast.error('Copy failed')
    }
  }

  const provision = async () => {
    if (selected.size === 0) { toast.error('Select at least one technology'); return }
    setProvisioning(true)
    setResult(null)
    try {
      const data = await adminApi.provisionTechnologies(Array.from(selected))
      setResult(data)
      toast.success(data.message || 'Re-seed complete')
      // Refresh catalog so newly-seeded techs lose their "not seeded" badge.
      loadData()
    } catch (e) {
      const msg = e?.response?.data?.error || 'Provisioning failed'
      toast.error(msg)
      setResult({ error: msg })
    } finally {
      setProvisioning(false)
    }
  }

  const allSelected = techs.length > 0 && selected.size === techs.length

  return (
    <div className="space-y-6 animate-fade-in">
      <AdminPageHeader
        title="Lab Provisioning"
        subtitle="Pick technologies to (re)seed their scenarios — no need to type comma-separated slugs"
        onRefresh={loadData}
        refreshing={loading}
        actions={
          <button
            type="button"
            onClick={provision}
            disabled={provisioning || selected.size === 0}
            className="btn-primary flex items-center gap-2 text-sm py-2 px-3 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <PlayCircle size={15} className={provisioning ? 'animate-spin' : ''} />
            {provisioning ? 'Re-seeding…' : `Provision / Re-seed selected${selected.size ? ` (${selected.size})` : ''}`}
          </button>
        }
      />

      {/* Safe-path explainer */}
      <div className="glass-card p-4 flex items-start gap-3 text-sm">
        <Layers size={16} className="text-accent-cyan mt-0.5 shrink-0" />
        <p className="text-surface-300 m-0">
          <strong className="text-white">Provision / Re-seed</strong> runs
          {' '}<code className="text-accent-cyan">seed_scenarios --merge-only --technologies &lt;slugs&gt;</code>{' '}
          for the selected technologies — it adds new scenarios from their YAML folders without overwriting existing ones.
          You can also copy the slug string below into the GitHub workflow <code className="text-accent-cyan">{meta.workflow_input}</code> input.
        </p>
      </div>

      {/* Selection toolbar + checkbox grid */}
      <div className="glass-card p-5 space-y-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <h2 className="font-semibold text-white text-sm m-0">Technologies</h2>
            <span className="text-xs text-surface-500">{selected.size} of {techs.length} selected</span>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={selectAll} disabled={allSelected} className="btn-secondary text-xs py-1.5 px-3 disabled:opacity-40">
              Select all
            </button>
            <button type="button" onClick={clearAll} disabled={selected.size === 0} className="btn-secondary text-xs py-1.5 px-3 disabled:opacity-40">
              Clear all
            </button>
          </div>
        </div>

        {loading ? (
          <p className="text-surface-400 text-sm py-6 text-center">Loading technologies…</p>
        ) : techs.length === 0 ? (
          <p className="text-surface-400 text-sm py-6 text-center">No scenario technologies found on this host.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {techs.map(t => {
              const isOn = selected.has(t.slug)
              return (
                <button
                  key={t.slug}
                  type="button"
                  onClick={() => toggle(t.slug)}
                  className={`flex items-start gap-2.5 p-3 rounded-lg border text-left transition-all ${
                    isOn
                      ? 'border-accent-cyan/40 bg-accent-cyan/[0.07]'
                      : 'border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.05]'
                  }`}
                >
                  {isOn
                    ? <CheckSquare size={16} className="text-accent-cyan mt-0.5 shrink-0" />
                    : <Square size={16} className="text-surface-500 mt-0.5 shrink-0" />}
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="font-medium text-white text-[13px] truncate">{t.name}</span>
                      {t.seeded === false && (
                        <span className="text-[9px] uppercase tracking-wide font-semibold text-amber-300 bg-amber-500/10 px-1.5 py-0.5 rounded">New</span>
                      )}
                    </span>
                    <span className="block text-[11px] text-surface-500 font-mono truncate">{t.slug}</span>
                    <span className="block text-[11px] text-surface-400 mt-0.5">{t.scenario_folders} scenario folder{t.scenario_folders === 1 ? '' : 's'}</span>
                  </span>
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* Comma-separated slug string — copy into the GitHub workflow input */}
      <div className="glass-card p-5 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-semibold text-white text-sm m-0">
            Comma-separated slugs
            <span className="text-surface-500 font-normal"> — for the GitHub workflow <code className="text-accent-cyan">{meta.workflow_input}</code> input</span>
          </h2>
          <button type="button" onClick={() => copy(slugCsv, 'Slug string copied')} className="btn-secondary flex items-center gap-1.5 text-xs py-1.5 px-3">
            <Copy size={13} /> Copy
          </button>
        </div>
        <code className="block w-full bg-black/30 border border-white/[0.08] rounded-lg p-3 text-[13px] text-accent-cyan font-mono break-all min-h-[44px]">
          {slugCsv || <span className="text-surface-500">Select technologies above to build the slug string…</span>}
        </code>
      </div>

      {/* gh CLI command — render to copy (no server-side GitHub token configured) */}
      <div className="glass-card p-5 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-semibold text-white text-sm m-0 flex items-center gap-2">
            <Terminal size={15} className="text-accent-purple" />
            Run the pipeline for this selection
          </h2>
          <button type="button" onClick={() => copy(slugCsv ? ghCommand : '', 'Command copied')} className="btn-secondary flex items-center gap-1.5 text-xs py-1.5 px-3">
            <Copy size={13} /> Copy command
          </button>
        </div>
        <p className="text-[12px] text-surface-400 m-0">
          No GitHub token is configured on the server, so run this command locally (with the GitHub CLI) to trigger the production workflow for the selected technologies:
        </p>
        <code className="block w-full bg-black/30 border border-white/[0.08] rounded-lg p-3 text-[13px] text-accent-green font-mono break-all">
          {ghCommand}
        </code>
      </div>

      {/* Result summary */}
      {result && (
        <div className={`glass-card p-5 space-y-3 border ${result.error ? 'border-accent-red/30' : 'border-accent-green/30'}`}>
          <div className="flex items-center gap-2">
            {result.error
              ? <AlertTriangle size={16} className="text-accent-red" />
              : <CheckCircle2 size={16} className="text-accent-green" />}
            <h2 className="font-semibold text-white text-sm m-0">{result.error ? 'Provisioning failed' : 'Re-seed result'}</h2>
          </div>
          {result.error ? (
            <p className="text-accent-red text-sm m-0">{result.error}</p>
          ) : (
            <>
              <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-surface-300">
                <span>Technologies: <strong className="text-white">{(result.technologies || []).join(', ')}</strong></span>
                <span>New scenarios: <strong className="text-white">{result.scenarios_created ?? 0}</strong></span>
                <span>Total scenarios: <strong className="text-white">{result.scenarios_total ?? 0}</strong></span>
              </div>
              {Array.isArray(result.unknown) && result.unknown.length > 0 && (
                <p className="text-amber-300 text-xs m-0">Ignored unknown slugs: {result.unknown.join(', ')}</p>
              )}
              {result.output_tail && (
                <pre className="bg-black/40 border border-white/[0.08] rounded-lg p-3 text-[11px] text-surface-300 font-mono whitespace-pre-wrap max-h-64 overflow-y-auto m-0">{result.output_tail}</pre>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
