import { create } from 'zustand'
import {
  COMPUTER, SEED_SERVICES, SEED_PROCESSES, SEED_ADAPTERS, SEED_DISKS, SEED_DEVICES,
  SEED_AD_USERS, SEED_AD_GROUPS, SEED_OU_TREE, SEED_PROGRAMS, SEED_UPDATES,
  SEED_TASKS, SEED_STARTUP, SEED_ROLES,
} from './data'
import { SEED_VFS } from './vfs'
import { SEED_EVENTS } from './events'
import { SEED_REGISTRY } from './registry'

let zCounter = 100
let winId = 0

const clone = (x) => JSON.parse(JSON.stringify(x))

// Normalize a Windows path (collapse trailing slash except for drive root).
export function normPath(p) {
  if (!p) return p
  let s = p.replace(/\//g, '\\')
  if (/^[A-Za-z]:$/.test(s)) s += '\\'
  if (s.length > 3 && s.endsWith('\\')) s = s.slice(0, -1)
  return s
}

export const useOS = create((set, get) => ({
  // ── identity ──
  computer: COMPUTER,
  currentUser: 'Administrator',
  bootTime: Date.now() - (2 * 86400000 + 14 * 3600000 + 23 * 60000),
  backendSnapshotKey: '',

  // ── window manager ──
  windows: [],
  activeWindowId: null,

  openApp: (app, props = {}, opts = {}) => {
    const id = `w${++winId}`
    const offset = (get().windows.length % 6) * 26
    const win = {
      id, app,
      title: opts.title || app,
      x: opts.x ?? 120 + offset,
      y: opts.y ?? 70 + offset,
      width: opts.width ?? 900,
      height: opts.height ?? 600,
      minimized: false,
      maximized: opts.maximized ?? false,
      prev: null,
      zIndex: ++zCounter,
      props,
    }
    set((s) => ({ windows: [...s.windows, win], activeWindowId: id }))
    return id
  },
  closeWindow: (id) => set((s) => ({
    windows: s.windows.filter((w) => w.id !== id),
    activeWindowId: s.activeWindowId === id ? (s.windows.filter((w) => w.id !== id).slice(-1)[0]?.id || null) : s.activeWindowId,
  })),
  focusWindow: (id) => set((s) => ({
    activeWindowId: id,
    windows: s.windows.map((w) => w.id === id ? { ...w, zIndex: ++zCounter, minimized: false } : w),
  })),
  minimizeWindow: (id) => set((s) => ({
    windows: s.windows.map((w) => w.id === id ? { ...w, minimized: true } : w),
    activeWindowId: s.activeWindowId === id ? null : s.activeWindowId,
  })),
  toggleMaximize: (id) => set((s) => ({
    windows: s.windows.map((w) => {
      if (w.id !== id) return w
      if (w.maximized) return { ...w, maximized: false, ...(w.prev || {}), prev: null }
      return { ...w, maximized: true, prev: { x: w.x, y: w.y, width: w.width, height: w.height } }
    }),
  })),
  setWindowBounds: (id, bounds) => set((s) => ({
    windows: s.windows.map((w) => w.id === id ? { ...w, ...bounds } : w),
  })),
  setWindowTitle: (id, title) => set((s) => ({
    windows: s.windows.map((w) => w.id === id ? { ...w, title } : w),
  })),
  snapWindow: (id, side) => set((s) => {
    const W = window.innerWidth, H = window.innerHeight - 40
    const half = Math.floor(W / 2)
    const b = side === 'left' ? { x: 0, y: 0, width: half, height: H }
      : side === 'right' ? { x: half, y: 0, width: W - half, height: H }
        : { x: 0, y: 0, width: W, height: H }
    return { windows: s.windows.map((w) => w.id === id ? { ...w, maximized: false, ...b } : w) }
  }),

  // ── VFS ──
  vfs: clone(SEED_VFS),
  listDir: (path) => {
    const p = normPath(path)
    return get().vfs.dirs[p] || null
  },
  isDir: (path) => get().vfs.dirs[normPath(path)] !== undefined,
  fileMeta: (path) => get().vfs.files[normPath(path)] || null,
  readFile: (path) => (get().vfs.files[normPath(path)] || {}).content ?? null,
  writeFile: (path, content) => set((s) => {
    const p = normPath(path)
    const vfs = clone(s.vfs)
    const parent = p.slice(0, p.lastIndexOf('\\')) || p.slice(0, 3)
    const name = p.slice(p.lastIndexOf('\\') + 1)
    const stamp = new Date().toISOString().slice(0, 19).replace('T', ' ')
    vfs.files[p] = { content, size: content.length, created: vfs.files[p]?.created || stamp, modified: stamp, accessed: stamp, attrs: vfs.files[p]?.attrs || [] }
    if (vfs.dirs[parent] && !vfs.dirs[parent].includes(name)) vfs.dirs[parent] = [...vfs.dirs[parent], name]
    return { vfs }
  }),
  createDirectory: (path) => set((s) => {
    const p = normPath(path)
    if (s.vfs.dirs[p]) return {}
    const vfs = clone(s.vfs)
    const parent = p.slice(0, p.lastIndexOf('\\')) || p.slice(0, 3)
    const name = p.slice(p.lastIndexOf('\\') + 1)
    vfs.dirs[p] = []
    if (vfs.dirs[parent] && !vfs.dirs[parent].includes(name)) vfs.dirs[parent] = [...vfs.dirs[parent], name]
    return { vfs }
  }),
  deleteItem: (path) => set((s) => {
    const p = normPath(path)
    const vfs = clone(s.vfs)
    const parent = p.slice(0, p.lastIndexOf('\\')) || p.slice(0, 3)
    const name = p.slice(p.lastIndexOf('\\') + 1)
    delete vfs.files[p]
    delete vfs.dirs[p]
    Object.keys(vfs.dirs).forEach((k) => { if (k.startsWith(p + '\\')) delete vfs.dirs[k] })
    Object.keys(vfs.files).forEach((k) => { if (k.startsWith(p + '\\')) delete vfs.files[k] })
    if (vfs.dirs[parent]) vfs.dirs[parent] = vfs.dirs[parent].filter((n) => n !== name)
    return { vfs }
  }),
  renameItem: (path, newName) => set((s) => {
    const p = normPath(path)
    const vfs = clone(s.vfs)
    const parent = p.slice(0, p.lastIndexOf('\\')) || p.slice(0, 3)
    const oldName = p.slice(p.lastIndexOf('\\') + 1)
    const np = normPath(parent + '\\' + newName)
    if (vfs.files[p]) { vfs.files[np] = vfs.files[p]; delete vfs.files[p] }
    if (vfs.dirs[p]) { vfs.dirs[np] = vfs.dirs[p]; delete vfs.dirs[p] }
    if (vfs.dirs[parent]) vfs.dirs[parent] = vfs.dirs[parent].map((n) => n === oldName ? newName : n)
    return { vfs }
  }),

  // ── disks ──
  disks: clone(SEED_DISKS),
  initializeDisk: (diskId, style) => set((s) => ({
    disks: s.disks.map((d) => d.id === diskId ? { ...d, initialized: true, style, status: 'Online' } : d),
  })),
  createVolume: (diskId, { letter, label, fs, sizeGB }) => set((s) => {
    const disks = clone(s.disks)
    const disk = disks.find((d) => d.id === diskId)
    if (!disk) return {}
    disk.partitions.push({ type: 'primary', letter, label, sizeGB, fs, status: 'Healthy (Primary Partition)' })
    const vfs = clone(s.vfs)
    vfs.drives[letter] = { label, fs, totalGB: sizeGB, usedGB: Math.round(sizeGB * 0.0008 * 100) / 100, type: 'local', system: false }
    vfs.dirs[`${letter}:\\`] = ['$RECYCLE.BIN', 'System Volume Information']
    vfs.dirs[`${letter}:\\$RECYCLE.BIN`] = []
    vfs.dirs[`${letter}:\\System Volume Information`] = []
    return { disks, vfs }
  }),

  // ── services ──
  services: clone(SEED_SERVICES),
  setService: (name, patch) => set((s) => ({
    services: s.services.map((sv) => sv.name === name ? { ...sv, ...patch } : sv),
  })),
  startService: (name) => { get().setService(name, { status: 'Running' }); get().logEvent('System', { id: 7036, level: 'Information', src: 'Service Control Manager', msg: `The ${name} service entered the running state.` }) },
  stopService: (name) => { get().setService(name, { status: 'Stopped' }); get().logEvent('System', { id: 7036, level: 'Information', src: 'Service Control Manager', msg: `The ${name} service entered the stopped state.` }) },

  // ── processes ──
  processes: clone(SEED_PROCESSES),
  endProcess: (pid) => set((s) => ({ processes: s.processes.filter((p) => p.pid !== pid) })),
  setProcessPriority: (pid, priority) => set((s) => ({ processes: s.processes.map((p) => p.pid === pid ? { ...p, priority } : p) })),

  // ── network ──
  adapters: clone(SEED_ADAPTERS),
  setAdapter: (id, patch) => set((s) => ({ adapters: s.adapters.map((a) => a.id === id ? { ...a, ...patch } : a) })),

  // ── events ──
  events: clone(SEED_EVENTS),
  logEvent: (log, ev) => set((s) => {
    const events = { ...s.events }
    const stamp = new Date().toISOString().slice(0, 19).replace('T', ' ')
    events[log] = [{ ...ev, log, time: stamp, recordId: 200000 + Math.floor(Math.random() * 1000), computer: 'SERVER01.lab.local', kw: ev.kw || 'Classic', task: ev.task || 'None' }, ...(events[log] || [])]
    return { events }
  }),
  clearLog: (log) => set((s) => ({ events: { ...s.events, [log]: [] } })),

  // ── registry ──
  registry: clone(SEED_REGISTRY),
  regSetValue: (pathArr, name, type, data) => set((s) => {
    const reg = clone(s.registry)
    let node = reg
    for (const k of pathArr) { node = node[k] = node[k] || { __values: [] } }
    node.__values = node.__values || []
    const ex = node.__values.find((x) => x.name === name)
    if (ex) { ex.type = type; ex.data = data } else node.__values.push({ name, type, data })
    return { registry: reg }
  }),
  regNewKey: (pathArr, name) => set((s) => {
    const reg = clone(s.registry)
    let node = reg
    for (const k of pathArr) { node = node[k] = node[k] || { __values: [] } }
    node[name] = node[name] || { __values: [] }
    return { registry: reg }
  }),
  regDeleteValue: (pathArr, name) => set((s) => {
    const reg = clone(s.registry)
    let node = reg
    for (const k of pathArr) { node = node?.[k] }
    if (node?.__values) node.__values = node.__values.filter((x) => x.name !== name)
    return { registry: reg }
  }),

  // ── Active Directory ──
  adUsers: clone(SEED_AD_USERS),
  adGroups: clone(SEED_AD_GROUPS),
  ouTree: clone(SEED_OU_TREE),
  createADUser: (user) => set((s) => ({ adUsers: [...s.adUsers, user] })),
  modifyADUser: (sam, changes) => set((s) => ({ adUsers: s.adUsers.map((u) => u.sam === sam ? { ...u, ...changes } : u) })),
  deleteADUser: (sam) => set((s) => ({ adUsers: s.adUsers.filter((u) => u.sam !== sam) })),
  addGroupMember: (sam, group) => set((s) => ({ adUsers: s.adUsers.map((u) => u.sam === sam && !u.groups.includes(group) ? { ...u, groups: [...u.groups, group] } : u) })),
  removeGroupMember: (sam, group) => set((s) => ({ adUsers: s.adUsers.map((u) => u.sam === sam ? { ...u, groups: u.groups.filter((g) => g !== group) } : u) })),

  // ── static reference data ──
  devices: clone(SEED_DEVICES),
  programs: clone(SEED_PROGRAMS),
  updates: clone(SEED_UPDATES),
  scheduledTasks: clone(SEED_TASKS),
  startupItems: clone(SEED_STARTUP),
  roles: clone(SEED_ROLES),
  hydrateFromBackend: (snapshot) => set((s) => {
    if (!snapshot) return {}
    const snapshotKey = JSON.stringify({
      computer_name: snapshot.computer_name,
      domain: snapshot.domain,
      roles: snapshot.roles,
      services: snapshot.services,
      updates: snapshot.updates,
      storage: snapshot.storage,
      ad: snapshot.ad,
    })
    if (s.backendSnapshotKey === snapshotKey) return {}

    const serviceStatus = (v) => String(v || '').toLowerCase() === 'running' ? 'Running' : 'Stopped'
    const startup = (v) => {
      const raw = String(v || '').toLowerCase()
      if (raw.includes('disabled')) return 'Disabled'
      if (raw.includes('auto') && raw.includes('delayed')) return 'Automatic (Delayed)'
      if (raw.includes('auto')) return 'Automatic'
      return 'Manual'
    }

    const computerName = snapshot.computer_name || s.computer.name
    const domainName = snapshot.domain?.joined ? snapshot.domain?.name : snapshot.domain?.workgroup
    const computer = {
      ...s.computer,
      name: computerName,
      fqdn: snapshot.domain?.joined ? `${computerName}.${snapshot.domain?.name}` : computerName,
      domain: domainName || s.computer.domain,
      workgroup: snapshot.domain?.workgroup || s.computer.workgroup,
      edition: snapshot.os || s.computer.edition,
    }

    const backendRoles = snapshot.roles || []
    const roles = s.roles.map((role) => {
      const match = backendRoles.find((r) => r.id === role.id || r.name === role.name)
      return match ? { ...role, installed: Boolean(match.installed) } : role
    })

    const backendServices = snapshot.services || []
    const seenServices = new Set()
    const services = s.services.map((svc) => {
      const match = backendServices.find((b) => (
        b.name?.toLowerCase() === svc.name.toLowerCase()
        || b.display?.toLowerCase() === svc.display.toLowerCase()
      ))
      if (!match) return svc
      seenServices.add(match.name)
      return {
        ...svc,
        name: match.name || svc.name,
        display: match.display || svc.display,
        status: serviceStatus(match.status),
        startup: startup(match.startup),
      }
    })
    backendServices.forEach((svc) => {
      if (!seenServices.has(svc.name)) {
        services.push({
          name: svc.name,
          display: svc.display || svc.name,
          status: serviceStatus(svc.status),
          startup: startup(svc.startup),
          logon: 'Local System',
          desc: '',
        })
      }
    })

    const updates = (snapshot.updates || s.updates).map((u) => ({
      date: u.installed_at || u.date || '2024-01-17',
      kb: u.kb,
      title: u.title,
      status: u.status === 'installed'
        ? 'Successfully installed'
        : u.status === 'failed'
          ? `Failed (${u.error_code || '0x80240022'})`
          : u.status === 'downloading'
            ? 'Downloading'
            : 'Pending install',
      type: u.severity || u.type || 'Quality',
    }))

    const disks = (snapshot.storage?.disks || []).length
      ? snapshot.storage.disks.map((d) => ({
        id: d.number ?? (Number(String(d.id || '').replace(/\D/g, '')) || 0),
        model: d.model || 'VMware Virtual disk SCSI Disk Device',
        sizeGB: d.size_gb || d.sizeGB || 80,
        initialized: (d.partition_style || d.style || 'RAW') !== 'RAW',
        style: d.partition_style || d.style || 'RAW',
        status: d.status || 'Online',
        bus: d.bus || 'SCSI',
        system: (d.number ?? 0) === 0,
        partitions: (snapshot.storage?.volumes || [])
          .filter((v) => v.disk_id === d.id || v.disk_id === `disk${d.number}` || (d.number ?? 0) === 0)
          .map((v) => ({
            type: 'primary',
            letter: String(v.letter || '').replace(':', ''),
            label: v.label || 'Volume',
            sizeGB: v.size_gb || 0,
            fs: v.fs || 'NTFS',
            status: `Healthy (${v.health || 'Primary Partition'})`,
          })),
      }))
      : s.disks

    const vfs = clone(s.vfs)
    ;(snapshot.storage?.volumes || []).forEach((v) => {
      const letter = String(v.letter || '').replace(':', '')
      if (!letter) return
      vfs.drives[letter] = {
        ...(vfs.drives[letter] || {}),
        label: v.label || vfs.drives[letter]?.label || 'Volume',
        fs: v.fs || vfs.drives[letter]?.fs || 'NTFS',
        totalGB: v.size_gb || vfs.drives[letter]?.totalGB || 0,
        usedGB: Math.max(0, (v.size_gb || 0) - (v.free_gb || 0)),
        type: 'local',
        system: letter === 'C',
      }
      vfs.dirs[`${letter}:\\`] = vfs.dirs[`${letter}:\\`] || ['$RECYCLE.BIN', 'System Volume Information']
    })

    const adUsers = snapshot.ad?.users
      ? snapshot.ad.users.map((u) => ({
        sam: u.name,
        display: u.display || u.name,
        first: (u.display || u.name).split(' ')[0] || '',
        last: (u.display || '').split(' ').slice(1).join(' '),
        upn: `${u.name}@${snapshot.domain?.name || 'lab.local'}`,
        email: `${u.name}@${snapshot.domain?.name || 'lab.local'}`,
        dept: '',
        title: '',
        ou: `CN=${u.ou || 'Users'},DC=${String(snapshot.domain?.name || 'lab.local').replace(/\./g, ',DC=')}`,
        enabled: Boolean(u.enabled),
        locked: Boolean(u.locked),
        groups: u.groups || [u.group || 'Domain Users'],
        phone: '',
        office: '',
        company: '',
        manager: '',
        employeeId: '',
        pwLastSet: u.must_change_pw ? 'Must change at next logon' : '2024-01-17',
        lastLogon: 'Never',
      }))
      : s.adUsers

    return {
      backendSnapshotKey: snapshotKey,
      computer,
      currentUser: String(snapshot.session?.current_user || s.currentUser).split('\\').pop(),
      roles,
      services,
      updates,
      disks,
      vfs,
      adUsers,
    }
  }),
  setDevice: (cls, name, patch) => set((s) => ({
    devices: s.devices.map((c) => c.cls !== cls ? c : { ...c, items: c.items.map((it) => it.name === name ? { ...it, ...patch } : it) }),
  })),
  uninstallProgram: (name) => set((s) => ({ programs: s.programs.filter((p) => p.name !== name) })),
  setRoleInstalled: (id, installed) => set((s) => ({ roles: s.roles.map((r) => r.id === id ? { ...r, installed } : r) })),
  toggleStartup: (name) => set((s) => ({ startupItems: s.startupItems.map((i) => i.name === name ? { ...i, enabled: !i.enabled } : i) })),

  // ── clipboard ──
  clipboard: null,
  setClipboard: (cb) => set({ clipboard: cb }),

  // ── desktop / shell UI state ──
  startOpen: false,
  setStartOpen: (v) => set({ startOpen: typeof v === 'function' ? v(get().startOpen) : v }),
}))
