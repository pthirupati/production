// ─────────────────────────────────────────────────────────────────────────
// Seed data for the Windows Server 2022 simulation.
// All data here is realistic and feeds the Zustand OS store. Nothing is a
// placeholder — every list is rendered by a real app panel.
// ─────────────────────────────────────────────────────────────────────────

export const COMPUTER = {
  name: 'SERVER01',
  fqdn: 'SERVER01.lab.local',
  domain: 'lab.local',
  workgroup: 'WORKGROUP',
  edition: 'Windows Server 2022 Standard Evaluation',
  build: '20348.2402',
  productId: '00454-20000-00001-AA278',
  cpu: 'Intel(R) Core(TM) i7-9700 CPU @ 3.00GHz',
  cores: 8,
  ramGB: 16,
  installDate: '2023-08-15',
}

// ── Services (curated, realistic Windows Server set) ───────────────────────
const S = (name, display, status, startup, logon, desc = '') =>
  ({ name, display, status, startup, logon, desc })

export const SEED_SERVICES = [
  S('AppHostSvc', 'Application Host Helper Service', 'Running', 'Automatic', 'Local Service', 'Provides administrative services for IIS.'),
  S('AppIDSvc', 'Application Identity', 'Stopped', 'Manual', 'Local Service', 'Determines and verifies the identity of an application.'),
  S('Appinfo', 'Application Information', 'Running', 'Manual', 'Local System', 'Facilitates the running of interactive applications with additional privileges (UAC).'),
  S('BITS', 'Background Intelligent Transfer Service', 'Running', 'Automatic (Delayed)', 'Local System', 'Transfers files in the background using idle network bandwidth.'),
  S('BFE', 'Base Filtering Engine', 'Running', 'Automatic', 'Local Service', 'Manages firewall and Internet Protocol security (IPsec) policies.'),
  S('CertPropSvc', 'Certificate Propagation', 'Running', 'Manual', 'Local System', 'Copies user certificates and root certificates from smart cards.'),
  S('KeyIso', 'CNG Key Isolation', 'Running', 'Manual', 'Local System', 'Provides key process isolation to private keys.'),
  S('EventSystem', 'COM+ Event System', 'Running', 'Automatic', 'Local Service', 'Supports System Event Notification Service.'),
  S('COMSysApp', 'COM+ System Application', 'Stopped', 'Manual', 'Local System', 'Manages the configuration and tracking of COM+ components.'),
  S('Browser', 'Computer Browser', 'Stopped', 'Disabled', 'Local System', 'Maintains an updated list of computers on the network.'),
  S('VaultSvc', 'Credential Manager', 'Running', 'Manual', 'Local System', 'Provides secure storage and retrieval of credentials.'),
  S('CryptSvc', 'Cryptographic Services', 'Running', 'Automatic', 'Network Service', 'Provides key-management services for the computer.'),
  S('DcomLaunch', 'DCOM Server Process Launcher', 'Running', 'Automatic', 'Local System', 'Launches COM and DCOM servers in response to object activation requests.'),
  S('Dhcp', 'DHCP Client', 'Running', 'Automatic', 'Local Service', 'Registers and updates IP addresses and DNS records.'),
  S('DPS', 'Diagnostic Policy Service', 'Running', 'Automatic', 'Local Service', 'Enables problem detection, troubleshooting and resolution.'),
  S('TrkWks', 'Distributed Link Tracking Client', 'Running', 'Automatic', 'Local System', 'Maintains links between NTFS files within and across computers.'),
  S('MSDTC', 'Distributed Transaction Coordinator', 'Running', 'Automatic', 'Network Service', 'Coordinates transactions that span multiple resource managers.'),
  S('Dnscache', 'DNS Client', 'Running', 'Automatic', 'Network Service', 'Caches Domain Name System (DNS) names.'),
  S('EFS', 'Encrypting File System (EFS)', 'Stopped', 'Manual', 'Local System', 'Provides the core file encryption technology used by NTFS.'),
  S('Eaphost', 'Extensible Authentication Protocol', 'Stopped', 'Manual', 'Local System', 'Provides network authentication in scenarios such as 802.1x.'),
  S('fdPHost', 'Function Discovery Provider Host', 'Running', 'Manual', 'Local Service', 'Hosts Function Discovery network providers.'),
  S('FDResPub', 'Function Discovery Resource Publication', 'Running', 'Manual', 'Local Service', 'Publishes this computer and resources to the network.'),
  S('gpsvc', 'Group Policy Client', 'Running', 'Automatic', 'Local System', 'Applies settings configured by administrators via Group Policy.'),
  S('IISADMIN', 'IIS Admin Service', 'Running', 'Automatic', 'Local System', 'Enables the server to administer the IIS metabase.'),
  S('iphlpsvc', 'IP Helper', 'Running', 'Automatic', 'Local System', 'Provides tunnel connectivity using IPv6 transition technologies.'),
  S('PolicyAgent', 'IPsec Policy Agent', 'Running', 'Manual', 'Network Service', 'Enforces IPsec policy.'),
  S('Netlogon', 'Netlogon', 'Running', 'Automatic', 'Local System', 'Maintains a secure channel between this computer and the domain controller.'),
  S('Netman', 'Network Connections', 'Running', 'Manual', 'Local System', 'Manages objects in the Network and Dial-Up Connections folder.'),
  S('netprofm', 'Network List Service', 'Running', 'Manual', 'Local Service', 'Identifies the networks to which the computer has connected.'),
  S('NlaSvc', 'Network Location Awareness', 'Running', 'Automatic', 'Network Service', 'Collects and stores configuration information for the network.'),
  S('nsi', 'Network Store Interface Service', 'Running', 'Automatic', 'Local Service', 'Delivers network notifications to user mode clients.'),
  S('PlugPlay', 'Plug and Play', 'Running', 'Manual', 'Local System', 'Enables a computer to recognize and adapt to hardware changes.'),
  S('Power', 'Power', 'Running', 'Automatic', 'Local System', 'Manages power policy and power policy notification delivery.'),
  S('Spooler', 'Print Spooler', 'Running', 'Automatic', 'Local System', 'This service spools print jobs and handles interaction with the printer.'),
  S('RpcSs', 'Remote Procedure Call (RPC)', 'Running', 'Automatic', 'Network Service', 'Serves as the endpoint mapper and COM Service Control Manager.'),
  S('RpcLocator', 'Remote Procedure Call (RPC) Locator', 'Stopped', 'Manual', 'Network Service', 'Manages the RPC name service database.'),
  S('RemoteRegistry', 'Remote Registry', 'Stopped', 'Disabled', 'Local Service', 'Enables remote users to modify registry settings on this computer.'),
  S('SamSs', 'Security Accounts Manager', 'Running', 'Automatic', 'Local System', 'Startup of this service signals other services that the SAM is ready.'),
  S('wscsvc', 'Security Center', 'Running', 'Automatic (Delayed)', 'Local Service', 'Monitors and reports security health settings on the computer.'),
  S('LanmanServer', 'Server', 'Running', 'Automatic', 'Local System', 'Supports file, print, and named-pipe sharing over the network.'),
  S('ShellHWDetection', 'Shell Hardware Detection', 'Running', 'Automatic', 'Local System', 'Provides notifications for AutoPlay hardware events.'),
  S('SCardSvr', 'Smart Card', 'Stopped', 'Disabled', 'Local Service', 'Manages access to smart cards read by this computer.'),
  S('SNMP', 'SNMP Service', 'Running', 'Automatic', 'Local Service', 'Enables Simple Network Management Protocol (SNMP) requests.'),
  S('sppsvc', 'Software Protection', 'Running', 'Automatic (Delayed)', 'Network Service', 'Enables download, install and enforcement of digital licenses.'),
  S('StorSvc', 'Storage Service', 'Running', 'Manual', 'Local System', 'Provides enabling services for storage settings and external storage.'),
  S('SysMain', 'SysMain', 'Running', 'Automatic', 'Local System', 'Maintains and improves system performance over time.'),
  S('SENS', 'System Event Notification Service', 'Running', 'Automatic', 'Local System', 'Monitors system events and notifies subscribers to COM+ Event System.'),
  S('Schedule', 'Task Scheduler', 'Running', 'Automatic', 'Local System', 'Enables a user to configure and schedule automated tasks.'),
  S('lmhosts', 'TCP/IP NetBIOS Helper', 'Running', 'Automatic', 'Local Service', 'Provides support for NetBIOS over TCP/IP service.'),
  S('Themes', 'Themes', 'Running', 'Automatic', 'Local System', 'Provides user experience theme management.'),
  S('UsoSvc', 'Update Orchestrator Service', 'Running', 'Automatic (Delayed)', 'Local System', 'Manages Windows Updates. If stopped, devices will not download/install updates.'),
  S('UALSVC', 'User Access Logging Service', 'Running', 'Automatic (Delayed)', 'Local System', 'Logs unique client requests of roles and services.'),
  S('UserManager', 'User Manager', 'Running', 'Automatic', 'Local System', 'User Manager provides the runtime components required for multi-user interaction.'),
  S('ProfSvc', 'User Profile Service', 'Running', 'Automatic', 'Local System', 'Responsible for loading and unloading user profiles.'),
  S('vds', 'Virtual Disk', 'Stopped', 'Manual', 'Local System', 'Provides management services for disks, volumes, file systems and storage arrays.'),
  S('VGAuthService', 'VMware Alias Manager and Ticket Service', 'Running', 'Automatic', 'Local System', 'Alias Manager and Ticket Service for VMware Tools.'),
  S('VMTools', 'VMware Tools', 'Running', 'Automatic', 'Local System', 'Provides support for synchronizing objects between host and guest OS.'),
  S('VSS', 'Volume Shadow Copy', 'Stopped', 'Manual', 'Local System', 'Manages and implements Volume Shadow Copies used for backup.'),
  S('WMSvc', 'Web Management Service', 'Stopped', 'Disabled', 'Local Service', 'Enables remote and delegated management of IIS.'),
  S('Audiosrv', 'Windows Audio', 'Running', 'Automatic', 'Local Service', 'Manages audio for Windows-based programs.'),
  S('AudioEndpointBuilder', 'Windows Audio Endpoint Builder', 'Running', 'Automatic', 'Local System', 'Manages audio devices for the Windows Audio service.'),
  S('Wcmsvc', 'Windows Connection Manager', 'Running', 'Automatic', 'Local Service', 'Makes automatic connect/disconnect decisions based on connectivity.'),
  S('WdNisSvc', 'Microsoft Defender Antivirus Network Inspection', 'Running', 'Manual', 'Local Service', 'Helps guard against intrusion attempts targeting known vulnerabilities.'),
  S('WinDefend', 'Microsoft Defender Antivirus Service', 'Running', 'Automatic', 'Local System', 'Helps protect users from malware and other potentially unwanted software.'),
  S('MpsSvc', 'Windows Defender Firewall', 'Running', 'Automatic', 'Local Service', 'Helps protect by preventing unauthorized access through the firewall.'),
  S('WerSvc', 'Windows Error Reporting Service', 'Running', 'Manual', 'Local System', 'Allows errors to be reported when programs stop working.'),
  S('EventLog', 'Windows Event Log', 'Running', 'Automatic', 'Local Service', 'Manages events and event logs.'),
  S('FontCache', 'Windows Font Cache Service', 'Running', 'Automatic', 'Local Service', 'Optimizes performance by caching commonly used font data.'),
  S('msiserver', 'Windows Installer', 'Stopped', 'Manual', 'Local System', 'Adds, modifies, and removes applications provided as a Windows Installer package.'),
  S('LicenseManager', 'Windows License Manager Service', 'Running', 'Manual', 'Local Service', 'Provides infrastructure support for the Microsoft Store.'),
  S('Winmgmt', 'Windows Management Instrumentation', 'Running', 'Automatic', 'Local System', 'Provides a common interface and object model to access management info.'),
  S('TrustedInstaller', 'Windows Modules Installer', 'Stopped', 'Manual', 'Local System', 'Enables installation, modification and removal of Windows updates and components.'),
  S('WpnService', 'Windows Push Notifications System Service', 'Running', 'Automatic', 'Local System', 'Runs in session 0 and hosts the notification platform.'),
  S('WinRM', 'Windows Remote Management (WS-Management)', 'Running', 'Automatic', 'Network Service', 'Implements the WS-Management protocol for remote management.'),
  S('WSearch', 'Windows Search', 'Running', 'Automatic (Delayed)', 'Local System', 'Provides content indexing, property caching, and search results for files.'),
  S('W32Time', 'Windows Time', 'Running', 'Manual', 'Local Service', 'Maintains date and time synchronization on all clients and servers.'),
  S('wuauserv', 'Windows Update', 'Running', 'Manual', 'Local System', 'Enables the detection, download, and installation of updates.'),
  S('WinHttpAutoProxySvc', 'WinHTTP Web Proxy Auto-Discovery Service', 'Running', 'Manual', 'Local Service', 'Implements the Web Proxy Auto-Discovery (WPAD) protocol.'),
  S('LanmanWorkstation', 'Workstation', 'Running', 'Automatic', 'Network Service', 'Creates and maintains client network connections to remote servers using SMB.'),
  S('W3SVC', 'World Wide Web Publishing Service', 'Running', 'Automatic', 'Local System', 'Provides Web connectivity and administration through the IIS Manager.'),
  S('DNS', 'DNS Server', 'Running', 'Automatic', 'Local System', 'Enables DNS name resolution by answering queries and update requests.'),
  S('DHCPServer', 'DHCP Server', 'Running', 'Automatic', 'Network Service', 'Performs TCP/IP configuration for DHCP clients, including IP leases.'),
  S('NTDS', 'Active Directory Domain Services', 'Running', 'Automatic', 'Local System', 'AD DS Domain Controller service. Stores directory data and manages logon.'),
  S('kdc', 'Kerberos Key Distribution Center', 'Running', 'Automatic', 'Local System', 'Enables users to log on using the Kerberos v5 authentication protocol.'),
  S('DFSR', 'DFS Replication', 'Running', 'Automatic', 'Local System', 'Replicates files among multiple servers to keep them synchronized.'),
  S('vmms', 'Hyper-V Virtual Machine Management', 'Running', 'Automatic', 'Local System', 'Management service for Hyper-V, provides VM management.'),
]

