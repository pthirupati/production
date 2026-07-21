import { useState } from 'react'
import { ChevronRight, Folder, Lock } from 'lucide-react'
import { useOS } from '../store'
import { useCtxMenu, Dialog } from '../ui'

function getNode(reg, pathArr) {
  let n = reg
  for (const k of pathArr) { if (!n) return null; n = n.__link ? reg[n.__link]?.[k] : n[k] }
  return n
}

export default function RegistryEditor() {
  const os = useOS()
  const ctx = useCtxMenu()
  const [pathArr, setPathArr] = useState(['HKEY_LOCAL_MACHINE', 'SOFTWARE', 'Microsoft', 'Windows NT', 'CurrentVersion'])
  const [expanded, setExpanded] = useState({ 'HKEY_LOCAL_MACHINE': true, 'HKEY_LOCAL_MACHINE/SOFTWARE': true, 'HKEY_LOCAL_MACHINE/SOFTWARE/Microsoft': true, 'HKEY_LOCAL_MACHINE/SOFTWARE/Microsoft/Windows NT': true })
  const [edit, setEdit] = useState(null)

  const node = getNode(os.registry, pathArr)
  const values = node?.__values || []

  const renderTree = (obj, parents = [], depth = 0) => {
    return Object.keys(obj).filter((k) => !k.startsWith('__')).map((key) => {
      const childPath = [...parents, key]
      const id = childPath.join('/')
      const child = obj[key]
      const realChild = child?.__link ? os.registry[child.__link] : child
      const hasKids = realChild && Object.keys(realChild).some((k) => !k.startsWith('__'))
      const denied = child?.__denied
      return (
        <div key={id}>
          <div className={`winos-tree-row ${pathArr.join('/') === id ? 'sel' : ''}`} style={{ paddingLeft: 8 + depth * 14 }}
            onClick={() => { setPathArr(childPath); if (hasKids) setExpanded((x) => ({ ...x, [id]: !x[id] })) }}
            onContextMenu={keyCtx(childPath)}>
            {hasKids ? <ChevronRight size={12} style={{ transform: expanded[id] ? 'rotate(90deg)' : '' }} /> : <span style={{ width: 12, display: 'inline-block' }} />}
            {denied ? <Lock size={12} color="#888" /> : <Folder size={12} color="#f0b400" />} {key}
          </div>
          {expanded[id] && hasKids && renderTree(realChild, childPath, depth + 1)}
        </div>
      )
    })
  }

  const keyCtx = (p) => (e) => {
    e.preventDefault()
    ctx.open(e.clientX, e.clientY, [
      { label: 'New', sub: [
        { label: 'Key', onClick: () => {
          const name = 'New Key #1'
          os.regNewKey(p, name)
          setExpanded((x) => ({ ...x, [p.join('/')]: true }))
          if (os.labAction) os.labAction('reg_new_key', { path: p, name })
        } },
        { sep: true },
        { label: 'String Value', onClick: () => {
          os.regSetValue(p, 'New Value #1', 'REG_SZ', '')
          if (os.labAction) os.labAction('reg_set_value', { path: p, name: 'New Value #1', type: 'REG_SZ', data: '' })
        } },
        { label: 'DWORD (32-bit) Value', onClick: () => {
          os.regSetValue(p, 'New Value #1', 'REG_DWORD', '0x00000000 (0)')
          if (os.labAction) os.labAction('reg_set_value', { path: p, name: 'New Value #1', type: 'REG_DWORD', data: '0x00000000 (0)' })
        } },
        { label: 'Multi-String Value', onClick: () => {
          os.regSetValue(p, 'New Value #1', 'REG_MULTI_SZ', '')
          if (os.labAction) os.labAction('reg_set_value', { path: p, name: 'New Value #1', type: 'REG_MULTI_SZ', data: '' })
        } },
        { label: 'Expandable String Value', onClick: () => {
          os.regSetValue(p, 'New Value #1', 'REG_EXPAND_SZ', '')
          if (os.labAction) os.labAction('reg_set_value', { path: p, name: 'New Value #1', type: 'REG_EXPAND_SZ', data: '' })
        } },
      ] },
      { sep: true }, { label: 'Delete' }, { label: 'Rename' }, { sep: true },
      { label: 'Copy Key Name', onClick: () => navigator.clipboard?.writeText('Computer\\' + p.join('\\')) },
    ])
  }

  const valCtx = (v) => (e) => {
    e.preventDefault()
    ctx.open(e.clientX, e.clientY, [
      { label: 'Modify…', onClick: () => setEdit(v) },
      { label: 'Modify Binary Data…', onClick: () => setEdit(v) },
      { sep: true },
      { label: 'Delete', onClick: () => {
        os.regDeleteValue(pathArr, v.name)
        if (os.labAction) os.labAction('reg_delete_value', { path: pathArr, name: v.name })
      } },
      { label: 'Rename' },
    ])
  }

  return (
    <div className="winos-app">
      <div className="winos-toolbar"><span style={{ fontSize: 12 }}>File &nbsp; Edit &nbsp; View &nbsp; Favorites &nbsp; Help</span></div>
      <div style={{ padding: '4px 10px', borderBottom: '1px solid #e2e2e2', fontSize: 12, fontFamily: 'Consolas, monospace', background: '#fafafa' }}>
        Computer\{pathArr.join('\\')}
      </div>
      <div className="winos-split">
        <div className="winos-tree" style={{ width: 320 }}>
          <div className="winos-tree-row" style={{ fontWeight: 600 }}>💻 Computer</div>
          {renderTree(os.registry, [], 1)}
        </div>
        <div className="winos-main">
          <table className="winos-table">
            <thead><tr><th style={{ width: '30%' }}>Name</th><th style={{ width: '20%' }}>Type</th><th>Data</th></tr></thead>
            <tbody>
              <tr onContextMenu={valCtx({ name: '(Default)', type: 'REG_SZ', data: values.find((v) => v.name === '(Default)')?.data || '(value not set)' })}>
                <td>🔤 (Default)</td><td>REG_SZ</td><td>{values.find((v) => v.name === '(Default)')?.data || '(value not set)'}</td>
              </tr>
              {values.filter((v) => v.name !== '(Default)').map((v) => (
                <tr key={v.name} onDoubleClick={() => setEdit(v)} onContextMenu={valCtx(v)}>
                  <td>{v.type === 'REG_DWORD' ? '🔢' : '🔤'} {v.name}</td><td>{v.type}</td><td>{v.data}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {edit && <EditValue v={edit} pathArr={pathArr} onClose={() => setEdit(null)} />}
    </div>
  )
}

function EditValue({ v, pathArr, onClose }) {
  const os = useOS()
  const [data, setData] = useState(v.type === 'REG_DWORD' ? (v.data.match(/\((\d+)\)/)?.[1] || '0') : v.data)
  const [base, setBase] = useState('hex')
  return (
    <Dialog title={v.type === 'REG_DWORD' ? 'Edit DWORD (32-bit) Value' : 'Edit String'} onClose={onClose} width={420}
      footer={<><button className="winos-btn primary" onClick={() => {
        const out = v.type === 'REG_DWORD' ? `0x${Number(data).toString(16).padStart(8, '0')} (${data})` : data
        os.regSetValue(pathArr, v.name, v.type, out)
        if (os.labAction) os.labAction('reg_set_value', { path: pathArr, name: v.name, type: v.type, data: out })
        onClose()
      }}>OK</button><button className="winos-btn" onClick={onClose}>Cancel</button></>}>
      <div style={{ fontSize: 12.5 }}>
        <div style={{ marginBottom: 6 }}>Value name:</div>
        <input className="winos-input" style={{ width: '100%', marginBottom: 12 }} value={v.name} readOnly />
        <div style={{ marginBottom: 6 }}>Value data:</div>
        {v.type === 'REG_MULTI_SZ'
          ? <textarea className="winos-input" rows={4} style={{ width: '100%' }} value={data} onChange={(e) => setData(e.target.value)} />
          : <input className="winos-input" style={{ width: '100%' }} value={data} onChange={(e) => setData(e.target.value)} />}
        {v.type === 'REG_DWORD' && (
          <div style={{ marginTop: 10 }}>Base: <label style={{ marginLeft: 8 }}><input type="radio" checked={base === 'hex'} onChange={() => setBase('hex')} /> Hexadecimal</label>
            <label style={{ marginLeft: 12 }}><input type="radio" checked={base === 'dec'} onChange={() => setBase('dec')} /> Decimal</label></div>
        )}
      </div>
    </Dialog>
  )
}
