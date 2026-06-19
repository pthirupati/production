/**
 * Camera/microphone access with Meet-style fallbacks and clear permission errors.
 */

export async function queryMediaPermission(kind = 'camera') {
  if (!navigator.permissions?.query) return 'prompt'
  // Permissions API uses 'microphone', not 'audio'
  const permName = kind === 'audio' ? 'microphone' : kind
  try {
    const status = await navigator.permissions.query({ name: permName })
    return status.state
  } catch {
    return 'prompt'
  }
}

export function isMediaDevicesSupported() {
  return typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia
}

export function isPermissionDeniedError(err) {
  const name = err?.name || ''
  return name === 'NotAllowedError' || name === 'PermissionDeniedError'
}

/**
 * True when the stream currently holds at least one live track of the kind(s)
 * requested. Used to make a successful getUserMedia authoritative over a racing
 * rejection — if media is actually live we must never show a "blocked" error.
 */
export function streamHasLiveTrack(stream, { audio = false, video = false } = {}) {
  if (!stream) return false
  const live = (t) => t.readyState === 'live'
  if (audio && stream.getAudioTracks().some(live)) return true
  if (video && stream.getVideoTracks().some(live)) return true
  if (!audio && !video) return stream.getTracks().some(live)
  return false
}

export function getMediaErrorMessage(err) {
  const name = err?.name || ''
  if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
    return (
      'Camera or microphone access is blocked. Open your browser site settings ' +
      '(click the lock icon next to the address bar), set Camera and Microphone to "Allow", then click Enable again.'
    )
  }
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
    return 'No camera or microphone was found. Connect a device or use a different browser.'
  }
  if (name === 'NotReadableError' || name === 'TrackStartError') {
    return 'Camera or mic is busy (another app may be using it). Close Zoom, Teams, or Meet and try again.'
  }
  if (name === 'SecurityError') {
    return 'Camera and microphone require a secure connection (HTTPS).'
  }
  if (name === 'NotSupportedError') {
    return err.message || 'This browser does not support camera/microphone access.'
  }
  return err?.message || 'Could not access camera or microphone'
}

function mergeStream(existing, incoming) {
  if (!existing) return incoming
  incoming.getTracks().forEach((track) => {
    existing.getTracks()
      .filter((t) => t.kind === track.kind)
      .forEach((t) => {
        existing.removeTrack(t)
        t.stop()
      })
    existing.addTrack(track)
  })
  return existing
}

async function getUserMediaWithFallback(constraints) {
  const attempts = [
    constraints,
    constraints.video
      ? { audio: constraints.audio, video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } } }
      : null,
    constraints.video ? { audio: constraints.audio, video: true } : null,
    constraints.audio ? { audio: true, video: false } : null,
    constraints.video ? { audio: false, video: true } : null,
  ].filter(Boolean)

  const seen = new Set()
  let lastError = null
  for (const attempt of attempts) {
    const key = JSON.stringify(attempt)
    if (seen.has(key)) continue
    seen.add(key)
    try {
      const stream = await navigator.mediaDevices.getUserMedia(attempt)
      return {
        stream,
        audio: !!attempt.audio,
        video: !!attempt.video,
      }
    } catch (err) {
      lastError = err
      if (err?.name === 'NotAllowedError' || err?.name === 'PermissionDeniedError') {
        throw err
      }
    }
  }
  throw lastError || new Error('Could not access media devices')
}

/**
 * Request audio and/or video, merging into an existing stream when provided.
 */
export async function requestUserMedia(
  { audio = true, video = true } = {},
  existingStream = null,
) {
  if (!isMediaDevicesSupported()) {
    const err = new Error(
      'Your browser does not support camera/microphone. Try Chrome, Firefox, Edge, or Safari.',
    )
    err.name = 'NotSupportedError'
    throw err
  }

  if (audio && video) {
    try {
      const result = await getUserMediaWithFallback({ audio: true, video: true })
      return { ...result, stream: mergeStream(existingStream, result.stream) }
    } catch (err) {
      if (err?.name === 'NotAllowedError' || err?.name === 'PermissionDeniedError') {
        throw err
      }
    }
  }

  let stream = existingStream
  let gotAudio = existingStream?.getAudioTracks().some((t) => t.enabled) ?? false
  let gotVideo = existingStream?.getVideoTracks().some((t) => t.enabled) ?? false
  let lastError = null

  if (audio && !gotAudio) {
    try {
      const result = await getUserMediaWithFallback({ audio: true, video: false })
      stream = mergeStream(stream, result.stream)
      gotAudio = true
    } catch (err) {
      lastError = err
      if (err?.name === 'NotAllowedError' || err?.name === 'PermissionDeniedError') {
        throw err
      }
    }
  }

  if (video && !gotVideo) {
    try {
      const result = await getUserMediaWithFallback({ audio: false, video: true })
      stream = mergeStream(stream, result.stream)
      gotVideo = true
    } catch (err) {
      lastError = err
      if (err?.name === 'NotAllowedError' || err?.name === 'PermissionDeniedError') {
        throw err
      }
    }
  }

  // Only fail when we obtained nothing at all. A partial success (e.g. mic
  // granted but camera busy/denied) is returned so callers can fall back to
  // audio-only instead of surfacing a "blocked" error over a working stream.
  if (!stream || (!gotAudio && !gotVideo)) {
    throw lastError || new Error('Could not enable requested devices')
  }

  return { stream, audio: gotAudio, video: gotVideo }
}

export async function attachStreamToVideo(videoEl, stream) {
  if (!videoEl || !stream) return
  videoEl.srcObject = stream
  videoEl.muted = true
  videoEl.playsInline = true
  await videoEl.play().catch(() => {})
}

export function stopMediaStream(stream) {
  stream?.getTracks().forEach((t) => t.stop())
}
