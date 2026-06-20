import { useState } from 'react'
import StatusIcon from './StatusIconInline'

function TreeRow({ depth = 0, label, status, active, onClick, onContextMenu, badge, badgeColor, caret, expanded, onToggle, hasChildren }) {
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
      {badge && (
        <span
          className="text-[8px] rounded px-1 font-bold leading-[1.4]"
          style={{ background: badgeColor || '#F5A623', color: '#1B2A3B' }}
          title={badgeColor === '#D9534F' ? 'Datastore full' : badgeColor === '#F5A623' ? 'Low free space' : undefined}
        >{badge}</span>
      )}
    </div>
  )
}

function DcClusterTree({
  dc, depth, hosts, vms, filterLabel, selectedNode, setSelectedNode, setActiveTab,
  onVmContextMenu, onHostContextMenu, onDcContextMenu, exp, setExp,
}) {
  const dcHosts = hosts.filter(h => (h.datacenter_id || 'dc-prod') === dc.id && filterLabel(h.name))
  const cluster = dc.clusters?.[0]

  return (
    <>
      <TreeRow
        depth={depth}
        label={dc.name}
        badge={dc.linked === false && dc.site === 'recovery' ? 'DR' : null}
        hasChildren
        expanded={exp[`dc-${dc.id}`]}
        onToggle={() => setExp(p => ({ ...p, [`dc-${dc.id}`]: !p[`dc-${dc.id}`] }))}
        onClick={() => { setSelectedNode({ type: 'datacenter', id: dc.id }); setActiveTab('summary') }}
        onContextMenu={onDcContextMenu ? (e => { e.preventDefault(); onDcContextMenu(e, dc) }) : undefined}
        active={selectedNode.type === 'datacenter' && selectedNode.id === dc.id}
      />
      {exp[`dc-${dc.id}`] && (
        <>
          <TreeRow
            depth={depth + 1}
            label={cluster?.name || 'Cluster-01'}
            hasChildren
            expanded={exp[`cluster-${dc.id}`]}
            onToggle={() => setExp(p => ({ ...p, [`cluster-${dc.id}`]: !p[`cluster-${dc.id}`] }))}
            onClick={() => setExp(p => ({ ...p, [`cluster-${dc.id}`]: !p[`cluster-${dc.id}`] }))}
          />
          {exp[`cluster-${dc.id}`] && dcHosts.map(host => (
            <div key={host.id}>
              <TreeRow
                depth={depth + 2}
                label={host.name}
                status={host.status}
                active={selectedNode.type === 'host' && selectedNode.id === host.id}
                badge={host.maintenance ? 'M' : null}
                hasChildren
                expanded={exp.hosts[host.id]}
                onToggle={() => setExp(p => ({ ...p, hosts: { ...p.hosts, [host.id]: !p.hosts[host.id] } }))}
                onClick={() => { setSelectedNode({ type: 'host', id: host.id }); setActiveTab('summary') }}
                onContextMenu={onHostContextMenu ? (e => { e.preventDefault(); onHostContextMenu(e, host) }) : undefined}
              />
              {exp.hosts[host.id] && vms.filter(v => v.host_id === host.id && filterLabel(v.name)).map(vm => (
                <TreeRow
                  key={vm.id}
                  depth={depth + 3}
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
  )
}

export default function VmwareInventoryTree({
  inv, hosts, vms, templates = [], datastores, networks,
  datacenters = [], linkedMode = false,
  filterLabel,
  selectedNode, setSelectedNode, setActiveTab,
  onVmContextMenu, onHostContextMenu, onDcContextMenu, onDsContextMenu, onNetContextMenu,
  onCreateVm, onDeployTemplate, onDeployOvf, onCreateVmWizard,
}) {
  const [exp, setExp] = useState({ vcenter: true, templates: true, storage: true, net: false, platform: true, hosts: {} })
  const toggle = (k) => setExp(p => ({ ...p, [k]: !p[k] }))

  const filteredTemplates = templates.filter(t => filterLabel(t.name))
  const visibleDcs = (datacenters.length ? datacenters : [{ id: 'dc-prod', name: inv.datacenter || 'DC-Prod', clusters: [{ name: inv.cluster || 'Cluster-01' }] }])
    .filter(dc => dc.site !== 'recovery' || linkedMode)

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
          <button type="button" onClick={onCreateVmWizard || onCreateVm} title="New VM Wizard" className="w-[22px] h-[22px] flex items-center justify-center rounded-[5px] border border-[#2d3a4a] bg-[#243447] text-[#00C8FF] text-[15px] leading-none">+</button>
        </div>
      </div>

      <TreeRow
        depth={0}
        label="vCenter Server"
        hasChildren
        caret
        expanded={exp.vcenter}
        onToggle={() => toggle('vcenter')}
        active={selectedNode.type === 'vcenter'}
        onClick={() => { setSelectedNode({ type: 'vcenter', id: 'vcenter' }); setActiveTab('summary') }}
      />
      {exp.vcenter && visibleDcs.map(dc => (
        <DcClusterTree
          key={dc.id}
          dc={dc}
          depth={1}
          hosts={hosts}
          vms={vms}
          filterLabel={filterLabel}
          selectedNode={selectedNode}
          setSelectedNode={setSelectedNode}
          setActiveTab={setActiveTab}
          onVmContextMenu={onVmContextMenu}
          onHostContextMenu={onHostContextMenu}
          onDcContextMenu={onDcContextMenu}
          exp={exp}
          setExp={setExp}
        />
      ))}

      <TreeRow depth={0} label="Platform Services" hasChildren expanded={exp.platform} onToggle={() => toggle('platform')} onClick={() => toggle('platform')} />
      {exp.platform && (
        <>
          <TreeRow depth={1} label="NSX-T" active={selectedNode.type === 'nsx'} onClick={() => { setSelectedNode({ type: 'nsx', id: 'nsx' }); setActiveTab('summary') }} />
          <TreeRow depth={1} label="Site Recovery" active={selectedNode.type === 'srm'} onClick={() => { setSelectedNode({ type: 'srm', id: 'srm' }); setActiveTab('summary') }} />
          <TreeRow depth={1} label="VAMI Updates" active={selectedNode.type === 'vami'} onClick={() => { setSelectedNode({ type: 'vami', id: 'vami' }); setActiveTab('summary') }} />
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
          badge={ds.warning === 'critical' ? '!' : ds.warning === 'warning' ? '⚠' : null}
          badgeColor={ds.warning === 'critical' ? '#D9534F' : ds.warning === 'warning' ? '#F5A623' : null}
          active={selectedNode.type === 'datastore' && selectedNode.id === ds.id}
          onClick={() => { setSelectedNode({ type: 'datastore', id: ds.id }); setActiveTab('summary') }}
          onContextMenu={onDsContextMenu ? (e => { e.preventDefault(); onDsContextMenu(e, ds) }) : undefined}
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
          onContextMenu={onNetContextMenu ? (e => { e.preventDefault(); onNetContextMenu(e, net) }) : undefined}
        />
      ))}

      <TreeRow
        depth={0}
        label="Administration"
        active={selectedNode.type === 'admin'}
        onClick={() => { setSelectedNode({ type: 'admin', id: 'admin' }); setActiveTab('summary') }}
      />
    </>
  )
}
