/**
 * Procedural facility ambience (Web Audio) — CRAC/fan bed + optional alert tone.
 * No external assets; mute-safe; auto-stops on unmount.
 */
import { useEffect, useRef, useState } from 'react'
import { Volume2, VolumeX } from 'lucide-react'

/** One second of white noise, reused for every noise-based voice.
 *  Three tuned oscillators cannot sound like moving air — a real hall is broadband
 *  noise shaped by the room, and this buffer is what makes HVAC read as HVAC. */
function makeNoiseBuffer(ctx) {
  const buf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate)
  const data = buf.getChannelData(0)
  for (let i = 0; i < data.length; i += 1) data[i] = Math.random() * 2 - 1
  return buf
}

/** Base master gain when unmuted at full volume (proximity / slider scale on top). */
export const AMBIENT_BASE_GAIN = 0.045

function startBed(ctx, { muted, volume = 1 }) {
  // Mutable flags — one-shots close over these objects, not the create-time booleans,
  // so mute/unmute and the volume slider take effect without remounting the bed.
  const flags = { muted: !!muted, volume: Math.max(0, Math.min(1, Number(volume) || 0)) }
  const masterGainFor = () => (flags.muted ? 0 : AMBIENT_BASE_GAIN * flags.volume)

  const master = ctx.createGain()
  master.gain.value = masterGainFor()
  master.connect(ctx.destination)

  const noiseBuffer = makeNoiseBuffer(ctx)

  // Broadband HVAC air. Band-passed around 320Hz with a wide Q so it sits under
  // the tonal fan whine instead of masking it.
  const hvac = ctx.createBufferSource()
  hvac.buffer = noiseBuffer
  hvac.loop = true
  const hvacFilter = ctx.createBiquadFilter()
  hvacFilter.type = 'bandpass'
  hvacFilter.frequency.value = 320
  hvacFilter.Q.value = 0.7
  const hvacGain = ctx.createGain()
  hvacGain.gain.value = 0.0001
  hvac.connect(hvacFilter)
  hvacFilter.connect(hvacGain)
  hvacGain.connect(master)
  // HVAC spins up rather than snapping on — a hall that starts at full noise
  // sounds like a sample loop starting, not like plant equipment.
  hvacGain.gain.setTargetAtTime(0.5, ctx.currentTime, 1.6)

  // Low CRAC rumble
  const osc1 = ctx.createOscillator()
  const g1 = ctx.createGain()
  osc1.type = 'sine'
  osc1.frequency.value = 55
  g1.gain.value = 0.55
  osc1.connect(g1)
  g1.connect(master)

  // Fan whir band
  const osc2 = ctx.createOscillator()
  const g2 = ctx.createGain()
  osc2.type = 'triangle'
  osc2.frequency.value = 118
  g2.gain.value = 0.18
  osc2.connect(g2)
  g2.connect(master)

  // Soft noise-ish via detuned pair
  const osc3 = ctx.createOscillator()
  const g3 = ctx.createGain()
  osc3.type = 'sawtooth'
  osc3.frequency.value = 210
  g3.gain.value = 0.04
  osc3.connect(g3)
  g3.connect(master)

  const now = ctx.currentTime
  osc1.start(now)
  osc2.start(now)
  osc3.start(now)
  hvac.start(now)

  let klaxon = null

  /** Short noise burst through a filter — the shared shape for footsteps, relay
   *  clacks and door SFX. */
  const noiseHit = ({ freq, q, peak, decay, type = 'bandpass' }) => {
    const src = ctx.createBufferSource()
    src.buffer = noiseBuffer
    // Random offset so repeated hits are not bit-identical; a footstep loop that
    // replays the exact same 60ms of noise reads as a glitch, not a step.
    const offset = Math.random() * (noiseBuffer.duration - decay - 0.02)
    const filter = ctx.createBiquadFilter()
    filter.type = type
    filter.frequency.value = freq
    filter.Q.value = q
    const g = ctx.createGain()
    g.gain.value = 0.0001
    src.connect(filter)
    filter.connect(g)
    g.connect(master)
    const t = ctx.currentTime
    g.gain.exponentialRampToValueAtTime(peak, t + 0.006)
    g.gain.exponentialRampToValueAtTime(0.0001, t + decay)
    src.start(t, Math.max(0, offset), decay + 0.02)
  }

  return {
    master,
    flags,
    stop() {
      try { osc1.stop(); osc2.stop(); osc3.stop(); hvac.stop() } catch { /* */ }
      try { klaxon?.stop() } catch { /* */ }
      try { master.disconnect() } catch { /* */ }
    },
    setMuted(m) {
      flags.muted = !!m
      master.gain.setTargetAtTime(masterGainFor(), ctx.currentTime, 0.08)
    },
    setVolume(v) {
      flags.volume = Math.max(0, Math.min(1, Number(v) || 0))
      master.gain.setTargetAtTime(masterGainFor(), ctx.currentTime, 0.08)
    },
    /** Raised-floor tile under a boot: a low thud plus the hollow tile ring above it. */
    footstep(sprinting = false) {
      if (flags.muted || flags.volume <= 0) return
      noiseHit({ freq: sprinting ? 165 : 130, q: 1.4, peak: sprinting ? 0.5 : 0.32, decay: 0.075 })
      noiseHit({ freq: sprinting ? 2600 : 2100, q: 2.2, peak: sprinting ? 0.1 : 0.06, decay: 0.045 })
    },
    /** Breaker / PDU relay — a hard high-Q click, near-instant decay. */
    relayClack() {
      if (flags.muted || flags.volume <= 0) return
      noiseHit({ freq: 1650, q: 9, peak: 0.55, decay: 0.05 })
    },
    /** Mantrap door cycle — a longer low sweep under a latch click. */
    doorCycle() {
      if (flags.muted || flags.volume <= 0) return
      noiseHit({ freq: 240, q: 0.8, peak: 0.3, decay: 0.55, type: 'lowpass' })
      noiseHit({ freq: 1900, q: 7, peak: 0.35, decay: 0.06 })
    },
    /** Continuous two-tone evacuation klaxon while the hall is in alarm. */
    setKlaxon(on) {
      if (on && !klaxon) {
        const o = ctx.createOscillator()
        const lfo = ctx.createOscillator()
        const lfoGain = ctx.createGain()
        const g = ctx.createGain()
        o.type = 'sawtooth'
        o.frequency.value = 560
        // ±90Hz at 1.6Hz — the classic warble. A steady tone reads as a bug.
        lfo.type = 'square'
        lfo.frequency.value = 1.6
        lfoGain.gain.value = 90
        lfo.connect(lfoGain)
        lfoGain.connect(o.frequency)
        g.gain.value = 0.0001
        o.connect(g)
        g.connect(master)
        const t = ctx.currentTime
        g.gain.setTargetAtTime(0.16, t, 0.25)
        o.start(t)
        lfo.start(t)
        klaxon = {
          stop() {
            const t2 = ctx.currentTime
            g.gain.setTargetAtTime(0.0001, t2, 0.2)
            try { o.stop(t2 + 0.9); lfo.stop(t2 + 0.9) } catch { /* */ }
          },
        }
      } else if (!on && klaxon) {
        klaxon.stop()
        klaxon = null
      }
    },
    alertStinger() {
      if (flags.muted || flags.volume <= 0) return
      const o = ctx.createOscillator()
      const g = ctx.createGain()
      o.type = 'square'
      o.frequency.value = 880
      g.gain.value = 0.0001
      o.connect(g)
      g.connect(master)
      const t = ctx.currentTime
      g.gain.exponentialRampToValueAtTime(0.08 * flags.volume, t + 0.02)
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.45)
      o.start(t)
      o.stop(t + 0.5)
    },
  }
}

