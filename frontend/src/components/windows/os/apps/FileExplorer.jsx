import { useMemo, useState } from 'react'
import {
  ArrowLeft, ArrowRight, ArrowUp, RefreshCw, Search, Folder, FileText, HardDrive,
  Disc, Network, Star, Monitor, Download, Image, Music, Video, FolderOpen, Scissors, Copy, Clipboard, Trash2, Plus,
} from 'lucide-react'
import { useOS, normPath } from '../store'
import { fmtBytes, useCtxMenu, Dialog, Tabs } from '../ui'

const QUICK = [
  { label: 'Desktop', path: 'C:\\Users\\Administrator\\Desktop', icon: <Monitor size={15} /> },
  { label: 'Downloads', path: 'C:\\Users\\Administrator\\Downloads', icon: <Download size={15} /> },
  { label: 'Documents', path: 'C:\\Users\\Administrator\\Documents', icon: <FileText size={15} /> },
  { label: 'Pictures', path: 'C:\\Users\\Administrator\\Pictures', icon: <Image size={15} /> },
]

function extOf(name) { const i = name.lastIndexOf('.'); return i > 0 ? name.slice(i + 1).toLowerCase() : '' }
function typeOf(name, isDir) {
  if (isDir) return 'File folder'
  const e = extOf(name)
  const map = { txt: 'Text Document', log: 'Text Document', ps1: 'Windows PowerShell Script', exe: 'Application', dll: 'Application extension', html: 'HTML Document', htm: 'HTML Document', config: 'XML Configuration File', iso: 'Disc Image File', msu: 'Microsoft Update Standalone Package', gz: 'GZ File', bak: 'BAK File', png: 'PNG image', csv: 'Microsoft Excel CSV', xlsx: 'Microsoft Excel Worksheet', docx: 'Microsoft Word Document', pdf: 'PDF Document', lnk: 'Shortcut' }
  return map[e] || (e ? `${e.toUpperCase()} File` : 'File')
}

