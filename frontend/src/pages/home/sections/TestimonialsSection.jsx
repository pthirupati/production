import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Star } from 'lucide-react'
import { testimonials } from '../data/homeContent'
import { blurIn, fadeUp, viewportOnce } from '../../../ui/motion'

export default function TestimonialsSection() {
  const [active, setActive] = useState(0)
  const [fading, setFading] = useState(false)

  useEffect(() => {
    const timer = setInterval(() => {
      setFading(true)
      setTimeout(() => {
        setActive(prev => (prev + 1) % testimonials.length)
        setFading(false)
      }, 200)
    }, 5500)
    return () => clearInterval(timer)
  }, [])

  const t = testimonials[active]

  const show = (i) => {
    if (i === active) return
    setFading(true)
    setTimeout(() => {
      setActive(i)
      setFading(false)
    }, 200)
  }

  return (
    <section className="fx-home-section" style={{ paddingTop: 0 }}>
      <div className="max-w-[860px] mx-auto text-center px-8">
        <motion.div
          className="fx-home-eyebrow mx-auto mb-10"
          style={{ background: 'rgba(254,177,85,.1)', border: '1px solid rgba(254,177,85,.25)', color: '#feb155' }}
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={blurIn}
        >
          Loved by engineers
        </motion.div>

        <motion.div
          className="fx-testimonial-card"
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={fadeUp}
        >
          <div className="flex justify-center gap-[5px] mb-[26px]">
            {[...Array(5)].map((_, i) => (
              <Star key={i} size={19} className="text-[#feb155] fill-[#feb155]" />
            ))}
          </div>

          <blockquote
            className="fx-testimonial-quote"
            style={{ opacity: fading ? 0 : 1 }}
          >
            &ldquo;{t.text}&rdquo;
          </blockquote>

          <div className="flex items-center justify-center gap-[14px]">
            <div
              className="w-[52px] h-[52px] rounded-full flex items-center justify-center font-bold text-[17px] text-white shrink-0"
              style={{ background: 'linear-gradient(135deg, var(--fx-ac), var(--fx-ac2))' }}
            >
              {t.initials}
            </div>
            <div className="text-left">
              <p className="font-bold text-base text-white m-0">{t.name}</p>
              <p className="text-sm text-white/50 mt-0.5 m-0">{t.role} · {t.company}</p>
            </div>
          </div>
        </motion.div>

        <div className="flex justify-center gap-[10px] mt-7">
          {testimonials.map((_, i) => (
            <button
              key={i}
              type="button"
              onClick={() => show(i)}
              aria-label={`Testimonial ${i + 1}`}
              className={`fx-testimonial-dot ${i === active ? 'fx-testimonial-dot-active' : ''}`}
            />
          ))}
        </div>
      </div>
    </section>
  )
}
