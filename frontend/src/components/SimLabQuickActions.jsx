import { HardDrive, Network, Terminal, RotateCcw, Play, Server } from 'lucide-react'

/**
 * One-click commands injected into the active simulation terminal.
 */
export default function SimLabQuickActions({
  scenario,
  labHosts = [],
  activeHost = 'primary',
  onSendCommand,
}) {
  if (!scenario || !onSendCommand) return null

  const slug = (scenario.slug || '').lower()
  const primary = labHosts.find(h => h.name === 'primary') || { ip: '10.0.0.10' }
  const suggestedIp = primary.ip?.replace(/\.\d+$/, '.20') || '10.0.0.20'

  const run = (cmd, host = activeHost) => {
    onSendCommand(cmd, host || activeHost)
  }

  const actions = []

  if (slug.includes('ssh-stop') || slug.includes('sshd-down') || scenario.dual_terminal) {
    actions.push(
      { label: 'SSH test', icon: Terminal, cmd: `ssh root@${primary.ip}`, host: 'ssh_client' },
      { label: 'sshd status', icon: Server, cmd: 'systemctl status sshd', host: 'primary' },
      { label: 'Start sshd', icon: Play, cmd: 'systemctl start sshd', host: 'primary' },
    )
  }

  if (slug.includes('lvm')) {
    actions.push(
      { label: 'pvdisplay', icon: HardDrive, cmd: 'pvs' },
      { label: 'Add disk', icon: HardDrive, cmd: 'pvcreate /dev/sdb && vgextend rhel /dev/sdb && lvextend -L +5G /dev/rhel/root' },
      { label: 'df -h', icon: HardDrive, cmd: 'df -h' },
    )
  }

  if (slug.includes('firewalld') || slug.includes('network') || slug.includes('hosts')) {
    actions.push(
      { label: 'ip addr', icon: Network, cmd: 'ip addr' },
      { label: 'Add NIC IP', icon: Network, cmd: `ip addr add ${suggestedIp}/24 dev eth0` },
      { label: 'Listening ports', icon: Network, cmd: 'ss -tlnp' },
    )
  }

  if (slug.includes('patch')) {
    actions.push(
      { label: 'Precheck', icon: Play, cmd: 'bash /opt/fixitlab/precheck.sh' },
      { label: 'dnf update', icon: Play, cmd: 'dnf update -y' },
      { label: 'Reboot', icon: RotateCcw, cmd: 'reboot' },
    )
  }

  if (slug.includes('grub') || slug.includes('boot') || slug.includes('initramfs')) {
    actions.push(
      { label: 'Reboot', icon: RotateCcw, cmd: 'reboot' },
      { label: 'dracut -f', icon: HardDrive, cmd: 'dracut -f' },
    )
  }

  if (!actions.length) {
    actions.push(
      { label: 'ip addr', icon: Network, cmd: 'ip addr' },
      { label: 'Services', icon: Server, cmd: 'systemctl list-units --type=service --state=running' },
      { label: 'df -h', icon: HardDrive, cmd: 'df -h' },
    )
  }

  const unique = actions.slice(0, 6)

  return (
    <div className="flex flex-wrap items-center gap-1">
      <span className="text-[10px] text-indigo-400/80 font-medium mr-0.5 hidden lg:inline">Quick:</span>
      {unique.map(({ label, icon: Icon, cmd, host }) => (
        <button
          key={label}
          type="button"
          title={cmd}
          onClick={() => run(cmd, host || activeHost)}
          className="inline-flex items-center gap-1 px-2 py-1 rounded border border-indigo-500/25 bg-indigo-500/10 text-indigo-300 hover:bg-indigo-500/20 text-[10px] font-medium transition-colors"
        >
          <Icon size={11} />
          {label}
        </button>
      ))}
    </div>
  )
}
