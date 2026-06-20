import { useEffect, useRef, useState, useCallback } from 'react'

/**
 * Virtual background for the interview camera preview.
 *
 * HARD REQUIREMENT: this must work offline and with NO paid API / no required
 * remote model. Every background option therefore renders with pure 2D-canvas
 * compositing that ships in the browser — blur, solid colors and gradients all
 * work without downloading anything.
 *
 * Person segmentation (cutting the background out behind the person) is treated
 * as *progressive enhancement*: if MediaPipe's free Selfie Segmentation model
 * happens to load from the CDN we use it for a clean cut-out; if it does NOT
 * load (offline, blocked, CSP, slow link) we fall back to a full-frame stylized
 * effect that still visibly changes the preview. We NEVER show an empty canvas.
 */

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

// Module-level singletons so the (optional) model is loaded at most once and the
// result is shared across every preview instance.
let segmenterPromise = null
let segmenterUnavailable = false

function loadScript(src, timeoutMs = 6000) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) {
      resolve()
      return
    }
    const script = document.createElement('script')
    script.src = src
    script.crossOrigin = 'anonymous'
    let done = false
    const finish = (ok, err) => {
      if (done) return
      done = true
      clearTimeout(timer)
      ok ? resolve() : reject(err || new Error('script load failed'))
    }
    const timer = setTimeout(() => finish(false, new Error('script load timeout')), timeoutMs)
    script.onload = () => finish(true)
    script.onerror = () => finish(false)
    document.head.appendChild(script)
  })
}

async function getSegmenter() {
  // Once we know it's unavailable, never retry — that would re-hang every frame.
  if (segmenterUnavailable) return null
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
  })().catch((err) => {
    // Mark unavailable so the render loop permanently uses the no-model path.
    segmenterUnavailable = true
    segmenterPromise = null
    throw err
  })
  return segmenterPromise
}

function paintBackdrop(ctx, w, h, bg) {
  if (bg.type === 'color') {
    ctx.fillStyle = bg.color
    ctx.fillRect(0, 0, w, h)
    return
  }
  if (bg.type === 'gradient') {
    const grd = ctx.createLinearGradient(0, 0, w, h)
    const stops = bg.colors
    stops.forEach((c, i) => grd.addColorStop(i / Math.max(stops.length - 1, 1), c))
    ctx.fillStyle = grd
    ctx.fillRect(0, 0, w, h)
    return
  }
  // Fallback neutral
  ctx.fillStyle = '#0f172a'
  ctx.fillRect(0, 0, w, h)
}

/**
 * NO-MODEL path — always works, never blank. Draws a stylized full-frame effect
 * for the chosen background so the option visibly changes the preview:
 *  - blur:     a privacy blur of the live video
 *  - color/gradient: the chosen backdrop fills the frame and the live video is
 *    composited on top through a soft radial window — the person stays clearly
 *    visible in the center while the chosen color frames the edges. This gives a
 *    convincing "background replaced" look without any ML segmentation.
 *
 * The video is first rendered (and edge-faded) on an offscreen layer so the
 * fade reveals the backdrop color underneath — not transparency.
 */
function compositeNoModel(ctx, video, w, h, bg, layerCanvas) {
  ctx.save()
  ctx.clearRect(0, 0, w, h)

  if (bg.type === 'blur') {
    ctx.filter = 'blur(12px)'
    ctx.drawImage(video, 0, 0, w, h)
    ctx.filter = 'none'
    ctx.restore()
    return
  }

  // 1. Fill the visible canvas with the chosen backdrop.
  paintBackdrop(ctx, w, h, bg)

  // 2. On an offscreen layer, draw the video and fade its edges to transparent
  //    using a radial mask (destination-in keeps only the center of the video).
  if (layerCanvas) {
    if (layerCanvas.width !== w || layerCanvas.height !== h) {
      layerCanvas.width = w
      layerCanvas.height = h
    }
    const lc = layerCanvas.getContext('2d')
    if (lc) {
      lc.clearRect(0, 0, w, h)
      lc.globalCompositeOperation = 'source-over'
      lc.drawImage(video, 0, 0, w, h)

      const mask = lc.createRadialGradient(
        w / 2, h * 0.46, Math.min(w, h) * 0.16,
        w / 2, h * 0.46, Math.max(w, h) * 0.62,
      )
      mask.addColorStop(0, 'rgba(0,0,0,1)')
      mask.addColorStop(0.6, 'rgba(0,0,0,1)')
      mask.addColorStop(1, 'rgba(0,0,0,0)')
      lc.globalCompositeOperation = 'destination-in'
      lc.fillStyle = mask
      lc.fillRect(0, 0, w, h)
      lc.globalCompositeOperation = 'source-over'

      // 3. Composite the edge-faded video over the backdrop. Where the video
      //    faded out, the backdrop color shows through.
      ctx.drawImage(layerCanvas, 0, 0, w, h)
    }
  } else {
    // No offscreen layer available — still show the person, just over the color.
    ctx.drawImage(video, 0, 0, w, h)
  }

  ctx.restore()
}

/**
 * MODEL path — proper person cut-out using the segmentation mask.
 * `results.image` is the camera frame, `results.segmentationMask` is white where
 * the person is.
 *
 * The person is cut out on a CLEAN offscreen layer (mask → source-in → image),
 * then composited over the backdrop. Doing the cut-out on a fresh layer is what
 * keeps the backdrop visible everywhere the person is NOT — compositing the
 * cut-out directly onto an already-painted backdrop would keep the full frame.
 */
