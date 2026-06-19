import { motion, useReducedMotion } from 'framer-motion'
import { viewportOnce } from './motion'

export default function ScrollReveal({
  children,
  variant = 'fadeUp',
  variants,
  className = '',
  delay = 0,
  as: Tag = motion.div,
}) {
  const reduce = useReducedMotion()
  const v = variants || {
    hidden: { opacity: reduce ? 1 : 0, y: reduce ? 0 : 24 },
    visible: { opacity: 1, y: 0, transition: { duration: reduce ? 0 : 0.6, delay } },
  }

  return (
    <Tag
      className={className}
      initial="hidden"
      whileInView="visible"
      viewport={viewportOnce}
      variants={v}
    >
      {children}
    </Tag>
  )
}
