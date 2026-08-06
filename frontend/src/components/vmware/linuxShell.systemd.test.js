import { describe, it, expect, beforeEach } from 'vitest'
import { createLinuxShell, purgeGuestStateForLab } from './linuxShell.js'

let seq = 0

// Each test needs a pristine guest: shared VFS/service state is memoised per
// (labSessionId, vm) key, so reuse would leak a previous test's edits.
function mkShell() {
  const labSessionId = `test-systemd-${++seq}`
  purgeGuestStateForLab(labSessionId)
  return createLinuxShell({ name: 'rhel-server-01', guest_os: 'rhel9', ip: '10.20.30.41' }, { labSessionId })
}

function out(sh, cmd) {
  return sh.run(cmd).lines.join('\n')
}

describe('linuxShell nginx -t config gate', () => {
  let sh
  beforeEach(() => { sh = mkShell() })

  it('accepts the seeded config — labs must not start pre-broken', () => {
    expect(out(sh, 'nginx -t')).toContain('test is successful')
    out(sh, 'systemctl restart nginx')
    expect(out(sh, 'systemctl is-active nginx')).toBe('active')
  })

  it('rejects an unknown directive', () => {
    sh.saveFile('/etc/nginx/conf.d/default.conf', 'server {\n    listn 80;\n}\n')
    expect(out(sh, 'nginx -t')).toContain('unknown directive "listn"')
    out(sh, 'systemctl restart nginx')
    expect(out(sh, 'systemctl is-active nginx')).toBe('failed')
  })

  it('rejects an unclosed brace', () => {
    sh.saveFile('/etc/nginx/conf.d/default.conf', 'server {\n    listen 80;\n')
    const t = out(sh, 'nginx -t')
    expect(t).toContain('[emerg]')
    expect(t).toContain('test failed')
    out(sh, 'systemctl restart nginx')
    expect(out(sh, 'systemctl is-active nginx')).toBe('failed')
  })

  it('rejects a directive missing its semicolon', () => {
    sh.saveFile('/etc/nginx/conf.d/default.conf', 'server {\n    listen 80\n    server_name _;\n}\n')
    expect(out(sh, 'nginx -t')).toContain('test failed')
    out(sh, 'systemctl start nginx')
    expect(out(sh, 'systemctl is-active nginx')).toBe('failed')
  })

  it('rejects a stray closing brace', () => {
    sh.saveFile('/etc/nginx/conf.d/default.conf', 'server {\n    listen 80;\n}\n}\n')
    expect(out(sh, 'nginx -t')).toContain('test failed')
  })

  it('rejects a missing main config', () => {
    out(sh, 'rm -f /etc/nginx/nginx.conf')
    expect(out(sh, 'nginx -t')).toContain('No such file or directory')
    out(sh, 'systemctl restart nginx')
    expect(out(sh, 'systemctl is-active nginx')).toBe('failed')
  })

  it('gates every activating verb, not just start', () => {
    sh.saveFile('/etc/nginx/conf.d/default.conf', 'server {\n    listn 80;\n}\n')
    for (const verb of ['start', 'restart', 'enable --now']) {
      out(sh, 'systemctl stop nginx')
      out(sh, `systemctl ${verb} nginx`)
      expect(out(sh, 'systemctl is-active nginx'), verb).toBe('failed')
    }
  })

  it('recovers once the config is fixed', () => {
    sh.saveFile('/etc/nginx/conf.d/default.conf', 'server {\n    listn 80;\n}\n')
    out(sh, 'systemctl restart nginx')
    expect(out(sh, 'systemctl is-active nginx')).toBe('failed')
    sh.saveFile('/etc/nginx/conf.d/default.conf', 'server {\n    listen 80;\n}\n')
    out(sh, 'systemctl restart nginx')
    expect(out(sh, 'systemctl is-active nginx')).toBe('active')
  })

  it('does not gate unrelated services on nginx config', () => {
    sh.saveFile('/etc/nginx/conf.d/default.conf', 'server {\n    listn 80;\n}\n')
    out(sh, 'systemctl restart sshd')
    expect(out(sh, 'systemctl is-active sshd')).toBe('active')
  })
})

