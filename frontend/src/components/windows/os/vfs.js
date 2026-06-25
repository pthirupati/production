// ─────────────────────────────────────────────────────────────────────────
// Virtual filesystem seed. Stored flat: directories map path -> child names,
// files map path -> { content, size, created, modified, attrs }.
// Paths use backslashes and are case-insensitive in lookups (store helper).
// ─────────────────────────────────────────────────────────────────────────

const now = '2024-01-17 11:30:00'
const f = (content = '', size = null, modified = '2024-01-16 14:47:15') =>
  ({ content, size: size == null ? content.length : size, created: '2024-01-15 09:23:41', modified, accessed: now, attrs: [] })

// Build directory + file maps from a nested spec.
const dirs = {}
const files = {}

function addDir(path, children) { dirs[path] = children }

// ── Drive roots ────────────────────────────────────────────────────────────
addDir('C:\\', ['$Recycle.Bin', 'Boot', 'inetpub', 'PerfLogs', 'Program Files', 'Program Files (x86)', 'ProgramData', 'System Volume Information', 'Users', 'Windows'])
addDir('D:\\', ['Backups', 'Data', 'ISO', 'Logs', 'Scripts'])

// ── C:\Boot ──────────────────────────────────────────────────────────────
addDir('C:\\Boot', ['BCD', 'bootstat.dat', 'en-US'])
files['C:\\Boot\\BCD'] = f('', 262144)
files['C:\\Boot\\bootstat.dat'] = f('', 67584)
addDir('C:\\Boot\\en-US', ['bootmgr.exe.mui'])
files['C:\\Boot\\en-US\\bootmgr.exe.mui'] = f('', 32768)

// ── C:\inetpub ─────────────────────────────────────────────────────────────
addDir('C:\\inetpub', ['custerr', 'history', 'logs', 'temp', 'wwwroot'])
addDir('C:\\inetpub\\logs', ['LogFiles'])
addDir('C:\\inetpub\\logs\\LogFiles', ['W3SVC1'])
addDir('C:\\inetpub\\logs\\LogFiles\\W3SVC1', ['u_ex240117.log', 'u_ex240116.log', 'u_ex240115.log'])
files['C:\\inetpub\\logs\\LogFiles\\W3SVC1\\u_ex240117.log'] = f('#Software: Microsoft Internet Information Services 10.0\n#Version: 1.0\n#Date: 2024-01-17 00:00:00\n#Fields: date time s-ip cs-method cs-uri-stem sc-status time-taken\n2024-01-17 08:14:22 192.168.10.50 GET /index.html 200 12\n2024-01-17 08:14:25 192.168.10.50 GET /favicon.ico 404 3\n', 48213)
files['C:\\inetpub\\logs\\LogFiles\\W3SVC1\\u_ex240116.log'] = f('', 51200)
files['C:\\inetpub\\logs\\LogFiles\\W3SVC1\\u_ex240115.log'] = f('', 49800)
addDir('C:\\inetpub\\wwwroot', ['index.html', 'iisstart.htm', 'iisstart.png', 'web.config'])
files['C:\\inetpub\\wwwroot\\index.html'] = f('<!DOCTYPE html>\n<html><head><title>IIS Windows Server</title></head>\n<body><h1>Internet Information Services</h1>\n<p>Welcome — the default web site is running.</p></body></html>\n')
files['C:\\inetpub\\wwwroot\\iisstart.htm'] = f('<!DOCTYPE html><html><head><title>IIS</title></head><body></body></html>\n')
files['C:\\inetpub\\wwwroot\\iisstart.png'] = f('', 99710)
files['C:\\inetpub\\wwwroot\\web.config'] = f('<?xml version="1.0" encoding="UTF-8"?>\n<configuration>\n  <system.webServer>\n    <defaultDocument>\n      <files>\n        <add value="index.html" />\n      </files>\n    </defaultDocument>\n  </system.webServer>\n</configuration>\n')

// ── C:\Program Files ───────────────────────────────────────────────────────
addDir('C:\\Program Files', ['Common Files', 'Internet Explorer', 'Microsoft SQL Server', 'Reference Assemblies', 'VMware', 'Windows Defender', 'Windows PowerShell'])
addDir('C:\\Program Files\\VMware', ['VMware Tools'])
addDir('C:\\Program Files\\VMware\\VMware Tools', ['vmtoolsd.exe', 'vmware-tools-daemon.exe', 'plugins', 'drivers'])
files['C:\\Program Files\\VMware\\VMware Tools\\vmtoolsd.exe'] = f('', 4523008)
addDir('C:\\Program Files (x86)', ['Common Files', 'Internet Explorer'])
addDir('C:\\ProgramData', ['Microsoft', 'VMware'])

