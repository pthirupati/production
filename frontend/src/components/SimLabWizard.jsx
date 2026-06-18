import { useState } from 'react'
import { HardDrive, Network, Wand2, Play, X, ChevronRight } from 'lucide-react'
import ConfirmModal from './ConfirmModal'

const DISK_STEPS = [
  { title: 'Inspect block devices', detail: 'Confirm /dev/sdb is visible and unused.', cmd: 'fdisk -l /dev/sdb', host: 'primary' },
  { title: 'Create physical volume', detail: 'Initialize the new disk for LVM.', cmd: 'pvcreate /dev/sdb', host: 'primary' },
  { title: 'Extend volume group', detail: 'Add /dev/sdb to the rhel volume group.', cmd: 'vgextend rhel /dev/sdb', host: 'primary' },
  { title: 'Extend logical volume', detail: 'Grow root LV by 5G (adjust size as needed).', cmd: 'lvextend -L +5G /dev/rhel/root', host: 'primary' },
  { title: 'Verify filesystem', detail: 'Confirm root filesystem reflects the new size.', cmd: 'df -h /', host: 'primary' },
]

function nicSteps(suggestedIp) {
  return [
    { title: 'Show interfaces', detail: 'Review eth0 and current addresses.', cmd: 'ip addr show dev eth0', host: 'primary' },
    { title: 'Assign IP address', detail: `Suggested address for this lab subnet: ${suggestedIp}/24`, cmd: `ip addr add ${suggestedIp}/24 dev eth0`, host: 'primary' },
    { title: 'Bring interface up', detail: 'Ensure eth0 is administratively up.', cmd: 'ip link set dev eth0 up', host: 'primary' },
    { title: 'Verify routing', detail: 'Check default route and connectivity.', cmd: 'ip route show', host: 'primary' },
  ]
}

function scenarioWizards(scenario, labHosts, suggestedIp) {
  const slug = (scenario?.slug || '').toLowerCase()
  const primary = labHosts.find(h => h.name === 'primary') || { ip: '10.0.0.10' }
  const wizards = []

  // Disk/NIC provisioning is via Jira @storage / @network team — no wizard buttons.

  if (slug.includes('ssh-stop') || slug.includes('sshd-down') || scenario?.dual_terminal) {
    wizards.push({
      id: 'ssh-recover',
      label: 'SSH recovery',
      icon: Network,
      description: 'Diagnose SSH from the client, fix sshd on the server console.',
      steps: [
        { title: 'Test SSH (client)', detail: `Try SSH from client to ${primary.ip}.`, cmd: `ssh -o ConnectTimeout=5 root@${primary.ip}`, host: 'ssh_client' },
        { title: 'Check sshd (server)', detail: 'On server console, inspect sshd.', cmd: 'systemctl status sshd', host: 'primary' },
        { title: 'Start sshd', detail: 'Start the SSH service on the server.', cmd: 'systemctl start sshd', host: 'primary' },
        { title: 'Retry SSH', detail: 'Confirm remote login works.', cmd: `ssh -o ConnectTimeout=5 root@${primary.ip}`, host: 'ssh_client' },
      ],
    })
  }

  if (slug.includes('firewalld') || slug.includes('firewall')) {
    wizards.push({
      id: 'firewall',
      label: 'Open firewall port',
      icon: Network,
      description: 'Allow HTTP through firewalld, then test from the client.',
      steps: [
        { title: 'Test HTTP (client)', detail: 'curl should fail until port 80 is open.', cmd: `curl -s -o /dev/null -w '%{{http_code}}' http://${primary.ip}/`, host: 'ssh_client' },
        { title: 'List firewall', detail: 'Review public zone on server.', cmd: 'firewall-cmd --list-all', host: 'primary' },
        { title: 'Allow HTTP', detail: 'Permanently allow http service.', cmd: 'firewall-cmd --permanent --add-service=http && firewall-cmd --reload', host: 'primary' },
        { title: 'Retry HTTP', detail: 'Should return 200 after fix.', cmd: `curl -s -o /dev/null -w '%{{http_code}}' http://${primary.ip}/`, host: 'ssh_client' },
      ],
    })
  }

  if (slug.includes('mysql')) {
    wizards.push({
      id: 'mysql',
      label: 'MySQL recovery',
      icon: HardDrive,
      description: 'Start mysqld on the server and verify from the client.',
      steps: [
        { title: 'Ping MySQL (client)', detail: 'Remote ping should fail while mysqld is down.', cmd: `mysqladmin ping -h ${primary.ip}`, host: 'ssh_client' },
        { title: 'Check mysqld', detail: 'Inspect service on server console.', cmd: 'systemctl status mysqld', host: 'primary' },
        { title: 'Start mysqld', detail: 'Start MySQL on the server.', cmd: 'systemctl start mysqld', host: 'primary' },
        { title: 'Retry ping', detail: 'Remote mysqladmin ping should succeed.', cmd: `mysqladmin ping -h ${primary.ip}`, host: 'ssh_client' },
      ],
    })
  }

  return wizards
}