function compositeWithMask(ctx, image, mask, w, h, bg, sourceVideo, layerCanvas) {
  ctx.save()
  ctx.clearRect(0, 0, w, h)

  // 1. Backdrop fills the visible canvas.
  if (bg.type === 'blur') {
    ctx.filter = 'blur(16px)'
    ctx.drawImage(sourceVideo || image, 0, 0, w, h)
    ctx.filter = 'none'
  } else {
    paintBackdrop(ctx, w, h, bg)
  }

  // 2. Build the person cut-out on a clean offscreen layer.
  let personLayer = layerCanvas
  if (personLayer) {
    if (personLayer.width !== w || personLayer.height !== h) {
      personLayer.width = w
      personLayer.height = h
    }
    const lc = personLayer.getContext('2d')
    if (lc) {
      lc.save()
      lc.clearRect(0, 0, w, h)
      lc.globalCompositeOperation = 'source-over'
      lc.drawImage(mask, 0, 0, w, h)
      lc.globalCompositeOperation = 'source-in'
      lc.drawImage(image, 0, 0, w, h)
      lc.restore()
    } else {
      personLayer = null
    }
  }

  // 3. Draw the cut-out person over the backdrop.
  if (personLayer) {
    ctx.drawImage(personLayer, 0, 0, w, h)
  } else {
    // No offscreen layer — degrade to showing the full frame (still not blank).
    ctx.drawImage(image, 0, 0, w, h)
  }

  ctx.restore()
}

export function useVirtualBackground({ videoRef, stream, backgroundId, enabled }) {
  const canvasRef = useRef(null)
  const rafRef = useRef(null)
  const bgRef = useRef(null)
  const [ready, setReady] = useState(false)
  const [loading, setLoading] = useState(false)

  const bg = VIRTUAL_BACKGROUNDS.find((b) => b.id === backgroundId) || VIRTUAL_BACKGROUNDS[0]
  // We render to the canvas for ANY non-"none" background, regardless of whether
  // the ML model is available — the no-model path guarantees a visible result.
  const needsSegmentation = enabled && !!stream && bg.type !== 'none'

  // Keep the latest bg in a ref so the running RAF loop always composites the
  // currently-selected background without restarting the loop on every change.
  bgRef.current = bg

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
    // Always attach the stream to the (hidden or visible) source video element.
    if (video.srcObject !== stream) video.srcObject = stream
    video.muted = true
    video.playsInline = true
    video.play().catch(() => {})

    if (!needsSegmentation) {
      // "None" — the component shows the raw <video> directly; no canvas work.
      stopLoop()
      setReady(true)
      setLoading(false)
      return () => stopLoop()
    }

    let cancelled = false
    setLoading(true)
    let segmenter = null
    let sending = false
    // Offscreen layer used by the no-model path to edge-fade the video over the
    // backdrop color. Created once per loop; lives only as long as the effect.
    const layerCanvas =
      typeof document !== 'undefined' ? document.createElement('canvas') : null

    const ensureCanvasSize = () => {
      const canvas = canvasRef.current
      if (!canvas || !video.videoWidth) return false
      if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
      }
      return true
    }

    const drawNoModel = () => {
      const canvas = canvasRef.current
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      if (ctx) compositeNoModel(ctx, video, canvas.width, canvas.height, bgRef.current, layerCanvas)
    }

    // --- Render loop -------------------------------------------------------
    // We immediately start a no-model loop so the preview is NEVER blank, then
    // try to upgrade to true segmentation in the background. If the model loads,
    // the onResults callback takes over the canvas; if it never loads, the
    // no-model loop keeps running.
    let useModel = false

    const loop = async () => {
      if (cancelled) return
      if (!ensureCanvasSize()) {
        rafRef.current = requestAnimationFrame(loop)
        return
      }
      if (useModel && segmenter && !sending) {
        sending = true
        try {
          await segmenter.send({ image: video })
        } catch {
          // A frame failure shouldn't kill the loop or blank the canvas.
          drawNoModel()
        } finally {
          sending = false
        }
      } else if (!useModel) {
        drawNoModel()
      }
      rafRef.current = requestAnimationFrame(loop)
    }

    setReady(true)
    setLoading(false)
    rafRef.current = requestAnimationFrame(loop)

    // Try to upgrade to the ML cut-out (best-effort, never required).
    getSegmenter()
      .then((seg) => {
        if (cancelled || !seg) return
        segmenter = seg
        seg.onResults((results) => {
          if (cancelled) return
          const canvas = canvasRef.current
          if (!canvas) return
          const ctx = canvas.getContext('2d')
          if (!ctx) return
          if (!results.image || !results.segmentationMask) {
            drawNoModel()
            return
          }
          compositeWithMask(
            ctx,
            results.image,
            results.segmentationMask,
            canvas.width,
            canvas.height,
            bgRef.current,
            video,
            layerCanvas,
          )
        })
        useModel = true
      })
      .catch(() => {
        // Model unavailable — the no-model loop is already running, nothing to do.
        useModel = false
      })

    return () => {
      cancelled = true
      stopLoop()
    }
    // Intentionally NOT depending on backgroundId: the loop reads bgRef each
    // frame, so switching backgrounds is instant and never restarts the model.
  }, [enabled, stream, needsSegmentation, videoRef, stopLoop])

  return { canvasRef, ready, loading, needsSegmentation, bg }
}