// ── C:\Users ───────────────────────────────────────────────────────────────
addDir('C:\\Users', ['Administrator', 'Default', 'Public'])
addDir('C:\\Users\\Administrator', ['.ssh', 'AppData', 'Desktop', 'Documents', 'Downloads', 'Favorites', 'Music', 'Pictures', 'Videos'])
addDir('C:\\Users\\Administrator\\.ssh', ['authorized_keys', 'id_rsa', 'id_rsa.pub', 'known_hosts'])
files['C:\\Users\\Administrator\\.ssh\\authorized_keys'] = f('ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDlab-admin-key admin@lab.local\n')
files['C:\\Users\\Administrator\\.ssh\\id_rsa.pub'] = f('ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDlab-admin-key admin@lab.local\n')
files['C:\\Users\\Administrator\\.ssh\\known_hosts'] = f('192.168.10.10 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI...\n')
addDir('C:\\Users\\Administrator\\AppData', ['Local', 'LocalLow', 'Roaming'])
addDir('C:\\Users\\Administrator\\AppData\\Local', ['Microsoft', 'Temp'])
addDir('C:\\Users\\Administrator\\AppData\\Roaming', ['Microsoft'])
addDir('C:\\Users\\Administrator\\Desktop', ['Server Manager.lnk', 'PowerShell.lnk', 'notes.txt'])
files['C:\\Users\\Administrator\\Desktop\\notes.txt'] = f('Lab environment - WS2022\n\nReminders:\n- Patch Tuesday updates pending review\n- Verify DHCP scope for VLAN 20\n- Rotate service account passwords\n')
files['C:\\Users\\Administrator\\Desktop\\Server Manager.lnk'] = f('', 1842)
files['C:\\Users\\Administrator\\Desktop\\PowerShell.lnk'] = f('', 1764)
addDir('C:\\Users\\Administrator\\Documents', ['WindowsPowerShell', 'scripts', 'reports'])
addDir('C:\\Users\\Administrator\\Documents\\WindowsPowerShell', ['profile.ps1'])
files['C:\\Users\\Administrator\\Documents\\WindowsPowerShell\\profile.ps1'] = f('# PowerShell profile\nSet-Location C:\\\nImport-Module ActiveDirectory\nfunction prompt { "PS $(Get-Location)> " }\n')
addDir('C:\\Users\\Administrator\\Documents\\scripts', ['backup.ps1', 'user-create.ps1', 'health-check.ps1'])
files['C:\\Users\\Administrator\\Documents\\scripts\\backup.ps1'] = f('# Daily backup script\n$src = "D:\\Data"\n$dst = "D:\\Backups\\Daily"\n$date = Get-Date -Format "yyyy-MM-dd"\nCompress-Archive -Path $src -DestinationPath "$dst\\backup_$date.zip" -Force\nWrite-Host "Backup complete: $date"\n')
files['C:\\Users\\Administrator\\Documents\\scripts\\user-create.ps1'] = f('param([string]$Name, [string]$Sam)\nNew-ADUser -Name $Name -SamAccountName $Sam -Enabled $true -AccountPassword (ConvertTo-SecureString "P@ssw0rd!" -AsPlainText -Force)\nAdd-ADGroupMember -Identity "Domain Users" -Members $Sam\n')
files['C:\\Users\\Administrator\\Documents\\scripts\\health-check.ps1'] = f('# Server health check\nGet-Service | Where-Object {$_.Status -eq "Stopped" -and $_.StartType -eq "Automatic"}\nGet-Volume | Where-Object {$_.SizeRemaining -lt 10GB}\nGet-EventLog -LogName System -EntryType Error -Newest 10\n')
addDir('C:\\Users\\Administrator\\Downloads', ['KB5025175.msu', 'VMwareTools-12.2.0.exe'])
files['C:\\Users\\Administrator\\Downloads\\KB5025175.msu'] = f('', 542113792)
files['C:\\Users\\Administrator\\Downloads\\VMwareTools-12.2.0.exe'] = f('', 134217728)
addDir('C:\\Users\\Public', ['Desktop', 'Documents', 'Downloads'])
addDir('C:\\Users\\Default', [])

