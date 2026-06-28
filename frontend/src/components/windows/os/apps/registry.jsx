import {
  HardDrive, Server, Settings, Terminal as TermIcon, FileText, Cpu, Globe, Network,
  ListTree, ScrollText, Activity, Box, Users, Wrench, Calendar, Info, FolderTree, Boxes, MonitorCog,
  Shield, Gauge, Palette, Calculator as CalcIcon,
} from 'lucide-react'

import FileExplorer from './FileExplorer'
import Notepad from './Notepad'
import Terminal from './Terminal'
import TaskManager from './TaskManager'
import Services from './Services'
import DiskManagement from './DiskManagement'
import DeviceManager from './DeviceManager'
import EventViewer from './EventViewer'
import RegistryEditor from './RegistryEditor'
import ADUC from './ADUC'
import ServerManager from './ServerManager'
import ControlPanel from './ControlPanel'
import SystemInformation from './SystemInformation'
import { DNSManager, HyperV, ComputerManagement, NetworkConnections, TaskScheduler, SettingsApp } from './MoreApps'
import {
  GPMC, IISManager, DHCPManager, FirewallAdvanced, PerformanceMonitor,
  Calculator, WordPad, Paint,
} from './RemainingApps'
import Edge from './Edge'

// app key → { component, icon, default window props, title }
export const APPS = {
  FileExplorer: { c: FileExplorer, title: 'File Explorer', icon: (s = 16) => <HardDrive size={s} color="#f0b400" />, w: 940, h: 600 },
  Notepad: { c: Notepad, title: 'Untitled - Notepad', icon: (s = 16) => <FileText size={s} color="#5b9bd5" />, w: 720, h: 520 },
  Terminal: { c: Terminal, title: 'Windows PowerShell', icon: (s = 16) => <TermIcon size={s} color="#1f6feb" />, w: 820, h: 500 },
  TaskManager: { c: TaskManager, title: 'Task Manager', icon: (s = 16) => <Activity size={s} color="#3a8a3a" />, w: 760, h: 560 },
  Services: { c: Services, title: 'Services', icon: (s = 16) => <Wrench size={s} color="#5a6b7b" />, w: 900, h: 560 },
  DiskManagement: { c: DiskManagement, title: 'Disk Management', icon: (s = 16) => <HardDrive size={s} color="#5a8" />, w: 880, h: 580 },
  DeviceManager: { c: DeviceManager, title: 'Device Manager', icon: (s = 16) => <Cpu size={s} color="#7a5" />, w: 720, h: 560 },
  EventViewer: { c: EventViewer, title: 'Event Viewer', icon: (s = 16) => <ScrollText size={s} color="#2b88d8" />, w: 980, h: 620 },
  RegistryEditor: { c: RegistryEditor, title: 'Registry Editor', icon: (s = 16) => <ListTree size={s} color="#6a6a6a" />, w: 900, h: 560 },
  ADUC: { c: ADUC, title: 'Active Directory Users and Computers', icon: (s = 16) => <Users size={s} color="#2b88d8" />, w: 980, h: 620 },
  ServerManager: { c: ServerManager, title: 'Server Manager', icon: (s = 16) => <Server size={s} color="#2b88d8" />, w: 1000, h: 640 },
  ControlPanel: { c: ControlPanel, title: 'Control Panel', icon: (s = 16) => <MonitorCog size={s} color="#5a6b7b" />, w: 860, h: 560 },
  SystemInformation: { c: SystemInformation, title: 'System Information', icon: (s = 16) => <Info size={s} color="#2b88d8" />, w: 820, h: 540 },
  DNSManager: { c: DNSManager, title: 'DNS Manager', icon: (s = 16) => <Globe size={s} color="#2b88d8" />, w: 880, h: 540 },
  HyperV: { c: HyperV, title: 'Hyper-V Manager', icon: (s = 16) => <Box size={s} color="#5a6b7b" />, w: 920, h: 560 },
  ComputerManagement: { c: ComputerManagement, title: 'Computer Management', icon: (s = 16) => <Boxes size={s} color="#5a6b7b" />, w: 940, h: 580 },
  NetworkConnections: { c: NetworkConnections, title: 'Network Connections', icon: (s = 16) => <Network size={s} color="#2b88d8" />, w: 700, h: 460 },
  TaskScheduler: { c: TaskScheduler, title: 'Task Scheduler', icon: (s = 16) => <Calendar size={s} color="#5a6b7b" />, w: 940, h: 560 },
  Settings: { c: SettingsApp, title: 'Settings', icon: (s = 16) => <Settings size={s} color="#5a6b7b" />, w: 820, h: 560 },
  GPMC: { c: GPMC, title: 'Group Policy Management', icon: (s = 16) => <ListTree size={s} color="#6a6a6a" />, w: 980, h: 620 },
  IISManager: { c: IISManager, title: 'Internet Information Services (IIS) Manager', icon: (s = 16) => <Globe size={s} color="#2b88d8" />, w: 980, h: 620 },
  DHCPManager: { c: DHCPManager, title: 'DHCP', icon: (s = 16) => <Network size={s} color="#2b88d8" />, w: 900, h: 560 },
  FirewallAdvanced: { c: FirewallAdvanced, title: 'Windows Defender Firewall with Advanced Security', icon: (s = 16) => <Shield size={s} color="#107c10" />, w: 980, h: 620 },
  PerformanceMonitor: { c: PerformanceMonitor, title: 'Performance Monitor', icon: (s = 16) => <Gauge size={s} color="#107c10" />, w: 900, h: 560 },
  Calculator: { c: Calculator, title: 'Calculator', icon: (s = 16) => <CalcIcon size={s} color="#5a6b7b" />, w: 330, h: 450 },
  WordPad: { c: WordPad, title: 'Document - WordPad', icon: (s = 16) => <FileText size={s} color="#5b9bd5" />, w: 760, h: 540 },
  Paint: { c: Paint, title: 'Untitled - Paint', icon: (s = 16) => <Palette size={s} color="#c0392b" />, w: 820, h: 560 },
  Edge: { c: Edge, title: 'Microsoft Edge', icon: (s = 16) => <Globe size={s} color="#0078d4" />, w: 960, h: 620 },
}

export function AppIcon({ app, size = 16 }) {
  const a = APPS[app]
  return a ? a.icon(size) : <FolderTree size={size} />
}
