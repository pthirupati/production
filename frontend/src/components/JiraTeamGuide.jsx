import { Bot, ChevronRight } from 'lucide-react'

const TEAM_COLORS = {
  backup:      { badge: 'bg-amber-500/10 text-amber-300 border-amber-500/20',  dot: 'bg-amber-400' },
  database:    { badge: 'bg-blue-500/10 text-blue-300 border-blue-500/20',     dot: 'bg-blue-400' },
  application: { badge: 'bg-green-500/10 text-green-300 border-green-500/20', dot: 'bg-green-400' },
  storage:     { badge: 'bg-purple-500/10 text-purple-300 border-purple-500/20', dot: 'bg-purple-400' },
  network:     { badge: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/20',     dot: 'bg-cyan-400' },
  security:    { badge: 'bg-red-500/10 text-red-300 border-red-500/20',        dot: 'bg-red-400' },
}

const ALL_TEAMS = [
  {
    key: 'backup',
    mention: '@backup',
    name: 'Backup Team',
    helps: 'Snapshots, restore points, pre-change backup validation.',
    examples: ['@backup team please take backup before patching', '@backup confirm backup completed'],
  },
  {
    key: 'database',
    mention: '@database',
    name: 'Database Team',
    helps: 'Stop/start databases, replication quiesce, maintenance windows.',
    examples: ['@database team stop database for maintenance', '@database start database after patch'],
  },
  {
    key: 'application',
    mention: '@application',
    name: 'Application Team',
    helps: 'Graceful shutdown, traffic drain, service restarts.',
    examples: ['@application team stop app services', '@application restart application after reboot'],
  },
  {
    key: 'storage',
    mention: '@storage',
    name: 'Storage Team',
    helps: 'Disk provisioning, LVM extension, mount fixes, volume attach.',
    examples: ['@storage team attach new disk', '@storage extend LVM volume'],
  },
  {
    key: 'network',
    mention: '@network',
    name: 'Network Team',
    helps: 'NIC config, IP assignment, routing, firewall rules.',
    examples: ['@network team configure eth1', '@network add IP to secondary NIC'],
  },
  {
    key: 'security',
    mention: '@security',
    name: 'Security Team',
    helps: 'Firewall approvals, access reviews, change-window sign-off.',
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
  return ALL_TEAMS.filter(t => keys.includes(t.key))
}

export default function JiraTeamGuide({ scenarioSlug, compact = false }) {
  const teams = teamsForScenario(scenarioSlug)

  if (compact) {
    return (
      <div className="flex flex-wrap gap-1.5">
        {teams.map(t => {
          const c = TEAM_COLORS[t.key] || TEAM_COLORS.network
          return (
            <span key={t.mention} className={`text-[10px] px-2 py-0.5 rounded-full border font-mono ${c.badge}`}>
              {t.mention}
            </span>
          )
        })}
      </div>
    )
  }

  return (
    <div className="fx-panel overflow-hidden p-0">
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-white/[0.06] bg-surface-950/40">
        <div className="w-8 h-8 rounded-lg fixit-logo-mark flex items-center justify-center shrink-0">
          <Bot size={15} className="text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-white">Jira Team Bots</p>
          <p className="text-xs text-surface-400">@mention a team in the Jira comment box — they respond in ~30 seconds</p>
        </div>
      </div>

      {/* Team list */}
      <div className="p-3 grid sm:grid-cols-2 gap-2">
        {teams.map(team => {
          const c = TEAM_COLORS[team.key] || TEAM_COLORS.network
          return (
            <div key={team.mention} className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3 group hover:border-white/10 transition-colors">
              <div className="flex items-center gap-2 mb-1.5">
                <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${c.dot}`} />
                <span className={`text-xs font-mono font-semibold px-2 py-0.5 rounded-full border ${c.badge}`}>
                  {team.mention}
                </span>
                <span className="text-xs text-surface-500 font-medium">{team.name}</span>
              </div>
              <p className="text-[11px] text-surface-400 mb-2 pl-3.5">{team.helps}</p>
              <div className="pl-3.5 flex items-start gap-1.5">
                <ChevronRight size={11} className="text-surface-600 shrink-0 mt-0.5" />
                <p className="text-[10px] font-mono text-surface-500 italic leading-relaxed">{team.examples[0]}</p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
