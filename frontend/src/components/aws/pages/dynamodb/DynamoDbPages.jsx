import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Plus, Search, Trash2 } from 'lucide-react'
import { ACCOUNT, useAwsStore, scoped } from '../../store/awsStore'
import { arn } from '../../lib/ids'
import { Badge, Breadcrumb, Button, ConfirmDialog, DataTable, EmptyState, IDCopy, Modal, SectionLabel, Tabs } from '../../ui/primitives'
import MetricChart from '../../ui/MetricChart'
import { BASE } from '../../layout/serviceNav'
import { getResourceConfig } from '../generic/serviceConfigs'

const SERVICE = 'dynamodb'
const RESOURCE = 'tables'
const KEY_TYPES = ['String', 'Number', 'Binary']

function ddbBadge(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'active') return 'available'
  if (s === 'creating' || s === 'updating') return 'pending'
  if (s === 'deleting') return 'stopped'
  return 'available'
}

function keyField(spec) {
  // spec is like "pk (String)" -> "pk"
  return String(spec || '').split(' ')[0]
}

function tableArn(row, region) {
  return arn('dynamodb', region, ACCOUNT, `table/${row.name}`)
}

export function DynamoDbList() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const tables = scoped(useAwsStore((s) => s.genericResources?.dynamodb?.tables), region)
  const deleteGenericResource = useAwsStore((s) => s.deleteGenericResource)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const [selected, setSelected] = useState([])
  const [deleteTarget, setDeleteTarget] = useState(null)

  const columns = [
    { key: 'name', label: 'Table name', render: (r) => <a onClick={() => navigate(`${BASE}/dynamodb/tables/${r.id}`)}>{r.name}</a> },
    { key: 'status', label: 'Status', render: (r) => <Badge state={ddbBadge(r.status)}>{r.status}</Badge> },
    { key: 'partitionKey', label: 'Partition key' },
    { key: 'sortKey', label: 'Sort key', render: (r) => r.sortKey || '—' },
    { key: 'billingMode', label: 'Capacity mode' },
    { key: 'items', label: 'Item count', render: (r) => r.items ?? (r.records || []).length },
  ]

  return (
    <div>
      <Breadcrumb items={[{ label: 'DynamoDB', onClick: () => navigate(`${BASE}/dynamodb/home`) }, { label: 'Tables' }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h1>Tables ({tables.length})</h1>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button disabled={selected.length !== 1} icon={Trash2} onClick={() => setDeleteTarget(tables.find((t) => t.id === selected[0]))}>Delete</Button>
            <Button variant="primary" icon={Plus} onClick={() => navigate(`${BASE}/dynamodb/tables/create`)}>Create table</Button>
          </div>
        </div>
        <DataTable
          columns={columns}
          rows={tables}
          getRowKey={(r) => r.id}
          selectable
          selected={selected}
          onSelect={setSelected}
          onRowClick={(r) => navigate(`${BASE}/dynamodb/tables/${r.id}`)}
          rowActions={(r) => [
            { label: 'View details', onClick: () => navigate(`${BASE}/dynamodb/tables/${r.id}`) },
            { label: 'Explore items', onClick: () => navigate(`${BASE}/dynamodb/tables/${r.id}`) },
            { label: 'Delete', danger: true, onClick: () => setDeleteTarget(r) },
          ]}
          tableId="dynamodb:tables"
          emptyTitle="No tables in this Region"
          emptyBody="Create a table to get started."
        />
      </div>
      {deleteTarget && (
        <ConfirmDialog
          title={`Delete ${deleteTarget.name}?`}
          body={`This permanently removes table ${deleteTarget.name} and all its items from the local DynamoDB simulation.`}
          confirmLabel="Delete"
          confirmText={deleteTarget.name}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => { deleteGenericResource(SERVICE, RESOURCE, deleteTarget.id); pushFlash('success', `Deleting table ${deleteTarget.name}`); setSelected([]); setDeleteTarget(null) }}
        />
      )}
    </div>
  )
}

