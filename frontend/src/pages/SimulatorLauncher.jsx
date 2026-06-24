import { Link } from 'react-router-dom'
import {
  Cloud, Server, Activity, Gauge, Monitor, Users, Radar, Waves, Bot, BarChart3, Cpu,
} from 'lucide-react'
import { PageHeader } from '../components/design'

const SIMULATORS = [
  { id: 'terraform', name: 'Terraform Cloud', desc: 'Workspaces, runs, registry, variables, and VS Code–style IDE', icon: Cloud, color: '#5c4ee5', path: '/technologies/terraform' },
  { id: 'awx', name: 'Ansible AWX / Tower', desc: 'Job templates, inventories, credentials, workflow visualizer', icon: Server, color: '#EE0000', path: '/technologies/ansible-awx' },
  { id: 'grafana', name: 'Grafana', desc: 'Dashboards, Explore, alerting, data sources, administration', icon: Gauge, color: '#f7913b', path: '/technologies/grafana' },
  { id: 'prometheus', name: 'Prometheus', desc: 'PromQL graph, alerts, targets, rules, service discovery', icon: Activity, color: '#e6522c', path: '/technologies/prometheus' },
  { id: 'windows', name: 'Windows Server', desc: 'Server Manager, AD Users & Computers, GPO Editor', icon: Monitor, color: '#0078D4', path: '/technologies/windows' },
  { id: 'peoplesoft', name: 'PeopleSoft HCM', desc: 'Fluid UI, job data, payroll, benefits enrollment', icon: Users, color: '#c74634', path: '/technologies/peoplesoft' },
  { id: 'nmap', name: 'Nmap', desc: 'Scan builder, host discovery, port scanning', icon: Radar, color: '#4ade80', path: '/technologies/nmap' },
  { id: 'wireshark', name: 'Wireshark', desc: 'Capture filters, packet analysis, TCP streams', icon: Waves, color: '#4c8dff', path: '/technologies/wireshark' },
  { id: 'aiml', name: 'AI Agent Builder', desc: 'n8n-style workflow canvas and execution trace', icon: Bot, color: '#a78bfa', path: '/technologies/ai-ml' },
  { id: 'datascience', name: 'Data Dashboard', desc: 'BI builder with charts and aggregations', icon: BarChart3, color: '#34d399', path: '/technologies/data-science' },
  { id: 'baremetal', name: 'Bare Metal', desc: 'MAAS, LXD, KVM, IPMI consoles', icon: Cpu, color: '#0d9488', path: '/technologies/baremetal' },
]

export default function SimulatorLauncher() {
  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <PageHeader
        title="Enterprise Lab Simulators"
        subtitle="Pixel-faithful, fully interactive mocks of production UIs — launch a scenario from each technology to practice hands-on."
      />
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-8">
        {SIMULATORS.map((sim) => {
          const Icon = sim.icon
          return (
            <Link key={sim.id} to={sim.path}
              className="glass-card p-5 border border-surface-800 hover:border-accent-cyan/40 transition-all group">
              <div className="flex items-start gap-3">
                <div className="p-2.5 rounded-lg shrink-0" style={{ background: `${sim.color}22`, color: sim.color }}>
                  <Icon size={22} />
                </div>
                <div className="min-w-0">
                  <h3 className="font-semibold text-white group-hover:text-accent-cyan transition-colors">{sim.name}</h3>
                  <p className="text-xs text-surface-400 mt-1 leading-relaxed">{sim.desc}</p>
                </div>
              </div>
            </Link>
          )
        })}
      </div>
      <p className="text-xs text-surface-500 mt-8 text-center">
        Simulators open inside lab sessions with Hints, Check, +30m, and Stop controls. VMware vCenter is available from cross-tech scenarios only.
      </p>
    </div>
  )
}