// ── Startup programs ───────────────────────────────────────────────────────
export const SEED_STARTUP = [
  { name: 'VMware Tools', publisher: 'VMware, Inc.', enabled: true, impact: 'Low' },
  { name: 'Windows Security notification icon', publisher: 'Microsoft Corporation', enabled: true, impact: 'Low' },
  { name: 'Microsoft OneDrive', publisher: 'Microsoft Corporation', enabled: false, impact: 'Medium' },
  { name: 'Server Manager', publisher: 'Microsoft Corporation', enabled: true, impact: 'Medium' },
  { name: 'CTF Loader', publisher: 'Microsoft Corporation', enabled: true, impact: 'Low' },
  { name: 'Realtek HD Audio Manager', publisher: 'Realtek Semiconductor', enabled: true, impact: 'Low' },
]

// ── Processes ──────────────────────────────────────────────────────────────
const P = (pid, name, desc, user, cpu, mem, type = 'background') =>
  ({ pid, name, desc, user, cpu, mem, type, priority: 'Normal', status: 'Running' })

export const SEED_PROCESSES = [
  P(0, 'System Idle Process', 'Percentage of time the processor is idle', 'SYSTEM', 94.2, 0.1, 'background'),
  P(4, 'System', 'NT Kernel & System', 'SYSTEM', 0.3, 0.1, 'background'),
  P(88, 'Registry', 'Registry', 'SYSTEM', 0.0, 86.4, 'background'),
  P(372, 'smss.exe', 'Windows Session Manager', 'SYSTEM', 0.0, 1.1, 'background'),
  P(488, 'csrss.exe', 'Client Server Runtime Process', 'SYSTEM', 0.1, 4.8, 'background'),
  P(564, 'wininit.exe', 'Windows Start-Up Application', 'SYSTEM', 0.0, 5.2, 'background'),
  P(580, 'winlogon.exe', 'Windows Logon Application', 'SYSTEM', 0.0, 8.4, 'background'),
  P(672, 'services.exe', 'Services and Controller app', 'SYSTEM', 0.1, 9.1, 'background'),
  P(688, 'lsass.exe', 'Local Security Authority Process', 'SYSTEM', 0.2, 38.6, 'background'),
  P(820, 'svchost.exe', 'Host Process for Windows Services', 'SYSTEM', 0.1, 22.4, 'background'),
  P(884, 'svchost.exe', 'Host Process for Windows Services (RPC)', 'Network Service', 0.2, 18.9, 'background'),
  P(960, 'svchost.exe', 'Host Process for Windows Services (DcomLaunch)', 'SYSTEM', 0.0, 14.3, 'background'),
  P(1024, 'svchost.exe', 'Host Process for Windows Services (WinMgmt)', 'SYSTEM', 0.3, 89.2, 'background'),
  P(1188, 'dwm.exe', 'Desktop Window Manager', 'DWM-1', 0.8, 124.6, 'background'),
  P(1456, 'MsMpEng.exe', 'Antimalware Service Executable', 'SYSTEM', 0.4, 245.8, 'background'),
  P(1632, 'vmtoolsd.exe', 'VMware Tools Core Service', 'SYSTEM', 0.1, 18.2, 'background'),
  P(1684, 'VGAuthService.exe', 'VMware Guest Authentication Service', 'SYSTEM', 0.0, 8.4, 'background'),
  P(2104, 'spoolsv.exe', 'Print Spooler Service', 'SYSTEM', 0.0, 10.6, 'background'),
  P(2456, 'dns.exe', 'Domain Name System (DNS) Server', 'SYSTEM', 0.2, 64.3, 'background'),
  P(2512, 'dfsrs.exe', 'DFS Replication Service', 'SYSTEM', 0.0, 28.1, 'background'),
  P(2880, 'inetinfo.exe', 'Internet Information Services', 'SYSTEM', 0.1, 22.7, 'background'),
  P(2912, 'w3wp.exe', 'IIS Worker Process (DefaultAppPool)', 'ApplicationPoolIdentity', 0.3, 78.4, 'background'),
  P(3204, 'explorer.exe', 'Windows Explorer', 'lab\\Administrator', 0.3, 67.2, 'app'),
  P(3960, 'ServerManager.exe', 'Server Manager', 'lab\\Administrator', 0.1, 142.6, 'app'),
  P(4120, 'WmiPrvSE.exe', 'WMI Provider Host', 'Network Service', 0.1, 24.8, 'background'),
  P(4532, 'svchost.exe', 'Host Process for Windows Services (EventLog)', 'Local Service', 0.1, 45.2, 'background'),
  P(4980, 'taskhostw.exe', 'Host Process for Windows Tasks', 'lab\\Administrator', 0.0, 12.4, 'background'),
  P(5120, 'audiodg.exe', 'Windows Audio Device Graph Isolation', 'Local Service', 0.0, 22.1, 'background'),
  P(5360, 'ctfmon.exe', 'CTF Loader', 'lab\\Administrator', 0.0, 15.3, 'background'),
  P(6044, 'dllhost.exe', 'COM Surrogate', 'lab\\Administrator', 0.0, 12.2, 'background'),
]

