import { useState } from 'react'
import { PanelRight, X } from 'lucide-react'
import '../../styles/vscode-workbench.css'

/**
 * Shared VS Code–style workbench shell for CodingIDE and IaC workspace IDE.
 * Slots: titleBar, activityBar, sidebar, editorTabs, editor, bottomPanel, rightPanel, statusBar.
 *
 * The right panel (instructions / preview / mentor) docks beside the editor at
 * lg and above. Below that it is reachable as a bottom-sheet drawer — see
 * .vsc-right-panel-drawer — because hiding it outright made lab instructions
 * unreadable on tablets and phones.
 */
export default function VsCodeWorkbench({
  theme = 'vscode',          // 'vscode' | 'app'
  accent,
  className = '',
  titleBar,
  title,
  subtitle,
  toolbar,
  activityBar,
  sidebar,
  sidebarHeader,
  sidebarWidth = 220,
  showSidebar = true,
  sidebarMobile = 'hidden', // 'hidden' | 'horizontal' — horizontal shows exercise list on small screens
  editorTabs,
  editorToolbar,
  editor,
  bottomPanel,
  rightPanel,
  statusBar,
  footer,
  rightPanelLabel = 'Instructions',
  /** Open the mobile instructions drawer on first paint (coding labs). */
  rightPanelDefaultOpen = false,
  children,
}) {
  const [drawerOpen, setDrawerOpen] = useState(Boolean(rightPanelDefaultOpen))
  const style = {
    ...(accent ? { '--vsc-accent': accent, '--vsc-status': accent } : {}),
    ...(sidebarWidth ? { '--vsc-sidebar-w': `${sidebarWidth}px` } : {}),
    ...(bottomPanel?.height ? { '--vsc-panel-h': `${bottomPanel.height}px` } : {}),
    ...(rightPanel?.width ? { '--vsc-right-w': `${rightPanel.width}px` } : {}),
  }

  return (
    <div
      className={`vsc-workbench ${theme === 'app' ? 'vsc-app-theme' : ''} ${theme === 'light' ? 'vsc-light-theme' : ''} ${theme === 'hc' ? 'vsc-hc-theme' : ''} ${className}`}
      style={style}
    >      {titleBar || (
        (title || toolbar) && (
          <div className="vsc-titlebar">
            {title && <span className="vsc-titlebar-title">{title}</span>}
            {subtitle && <span className="vsc-titlebar-sub hidden sm:inline">— {subtitle}</span>}
            {toolbar && <div className="vsc-titlebar-actions">{toolbar}</div>}
          </div>
        )
      )}

      <div className={`vsc-body ${sidebarMobile === 'horizontal' ? 'vsc-body-mobile-sidebar' : ''}`}>
        {activityBar}
        {showSidebar && sidebar != null && sidebarMobile === 'horizontal' && (
          <aside className="vsc-sidebar-mobile md:hidden">
            {sidebarHeader && <div className="vsc-sidebar-header">{sidebarHeader}</div>}
            <div className="vsc-sidebar-body vsc-sidebar-body-horizontal">{sidebar}</div>
          </aside>
        )}
        {showSidebar && sidebar != null && (
          <aside className={`vsc-sidebar ${sidebarMobile === 'horizontal' ? 'hidden md:flex' : 'flex'}`}>
            {sidebarHeader && <div className="vsc-sidebar-header">{sidebarHeader}</div>}
            <div className="vsc-sidebar-body">{sidebar}</div>
          </aside>
        )}

        <div className="vsc-main">
          {editorTabs && <div className="vsc-editor-tabs">{editorTabs}</div>}
          <div className="vsc-editor-area">
            {editorToolbar && <div className="vsc-editor-toolbar">{editorToolbar}</div>}
            <div className="vsc-editor-content">{editor}</div>
          </div>

          {bottomPanel?.visible !== false && bottomPanel && (
            <div className="vsc-bottom-panel" style={{ height: bottomPanel.height || 224 }}>
              {bottomPanel.tabs && (
                <div className="vsc-panel-tabs">{bottomPanel.tabs}</div>
              )}
              <div className="vsc-panel-body" style={{ flex: 1, minHeight: 0 }}>
                {bottomPanel.content}
              </div>
            </div>
          )}
        </div>

        {rightPanel?.visible !== false && rightPanel && (
          <>
            {/* Docked panel — lg and up. */}
            <aside className="vsc-right-panel hidden lg:flex">
              {rightPanel.header && <div className="vsc-right-header">{rightPanel.header}</div>}
              <div className="vsc-right-body">{rightPanel.content}</div>
            </aside>

            {/* Below lg: a bottom sheet, so instructions/preview stay reachable
                without stealing width from an already-narrow editor. */}
            {!drawerOpen && (
              <button
                type="button"
                className="vsc-right-drawer-toggle lg:hidden"
                onClick={() => setDrawerOpen(true)}
                aria-expanded={false}
              >
                <PanelRight size={13} /> {rightPanelLabel}
              </button>
            )}
            {drawerOpen && (
              <>
                <button
                  type="button"
                  className="vsc-right-scrim lg:hidden"
                  aria-label="Close panel"
                  onClick={() => setDrawerOpen(false)}
                />
                <aside className="vsc-right-panel vsc-right-panel-drawer flex lg:hidden">
                  <div className="vsc-right-header">
                    <div className="flex-1 flex min-w-0">{rightPanel.header}</div>
                    <button
                      type="button"
                      onClick={() => setDrawerOpen(false)}
                      className="px-2 text-[var(--vsc-muted)] shrink-0"
                      aria-label="Close panel"
                    >
                      <X size={14} />
                    </button>
                  </div>
                  <div className="vsc-right-body">{rightPanel.content}</div>
                </aside>
              </>
            )}
          </>
        )}
      </div>

      {statusBar && (
        <div className="vsc-statusbar">
          <div className="vsc-statusbar-left">{statusBar.left}</div>
          {statusBar.center && <div className="vsc-statusbar-center">{statusBar.center}</div>}
          <div className="vsc-statusbar-right">{statusBar.right}</div>
        </div>
      )}

      {footer}
      {children}
    </div>
  )
}

export function VscFileItem({ active, onClick, children, className = '' }) {
  return (
    <button type="button" onClick={onClick} className={`vsc-file-item ${active ? 'active' : ''} ${className}`}>
      {children}
    </button>
  )
}

export function VscEditorTab({ active, onClick, children }) {
  return (
    <button type="button" onClick={onClick} className={`vsc-editor-tab ${active ? 'active' : ''}`}>
      {children}
    </button>
  )
}

export function VscPanelTab({ active, onClick, children }) {
  return (
    <button type="button" onClick={onClick} className={`vsc-panel-tab ${active ? 'active' : ''}`}>
      {children}
    </button>
  )
}

export function VscActivityButton({ active, onClick, title, children }) {
  return (
    <button type="button" title={title} onClick={onClick} className={`vsc-activity-btn ${active ? 'active' : ''}`}>
      {children}
    </button>
  )
}