// ── C:\Windows (representative subset, deep enough to be real) ──────────────
addDir('C:\\Windows', ['System32', 'SysWOW64', 'Temp', 'Logs', 'Fonts', 'INF', 'Web', 'WinSxS', 'SoftwareDistribution', 'explorer.exe', 'notepad.exe', 'regedit.exe', 'win.ini', 'system.ini'])
files['C:\\Windows\\explorer.exe'] = f('', 4831232)
files['C:\\Windows\\notepad.exe'] = f('', 201728)
files['C:\\Windows\\regedit.exe'] = f('', 401408)
files['C:\\Windows\\win.ini'] = f('; for 16-bit app support\n[fonts]\n[extensions]\n[mci extensions]\n[files]\n[Mail]\nMAPI=1\n')
files['C:\\Windows\\system.ini'] = f('; for 16-bit app support\n[386Enh]\nwoafont=dosapp.fon\n[drivers]\nwave=mmdrv.dll\ntimer=timer.drv\n[mci]\n')
addDir('C:\\Windows\\System32', ['config', 'drivers', 'winevt', 'Tasks', 'WindowsPowerShell', 'cmd.exe', 'powershell.exe', 'regedit.exe', 'mmc.exe', 'services.exe', 'svchost.exe', 'taskmgr.exe', 'dnsmgmt.msc', 'dhcpmgmt.msc', 'dsa.msc', 'gpmc.msc'])
files['C:\\Windows\\System32\\cmd.exe'] = f('', 289792)
files['C:\\Windows\\System32\\powershell.exe'] = f('', 452608)
files['C:\\Windows\\System32\\taskmgr.exe'] = f('', 1284608)
addDir('C:\\Windows\\System32\\config', ['SAM', 'SECURITY', 'SOFTWARE', 'SYSTEM', 'DEFAULT'])
files['C:\\Windows\\System32\\config\\SAM'] = f('', 65536)
files['C:\\Windows\\System32\\config\\SYSTEM'] = f('', 14680064)
files['C:\\Windows\\System32\\config\\SOFTWARE'] = f('', 132120576)
addDir('C:\\Windows\\System32\\drivers', ['etc', 'disk.sys', 'tcpip.sys', 'ndis.sys', 'vmxnet3.sys'])
addDir('C:\\Windows\\System32\\drivers\\etc', ['hosts', 'networks', 'protocol', 'services', 'lmhosts.sam'])
files['C:\\Windows\\System32\\drivers\\etc\\hosts'] = f('# Copyright (c) 1993-2009 Microsoft Corp.\n#\n# This is a sample HOSTS file used by Microsoft TCP/IP for Windows.\n#\n127.0.0.1       localhost\n::1             localhost\n192.168.10.10   dc01.lab.local dc01\n192.168.10.20   mail.lab.local mail\n192.168.10.50   server01.lab.local server01\n192.168.10.51   server02.lab.local server02\n192.168.10.60   web01.lab.local web01\n192.168.10.70   db01.lab.local db01\n10.0.0.50       server01-mgmt\n')
files['C:\\Windows\\System32\\drivers\\etc\\networks'] = f('# networks - This file contains network name/number mappings\nloopback 127\n')
files['C:\\Windows\\System32\\drivers\\etc\\services'] = f('# This file contains port numbers for well-known services\nftp                21/tcp\nssh                22/tcp\ntelnet             23/tcp\nsmtp               25/tcp\ndomain             53/tcp\nhttp               80/tcp\nhttps             443/tcp\nldap              389/tcp\nkerberos           88/tcp\nmicrosoft-ds      445/tcp\n')
addDir('C:\\Windows\\System32\\winevt', ['Logs'])
addDir('C:\\Windows\\System32\\winevt\\Logs', ['Application.evtx', 'Security.evtx', 'System.evtx', 'Setup.evtx', 'Microsoft-Windows-PowerShell%4Operational.evtx', 'Microsoft-Windows-WindowsUpdateClient%4Operational.evtx', 'Microsoft-Windows-GroupPolicy%4Operational.evtx'])
files['C:\\Windows\\System32\\winevt\\Logs\\Application.evtx'] = f('', 20975616)
files['C:\\Windows\\System32\\winevt\\Logs\\Security.evtx'] = f('', 20975616)
files['C:\\Windows\\System32\\winevt\\Logs\\System.evtx'] = f('', 20975616)
addDir('C:\\Windows\\System32\\WindowsPowerShell', ['v1.0'])
addDir('C:\\Windows\\System32\\WindowsPowerShell\\v1.0', ['powershell.exe', 'powershell_ise.exe', 'Modules'])
addDir('C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\Modules', ['ActiveDirectory', 'DnsServer', 'DhcpServer', 'Hyper-V', 'NetTCPIP', 'Storage', 'Microsoft.PowerShell.Management'])
addDir('C:\\Windows\\System32\\Tasks', ['Daily Backup', 'Weekly Defrag', 'Microsoft'])
addDir('C:\\Windows\\Temp', ['vmware-SYSTEM', 'TS_ABCD.tmp'])
addDir('C:\\Windows\\Logs', ['CBS', 'DISM', 'WindowsUpdate'])
addDir('C:\\Windows\\Logs\\CBS', ['CBS.log'])
files['C:\\Windows\\Logs\\CBS\\CBS.log'] = f('2024-01-17 06:00:01, Info CBS Starting TrustedInstaller initialization.\n2024-01-17 06:00:01, Info CBS Loaded Servicing Stack v10.0.20348.2402\n2024-01-17 06:00:02, Info CBS Ending TrustedInstaller initialization.\n', 4823611)
addDir('C:\\Windows\\Fonts', ['arial.ttf', 'arialbd.ttf', 'calibri.ttf', 'consola.ttf', 'segoeui.ttf', 'segoeuib.ttf', 'tahoma.ttf', 'times.ttf', 'verdana.ttf', 'cour.ttf'])
addDir('C:\\Windows\\SoftwareDistribution', ['Download', 'DataStore'])
addDir('C:\\Windows\\SysWOW64', ['cmd.exe', 'kernel32.dll', 'user32.dll'])
addDir('C:\\Windows\\WinSxS', ['Manifests', 'Temp'])
addDir('C:\\Windows\\INF', ['setupapi.dev.log'])
addDir('C:\\Windows\\Web', ['Wallpaper', 'Screen'])

