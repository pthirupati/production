import { useState } from 'react'
import { ChevronLeft, ChevronRight, Search, Save, Plus, Minus } from 'lucide-react'
import {
  PS_FLUID_TILES, PS_JOB_DATA, PS_BENEFITS_STEPS, PS_HEALTH_PLANS, PS_PAYCHECK, PS_PROCESS_INSTANCES,
} from '../../mockData/peoplesoft'
import { SimStatusBadge } from '../sim/shared'

const PS_BLUE = '#1b3a5c'
const PS_RED = '#c74634'

export function FluidHome({ onNavigate }) {
  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-800 mb-4">Homepage</h2>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {PS_FLUID_TILES.map((t) => (
          <button key={t.id} type="button" onClick={() => onNavigate(t.id)}
            className="ps-tile text-left rounded-lg border border-slate-200 bg-white p-4 hover:shadow-md hover:border-[#c74634]/40 transition-all">
            <div className="text-2xl mb-2">{t.icon}</div>
            <div className="font-semibold text-slate-800">{t.title}</div>
            <div className="text-xs text-slate-500 mt-0.5">{t.subtitle}</div>
          </button>
        ))}
      </div>
    </div>
  )
}

// Map an engine self-service profile (snake_case job dict) onto the shape the
// Job Data page renders. Falls back to the static mock when no profile is passed.
function resolveJobData(profile) {
  const j = profile?.job || {}
  return {
    emplId: profile?.empl_id || PS_JOB_DATA.emplId,
    name: profile?.name || PS_JOB_DATA.name,
    effectiveDate: j.effective_date || PS_JOB_DATA.effectiveDate,
    company: j.company || PS_JOB_DATA.company,
    businessUnit: j.business_unit || PS_JOB_DATA.businessUnit,
    department: j.department || PS_JOB_DATA.department,
    location: j.location || PS_JOB_DATA.location,
    jobCode: j.job_code || PS_JOB_DATA.jobCode,
    jobTitle: j.job_title || 'Systems Administrator',
    reportsTo: j.reports_to || 'IT Director',
    fte: j.fte || '1.0',
    payGroup: j.pay_group || 'MONTHLY',
    taxLocation: j.tax_location || 'IN-HYD',
    payFrequency: j.pay_frequency || 'Semi-monthly',
    salaryPlan: j.salary_plan || PS_JOB_DATA.salaryPlan,
    grade: j.grade || 'G12',
    compRate: j.comp_rate || '₹85,000/mo',
    benefitsProgram: j.benefits_program || 'FIXIT-IND',
    status: j.status || PS_JOB_DATA.status,
    hireDate: j.hire_date || '2022-03-15',
    serviceDate: j.service_date || '2022-03-15',
    regTemp: j.reg_temp || 'Regular',
  }
}

