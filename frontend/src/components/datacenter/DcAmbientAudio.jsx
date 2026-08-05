/**
 * Procedural facility ambience (Web Audio) — CRAC/fan bed + optional alert tone.
 * No external assets; mute-safe; auto-stops on unmount.
 */
import { useEffect, useRef, useState } from 'react'
import { Volume2, VolumeX } from 'lucide-react'

function startBed(ctx, { muted }) {
  const master = ctx.createGain()
  master.gain.value = muted ? 0 : 0.045
  master.connect(ctx.destination)

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

  return {
    master,
    stop() {
      try { osc1.stop(); osc2.stop(); osc3.stop() } catch { /* */ }
      try { master.disconnect() } catch { /* */ }
    },
    setMuted(m) {
      master.gain.setTargetAtTime(m ? 0 : 0.045, ctx.currentTime, 0.08)
    },
    alertStinger() {
      if (muted) return
      const o = ctx.createOscillator()
      const g = ctx.createGain()
      o.type = 'square'
      o.frequency.value = 880
      g.gain.value = 0.0001
      o.connect(g)
      g.connect(master)
      const t = ctx.currentTime
      g.gain.exponentialRampToValueAtTime(0.08, t + 0.02)
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.45)
      o.start(t)
      o.stop(t + 0.5)
    },
  }
}

export default function DcAmbientAudio({
  enabled = true,
  alert = false,
  storageKey = 'fixitlab-dc-ambient-mute',
}) {
  const [muted, setMuted] = useState(() => {
    try { return sessionStorage.getItem(storageKey) === '1' } catch { return false }
  })
  const [armed, setArmed] = useState(false)
  const bedRef = useRef(null)
  const ctxRef = useRef(null)

  useEffect(() => {
    try { sessionStorage.setItem(storageKey, muted ? '1' : '0') } catch { /* */ }
    bedRef.current?.setMuted?.(muted)
  }, [muted, storageKey])

  useEffect(() => {
    if (!enabled || !armed) return undefined
    const AC = window.AudioContext || window.webkitAudioContext
    if (!AC) return undefined
    const ctx = new AC()
    ctxRef.current = ctx
    const bed = startBed(ctx, { muted })
    bedRef.current = bed
    if (ctx.state === 'suspended') ctx.resume().catch(() => {})
    return () => {
      bed.stop()
      bedRef.current = null
      ctx.close().catch(() => {})
      ctxRef.current = null
    }
  }, [enabled, armed]) // eslint-disable-line react-hooks/exhaustive-deps -- remount bed when armed

  useEffect(() => {
    if (alert && armed && !muted) bedRef.current?.alertStinger?.()
  }, [alert, armed, muted])

  if (!enabled) return null

  return (
    <div className="dc-ambient-audio" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
      {!armed ? (
        <button
          type="button"
          className="dc-btn-outline dc-btn-xs"
          title="Enable facility ambience (browser requires a click)"
          onClick={() => setArmed(true)}
        >
          <Volume2 size={11} /> Enable sound
        </button>
      ) : (
        <button
          type="button"
          className="dc-btn-outline dc-btn-xs"
          title={muted ? 'Unmute CRAC / fan bed' : 'Mute facility ambience'}
          onClick={() => setMuted((m) => !m)}
        >
          {muted ? <VolumeX size={11} /> : <Volume2 size={11} />}
          {muted ? 'Muted' : 'Ambience'}
        </button>
      )}
    </div>
  )
}
