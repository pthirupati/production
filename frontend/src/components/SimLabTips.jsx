/** Contextual quick tips for simulation labs — shown in LabRunner sidebar. */
export const SIM_LAB_TIPS = {
  default: [
    'Use systemctl status <service> to inspect services',
    'cat /etc/* config files to find misconfigurations',
    'journalctl -u <service> for service logs',
    'reboot triggers a live GRUB → boot → login sequence',
  ],
  patching: [
    'Run /opt/fixitlab/precheck.sh before patching',
    'dnf update -y then reboot to load the new kernel',
    'Login: root / redhat after reboot',
    'Run /opt/fixitlab/postcheck.sh to verify',
  ],
  lvm: [
    'pvdisplay / vgdisplay / lvdisplay to inspect LVM',
    'pvcreate /dev/sdb then vgextend and lvextend',
    'Suggested: pvcreate /dev/sdb; vgextend rhel /dev/sdb; lvextend -L +5G /dev/rhel/root',
  ],
  network: [
    'ip addr show — check interfaces and addresses',
    'ip addr add 10.0.0.20/24 dev eth0 to assign an IP',
    'systemctl restart NetworkManager after changes',
    'ss -tlnp to see listening ports',
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
  if (slug.includes('firewalld') || slug.includes('network') || slug.includes('hosts')) {
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
