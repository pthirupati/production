import { MessageSquare } from 'lucide-react'

const ALL_TEAMS = [
  {
    mention: '@backup',
    name: 'Backup Team',
    helps: 'Snapshot backups, restore points, and pre-change backup validation.',
    examples: ['@backup team please take backup before patching', '@backup confirm backup completed'],
  },
  {
    mention: '@database',
    name: 'Database Team',
    helps: 'Stop/start databases, replication quiesce, and DB maintenance windows.',
    examples: ['@database team stop database for maintenance', '@database start database after patch'],
  },
  {
    mention: '@application',
    name: 'Application Team',
    helps: 'Graceful app shutdown, traffic drain, and service restarts after changes.',
    examples: ['@application team stop app services', '@application restart application after reboot'],
  },
  {
    mention: '@storage',
    name: 'Storage Team',
    helps: 'Disk provisioning, LVM extension, mount fixes, and volume attach.',
    examples: ['@storage team attach new disk', '@storage extend LVM volume'],
  },
  {
    mention: '@network',
    name: 'Network Team',
    helps: 'NIC configuration, IP assignment, routing, and firewall rules.',
    examples: ['@network team configure eth1', '@network add IP to secondary NIC'],
  },
  {
    mention: '@security',
    name: 'Security Team',
    helps: 'Firewall approvals, access reviews, and change-window security sign-off.',
    examples: ['@security team approve firewall change', '@security review access for maintenance'],
  },
]

const SCENARIO_TEAMS = {
  'sim-rhel-patching': ['backup', 'database', 'application'],
  'sim-rhel-lvm-extend': ['storage'],
  'sim-rhel-network-nic': ['network'],
  'sim-rhel-ssh-stop': ['network', 'security'],
}

function teamsForScenario(slug) {
  const keys = SCENARIO_TEAMS[slug]
  if (!keys) return ALL_TEAMS
  return ALL_TEAMS.filter(t => keys.some(k => t.mention.includes(k)))
}

export default function JiraTeamGuide({ scenarioSlug, compact = false }) {
  const teams = teamsForScenario(scenarioSlug)

  if (compact) {
    return (
      <div className="flex flex-wrap gap-1.5">
        {teams.map(t => (
          <span key={t.mention} className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
            {t.mention}
          </span>
        ))}
      </div>
    )
  }

  return (
    <div className="glass-card p-5 border border-indigo-500/20 bg-indigo-500/5">
      <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-2">
        <MessageSquare size={16} className="text-indigo-400" />
        Jira @team bots — who to mention
      </h3>
      <p className="text-xs text-surface-400 mb-4">
        In the lab Jira panel, mention teams in comments. They reply in ~30 seconds and update the simulation (stop DB, attach disk, etc.).
      </p>
      <div className="space-y-3">
        {teams.map(team => (
          <div key={team.mention} className="rounded-lg border border-surface-800 bg-surface-900/50 p-3">
            <p className="text-sm font-medium text-indigo-300">{team.mention} — {team.name}</p>
            <p className="text-xs text-surface-400 mt-1">{team.helps}</p>
            <p className="text-[10px] text-surface-500 mt-2 font-mono">
              e.g. {team.examples[0]}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
