import { useRef } from 'react'
import { Image, Loader2, VideoOff } from 'lucide-react'
import { useVirtualBackground, VIRTUAL_BACKGROUNDS } from '../../hooks/useVirtualBackground'

export default function InterviewVideoPreview({
  stream,
  cameraOn,
  backgroundId,
  onBackgroundChange,
  showBackgroundPicker = true,
  className = '',
  mirror = true,
  placeholder = 'Camera preview appears here after you allow access',
}) {
  const sourceVideoRef = useRef(null)
  const { canvasRef, loading, needsSegmentation } = useVirtualBackground({
    videoRef: sourceVideoRef,
    stream,
    backgroundId,
    enabled: cameraOn && !!stream,
  })

  const mirrorClass = mirror ? 'scale-x-[-1]' : ''

  return (
    <div className={`relative overflow-hidden bg-surface-900 ${className}`}>
      {cameraOn && stream ? (
        <>
          <video
            ref={sourceVideoRef}
            autoPlay
            muted
            playsInline
            className={
              needsSegmentation
                ? `absolute w-px h-px opacity-0 pointer-events-none ${mirrorClass}`
                : `w-full h-full object-cover ${mirrorClass}`
            }
            aria-hidden={needsSegmentation}
          />
          {needsSegmentation && (
            <canvas
              ref={canvasRef}
              className={`absolute inset-0 w-full h-full object-cover ${mirrorClass}`}
            />
          )}
        </>
      ) : (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-surface-400 text-sm px-6 text-center">
          <VideoOff size={32} className="mb-2 opacity-50" />
          {placeholder}
        </div>
      )}

      {loading && cameraOn && (
        <div className="absolute inset-0 flex items-center justify-center bg-surface-900/60">
          <Loader2 size={24} className="animate-spin text-indigo-400" />
        </div>
      )}

      {showBackgroundPicker && cameraOn && stream && onBackgroundChange && (
        <div className="absolute bottom-2 left-2 right-2 flex gap-1.5 overflow-x-auto pb-1 z-10">
          {VIRTUAL_BACKGROUNDS.map((bg) => (
            <button
              key={bg.id}
              type="button"
              title={bg.label}
              onClick={() => onBackgroundChange(bg.id)}
              className={`shrink-0 w-10 h-10 rounded-lg border-2 overflow-hidden transition-all ${
                backgroundId === bg.id
                  ? 'border-indigo-400 ring-2 ring-indigo-400/40'
                  : 'border-surface-600 hover:border-surface-400'
              }`}
            >
              <BackgroundThumb bg={bg} />
            </button>
          ))}
        </div>
      )}

      {showBackgroundPicker && cameraOn && stream && (
        <div className="absolute top-2 left-2 flex items-center gap-1 text-[10px] text-white/80 bg-black/40 px-2 py-1 rounded-full z-10">
          <Image size={10} />
          Background
        </div>
      )}
    </div>
  )
}

function BackgroundThumb({ bg }) {
  if (bg.type === 'none') {
    return (
      <div className="w-full h-full bg-surface-800 flex items-center justify-center text-[8px] text-surface-400">
        Off
      </div>
    )
  }
  if (bg.type === 'blur') {
    return <div className="w-full h-full bg-gradient-to-br from-surface-500 to-surface-700" />
  }
  if (bg.type === 'color') {
    return <div className="w-full h-full" style={{ background: bg.color }} />
  }
  return (
    <div
      className="w-full h-full"
      style={{ background: `linear-gradient(135deg, ${bg.colors.join(', ')})` }}
    />
  )
}