// ── Network adapters ───────────────────────────────────────────────────────
export const SEED_ADAPTERS = [
  {
    id: 'eth0', name: 'Ethernet0', desc: 'vmxnet3 Ethernet Adapter', mac: '00:50:56:9A:12:34',
    status: 'Connected', speed: '10.0 Gbps', dhcp: false, ipv4: '192.168.10.50', mask: '255.255.255.0',
    gateway: '192.168.10.1', dns: ['192.168.10.10', '192.168.10.11'],
    ipv6: 'fe80::a1b2:c3d4:e5f6:7890', sent: 1234567890, received: 9876543210,
  },
  {
    id: 'eth1', name: 'Ethernet1', desc: 'vmxnet3 Ethernet Adapter #2', mac: '00:50:56:9A:56:78',
    status: 'Connected', speed: '10.0 Gbps', dhcp: false, ipv4: '10.0.0.50', mask: '255.255.255.0',
    gateway: '10.0.0.1', dns: ['192.168.10.10'], ipv6: 'fe80::b2c3:d4e5:f6a1:2345',
    sent: 456789012, received: 1234567890,
  },
]

// ── Physical disks (Disk 1 added via VMware, uninitialized) ─────────────────
export const SEED_DISKS = [
  {
    id: 0, model: 'VMware Virtual disk SCSI Disk Device', sizeGB: 256, initialized: true,
    style: 'GPT', status: 'Online', bus: 'SCSI', system: true,
    partitions: [
      { type: 'efi', label: 'EFI System Partition', sizeGB: 0.1, fs: '', status: 'Healthy (EFI System Partition)' },
      { type: 'primary', letter: 'C', label: 'Windows', sizeGB: 239.41, fs: 'NTFS', status: 'Healthy (Boot, Page File, Crash Dump, Primary Partition)' },
      { type: 'recovery', label: 'Recovery Partition', sizeGB: 0.51, fs: 'NTFS', status: 'Healthy (Recovery Partition)' },
    ],
  },
  {
    id: 1, model: 'VMware Virtual disk SCSI Disk Device', sizeGB: 500, initialized: true,
    style: 'GPT', status: 'Online', bus: 'SCSI', system: false,
    partitions: [
      { type: 'primary', letter: 'D', label: 'Data', sizeGB: 500, fs: 'NTFS', status: 'Healthy (Primary Partition)' },
    ],
  },
  {
    id: 2, model: 'VMware Virtual disk SCSI Disk Device', sizeGB: 100, initialized: false,
    style: 'RAW', status: 'Not Initialized', bus: 'SCSI', system: false, partitions: [],
  },
]

