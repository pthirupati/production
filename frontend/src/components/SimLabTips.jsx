/** Contextual quick tips for simulation labs — shown in LabRunner sidebar. */
export const SIM_LAB_TIPS = {
  default: [
    'Use systemctl status <service> to inspect services',
    'cat /etc/* config files to find misconfigurations',
    'journalctl -u <service> for service logs',
    'reboot triggers a live GRUB → boot → login sequence',
  ],
  patching: [
    'Jira: @backup team @database team @application team — stop & backup (~30s)',
    'Run /opt/fixitlab/precheck.sh only after team confirmations',
    'dnf update -y → reboot → mount -a if needed → postcheck',
    'Start services via Jira: @database team @application team',
  ],
  lvm: [
    'Jira: @storage team please add a 50G disk (~30s reply with device name)',
    'Verify: fdisk -l /dev/sdb or echo 1 > /sys/class/scsi_host/host0/scan',
    'pvcreate → vgextend → lvextend → xfs_growfs in terminal',
  ],
  network: [
    'Jira: @network team please add secondary IP on eth0',
    'Wait ~30s, then ip addr show dev eth0 to verify',
    'No Add NIC button — coordinate through the ticket like production',
  ],
  ssh: [
    'Use the SSH Client terminal tab to connect to remote hosts',
    'systemctl status sshd on the target server',
    'If SSH fails, open the server terminal and start sshd',
    'ssh root@10.0.0.11 from the SSH client pane',
  ],
  boot: [
    'GRUB: press Enter to boot, e to edit kernel/initrd lines',
    'Watch the auto-boot countdown or press Enter early',
    'dracut -f regenerates initramfs; grub2-mkconfig fixes GRUB',
    'Emergency mode: systemctl emergency (requires root password)',
  ],
  nginx: [
    'nginx -t tests configuration syntax',
    'systemctl status nginx && journalctl -u nginx',
    'Check /etc/nginx/sites-enabled/default for typos',
  ],
}

export function tipsForScenario(scenario) {
  if (!scenario) return SIM_LAB_TIPS.default
  const slug = (scenario.slug || '').toLowerCase()
  const tips = [...SIM_LAB_TIPS.default]
  if (slug.includes('patch')) tips.unshift(...SIM_LAB_TIPS.patching)
  if (slug.includes('lvm')) tips.unshift(...SIM_LAB_TIPS.lvm)
  if (slug.includes('firewalld') || slug.includes('network') || slug.includes('nic') || slug.includes('hosts')) {
    tips.unshift(...SIM_LAB_TIPS.network)
  }
  if (slug.includes('ansible') || slug.includes('ssh') || scenario.dual_terminal) {
    tips.unshift(...SIM_LAB_TIPS.ssh)
  }
  if (slug.includes('grub') || slug.includes('boot') || slug.includes('initramfs') || slug.includes('mbr')) {
    tips.unshift(...SIM_LAB_TIPS.boot)
  }
  if (slug.includes('nginx')) tips.unshift(...SIM_LAB_TIPS.nginx)
  return [...new Set(tips)].slice(0, 8)
}

export default function SimLabTips({ scenario }) {
  const tips = tipsForScenario(scenario)
  if (!tips.length) return null

  return (
    <div className="bg-indigo-500/5 border border-indigo-500/20 rounded-lg p-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-indigo-400 mb-2">
        Simulation tips
      </p>
      <ul className="space-y-1.5">
        {tips.map((tip, i) => (
          <li key={i} className="text-[11px] text-surface-400 leading-relaxed flex gap-1.5">
            <span className="text-indigo-500 shrink-0">›</span>
            <span>{tip}</span>
          </li>
        ))}
      </ul>
      {scenario?.dual_terminal && (
        <p className="text-[10px] text-surface-500 mt-2 pt-2 border-t border-indigo-500/15">
          Dual terminals enabled — use host tabs or SSH Client to reach companion servers.
        </p>
      )}
    </div>
  )
}
