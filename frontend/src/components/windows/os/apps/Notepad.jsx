import { useState } from 'react'
import { useOS } from '../store'
import { Dialog } from '../ui'

export default function Notepad({ win }) {
  const { readFile, writeFile, setWindowTitle, listDir, vfs } = useOS()
  const initialPath = win.props?.path || null
  const [path, setPath] = useState(initialPath)
  const [text, setText] = useState(initialPath ? (readFile(initialPath) ?? '') : '')
  const [wrap, setWrap] = useState(true)
  const [dirty, setDirty] = useState(false)
  const [menu, setMenu] = useState(null)
  const [saveAs, setSaveAs] = useState(false)
  const [saveName, setSaveName] = useState('Untitled.txt')
  const [saveDir, setSaveDir] = useState('C:\\Users\\Administrator\\Documents')

  const title = (path ? path.split('\\').pop() : 'Untitled') + (dirty ? ' *' : '') + ' - Notepad'
  if (win.title !== title) setWindowTitle(win.id, title)

  const doSave = () => {
    if (!path) { setSaveAs(true); return }
    writeFile(path, text); setDirty(false)
  }
  const doSaveAs = () => {
    const full = `${saveDir}\\${saveName}`
    writeFile(full, text); setPath(full); setDirty(false); setSaveAs(false)
  }

  const dirEntries = (listDir(saveDir) || []).filter((n) => vfs.dirs[`${saveDir}\\${n}`] === undefined)

  const Menu = ({ name, items }) => (
    <div style={{ position: 'relative' }}>
      <span style={{ padding: '4px 9px', cursor: 'default', background: menu === name ? '#e5e5e5' : 'transparent' }}
        onClick={() => setMenu(menu === name ? null : name)}>{name}</span>
      {menu === name && (
        <div className="winos-ctx" style={{ position: 'absolute', top: 24, left: 0 }} onMouseLeave={() => setMenu(null)}>
          {items.map((it, i) => it.sep ? <div key={i} className="winos-ctx-sep" />
            : <div key={i} className="winos-ctx-item" onClick={() => { it.onClick?.(); setMenu(null) }}>{it.label}{it.right && <span className="chev">{it.right}</span>}</div>)}
        </div>
      )}
    </div>
  )

  return (
    <div className="winos-app">
      <div style={{ display: 'flex', borderBottom: '1px solid #e2e2e2', background: '#f7f7f7', fontSize: 12.5 }} onMouseLeave={() => setMenu(null)}>
        <Menu name="File" items={[
          { label: 'New', right: 'Ctrl+N', onClick: () => { setText(''); setPath(null); setDirty(false) } },
          { label: 'Open…', right: 'Ctrl+O', onClick: () => setSaveAs('open') },
          { label: 'Save', right: 'Ctrl+S', onClick: doSave },
          { label: 'Save As…', onClick: () => setSaveAs(true) },
          { sep: true },
          { label: 'Exit' },
        ]} />
        <Menu name="Edit" items={[
          { label: 'Undo', right: 'Ctrl+Z' }, { sep: true },
          { label: 'Cut', right: 'Ctrl+X' }, { label: 'Copy', right: 'Ctrl+C' }, { label: 'Paste', right: 'Ctrl+V' },
          { sep: true }, { label: 'Select All', right: 'Ctrl+A' },
          { label: 'Time/Date', right: 'F5', onClick: () => setText((t) => t + new Date().toLocaleString()) },
        ]} />
        <Menu name="Format" items={[{ label: (wrap ? '✓ ' : '') + 'Word Wrap', onClick: () => setWrap((w) => !w) }, { label: 'Font…' }]} />
        <Menu name="View" items={[{ label: 'Zoom' }, { label: 'Status Bar' }]} />
        <Menu name="Help" items={[{ label: 'About Notepad' }]} />
      </div>
      <textarea
        value={text}
        onChange={(e) => { setText(e.target.value); setDirty(true) }}
        spellCheck={false}
        style={{
          flex: 1, minHeight: 0, resize: 'none', border: 'none', outline: 'none', padding: '6px 8px',
          fontFamily: 'Consolas, monospace', fontSize: 13, whiteSpace: wrap ? 'pre-wrap' : 'pre', overflow: 'auto',
        }}
      />
      <div className="winos-status">
        <span>{path || 'Untitled'}</span>
        <span>Ln {text.slice(0, text.length).split('\n').length}, Col 1&nbsp;&nbsp;&nbsp;100%&nbsp;&nbsp;&nbsp;Windows (CRLF)&nbsp;&nbsp;&nbsp;UTF-8</span>
      </div>

      {saveAs && (
        <Dialog title={saveAs === 'open' ? 'Open' : 'Save As'} onClose={() => setSaveAs(false)} width={520}
          footer={<>
            <button className="winos-btn" onClick={() => setSaveAs(false)}>Cancel</button>
            <button className="winos-btn primary" onClick={saveAs === 'open'
              ? () => { const full = `${saveDir}\\${saveName}`; const c = readFile(full); if (c != null) { setText(c); setPath(full); setDirty(false) } setSaveAs(false) }
              : doSaveAs}>{saveAs === 'open' ? 'Open' : 'Save'}</button>
          </>}>
          <div style={{ marginBottom: 8, fontSize: 12 }}>Folder:
            <select className="winos-input" style={{ marginLeft: 8 }} value={saveDir} onChange={(e) => setSaveDir(e.target.value)}>
              {['C:\\Users\\Administrator\\Documents', 'C:\\Users\\Administrator\\Desktop', 'C:\\Users\\Administrator\\Downloads', 'D:\\Scripts\\automation', 'D:\\Logs'].map((d) => <option key={d}>{d}</option>)}
            </select>
          </div>
          <div style={{ height: 180, overflow: 'auto', border: '1px solid #ddd', marginBottom: 8 }}>
            {dirEntries.map((n) => (
              <div key={n} className="winos-tree-row" onClick={() => setSaveName(n)} style={{ background: saveName === n ? '#cfe6fb' : undefined }}>📄 {n}</div>
            ))}
            {dirEntries.length === 0 && <div style={{ padding: 10, color: '#888', fontSize: 12 }}>No files</div>}
          </div>
          <div style={{ fontSize: 12 }}>File name:
            <input className="winos-input" style={{ marginLeft: 8, width: 280 }} value={saveName} onChange={(e) => setSaveName(e.target.value)} />
          </div>
        </Dialog>
      )}
    </div>
  )
}
