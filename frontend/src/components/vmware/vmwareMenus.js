/* Shared vSphere menu builders. Each returns an array of menu items used by
   both the right-click context menu (VmwareContextMenu) and the "Actions"
   dropdown (VmwareActionsMenu). Items are either:
     - { label, icon, onClick, disabled, color }   leaf
     - { label, icon, children: [...] }            submenu
     - { divider: true }
   Every onClick calls a real engine action via `onAction` (which mutates
   get_state) OR a UI sentinel (e.g. '__edit__', '__snapshot__') that the
   simulator maps to a modal/panel. */

/* ── VM (requirement 3) ─────────────────────────────────────────────── */
export function buildVmMenu(vm, onAction, onConsole, onClose, acting) {
  const isOn = vm.power === 'poweredOn'
  const isOff = vm.power === 'poweredOff'
  const isSuspended = vm.power === 'suspended'
  const toolsCurrent = (vm.vmware_tools_status || (vm.tools === 'ok' ? 'current' : 'notRunning')) === 'current'
  const id = vm.id
  return [
    {
      label: 'Power', icon: 'Power', children: [
        { label: 'Power On', icon: 'Power', onClick: () => onAction('power_on', { vm_id: id }), disabled: isOn || acting },
        { label: 'Power Off', icon: 'Power', onClick: () => onAction('power_off', { vm_id: id }), disabled: isOff || acting, color: '#D9534F' },
        { label: 'Suspend', icon: 'Pause', onClick: () => onAction('__suspend__', vm), disabled: !isOn || acting },
        ...(isSuspended ? [{ label: 'Resume', icon: 'Power', onClick: () => onAction('resume', { vm_id: id }), disabled: acting }] : []),
        { label: 'Reset', icon: 'Power', onClick: () => onAction('reboot', { vm_id: id }), disabled: !isOn || acting },
        { divider: true },
        { label: 'Shut Down Guest OS', icon: 'Power', onClick: () => onAction('power_off_guest', { vm_id: id }), disabled: !isOn || acting },
        { label: 'Restart Guest OS', icon: 'Power', onClick: () => onAction('reboot_guest', { vm_id: id }), disabled: !isOn || acting },
      ],
    },
    {
      label: 'Guest OS', icon: 'Terminal', children: [
        { label: toolsCurrent ? 'VMware Tools (current)' : 'Install/Upgrade VMware Tools', icon: 'Wrench', onClick: () => onAction('upgrade_vmware_tools', { vm_id: id }), disabled: toolsCurrent || acting },
        { label: 'Restart Guest', icon: 'Power', onClick: () => onAction('reboot_guest', { vm_id: id }), disabled: !isOn || acting },
      ],
    },
    {
      label: 'Snapshots', icon: 'Camera', children: [
        { label: 'Take Snapshot…', icon: 'Camera', onClick: () => onAction('__snapshot__', vm) },
        { label: 'Manage Snapshots…', icon: 'Camera', onClick: () => onAction('__manage_snapshots__', vm) },
        { label: 'Revert to Latest Snapshot', icon: 'RefreshCw', onClick: () => onAction('__revert_latest__', vm), disabled: !(vm.snapshots || []).length || acting },
        { label: 'Consolidate', icon: 'Layers', onClick: () => onAction('__consolidate__', vm), disabled: acting },
      ],
    },
    { divider: true },
    { label: 'Migrate…', icon: 'ArrowRightLeft', onClick: () => onAction('__migrate__', vm) },
    {
      label: 'Clone', icon: 'Copy', children: [
        { label: 'Clone to Virtual Machine…', icon: 'Copy', onClick: () => onAction('__clone__', vm) },
        { label: 'Clone to Template…', icon: 'Boxes', onClick: () => onAction('convert_to_template', { vm_id: id }), disabled: !isOff || acting },
      ],
    },
    {
      label: 'Fault Tolerance', icon: 'ShieldCheck', children: [
        { label: 'Turn On Fault Tolerance', icon: 'ShieldCheck', onClick: () => onAction('__ft_on__', vm), disabled: acting },
      ],
    },
    { divider: true },
    { label: 'Edit Settings…', icon: 'Settings', onClick: () => onAction('__edit__', vm) },
    { label: 'Add Disk…', icon: 'HardDrive', onClick: () => onAction('__add_disk__', vm) },
    { label: 'Add Network Adapter…', icon: 'Network', onClick: () => onAction('__add_nic__', vm) },
    {
      label: 'Move To…', icon: 'Move', onClick: () => onAction('__move_vm__', vm),
    },
    { label: 'Rename…', icon: 'Pencil', onClick: () => onAction('__rename__', vm) },
    {
      label: 'Tags & Custom Attributes', icon: 'Tag', children: [
        { label: 'Assign Tag…', icon: 'Tag', onClick: () => onAction('__assign_tag__', vm) },
        { label: 'Remove Tag', icon: 'Tag', onClick: () => onAction('__remove_tag__', vm) },
      ],
    },
    { label: 'Add Permission…', icon: 'ShieldCheck', onClick: () => onAction('__add_permission__', vm) },
    { divider: true },
    { label: 'Open Remote Console', icon: 'Terminal', onClick: () => { onConsole?.(vm); onClose?.() }, keepOpen: false },
    { label: 'Open Web Console', icon: 'Terminal', onClick: () => { onConsole?.(vm); onClose?.() }, keepOpen: false },
    { divider: true },
    { label: 'Delete from Disk', icon: 'Trash2', onClick: () => onAction('__delete__', vm), disabled: isOn || acting, color: '#D9534F' },
  ]
}

