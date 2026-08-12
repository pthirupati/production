import { useModalA11y } from '../../ConfirmModal'

/**
 * Shared accessibility shell for simulator sign-in cards.
 * Focus trap + Escape (calls onClose when provided) + dialog landmark.
 */
export default function SimLoginGateCard({
  title,
  onClose,
  className = 'bg-white rounded-lg shadow-2xl w-full max-w-[400px] overflow-hidden',
  children,
}) {
  const panelRef = useModalA11y(true, onClose || (() => {}))
  return (
    <div
      ref={panelRef}
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className={`${className} outline-none`}
    >
      {children}
    </div>
  )
}