export function DynamoDbCreate() {
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const tables = scoped(useAwsStore((s) => s.genericResources?.dynamodb?.tables), region)
  const createGenericResource = useAwsStore((s) => s.createGenericResource)
  const pushFlash = useAwsStore((s) => s.pushFlash)

  const [name, setName] = useState('')
  const [pkName, setPkName] = useState('')
  const [pkType, setPkType] = useState('String')
  const [useSort, setUseSort] = useState(false)
  const [skName, setSkName] = useState('')
  const [skType, setSkType] = useState('String')
  const [billingMode, setBillingMode] = useState('On-demand')
  const [rcu, setRcu] = useState(5)
  const [wcu, setWcu] = useState(5)

  const nameError = !name ? '' : !/^[a-zA-Z0-9._-]{3,255}$/.test(name) ? 'Table name must be 3-255 chars: letters, numbers, dot, dash, underscore.' : tables.some((t) => t.name === name) ? 'A table with this name already exists in this Region.' : ''
  const pkError = !pkName ? 'Partition key name is required.' : ''
  const canCreate = !!name && !nameError && !pkError

  const submit = () => {
    const created = createGenericResource(SERVICE, RESOURCE, {
      name,
      partitionKey: `${pkName} (${pkType})`,
      sortKey: useSort && skName ? `${skName} (${skType})` : '',
      billingMode,
      rcu: billingMode === 'Provisioned' ? Number(rcu) : undefined,
      wcu: billingMode === 'Provisioned' ? Number(wcu) : undefined,
      records: [],
      items: 0,
    })
    if (!created || created.ok === false) return
    pushFlash('success', `Creating table ${name}`)
    navigate(`${BASE}/dynamodb/tables/${created.id}`)
  }

  return (
    <div>
      <Breadcrumb items={[{ label: 'DynamoDB', onClick: () => navigate(`${BASE}/dynamodb/home`) }, { label: 'Tables', onClick: () => navigate(`${BASE}/dynamodb/tables`) }, { label: 'Create table' }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <h1 style={{ marginBottom: 16 }}>Create table</h1>
        <div className="aws-card" style={{ marginBottom: 12 }}>
          <SectionLabel>Table details</SectionLabel>
          <label className="aws-label" style={{ marginTop: 10 }}>Table name</label>
          <input className={`aws-input ${nameError ? 'aws-invalid' : ''}`} value={name} onChange={(e) => setName(e.target.value)} placeholder="Orders" style={{ maxWidth: 420 }} />
          {nameError && <div className="aws-field-error">{nameError}</div>}
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12, marginTop: 12 }}>
            <div>
              <label className="aws-label">Partition key</label>
              <input className={`aws-input ${pkError && name ? 'aws-invalid' : ''}`} value={pkName} onChange={(e) => setPkName(e.target.value)} placeholder="pk" />
            </div>
            <div>
              <label className="aws-label">Type</label>
              <select className="aws-input" value={pkType} onChange={(e) => setPkType(e.target.value)}>
                {KEY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>
          <label style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'center' }}>
            <input type="checkbox" checked={useSort} onChange={(e) => setUseSort(e.target.checked)} /> Add sort key
          </label>
          {useSort && (
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12, marginTop: 8 }}>
              <div>
                <label className="aws-label">Sort key</label>
                <input className="aws-input" value={skName} onChange={(e) => setSkName(e.target.value)} placeholder="sk" />
              </div>
              <div>
                <label className="aws-label">Type</label>
                <select className="aws-input" value={skType} onChange={(e) => setSkType(e.target.value)}>
                  {KEY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
            </div>
          )}
        </div>
        <div className="aws-card" style={{ marginBottom: 16 }}>
          <SectionLabel>Table settings</SectionLabel>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 10 }}>
            {['On-demand', 'Provisioned'].map((m) => (
              <label key={m} className="aws-card aws-card-hover" style={{ cursor: 'pointer', borderColor: billingMode === m ? 'var(--aws-orange)' : undefined }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="radio" name="billing" checked={billingMode === m} onChange={() => setBillingMode(m)} />
                  <strong>{m}</strong>
                </div>
                <div className="aws-hint" style={{ marginTop: 6 }}>{m === 'On-demand' ? 'Pay per request. Best for unpredictable workloads.' : 'Provision read/write capacity for predictable workloads.'}</div>
              </label>
            ))}
          </div>
          {billingMode === 'Provisioned' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
              <div>
                <label className="aws-label">Read capacity units (RCU)</label>
                <input type="number" min={1} className="aws-input" value={rcu} onChange={(e) => setRcu(Number(e.target.value))} />
              </div>
              <div>
                <label className="aws-label">Write capacity units (WCU)</label>
                <input type="number" min={1} className="aws-input" value={wcu} onChange={(e) => setWcu(Number(e.target.value))} />
              </div>
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button onClick={() => navigate(`${BASE}/dynamodb/tables`)}>Cancel</Button>
          <Button variant="primary" disabled={!canCreate} onClick={submit}>Create table</Button>
        </div>
      </div>
    </div>
  )
}

