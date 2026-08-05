import {
  FileCode, Folder, FolderOpen, Trash2, Pencil, ChevronRight, ChevronDown, Lock,
} from 'lucide-react'
import { VscFileItem } from './VsCodeWorkbench'
import { buildFileTree, fileBasename } from '../../utils/ide/fileTree'

/**
 * VS Code–style nested file tree (sidebar body). Header actions live in the parent.
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
  protectedPaths = null,
  emptyHint = 'No files yet — use New File or New Folder in the Explorer header.',
  onCreateFile,
}) {
  const tree = buildFileTree(files)
  const dirty = dirtyPaths instanceof Set ? dirtyPaths : new Set(dirtyPaths || [])
  const readonly = readonlyPaths instanceof Set ? readonlyPaths : new Set(readonlyPaths || [])
  const protectedSet = protectedPaths instanceof Set ? protectedPaths : new Set(protectedPaths || [])
  const paths = Object.keys(files || {})

  const renderTree = (node, prefix = '') => {
    const dirNames = Object.keys(node.children || {}).sort()
    const items = []
    dirNames.forEach((dir) => {
      const path = prefix ? `${prefix}/${dir}` : dir
      const open = expandedDirs?.has(path)
      items.push(
        <div key={`d-${path}`}>
          <button type="button" className="vsc-tree-row" onClick={() => onToggleDir?.(path)}>
            {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            {open
              ? <FolderOpen size={13} className="text-amber-400/90 shrink-0" />
              : <Folder size={13} className="text-amber-400/70 shrink-0" />}
            <span className="truncate">{dir}</span>
          </button>
          {open && (
            <div className="vsc-tree-children">
              {renderTree(node.children[dir], path)}
            </div>
          )}
        </div>,
      )
    })
    ;(node.files || []).forEach((f) => {
      const base = fileBasename(f)
      const canMutate = !readonly.has(f) && !protectedSet.has(f)
      items.push(
        <div key={f} className="flex items-center gap-0.5 w-full group">
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
                  className="p-1 text-[var(--vsc-muted)] hover:text-[var(--vsc-text)]"
                  title="Rename"
                >
                  <Pencil size={11} />
                </button>
              )}
              {onDeleteFile && (
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onDeleteFile(f) }}
                  className="p-1 text-red-400 hover:text-red-300"
                  title="Delete"
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

  if (paths.length === 0) {
    return (
      <div className="p-3 space-y-2 text-xs text-[var(--vsc-muted)]">
        <p>{emptyHint}</p>
        {onCreateFile && (
          <button type="button" onClick={onCreateFile} className="vsc-btn w-full justify-center text-[11px]">
            New File
          </button>
        )}
      </div>
    )
  }

  return <div className="vsc-file-tree">{renderTree(tree)}</div>
}