// ── Devices (Device Manager tree) ──────────────────────────────────────────
export const SEED_DEVICES = [
  { cls: 'Audio inputs and outputs', items: [{ name: 'Speakers/Headphones (High Definition Audio Device)', status: 'OK', driver: 'hdaudio.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' }] },
  { cls: 'Computer', items: [{ name: 'ACPI x64-based PC', status: 'OK', driver: 'hal.dll', ver: '10.0.20348.2402', provider: 'Microsoft', date: '2023-08-15' }] },
  { cls: 'Disk drives', items: [
    { name: 'VMware Virtual disk SCSI Disk Device', status: 'OK', driver: 'disk.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' },
    { name: 'VMware Virtual disk SCSI Disk Device', status: 'OK', driver: 'disk.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' },
  ] },
  { cls: 'Display adapters', items: [{ name: 'VMware SVGA 3D', status: 'OK', driver: 'vm3dmp.sys', ver: '8.17.2.14', provider: 'VMware, Inc.', date: '2023-05-01' }] },
  { cls: 'DVD/CD-ROM drives', items: [{ name: 'NECVMWar VMware SATA CD00', status: 'OK', driver: 'cdrom.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' }] },
  { cls: 'Firmware', items: [{ name: 'System Firmware', status: 'OK', driver: 'BiosDevice.sys', ver: '1.0.0.0', provider: 'Microsoft', date: '2023-08-15' }] },
  { cls: 'Keyboards', items: [{ name: 'Standard PS/2 Keyboard', status: 'OK', driver: 'kbdclass.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' }] },
  { cls: 'Mice and other pointing devices', items: [{ name: 'VMware Pointing Device', status: 'OK', driver: 'vmmouse.sys', ver: '12.5.10.0', provider: 'VMware, Inc.', date: '2023-05-01' }] },
  { cls: 'Monitors', items: [{ name: 'Generic Non-PnP Monitor', status: 'OK', driver: 'monitor.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' }] },
  { cls: 'Network adapters', items: [
    { name: 'vmxnet3 Ethernet Adapter', status: 'OK', driver: 'vmxnet3.sys', ver: '1.9.0.0', provider: 'VMware, Inc.', date: '2023-05-01' },
    { name: 'vmxnet3 Ethernet Adapter #2', status: 'OK', driver: 'vmxnet3.sys', ver: '1.9.0.0', provider: 'VMware, Inc.', date: '2023-05-01' },
    { name: 'WAN Miniport (IKEv2)', status: 'OK', driver: 'rasl2tp.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' },
    { name: 'WAN Miniport (PPTP)', status: 'OK', driver: 'raspptp.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' },
  ] },
  { cls: 'Ports (COM & LPT)', items: [
    { name: 'Communications Port (COM1)', status: 'OK', driver: 'serial.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' },
    { name: 'ECP Printer Port (LPT1)', status: 'OK', driver: 'parport.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' },
  ] },
  { cls: 'Print queues', items: [
    { name: 'Microsoft Print To PDF', status: 'OK', driver: 'mxdwdrv.dll', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' },
    { name: 'Microsoft XPS Document Writer', status: 'OK', driver: 'mxdwdrv.dll', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' },
  ] },
  { cls: 'Processors', items: Array.from({ length: 8 }, () => ({ name: 'Intel(R) Core(TM) i7-9700 CPU @ 3.00GHz', status: 'OK', driver: 'intelppm.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' })) },
  { cls: 'SCSI and RAID controllers', items: [{ name: 'VMware PVSCSI Controller', status: 'OK', driver: 'pvscsi.sys', ver: '1.3.20.0', provider: 'VMware, Inc.', date: '2023-05-01' }] },
  { cls: 'Security devices', items: [{ name: 'Trusted Platform Module 2.0', status: 'OK', driver: 'tpm.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' }] },
  { cls: 'Storage controllers', items: [
    { name: 'Microsoft Storage Spaces Controller', status: 'OK', driver: 'spaceport.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' },
    { name: 'Standard NVM Express Controller', status: 'OK', driver: 'stornvme.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' },
  ] },
  { cls: 'System devices', items: [
    { name: 'ACPI Fixed Feature Button', status: 'OK', driver: 'acpi.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' },
    { name: 'Direct memory access controller', status: 'OK', driver: 'acpi.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' },
    { name: 'High precision event timer', status: 'OK', driver: 'mshpet.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' },
    { name: 'PCI Express Root Complex', status: 'OK', driver: 'pci.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' },
    { name: 'System timer', status: 'OK', driver: 'acpi.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' },
  ] },
  { cls: 'Universal Serial Bus controllers', items: [
    { name: 'USB Root Hub (USB 3.0)', status: 'OK', driver: 'usbhub3.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' },
    { name: 'Intel(R) USB 3.0 eXtensible Host Controller', status: 'OK', driver: 'usbxhci.sys', ver: '10.0.20348.1', provider: 'Microsoft', date: '2023-08-15' },
  ] },
]

// ── Active Directory ───────────────────────────────────────────────────────
const FIRST = ['John', 'Sarah', 'Michael', 'Emily', 'Robert', 'Jessica', 'David', 'Ashley', 'James', 'Amanda',
  'Daniel', 'Melissa', 'Matthew', 'Stephanie', 'Andrew', 'Nicole', 'Joshua', 'Elizabeth', 'Christopher', 'Megan',
  'Anthony', 'Lauren', 'William', 'Rachel', 'Brandon', 'Kayla', 'Ryan', 'Brittany', 'Justin', 'Samantha']
const LAST = ['Smith', 'Johnson', 'Chen', 'Davis', 'Wilson', 'Brown', 'Taylor', 'Anderson', 'Thomas', 'Jackson',
  'White', 'Harris', 'Martin', 'Thompson', 'Garcia', 'Martinez', 'Robinson', 'Clark', 'Rodriguez', 'Lewis',
  'Lee', 'Walker', 'Hall', 'Allen', 'Young', 'King', 'Wright', 'Lopez', 'Hill', 'Green']
const TITLES = {
  Engineering: ['Senior Software Engineer', 'Software Engineer', 'DevOps Engineer', 'QA Engineer', 'Engineering Manager'],
  Finance: ['Financial Analyst', 'Accountant', 'Controller', 'Finance Manager', 'Payroll Specialist'],
  HR: ['HR Manager', 'Recruiter', 'HR Generalist', 'Benefits Coordinator'],
  IT: ['Systems Administrator', 'Network Engineer', 'Help Desk Technician', 'IT Manager', 'Security Analyst'],
  Marketing: ['Marketing Director', 'Content Strategist', 'SEO Specialist', 'Brand Manager', 'Social Media Manager'],
  Legal: ['Corporate Counsel', 'Paralegal', 'Compliance Officer'],
}

function buildUsers() {
  const depts = Object.keys(TITLES)
  const users = []
  let idx = 0
  depts.forEach((dept) => {
    const count = { Engineering: 25, Finance: 12, HR: 8, IT: 10, Marketing: 15, Legal: 5 }[dept]
    for (let i = 0; i < count; i++) {
      const fn = FIRST[idx % FIRST.length]
      const ln = LAST[(idx * 7 + 3) % LAST.length]
      const sam = (fn[0] + ln).toLowerCase() + (i || '')
      const title = TITLES[dept][i % TITLES[dept].length]
      users.push({
        sam, first: fn, last: ln, display: `${fn} ${ln}`,
        upn: `${sam}@lab.local`, email: `${sam}@lab.local`,
        dept, title, ou: `OU=${dept},OU=Corp,DC=lab,DC=local`,
        enabled: idx % 17 !== 0, locked: idx % 23 === 0,
        phone: `+1 (555) ${String(100 + idx).padStart(3, '0')}-${String(1000 + idx * 7).slice(-4)}`,
        office: `Building ${1 + (idx % 3)}, Room ${100 + idx}`,
        company: 'Lab Industries', manager: idx > 0 ? users[Math.max(0, idx - 5)]?.display : '',
        employeeId: `E${String(10000 + idx)}`,
        groups: ['Domain Users', `${dept}-Team`].concat(dept === 'IT' ? ['IT-Admins'] : []),
        pwLastSet: '2024-01-02', lastLogon: '2024-01-17 08:' + String(10 + (idx % 49)).padStart(2, '0'),
      })
      idx++
    }
  })
  users.unshift({
    sam: 'Administrator', first: '', last: '', display: 'Administrator', upn: 'Administrator@lab.local',
    email: '', dept: '', title: 'Built-in account for administering the computer/domain',
    ou: 'CN=Users,DC=lab,DC=local', enabled: true, locked: false, phone: '', office: '',
    company: '', manager: '', employeeId: '', groups: ['Domain Admins', 'Enterprise Admins', 'Schema Admins', 'Administrators', 'Domain Users'],
    pwLastSet: '2023-08-15', lastLogon: '2024-01-17 06:00',
  })
  return users
}

export const SEED_AD_USERS = buildUsers()

export const SEED_AD_GROUPS = [
  { name: 'Domain Admins', scope: 'Global', category: 'Security', desc: 'Designated administrators of the domain' },
  { name: 'Domain Users', scope: 'Global', category: 'Security', desc: 'All domain users' },
  { name: 'Domain Computers', scope: 'Global', category: 'Security', desc: 'All workstations and servers joined to the domain' },
  { name: 'Enterprise Admins', scope: 'Universal', category: 'Security', desc: 'Designated administrators of the enterprise' },
  { name: 'Schema Admins', scope: 'Universal', category: 'Security', desc: 'Designated administrators of the schema' },
  { name: 'Group Policy Creator Owners', scope: 'Global', category: 'Security', desc: 'Members can modify group policy for the domain' },
  { name: 'IT-Admins', scope: 'Global', category: 'Security', desc: 'IT administrative staff' },
  { name: 'Server-Admins', scope: 'Global', category: 'Security', desc: 'Server administrators' },
  { name: 'Help-Desk', scope: 'Global', category: 'Security', desc: 'Tier-1 support staff' },
  { name: 'Engineering-Team', scope: 'Global', category: 'Security', desc: 'Engineering department' },
  { name: 'Finance-Team', scope: 'Global', category: 'Security', desc: 'Finance department' },
  { name: 'HR-Team', scope: 'Global', category: 'Security', desc: 'HR department' },
  { name: 'Marketing-Team', scope: 'Global', category: 'Security', desc: 'Marketing department' },
  { name: 'Legal-Team', scope: 'Global', category: 'Security', desc: 'Legal department' },
  { name: 'VPN-Users', scope: 'Global', category: 'Security', desc: 'Users allowed VPN access' },
  { name: 'Remote-Desktop-Users', scope: 'DomainLocal', category: 'Security', desc: 'Members may log on via Remote Desktop' },
  { name: 'Backup-Operators', scope: 'DomainLocal', category: 'Security', desc: 'Members can override security to back up files' },
  { name: 'SQL-Admins', scope: 'Global', category: 'Security', desc: 'SQL Server administrators' },
  { name: 'IIS-Admins', scope: 'Global', category: 'Security', desc: 'IIS administrators' },
  { name: 'Security-Team', scope: 'Global', category: 'Security', desc: 'Information security team' },
]

export const SEED_OU_TREE = {
  name: 'lab.local', type: 'domain',
  children: [
    { name: 'Builtin', type: 'builtin' },
    { name: 'Computers', type: 'container' },
    { name: 'Domain Controllers', type: 'ou', computers: ['DC01'] },
    { name: 'ForeignSecurityPrincipals', type: 'container' },
    { name: 'Managed Service Accounts', type: 'container' },
    { name: 'Users', type: 'container' },
    {
      name: 'Corp', type: 'ou', children: [
        { name: 'Engineering', type: 'ou', dept: 'Engineering' },
        { name: 'Finance', type: 'ou', dept: 'Finance' },
        { name: 'HR', type: 'ou', dept: 'HR' },
        { name: 'IT', type: 'ou', dept: 'IT', children: [{ name: 'Servers', type: 'ou' }] },
        { name: 'Legal', type: 'ou', dept: 'Legal' },
        { name: 'Marketing', type: 'ou', dept: 'Marketing' },
      ],
    },
    { name: 'Service Accounts', type: 'ou' },
  ],
}

// ── Installed programs (Programs and Features) ─────────────────────────────
export const SEED_PROGRAMS = [
  { name: 'Google Chrome', publisher: 'Google LLC', installed: '1/10/2024', size: '312 MB', version: '120.0.6099.130' },
  { name: 'Mozilla Firefox', publisher: 'Mozilla', installed: '12/20/2023', size: '214 MB', version: '121.0' },
  { name: '7-Zip 23.01', publisher: 'Igor Pavlov', installed: '11/5/2023', size: '5.12 MB', version: '23.01' },
  { name: 'Notepad++ (64-bit)', publisher: 'Notepad++ Team', installed: '10/15/2023', size: '11.4 MB', version: '8.6' },
  { name: 'PuTTY release 0.79', publisher: 'Simon Tatham', installed: '9/20/2023', size: '3.5 MB', version: '0.79' },
  { name: 'WinSCP 6.1.1', publisher: 'Martin Prikryl', installed: '9/20/2023', size: '45.2 MB', version: '6.1.1' },
  { name: 'Microsoft Visual Studio Code', publisher: 'Microsoft Corporation', installed: '1/5/2024', size: '356 MB', version: '1.85.1' },
  { name: 'Git', publisher: 'The Git Development Community', installed: '12/10/2023', size: '282 MB', version: '2.43.0' },
  { name: 'Python 3.11.7 (64-bit)', publisher: 'Python Software Foundation', installed: '11/28/2023', size: '67.1 MB', version: '3.11.7150.0' },
  { name: 'VMware Tools', publisher: 'VMware, Inc.', installed: '8/15/2023', size: '62.4 MB', version: '12.2.0.21872' },
  { name: 'Microsoft Visual C++ 2015-2022 Redistributable (x64)', publisher: 'Microsoft Corporation', installed: '8/15/2023', size: '24.7 MB', version: '14.36.32532.0' },
  { name: 'Microsoft Visual C++ 2015-2022 Redistributable (x86)', publisher: 'Microsoft Corporation', installed: '8/15/2023', size: '19.1 MB', version: '14.36.32532.0' },
  { name: 'Microsoft .NET Framework 4.8', publisher: 'Microsoft Corporation', installed: '8/15/2023', size: '—', version: '4.8.09032' },
  { name: 'Wireshark 4.2.0 64-bit', publisher: 'The Wireshark developer community', installed: '12/1/2023', size: '198 MB', version: '4.2.0' },
  { name: 'Microsoft Edge', publisher: 'Microsoft Corporation', installed: '8/15/2023', size: '178 MB', version: '120.0.2210.91' },
]

// ── Windows Update history ─────────────────────────────────────────────────
export const SEED_UPDATES = [
  { date: '2024-01-15', kb: 'KB5034129', title: '2024-01 Cumulative Update for Microsoft server operating system version 21H2 for x64-based Systems', status: 'Successfully installed', type: 'Security' },
  { date: '2024-01-09', kb: 'KB5033909', title: '2024-01 Cumulative Update for .NET Framework 3.5 and 4.8 for Microsoft server operating system version 21H2', status: 'Successfully installed', type: 'Quality' },
  { date: '2024-01-09', kb: 'KB5034619', title: 'Security Intelligence Update for Microsoft Defender Antivirus - KB2267602', status: 'Successfully installed', type: 'Definition' },
  { date: '2023-12-12', kb: 'KB5033118', title: '2023-12 Cumulative Update for Microsoft server operating system version 21H2 for x64-based Systems', status: 'Successfully installed', type: 'Security' },
  { date: '2023-12-12', kb: 'KB5032392', title: 'Servicing Stack Update for Microsoft server operating system version 21H2', status: 'Successfully installed', type: 'Quality' },
  { date: '2023-11-14', kb: 'KB5032198', title: '2023-11 Cumulative Update for Microsoft server operating system version 21H2 for x64-based Systems', status: 'Successfully installed', type: 'Security' },
  { date: '2023-10-10', kb: 'KB5031364', title: '2023-10 Cumulative Update for Microsoft server operating system version 21H2 for x64-based Systems', status: 'Successfully installed', type: 'Security' },
]

// ── Scheduled tasks ────────────────────────────────────────────────────────
export const SEED_TASKS = [
  { name: 'Daily Backup', status: 'Ready', triggers: 'At 2:00 AM every day', nextRun: '2024-01-18 2:00:00 AM', lastRun: '2024-01-17 2:00:00 AM', result: '0x0', author: 'lab\\Administrator' },
  { name: 'Weekly Defrag', status: 'Ready', triggers: 'At 3:00 AM every Sunday', nextRun: '2024-01-21 3:00:00 AM', lastRun: '2024-01-14 3:00:00 AM', result: '0x0', author: 'lab\\Administrator' },
  { name: 'Clear Temp Files', status: 'Ready', triggers: 'At 12:00 AM every day', nextRun: '2024-01-18 12:00:00 AM', lastRun: '2024-01-17 12:00:00 AM', result: '0x0', author: 'lab\\Administrator' },
  { name: 'Windows Update Check', status: 'Ready', triggers: 'At 6:00 AM every day', nextRun: '2024-01-18 6:00:00 AM', lastRun: '2024-01-17 6:00:00 AM', result: '0x0', author: 'SYSTEM' },
  { name: 'SSL Certificate Renewal', status: 'Ready', triggers: 'At 1:00 AM on day 1 of every month', nextRun: '2024-02-01 1:00:00 AM', lastRun: '2024-01-01 1:00:00 AM', result: '0x0', author: 'lab\\Administrator' },
  { name: 'Database Maintenance', status: 'Ready', triggers: 'At 1:00 AM every day', nextRun: '2024-01-18 1:00:00 AM', lastRun: '2024-01-17 1:00:00 AM', result: '0x0', author: 'lab\\Administrator' },
  { name: 'Log Rotation', status: 'Ready', triggers: 'At 11:59 PM every day', nextRun: '2024-01-17 11:59:00 PM', lastRun: '2024-01-16 11:59:00 PM', result: '0x0', author: 'lab\\Administrator' },
  { name: 'Health Check Report', status: 'Running', triggers: 'At 8:00 AM every day', nextRun: '2024-01-18 8:00:00 AM', lastRun: '2024-01-17 8:00:00 AM', result: '0x41301 (running)', author: 'lab\\Administrator' },
]

// ── Roles (Server Manager) ─────────────────────────────────────────────────
export const SEED_ROLES = [
  { id: 'AD-Domain-Services', name: 'Active Directory Domain Services', installed: true, events: 2, services: 0, perf: 'OK', bpa: 1 },
  { id: 'DNS', name: 'DNS Server', installed: true, events: 0, services: 0, perf: 'OK', bpa: 0 },
  { id: 'DHCP', name: 'DHCP Server', installed: true, events: 1, services: 0, perf: 'OK', bpa: 0 },
  { id: 'FileAndStorage', name: 'File and Storage Services', installed: true, events: 0, services: 0, perf: 'OK', bpa: 0 },
  { id: 'Hyper-V', name: 'Hyper-V', installed: true, events: 0, services: 1, perf: 'OK', bpa: 2 },
  { id: 'Web-Server', name: 'Web Server (IIS)', installed: true, events: 3, services: 0, perf: 'OK', bpa: 0 },
]