describe('linuxShell systemctl cat/show read the unit file', () => {
  let sh
  beforeEach(() => { sh = mkShell() })

  it('cat reflects the on-disk unit, including edits', () => {
    const before = out(sh, 'systemctl cat app')
    expect(before).toContain('ExecStart=/usr/bin/node /opt/app/server.js')
    sh.saveFile('/etc/systemd/system/app.service',
      '[Unit]\nDescription=FixitLab API service\n\n[Service]\nExecStart=/usr/bin/node /opt/app/other.js\n\n[Install]\nWantedBy=multi-user.target\n')
    const after = out(sh, 'systemctl cat app')
    expect(after).toContain('ExecStart=/usr/bin/node /opt/app/other.js')
    expect(after).not.toContain('server.js')
  })

  it('cat names the real path it read', () => {
    expect(out(sh, 'systemctl cat app')).toContain('# /etc/systemd/system/app.service')
    expect(out(sh, 'systemctl cat sshd')).toContain('# /usr/lib/systemd/system/sshd.service')
  })

  it('cat reports a missing unit rather than fabricating one', () => {
    expect(out(sh, 'systemctl cat nosuch')).toContain('No files found for nosuch.service')
  })

  it('show exposes unit properties parsed from the file', () => {
    const s = out(sh, 'systemctl show app')
    expect(s).toContain('Id=app.service')
    expect(s).toContain('ExecStart=/usr/bin/node /opt/app/server.js')
    expect(s).toContain('WantedBy=multi-user.target')
  })

  it('show -p returns just the requested property', () => {
    expect(out(sh, 'systemctl show -p ActiveState app').trim()).toBe('ActiveState=active')
  })

  it('enable fails closed on a unit with no [Install] section', () => {
    sh.saveFile('/etc/systemd/system/app.service',
      '[Unit]\nDescription=FixitLab API service\n\n[Service]\nExecStart=/usr/bin/node /opt/app/server.js\n')
    out(sh, 'systemctl disable app')
    const r = out(sh, 'systemctl enable app')
    expect(r).toContain('no [Install] section')
    // The refused enable must not flip state — that is the fail-closed part.
    expect(out(sh, 'systemctl is-enabled app')).toBe('disabled')
  })

  it('enable reports the WantedBy target the unit file actually declares', () => {
    expect(out(sh, 'systemctl enable app')).toContain('multi-user.target.wants/app.service')
    sh.saveFile('/etc/systemd/system/app.service',
      '[Unit]\nDescription=FixitLab API service\n\n[Service]\nExecStart=/usr/bin/node /opt/app/server.js\n\n[Install]\nWantedBy=graphical.target\n')
    expect(out(sh, 'systemctl enable app')).toContain('graphical.target.wants/app.service')
  })

  it('a malformed unit fails to load and must not report active', () => {
    sh.saveFile('/etc/systemd/system/app.service', '[Unit\nDescription=broken\n')
    out(sh, 'systemctl stop app')
    const r = out(sh, 'systemctl start app')
    expect(r).toContain('Bad message')
    expect(out(sh, 'systemctl is-active app')).not.toBe('active')
  })
})

describe('linuxShell journalctl -u derives messages from state', () => {
  let sh
  beforeEach(() => { sh = mkShell() })

  it('does not cite an nginx bind error for a failed non-nginx unit', () => {
    sh.saveFile('/etc/systemd/system/app.service', '[Unit\nDescription=broken\n')
    out(sh, 'systemctl restart app')
    const j = out(sh, 'journalctl -u app')
    expect(j).not.toContain('nginx')
    expect(j).not.toContain('Address already in use')
  })

  it('keeps [emerg]/FAILURE tokens on a failed nginx so hints still match', () => {
    sh.saveFile('/etc/nginx/conf.d/default.conf', 'server {\n    listn 80;\n}\n')
    out(sh, 'systemctl restart nginx')
    const j = out(sh, 'journalctl -u nginx')
    expect(j).toContain('[emerg]')
    expect(j).toContain('FAILURE')
  })

  it('reports the actual nginx config error, not a canned port conflict', () => {
    sh.saveFile('/etc/nginx/conf.d/default.conf', 'server {\n    listn 80;\n}\n')
    out(sh, 'systemctl restart nginx')
    const j = out(sh, 'journalctl -u nginx')
    expect(j).toContain('unknown directive "listn"')
    expect(j).not.toContain('Address already in use')
  })

  it('a healthy unit logs a start, not a failure', () => {
    const j = out(sh, 'journalctl -u sshd')
    expect(j).toContain('Started OpenSSH server daemon')
    expect(j).not.toContain('[emerg]')
  })
})
