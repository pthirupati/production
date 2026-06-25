import { useState } from 'react'
import { useOS } from '../store'
import { useCtxMenu, Dialog } from '../ui'

export default function DiskManagement() {
  const os = useOS()
  const ctx = useCtxMenu()
  const [initDisk, setInitDisk] = useState(null)
  const [wizard, setWizard] = useState(null) // diskId for new volume

  const volumes = []
  os.disks.forEach((d) => d.partitions.forEach((p) => { if (p.letter) volumes.push({ ...p, disk: d.id }) }))
  Object.entries(os.vfs.drives).forEach(([letter, dr]) => {
    if (!volumes.find((v) => v.letter === letter) && !dr.noMedia) volumes.push({ letter, label: dr.label, fs: dr.fs, sizeGB: dr.totalGB, status: 'Healthy (Primary Partition)', disk: '-' })
  })

  const diskCtx = (d) => (e) => {
    e.preventDefault()
    const items = []
    if (!d.initialized) items.push({ label: 'Initialize Disk', onClick: () => setInitDisk(d.id) })
    items.push({ label: 'Online', disabled: d.status === 'Online' }, { label: 'Offline', disabled: d.status !== 'Online' })
    items.push({ sep: true }, { label: 'Properties' })
    ctx.open(e.clientX, e.clientY, items)
  }

  const unallocCtx = (d) => (e) => {
    e.preventDefault()
    ctx.open(e.clientX, e.clientY, [
      { label: 'New Simple Volume…', onClick: () => setWizard(d.id) },
      { label: 'New Spanned Volume…', disabled: true },
      { label: 'New Striped Volume…', disabled: true },
      { label: 'Properties' },
    ])
  }

  const volCtx = (v) => (e) => {
    e.preventDefault()
    ctx.open(e.clientX, e.clientY, [
      { label: 'Open', onClick: () => os.openApp('FileExplorer', { path: `${v.letter}:\\` }, { title: `${v.label} (${v.letter}:)` }) },
      { label: 'Explore' }, { sep: true },
      { label: 'Mark Partition as Active', disabled: true },
      { label: 'Change Drive Letter and Paths…' }, { label: 'Format…' },
      { label: 'Extend Volume…' }, { label: 'Shrink Volume…' }, { sep: true },
      { label: 'Delete Volume…', disabled: v.letter === 'C' }, { label: 'Properties' },
    ])
  }

  return (
    <div className="winos-app">
      <div className="winos-toolbar"><strong>Disk Management</strong></div>
      {/* volume table */}
      <div style={{ flex: '0 0 40%', overflow: 'auto', borderBottom: '2px solid #ccc' }}>
        <table className="winos-table">
          <thead><tr><th>Volume</th><th>Layout</th><th>Type</th><th>File System</th><th>Status</th><th>Capacity</th><th>Free Space</th><th>% Free</th></tr></thead>
          <tbody>
            {volumes.map((v) => {
              const dr = os.vfs.drives[v.letter]
              const free = dr ? dr.totalGB - dr.usedGB : v.sizeGB
              const pct = dr ? Math.round((free / dr.totalGB) * 100) : 100
              return (
                <tr key={v.letter} onContextMenu={volCtx(v)}>
                  <td>■ {v.label ? `${v.label} (${v.letter}:)` : `(${v.letter}:)`}</td>
                  <td>Simple</td><td>Basic</td><td>{v.fs}</td><td>{v.status}</td>
                  <td>{v.sizeGB} GB</td><td>{free.toFixed(0)} GB</td><td>{pct} %</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {/* graphical map */}
      <div style={{ flex: 1, overflow: 'auto', padding: 12, background: '#f7f7f7' }}>
        {os.disks.map((d) => (
          <div key={d.id} style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
            <div style={{ width: 130, flex: 'none', background: '#dde6ef', border: '1px solid #b9c6d6', padding: 8, fontSize: 11 }} onContextMenu={diskCtx(d)}>
              <strong>Disk {d.id}</strong><br />{d.initialized ? 'Basic' : 'Unknown'}<br />{d.sizeGB} GB<br />
              <span style={{ color: d.status === 'Online' ? '#107c10' : '#c42b1c' }}>{d.status}</span>
            </div>
            <div style={{ flex: 1, display: 'flex', gap: 2 }}>
              {d.partitions.length === 0 ? (
                <div onContextMenu={unallocCtx(d)} style={{ flex: 1, background: 'repeating-linear-gradient(45deg,#e8e8e8,#e8e8e8 8px,#dcdcdc 8px,#dcdcdc 16px)', border: '1px solid #c0c0c0', padding: 8, fontSize: 11 }}>
                  {d.sizeGB} GB {d.initialized ? 'Unallocated' : 'Unallocated'}<br /><span style={{ color: '#666' }}>{d.initialized ? 'Unallocated' : 'Not Initialized — right-click disk to Initialize'}</span>
                </div>
              ) : d.partitions.map((p, i) => (
                <div key={i} onContextMenu={p.letter ? volCtx(p) : undefined}
                  style={{ flex: p.sizeGB, minWidth: 60, background: p.letter === 'C' ? '#cfe6cf' : p.type === 'primary' ? '#d4e6f7' : '#e6e0f0', border: '1px solid #9fb6cc', borderTop: '4px solid #6f9fd8', padding: 8, fontSize: 11 }}>
                  <strong>{p.label}{p.letter ? ` (${p.letter}:)` : ''}</strong><br />
                  {p.sizeGB < 1 ? `${Math.round(p.sizeGB * 1024)} MB` : `${p.sizeGB} GB`} {p.fs}<br />
                  <span style={{ color: '#107c10', fontSize: 10 }}>{p.status}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
        <div style={{ display: 'flex', gap: 8 }}>
          <div style={{ width: 130, flex: 'none', background: '#dde6ef', border: '1px solid #b9c6d6', padding: 8, fontSize: 11 }}>
            <strong>CD-ROM 0</strong><br />DVD (E:)<br />No Media
          </div>
          <div style={{ flex: 1, background: '#eee', border: '1px solid #ccc', padding: 8, fontSize: 11, color: '#888' }}>No Media</div>
        </div>
      </div>

      {initDisk != null && <InitDialog diskId={initDisk} onClose={() => setInitDisk(null)} />}
      {wizard != null && <NewVolumeWizard diskId={wizard} onClose={() => setWizard(null)} />}
    </div>
  )
}

function InitDialog({ diskId, onClose }) {
  const os = useOS()
  const [style, setStyle] = useState('GPT')
  return (
    <Dialog title="Initialize Disk" onClose={onClose} width={440}
      footer={<><button className="winos-btn primary" onClick={() => { os.initializeDisk(diskId, style); onClose() }}>OK</button><button className="winos-btn" onClick={onClose}>Cancel</button></>}>
      <p style={{ fontSize: 12.5 }}>You must initialize a disk before Logical Disk Manager can access it.</p>
      <p style={{ fontSize: 12.5 }}>Select disks:</p>
      <div style={{ border: '1px solid #ddd', padding: 8, marginBottom: 12 }}><label><input type="checkbox" defaultChecked readOnly /> Disk {diskId}</label></div>
      <p style={{ fontSize: 12.5 }}>Use the following partition style for the selected disks:</p>
      <label style={{ display: 'block' }}><input type="radio" name="ps" checked={style === 'MBR'} onChange={() => setStyle('MBR')} /> MBR (Master Boot Record)</label>
      <label style={{ display: 'block' }}><input type="radio" name="ps" checked={style === 'GPT'} onChange={() => setStyle('GPT')} /> GPT (GUID Partition Table)</label>
    </Dialog>
  )
}

function NewVolumeWizard({ diskId, onClose }) {
  const os = useOS()
  const disk = os.disks.find((d) => d.id === diskId)
  const maxMB = Math.floor((disk?.sizeGB || 100) * 1024) - 8
  const [page, setPage] = useState(1)
  const used = Object.keys(os.vfs.drives)
  const freeLetter = [...'FGHIJKLMNOPQRSTUVWXYZ'].find((l) => !used.includes(l)) || 'F'
  const [sizeMB, setSizeMB] = useState(maxMB)
  const [letter, setLetter] = useState(freeLetter)
  const [fs, setFs] = useState('NTFS')
  const [label, setLabel] = useState('New Volume')
  const [quick, setQuick] = useState(true)

  const finish = () => {
    os.createVolume(diskId, { letter, label, fs, sizeGB: Math.round((sizeMB / 1024) * 100) / 100 })
    os.logEvent('System', { id: 98, level: 'Information', src: 'Virtual Disk Service', msg: `Volume ${letter}: was created and formatted with ${fs}.` })
    onClose()
  }

  return (
    <Dialog title="New Simple Volume Wizard" onClose={onClose} width={500}
      footer={<>
        {page > 1 && page < 5 && <button className="winos-btn" onClick={() => setPage(page - 1)}>&lt; Back</button>}
        {page < 5 ? <button className="winos-btn primary" onClick={() => setPage(page + 1)}>Next &gt;</button>
          : <button className="winos-btn primary" onClick={finish}>Finish</button>}
        <button className="winos-btn" onClick={onClose}>Cancel</button>
      </>}>
      {page === 1 && <div style={{ fontSize: 12.5 }}><h3 style={{ fontWeight: 600 }}>Welcome to the New Simple Volume Wizard</h3><p>This wizard helps you create a simple volume on a disk. A simple volume can only be on a single disk.</p><p>To continue, click Next.</p></div>}
      {page === 2 && <div style={{ fontSize: 12.5 }}>
        <h3 style={{ fontWeight: 600 }}>Specify Volume Size</h3>
        <div className="winos-grid2" style={{ marginTop: 10 }}>
          <span>Maximum disk space in MB:</span><span>{maxMB}</span>
          <span>Minimum disk space in MB:</span><span>8</span>
          <span>Simple volume size in MB:</span><input className="winos-input" type="number" value={sizeMB} min={8} max={maxMB} onChange={(e) => setSizeMB(Math.min(maxMB, Math.max(8, Number(e.target.value))))} />
        </div>
      </div>}
      {page === 3 && <div style={{ fontSize: 12.5 }}>
        <h3 style={{ fontWeight: 600 }}>Assign Drive Letter or Path</h3>
        <label style={{ display: 'block', marginTop: 10 }}><input type="radio" checked readOnly /> Assign the following drive letter:
          <select className="winos-input" style={{ marginLeft: 8 }} value={letter} onChange={(e) => setLetter(e.target.value)}>
            {[...'FGHIJKLMNOPQRSTUVWXYZ'].filter((l) => !used.includes(l)).map((l) => <option key={l}>{l}</option>)}
          </select>
        </label>
        <label style={{ display: 'block', marginTop: 6, color: '#888' }}><input type="radio" disabled /> Mount in the following empty NTFS folder</label>
        <label style={{ display: 'block', marginTop: 6, color: '#888' }}><input type="radio" disabled /> Do not assign a drive letter or drive path</label>
      </div>}
      {page === 4 && <div style={{ fontSize: 12.5 }}>
        <h3 style={{ fontWeight: 600 }}>Format Partition</h3>
        <label style={{ display: 'block', marginTop: 10 }}><input type="radio" checked readOnly /> Format this volume with the following settings:</label>
        <div className="winos-grid2" style={{ marginTop: 8, marginLeft: 22 }}>
          <span>File system:</span><select className="winos-input" value={fs} onChange={(e) => setFs(e.target.value)}><option>NTFS</option><option>ReFS</option><option>exFAT</option><option>FAT32</option></select>
          <span>Allocation unit size:</span><select className="winos-input"><option>Default</option><option>4096</option><option>8192</option><option>64K</option></select>
          <span>Volume label:</span><input className="winos-input" value={label} onChange={(e) => setLabel(e.target.value)} />
        </div>
        <label style={{ display: 'block', marginTop: 8, marginLeft: 22 }}><input type="checkbox" checked={quick} onChange={(e) => setQuick(e.target.checked)} /> Perform a quick format</label>
        <label style={{ display: 'block', marginLeft: 22 }}><input type="checkbox" /> Enable file and folder compression</label>
      </div>}
      {page === 5 && <div style={{ fontSize: 12.5 }}>
        <h3 style={{ fontWeight: 600 }}>Completing the New Simple Volume Wizard</h3>
        <p>You selected the following settings:</p>
        <pre style={{ background: '#f3f3f3', padding: 10, fontSize: 11.5 }}>{`Volume type: Simple Volume
Disk selected: Disk ${diskId}
Volume size: ${sizeMB} MB
Drive letter or path: ${letter}:
File system: ${fs}
Allocation unit size: Default
Volume label: ${label}
Quick format: ${quick ? 'Yes' : 'No'}`}</pre>
        <p>To close this wizard, click Finish.</p>
      </div>}
    </Dialog>
  )
}
