import { useEffect, useRef, useState } from 'react'
import {
  FileCode, Folder, FolderOpen, Trash2, Pencil, ChevronRight, ChevronDown, Lock,
  Plus, FolderPlus, Copy, MoreHorizontal,
} from 'lucide-react'
import { VscFileItem } from './VsCodeWorkbench'
import { buildFileTree, fileBasename, newFileBasename } from '../../utils/ide/fileTree'

/**
 * VS Code–style nested file tree with inline New File / New Folder and
 * right-click context menu (no window.prompt for create).
 */
export default function IdeExplorer({
  files = {},
  activePath = '',
  dirtyPaths = null,
  readonlyPaths = null,
  expandedDirs,
  onToggleDir,
  onOpenFile,
  onDeleteFile,
  onRenameFile,
  onDuplicateFile,
  onCreateFileAt,
  onCreateFolderAt,
  protectedPaths = null,
  emptyHint = 'No files yet — create a file or folder to begin.',
  disabled = false,
  language = 'python',
}) {
  const tree = buildFileTree(files)
  const dirty = dirtyPaths instanceof Set ? dirtyPaths : new Set(dirtyPaths || [])
  const readonly = readonlyPaths instanceof Set ? readonlyPaths : new Set(readonlyPaths || [])
  const protectedSet = protectedPaths instanceof Set ? protectedPaths : new Set(protectedPaths || [])
  const paths = Object.keys(files || {}).filter((p) => !p.endsWith('/.keep') && fileBasename(p) !== '.keep')

  const [draft, setDraft] = useState(null) // { kind: 'file'|'folder', parent: '', value: '' }
  const [menu, setMenu] = useState(null)   // { x, y, path, isDir }
  const inputRef = useRef(null)

  useEffect(() => {
    if (draft) {
      const t = setTimeout(() => inputRef.current?.focus?.(), 30)
      return () => clearTimeout(t)
    }
    return undefined
  }, [draft])

  useEffect(() => {
    if (!menu) return undefined
    const close = () => setMenu(null)
    const onKey = (e) => { if (e.key === 'Escape') close() }
    window.addEventListener('click', close)
    window.addEventListener('keydown', onKey)
    window.addEventListener('scroll', close, true)
    return () => {
      window.removeEventListener('click', close)
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('scroll', close, true)
    }
  }, [menu])

  const startCreate = (kind, parent = '') => {
    if (disabled) return
    setMenu(null)
    // Bare basename, not newFileHint(): `parent` is prepended on commit, so a
    // src/-prefixed hint would yield src/src/module.py inside a src/ folder.
    const defaultName = kind === 'folder' ? 'new-folder' : newFileBasename(language)
    setDraft({ kind, parent, value: defaultName })
    if (parent) onToggleDir?.(parent) // ensure parent is expanded
  }

  const commitDraft = () => {
    if (!draft) return
    const name = (draft.value || '').trim().replace(/^\/+|\/+$/g, '')
    if (!name) { setDraft(null); return }
    const full = draft.parent ? `${draft.parent}/${name}` : name
    if (draft.kind === 'folder') onCreateFolderAt?.(full)
    else onCreateFileAt?.(full)
    setDraft(null)
  }

  const cancelDraft = () => setDraft(null)

  const openMenu = (e, path, isDir) => {
    e.preventDefault()
    e.stopPropagation()
    if (disabled) return
    setMenu({ x: e.clientX, y: e.clientY, path, isDir })
  }

  const draftRow = (parent) => {
    if (!draft || (draft.parent || '') !== (parent || '')) return null
    return (
      <div className="flex items-center gap-1 px-1 py-0.5 ml-3">
        {draft.kind === 'folder'
          ? <Folder size={13} className="text-amber-400/90 shrink-0" />
          : <FileCode size={13} className="opacity-70 shrink-0" />}
        <input
          ref={inputRef}
          value={draft.value}
          onChange={(e) => setDraft((d) => ({ ...d, value: e.target.value }))}
          onKeyDown={(e) => {
            if (e.key === 'Enter') { e.preventDefault(); commitDraft() }
            if (e.key === 'Escape') { e.preventDefault(); cancelDraft() }
          }}
          onBlur={() => commitDraft()}
          className="flex-1 min-w-0 bg-[#1e1e1e] border border-[#007acc] rounded px-1.5 py-0.5 text-[11px] text-[var(--vsc-text)] outline-none"
          aria-label={draft.kind === 'folder' ? 'New folder name' : 'New file name'}
        />
      </div>
    )
  }

  const renderTree = (node, prefix = '') => {
    const dirNames = Object.keys(node.children || {}).sort()
    const items = []
    dirNames.forEach((dir) => {
      const path = prefix ? `${prefix}/${dir}` : dir
      const open = expandedDirs?.has(path)
      items.push(
        <div key={`d-${path}`}>
          <button
            type="button"
            className="vsc-tree-row group"
            onClick={() => onToggleDir?.(path)}
            onContextMenu={(e) => openMenu(e, path, true)}
          >
            {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            {open
              ? <FolderOpen size={13} className="text-amber-400/90 shrink-0" />
              : <Folder size={13} className="text-amber-400/70 shrink-0" />}
            <span className="truncate flex-1 text-left">{dir}</span>
            {!disabled && (
              <span
                role="button"
                tabIndex={0}
                className="opacity-0 group-hover:opacity-100 p-0.5 text-[var(--vsc-muted)] hover:text-[var(--vsc-text)]"
                title="More actions"
                onClick={(e) => openMenu(e, path, true)}
                onKeyDown={(e) => { if (e.key === 'Enter') openMenu(e, path, true) }}
              >
                <MoreHorizontal size={12} />
              </span>
            )}
          </button>
          {open && (
            <div className="vsc-tree-children">
              {draftRow(path)}
              {renderTree(node.children[dir], path)}
            </div>
          )}
        </div>,
      )
    })
    ;(node.files || []).forEach((f) => {
      const base = fileBasename(f)
      const canMutate = !readonly.has(f) && !protectedSet.has(f) && !disabled
      items.push(
        <div
          key={f}
          className="flex items-center gap-0.5 w-full group"
          onContextMenu={(e) => openMenu(e, f, false)}
        >
          <VscFileItem
            active={activePath === f}
            onClick={() => onOpenFile?.(f)}
            className="flex-1 min-w-0 vsc-tree-file"
          >
            <FileCode size={13} className="shrink-0 opacity-70" />
            <span className="truncate">{base}</span>
            {readonly.has(f) && <Lock size={10} className="ml-auto opacity-50 shrink-0" />}
            {dirty.has(f) && !readonly.has(f) && (
              <span className="ml-auto text-[10px] text-amber-400 shrink-0" title="Unsaved changes">●</span>
            )}
          </VscFileItem>
          {canMutate && (
            <div className="opacity-0 group-hover:opacity-100 flex items-center shrink-0">
              {onRenameFile && (
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onRenameFile(f) }}
                  className="p-1 min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-[var(--vsc-muted)] hover:text-[var(--vsc-text)]"
                  title="Rename"
                  aria-label={`Rename ${f}`}
                >
                  <Pencil size={11} />
                </button>
              )}
              {onDeleteFile && (
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onDeleteFile(f) }}
                  className="p-1 min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-red-400 hover:text-red-300"
                  title="Delete"
                  aria-label={`Delete ${f}`}
                >
                  <Trash2 size={11} />
                </button>
              )}
            </div>
          )}
        </div>,
      )
    })
    return items
  }

  const menuItems = (() => {
    if (!menu) return []
    const { path, isDir } = menu
    if (isDir) {
      return [
        { label: 'New File…', icon: Plus, action: () => startCreate('file', path) },
        { label: 'New Folder…', icon: FolderPlus, action: () => startCreate('folder', path) },
      ]
    }
    const canMutate = !readonly.has(path) && !protectedSet.has(path)
    const items = [
      { label: 'Open', icon: FileCode, action: () => onOpenFile?.(path) },
    ]
    if (canMutate) {
      items.push(
        { label: 'Rename…', icon: Pencil, action: () => onRenameFile?.(path) },
        { label: 'Duplicate', icon: Copy, action: () => onDuplicateFile?.(path) },
        { label: 'Delete', icon: Trash2, action: () => onDeleteFile?.(path), danger: true },
      )
    }
    items.push(
      { label: 'New File…', icon: Plus, action: () => startCreate('file', path.includes('/') ? path.split('/').slice(0, -1).join('/') : '') },
      { label: 'New Folder…', icon: FolderPlus, action: () => startCreate('folder', path.includes('/') ? path.split('/').slice(0, -1).join('/') : '') },
    )
    return items
  })()

  return (
    <div className="relative flex flex-col h-full min-h-0">
      <div className="flex items-center gap-1 px-2 py-1.5 border-b border-[var(--vsc-border,#333)] shrink-0">
        <button
          type="button"
          disabled={disabled}
          onClick={() => startCreate('file', '')}
          className="vsc-btn text-[10px] px-1.5 py-0.5 disabled:opacity-40"
          title="New File"
        >
          <Plus size={11} /> File
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() => startCreate('folder', '')}
          className="vsc-btn text-[10px] px-1.5 py-0.5 disabled:opacity-40"
          title="New Folder"
        >
          <FolderPlus size={11} /> Folder
        </button>
      </div>

      {paths.length === 0 && !draft ? (
        <div className="p-3 space-y-2 text-xs text-[var(--vsc-muted)] flex-1">
          <p>{emptyHint}</p>
          <div className="flex flex-col gap-1.5">
            <button
              type="button"
              disabled={disabled}
              onClick={() => startCreate('file', '')}
              className="vsc-btn w-full justify-center text-[11px]"
            >
              <Plus size={12} /> New File
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={() => startCreate('folder', '')}
              className="vsc-btn w-full justify-center text-[11px]"
            >
              <FolderPlus size={12} /> New Folder
            </button>
          </div>
        </div>
      ) : (
        <div className="vsc-file-tree flex-1 overflow-auto">
          {draftRow('')}
          {renderTree(tree)}
        </div>
      )}

      {menu && (
        <div
          className="fixed z-[100] min-w-[160px] py-1 rounded border border-[#3e3e42] bg-[#252526] shadow-xl text-[11px]"
          style={{ left: Math.min(menu.x, window.innerWidth - 180), top: Math.min(menu.y, window.innerHeight - 200) }}
          role="menu"
          onClick={(e) => e.stopPropagation()}
        >
          {menuItems.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              className={`w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-[#094771] ${item.danger ? 'text-red-400' : 'text-[#cccccc]'}`}
              onClick={() => { setMenu(null); item.action?.() }}
            >
              {item.icon && <item.icon size={12} />}
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
