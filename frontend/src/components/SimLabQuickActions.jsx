import { HardDrive, Network, Terminal, Server } from 'lucide-react'

/**
 * Inspection-only quick actions — resource changes go through Jira @team mentions.
 */
export default function SimLabQuickActions({
  scenario,
  labHosts = [],
  activeHost = 'primary',
  onSendCommand,
}) {
  if (!scenario || !onSendCommand) return null

  const slug = (scenario.slug || '').toLowerCase()
  const primary = labHosts.find(h => h.name === 'primary') || { ip: '10.0.0.10' }

  const run = (cmd, host = activeHost) => {
    onSendCommand(cmd, host || activeHost)
  }

  const actions = []

  if (slug.includes('ssh-stop') || slug.includes('sshd-down') || scenario.dual_terminal) {
    actions.push(
      { label: 'SSH test', icon: Terminal, cmd: `ssh root@${primary.ip}`, host: 'ssh_client' },
      { label: 'sshd status', icon: Server, cmd: 'systemctl status sshd', host: 'primary' },
    )
  }

  if (slug.includes('lvm')) {
    actions.push(
      { label: 'pvs', icon: HardDrive, cmd: 'pvs' },
      { label: 'fdisk -l', icon: HardDrive, cmd: 'fdisk -l' },
      { label: 'df -h', icon: HardDrive, cmd: 'df -h' },
    )
  }

  if (slug.includes('firewalld') || slug.includes('firewall') || slug.includes('mysql')) {
    if (slug.includes('mysql')) {
      actions.push(
        { label: 'MySQL ping', icon: Server, cmd: `mysqladmin ping -h ${primary.ip}`, host: 'ssh_client' },
      )
    }
    if (slug.includes('firewall') || slug.includes('firewalld')) {
      actions.push(
        { label: 'curl test', icon: Network, cmd: `curl -s -o /dev/null -w '%{{http_code}}' http://${primary.ip}/`, host: 'ssh_client' },
      )
    }
  }

  if (slug.includes('network') || slug.includes('nic')) {
    actions.push(
      { label: 'ip addr', icon: Network, cmd: 'ip addr' },
      { label: 'Listening ports', icon: Network, cmd: 'ss -tlnp' },
    )
  }

  if (slug.includes('patch')) {
    actions.push(
      { label: 'Precheck', icon: Terminal, cmd: 'bash /opt/fixitlab/precheck.sh' },
      { label: 'df -h', icon: HardDrive, cmd: 'df -h' },
    )
  }

  if (slug.includes('grub') || slug.includes('boot') || slug.includes('initramfs')) {
    actions.push(
      { label: 'Reboot', icon: Terminal, cmd: 'reboot' },
    )
  }

  if (!actions.length) return null

  const unique = actions.slice(0, 5)

  return (
    <div className="flex flex-wrap items-center gap-1">
      <span className="text-[10px] text-indigo-400/80 font-medium mr-0.5 hidden lg:inline">Inspect:</span>
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
