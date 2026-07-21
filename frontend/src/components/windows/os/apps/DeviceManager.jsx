import { useState } from 'react'
import { ChevronRight, Cpu, Monitor } from 'lucide-react'
import { useOS } from '../store'
import { useCtxMenu, Dialog, Tabs } from '../ui'

export default function DeviceManager() {
  const os = useOS()
  const ctx = useCtxMenu()
  const [expanded, setExpanded] = useState({ Computer: true })
  const [sel, setSel] = useState(null)
  const [props, setProps] = useState(null)
  const [scanning, setScanning] = useState(false)

  const toggleDevice = (cls, item) => {
    const disabled = !item.disabled
    os.setDevice(cls, item.name, { disabled })
    if (os.labAction) {
      os.labAction(disabled ? 'disable_device' : 'enable_device', { name: item.name, class: cls, cls })
    }
  }

  const scanDevices = () => {
    setScanning(true)
    if (os.labAction) os.labAction('scan_devices', {})
    setTimeout(() => setScanning(false), 1200)
  }

  const devCtx = (cls, item) => (e) => {
    e.preventDefault(); setSel(`${cls}/${item.name}`)
    ctx.open(e.clientX, e.clientY, [
      { label: 'Update driver', onClick: () => setProps({ cls, item, tab: 'Driver', updating: true }) },
      { label: item.disabled ? 'Enable device' : 'Disable device', onClick: () => toggleDevice(cls, item) },
      { label: 'Uninstall device' }, { sep: true },
      { label: 'Scan for hardware changes', onClick: scanDevices },
      { sep: true }, { label: 'Properties', onClick: () => setProps({ cls, item, tab: 'General' }) },
    ])
  }

  return (
    <div className="winos-app">
      <div className="winos-toolbar">
        <span style={{ fontSize: 12 }}>File &nbsp; Action &nbsp; View &nbsp; Help</span>
        <span style={{ flex: 1 }} />
        <button className="winos-btn" onClick={scanDevices}>Scan for hardware changes</button>
      </div>
      <div className="winos-main" style={{ padding: '6px 0' }}>
        <div className="winos-tree-row" style={{ fontWeight: 600 }}><Monitor size={14} /> SERVER01</div>
        {scanning && <div style={{ padding: '4px 24px', color: '#06c', fontSize: 12 }}>Scanning for hardware changes…</div>}
        {os.devices.map((cat) => (
          <div key={cat.cls}>
            <div className="winos-tree-row" style={{ paddingLeft: 24 }} onClick={() => setExpanded((x) => ({ ...x, [cat.cls]: !x[cat.cls] }))}>
              <ChevronRight size={13} style={{ transform: expanded[cat.cls] ? 'rotate(90deg)' : 'none' }} />
              {cat.cls === 'Processors' ? <Cpu size={13} /> : '📁'} {cat.cls}
            </div>
            {expanded[cat.cls] && cat.items.map((item, i) => (
              <div key={i} className={`winos-tree-row ${sel === `${cat.cls}/${item.name}` ? 'sel' : ''}`} style={{ paddingLeft: 50 }}
                onClick={() => setSel(`${cat.cls}/${item.name}`)} onDoubleClick={() => setProps({ cls: cat.cls, item, tab: 'General' })} onContextMenu={devCtx(cat.cls, item)}>
                {item.disabled ? '⬇️' : '🔧'} <span style={{ opacity: item.disabled ? 0.5 : 1 }}>{item.name}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
      {props && <DeviceProps {...props} onClose={() => setProps(null)} />}
    </div>
  )
}

function DeviceProps({ cls, item, tab: initTab, updating, onClose }) {
  const os = useOS()
  const live = os.devices.find((c) => c.cls === cls)?.items.find((i) => i.name === item.name) || item
  const [tab, setTab] = useState(initTab || 'General')
  const [searchState, setSearchState] = useState(updating ? 'searching' : null)
  const [detailProp, setDetailProp] = useState('Device description')

  if (searchState === 'searching') setTimeout(() => setSearchState('done'), 1500)

  const detailValues = {
    'Device description': live.name,
    'Hardware Ids': `PCI\\VEN_15AD&DEV_07B0&SUBSYS_07B015AD&REV_01`,
    'Compatible Ids': `PCI\\VEN_15AD&DEV_07B0`,
    'Service': live.driver?.replace('.sys', ''),
    'Class': cls,
    'Class Guid': '{4d36e972-e325-11ce-bfc1-08002be10318}',
    'Driver key': '{4d36e972-e325-11ce-bfc1-08002be10318}\\0001',
  }

  return (
    <Dialog title={`${live.name} Properties`} onClose={onClose} width={440}
      footer={<><button className="winos-btn primary" onClick={onClose}>OK</button><button className="winos-btn" onClick={onClose}>Cancel</button></>}>
      <Tabs tabs={['General', 'Driver', 'Details', 'Events', 'Resources']} active={tab} onChange={setTab} />
      <div style={{ paddingTop: 12, fontSize: 12.5 }}>
        {tab === 'General' && (
          <div className="winos-grid2">
            <span style={{ gridColumn: '1/-1', fontWeight: 600 }}>{live.name}</span>
            <span style={{ color: '#666' }}>Device type:</span><span>{cls}</span>
            <span style={{ color: '#666' }}>Manufacturer:</span><span>{live.provider}</span>
            <span style={{ color: '#666' }}>Location:</span><span>PCI bus 3, device 0, function 0</span>
            <span style={{ color: '#666', alignSelf: 'start' }}>Device status:</span>
            <span>{live.disabled ? 'This device is disabled. (Code 22)' : 'This device is working properly.'}</span>
          </div>
        )}
        {tab === 'Driver' && (
          <div>
            {searchState === 'searching' && <p style={{ color: '#06c' }}>Searching Windows Update for drivers…</p>}
            {searchState === 'done' && <p style={{ color: '#107c10' }}>The best drivers for your device are already installed.</p>}
            <div className="winos-grid2">
              <span style={{ color: '#666' }}>Driver Provider:</span><span>{live.provider}</span>
              <span style={{ color: '#666' }}>Driver Date:</span><span>{live.date}</span>
              <span style={{ color: '#666' }}>Driver Version:</span><span>{live.ver}</span>
              <span style={{ color: '#666' }}>Digital Signer:</span><span>Microsoft Windows Hardware Compatibility Publisher</span>
            </div>
            <div style={{ display: 'flex', gap: 6, marginTop: 14, flexWrap: 'wrap' }}>
              <button className="winos-btn">Driver Details</button>
              <button className="winos-btn" onClick={() => setSearchState('searching')}>Update Driver</button>
              <button className="winos-btn" disabled>Roll Back Driver</button>
              <button className="winos-btn" onClick={() => {
                const disabled = !live.disabled
                os.setDevice(cls, live.name, { disabled })
                if (os.labAction) {
                  os.labAction(disabled ? 'disable_device' : 'enable_device', { name: live.name, class: cls, cls })
                }
              }}>{live.disabled ? 'Enable Device' : 'Disable Device'}</button>
              <button className="winos-btn">Uninstall Device</button>
            </div>
          </div>
        )}
        {tab === 'Details' && (
          <div>
            <div style={{ color: '#666', marginBottom: 4 }}>Property</div>
            <select className="winos-input" style={{ width: '100%', marginBottom: 10 }} value={detailProp} onChange={(e) => setDetailProp(e.target.value)}>
              {Object.keys(detailValues).map((k) => <option key={k}>{k}</option>)}
            </select>
            <div style={{ color: '#666', marginBottom: 4 }}>Value</div>
            <div style={{ border: '1px solid #ddd', minHeight: 80, padding: 8, fontFamily: 'Consolas, monospace', fontSize: 12 }}>{detailValues[detailProp]}</div>
          </div>
        )}
        {tab === 'Events' && (
          <div style={{ border: '1px solid #ddd', height: 120, overflow: 'auto' }}>
            {[['2023-08-15 10:02:11', 'Device configured (' + live.driver + ')'], ['2023-08-15 10:02:09', 'Device started (' + (live.driver || '') + ')'], ['2023-08-15 10:02:08', 'Device installed (' + (live.driver || '') + ')']].map(([t, m], i) => (
              <div key={i} style={{ padding: '4px 8px', borderBottom: '1px solid #f0f0f0', fontSize: 12 }}><span style={{ color: '#888' }}>{t}</span> — {m}</div>
            ))}
          </div>
        )}
        {tab === 'Resources' && (
          <div>
            <div style={{ color: '#666', marginBottom: 6 }}>Resource settings:</div>
            <div style={{ border: '1px solid #ddd', height: 100, overflow: 'auto', fontFamily: 'Consolas, monospace', fontSize: 12 }}>
              <div style={{ padding: '3px 8px' }}>Memory Range&nbsp;&nbsp;&nbsp;FB000000 - FBFFFFFF</div>
              <div style={{ padding: '3px 8px' }}>I/O Range&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;1400 - 1407</div>
              <div style={{ padding: '3px 8px' }}>IRQ&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0xFFFFFFFB (-5)</div>
            </div>
            <div style={{ marginTop: 8, color: '#666' }}>Conflicting device list:</div>
            <div style={{ border: '1px solid #ddd', padding: 8, fontSize: 12 }}>No conflicts.</div>
          </div>
        )}
      </div>
    </Dialog>
  )
}