export function DynamoDbDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const region = useAwsStore((s) => s.region)
  const table = useAwsStore((s) => (s.genericResources?.dynamodb?.tables || []).find((t) => t.id === id))
  const putDynamoItem = useAwsStore((s) => s.putDynamoItem)
  const deleteDynamoItem = useAwsStore((s) => s.deleteDynamoItem)
  const queryDynamo = useAwsStore((s) => s.queryDynamo)
  const scanDynamo = useAwsStore((s) => s.scanDynamo)
  const deleteGenericResource = useAwsStore((s) => s.deleteGenericResource)
  const pushFlash = useAwsStore((s) => s.pushFlash)
  const cfg = getResourceConfig(SERVICE, RESOURCE)
  const [tab, setTab] = useState('overview')
  const [mode, setMode] = useState('Scan')
  const [queryPk, setQueryPk] = useState('')
  const [rows, setRows] = useState(null) // null = show all records
  const [createItemOpen, setCreateItemOpen] = useState(false)
  const [itemJson, setItemJson] = useState('')
  const [itemError, setItemError] = useState('')
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteItem, setDeleteItem] = useState(null)

  if (!table) return <div className="aws-page"><EmptyState title="Table not found" action={<Button onClick={() => navigate(`${BASE}/dynamodb/tables`)}>Back to tables</Button>} /></div>

  const pkField = keyField(table.partitionKey || 'pk')
  const skField = keyField(table.sortKey || '')
  const records = table.records || []
  const displayed = rows == null ? records : rows

  // Column set = union of all keys across records, PK/SK first.
  const allKeys = Array.from(new Set(displayed.flatMap((r) => Object.keys(r))))
  const orderedKeys = [pkField, ...(skField ? [skField] : []), ...allKeys.filter((k) => k !== pkField && k !== skField)]
  const itemColumns = [
    ...orderedKeys.map((k) => ({ key: k, label: k, render: (r) => (r[k] === undefined ? '—' : String(r[k])) })),
    { key: '__actions', label: '', sortable: false, render: (r) => <Button icon={Trash2} onClick={() => { setDeleteItem(r); }}>Delete</Button> },
  ]

  const runQuery = () => {
    if (mode === 'Scan') { setRows(scanDynamo(table.id)) }
    else { setRows(queryDynamo(table.id, { [pkField]: queryPk })) }
  }

  const openCreateItem = () => {
    const seed = { [pkField]: '' }
    if (skField) seed[skField] = ''
    setItemJson(JSON.stringify(seed, null, 2))
    setItemError('')
    setCreateItemOpen(true)
  }

  const submitItem = () => {
    let parsed
    try { parsed = JSON.parse(itemJson) } catch { setItemError('Item must be valid JSON.'); return }
    if (parsed[pkField] === undefined || parsed[pkField] === '') { setItemError(`Item must include partition key "${pkField}".`); return }
    putDynamoItem(table.id, parsed)
    pushFlash('success', 'Item saved')
    setCreateItemOpen(false)
    setRows(null)
  }

  return (
    <div>
      <Breadcrumb items={[{ label: 'DynamoDB', onClick: () => navigate(`${BASE}/dynamodb/home`) }, { label: 'Tables', onClick: () => navigate(`${BASE}/dynamodb/tables`) }, { label: table.name }]} />
      <div className="aws-page" style={{ paddingTop: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: 10 }}>{table.name} <Badge state={ddbBadge(table.status)}>{table.status}</Badge></h1>
          <Button variant="danger" onClick={() => setDeleteOpen(true)}>Delete table</Button>
        </div>

        <Tabs tabs={[
          { key: 'overview', label: 'Overview' },
          { key: 'items', label: 'Explore items' },
          { key: 'monitor', label: 'Monitor' },
        ]} active={tab} onChange={setTab} />

        <div style={{ marginTop: 16 }}>
          {tab === 'overview' && (
            <div className="aws-card">
              <SectionLabel>General information</SectionLabel>
              <div className="aws-summary-grid" style={{ marginTop: 8 }}>
                <div className="aws-kv"><span className="k">Table name</span><span className="v">{table.name}</span></div>
                <div className="aws-kv"><span className="k">ARN</span><span className="v"><IDCopy value={tableArn(table, region)} /></span></div>
                <div className="aws-kv"><span className="k">Partition key</span><span className="v">{table.partitionKey}</span></div>
                <div className="aws-kv"><span className="k">Sort key</span><span className="v">{table.sortKey || '—'}</span></div>
                <div className="aws-kv"><span className="k">Capacity mode</span><span className="v">{table.billingMode}</span></div>
                {table.billingMode === 'Provisioned' && <div className="aws-kv"><span className="k">RCU / WCU</span><span className="v">{table.rcu ?? 5} / {table.wcu ?? 5}</span></div>}
                <div className="aws-kv"><span className="k">Item count</span><span className="v">{records.length}</span></div>
                <div className="aws-kv"><span className="k">Region</span><span className="v">{table.region || region}</span></div>
              </div>
            </div>
          )}
          {tab === 'items' && (
            <div style={{ display: 'grid', gap: 12 }}>
              <div className="aws-card">
                <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
                  <div>
                    <label className="aws-label">Operation</label>
                    <select className="aws-input" value={mode} onChange={(e) => { setMode(e.target.value); setRows(null) }} style={{ width: 140 }}>
                      <option>Scan</option>
                      <option>Query</option>
                    </select>
                  </div>
                  {mode === 'Query' && (
                    <div>
                      <label className="aws-label">{pkField} =</label>
                      <input className="aws-input" value={queryPk} onChange={(e) => setQueryPk(e.target.value)} placeholder={`e.g. ORDER#1001`} />
                    </div>
                  )}
                  <Button icon={Search} variant="primary" onClick={runQuery}>Run</Button>
                  <Button onClick={() => setRows(null)}>Reset</Button>
                  <div style={{ flex: 1 }} />
                  <Button icon={Plus} onClick={openCreateItem}>Create item</Button>
                </div>
                {rows != null && <div className="aws-hint" style={{ marginTop: 10 }}>{mode} returned <strong>{displayed.length}</strong> item(s).</div>}
              </div>
              <div className="aws-card">
                <DataTable
                  columns={itemColumns}
                  rows={displayed}
                  getRowKey={(r) => `${r[pkField]}#${skField ? r[skField] : ''}`}
                  tableId={`dynamodb:items:${table.id}`}
                  emptyTitle="No items"
                  emptyBody="Create an item or run a scan to see records."
                />
              </div>
            </div>
          )}
          {tab === 'monitor' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
              {(cfg.metrics || []).map((m) => (
                <MetricChart key={m.title} title={m.title} unit={m.unit} color={m.color} base={m.base} variance={m.variance} />
              ))}
            </div>
          )}
        </div>
      </div>

      {createItemOpen && (
        <Modal title="Create item" width={640} onClose={() => setCreateItemOpen(false)}
          footer={<><Button onClick={() => setCreateItemOpen(false)}>Cancel</Button><Button variant="primary" onClick={submitItem}>Create item</Button></>}>
          <div className="aws-hint" style={{ marginBottom: 8 }}>Edit the attributes as JSON. The partition key <span className="aws-mono">{pkField}</span>{skField ? <> and sort key <span className="aws-mono">{skField}</span></> : null} are required.</div>
          <textarea className={`aws-input aws-mono ${itemError ? 'aws-invalid' : ''}`} value={itemJson} onChange={(e) => setItemJson(e.target.value)} spellCheck={false} style={{ minHeight: 220, lineHeight: 1.5, width: '100%', resize: 'vertical' }} />
          {itemError && <div className="aws-field-error">{itemError}</div>}
        </Modal>
      )}
      {deleteItem && (
        <ConfirmDialog
          title="Delete item?"
          body={`This removes the item with ${pkField}=${deleteItem[pkField]}${skField ? `, ${skField}=${deleteItem[skField]}` : ''} from the table.`}
          confirmLabel="Delete item"
          onCancel={() => setDeleteItem(null)}
          onConfirm={() => {
            const key = { [pkField]: deleteItem[pkField] }
            if (skField) key[skField] = deleteItem[skField]
            deleteDynamoItem(table.id, key)
            pushFlash('success', 'Item deleted')
            setDeleteItem(null)
            if (rows != null) setRows((prev) => (prev || []).filter((r) => r !== deleteItem))
          }}
        />
      )}
      {deleteOpen && (
        <ConfirmDialog
          title={`Delete ${table.name}?`}
          body={`This permanently removes table ${table.name} and all its items from the local DynamoDB simulation.`}
          confirmLabel="Delete"
          confirmText={table.name}
          onCancel={() => setDeleteOpen(false)}
          onConfirm={() => { deleteGenericResource(SERVICE, RESOURCE, table.id); pushFlash('success', `Deleting table ${table.name}`); navigate(`${BASE}/dynamodb/tables`) }}
        />
      )}
    </div>
  )
}