export default function SimLabWizard({ open, onClose, scenario, labHosts = [], onSendCommand }) {
  const primary = labHosts.find(h => h.name === 'primary') || { ip: '10.0.0.10' }
  const suggestedIp = primary.ip?.replace(/\.\d+$/, '.20') || '10.0.0.20'
  const wizards = scenarioWizards(scenario, labHosts, suggestedIp)
  const [activeWizard, setActiveWizard] = useState(wizards[0]?.id || '')
  const [stepIdx, setStepIdx] = useState(0)

  const wizard = wizards.find(w => w.id === activeWizard) || wizards[0]
  const step = wizard?.steps[stepIdx]

  if (!open) return null

  if (!wizards.length) {
    return (
      <ConfirmModal open={open} onClose={onClose} title="Lab Wizards" maxWidth="max-w-lg">
        <p className="text-sm text-surface-400">
          For disk, NIC, and change-window actions, use the <strong className="text-surface-200">Jira ticket</strong> and
          mention @storage team, @network team, @backup team, @database team, or @application team.
          Replies arrive in ~30 seconds.
        </p>
        <div className="flex justify-end pt-4">
          <button type="button" onClick={onClose} className="btn-secondary text-sm px-4 py-2">Close</button>
        </div>
      </ConfirmModal>
    )
  }

  const runStep = () => {
    if (!step || !onSendCommand) return
    onSendCommand(step.cmd, step.host || 'primary')
  }

  const runAll = async () => {
    if (!wizard || !onSendCommand) return
    for (const s of wizard.steps) {
      onSendCommand(s.cmd, s.host || 'primary')
      await new Promise(r => setTimeout(r, 600))
    }
  }

  if (!open) return null

  return (
    <ConfirmModal open={open} onClose={onClose} title="Lab Wizards" maxWidth="max-w-lg">
      <div className="space-y-4">
        <p className="text-xs text-surface-400">
          Step-by-step guides inject commands into the correct terminal. Password hint: <span className="text-surface-200">redhat</span>
        </p>

        <div className="flex flex-wrap gap-1.5">
          {wizards.map(w => {
            const Icon = w.icon
            return (
              <button
                key={w.id}
                type="button"
                onClick={() => { setActiveWizard(w.id); setStepIdx(0) }}
                className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs border transition-colors ${
                  activeWizard === w.id
                    ? 'border-indigo-500/50 bg-indigo-500/15 text-indigo-300'
                    : 'border-surface-700 text-surface-400 hover:border-surface-600'
                }`}
              >
                <Icon size={12} /> {w.label}
              </button>
            )
          })}
        </div>

        {wizard && (
          <>
            <p className="text-sm text-surface-300">{wizard.description}</p>
            <div className="flex gap-1 overflow-x-auto pb-1">
              {wizard.steps.map((s, i) => (
                <button
                  key={s.title}
                  type="button"
                  onClick={() => setStepIdx(i)}
                  className={`shrink-0 px-2 py-1 rounded text-[10px] border ${
                    i === stepIdx ? 'border-accent-cyan text-accent-cyan bg-accent-cyan/10' : 'border-surface-800 text-surface-500'
                  }`}
                >
                  {i + 1}. {s.title}
                </button>
              ))}
            </div>

            {step && (
              <div className="bg-surface-950 rounded-lg border border-surface-800 p-4 space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-medium text-white">{step.title}</p>
                    <p className="text-xs text-surface-400 mt-1">{step.detail}</p>
                    <p className="text-[10px] text-surface-500 mt-1">
                      Terminal: <span className="text-surface-300">{step.host || 'primary'}</span>
                    </p>
                  </div>
                  <span className="text-[10px] text-surface-600 shrink-0">
                    {stepIdx + 1}/{wizard.steps.length}
                  </span>
                </div>
                <pre className="text-xs font-mono text-accent-cyan bg-surface-900 rounded p-2 overflow-x-auto whitespace-pre-wrap">
                  {step.cmd}
                </pre>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={runStep}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-500/30"
                  >
                    <Play size={12} /> Run step
                  </button>
                  {stepIdx < wizard.steps.length - 1 && (
                    <button
                      type="button"
                      onClick={() => setStepIdx(i => i + 1)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs text-surface-400 border border-surface-700 hover:text-white"
                    >
                      Next <ChevronRight size={12} />
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={runAll}
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs text-surface-400 border border-surface-700 hover:text-white ml-auto"
                  >
                    <Wand2 size={12} /> Run all steps
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        <div className="flex justify-end pt-2">
          <button type="button" onClick={onClose} className="btn-secondary text-sm px-4 py-2 inline-flex items-center gap-1">
            <X size={14} /> Close
          </button>
        </div>
      </div>
    </ConfirmModal>
  )
}