/* ── Host (requirement 2) ───────────────────────────────────────────── */
export function buildHostMenu(host, onAction, acting) {
  const inMaint = !!host.maintenance
  const connected = host.status === 'connected'
  const id = host.id
  return [
    { label: 'New Virtual Machine…', icon: 'Plus', onClick: () => onAction('__create_vm__', host) },
    { label: 'Deploy OVF Template…', icon: 'Cloud', onClick: () => onAction('__deploy_ovf__', host) },
    { divider: true },
    { label: 'New Resource Pool…', icon: 'Boxes', onClick: () => onAction('__new_resource_pool__', host) },
    { label: 'New vApp…', icon: 'Layers', onClick: () => onAction('__new_vapp__', host) },
    { divider: true },
    {
      label: 'Maintenance Mode', icon: 'Wrench', children: [
        { label: 'Enter Maintenance Mode', icon: 'Wrench', onClick: () => onAction('enter_maintenance', { host_id: id }), disabled: inMaint || acting },
        { label: 'Exit Maintenance Mode', icon: 'Wrench', onClick: () => onAction('exit_maintenance', { host_id: id }), disabled: !inMaint || acting },
      ],
    },
    {
      label: 'Connection', icon: 'RefreshCw', children: [
        { label: 'Connect', icon: 'RefreshCw', onClick: () => onAction('reconnect_host', { host_id: id }), disabled: connected || acting },
        { label: 'Disconnect', icon: 'RefreshCw', onClick: () => onAction('__disconnect_host__', host), disabled: !connected || acting },
      ],
    },
    {
      label: 'Power', icon: 'Power', children: [
        { label: 'Power On', icon: 'Power', onClick: () => onAction('__host_power_on__', host), disabled: acting },
        { label: 'Shut Down', icon: 'Power', onClick: () => onAction('__host_shutdown__', host), disabled: acting, color: '#D9534F' },
        { label: 'Reboot', icon: 'Power', onClick: () => onAction('__host_reboot__', host), disabled: acting },
      ],
    },
    {
      label: 'Certificates', icon: 'ShieldCheck', children: [
        { label: 'Renew CA Certificate', icon: 'ShieldCheck', onClick: () => onAction('renew_host_cert', { host_id: id }), disabled: acting },
        { label: 'Refresh CA Certificates', icon: 'RefreshCw', onClick: () => onAction('renew_host_cert', { host_id: id }), disabled: acting },
      ],
    },
    {
      label: 'Storage', icon: 'Database', children: [
        { label: 'New Datastore…', icon: 'Database', onClick: () => onAction('__create_datastore__', host) },
        { label: 'Rescan Storage', icon: 'RefreshCw', onClick: () => onAction('rescan_storage', { host_id: id }), disabled: acting },
      ],
    },
    { label: 'Add Networking…', icon: 'Network', onClick: () => onAction('__create_vswitch__', host) },
    {
      label: 'Host Profiles', icon: 'FileText', children: [
        { label: 'Extract Host Profile…', icon: 'FileText', onClick: () => onAction('extract_host_profile', { host_id: id }), disabled: acting },
        { label: 'Attach Host Profile…', icon: 'FileText', onClick: () => onAction('attach_host_profile', { host: host.name || id, name: `Profile-${host.name || id}` }), disabled: acting },
      ],
    },
    { label: 'Export System Logs…', icon: 'FileText', onClick: () => onAction('export_system_logs', { host_id: id }), disabled: acting },
    { divider: true },
    { label: 'Settings', icon: 'Settings', onClick: () => onAction('__host_settings__', host) },
  ]
}

