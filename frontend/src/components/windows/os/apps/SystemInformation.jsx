import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import { useOS } from '../store'

export default function SystemInformation() {
  const os = useOS()
  const [sel, setSel] = useState('System Summary')
  const [expand, setExpand] = useState({ 'Components': true, 'Software Environment': true })

  const tree = [
    { id: 'System Summary' },
    { id: 'Hardware Resources', kids: ['Conflicts/Sharing', 'DMA', 'Forced Hardware', 'I/O', 'IRQs', 'Memory'] },
    { id: 'Components', kids: ['Display', 'Network', 'Storage', 'Ports', 'Problem Devices', 'USB'] },
    { id: 'Software Environment', kids: ['System Drivers', 'Environment Variables', 'Running Tasks', 'Services', 'Startup Programs'] },
  ]

  const data = buildData(os)

  return (
    <div className="winos-app">
      <div className="winos-toolbar"><span style={{ fontSize: 12 }}>File &nbsp; Edit &nbsp; View &nbsp; Help</span></div>
      <div className="winos-split">
        <div className="winos-tree" style={{ width: 230 }}>
          {tree.map((n) => (
            <div key={n.id}>
              <div className={`winos-tree-row ${sel === n.id ? 'sel' : ''}`} onClick={() => { setSel(n.id); if (n.kids) setExpand((x) => ({ ...x, [n.id]: !x[n.id] })) }}>
                {n.kids ? <ChevronRight size={12} style={{ transform: expand[n.id] ? 'rotate(90deg)' : '' }} /> : <span style={{ width: 12, display: 'inline-block' }} />}{n.id}
              </div>
              {n.kids && expand[n.id] && n.kids.map((k) => (
                <div key={k} className={`winos-tree-row ${sel === k ? 'sel' : ''}`} style={{ paddingLeft: 36 }} onClick={() => setSel(k)}>{k}</div>
              ))}
            </div>
          ))}
        </div>
        <div className="winos-main">
          <table className="winos-table">
            <thead><tr><th style={{ width: '40%' }}>Item</th><th>Value</th></tr></thead>
            <tbody>{(data[sel] || [['Item', 'No information available for this view.']]).map(([k, v], i) => (
              <tr key={i}><td>{k}</td><td>{v}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function buildData(os) {
  return {
    'System Summary': [
      ['OS Name', 'Microsoft Windows Server 2022 Standard Evaluation'],
      ['Version', '10.0.20348 Build 20348'], ['System Manufacturer', 'VMware, Inc.'],
      ['System Model', 'VMware Virtual Platform'], ['System Type', 'x64-based PC'],
      ['Processor', `${os.computer.cpu}, 3000 Mhz, 8 Core(s), 8 Logical Processor(s)`],
      ['BIOS Version/Date', 'VMware, Inc. VMW71.00V.0, 11/12/2020'],
      ['SMBIOS Version', '2.7'], ['BaseBoard Manufacturer', 'Intel Corporation'],
      ['Installed Physical Memory (RAM)', '16.0 GB'], ['Total Physical Memory', '16.0 GB'],
      ['Available Physical Memory', '9.8 GB'], ['Total Virtual Memory', '34.0 GB'],
      ['Domain', os.computer.domain], ['Computer Name', os.computer.name],
      ['Time Zone', 'Eastern Standard Time'], ['Hyper-V - VM Monitor Mode Extensions', 'Yes'],
    ],
    'Display': [
      ['Name', 'VMware SVGA 3D'], ['Adapter Type', 'VMware SVGA 3D, VMware, Inc. compatible'],
      ['Adapter RAM', '128.00 MB'], ['Driver Version', '8.17.2.14'],
      ['Resolution', '1920 x 1080 x 60 hertz'], ['Bits/Pixel', '32'],
    ],
    'Network': os.adapters.flatMap((a) => [[`[${a.name}] Name`, a.desc], [`[${a.name}] IP Address`, a.ipv4], [`[${a.name}] MAC`, a.mac], [`[${a.name}] DHCP Enabled`, a.dhcp ? 'Yes' : 'No']]),
    'Storage': Object.entries(os.vfs.drives).filter(([, d]) => !d.noMedia).flatMap(([l, d]) => [[`Drive ${l}:`, `${d.label}, ${d.fs}, ${(d.totalGB - d.usedGB).toFixed(1)} GB free of ${d.totalGB} GB`]]),
    'Services': os.services.slice(0, 30).map((s) => [s.display, `${s.status} · ${s.startup}`]),
    'Running Tasks': os.processes.slice(0, 30).map((p) => [p.name, `PID ${p.pid} · ${p.mem.toFixed(1)} MB`]),
    'Startup Programs': os.startupItems.map((i) => [i.name, `${i.publisher} · ${i.enabled ? 'Enabled' : 'Disabled'}`]),
    'Environment Variables': [['Path', 'C:\\Windows\\system32;C:\\Windows;C:\\Windows\\System32\\Wbem'], ['NUMBER_OF_PROCESSORS', '8'], ['OS', 'Windows_NT'], ['PROCESSOR_ARCHITECTURE', 'AMD64'], ['windir', 'C:\\Windows'], ['TEMP', 'C:\\Windows\\TEMP']],
    'System Drivers': os.devices.flatMap((c) => c.items.slice(0, 1).map((it) => [it.driver, `${c.cls} · ${it.ver} · Running`])),
    'IRQs': Array.from({ length: 10 }, (_, i) => [`IRQ ${i}`, i === 0 ? 'System timer' : i === 1 ? 'PS/2 Keyboard' : `(ISA) ${i} reserved`]),
    'USB': [['USB Root Hub (USB 3.0)', 'Working properly'], ['Intel(R) USB 3.0 eXtensible Host Controller', 'Working properly']],
    'Ports': [['Communications Port (COM1)', 'OK'], ['ECP Printer Port (LPT1)', 'OK']],
    'Problem Devices': [['', 'No problem devices found.']],
    'Memory': [['Total Physical Memory', '16.0 GB'], ['Available Physical Memory', '9.8 GB'], ['Memory Module 1', '8 GB DIMM @ 3200 MHz'], ['Memory Module 2', '8 GB DIMM @ 3200 MHz']],
  }
}
