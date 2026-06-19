/** Simulated Windows Server guest for VMware console / SSH */

export function createWindowsShell(vm) {
  const hostname = vm?.hostname || vm?.name || 'WIN-GUEST'
  const cwd = { path: 'C:\\Users\\Administrator' }
  const history = []

  const prompt = () => `PS ${hostname}>`

  const run = (raw) => {
    const line = raw.trim()
    if (!line) return { lines: [''], prompt: prompt() }
    history.push(line)
    const lower = line.toLowerCase()
    const out = []

    if (lower === 'help') {
      out.push('Windows PowerShell simulated shell')
      out.push('Get-Service, Get-Process, ipconfig, ping, hostname, systeminfo, sfc /scannow, chkdsk')
    } else if (lower === 'clear' || lower === 'cls') {
      return { lines: [], clear: true, prompt: prompt() }
    } else if (lower === 'exit') {
      return { lines: [''], exit: true, prompt: prompt() }
    } else if (lower === 'hostname') {
      out.push(hostname)
    } else if (lower.startsWith('get-service')) {
      out.push('Status   Name               DisplayName', '------   ----               -----------', 'Running  W32Time            Windows Time', 'Running  TermService        Remote Desktop Services', 'Stopped  Spooler            Print Spooler')
    } else if (lower.startsWith('get-process')) {
      out.push('Handles  NPM(K)    PM(K) WS(K) CPU(s)   Id ProcessName', '    120      12     3456  8901   0.12 1234 svchost', '     45       5     1234  4567   0.01 5678 csrss')
    } else if (lower.startsWith('ipconfig')) {
      out.push(`Windows IP Configuration`, `Ethernet adapter Ethernet0:`, `   IPv4 Address. . . . . . . . . . . : ${vm?.ip || '10.20.30.50'}`, `   Subnet Mask . . . . . . . . . . . : 255.255.255.0`, `   Default Gateway . . . . . . . . . : 10.20.30.1`)
    } else if (lower.startsWith('ping')) {
      const host = line.split(/\s+/)[1] || '127.0.0.1'
      out.push(`Pinging ${host} with 32 bytes of data:`, `Reply from ${host}: bytes=32 time<1ms TTL=128`, `Ping statistics for ${host}:`, `    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss)`)
    } else if (lower.startsWith('systeminfo')) {
      out.push(`Host Name:                 ${hostname}`, 'OS Name:                   Microsoft Windows Server 2019 Standard', 'System Boot Time:          6/5/2026, 8:00:00 AM', 'Total Physical Memory:     4,096 MB')
    } else if (lower.includes('sfc')) {
      out.push('Beginning system scan...', 'Verification 100% complete.', 'Windows Resource Protection did not find any integrity violations.')
    } else if (lower.startsWith('chkdsk')) {
      out.push('The type of the file system is NTFS.', 'Windows has scanned the file system and found no problems.')
    } else if (lower.startsWith('whoami')) {
      out.push(`${hostname}\\Administrator`)
    } else if (lower.startsWith('get-eventlog')) {
      out.push('Index Time          EntryType   Source', '----- ----          ---------   ------', '  123 6/5/2026 8:01  Information Service Control Manager')
    } else if (lower.startsWith('restart-computer') || lower.startsWith('shutdown')) {
      out.push('Simulated reboot initiated...')
    } else {
      out.push(`'${line.split(/\s+/)[0]}' is not recognized as an internal or external command,`, 'operable program or batch file.')
    }

    return { lines: out, prompt: prompt() }
  }

  return { run, prompt, history }
}

export const WIN_BOOT_SEQUENCE = [
  'SeaBIOS (version fixitlab-1.0)',
  'Booting from Hard Disk...',
  'Windows Boot Manager',
  'Loading Windows\\system32\\winload.exe',
  'Starting Windows Server 2019',
  'Applying computer settings...',
  'Services started.',
]

export const WIN_LOGIN_HINT = 'Hint: Administrator / P@ssw0rd123'
