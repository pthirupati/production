// EC2 SSH shell — delegates to the shared FixitLab Linux/Kubernetes/Windows
// simulation engines (vmware/linuxShell + windowsShell) while keeping a light
// VFS for the Instance Connect welcome banner (motd).
import { createVfs } from './vfs'
import { createEc2SimShell } from './ec2SimBridge'
import { resolveEc2Workload } from './ec2Workload'

export class Shell {
  constructor({ instance, store }) {
    this.store = store
    this.instance = instance
    this.os = instance.os
    this.hostname = `ip-${(instance.privateIp || '172.31.14.52').replace(/\./g, '-')}`
    this.privateIp = instance.privateIp || '172.31.14.52'
    this.publicIp = instance.publicIp || ''
    this.workload = resolveEc2Workload(instance)
    const { fs, home, user } = createVfs(this.os, this.hostname, this.privateIp, instance.sshUser)
    this.fs = fs
    this.user = user
    this.home = home
    this._onExit = null
    this._bridge = createEc2SimShell(instance, {
      store,
      user: instance.sshUser,
      onExit: () => this._onExit?.(),
    })
  }

  get history() {
    return this._bridge.history
  }

  set onExit(fn) {
    this._onExit = fn
  }

  prompt() {
    return this._bridge.prompt()
  }

  async run(rawLine, onWrite) {
    await this._bridge.run(rawLine, onWrite)
  }
}