export function JobDataComponent({ profile, oprid, onSave, busy }) {
  const [tab, setTab] = useState('work')
  const j = resolveJobData(profile)
  const tabs = ['Work Location', 'Job Information', 'Payroll', 'Salary Plan', 'Benefits Program', 'Employment Data']
  const tabKey = (t) => t.toLowerCase().split(' ')[0]

  const fieldsByTab = {
    work: [['Company', j.company], ['Business Unit', j.businessUnit], ['Department', j.department], ['Location', j.location]],
    job: [['Job Code', j.jobCode], ['Job Title', j.jobTitle], ['Reports To', j.reportsTo], ['FTE', j.fte]],
    payroll: [['Pay Group', j.payGroup], ['Tax Location', j.taxLocation], ['Pay Frequency', j.payFrequency]],
    salary: [['Salary Plan', j.salaryPlan], ['Grade', j.grade], ['Comp Rate', j.compRate]],
    benefits: [['Benefits Program', j.benefitsProgram], ['Eligibility', j.status], ['Event', 'Open Enrollment']],
    employment: [['Status', j.status], ['Hire Date', j.hireDate], ['Service Date', j.serviceDate], ['Reg Temp', j.regTemp]],
  }
  const fields = fieldsByTab[tab] || fieldsByTab.work

  return (
    <div className="bg-white border border-slate-200 rounded shadow-sm">
      <div className="px-4 py-2 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2 bg-[#f8f9fa]">
        <div className="flex items-center gap-2 text-sm">
          <button type="button" className="p-1 rounded hover:bg-slate-200"><ChevronLeft size={16} /></button>
          <button type="button" className="p-1 rounded hover:bg-slate-200"><ChevronRight size={16} /></button>
          <span className="font-semibold text-slate-700">Job Data</span>
          <span className="text-slate-400">·</span>
          <span className="text-slate-600">{j.emplId} — {j.name}{oprid ? ` (${oprid})` : ''}</span>
        </div>
        <div className="flex gap-1">
          <button type="button" className="text-xs px-2 py-1 border rounded bg-white hover:bg-slate-50 flex items-center gap-1"><Plus size={12} /> Add</button>
          <button type="button" disabled={busy} onClick={() => onSave?.()}
            className="text-xs px-2 py-1 border rounded text-white flex items-center gap-1 disabled:opacity-50" style={{ background: PS_BLUE }}><Save size={12} /> Save</button>
        </div>
      </div>
      <div className="px-4 py-2 text-xs text-slate-500 border-b flex items-center gap-2">
        <span>Effective Date:</span>
        <input type="date" defaultValue={j.effectiveDate} className="border rounded px-2 py-0.5 text-slate-700" />
        <span className="ml-4">Seq:</span><span className="font-mono">0</span>
      </div>
      <div className="flex border-b overflow-x-auto">
        {tabs.map((t) => (
          <button key={t} type="button" onClick={() => setTab(tabKey(t))}
            className={`px-4 py-2 text-xs whitespace-nowrap border-b-2 ${tab === tabKey(t) ? 'border-[#c74634] text-[#c74634] font-semibold' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>
            {t}
          </button>
        ))}
      </div>
      <div className="p-4 grid sm:grid-cols-2 gap-4 text-sm">
        {fields.map(([label, val]) => (
          <label key={label} className="block">
            <span className="text-[11px] uppercase text-slate-500 tracking-wide">{label}</span>
            <div className="mt-1 flex items-center gap-1">
              <input readOnly value={val} className="flex-1 border border-slate-300 rounded px-2 py-1.5 bg-slate-50 text-slate-800" />
              {label === 'Department' && <button type="button" className="p-1.5 border rounded hover:bg-slate-100" title="Prompt"><Search size={14} /></button>}
            </div>
          </label>
        ))}
      </div>
    </div>
  )
}

export function BenefitsEnrollment({ profile, plans, steps, onSubmit, busy }) {
  const stepList = (steps && steps.length) ? steps : PS_BENEFITS_STEPS
  const planList = (plans && plans.length) ? plans : PS_HEALTH_PLANS
  const ben = profile?.benefits || {}
  const [step, setStep] = useState(0)
  const [plan, setPlan] = useState(ben.elected_plan || planList[0]?.id || 'ppo')
  const submitted = ben.event_status === 'Submitted'
  const current = stepList[step] || stepList[0]
  const isLast = step === stepList.length - 1
  return (
    <div className="flex gap-4 min-h-[420px]">
      <aside className="w-48 shrink-0 bg-white border border-slate-200 rounded p-3">
        <div className="text-xs font-semibold text-slate-500 uppercase mb-2">Open Enrollment</div>
        {stepList.map((s, i) => (
          <button key={s.key} type="button" onClick={() => setStep(i)}
            className={`w-full text-left text-xs py-2 px-2 rounded mb-0.5 ${i === step ? 'bg-[#c74634]/10 text-[#c74634] font-semibold' : 'text-slate-600 hover:bg-slate-50'}`}>
            {i + 1}. {s.label}
          </button>
        ))}
        {submitted && (
          <div className="mt-3 text-[11px] px-2 py-1 rounded bg-green-50 text-green-700 border border-green-200">
            Submitted{ben.submitted_plan ? ` · ${planList.find((p) => p.id === ben.submitted_plan)?.name || ben.submitted_plan}` : ''}
          </div>
        )}
      </aside>
      <div className="flex-1 bg-white border border-slate-200 rounded p-5">
        <h3 className="font-semibold text-slate-800 mb-4">{current.label}</h3>
        {current.key === 'health' && (
          <div className="grid md:grid-cols-3 gap-3">
            {planList.map((p) => (
              <label key={p.id} className={`block border rounded-lg p-4 cursor-pointer ${plan === p.id ? 'border-[#c74634] ring-2 ring-[#c74634]/20' : 'border-slate-200 hover:border-slate-300'}`}>
                <input type="radio" name="plan" className="sr-only" checked={plan === p.id} onChange={() => setPlan(p.id)} />
                <div className="font-semibold text-slate-800">{p.name}</div>
                <div className="text-xs text-slate-500 mt-2 space-y-1">
                  <div>Deductible: {p.deductible}</div>
                  <div>OOP max: {p.oop}</div>
                  <div className="font-semibold text-[#c74634]">{p.premium}</div>
                </div>
              </label>
            ))}
          </div>
        )}
        {current.key !== 'health' && current.key !== 'review' && (
          <p className="text-sm text-slate-500">Complete the {current.label.toLowerCase()} section for this enrollment event.</p>
        )}
        {current.key === 'review' && (
          <div className="text-sm space-y-2">
            <p>Selected medical plan: <strong>{planList.find((p) => p.id === plan)?.name}</strong></p>
            <p className="text-slate-500">Click Submit to finalize open enrollment. This queues a BEN_ENROLL process on the Process Scheduler.</p>
          </div>
        )}
        <div className="flex justify-between mt-6 pt-4 border-t">
          <button type="button" disabled={step === 0} onClick={() => setStep((s) => s - 1)} className="text-sm px-3 py-1.5 border rounded disabled:opacity-40">Previous</button>
          <button type="button" disabled={busy}
            onClick={() => { if (isLast) onSubmit?.(plan); else setStep((s) => Math.min(s + 1, stepList.length - 1)) }}
            className="text-sm px-4 py-1.5 rounded text-white disabled:opacity-50" style={{ background: PS_RED }}>
            {isLast ? (submitted ? 'Resubmit' : 'Submit') : 'Continue'}
          </button>
        </div>
      </div>
    </div>
  )
}

// Normalize an engine paycheck (snake_case) onto the mock's camelCase shape.
function resolvePaycheck(profile) {
  const p = profile?.paycheck
  if (!p) return PS_PAYCHECK
  return {
    company: p.company ?? PS_PAYCHECK.company,
    periodStart: p.period_start ?? PS_PAYCHECK.periodStart,
    periodEnd: p.period_end ?? PS_PAYCHECK.periodEnd,
    payDate: p.pay_date ?? PS_PAYCHECK.payDate,
    earnings: p.earnings ?? PS_PAYCHECK.earnings,
    taxes: p.taxes ?? PS_PAYCHECK.taxes,
    deductions: p.deductions ?? PS_PAYCHECK.deductions,
    netPay: p.net_pay ?? PS_PAYCHECK.netPay,
    ytdNet: p.ytd_net ?? PS_PAYCHECK.ytdNet,
    deposit: p.deposit ?? PS_PAYCHECK.deposit,
  }
}

export function PaycheckReview({ profile, onReprint, busy }) {
  const p = resolvePaycheck(profile)
  return (
    <div className="max-w-2xl mx-auto bg-white border border-slate-200 rounded shadow-sm overflow-hidden">
      <div className="px-6 py-4 text-center border-b" style={{ background: PS_BLUE, color: '#fff' }}>
        <div className="font-semibold">{p.company}</div>
        <div className="text-xs opacity-90 mt-1">Pay Period {p.periodStart} — {p.periodEnd} · Pay Date {p.payDate}</div>
      </div>
      <div className="p-6 space-y-4 text-sm">
        <table className="w-full">
          <thead><tr className="text-xs text-slate-500 border-b"><th className="text-left py-1">Earnings</th><th className="text-right">Hours</th><th className="text-right">Amount</th><th className="text-right">YTD</th></tr></thead>
          <tbody>
            {p.earnings.map((e) => (
              <tr key={e.type} className="border-b border-slate-100"><td>{e.type}</td><td className="text-right">{e.hours}</td><td className="text-right">${e.amount.toFixed(2)}</td><td className="text-right text-slate-400">—</td></tr>
            ))}
          </tbody>
        </table>
        <table className="w-full">
          <thead><tr className="text-xs text-slate-500 border-b"><th className="text-left py-1">Taxes & Deductions</th><th className="text-right">Amount</th></tr></thead>
          <tbody>
            {[...p.taxes, ...p.deductions].map((r) => (
              <tr key={r.type} className="border-b border-slate-100"><td>{r.type}</td><td className="text-right text-red-600">${Math.abs(r.amount).toFixed(2)}</td></tr>
            ))}
          </tbody>
        </table>
        <div className="flex justify-between items-center pt-2 border-t-2 border-slate-300 font-semibold text-base">
          <span>Net Pay</span>
          <span style={{ color: PS_RED }}>${p.netPay.toFixed(2)}</span>
        </div>
        <p className="text-xs text-slate-500">Direct deposit to {p.deposit} · YTD net ${p.ytdNet.toLocaleString()}</p>
        {onReprint && (
          <div className="pt-2 border-t flex justify-end">
            <button type="button" disabled={busy} onClick={() => onReprint?.()}
              className="text-xs px-3 py-1.5 rounded text-white disabled:opacity-50 flex items-center gap-1" style={{ background: PS_BLUE }}>
              <Save size={12} /> Reprint Pay Advice
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export function ProcessMonitorTable({ runs = [], onRerun, busy }) {
  const rows = runs.length ? runs : PS_PROCESS_INSTANCES
  return (
    <table className="w-full text-sm bg-white rounded border border-slate-200 overflow-hidden">
      <thead><tr className="bg-slate-50 text-slate-500 text-xs">
        {['Instance', 'Process', 'Description', 'Server', 'Status', 'Run Date/Time', ''].map((h) => <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>)}
      </tr></thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.instance} className="border-t border-slate-100 hover:bg-slate-50">
            <td className="px-3 py-2 font-mono">{r.instance}</td>
            <td className="px-3 py-2 font-mono text-xs">{r.name || r.process}</td>
            <td className="px-3 py-2 text-slate-600">{r.description || r.run_control || '—'}</td>
            <td className="px-3 py-2">{r.server}</td>
            <td className="px-3 py-2"><SimStatusBadge status={(r.status || '').toLowerCase()} label={r.status} /></td>
            <td className="px-3 py-2 text-slate-500 text-xs">{r.runDt || r.run_datetime || '—'}</td>
            <td className="px-3 py-2 text-right">
              {['error', 'cancelled'].includes((r.status || '').toLowerCase()) && onRerun && (
                <button type="button" disabled={busy} onClick={() => onRerun(r.instance)}
                  className="text-xs px-2 py-1 rounded text-white" style={{ background: PS_BLUE }}>Rerun</button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function FluidStubPage({ title, description }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-8 text-center max-w-lg mx-auto">
      <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
      <p className="text-sm text-slate-500 mt-2">{description}</p>
    </div>
  )
}

export function PeopleSoftNavMenu({ open, onClose, menu = [], onSelect }) {
  if (!open) return null
  const pick = (item) => { onSelect?.(item); onClose?.() }
  return (
    <>
      <button type="button" className="fixed inset-0 bg-black/40 z-40" onClick={onClose} aria-label="Close menu" />
      <aside className="fixed inset-y-0 left-0 w-72 bg-white shadow-xl z-50 overflow-y-auto border-r border-slate-200">
        <div className="px-4 py-3 font-semibold text-white" style={{ background: PS_RED }}>Navigator</div>
        {(menu.length ? menu : []).map((section) => (
          <div key={section.label} className="border-b border-slate-100">
            <div className="px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wide">{section.label}</div>
            {(section.items || []).map((item) => (
              <button key={item} type="button" onClick={() => pick(item)}
                className="w-full text-left px-6 py-2 text-sm text-slate-700 hover:bg-slate-50">{item}</button>
            ))}
          </div>
        ))}
      </aside>
    </>
  )
}
