/** Stat card matching FixitLab design system (Dashboard.dc.html). */
export default function FixitStatCard({ icon: Icon, value, label, iconBg = 'bg-accent-cyan/15', iconColor = 'text-accent-cyan', className = '' }) {
  return (
    <div className={`fx-stat-card ${className}`}>
      {Icon && (
        <div className={`w-11 h-11 rounded-[13px] flex items-center justify-center mb-3.5 ${iconBg} ${iconColor}`}>
          <Icon size={22} />
        </div>
      )}
      <p className="font-display font-extrabold text-3xl text-white m-0">{value}</p>
      <p className="text-sm text-white/50 mt-1 font-medium">{label}</p>
    </div>
  )
}