/** Hall-center anchor used for proximity attenuation (roughly the cold-aisle midpoint). */
const HALL_CENTER = { x: -1, z: 0 }
const PROXIMITY_MAX_DIST = 9

/** Module-level SFX bus. The 3D scene lives inside a <Canvas> and cannot reach this
 *  component through React context, and every alternative (a second AudioContext per
 *  emitter) fights the browser's per-tab context limit and ignores the mute toggle.
 *  Null whenever audio is disarmed or muted, so callers can fire blind. */
let sfxBus = null
export function dcSfx() { return sfxBus }

const VOLUME_STORAGE_KEY = 'fixitlab-dc-ambient-volume'

export function readAmbientVolume(storage = typeof sessionStorage !== 'undefined' ? sessionStorage : null) {
  try {
    const raw = storage?.getItem?.(VOLUME_STORAGE_KEY)
    if (raw == null) return 0.7
    const n = Number(raw)
    if (!Number.isFinite(n)) return 0.7
    return Math.max(0, Math.min(1, n))
  } catch {
    return 0.7
  }
}

export default function DcAmbientAudio({
  enabled = true,
  alert = false,
  alarm = false,
  storageKey = 'fixitlab-dc-ambient-mute',
  posRef = null,
  distanceToHall = null,
}) {
  const [muted, setMuted] = useState(() => {
    try { return sessionStorage.getItem(storageKey) === '1' } catch { return false }
  })
  const [volume, setVolume] = useState(() => readAmbientVolume())
  const [armed, setArmed] = useState(false)
  const bedRef = useRef(null)
  const ctxRef = useRef(null)
  // Simple HTMLAudioElement-style volume scaling by walk-position proximity to the
  // hall center — no Three AudioListener needed for this procedural oscillator bed.
  const hasProximity = !!posRef || typeof distanceToHall === 'number'

  useEffect(() => {
    try { sessionStorage.setItem(storageKey, muted ? '1' : '0') } catch { /* */ }
    if (!hasProximity) bedRef.current?.setMuted?.(muted)
  }, [muted, storageKey, hasProximity])

  useEffect(() => {
    try { sessionStorage.setItem(VOLUME_STORAGE_KEY, String(volume)) } catch { /* */ }
    bedRef.current?.setVolume?.(volume)
  }, [volume])

  useEffect(() => {
    if (!armed || !enabled || !hasProximity) return undefined
    let raf
    const tick = () => {
      const bed = bedRef.current
      const ctx = ctxRef.current
      if (bed && ctx) {
        let dist = 0
        if (posRef?.current) {
          const dx = (posRef.current.x ?? 0) - HALL_CENTER.x
          const dz = (posRef.current.z ?? 0) - HALL_CENTER.z
          dist = Math.hypot(dx, dz)
        } else if (typeof distanceToHall === 'number') {
          dist = distanceToHall
        }
        const proximity = 1 - Math.min(1, Math.max(0, dist) / PROXIMITY_MAX_DIST)
        const target = muted ? 0 : AMBIENT_BASE_GAIN * volume * (0.35 + proximity * 0.65)
        bed.master.gain.setTargetAtTime(target, ctx.currentTime, 0.3)
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [armed, enabled, hasProximity, posRef, distanceToHall, muted, volume])

  useEffect(() => {
    if (!enabled || !armed) return undefined
    const AC = window.AudioContext || window.webkitAudioContext
    if (!AC) return undefined
    const ctx = new AC()
    ctxRef.current = ctx
    const bed = startBed(ctx, { muted, volume })
    bedRef.current = bed
    sfxBus = muted || volume <= 0 ? null : bed
    if (ctx.state === 'suspended') ctx.resume().catch(() => {})
    return () => {
      sfxBus = null
      bed.stop()
      bedRef.current = null
      ctx.close().catch(() => {})
      ctxRef.current = null
    }
  }, [enabled, armed]) // eslint-disable-line react-hooks/exhaustive-deps -- remount bed when armed

  useEffect(() => {
    if (alert && armed && !muted && volume > 0) bedRef.current?.alertStinger?.()
  }, [alert, armed, muted, volume])

  // Klaxon follows the hall alarm state, and stops the moment the player mutes.
  useEffect(() => {
    bedRef.current?.setKlaxon?.(!!alarm && armed && !muted && volume > 0)
    return () => bedRef.current?.setKlaxon?.(false)
  }, [alarm, armed, muted, volume])

  // Muting / zero volume must also silence one-shots fired from inside the Canvas.
  useEffect(() => {
    sfxBus = armed && !muted && volume > 0 ? bedRef.current : null
  }, [armed, muted, volume])

  const armFromGesture = () => {
    setArmed(true)
    // Resume any suspended context created on a prior Enable click.
    try { ctxRef.current?.resume?.() } catch { /* */ }
  }

  if (!enabled) return null

  return (
    <div className="dc-ambient-audio" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
      {!armed ? (
        <button
          type="button"
          className="dc-btn-outline dc-btn-xs"
          title="Enable facility ambience (browser requires a click)"
          onClick={armFromGesture}
        >
          <Volume2 size={11} /> Enable sound
        </button>
      ) : (
        <>
          <button
            type="button"
            className="dc-btn-outline dc-btn-xs"
            title={muted ? 'Unmute CRAC / fan bed' : 'Mute facility ambience'}
            onClick={() => {
              armFromGesture()
              setMuted((m) => !m)
            }}
          >
            {muted ? <VolumeX size={11} /> : <Volume2 size={11} />}
            {muted ? 'Muted' : 'Ambience'}
          </button>
          <label className="dc-ambient-volume" title="Facility ambience volume">
            <span className="sr-only">Volume</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={volume}
              aria-label="Ambience volume"
              onPointerDown={armFromGesture}
              onChange={(e) => {
                const next = Number(e.target.value)
                setVolume(next)
                if (next > 0) setMuted(false)
                armFromGesture()
              }}
            />
          </label>
        </>
      )}
    </div>
  )
}