export default function FileExplorer({ win }) {
  const os = useOS()
  const ctx = useCtxMenu()
  const [history, setHistory] = useState([win.props?.path || 'This PC'])
  const [hi, setHi] = useState(0)
  const [sel, setSel] = useState(null)
  const [search, setSearch] = useState('')
  const [view, setView] = useState('Details')
  const [ribbon, setRibbon] = useState('Home')
  const [props, setProps] = useState(null)
  const [renaming, setRenaming] = useState(null)
  const [renameVal, setRenameVal] = useState('')
  const [folderOptions, setFolderOptions] = useState(false)

  const path = history[hi]
  const isThisPC = path === 'This PC'
  const isNetwork = path === 'Network'

  const navigate = (p) => { const h = history.slice(0, hi + 1); h.push(p); setHistory(h); setHi(h.length - 1); setSel(null); setSearch('') }
  const back = () => hi > 0 && setHi(hi - 1)
  const fwd = () => hi < history.length - 1 && setHi(hi + 1)
  const up = () => {
    if (isThisPC || isNetwork) return
    const p = normPath(path)
    if (/^[A-Za-z]:\\?$/.test(p)) { navigate('This PC'); return }
    const parent = p.slice(0, p.lastIndexOf('\\')) || p.slice(0, 3)
    navigate(parent)
  }

  // entries for current folder
  const entries = useMemo(() => {
    if (isThisPC || isNetwork) return []
    const names = os.listDir(path) || []
    let list = names.map((n) => {
      const full = normPath(path + '\\' + n)
      const dir = os.isDir(full)
      const meta = dir ? null : os.fileMeta(full)
      return { name: n, full, dir, size: dir ? null : meta?.size ?? 0, modified: dir ? '2024-01-16 14:47' : (meta?.modified || ''), type: typeOf(n, dir), created: meta?.created || '2024-01-15 09:23' }
    })
    if (search) list = list.filter((e) => e.name.toLowerCase().includes(search.toLowerCase()))
    list.sort((a, b) => (a.dir === b.dir ? a.name.localeCompare(b.name) : a.dir ? -1 : 1))
    return list
  }, [path, search, os, isThisPC, isNetwork])

  const drives = os.vfs.drives
  const breadcrumb = isThisPC ? [{ label: 'This PC', path: 'This PC' }]
    : isNetwork ? [{ label: 'Network', path: 'Network' }]
      : (() => {
        const out = [{ label: 'This PC', path: 'This PC' }]
        const p = normPath(path)
        const drive = p.slice(0, 1)
        let acc = `${drive}:\\`
        out.push({ label: `${drives[drive]?.label || 'Local Disk'} (${drive}:)`, path: acc })
        const rest = p.slice(3).split('\\').filter(Boolean)
        rest.forEach((seg) => { acc = normPath(acc + '\\' + seg); out.push({ label: seg, path: acc }) })
        return out
      })()

  const openEntry = (e) => {
    if (e.dir) navigate(e.full)
    else if (['txt', 'log', 'ps1', 'config', 'html', 'htm', 'csv', 'ini'].includes(extOf(e.name)) || e.size < 1_000_000) {
      os.openApp('Notepad', { path: e.full }, { width: 760, height: 540, title: `${e.name} - Notepad` })
    }
  }

  const fileCtx = (e) => (ev) => {
    ev.preventDefault(); ev.stopPropagation(); setSel(e.name)
    ctx.open(ev.clientX, ev.clientY, [
      { label: 'Open', icon: <FolderOpen size={14} />, onClick: () => openEntry(e) },
      ...(e.dir ? [{ label: 'Open in new window', onClick: () => os.openApp('FileExplorer', { path: e.full }, { title: e.name }) }] : []),
      { sep: true },
      { label: 'Cut', icon: <Scissors size={14} />, onClick: () => os.setClipboard({ op: 'cut', path: e.full, name: e.name, dir: e.dir }) },
      { label: 'Copy', icon: <Copy size={14} />, onClick: () => os.setClipboard({ op: 'copy', path: e.full, name: e.name, dir: e.dir }) },
      { sep: true },
      { label: 'Delete', icon: <Trash2 size={14} />, onClick: () => { os.deleteItem(e.full); setSel(null) } },
      { label: 'Rename', onClick: () => { setRenaming(e.name); setRenameVal(e.name) } },
      { sep: true },
      { label: 'Properties', onClick: () => setProps(e) },
    ])
  }

  const bgCtx = (ev) => {
    if (isThisPC || isNetwork) return
    ev.preventDefault()
    const paste = os.clipboard ? [{
      label: 'Paste', icon: <Clipboard size={14} />, onClick: () => {
        const cb = os.clipboard
        const dest = normPath(path + '\\' + cb.name)
        if (cb.dir) os.createDirectory(dest)
        else os.writeFile(dest, os.readFile(cb.path) || '')
        if (cb.op === 'cut') { os.deleteItem(cb.path); os.setClipboard(null) }
      },
    }] : []
    ctx.open(ev.clientX, ev.clientY, [
      ...paste,
      { label: 'New', icon: <Plus size={14} />, sub: [
        { label: 'Folder', onClick: () => { let n = 'New folder', i = 1; while (os.isDir(normPath(path + '\\' + n))) n = `New folder (${++i})`; os.createDirectory(normPath(path + '\\' + n)); setRenaming(n); setRenameVal(n) } },
        { label: 'Text Document', onClick: () => { os.writeFile(normPath(path + '\\New Text Document.txt'), ''); setRenaming('New Text Document.txt'); setRenameVal('New Text Document.txt') } },
      ] },
      { sep: true },
      { label: 'Refresh', icon: <RefreshCw size={14} />, onClick: () => setHistory([...history]) },
      { sep: true },
      { label: 'Open Windows PowerShell', onClick: () => os.openApp('Terminal', { shell: 'ps', cwd: path }, { title: 'Windows PowerShell' }) },
    ])
  }

  const commitRename = () => {
    if (renaming && renameVal && renameVal !== renaming) os.renameItem(normPath(path + '\\' + renaming), renameVal)
    setRenaming(null)
  }

  const selCount = sel ? 1 : 0
  const selEntry = entries.find((e) => e.name === sel)

  return (
    <div className="winos-app">
      {/* ribbon */}
      <div style={{ background: '#f7f7f7', borderBottom: '1px solid #e2e2e2' }}>
        <div style={{ display: 'flex', gap: 2, padding: '2px 6px 0' }}>
          {['File', 'Home', 'Share', 'View'].map((t) => (
            <div key={t} onClick={() => setRibbon(t)} style={{ padding: '4px 12px', fontSize: 12, cursor: 'default', background: ribbon === t ? '#fff' : 'transparent', border: ribbon === t ? '1px solid #e2e2e2' : '1px solid transparent', borderBottom: 'none', borderRadius: '4px 4px 0 0' }}>{t}</div>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', borderTop: '1px solid #e2e2e2', flexWrap: 'wrap' }}>
          {ribbon === 'Home' && <>
            <button className="winos-btn" disabled={!sel} onClick={() => selEntry && os.setClipboard({ op: 'copy', path: selEntry.full, name: selEntry.name, dir: selEntry.dir })}><Copy size={14} /> Copy</button>
            <button className="winos-btn" disabled={!os.clipboard} onClick={() => bgCtx({ preventDefault() {}, clientX: 200, clientY: 200 })}><Clipboard size={14} /> Paste</button>
            <button className="winos-btn" disabled={!sel} onClick={() => selEntry && os.setClipboard({ op: 'cut', path: selEntry.full, name: selEntry.name, dir: selEntry.dir })}><Scissors size={14} /> Cut</button>
            <span style={{ width: 1, height: 22, background: '#ddd' }} />
            <button className="winos-btn" disabled={!sel} onClick={() => { if (selEntry) { os.deleteItem(selEntry.full); setSel(null) } }}><Trash2 size={14} /> Delete</button>
            <button className="winos-btn" disabled={!sel} onClick={() => selEntry && (setRenaming(selEntry.name), setRenameVal(selEntry.name))}>Rename</button>
            <span style={{ width: 1, height: 22, background: '#ddd' }} />
            <button className="winos-btn" disabled={isThisPC} onClick={() => { let n = 'New folder'; os.createDirectory(normPath(path + '\\' + n)); setRenaming(n); setRenameVal(n) }}><Plus size={14} /> New folder</button>
            <button className="winos-btn" disabled={!sel} onClick={() => selEntry && setProps(selEntry)}>Properties</button>
          </>}
          {ribbon === 'View' && <>
            {['Details', 'Large icons', 'List', 'Tiles'].map((v) => (
              <button key={v} className={`winos-btn ${view === v ? 'primary' : ''}`} onClick={() => setView(v)}>{v}</button>
            ))}
            <span style={{ width: 1, height: 22, background: '#ddd' }} />
            <button className="winos-btn" onClick={() => setFolderOptions(true)}>Options</button>
          </>}
          {ribbon === 'Share' && <>
            <button className="winos-btn">Email</button><button className="winos-btn">Zip</button>
            <button className="winos-btn">Print</button><button className="winos-btn">Specific people…</button>
          </>}
          {ribbon === 'File' && <>
            <button className="winos-btn" onClick={() => os.openApp('FileExplorer', { path }, { title: 'File Explorer' })}>Open new window</button>
            <button className="winos-btn" onClick={() => os.openApp('Terminal', { shell: 'ps', cwd: isThisPC ? 'C:\\' : path }, { title: 'Windows PowerShell' })}>Open Windows PowerShell</button>
          </>}
        </div>
      </div>

      {/* address bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 8px', borderBottom: '1px solid #e2e2e2' }}>
        <button className="winos-btn" style={{ padding: '4px 7px' }} onClick={back} disabled={hi === 0}><ArrowLeft size={15} /></button>
        <button className="winos-btn" style={{ padding: '4px 7px' }} onClick={fwd} disabled={hi >= history.length - 1}><ArrowRight size={15} /></button>
        <button className="winos-btn" style={{ padding: '4px 7px' }} onClick={up}><ArrowUp size={15} /></button>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', border: '1px solid #c8c8c8', borderRadius: 4, padding: '3px 8px', background: '#fff', minWidth: 0, overflow: 'hidden' }}>
          {breadcrumb.map((b, i) => (
            <span key={i} style={{ display: 'inline-flex', alignItems: 'center' }}>
              <span style={{ cursor: 'default', whiteSpace: 'nowrap' }} onClick={() => navigate(b.path)}>{b.label}</span>
              {i < breadcrumb.length - 1 && <span style={{ margin: '0 4px', color: '#999' }}>›</span>}
            </span>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', border: '1px solid #c8c8c8', borderRadius: 4, padding: '3px 8px', background: '#fff', width: 180 }}>
          <Search size={13} style={{ color: '#888' }} />
          <input className="winos-input" style={{ border: 'none', padding: '0 4px', flex: 1 }} placeholder={`Search ${breadcrumb.slice(-1)[0]?.label || ''}`} value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
      </div>

      <div className="winos-split">
        {/* nav pane */}
        <div className="winos-tree" style={{ width: 220 }}>
          <div style={{ padding: '4px 10px', fontSize: 11, color: '#888' }}>Quick access</div>
          {QUICK.map((q) => (
            <div key={q.label} className="winos-tree-row" onClick={() => navigate(q.path)}><Star size={12} color="#f0b400" />{q.icon}{q.label}</div>
          ))}
          <div style={{ padding: '8px 10px 4px', fontSize: 11, color: '#888' }}>This PC</div>
          <div className="winos-tree-row" onClick={() => navigate('This PC')}><Monitor size={14} /> This PC</div>
          {Object.entries(drives).map(([letter, d]) => (
            <div key={letter} className="winos-tree-row" onClick={() => !d.noMedia && navigate(`${letter}:\\`)} style={{ opacity: d.noMedia ? 0.5 : 1 }}>
              {d.type === 'dvd' ? <Disc size={14} /> : <HardDrive size={14} />} {d.label} ({letter}:)
            </div>
          ))}
          <div style={{ padding: '8px 10px 4px', fontSize: 11, color: '#888' }}>Network</div>
          {Object.keys(os.vfs.network).map((n) => (
            <div key={n} className="winos-tree-row" onClick={() => {}}><Network size={13} /> {n.replace(/\\\\/, '').split('\\')[0]}</div>
          ))}
        </div>

        {/* main */}
        <div className="winos-main" onContextMenu={bgCtx} onClick={() => setSel(null)}>
          {isThisPC ? (
            <div style={{ padding: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, margin: '4px 0 10px' }}>Devices and drives</div>
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {Object.entries(drives).map(([letter, d]) => {
                  const pct = d.totalGB ? Math.round((d.usedGB / d.totalGB) * 100) : 0
                  return (
                    <div key={letter} style={{ width: 230, cursor: 'default' }} onDoubleClick={() => !d.noMedia && navigate(`${letter}:\\`)}>
                      <div style={{ display: 'flex', gap: 10 }}>
                        {d.type === 'dvd' ? <Disc size={36} color="#888" /> : <HardDrive size={36} color="#5a8" />}
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 12.5 }}>{d.label} ({letter}:)</div>
                          {d.noMedia ? <div style={{ fontSize: 11, color: '#888' }}>No media</div> : <>
                            <div style={{ height: 8, background: '#e6e6e6', borderRadius: 3, marginTop: 4, overflow: 'hidden' }}>
                              <div style={{ width: `${pct}%`, height: '100%', background: pct > 90 ? '#c42b1c' : '#0078d4' }} />
                            </div>
                            <div style={{ fontSize: 11, color: '#666', marginTop: 2 }}>{(d.totalGB - d.usedGB).toFixed(1)} GB free of {d.totalGB} GB</div>
                          </>}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ) : view === 'Details' ? (
            <table className="winos-table">
              <thead><tr><th style={{ width: '40%' }}>Name</th><th>Date modified</th><th>Type</th><th style={{ textAlign: 'right' }}>Size</th></tr></thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.name} className={sel === e.name ? 'sel' : ''}
                    onClick={(ev) => { ev.stopPropagation(); setSel(e.name) }}
                    onDoubleClick={() => openEntry(e)} onContextMenu={fileCtx(e)}>
                    <td><span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                      {e.dir ? <Folder size={15} color="#f0b400" /> : <FileText size={15} color="#5b9bd5" />}
                      {renaming === e.name
                        ? <input autoFocus className="winos-input" style={{ padding: '1px 4px' }} value={renameVal} onChange={(ev) => setRenameVal(ev.target.value)} onBlur={commitRename} onKeyDown={(ev) => ev.key === 'Enter' && commitRename()} onClick={(ev) => ev.stopPropagation()} />
                        : e.name}
                    </span></td>
                    <td>{e.modified}</td>
                    <td>{e.type}</td>
                    <td style={{ textAlign: 'right' }}>{e.dir ? '' : fmtBytes(e.size)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: view === 'List' ? 0 : 14, padding: 12, flexDirection: view === 'List' ? 'column' : 'row' }}>
              {entries.map((e) => (
                <div key={e.name} onClick={(ev) => { ev.stopPropagation(); setSel(e.name) }} onDoubleClick={() => openEntry(e)} onContextMenu={fileCtx(e)}
                  style={{ width: view === 'Large icons' ? 96 : view === 'Tiles' ? 200 : 'auto', display: 'flex', flexDirection: view === 'Large icons' ? 'column' : 'row', alignItems: 'center', gap: 8, padding: 6, borderRadius: 4, background: sel === e.name ? '#cfe6fb' : 'transparent', cursor: 'default', textAlign: view === 'Large icons' ? 'center' : 'left' }}>
                  {e.dir ? <Folder size={view === 'Large icons' ? 44 : 18} color="#f0b400" /> : <FileText size={view === 'Large icons' ? 44 : 18} color="#5b9bd5" />}
                  <span style={{ fontSize: 12, wordBreak: 'break-word' }}>{e.name}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="winos-status">
        <span>{isThisPC ? `${Object.keys(drives).length} items` : selCount ? `${selCount} item selected${selEntry && !selEntry.dir ? `  ${fmtBytes(selEntry.size)}` : ''}` : `${entries.length} items`}</span>
        <span>{view}</span>
      </div>

      {props && <PropertiesDialog entry={props} path={path} onClose={() => setProps(null)} />}
      {folderOptions && <FolderOptionsDialog onClose={() => setFolderOptions(false)} />}
    </div>
  )
}

function PropertiesDialog({ entry, path, onClose }) {
  const [tab, setTab] = useState('General')
  const tabs = entry.dir ? ['General', 'Sharing', 'Security', 'Previous Versions'] : ['General', 'Security', 'Details', 'Previous Versions']
  return (
    <Dialog title={`${entry.name} Properties`} onClose={onClose} width={420}
      footer={<><button className="winos-btn primary" onClick={onClose}>OK</button><button className="winos-btn" onClick={onClose}>Cancel</button><button className="winos-btn" disabled>Apply</button></>}>
      <Tabs tabs={tabs} active={tab} onChange={setTab} />
      <div style={{ paddingTop: 12, fontSize: 12.5 }}>
        {tab === 'General' && (
          <div className="winos-grid2">
            <div style={{ gridColumn: '1 / -1', display: 'flex', alignItems: 'center', gap: 10, paddingBottom: 8, borderBottom: '1px solid #eee', marginBottom: 4 }}>
              {entry.dir ? <Folder size={28} color="#f0b400" /> : <FileText size={28} color="#5b9bd5" />}
              <strong>{entry.name}</strong>
            </div>
            <span style={{ color: '#666' }}>Type of file:</span><span>{entry.type}</span>
            {!entry.dir && <><span style={{ color: '#666' }}>Opens with:</span><span>Notepad</span></>}
            <span style={{ color: '#666' }}>Location:</span><span>{path}</span>
            <span style={{ color: '#666' }}>Size:</span><span>{entry.dir ? '—' : `${fmtBytes(entry.size)} (${entry.size.toLocaleString()} bytes)`}</span>
            <span style={{ color: '#666' }}>Size on disk:</span><span>{entry.dir ? '—' : `${fmtBytes(Math.ceil(entry.size / 4096) * 4096)}`}</span>
            <span style={{ color: '#666' }}>Created:</span><span>{entry.created}</span>
            <span style={{ color: '#666' }}>Modified:</span><span>{entry.modified}</span>
            <span style={{ color: '#666' }}>Attributes:</span><span><label><input type="checkbox" /> Read-only</label> &nbsp; <label><input type="checkbox" /> Hidden</label></span>
          </div>
        )}
        {tab === 'Security' && (
          <div>
            <div style={{ color: '#666', marginBottom: 6 }}>Group or user names:</div>
            <div style={{ border: '1px solid #ddd', height: 110, overflow: 'auto', marginBottom: 8 }}>
              {['SYSTEM', 'Administrators (SERVER01\\Administrators)', 'Users (SERVER01\\Users)', 'TrustedInstaller'].map((g) => <div key={g} className="winos-tree-row">{g}</div>)}
            </div>
            <div style={{ color: '#666', marginBottom: 6 }}>Permissions for Administrators:</div>
            {['Full control', 'Modify', 'Read & execute', 'Read', 'Write'].map((p) => (
              <div key={p} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 6px' }}>
                <span>{p}</span><span><input type="checkbox" defaultChecked readOnly /> Allow &nbsp; <input type="checkbox" readOnly /> Deny</span>
              </div>
            ))}
          </div>
        )}
        {tab === 'Details' && (
          <div className="winos-grid2">
            <span style={{ color: '#666' }}>Name:</span><span>{entry.name}</span>
            <span style={{ color: '#666' }}>Item type:</span><span>{entry.type}</span>
            <span style={{ color: '#666' }}>Folder path:</span><span>{path}</span>
            <span style={{ color: '#666' }}>Date created:</span><span>{entry.created}</span>
            <span style={{ color: '#666' }}>Date modified:</span><span>{entry.modified}</span>
            <span style={{ color: '#666' }}>Size:</span><span>{fmtBytes(entry.size)}</span>
            <span style={{ color: '#666' }}>Owner:</span><span>SERVER01\\Administrators</span>
            <span style={{ color: '#666' }}>Computer:</span><span>SERVER01 (this PC)</span>
          </div>
        )}
        {tab === 'Sharing' && <div style={{ color: '#555' }}>Network File and Folder Sharing<br /><br /><b>{entry.name}</b> — Not Shared<br /><br /><button className="winos-btn">Share…</button> <button className="winos-btn">Advanced Sharing…</button></div>}
        {tab === 'Previous Versions' && <div style={{ color: '#555' }}>There are no previous versions available.</div>}
      </div>
    </Dialog>
  )
}

function FolderOptionsDialog({ onClose }) {
  const [tab, setTab] = useState('General')
  const checks = [
    'Always show icons, never thumbnails',
    'Always show menus',
    'Display file icon on thumbnails',
    'Display file size information in folder tips',
    'Display the full path in the title bar',
    'Hide empty drives',
    'Hide extensions for known file types',
    'Hide folder merge conflicts',
    'Hide protected operating system files',
    'Launch folder windows in a separate process',
    'Restore previous folder windows at logon',
    'Show drive letters',
    'Show encrypted or compressed NTFS files in color',
    'Show pop-up description for folder and desktop items',
    'Show preview handlers in preview pane',
    'Show status bar',
    'Show sync provider notifications',
    'Use check boxes to select items',
    'Use Sharing Wizard',
  ]
  return (
    <Dialog title="Folder Options" onClose={onClose} width={500}
      footer={<><button className="winos-btn primary" onClick={onClose}>OK</button><button className="winos-btn" onClick={onClose}>Cancel</button><button className="winos-btn">Apply</button></>}>
      <Tabs tabs={['General', 'View', 'Search']} active={tab} onChange={setTab} />
      <div style={{ paddingTop: 12, fontSize: 12.5 }}>
        {tab === 'General' && (
          <div>
            <fieldset style={{ border: '1px solid #ddd', padding: 10, marginBottom: 10 }}>
              <legend>Open File Explorer to:</legend>
              <select className="winos-input" defaultValue="This PC"><option>Quick access</option><option>This PC</option></select>
            </fieldset>
            <fieldset style={{ border: '1px solid #ddd', padding: 10, marginBottom: 10 }}>
              <legend>Browse folders</legend>
              <label style={{ display: 'block' }}><input type="radio" name="browse" defaultChecked /> Open each folder in the same window</label>
              <label style={{ display: 'block' }}><input type="radio" name="browse" /> Open each folder in its own window</label>
            </fieldset>
            <fieldset style={{ border: '1px solid #ddd', padding: 10 }}>
              <legend>Click items as follows</legend>
              <label style={{ display: 'block' }}><input type="radio" name="click" /> Single-click to open an item</label>
              <label style={{ display: 'block' }}><input type="radio" name="click" defaultChecked /> Double-click to open an item</label>
            </fieldset>
          </div>
        )}
        {tab === 'View' && (
          <div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}><button className="winos-btn">Apply to Folders</button><button className="winos-btn">Reset Folders</button></div>
            <div style={{ border: '1px solid #ddd', height: 260, overflow: 'auto', padding: 8 }}>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>Advanced settings:</div>
              <div style={{ marginBottom: 8 }}>
                <div>Hidden files and folders</div>
                <label style={{ display: 'block', marginLeft: 18 }}><input type="radio" name="hidden" defaultChecked /> Don't show hidden files, folders, or drives</label>
                <label style={{ display: 'block', marginLeft: 18 }}><input type="radio" name="hidden" /> Show hidden files, folders, and drives</label>
              </div>
              {checks.map((c, i) => <label key={c} style={{ display: 'block', padding: '2px 0' }}><input type="checkbox" defaultChecked={[2, 3, 6, 7, 11, 13, 14, 15, 18].includes(i)} /> {c}</label>)}
              <div style={{ marginTop: 8 }}>
                <div>When typing into list view</div>
                <label style={{ display: 'block', marginLeft: 18 }}><input type="radio" name="typing" /> Automatically type into the Search Box</label>
                <label style={{ display: 'block', marginLeft: 18 }}><input type="radio" name="typing" defaultChecked /> Select the typed item in the view</label>
              </div>
            </div>
          </div>
        )}
        {tab === 'Search' && (
          <div>
            <fieldset style={{ border: '1px solid #ddd', padding: 10, marginBottom: 10 }}>
              <legend>What to search</legend>
              <label style={{ display: 'block' }}><input type="radio" name="what" defaultChecked /> In indexed locations, search file names and contents</label>
              <label style={{ display: 'block' }}><input type="radio" name="what" /> Always search file names and contents</label>
            </fieldset>
            <fieldset style={{ border: '1px solid #ddd', padding: 10, marginBottom: 10 }}>
              <legend>How to search</legend>
              <label style={{ display: 'block' }}><input type="checkbox" /> Include compressed files (.zip, .cab...)</label>
              <label style={{ display: 'block' }}><input type="checkbox" defaultChecked /> Always search file names</label>
            </fieldset>
            <fieldset style={{ border: '1px solid #ddd', padding: 10 }}>
              <legend>When searching non-indexed locations</legend>
              <label style={{ display: 'block' }}><input type="checkbox" /> Include system directories</label>
              <label style={{ display: 'block' }}><input type="checkbox" /> Include compressed files</label>
            </fieldset>
          </div>
        )}
      </div>
    </Dialog>
  )
}
