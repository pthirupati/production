import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createLinuxShell } from '../vmware/linuxShell'

let tabCounter = 0

function nextTabId() {
  tabCounter += 1
  return `bash-${tabCounter}`
}

const TAB_LABELS = ['bash-1', 'bash-2', 'bash-3', 'bash-4', 'bash-5', 'bash-6']

/**
 * Manages multiple independent shell sessions per VM with a shared VFS (via vm.id).
 * Returns shells keyed by tab id; editor tabs (vim/htop) are virtual labels only.
 */
export function useLinuxTerminalTabs(vm, { enabled = true, initialTabs = 1 } = {}) {
  const vmKey = vm?.id || vm?.name || 'guest'
  const hwSig = [
    vm?.guest_disk_hidden,
    vm?.guest_disk_visible,
    vm?.guest_nic_pending,
    vm?.guest_pending_disks?.length || 0,
    vm?.guest_pending_nics?.length || 0,
    vm?.disks?.length || 0,
    vm?.nics?.length || 0,
  ].join('|')
  const [tabs, setTabs] = useState(() => {
    if (!enabled) return []
    const n = Math.max(1, Math.min(initialTabs, TAB_LABELS.length))
    return Array.from({ length: n }, (_, i) => {
      const id = nextTabId()
      return { id, label: TAB_LABELS[i] || `bash-${i + 1}`, kind: 'shell' }
    })
  })
  const [activeId, setActiveId] = useState(() => tabs[0]?.id)
  const shellsRef = useRef(new Map())

  const getShell = useCallback((tabId) => {
    if (!shellsRef.current.has(tabId)) {
      shellsRef.current.set(tabId, createLinuxShell(vm, { sessionId: tabId }))
    }
    return shellsRef.current.get(tabId)
  }, [vm, vmKey])

  // Drop cached shells when VM identity or hot-add hardware flags change
  useEffect(() => {
    shellsRef.current = new Map()
  }, [vmKey, hwSig])

  const activeShell = useMemo(() => {
    if (!enabled || !activeId) return null
    return getShell(activeId)
  }, [enabled, activeId, getShell])

  const addTab = useCallback((kind = 'shell') => {
    setTabs((prev) => {
      if (prev.length >= TAB_LABELS.length) return prev
      const id = nextTabId()
      const label = kind === 'vim'
        ? 'vim'
        : kind === 'htop'
          ? 'htop'
          : TAB_LABELS[prev.length] || `bash-${prev.length + 1}`
      const next = [...prev, { id, label, kind }]
      setActiveId(id)
      return next
    })
  }, [])

  const closeTab = useCallback((tabId) => {
    setTabs((prev) => {
      if (prev.length <= 1) return prev
      const idx = prev.findIndex((t) => t.id === tabId)
      if (idx < 0) return prev
      shellsRef.current.delete(tabId)
      tabUiRef.current.delete(tabId)
      const next = prev.filter((t) => t.id !== tabId)
      setActiveId((cur) => (cur === tabId ? next[Math.max(0, idx - 1)]?.id : cur))
      return next
    })
  }, [])

  const renameTab = useCallback((tabId, label) => {
    setTabs((prev) => prev.map((t) => (t.id === tabId ? { ...t, label } : t)))
  }, [])

  const [status, setStatus] = useState(null)
  const tabUiRef = useRef(new Map())

  const persistTabUi = useCallback((tabId, ui) => {
    if (tabId) tabUiRef.current.set(tabId, ui)
  }, [])

  const getTabUi = useCallback((tabId) => tabUiRef.current.get(tabId) || null, [])

  useEffect(() => {
    if (!enabled || !activeShell) {
      setStatus(null)
      return undefined
    }
    const tick = () => setStatus(activeShell.getStatus?.() || null)
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [enabled, activeShell, activeId])

  return {
    tabs,
    activeId,
    setActiveId,
    activeShell,
    getShell,
    addTab,
    closeTab,
    renameTab,
    status,
    persistTabUi,
    getTabUi,
  }
}