addDir('C:\\PerfLogs', [])
addDir('C:\\$Recycle.Bin', [])
addDir('C:\\System Volume Information', [])

// ── D: drive ───────────────────────────────────────────────────────────────
addDir('D:\\Backups', ['Daily', 'Weekly'])
addDir('D:\\Backups\\Daily', ['backup_2024-01-15.tar.gz', 'backup_2024-01-16.tar.gz', 'backup_2024-01-17.tar.gz'])
files['D:\\Backups\\Daily\\backup_2024-01-15.tar.gz'] = f('', 4509715660)
files['D:\\Backups\\Daily\\backup_2024-01-16.tar.gz'] = f('', 4616794931)
files['D:\\Backups\\Daily\\backup_2024-01-17.tar.gz'] = f('', 4402341478)
addDir('D:\\Backups\\Weekly', ['weekly_2024-01-14.tar.gz'])
files['D:\\Backups\\Weekly\\weekly_2024-01-14.tar.gz'] = f('', 13743895347)
addDir('D:\\Data', ['Databases', 'Shares'])
addDir('D:\\Data\\Databases', ['production.bak', 'staging.bak'])
files['D:\\Data\\Databases\\production.bak'] = f('', 9341899571)
files['D:\\Data\\Databases\\staging.bak'] = f('', 2254857830)
addDir('D:\\Data\\Shares', ['HR', 'Finance', 'IT', 'Public'])
addDir('D:\\Data\\Shares\\HR', ['policies.docx', 'org-chart.pdf', 'onboarding.xlsx'])
addDir('D:\\Data\\Shares\\Finance', ['budget-2024.xlsx', 'invoices', 'reports'])
addDir('D:\\Data\\Shares\\IT', ['runbooks', 'diagrams', 'inventory.csv'])
addDir('D:\\Data\\Shares\\Public', ['readme.txt'])
files['D:\\Data\\Shares\\Public\\readme.txt'] = f('Public share — drop files here for everyone.\n')
addDir('D:\\ISO', ['WS2022_EVAL_x64FRE_en-us.iso', 'ubuntu-22.04.3-live-server-amd64.iso'])
files['D:\\ISO\\WS2022_EVAL_x64FRE_en-us.iso'] = f('', 5045088256)
files['D:\\ISO\\ubuntu-22.04.3-live-server-amd64.iso'] = f('', 1503238553)
addDir('D:\\Logs', ['app-2024-01-17.log', 'app-2024-01-16.log', 'IIS'])
files['D:\\Logs\\app-2024-01-17.log'] = f('2024-01-17 08:00:00 INFO  Service started\n2024-01-17 08:15:23 INFO  Health check OK\n2024-01-17 09:42:11 WARN  High memory usage: 78%\n', 159744)
files['D:\\Logs\\app-2024-01-16.log'] = f('', 207872)
addDir('D:\\Scripts', ['automation', 'maintenance'])
addDir('D:\\Scripts\\automation', ['deploy.ps1', 'monitor.ps1', 'cleanup.ps1'])
files['D:\\Scripts\\automation\\deploy.ps1'] = f('# Deployment automation\nparam([string]$Environment = "staging")\nWrite-Host "Deploying to $Environment..."\n')
addDir('D:\\Scripts\\maintenance', ['defrag.ps1', 'backup-verify.ps1'])

export const SEED_VFS = {
  drives: {
    C: { label: 'Windows', fs: 'NTFS', totalGB: 256, usedGB: 94.2, type: 'local', system: true },
    D: { label: 'Data', fs: 'NTFS', totalGB: 500, usedGB: 187.4, type: 'local', system: false },
    E: { label: 'DVD Drive', fs: '', totalGB: 0, usedGB: 0, type: 'dvd', noMedia: true },
  },
  network: {
    '\\\\SERVER01\\Shared': { totalGB: 1024, usedGB: 445 },
    '\\\\BACKUP01\\Backups': { totalGB: 2048, usedGB: 1126 },
  },
  dirs,
  files,
}
