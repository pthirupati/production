import { toast, Toaster, ToastBar } from 'react-hot-toast'
import { X } from '../ui/eagerIcons'

export default function DismissableToaster() {
  return (
    <Toaster
      position="top-right"
      toastOptions={{
        duration: 5000,
        style: {
          background: 'rgb(var(--s-800))',
          color: 'rgb(var(--s-100))',
          border: '1px solid rgb(var(--s-700))',
        },
      }}
    >
      {(t) => (
        <ToastBar toast={t}>
          {({ icon, message }) => (
            <>
              {icon}
              {message}
              {t.type !== 'loading' && (
                <button
                  type="button"
                  aria-label="Dismiss notification"
                  onClick={() => toast.dismiss(t.id)}
                  className="ml-2 shrink-0 rounded-md p-1 text-surface-400 hover:text-white hover:bg-surface-700/60 transition-colors"
                >
                  <X size={14} />
                </button>
              )}
            </>
          )}
        </ToastBar>
      )}
    </Toaster>
  )
}
