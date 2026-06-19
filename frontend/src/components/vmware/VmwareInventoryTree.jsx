import { useState } from 'react'
import StatusIcon from './StatusIconInline'

function TreeRow({ depth = 0, label, status, active, onClick, onContextMenu, badge, caret, expanded, onToggle, hasChildren }) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onContextMenu={onContextMenu}
      onKeyDown={e => e.key === 'Enter' && onClick?.()}
      className={`vm-nav-item ${active ? 'vm-nav-item-active' : ''}`}
      style={{ paddingLeft: 10 + depth * 14 }}
    >
      {hasChildren ? (
        <span
          role="button"
          tabIndex={-1}
          onClick={e => { e.stopPropagation(); onToggle?.() }}
          className="text-[8px] text-[#8FA5B8] w-2.5 transition-transform"
          style={{ transform: expanded ? 'rotate(90deg)' : 'none' }}
        >▶</span>
      ) : <span className="w-2.5 shrink-0" />}
      {status != null && <StatusIcon status={status} size={8} />}
      <span className="truncate flex-1">{label}</span>
      {badge && <span className="text-[8px] bg-[#F5A623] text-[#1B2A3B] rounded px-1 font-bold">{badge}</span>}
    </div>
  )
}

export default function VmwareInventoryTree({
  inv, hosts, vms, templates = [], datastores, networks,
  filterLabel,
  selectedNode, setSelectedNode, setActiveTab,
  onVmContextMenu, onCreateVm, onDeployTemplate, onDeployOvf,
}) {
  const [exp, setExp] = useState({ vcenter: true, dc: true, cluster: true, hosts: {}, vms: true, templates: true, storage: true, net: false })
  const toggle = (k) => setExp(p => ({ ...p, [k]: !p[k] }))

  const filteredHosts = hosts.filter(h => filterLabel(h.name))
  const filteredVms = vms.filter(v => filterLabel(v.name))
  const filteredTemplates = templates.filter(t => filterLabel(t.name))

  return (
    <>
      <div className="flex items-center justify-between px-3 pb-2 gap-1">
        <span className="vm-nav-label p-0">Inventory</span>
        <div className="flex gap-1">
          {templates.length > 0 && onDeployTemplate && (
            <button type="button" onClick={onDeployTemplate} title="Deploy from template" className="w-[22px] h-[22px] flex items-center justify-center rounded-[5px] border border-[#2d3a4a] bg-[#243447] text-[#F5A623] text-[10px] leading-none font-bold">T</button>
          )}
          {onDeployOvf && (
            <button type="button" onClick={onDeployOvf} title="Deploy OVF from content library" className="w-[22px] h-[22px] flex items-center justify-center rounded-[5px] border border-[#2d3a4a] bg-[#243447] text-[#5DB85D] text-[10px] leading-none font-bold">O</button>
          )}
          <button type="button" onClick={onCreateVm} title="New VM" className="w-[22px] h-[22px] flex items-center justify-center rounded-[5px] border border-[#2d3a4a] bg-[#243447] text-[#00C8FF] text-[15px] leading-none">+</button>
        </div>
      </div>

      <TreeRow depth={0} label="vCenter Server" hasChildren caret expanded={exp.vcenter} onToggle={() => toggle('vcenter')} onClick={() => toggle('vcenter')} />
      {exp.vcenter && (
        <>
          <TreeRow depth={1} label={inv.datacenter || 'DC-Prod'} hasChildren expanded={exp.dc} onToggle={() => toggle('dc')} onClick={() => toggle('dc')} />
          {exp.dc && (
            <>
              <TreeRow depth={2} label={inv.cluster || 'Cluster-01'} hasChildren expanded={exp.cluster} onToggle={() => toggle('cluster')} onClick={() => toggle('cluster')} />
              {exp.cluster && filteredHosts.map(host => (
                <div key={host.id}>
                  <TreeRow
                    depth={3}
                    label={host.name}
                    status={host.status}
                    active={selectedNode.type === 'host' && selectedNode.id === host.id}
                    badge={host.maintenance ? 'M' : null}
                    hasChildren
                    expanded={exp.hosts[host.id]}
                    onToggle={() => setExp(p => ({ ...p, hosts: { ...p.hosts, [host.id]: !p.hosts[host.id] } }))}
                    onClick={() => { setSelectedNode({ type: 'host', id: host.id }); setActiveTab('summary') }}
                  />
                  {exp.hosts[host.id] && filteredVms.filter(v => v.host_id === host.id).map(vm => (
                    <TreeRow
                      key={vm.id}
                      depth={4}
                      label={vm.name}
                      status={vm.power}
                      active={selectedNode.type === 'vm' && selectedNode.id === vm.id}
                      onClick={() => { setSelectedNode({ type: 'vm', id: vm.id }); setActiveTab('summary') }}
                      onContextMenu={e => { e.preventDefault(); onVmContextMenu(e, vm) }}
                    />
                  ))}
                </div>
              ))}
            </>
          )}
        </>
      )}

      {filteredTemplates.length > 0 && (
        <>
          <TreeRow depth={0} label="Templates" hasChildren expanded={exp.templates} onToggle={() => toggle('templates')} onClick={() => toggle('templates')} />
          {exp.templates && filteredTemplates.map(tpl => (
            <TreeRow
              key={tpl.id}
              depth={1}
              label={tpl.name}
              active={selectedNode.type === 'template' && selectedNode.id === tpl.id}
              onClick={() => { setSelectedNode({ type: 'template', id: tpl.id }); setActiveTab('summary') }}
            />
          ))}
        </>
      )}

      <TreeRow depth={0} label="Storage" hasChildren expanded={exp.storage} onToggle={() => toggle('storage')} onClick={() => toggle('storage')} />
      {exp.storage && datastores.filter(d => filterLabel(d.name)).map(ds => (
        <TreeRow
          key={ds.id}
          depth={1}
          label={ds.name}
          status={ds.accessible ? 'connected' : 'disconnected'}
          active={selectedNode.type === 'datastore' && selectedNode.id === ds.id}
          onClick={() => { setSelectedNode({ type: 'datastore', id: ds.id }); setActiveTab('summary') }}
        />
      ))}

      <TreeRow depth={0} label="Networking" hasChildren expanded={exp.net} onToggle={() => toggle('net')} onClick={() => toggle('net')} />
      {exp.net && networks.filter(n => filterLabel(n.name)).map(net => (
        <TreeRow
          key={net.id}
          depth={1}
          label={net.name}
          status="connected"
          active={selectedNode.type === 'network' && selectedNode.id === net.id}
          onClick={() => { setSelectedNode({ type: 'network', id: net.id }); setActiveTab('summary') }}
        />
      ))}
    </>
  )
}
