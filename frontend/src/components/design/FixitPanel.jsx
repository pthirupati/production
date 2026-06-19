/** Panel/card wrapper — design system surface with optional gradient hero. */
export default function FixitPanel({ children, hero = false, className = '', padding = 'p-6' }) {
  return (
    <div className={`${hero ? 'fx-hero-panel' : 'fx-panel'} ${padding} ${className}`}>
      {children}
    </div>
  )
}
