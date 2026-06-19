/** Shared Framer Motion variants — matches reference mockup timing. */
export const easeOut = [0.16, 1, 0.3, 1]
export const easeSpring = [0.2, 0.8, 0.2, 1]

export const fadeUp = {
  hidden: { opacity: 0, y: 28 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.65, ease: easeOut } },
}

export const fadeLeft = {
  hidden: { opacity: 0, x: -52 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.75, ease: easeOut } },
}

export const fadeRight = {
  hidden: { opacity: 0, x: 52 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.75, ease: easeOut } },
}

export const scaleIn = {
  hidden: { opacity: 0, y: 24, scale: 0.92 },
  visible: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.55, ease: easeSpring } },
}

export const blurIn = {
  hidden: { opacity: 0, y: 26, filter: 'blur(16px)' },
  visible: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.85, ease: easeOut } },
}

export const staggerContainer = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.06 } },
}

export const viewportOnce = { once: true, margin: '-8% 0px -7% 0px', amount: 0.14 }
