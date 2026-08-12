import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Clock, Search, Info, Lightbulb, CheckCircle2, FileText, Terminal,
  Check, Plus, Square, Maximize2, Minimize2, X,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { labApi } from '../../api/labs'
import { vmwareApi } from '../../api/vmware'
import JiraTicketLink from '../JiraTicketLink'
import { ConfirmDialog } from '../ConfirmModal'
import VmwareSshTerminal from './VmwareSshTerminal'

const TOAST = { style: { background: '#1b2a3b', color: '#e8edf2', border: '1px solid #2d3a4a', fontSize: '12px' } }

function formatTimer(seconds) {
  if (seconds == null || seconds < 0) return '--:--'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export default function VmwareLabChrome({
  sessionId,
  searchQuery,
  onSearchChange,
  onFullscreenToggle,
  isFullscreen,
  inventorySearch,
  vms = [],
  summary = null,
}) {
  const navigate = useNavigate()
  const [labSession, setLabSession] = useState(null)
  const [timeRemaining, setTimeRemaining] = useState(null)
  const [hints, setHints] = useState({ revealed: [], total_hints: 0, hints_used: 0, next_available: false })
  const [validationResult, setValidationResult] = useState(null)
  const [validating, setValidating] = useState(false)
  const [vmSummary, setVmSummary] = useState(null)
  const [workflowBusy, setWorkflowBusy] = useState(false)
  const [extending, setExtending] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [showStopConfirm, setShowStopConfirm] = useState(false)
  const [panel, setPanel] = useState(null) // hints | results | info | ticket | ssh
  const [sshVmId, setSshVmId] = useState('')

  const loadSession = useCallback(async () => {
    if (!sessionId) return
    try {
      const status = await labApi.getSessionStatus(sessionId)
      setLabSession(status)
      if (status.time_remaining != null) setTimeRemaining(status.time_remaining)
    } catch {
      /* session may not exist for standalone vmware preview */
    }
  }, [sessionId])

  const loadHints = useCallback(async () => {
    if (!sessionId) return
    try {
      const data = await labApi.getHints(sessionId)
      setHints({
        ...data,
        revealed: (data.revealed || []).map(h => typeof h === 'string' ? { content: h, penalty: 10 } : h),
      })
    } catch { /* ignore */ }
  }, [sessionId])

  const loadVmwareSummary = useCallback(async () => {
    if (!sessionId) return
    try {
      const data = await vmwareApi.getState(sessionId, labSession?.scenario_detail?.slug || labSession?.scenario?.slug || '')
      setVmSummary(data.summary || null)
    } catch { /* preview mode */ }
  }, [sessionId, labSession?.scenario_detail?.slug, labSession?.scenario?.slug])

  useEffect(() => { loadSession(); loadHints() }, [loadSession, loadHints])
  useEffect(() => { loadVmwareSummary() }, [loadVmwareSummary, labSession?.id])

  useEffect(() => {
    if (timeRemaining == null || timeRemaining <= 0) return
    const t = setInterval(() => setTimeRemaining(v => (v != null && v > 0 ? v - 1 : 0)), 1000)
    return () => clearInterval(t)
  }, [timeRemaining != null && timeRemaining > 0])

  const timerUrgent = timeRemaining != null && timeRemaining < 300
  const timerStyle = timerUrgent
    ? { background: 'rgba(217,83,79,.14)', border: '1px solid rgba(217,83,79,.45)', color: '#f08080' }
    : { background: 'rgba(45,124,255,.12)', border: '1px solid rgba(45,124,255,.35)', color: '#5b9bf5' }

  const handleValidate = async () => {
    if (!sessionId) return
    setValidating(true)
    try {
      const result = await labApi.validateLab(sessionId)
      setValidationResult(result)
      setPanel('results')
      await loadVmwareSummary()
      if (result.passed) {
        toast.success(result.message || `Challenge solved! Score: ${result.score}`, { duration: 6000, ...TOAST })
      } else {
        toast('Validation failed — keep trying!', { icon: '🔍', ...TOAST })
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Validation error', TOAST)
    } finally {
      setValidating(false)
    }
  }

  const handleRevealHint = async () => {
    if (!sessionId) return
    try {
      const result = await labApi.revealHint(sessionId)
      setHints(prev => ({
        ...prev,
        revealed: [...(prev.revealed || []), result.hint || { content: '', penalty: 10 }],
        hints_used: result.hints_used,
        next_available: result.hints_used < (result.total_hints ?? prev.total_hints),
        total_hints: result.total_hints ?? prev.total_hints,
      }))
      setPanel('hints')
    } catch (err) {
      toast.error(err.response?.data?.error || 'No more hints', TOAST)
    }
  }

  const handleExtend = async () => {
    if (!sessionId || extending) return
    setExtending(true)
    try {
      const res = await labApi.extendLab(sessionId)
      setTimeRemaining(res.time_remaining)
      toast.success(`+30 min added. ${res.extensions_remaining} extension(s) remaining today.`, TOAST)
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not extend lab', TOAST)
    } finally {
      setExtending(false)
    }
  }

  const handleWorkflowAction = async (action) => {
    if (!sessionId || workflowBusy) return
    setWorkflowBusy(true)
    try {
      await vmwareApi.action(sessionId, action, {})
      await loadVmwareSummary()
      toast.success(action === 'mark_jira_updated' ? 'Jira incident updated' : 'Customer approved reboot', TOAST)
    } catch (err) {
      toast.error(err.response?.data?.error || 'Action failed', TOAST)
    } finally {
      setWorkflowBusy(false)
    }
  }

  const handleStop = async () => {
    if (!sessionId || stopping) return
    setShowStopConfirm(true)
  }

  const confirmStop = async () => {
    if (!sessionId || stopping) return
    setStopping(true)
    try {
      await labApi.stopLab(sessionId)
      toast.success('Lab stopped', TOAST)
      navigate('/scenarios')
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to stop lab', TOAST)
    } finally {
      setStopping(false)
      setShowStopConfirm(false)
    }
  }

  const scenario = labSession?.scenario_detail || labSession?.scenario || {}
  const jiraKey = labSession?.jira_issue_key
  const sshVm = vms.find(v => v.id === sshVmId) || vms.find(v => v.power === 'poweredOn') || vms[0]
  const sshOk = summary?.linux_ssh_ok !== false && !sshVm?.guest_hung

  useEffect(() => {
    if (sshVm && !sshVmId) setSshVmId(sshVm.id)
  }, [sshVm?.id, sshVmId])

  return (
    <>
      <header className="vm-toolbar">
        <span className="font-bold text-[15px] tracking-tight text-white whitespace-nowrap shrink-0">
          <span className="vm-logo-vm">vm</span>ware{' '}
          <span className="vm-logo-vsphere">vSphere</span>
        </span>

        <div className="w-px h-[22px] bg-[#2d3a4a] shrink-0" />

        <div className="vm-toolbar-search relative">
          <Search size={13} className="absolute left-[9px] top-1/2 -translate-y-1/2 text-[#8fa5b8] pointer-events-none" />
          <input
            type="text"
            placeholder="Search inventory…"
            value={inventorySearch ?? searchQuery ?? ''}
            onChange={e => (onSearchChange || (() => {}))(e.target.value)}
          />
        </div>

        <div className="w-px h-[22px] bg-[#2d3a4a] shrink-0" />

        {sessionId && (
          <span className="vm-timer" style={timerStyle}>
            <Clock size={14} />
            {formatTimer(timeRemaining)}
          </span>
        )}

        {jiraKey && (
          <span className="vm-jira-badge">
            <FileText size={12} fill="#2D7CFF" stroke="none" />
            <JiraTicketLink
              issueKey={jiraKey}
              issueUrl={labSession?.jira_issue_url || `/jira/${jiraKey}`}
              className="text-[11.5px] font-bold text-[#5b9bf5] hover:underline"
            />
          </span>
        )}

        <button type="button" className="vm-toolbar-btn w-[30px] h-[30px] p-0 justify-center" onClick={() => setPanel('info')} aria-label="Lab info">
          <Info size={15} />
        </button>

        {sessionId && (
          <>
            <button type="button" className="vm-toolbar-btn" onClick={() => setPanel('hints')}>
              <Lightbulb size={13} className="text-[#F5A623]" />
              Hints ({hints.hints_used || 0}/{hints.total_hints || 3})
            </button>
            <button type="button" className="vm-toolbar-btn" onClick={() => setPanel('results')}>
              <CheckCircle2 size={13} className="text-[#5DB85D]" />
              Results
            </button>
            {jiraKey && (
              <button type="button" className="vm-toolbar-btn" onClick={() => setPanel('ticket')}>
                <FileText size={13} className="text-[#2D7CFF]" />
                Incident ticket
              </button>
            )}
          </>
        )}

        <button type="button" className="vm-toolbar-btn" onClick={() => setPanel('ssh')}>
          <Terminal size={13} className="text-[#5DB85D]" />
          SSH
        </button>

        <div className="flex-1 min-w-[8px]" />

        {sessionId && (
          <>
            <button type="button" className="vm-toolbar-btn vm-toolbar-btn-primary" onClick={handleValidate} disabled={validating}>
              <Check size={14} strokeWidth={2.4} />
              {validating ? 'Checking…' : 'Check'}
            </button>
            <button type="button" className="vm-toolbar-btn" onClick={handleExtend} disabled={extending}>
              <Plus size={13} />
              +30m
            </button>
          </>
        )}

        <button type="button" className="vm-toolbar-btn w-8 h-8 p-0 justify-center" onClick={onFullscreenToggle} aria-label="Fullscreen">
          {isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
        </button>

        {sessionId && (
          <button type="button" className="vm-toolbar-btn vm-toolbar-btn-danger" onClick={handleStop} disabled={stopping}>
            <Square size={13} fill="currentColor" stroke="none" />
            Stop
          </button>
        )}

        <Link to={sessionId ? `/lab/${sessionId}` : '/scenarios'} className="vm-toolbar-btn text-[#8fa5b8] hover:text-white ml-1">
          ← Lab
        </Link>
      </header>

      {/* Hints drawer — Claude mockup with penalty cards */}
      {panel === 'hints' && (
        <SidePanel title="Hints" onClose={() => setPanel(null)}>
          <div className="space-y-3">
            {Array.from({ length: hints.total_hints || 3 }).map((_, i) => {
              const revealed = hints.revealed?.[i]
              const isLocked = i >= (hints.hints_used || 0)
              const penalty = revealed?.penalty ?? [10, 15, 20][i] ?? 10
              if (isLocked && !revealed) {
                return (
                  <div key={i} className="rounded-[10px] p-3.5 border border-dashed border-[#3D5A73] bg-transparent">
                    <button
                      type="button"
                      onClick={handleRevealHint}
                      disabled={i !== hints.hints_used}
                      className="w-full text-left text-xs font-semibold text-[#8FA5B8] disabled:opacity-40 hover:text-[#E8EDF2]"
                    >
                      Reveal hint {i + 1} (−{penalty} pts)
                    </button>
                  </div>
                )
              }
              return (
                <div key={i} className="rounded-[10px] p-3.5 bg-[rgba(245,166,35,.08)] border border-[rgba(245,166,35,.25)]">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <span className="text-[10px] font-bold text-[#F5A623] uppercase">Hint {i + 1}</span>
                    <span className="text-[10px] text-[#8FA5B8]">−{penalty} pts</span>
                  </div>
                  <p className="text-[12.5px] leading-relaxed text-[#E8EDF2] m-0">
                    {typeof revealed === 'string' ? revealed : revealed?.content || revealed?.text || ''}
                  </p>
                </div>
              )
            })}
          </div>
          {hints.next_available !== false && hints.hints_used < (hints.total_hints || 3) && (
            <button type="button" className="vm-btn vm-btn-green mt-4 w-full justify-center" onClick={handleRevealHint}>
              Reveal next hint
            </button>
          )}
        </SidePanel>
      )}

      {/* Results drawer */}
      {panel === 'results' && (
        <SidePanel title="Validation results" onClose={() => setPanel(null)}>
          {!validationResult ? (
            <p className="text-[#8fa5b8] text-sm">Run Check to validate your fix.</p>
          ) : (
            <div className="space-y-3">
              <div className={`vm-state-badge ${validationResult.passed ? 'bg-[rgba(93,184,93,.15)] text-[#5DB85D]' : 'bg-[rgba(217,83,79,.15)] text-[#D9534F]'}`}>
                {validationResult.passed ? '✓ Passed' : '✗ Failed'}
                {validationResult.score != null && ` — Score: ${validationResult.score}`}
              </div>
              <p className="text-sm text-[#e8edf2]">{validationResult.message || validationResult.detail}</p>
              {validationResult.checks?.length > 0 && (
                <ul className="space-y-1.5 text-xs">
                  {validationResult.checks.map((c, i) => (
                    <li key={i} className={c.passed ? 'text-[#5DB85D]' : 'text-[#D9534F]'}>
                      {c.passed ? '✓' : '✗'} {c.name || c.message}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          <button type="button" className="vm-btn vm-btn-green mt-4 w-full justify-center" onClick={handleValidate} disabled={validating}>
            {validating ? 'Checking…' : 'Run validation again'}
          </button>
        </SidePanel>
      )}

      {/* Info drawer */}
      {panel === 'info' && (
        <SidePanel title="Lab information" onClose={() => setPanel(null)}>
          <div className="space-y-2 text-sm">
            <p className="text-white font-semibold">{scenario.title || 'VMware lab'}</p>
            <p className="text-[#8fa5b8]">{scenario.description || 'Practice vSphere troubleshooting in a hands-on lab environment.'}</p>
            {scenario.difficulty && (
              <p className="text-xs"><span className="text-[#8fa5b8]">Difficulty:</span> {scenario.difficulty}</p>
            )}
            {scenario.technology?.name && (
              <p className="text-xs"><span className="text-[#8fa5b8]">Technology:</span> {scenario.technology.name}</p>
            )}
          </div>
        </SidePanel>
      )}

      {/* Jira ticket drawer */}
      {panel === 'ticket' && jiraKey && (
        <SidePanel title="Incident ticket" onClose={() => setPanel(null)}>
          <JiraTicketLink issueKey={jiraKey} issueUrl={labSession?.jira_issue_url} className="text-[#5b9bf5] font-bold text-lg" />
          <p className="text-sm text-[#8fa5b8] mt-3">Track this incident in Jira. Document console findings and coordinate customer approval before rebooting a hung guest.</p>
          {vmSummary?.linux_ssh_ok === false && (
            <div className="mt-4 space-y-2">
              <button type="button" className="vm-btn vm-btn-blue w-full justify-center" disabled={workflowBusy || vmSummary?.jira_incident_updated} onClick={() => handleWorkflowAction('mark_jira_updated')}>
                {vmSummary?.jira_incident_updated ? '✓ Jira updated' : 'Update Jira with console findings'}
              </button>
              <button type="button" className="vm-btn vm-btn-green w-full justify-center" disabled={workflowBusy || !vmSummary?.jira_incident_updated || vmSummary?.customer_reboot_approved} onClick={() => handleWorkflowAction('confirm_customer_reboot')}>
                {vmSummary?.customer_reboot_approved ? '✓ Customer approved reboot' : 'Confirm customer reboot approval'}
              </button>
            </div>
          )}
          <Link to={labSession?.jira_issue_url || `/jira/${jiraKey}`} className="vm-btn vm-btn-blue mt-4 inline-flex">
            Open ticket
          </Link>
        </SidePanel>
      )}

      {/* SSH — full console-style window (modal overlay, minimize/maximize),
          not a cramped drawer panel. */}
      {panel === 'ssh' && (
        sshVm ? (
          <>
            {vms.length > 1 && (
              <div className="fixed top-3 left-1/2 -translate-x-1/2 z-[110] flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1b2a3b] border border-[#2d3a4a] shadow-xl">
                <label className="text-[10px] text-[#8fa5b8] uppercase tracking-wide">SSH target</label>
                <select value={sshVmId || sshVm?.id || ''} onChange={e => setSshVmId(e.target.value)} className="vm-input !pl-2 !py-1 text-xs min-w-[180px]">
                  {vms.map(v => (
                    <option key={v.id} value={v.id}>{v.name} ({v.ip || 'no IP'})</option>
                  ))}
                </select>
              </div>
            )}
            <VmwareSshTerminal key={sshVm.id} vm={sshVm} labSessionId={sessionId} sshOk={sshOk} onClose={() => setPanel(null)} />
          </>
        ) : (
          <SidePanel title="SSH console" onClose={() => setPanel(null)}>
            <p className="text-[#8fa5b8] text-sm">No VMs in inventory.</p>
          </SidePanel>
        )
      )}
      <ConfirmDialog
        open={showStopConfirm}
        onClose={() => !stopping && setShowStopConfirm(false)}
        title="Stop lab?"
        message="Stop this lab session? Progress will be saved."
        confirmLabel="Stop lab"
        danger
        loading={stopping}
        onConfirm={confirmStop}
      />
    </>
  )
}

function SidePanel({ title, children, onClose }) {
  return (
    <div className="vm-drawer">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#2d3a4a] bg-[#243447]">
        <h3 className="font-bold text-sm text-white">{title}</h3>
        <button type="button" onClick={onClose} className="p-1 min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-[#8fa5b8] hover:text-white rounded" aria-label="Close panel">
          <X size={18} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4">{children}</div>
    </div>
  )
}
