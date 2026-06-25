// ─────────────────────────────────────────────────────────────────────────
// Event Viewer seed: generate realistic events for Application/Security/System.
// ─────────────────────────────────────────────────────────────────────────

function pad(n) { return String(n).padStart(2, '0') }

function timeAt(daysAgo, h, m) {
  const d = new Date(2024, 0, 17 - daysAgo, h, m, 0)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad((h * 7 + m * 3) % 60)}`
}

const SEC_TEMPLATES = [
  { id: 4624, level: 'Information', kw: 'Audit Success', task: 'Logon', src: 'Microsoft-Windows-Security-Auditing', msg: 'An account was successfully logged on.\n\nSubject:\n\tSecurity ID:\t\tSYSTEM\n\tAccount Name:\t\tSERVER01$\n\nLogon Type:\t\t3\n\nNew Logon:\n\tAccount Name:\t\tAdministrator\n\tAccount Domain:\t\tLAB\n\tLogon ID:\t\t0x3E7' },
  { id: 4634, level: 'Information', kw: 'Audit Success', task: 'Logoff', src: 'Microsoft-Windows-Security-Auditing', msg: 'An account was logged off.\n\nSubject:\n\tAccount Name:\t\tAdministrator\n\tAccount Domain:\t\tLAB\n\tLogon ID:\t\t0x1A2B3C' },
  { id: 4625, level: 'Information', kw: 'Audit Failure', task: 'Logon', src: 'Microsoft-Windows-Security-Auditing', msg: 'An account failed to log on.\n\nAccount For Which Logon Failed:\n\tAccount Name:\t\tjsmith\n\tAccount Domain:\t\tLAB\n\nFailure Reason:\t\tUnknown user name or bad password.\nStatus:\t\t\t0xC000006D\nSub Status:\t\t0xC000006A' },
  { id: 4672, level: 'Information', kw: 'Audit Success', task: 'Special Logon', src: 'Microsoft-Windows-Security-Auditing', msg: 'Special privileges assigned to new logon.\n\nSubject:\n\tAccount Name:\t\tAdministrator\n\tPrivileges:\t\tSeSecurityPrivilege, SeBackupPrivilege, SeRestorePrivilege, SeTakeOwnershipPrivilege, SeDebugPrivilege' },
  { id: 4688, level: 'Information', kw: 'Audit Success', task: 'Process Creation', src: 'Microsoft-Windows-Security-Auditing', msg: 'A new process has been created.\n\nProcess Information:\n\tNew Process Name:\tC:\\Windows\\System32\\cmd.exe\n\tCreator Process Name:\tC:\\Windows\\explorer.exe' },
  { id: 4740, level: 'Information', kw: 'Audit Success', task: 'User Account Management', src: 'Microsoft-Windows-Security-Auditing', msg: 'A user account was locked out.\n\nSubject:\n\tAccount Name:\t\tjsmith\n\tAccount Domain:\t\tLAB\n\nAdditional Information:\n\tCaller Computer Name:\tWS-ENG-04' },
  { id: 4768, level: 'Information', kw: 'Audit Success', task: 'Kerberos Authentication Service', src: 'Microsoft-Windows-Security-Auditing', msg: 'A Kerberos authentication ticket (TGT) was requested.\n\nAccount Information:\n\tAccount Name:\t\tjsmith\n\tService Name:\t\tkrbtgt\n\tResult Code:\t\t0x0' },
  { id: 4720, level: 'Information', kw: 'Audit Success', task: 'User Account Management', src: 'Microsoft-Windows-Security-Auditing', msg: 'A user account was created.\n\nNew Account:\n\tAccount Name:\t\tnewhire01\n\tAccount Domain:\t\tLAB\n\nSubject:\n\tAccount Name:\t\tAdministrator' },
]

const SYS_TEMPLATES = [
  { id: 7036, level: 'Information', src: 'Service Control Manager', task: 'None', msg: 'The Windows Update service entered the running state.' },
  { id: 7036, level: 'Information', src: 'Service Control Manager', task: 'None', msg: 'The Print Spooler service entered the stopped state.' },
  { id: 7040, level: 'Information', src: 'Service Control Manager', task: 'None', msg: 'The start type of the Background Intelligent Transfer Service was changed from demand start to auto start.' },
  { id: 6005, level: 'Information', src: 'EventLog', task: 'None', msg: 'The Event log service was started.' },
  { id: 6006, level: 'Information', src: 'EventLog', task: 'None', msg: 'The Event log service was stopped.' },
  { id: 1074, level: 'Information', src: 'User32', task: 'None', msg: 'The process C:\\Windows\\System32\\winlogon.exe has initiated the restart of computer SERVER01 on behalf of user LAB\\Administrator for the following reason: Operating System: Upgrade (Planned).' },
  { id: 41, level: 'Critical', src: 'Microsoft-Windows-Kernel-Power', task: '(63)', msg: 'The system has rebooted without cleanly shutting down first. This error could be caused if the system stopped responding, crashed, or lost power unexpectedly.' },
  { id: 6008, level: 'Error', src: 'EventLog', task: 'None', msg: 'The previous system shutdown at 3:42:17 AM on 1/12/2024 was unexpected.' },
  { id: 10016, level: 'Warning', src: 'DCOM', task: 'None', msg: 'The application-specific permission settings do not grant Local Activation permission for the COM Server application with CLSID {2593F8B9-4EAF-457C-B68A-50F6B8EA6B54}.' },
  { id: 129, level: 'Warning', src: 'vmxnet3', task: 'None', msg: 'Reset to device, \\Device\\RaidPort0, was issued.' },
  { id: 27, level: 'Information', src: 'e1iexpress', task: 'None', msg: 'Intel(R) Ethernet Connection: Network link is established at 10 Gbps full duplex.' },
]

const APP_TEMPLATES = [
  { id: 1000, level: 'Error', src: 'Application Error', task: '(100)', msg: 'Faulting application name: legacyapp.exe, version: 1.0.0.0\nFaulting module name: ntdll.dll\nException code: 0xc0000005' },
  { id: 1026, level: 'Error', src: '.NET Runtime', task: 'None', msg: 'Application: WebService.exe\nFramework Version: v4.0.30319\nUnhandled Exception: System.NullReferenceException' },
  { id: 1001, level: 'Information', src: 'Windows Error Reporting', task: 'None', msg: 'Fault bucket, type 0\nEvent Name: APPCRASH\nResponse: Not available' },
  { id: 17137, level: 'Information', src: 'MSSQLSERVER', task: 'Server', msg: 'Starting up database "production".' },
  { id: 18456, level: 'Error', src: 'MSSQLSERVER', task: 'Logon', msg: 'Login failed for user \'sa\'. Reason: Password did not match.' },
  { id: 1309, level: 'Warning', src: 'ASP.NET 4.0.30319.0', task: 'Web Event', msg: 'Event code: 3005\nEvent message: An unhandled exception has occurred.' },
  { id: 5615, level: 'Information', src: 'Windows Server Update Services', task: 'None', msg: 'WSUS synchronization completed successfully.' },
  { id: 11707, level: 'Information', src: 'MsiInstaller', task: 'None', msg: 'Product: VMware Tools -- Installation completed successfully.' },
]

function genEvents(templates, count, log) {
  const out = []
  for (let i = 0; i < count; i++) {
    const t = templates[i % templates.length]
    const daysAgo = Math.floor(i / 8)
    const h = (23 - (i % 24))
    const m = (i * 13) % 60
    out.push({
      ...t, log,
      time: timeAt(daysAgo, h, m),
      recordId: 100000 - i,
      computer: 'SERVER01.lab.local',
      kw: t.kw || 'Classic',
    })
  }
  return out
}

export const SEED_EVENTS = {
  Application: genEvents(APP_TEMPLATES, 120, 'Application'),
  Security: genEvents(SEC_TEMPLATES, 160, 'Security'),
  System: genEvents(SYS_TEMPLATES, 140, 'System'),
  Setup: genEvents([
    { id: 2, level: 'Information', src: 'Microsoft-Windows-Servicing', task: 'None', msg: 'Package KB5034129 was successfully changed to the Installed state.' },
    { id: 4, level: 'Information', src: 'Microsoft-Windows-Servicing', task: 'None', msg: 'Windows update "Security Update" was installed successfully.' },
  ], 40, 'Setup'),
}

export function eventXml(e) {
  return `<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
  <System>
    <Provider Name="${e.src}" />
    <EventID>${e.id}</EventID>
    <Version>0</Version>
    <Level>${e.level === 'Critical' ? 1 : e.level === 'Error' ? 2 : e.level === 'Warning' ? 3 : 4}</Level>
    <Task>0</Task>
    <Keywords>0x8020000000000000</Keywords>
    <TimeCreated SystemTime="${e.time.replace(' ', 'T')}Z" />
    <EventRecordID>${e.recordId}</EventRecordID>
    <Channel>${e.log}</Channel>
    <Computer>${e.computer}</Computer>
    <Security />
  </System>
  <EventData>
    <Data>${(e.msg || '').split('\n')[0]}</Data>
  </EventData>
</Event>`
}
