import { useEffect, useRef, useState, useCallback } from 'react'

export const VIRTUAL_BACKGROUNDS = [
  { id: 'none', label: 'None', type: 'none' },
  { id: 'blur', label: 'Blur', type: 'blur' },
  { id: 'indigo', label: 'Indigo', type: 'color', color: '#312e81' },
  { id: 'slate', label: 'Slate', type: 'color', color: '#0f172a' },
  { id: 'teal', label: 'Teal', type: 'color', color: '#134e4a' },
  { id: 'office', label: 'Office', type: 'gradient', colors: ['#4b5563', '#374151', '#1f2937'] },
  { id: 'brand', label: 'FixitLab', type: 'gradient', colors: ['#0891b2', '#4f46e5', '#312e81'] },
]

const SEGMENTER_CDN = 'https://cdn.jsdelivr.net/npm/@mediapipe/selfie_segmentation'

let segmenterPromise = null

function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) {
      resolve()
      return
    }
    const script = document.createElement('script')
    script.src = src
    script.crossOrigin = 'anonymous'
    script.onload = () => resolve()
    script.onerror = reject
    document.head.appendChild(script)
  })
}

async function getSegmenter() {
  if (segmenterPromise) return segmenterPromise
  segmenterPromise = (async () => {
    await loadScript(`${SEGMENTER_CDN}/selfie_segmentation.js`)
    const SelfieSegmentation = window.SelfieSegmentation
    if (!SelfieSegmentation) throw new Error('Segmentation unavailable')
    const segmenter = new SelfieSegmentation({
      locateFile: (file) => `${SEGMENTER_CDN}/${file}`,
    })
    segmenter.setOptions({ modelSelection: 1, selfieMode: true })
    await segmenter.initialize()
    return segmenter
  })()
  return segmenterPromise
}

function drawBackground(ctx, w, h, bg) {
  if (bg.type === 'blur') {
    ctx.filter = 'blur(18px)'
    return 'blur'
  }
  if (bg.type === 'color') {
    ctx.fillStyle = bg.color
    ctx.fillRect(0, 0, w, h)
    return null
  }
  if (bg.type === 'gradient') {
    const grd = ctx.createLinearGradient(0, 0, w, h)
    bg.colors.forEach((c, i) => {
      grd.addColorStop(i / Math.max(bg.colors.length - 1, 1), c)
    })
    ctx.fillStyle = grd
    ctx.fillRect(0, 0, w, h)
    return null
  }
  return null
}

function compositeFrame(ctx, image, mask, w, h, bg, sourceVideo) {
  ctx.clearRect(0, 0, w, h)

  if (bg.type === 'none') {
    ctx.drawImage(image, 0, 0, w, h)
    return
  }

  const blurMode = drawBackground(ctx, w, h, bg)
  if (blurMode === 'blur' && sourceVideo) {
    ctx.drawImage(sourceVideo, 0, 0, w, h)
    ctx.filter = 'none'
  }

  ctx.globalCompositeOperation = 'destination-out'
  ctx.drawImage(mask, 0, 0, w, h)
  ctx.globalCompositeOperation = 'destination-atop'
  ctx.drawImage(image, 0, 0, w, h)
  ctx.globalCompositeOperation = 'source-over'
}

export function useVirtualBackground({ videoRef, stream, backgroundId, enabled }) {
  const canvasRef = useRef(null)
  const segmenterRef = useRef(null)
  const rafRef = useRef(null)
  const [ready, setReady] = useState(false)
  const [loading, setLoading] = useState(false)

  const bg = VIRTUAL_BACKGROUNDS.find((b) => b.id === backgroundId) || VIRTUAL_BACKGROUNDS[0]
  const needsSegmentation = enabled && bg.type !== 'none'

  const stopLoop = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!enabled || !stream || !videoRef?.current) {
      stopLoop()
      setReady(false)
      return undefined
    }

    const video = videoRef.current
    video.srcObject = stream
    video.muted = true
    video.playsInline = true
    video.play().catch(() => {})

    if (!needsSegmentation) {
      stopLoop()
      setReady(true)
      setLoading(false)
      return () => stopLoop()
    }

    let cancelled = false
    setLoading(true)

    getSegmenter()
      .then((segmenter) => {
        if (cancelled) return
        segmenterRef.current = segmenter

        const canvas = canvasRef.current
        if (!canvas) return

        segmenter.onResults((results) => {
          const ctx = canvas.getContext('2d')
          if (!ctx || !results.image || !results.segmentationMask) return
          const w = canvas.width
          const h = canvas.height
          compositeFrame(ctx, results.image, results.segmentationMask, w, h, bg, video)
        })

        const tick = async () => {
          if (cancelled || !video.videoWidth) {
            rafRef.current = requestAnimationFrame(tick)
            return
          }
          const canvas = canvasRef.current
          if (canvas && (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight)) {
            canvas.width = video.videoWidth
            canvas.height = video.videoHeight
          }
          try {
            await segmenter.send({ image: video })
          } catch {
            /* ignore frame errors */
          }
          rafRef.current = requestAnimationFrame(tick)
        }

        setReady(true)
        setLoading(false)
        rafRef.current = requestAnimationFrame(tick)
      })
      .catch(() => {
        if (!cancelled) {
          setLoading(false)
          setReady(true)
        }
      })

    return () => {
      cancelled = true
      stopLoop()
    }
  }, [enabled, stream, backgroundId, needsSegmentation, bg, videoRef, stopLoop])

  return { canvasRef, ready, loading, needsSegmentation, bg }
}
