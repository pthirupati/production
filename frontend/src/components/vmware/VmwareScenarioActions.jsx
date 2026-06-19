const SCENARIO_ACTIONS = [
  { action: 'sync_ntp', label: 'Sync NTP on all hosts', group: 'Host' },
  { action: 'clear_coredump', label: 'Clear ESXi core dump', group: 'Host', payload: { host_name: 'esxi-01.fixitlab.local' } },
  { action: 'toggle_ssh', label: 'Toggle host SSH', group: 'Host', payload: { host_name: 'esxi-01.fixitlab.local' } },
  { action: 'fix_admission_control', label: 'Fix HA admission control', group: 'Cluster' },
  { action: 'run_drs', label: 'Run DRS balance', group: 'Cluster' },
  { action: 'disable_drs', label: 'Disable DRS', group: 'Cluster' },
  { action: 'claim_vsan_disk', label: 'Claim vSAN disk', group: 'Storage' },
  { action: 'complete_storage_vmotion', label: 'Complete storage vMotion', group: 'Storage' },
  { action: 'fix_dv_switch_mtu', label: 'Fix DV switch MTU', group: 'Network' },
  { action: 'create_portgroup', label: 'Create missing port group', group: 'Network', payload: { name: 'Prod-VLAN-200', vlan: 200 } },
  { action: 'resolve_vmotion', label: 'Resolve failed vMotion', group: 'vMotion' },
  { action: 'convert_template', label: 'Convert template to VM', group: 'Templates', payload: { template_name: 'rhel8-template' } },
  { action: 'renew_vcenter_cert', label: 'Renew vCenter certificate', group: 'vCenter' },
  { action: 'expand_vcenter_db', label: 'Expand vCenter DB partition', group: 'vCenter' },
  { action: 'unlock_sso', label: 'Unlock SSO administrator', group: 'vCenter' },
  { action: 'upgrade_tools', label: 'Upgrade VMware Tools', group: 'VM', needsVm: true },
  { action: 'connect_network', label: 'Connect network adapter', group: 'VM', needsVm: true },
  { action: 'answer_question', label: 'Answer pending VM question', group: 'VM', needsVm: true },
  { action: 'reduce_cpu_contention', label: 'Reduce CPU contention', group: 'VM', needsVm: true },
]

export default function VmwareScenarioActions({ selectedVm, onAction, acting }) {
  const groups = [...new Set(SCENARIO_ACTIONS.map(a => a.group))]

  const fire = (item) => {
    const payload = { ...(item.payload || {}) }
    if (item.needsVm && selectedVm) payload.vm_id = selectedVm.id
    onAction(item.action, payload)
  }

  return (
    <div className="vm-panel">
      <div className="vm-panel-header">Lab scenario actions</div>
      <div className="vm-panel-body space-y-4 max-h-[420px] overflow-y-auto">
        {groups.map(group => (
          <div key={group}>
            <p className="text-[10px] font-bold text-[#8FA5B8] uppercase tracking-wider mb-2">{group}</p>
            <div className="flex flex-wrap gap-2">
              {SCENARIO_ACTIONS.filter(a => a.group === group).map(item => (
                <button
                  key={item.action}
                  type="button"
                  disabled={acting || (item.needsVm && !selectedVm)}
                  onClick={() => fire(item)}
                  className="vm-btn vm-btn-blue text-[10px] py-1 px-2 disabled:opacity-40"
                  title={item.needsVm && !selectedVm ? 'Select a VM first' : item.label}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
