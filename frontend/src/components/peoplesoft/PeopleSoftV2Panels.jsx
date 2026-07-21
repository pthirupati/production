import { peoplesoftApi } from '../../api/peoplesoft'

const PS_BLUE = '#1b3a5c'

/** Query Manager, PeopleCode, GL, AP/AR, Payroll — V2 PIA blades. */
export function renderPeopleSoftV2Page({ section, v2 = {}, sessionId, busy, run }) {
  if (section === 'query') {
    const queries = v2.queries || []
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-sm font-semibold text-slate-700">Query Manager</h2>
          <button type="button" disabled={busy} className="text-xs px-3 py-1.5 rounded text-white" style={{ background: PS_BLUE }}
            onClick={() => run(() => peoplesoftApi.createQuery(sessionId, {
              name: `QRY_FIXIT_${Date.now().toString(36).slice(-4).toUpperCase()}`,
              records: ['JOB', 'PERSONAL_DATA'],
              fields: ['EMPLID', 'NAME', 'DEPTID'],
            }), 'Query saved')}>
            Create query
          </button>
        </div>
        <Table head={['Name', 'Owner', 'Records', 'Last run', 'Rows', '']}>
          {queries.map((q) => (
            <tr key={q.id} className="border-t border-slate-100">
              <td className="px-3 py-2 font-mono text-xs">{q.name}</td>
              <td className="px-3 py-2">{q.owner}</td>
              <td className="px-3 py-2 text-xs">{(q.records || []).join(', ')}</td>
              <td className="px-3 py-2 text-xs text-slate-500">{q.last_run || '—'}</td>
              <td className="px-3 py-2">{q.row_count || 0}</td>
              <td className="px-3 py-2 text-right">
                <button type="button" disabled={busy} className="text-xs px-2 py-1 rounded border border-slate-200 hover:bg-slate-50"
                  onClick={() => run(() => peoplesoftApi.runQuery(sessionId, q.id), `Ran ${q.name}`)}>
                  Run
                </button>
              </td>
            </tr>
          ))}
        </Table>
        {queries.some((q) => q.preview?.length) && (
          <div>
            <div className="text-xs font-semibold text-slate-500 mb-1">Preview results</div>
            <Table head={Object.keys(queries.find((q) => q.preview?.length)?.preview[0] || {})}>
              {(queries.find((q) => q.preview?.length)?.preview || []).map((row, i) => (
                <tr key={i} className="border-t border-slate-100">
                  {Object.values(row).map((v, j) => <td key={j} className="px-3 py-2 text-xs">{String(v)}</td>)}
                </tr>
              ))}
            </Table>
          </div>
        )}
      </div>
    )
  }

  if (section === 'peoplecode') {
    const pcs = v2.peoplecode || []
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-sm font-semibold text-slate-700">Application Designer — PeopleCode</h2>
          <button type="button" disabled={busy} className="text-xs px-3 py-1.5 rounded text-white" style={{ background: PS_BLUE }}
            onClick={() => run(() => peoplesoftApi.savePeopleCode(sessionId, {
              object: 'JOB.EFFDT.FieldChange',
              body: "Function EffDtCheck()\n   If None(JOB.EFFDT) Then\n      Error \"Effective date required\";\n   End-If;\nEnd-Function;\n",
            }), 'PeopleCode saved')}>
            Save sample PeopleCode
          </button>
        </div>
        {pcs.map((pc) => (
          <div key={pc.id} className="bg-white border border-slate-200 rounded overflow-hidden">
            <div className="px-3 py-2 text-xs font-medium border-b border-slate-100 flex justify-between">
              <span className="font-mono">{pc.object}</span>
              <span className={pc.validated ? 'text-emerald-600' : 'text-amber-600'}>{pc.validated ? 'Validated' : 'Needs review'}</span>
            </div>
            <pre className="p-3 text-xs font-mono bg-slate-50 overflow-x-auto whitespace-pre-wrap">{pc.body}</pre>
          </div>
        ))}
      </div>
    )
  }

  if (section === 'gl') {
    const journals = v2.journals || []
    const tb = v2.trial_balance || []
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-sm font-semibold text-slate-700">General Ledger — Journals</h2>
          <button type="button" disabled={busy} className="text-xs px-3 py-1.5 rounded text-white" style={{ background: PS_BLUE }}
            onClick={() => run(() => peoplesoftApi.createJournal(sessionId, { post: true }), 'Journal posted')}>
            Create & post journal
          </button>
        </div>
        <Table head={['Journal', 'BU', 'Date', 'Ledger', 'Status', 'Balanced']}>
          {journals.map((j) => (
            <tr key={j.id} className="border-t border-slate-100">
              <td className="px-3 py-2 font-mono text-xs">{j.id}</td>
              <td className="px-3 py-2">{j.business_unit}</td>
              <td className="px-3 py-2">{j.journal_date}</td>
              <td className="px-3 py-2">{j.ledger}</td>
              <td className="px-3 py-2">{j.status}</td>
              <td className="px-3 py-2">{j.balanced ? 'Yes' : 'No'}</td>
            </tr>
          ))}
        </Table>
        <div>
          <div className="text-xs font-semibold text-slate-500 mb-1">Trial balance</div>
          <Table head={['Account', 'Description', 'Debit', 'Credit']}>
            {tb.map((r) => (
              <tr key={r.account} className="border-t border-slate-100">
                <td className="px-3 py-2 font-mono">{r.account}</td>
                <td className="px-3 py-2">{r.descr}</td>
                <td className="px-3 py-2 text-right">{r.debit?.toLocaleString?.() ?? r.debit}</td>
                <td className="px-3 py-2 text-right">{r.credit?.toLocaleString?.() ?? r.credit}</td>
              </tr>
            ))}
          </Table>
        </div>
      </div>
    )
  }

  if (section === 'ap') {
    const vouchers = v2.vouchers || []
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-sm font-semibold text-slate-700">Accounts Payable — Vouchers</h2>
          <button type="button" disabled={busy} className="text-xs px-3 py-1.5 rounded text-white" style={{ background: PS_BLUE }}
            onClick={() => run(() => peoplesoftApi.createVoucher(sessionId, {
              vendor: 'ACME CONSULTING', gross: 2500,
            }), 'Voucher created')}>
            Enter voucher
          </button>
        </div>
        <Table head={['Voucher', 'Vendor', 'Invoice', 'Gross', 'Status', 'Due']}>
          {vouchers.map((v) => (
            <tr key={v.id} className="border-t border-slate-100">
              <td className="px-3 py-2 font-mono text-xs">{v.id}</td>
              <td className="px-3 py-2">{v.vendor}</td>
              <td className="px-3 py-2">{v.invoice}</td>
              <td className="px-3 py-2 text-right">{Number(v.gross).toLocaleString()}</td>
              <td className="px-3 py-2">{v.status}</td>
              <td className="px-3 py-2">{v.due_date}</td>
            </tr>
          ))}
        </Table>
      </div>
    )
  }

  if (section === 'ar') {
    const invoices = v2.ar_invoices || []
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-sm font-semibold text-slate-700">Accounts Receivable — Invoices</h2>
          <button type="button" disabled={busy} className="text-xs px-3 py-1.5 rounded text-white" style={{ background: PS_BLUE }}
            onClick={() => run(() => peoplesoftApi.createArInvoice(sessionId, {
              customer: 'CONTOSO LTD', amount: 1500,
            }), 'Invoice created')}>
            Create invoice
          </button>
        </div>
        <Table head={['Invoice', 'Customer', 'Amount', 'Status', 'Aging']}>
          {invoices.map((inv) => (
            <tr key={inv.id} className="border-t border-slate-100">
              <td className="px-3 py-2 font-mono text-xs">{inv.id}</td>
              <td className="px-3 py-2">{inv.customer}</td>
              <td className="px-3 py-2 text-right">{Number(inv.amount).toLocaleString()}</td>
              <td className="px-3 py-2">{inv.status}</td>
              <td className="px-3 py-2">{inv.aging_bucket}</td>
            </tr>
          ))}
        </Table>
      </div>
    )
  }

  if (section === 'payroll_admin') {
    const runs = v2.pay_runs || []
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-sm font-semibold text-slate-700">Payroll for North America</h2>
          <div className="flex gap-2">
            <button type="button" disabled={busy} className="text-xs px-3 py-1.5 rounded border border-slate-200 hover:bg-slate-50"
              onClick={() => run(() => peoplesoftApi.runPayroll(sessionId, {}), 'Pay calculated')}>
              Calculate
            </button>
            <button type="button" disabled={busy} className="text-xs px-3 py-1.5 rounded text-white" style={{ background: PS_BLUE }}
              onClick={() => run(() => peoplesoftApi.runPayroll(sessionId, { confirm: true }), 'Pay confirmed')}>
              Confirm pay
            </button>
          </div>
        </div>
        <Table head={['Pay run', 'Group', 'Period end', 'Status', 'Employees', 'Gross', 'Net']}>
          {runs.map((r) => (
            <tr key={r.id} className="border-t border-slate-100">
              <td className="px-3 py-2 font-mono text-xs">{r.id}</td>
              <td className="px-3 py-2">{r.pay_group}</td>
              <td className="px-3 py-2">{r.period_end}</td>
              <td className="px-3 py-2">{r.status}</td>
              <td className="px-3 py-2">{r.employees}</td>
              <td className="px-3 py-2 text-right">{Number(r.gross).toLocaleString()}</td>
              <td className="px-3 py-2 text-right">{Number(r.net).toLocaleString()}</td>
            </tr>
          ))}
        </Table>
      </div>
    )
  }

  return null
}

function Table({ head, children }) {
  return (
    <div className="bg-white rounded border border-slate-200 overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-50 text-slate-500 text-xs">
            {head.map((h, i) => <th key={i} className="px-3 py-2 text-left font-medium">{h}</th>)}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}