/* ── Datacenter (requirement 1) ─────────────────────────────────────── */
export function buildDatacenterMenu(dc, onAction, acting) {
  const id = dc.id
  return [
    { label: 'Add Host…', icon: 'Server', onClick: () => onAction('__add_host__', dc) },
    { label: 'New Cluster…', icon: 'Boxes', onClick: () => onAction('__new_cluster__', dc) },
    {
      label: 'New Folder', icon: 'Folder', children: [
        { label: 'New Host Folder…', icon: 'Folder', onClick: () => onAction('__new_folder_host__', dc) },
        { label: 'New VM Folder…', icon: 'Folder', onClick: () => onAction('__new_folder_vm__', dc) },
        { label: 'New Storage Folder…', icon: 'Folder', onClick: () => onAction('__new_folder_storage__', dc) },
        { label: 'New Network Folder…', icon: 'Folder', onClick: () => onAction('__new_folder_network__', dc) },
      ],
    },
    {
      label: 'Distributed Switch', icon: 'Network', children: [
        { label: 'New Distributed Switch…', icon: 'Network', onClick: () => onAction('__create_vswitch_dvs__', dc) },
      ],
    },
    { label: 'New Virtual Machine…', icon: 'Plus', onClick: () => onAction('__create_vm__', dc) },
    { label: 'Deploy OVF Template…', icon: 'Cloud', onClick: () => onAction('__deploy_ovf__', dc) },
    {
      label: 'Storage', icon: 'Database', children: [
        { label: 'New Datastore…', icon: 'Database', onClick: () => onAction('__create_datastore__', dc) },
        { label: 'New Datastore Cluster…', icon: 'Boxes', onClick: () => onAction('__create_datastore_cluster__', dc) },
        { label: 'Rescan Storage', icon: 'RefreshCw', onClick: () => onAction('rescan_storage', {}), disabled: acting },
      ],
    },
    { divider: true },
    { label: 'Edit Default VM Compatibility…', icon: 'Settings', onClick: () => onAction('__edit_default_compat__', dc) },
    { label: 'Migrate VMs to Another Network…', icon: 'ArrowRightLeft', onClick: () => onAction('__migrate_network__', dc) },
    { label: 'Move To…', icon: 'Move', onClick: () => onAction('__move_dc__', dc) },
    { label: 'Rename…', icon: 'Pencil', onClick: () => onAction('__rename_dc__', dc) },
    {
      label: 'Tags & Custom Attributes', icon: 'Tag', children: [
        { label: 'Assign Tag…', icon: 'Tag', onClick: () => onAction('__assign_tag__', dc) },
        { label: 'Remove Tag', icon: 'Tag', onClick: () => onAction('__remove_tag__', dc) },
      ],
    },
    { label: 'Add Permission…', icon: 'ShieldCheck', onClick: () => onAction('__add_permission__', dc) },
    {
      label: 'Alarms', icon: 'Bell', children: [
        { label: 'New Alarm Definition…', icon: 'Bell', onClick: () => onAction('__new_alarm_def__', dc) },
      ],
    },
    { divider: true },
    { label: 'Delete', icon: 'Trash2', onClick: () => onAction('__delete_dc__', dc), disabled: acting, color: '#D9534F' },
  ]
}
