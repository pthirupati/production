import { RefreshCw } from '../../ui/eagerIcons'

/** Admin panel page header — FixitLab Admin.dc.html style. */
export default function AdminPageHeader({
  title,
  subtitle,
  onRefresh,
  refreshing = false,
  actions,
}) {
  return (
    <div className="fx-admin-header animate-fx-rise">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <p className="fx-admin-eyebrow m-0 mb-1.5">FixitLab Admin</p>
          <h1 className="font-display font-extrabold text-2xl text-white m-0 tracking-tight">{title}</h1>
          {subtitle && <p className="text-surface-400 text-sm mt-1.5 m-0">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2">
          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              disabled={refreshing}
              className="btn-secondary flex items-center gap-2 text-sm py-2 px-3"
            >
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
              Refresh
            </button>
          )}
          {actions}
        </div>
      </div>
    </div>
  )
}
