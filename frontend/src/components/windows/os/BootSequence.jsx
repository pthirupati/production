import { useEffect, useRef, useState } from 'react'
import { useOS } from './store'

// Realistic Windows Server 2022 power/boot sequence overlay.
//
// Real hardware reboot order: firmware POST → Windows Boot Manager → spinning
// dots under the OEM/Windows logo → (optional) "Working on updates" → "Getting
// Windows ready" → sign-in/desktop. We reproduce that here so a Restart from
// the Start menu, `Restart-Computer` in the terminal, or "restart now" after a
// Windows Update shows the full boot process instead of a static card.
//
// Phases:
//   restart:  restarting → post → logo → updates → ready → welcome → done
//   shutdown: down → off (waits for Power on) → post → logo → ready → welcome
//   sleep:    handled inline (wake button) — no boot sequence
const SEQUENCES = {
  restart: [
    { key: 'restarting', ms: 1200 },
    { key: 'post', ms: 2000 },
    { key: 'logo', ms: 2200 },
    { key: 'updates', ms: 2800 },
    { key: 'ready', ms: 1600 },
    { key: 'welcome', ms: 900 },
  ],
  // Shutdown pauses at the "off" phase until the user presses Power on.
  shutdown: [
    { key: 'down', ms: 1500 },
    { key: 'off', ms: null }, // null = wait for user
    { key: 'post', ms: 2000 },
    { key: 'logo', ms: 2200 },
    { key: 'ready', ms: 1600 },
    { key: 'welcome', ms: 900 },
  ],
}

const OEM = 'FIXITLAB VIRTUAL PLATFORM'
const BIOS_VER = 'UEFI BIOS v2.18.1264 — Hyper-V Gen2'

function SpinnerDots() {
  return (
    <div className="winboot-dots" aria-hidden>
      {Array.from({ length: 5 }).map((_, i) => (
        <span key={i} style={{ animationDelay: `${i * 0.16}s` }} />
      ))}
    </div>
  )
}

export default function BootSequence() {
  const powerState = useOS((s) => s.powerState)
  const setPowerState = useOS((s) => s.setPowerState)
  const [phaseIdx, setPhaseIdx] = useState(0)
  const [pct, setPct] = useState(0)
  const timerRef = useRef(null)

  const seq = powerState ? SEQUENCES[powerState] : null
  const phase = seq ? seq[phaseIdx]?.key : null

  // Reset to the first phase whenever a new power action starts.
  useEffect(() => {
    setPhaseIdx(0)
    setPct(0)
  }, [powerState])

  // Advance through the timed phases. A phase with ms === null (the powered-off
  // state) waits for the user to press "Power on".
  useEffect(() => {
    if (!seq) return
    const cur = seq[phaseIdx]
    if (!cur) {
      // Sequence finished — restore the desktop.
      setPowerState(null)
      return
    }
    if (cur.ms == null) return // wait for user (Power on)
    timerRef.current = setTimeout(() => setPhaseIdx((i) => i + 1), cur.ms)
    return () => clearTimeout(timerRef.current)
  }, [seq, phaseIdx, setPowerState])

  // Drive the "Working on updates" percentage during the updates phase.
  useEffect(() => {
    if (phase !== 'updates') return
    setPct(0)
    const id = setInterval(() => {
      setPct((p) => {
        const next = p + Math.floor(Math.random() * 11) + 4
        return next >= 100 ? 100 : next
      })
    }, 240)
    return () => clearInterval(id)
  }, [phase])

  if (!powerState || powerState === 'sleep') return null

  // ── Firmware POST screen ──
  if (phase === 'post') {
    return (
      <div className="winboot-screen winboot-post">
        <div className="winboot-post-head">{OEM}</div>
        <div className="winboot-post-sub">{BIOS_VER}</div>
        <pre className="winboot-post-body">{`
CPU0: Intel(R) Xeon(R) Platinum 8370C  @ 2.80GHz
Memory Test : 16384 MB  OK
Detecting drives ...
  SATA0: Virtual HD              128 GB
  SATA1: Virtual DVD-ROM
Network: Microsoft Hyper-V Network Adapter  (PXE)
Secure Boot: Enabled    TPM 2.0: Present

Initializing boot devices ...`}</pre>
        <div className="winboot-post-foot">F2 Setup&nbsp;&nbsp;|&nbsp;&nbsp;F12 Boot Menu&nbsp;&nbsp;|&nbsp;&nbsp;Booting from Windows Boot Manager…</div>
      </div>
    )
  }

  // ── Windows boot logo + spinner ──
  if (phase === 'logo' || phase === 'restarting' || phase === 'down') {
    const caption =
      phase === 'restarting' ? 'Restarting' : phase === 'down' ? 'Shutting down' : ''
    return (
      <div className="winboot-screen winboot-logo">
        <div className="winboot-logo-mark" aria-hidden>
          <span /><span /><span /><span />
        </div>
        {caption ? <div className="winboot-caption">{caption}</div> : null}
        <SpinnerDots />
      </div>
    )
  }

  // ── Powered off — wait for Power on ──
  if (phase === 'off') {
    return (
      <div className="winboot-screen winboot-off">
        <div className="winboot-off-title">The VM has powered off</div>
        <p className="winboot-off-text">This Windows Server lab instance is stopped.</p>
        <button type="button" className="winboot-power-btn" onClick={() => setPhaseIdx((i) => i + 1)}>
          ⏻ Power on
        </button>
      </div>
    )
  }

  // ── Working on updates ──
  if (phase === 'updates') {
    return (
      <div className="winboot-screen winboot-logo">
        <div className="winboot-logo-mark" aria-hidden>
          <span /><span /><span /><span />
        </div>
        <SpinnerDots />
        <div className="winboot-update-text">
          Working on updates {pct}% complete.
          <br />
          Don&apos;t turn off your computer. This will take a while.
        </div>
      </div>
    )
  }

  // ── Getting Windows ready ──
  if (phase === 'ready') {
    return (
      <div className="winboot-screen winboot-logo">
        <SpinnerDots />
        <div className="winboot-ready-text">
          Getting Windows ready
          <br />
          Don&apos;t turn off your computer.
        </div>
      </div>
    )
  }

  // ── Welcome ──
  if (phase === 'welcome') {
    return (
      <div className="winboot-screen winboot-welcome">
        <div className="winboot-logo-mark sm" aria-hidden>
          <span /><span /><span /><span />
        </div>
        <div className="winboot-welcome-text">Welcome</div>
      </div>
    )
  }

  return null
}
