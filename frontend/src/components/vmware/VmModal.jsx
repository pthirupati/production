import { useModalA11y } from '../ConfirmModal'

/** Dark vSphere modal shell — matches Claude VMware Lab design */
export default function VmModal({ title, onClose, children, footer, width = 'max-w-md', headerClass = '' }) {
  const dialogRef = useModalA11y(true, onClose)
  return (
    <div className="vm-modal-overlay" onMouseDown={e => e.target === e.currentTarget && onClose?.()}>
      <div
        ref={dialogRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`vm-modal w-full ${width} outline-none`}
      >
        <div className={`vm-modal-header ${headerClass}`}>
          <span>{title}</span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-[#8fa5b8] hover:text-white text-lg leading-none"
          >
            ✕
          </button>
        </div>
        <div className="vm-modal-body">{children}</div>
        {footer && <div className="vm-modal-footer">{footer}</div>}
      </div>
    </div>
  )
}
