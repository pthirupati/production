import { Mic, Video, Shield } from 'lucide-react'

const COPY = {
  both: {
    title: 'Allow camera and microphone?',
    body: 'FixitLab needs access so your interviewer can see and hear you during the session. Your video is not recorded on our servers.',
    icon: 'both',
  },
  audio: {
    title: 'Allow microphone?',
    body: 'FixitLab needs microphone access for voice answers and the live interview. Audio is used only during your session.',
    icon: 'audio',
  },
  video: {
    title: 'Allow camera?',
    body: 'FixitLab needs camera access so you can preview yourself and stay visible during the interview, like Google Meet.',
    icon: 'video',
  },
}

export default function MediaPermissionDialog({ open, type = 'both', onAllow, onBlock, loading = false }) {
  if (!open) return null

  const copy = COPY[type] || COPY.both

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div
        className="w-full max-w-md rounded-2xl border border-surface-700 bg-surface-900 shadow-2xl animate-fade-in"
        role="dialog"
        aria-labelledby="media-permission-title"
        aria-modal="true"
      >
        <div className="p-6 text-center border-b border-surface-800">
          <div className="flex justify-center gap-3 mb-4">
            {(copy.icon === 'both' || copy.icon === 'video') && (
              <div className="w-12 h-12 rounded-full bg-indigo-500/15 flex items-center justify-center">
                <Video size={22} className="text-indigo-300" />
              </div>
            )}
            {(copy.icon === 'both' || copy.icon === 'audio') && (
              <div className="w-12 h-12 rounded-full bg-cyan-500/15 flex items-center justify-center">
                <Mic size={22} className="text-cyan-300" />
              </div>
            )}
          </div>
          <h2 id="media-permission-title" className="text-lg font-semibold text-white">
            {copy.title}
          </h2>
          <p className="text-sm text-surface-400 mt-2 leading-relaxed">{copy.body}</p>
          <p className="text-xs text-surface-500 mt-3 flex items-center justify-center gap-1.5">
            <Shield size={12} />
            After you click Allow, your browser will ask you to confirm — choose Allow there too.
          </p>
        </div>
        <div className="flex">
          <button
            type="button"
            onClick={onBlock}
            disabled={loading}
            className="flex-1 py-3.5 text-sm font-medium text-surface-300 hover:bg-surface-800/80 border-r border-surface-800 transition-colors"
          >
            Block
          </button>
          <button
            type="button"
            onClick={onAllow}
            disabled={loading}
            className="flex-1 py-3.5 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition-colors disabled:opacity-50"
          >
            {loading ? 'Requesting…' : 'Allow'}
          </button>
        </div>
      </div>
    </div>
  )
}
