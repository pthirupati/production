import { useEffect, useRef, useState } from 'react'
import { useOS, normPath } from '../store'

// Build realistic output for PowerShell / CMD commands against the live store.
function runCommand(raw, shell, os, cwdRef) {
  const line = raw.trim()
  if (!line) return ['']
  const out = []
  const lower = line.toLowerCase()
  const cwd = cwdRef.current

  const tableFromObjects = (rows, cols) => {
    if (!rows.length) return ['']
    const widths = cols.map((c) => Math.max(c.h.length, ...rows.map((r) => String(c.v(r) ?? '').length)))
    const header = cols.map((c, i) => c.h.padEnd(widths[i])).join('  ')
    const sep = cols.map((c, i) => '-'.repeat(widths[i])).join('  ')
    const body = rows.map((r) => cols.map((c, i) => String(c.v(r) ?? '').padEnd(widths[i])).join('  '))
    return ['', header, sep, ...body, '']
  }

  // ── shared commands ──
  if (lower === 'hostname') return ['SERVER01']
  if (lower === 'whoami') return ['lab\\administrator']
  if (lower === 'cls' || lower === 'clear') return ['__CLEAR__']
  if (lower === 'exit') return ['__EXIT__']

  if (shell === 'ps') {
    if (lower === '$psversiontable' || lower === 'get-host') {
      return ['', 'Name                           Value', '----                           -----',
        'PSVersion                      5.1.20348.2402', 'PSEdition                      Desktop',
        'BuildVersion                   10.0.20348.2402', 'CLRVersion                     4.0.30319.42000',
        'WSManStackVersion              3.0', 'PSRemotingProtocolVersion      2.3', '']
    }
    if (lower === 'get-process' || lower.startsWith('get-process ')) {
      const rows = os.processes.filter((p) => p.pid > 4).slice(0, 24)
      return tableFromObjects(rows, [
        { h: 'Handles', v: (r) => 100 + (r.pid % 900) }, { h: 'NPM(K)', v: (r) => 10 + (r.pid % 40) },
        { h: 'PM(K)', v: (r) => Math.round(r.mem * 1024) }, { h: 'WS(K)', v: (r) => Math.round(r.mem * 1024) },
        { h: 'CPU(s)', v: (r) => (r.cpu * 3.2).toFixed(2) }, { h: 'Id', v: (r) => r.pid },
        { h: 'ProcessName', v: (r) => r.name.replace('.exe', '') },
      ])
    }
    if (lower === 'get-service' || lower.startsWith('get-service ')) {
      let rows = os.services
      const m = line.match(/-name\s+(\S+)/i)
      if (m) rows = rows.filter((s) => s.name.toLowerCase() === m[1].toLowerCase().replace(/['"]/g, ''))
      if (lower.includes('stopped')) rows = os.services.filter((s) => s.status === 'Stopped')
      return tableFromObjects(rows.slice(0, 40), [
        { h: 'Status', v: (r) => r.status }, { h: 'Name', v: (r) => r.name }, { h: 'DisplayName', v: (r) => r.display },
      ])
    }
    if (lower.startsWith('start-service')) { const m = line.match(/-name\s+(\S+)|start-service\s+(\S+)/i); const n = (m?.[1] || m?.[2] || '').replace(/['"]/g, ''); os.startService(n); return [''] }
    if (lower.startsWith('stop-service')) { const m = line.match(/-name\s+(\S+)|stop-service\s+(\S+)/i); const n = (m?.[1] || m?.[2] || '').replace(/['"]/g, ''); os.stopService(n); return [''] }
    if (lower.startsWith('restart-service')) { const m = line.match(/-name\s+(\S+)|restart-service\s+(\S+)/i); const n = (m?.[1] || m?.[2] || '').replace(/['"]/g, ''); os.stopService(n); os.startService(n); return [''] }

    if (lower.startsWith('get-childitem') || lower === 'ls' || lower === 'dir' || lower === 'gci') {
      const names = os.listDir(cwd) || []
      out.push('', `    Directory: ${cwd}`, '', 'Mode                 LastWriteTime         Length Name', '----                 -------------         ------ ----')
      names.forEach((n) => {
        const full = normPath(cwd + '\\' + n); const dir = os.isDir(full); const meta = os.fileMeta(full)
        const mode = dir ? 'd-----' : '-a----'
        out.push(`${mode}        2024-01-16  2:47 PM ${dir ? '' : String(meta?.size ?? 0).padStart(14)} ${n}`)
      })
      out.push('')
      return out
    }
    if (lower.startsWith('set-location') || lower.startsWith('cd ')) {
      const target = line.replace(/^(set-location|cd)\s+/i, '').replace(/['"]/g, '').trim()
      let np = target
      if (target === '..') { np = cwd.slice(0, cwd.lastIndexOf('\\')) || cwd.slice(0, 3) }
      else if (!/^[A-Za-z]:/.test(target)) np = normPath(cwd + '\\' + target)
      np = normPath(np)
      if (os.isDir(np)) { cwdRef.current = np; return [] }
      return [`Set-Location : Cannot find path '${target}' because it does not exist.`, '__ERR__']
    }
    if (lower.startsWith('new-item')) {
      const nameM = line.match(/-name\s+["']?([^"'\s]+)/i)
      const isDir = /directory/i.test(line)
      const nm = nameM?.[1] || 'NewItem'
      const full = normPath(cwd + '\\' + nm)
      if (isDir) os.createDirectory(full); else os.writeFile(full, '')
      out.push('', `    Directory: ${cwd}`, '', 'Mode                 LastWriteTime         Length Name', '----                 -------------         ------ ----', `${isDir ? 'd-----' : '-a----'}        2024-01-17  ${new Date().getHours()}:00 ${isDir ? '' : '             0'} ${nm}`, '')
      return out
    }
    if (lower.startsWith('remove-item')) { const m = line.match(/remove-item\s+["']?([^"'\s]+)/i); if (m) os.deleteItem(normPath(/^[A-Za-z]:/.test(m[1]) ? m[1] : cwd + '\\' + m[1])); return [''] }
    if (lower.startsWith('get-content') || lower.startsWith('cat ') || lower.startsWith('type ')) {
      const m = line.match(/(get-content|cat|type)\s+["']?([^"']+)/i)
      const p = normPath(/^[A-Za-z]:/.test(m?.[2] || '') ? m[2] : cwd + '\\' + (m?.[2] || ''))
      const c = os.readFile(p)
      return c == null ? [`Get-Content : Cannot find path '${m?.[2]}'.`, '__ERR__'] : c.split('\n')
    }

    if (lower.startsWith('get-aduser')) {
      if (lower.includes('-filter *')) {
        return tableFromObjects(os.adUsers.slice(0, 30), [
          { h: 'Name', v: (r) => r.display }, { h: 'SamAccountName', v: (r) => r.sam }, { h: 'Enabled', v: (r) => r.enabled },
        ])
      }
      const m = line.match(/get-aduser\s+["']?(\S+?)["']?(\s|$)/i)
      const u = os.adUsers.find((x) => x.sam.toLowerCase() === (m?.[1] || '').toLowerCase())
      if (!u) return [`Get-ADUser : Cannot find an object with identity: '${m?.[1]}' under: 'DC=lab,DC=local'.`, '__ERR__']
      return ['', `DistinguishedName : CN=${u.display},${u.ou}`, `Enabled           : ${u.enabled}`, `GivenName         : ${u.first}`,
        `Name              : ${u.display}`, `SamAccountName    : ${u.sam}`, `Surname           : ${u.last}`,
        `UserPrincipalName : ${u.upn}`, '']
    }
    if (lower.startsWith('new-aduser')) { const m = line.match(/-samaccountname\s+(\S+)/i); const n = line.match(/-name\s+["']([^"']+)/i); if (m) os.createADUser({ sam: m[1], display: n?.[1] || m[1], first: n?.[1]?.split(' ')[0] || '', last: n?.[1]?.split(' ')[1] || '', upn: `${m[1]}@lab.local`, email: `${m[1]}@lab.local`, dept: '', title: '', ou: 'CN=Users,DC=lab,DC=local', enabled: true, locked: false, groups: ['Domain Users'], phone: '', office: '', company: '', manager: '', employeeId: '', pwLastSet: '2024-01-17', lastLogon: 'Never' }); return [''] }
    if (lower.startsWith('enable-adaccount')) { const m = line.match(/(\S+)$/); os.modifyADUser(m[1].replace(/['"]/g, ''), { enabled: true }); return ['The command completed successfully.'] }
    if (lower.startsWith('disable-adaccount')) { const m = line.match(/(\S+)$/); os.modifyADUser(m[1].replace(/['"]/g, ''), { enabled: false }); return ['The command completed successfully.'] }
    if (lower.startsWith('unlock-adaccount')) { const m = line.match(/(\S+)$/); os.modifyADUser(m[1].replace(/['"]/g, ''), { locked: false }); return ['The command completed successfully.'] }
    if (lower.startsWith('get-adgroup')) {
      return tableFromObjects(os.adGroups, [{ h: 'Name', v: (r) => r.name }, { h: 'GroupScope', v: (r) => r.scope }, { h: 'GroupCategory', v: (r) => r.category }])
    }
    if (lower.startsWith('add-adgroupmember')) { const g = line.match(/-identity\s+["']?([^"']+?)["']?\s/i); const u = line.match(/-members\s+(\S+)/i); if (g && u) os.addGroupMember(u[1].replace(/['"]/g, ''), g[1]); return [''] }

    if (lower === 'get-netadapter' || lower.startsWith('get-netadapter')) {
      return tableFromObjects(os.adapters, [{ h: 'Name', v: (r) => r.name }, { h: 'InterfaceDescription', v: (r) => r.desc }, { h: 'Status', v: (r) => r.status === 'Connected' ? 'Up' : 'Disconnected' }, { h: 'LinkSpeed', v: (r) => r.speed }])
    }
    if (lower === 'get-netipaddress' || lower.startsWith('get-netipconfiguration')) {
      os.adapters.forEach((a) => out.push('', `InterfaceAlias : ${a.name}`, `IPv4Address    : ${a.ipv4}`, `IPv4Gateway    : ${a.gateway}`, `DNSServer      : ${a.dns.join(', ')}`))
      out.push('')
      return out
    }
    if (lower.startsWith('test-netconnection')) {
      const host = line.split(/\s+/)[1] || 'google.com'
      return ['', `ComputerName     : ${host}`, 'RemoteAddress    : 142.250.80.46', 'InterfaceAlias   : Ethernet0',
        'SourceAddress    : 192.168.10.50', 'PingSucceeded    : True', 'PingReplyDetails (RTT) : 14 ms', '']
    }
    if (lower.startsWith('resolve-dnsname')) {
      const host = line.split(/\s+/)[1] || 'server01.lab.local'
      return ['', 'Name                          Type   TTL   Section    IPAddress', '----                          ----   ---   -------    ---------', `${host.padEnd(29)} A      3600  Answer     192.168.10.50`, '']
    }
    if (lower === 'get-disk' || lower.startsWith('get-disk')) {
      return tableFromObjects(os.disks, [{ h: 'Number', v: (r) => r.id }, { h: 'PartitionStyle', v: (r) => r.style }, { h: 'OperationalStatus', v: (r) => r.status }, { h: 'HealthStatus', v: (r) => r.initialized ? 'Healthy' : 'Unknown' }, { h: 'Total Size', v: (r) => `${r.sizeGB} GB` }])
    }
    if (lower === 'get-volume' || lower.startsWith('get-volume')) {
      const vols = Object.entries(os.vfs.drives).filter(([, d]) => !d.noMedia)
      return tableFromObjects(vols, [
        { h: 'DriveLetter', v: ([l]) => l }, { h: 'FileSystemLabel', v: ([, d]) => d.label }, { h: 'FileSystem', v: ([, d]) => d.fs },
        { h: 'DriveType', v: () => 'Fixed' }, { h: 'HealthStatus', v: () => 'Healthy' },
        { h: 'SizeRemaining', v: ([, d]) => `${(d.totalGB - d.usedGB).toFixed(1)} GB` }, { h: 'Size', v: ([, d]) => `${d.totalGB} GB` },
      ])
    }
    if (lower.startsWith('initialize-disk')) { const m = line.match(/-number\s+(\d+)/i); const st = /mbr/i.test(line) ? 'MBR' : 'GPT'; if (m) os.initializeDisk(Number(m[1]), st); return [''] }
    if (lower.startsWith('new-partition')) {
      const m = line.match(/-disknumber\s+(\d+)/i)
      if (m) { const disk = os.disks.find((d) => d.id === Number(m[1])); const used = (os.vfs.drives ? Object.keys(os.vfs.drives) : []); let letter = 'F'; for (const L of 'FGHIJK') { if (!used.includes(L)) { letter = L; break } } os.createVolume(Number(m[1]), { letter, label: 'New Volume', fs: 'RAW', sizeGB: disk?.sizeGB || 100 }) }
      return ['', '   DiskPath: \\\\?\\scsi#disk...', '', 'PartitionNumber  DriveLetter Offset  Size  Type', '---------------  ----------- ------  ----  ----', '2                F           135266304  100 GB  Basic', '']
    }
    if (lower.startsWith('format-volume')) { return ['', 'DriveLetter FileSystemLabel FileSystem DriveType HealthStatus SizeRemaining   Size', '----------- --------------- ---------- --------- ------------ -------------   ----', 'F           NewVolume       NTFS       Fixed     Healthy      99.8 GB         100 GB', ''] }

    if (lower === 'get-hotfix') {
      return tableFromObjects(os.updates, [{ h: 'Source', v: () => 'SERVER01' }, { h: 'Description', v: (r) => r.type === 'Security' ? 'Security Update' : 'Update' }, { h: 'HotFixID', v: (r) => r.kb }, { h: 'InstalledOn', v: (r) => r.date }])
    }
    if (lower.startsWith('get-eventlog') || lower.startsWith('get-winevent')) {
      const logM = line.match(/-logname\s+(\S+)/i)
      const log = logM?.[1]?.replace(/['"]/g, '') || 'System'
      const evs = (os.events[log] || os.events.System).slice(0, 15)
      out.push('', '   Index Time          EntryType   Source                 EventID Message', '   ----- ----          ---------   ------                 ------- -------')
      evs.forEach((e) => out.push(`   ${String(e.recordId).slice(-5)} ${e.time.slice(5, 16)} ${(e.level).padEnd(11)} ${e.src.slice(0, 22).padEnd(22)} ${String(e.id).padEnd(7)} ${(e.msg || '').split('\n')[0].slice(0, 40)}`))
      out.push('')
      return out
    }
    if (lower.startsWith('get-computerinfo') || lower === 'systeminfo') {
      return ['', `WindowsProductName             : ${os.computer.edition}`, 'WindowsVersion                 : 2009',
        `OsHardwareAbstractionLayer     : 10.0.20348.2402`, `CsName                         : ${os.computer.name}`,
        `CsDomain                       : ${os.computer.domain}`, `CsManufacturer                 : VMware, Inc.`,
        `CsModel                        : VMware Virtual Platform`, `CsNumberOfLogicalProcessors    : ${os.computer.cores}`,
        `CsTotalPhysicalMemory          : ${os.computer.ramGB * 1024 * 1024 * 1024}`, `OsArchitecture                 : 64-bit`, '']
    }
    if (lower.startsWith('write-host') || lower.startsWith('echo ')) {
      const m = line.match(/(write-host|echo)\s+["']?([^"']*)/i)
      return [m?.[2] || '']
    }
    if (lower.startsWith('get-date')) return [new Date().toString()]
    if (lower.startsWith('import-module')) return ['']
    if (lower === 'get-module -listavailable' || lower.startsWith('get-module')) {
      return ['', '    Directory: C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\Modules', '',
        'ModuleType Version    Name', '---------- -------    ----', 'Manifest   1.0.1.0    ActiveDirectory', 'Manifest   2.0.0.0    DnsServer',
        'Manifest   2.0.0.0    DhcpServer', 'Manifest   2.0.0.0    Hyper-V', 'Manifest   2.0.0.0    Storage', '']
    }
    if (lower.startsWith('test-path')) return ['True']
    if (lower.startsWith('start-process')) { const m = line.match(/start-process\s+(\S+)/i); const app = (m?.[1] || '').toLowerCase(); if (app.includes('notepad')) os.openApp('Notepad', {}, { title: 'Untitled - Notepad' }); return [''] }

    // unknown
    return [`${line.split(' ')[0]} : The term '${line.split(' ')[0]}' is not recognized as the name of a cmdlet, function, script file, or operable program. Check the spelling of the name, or if a path was included, verify that the path is correct and try again.`, '__ERR__']
  }

  // ── CMD ──
  if (lower === 'ipconfig' || lower.startsWith('ipconfig')) {
    if (lower.includes('/flushdns')) return ['', 'Windows IP Configuration', '', 'Successfully flushed the DNS Resolver Cache.']
    if (lower.includes('/release')) return ['', 'Windows IP Configuration', '', 'No operation can be performed on Ethernet0 while it has its media disconnected.']
    if (lower.includes('/renew')) return ['', 'Windows IP Configuration', '']
    out.push('', 'Windows IP Configuration', '')
    os.adapters.forEach((a) => {
      out.push(`Ethernet adapter ${a.name}:`, '', `   Connection-specific DNS Suffix  . : lab.local`,
        `   IPv4 Address. . . . . . . . . . . : ${a.ipv4}`, `   Subnet Mask . . . . . . . . . . . : ${a.mask}`,
        `   Default Gateway . . . . . . . . . : ${a.gateway}`, '')
      if (lower.includes('/all')) out.splice(out.length - 1, 0, `   Physical Address. . . . . . . . . : ${a.mac}`, `   DHCP Enabled. . . . . . . . . . . : ${a.dhcp ? 'Yes' : 'No'}`, `   DNS Servers . . . . . . . . . . . : ${a.dns.join('\n                                       ')}`)
    })
    return out
  }
  if (lower === 'dir' || lower.startsWith('dir')) {
    const names = os.listDir(cwd) || []
    out.push('', ` Volume in drive ${cwd[0]} is ${os.vfs.drives[cwd[0]]?.label || ''}`, ` Directory of ${cwd}`, '')
    names.forEach((n) => {
      const full = normPath(cwd + '\\' + n); const dir = os.isDir(full); const meta = os.fileMeta(full)
      out.push(`01/16/2024  02:47 PM ${dir ? '   <DIR>          ' : String(meta?.size ?? 0).padStart(16) + ' '} ${n}`)
    })
    out.push('')
    return out
  }
  if (lower.startsWith('cd ') || lower.startsWith('chdir')) {
    const t = line.replace(/^(cd|chdir)\s+/i, '').trim()
    let np = t === '..' ? cwd.slice(0, cwd.lastIndexOf('\\')) || cwd.slice(0, 3) : (/^[A-Za-z]:/.test(t) ? t : normPath(cwd + '\\' + t))
    np = normPath(np)
    if (os.isDir(np)) { cwdRef.current = np; return [] }
    return ['The system cannot find the path specified.']
  }
  if (lower === 'tasklist') {
    out.push('', 'Image Name                     PID Session Name        Session#    Mem Usage', '========================= ======== ================ =========== ============')
    os.processes.slice(0, 22).forEach((p) => out.push(`${p.name.padEnd(25)} ${String(p.pid).padStart(8)} Services${' '.repeat(16)}0 ${(Math.round(p.mem * 1024).toLocaleString() + ' K').padStart(12)}`))
    return out
  }
  if (lower.startsWith('net user')) {
    if (lower.trim() === 'net user') { out.push('', 'User accounts for \\\\SERVER01', '', '-------------------------------------------------------------------------------', 'Administrator            DefaultAccount           Guest', os.adUsers.slice(1, 7).map((u) => u.sam).join('            '), 'The command completed successfully.', ''); return out }
  }
  if (lower === 'ver') return ['', 'Microsoft Windows [Version 10.0.20348.2402]']
  if (lower.startsWith('ping ')) {
    const host = line.split(/\s+/)[1]
    out.push('', `Pinging ${host} [192.168.10.50] with 32 bytes of data:`)
    for (let i = 0; i < 4; i++) out.push('Reply from 192.168.10.50: bytes=32 time<1ms TTL=128')
    out.push('', `Ping statistics for 192.168.10.50:`, '    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),', 'Approximate round trip times in milli-seconds:', '    Minimum = 0ms, Maximum = 1ms, Average = 0ms')
    return out
  }
  if (lower === 'sfc /scannow') return ['', 'Beginning system scan.  This process will take some time.', '', 'Verification 100% complete.', '', 'Windows Resource Protection did not find any integrity violations.']
  if (lower.startsWith('sc query')) return ['', 'SERVICE_NAME: ' + (line.split(/\s+/)[2] || 'wuauserv'), '        TYPE               : 20  WIN32_SHARE_PROCESS', '        STATE              : 4  RUNNING', '        WIN32_EXIT_CODE    : 0  (0x0)']
  if (lower.startsWith('gpupdate')) return ['Updating policy...', '', 'Computer Policy update has completed successfully.', 'User Policy update has completed successfully.', '']

  return [`'${line.split(' ')[0]}' is not recognized as an internal or external command,`, 'operable program or batch file.']
}

export default function Terminal({ win }) {
  const os = useOS()
  const shell = win.props?.shell || 'ps'
  const cwdRef = useRef(normPath(win.props?.cwd || 'C:\\Users\\Administrator'))
  const [, force] = useState(0)
  const banner = shell === 'ps'
    ? ['Windows PowerShell', 'Copyright (C) Microsoft Corporation. All rights reserved.', '', 'Install the latest PowerShell for new features and improvements! https://aka.ms/PSWindows', '']
    : ['Microsoft Windows [Version 10.0.20348.2402]', '(c) Microsoft Corporation. All rights reserved.', '']
  const [lines, setLines] = useState(banner.map((t) => ({ t })))
  const [input, setInput] = useState('')
  const [hist, setHist] = useState([])
  const [hp, setHp] = useState(-1)
  const bodyRef = useRef(null)
  const inputRef = useRef(null)

  const prompt = () => shell === 'ps' ? `PS ${cwdRef.current}> ` : `${cwdRef.current}>`

  useEffect(() => { bodyRef.current?.scrollTo(0, bodyRef.current.scrollHeight); inputRef.current?.focus() })

  const submit = () => {
    const cmd = input
    const echoed = [...lines, { t: prompt() + cmd, pr: true }]
    const result = runCommand(cmd, shell, os, cwdRef)
    if (result[0] === '__CLEAR__') { setLines([]); setInput(''); return }
    if (result[0] === '__EXIT__') { os.closeWindow(win.id); return }
    const isErr = result[result.length - 1] === '__ERR__'
    const clean = result.filter((r) => r !== '__ERR__')
    setLines([...echoed, ...clean.map((t) => ({ t, err: isErr }))])
    if (cmd.trim()) setHist([cmd, ...hist])
    setHp(-1); setInput(''); force((n) => n + 1)
  }

  const onKey = (e) => {
    if (e.key === 'Enter') submit()
    else if (e.key === 'ArrowUp') { e.preventDefault(); const n = Math.min(hp + 1, hist.length - 1); if (n >= 0) { setHp(n); setInput(hist[n]) } }
    else if (e.key === 'ArrowDown') { e.preventDefault(); const n = hp - 1; if (n < 0) { setHp(-1); setInput('') } else { setHp(n); setInput(hist[n]) } }
  }

  return (
    <div className={`winos-term ${shell === 'cmd' ? 'cmd' : ''}`} ref={bodyRef} onClick={() => inputRef.current?.focus()}>
      {lines.map((l, i) => <div key={i} className={l.err ? 'err' : l.pr ? 'pr' : ''}>{l.t || '\u00A0'}</div>)}
      <div style={{ display: 'flex' }}>
        <span className="pr">{prompt()}</span>
        <input ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKey} spellCheck={false} autoFocus />
      </div>
    </div>
  )
}
