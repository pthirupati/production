/** Dark vSphere modal shell — matches Claude VMware Lab design */
export default function VmModal({ title, onClose, children, footer, width = 'max-w-md', headerClass = '' }) {
  return (
    <div className="vm-modal-overlay" onMouseDown={e => e.target === e.currentTarget && onClose?.()}>
      <div className={`vm-modal w-full ${width}`}>
        <div className={`vm-modal-header ${headerClass}`}>
          <span>{title}</span>
          <button type="button" onClick={onClose} className="text-[#8fa5b8] hover:text-white text-lg leading-none">✕</button>
        </div>
        <div className="vm-modal-body">{children}</div>
        {footer && <div className="vm-modal-footer">{footer}</div>}
      </div>
    </div>
  )
}
