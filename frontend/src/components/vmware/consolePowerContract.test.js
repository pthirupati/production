import { describe, it, expect } from 'vitest'
import { createLinuxShell } from './linuxShell.js'

// Unified server model (#17): VmwareConsole.handleResult keys off result.reboot /
// result.poweroff to (a) drive its own boot/off animation AND (b) emit
// onGuestAction({action:'reboot'|'power_off'}) so the VMware VM tile follows the
// guest OS. These tests lock the shell → result contract that wiring depends on;
// if linuxShell ever stops flagging reboot/poweroff, the VM tile would silently
// stop tracking console power changes.
describe('VmwareConsole power contract', () => {
  const vm = { id: 'vm-web', name: 'web-prod-01', hostname: 'web-prod-01',
               ip: '10.20.30.41', cpu: 4, memory_mb: 8192,
               guest_os: 'Red Hat Enterprise Linux 8 (64-bit)' }

  const run = (line) => createLinuxShell(vm).run(line)

  it('reboot flags result.reboot', () => {
    expect(run('reboot').reboot).toBeTruthy()
  })

  it('poweroff flags result.poweroff', () => {
    expect(run('poweroff').poweroff).toBe(true)
  })

  it('shutdown -r reboots, shutdown -h powers off', () => {
    expect(run('shutdown -r now').reboot).toBeTruthy()
    expect(run('shutdown -h now').poweroff).toBe(true)
  })

  it('systemctl reboot / poweroff flag the same result fields', () => {
    expect(run('systemctl reboot').reboot).toBeTruthy()
    expect(run('systemctl poweroff').poweroff).toBe(true)
  })
})
