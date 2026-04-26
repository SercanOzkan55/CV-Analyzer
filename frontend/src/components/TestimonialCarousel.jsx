import React, { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const TESTIMONIALS = [
  {
    name: 'Sarah M.',
    role: 'Software Engineer',
    company: 'Google',
    avatar: 'https://i.pravatar.cc/80?u=sarah-google',
    text: 'CV Analyzer helped me understand exactly why I was getting rejected. After following the recommendations, my interview rate jumped from 10% to over 60%.',
    score: 92,
  },
  {
    name: 'James T.',
    role: 'Product Manager',
    company: 'Shopify',
    avatar: 'https://i.pravatar.cc/80?u=james-shopify',
    text: 'The ATS optimization feature is a game-changer. It showed me keywords I was missing and helped me land 3 interviews in my first week of applying.',
    score: 87,
  },
  {
    name: 'Aisha K.',
    role: 'Data Scientist',
    company: 'Spotify',
    avatar: 'https://i.pravatar.cc/80?u=aisha-spotify',
    text: 'As a recruiter, the batch ranking feature saves me hours every week. I can screen 50 CVs in minutes instead of days. Absolutely invaluable.',
    score: 95,
  },
  {
    name: 'Marco R.',
    role: 'UX Designer',
    company: 'Figma',
    avatar: 'https://i.pravatar.cc/80?u=marco-figma',
    text: 'The skill gap analysis was eye-opening. I learned exactly which skills to add to my portfolio to become a stronger candidate for senior roles.',
    score: 84,
  },
  {
    name: 'Lena S.',
    role: 'HR Manager',
    company: 'Stripe',
    avatar: 'https://i.pravatar.cc/80?u=lena-stripe',
    text: 'Our hiring team relies on CV Analyzer daily. The semantic search finds the right candidates from hundreds of applications automatically.',
    score: 91,
  },
  {
    name: 'David C.',
    role: 'Backend Engineer',
    company: 'Cloudflare',
    avatar: 'https://i.pravatar.cc/80?u=david-cloudflare',
    text: 'I was skeptical at first, but the AI scoring is surprisingly accurate. It caught issues I never noticed, and my final resume was dramatically better.',
    score: 89,
  },
]

const ITEMS_PER_PAGE = 3

const cardVariants = {
  hidden: { opacity: 0, y: 28, scale: 0.96 },
  visible: (i) => ({
    opacity: 1, y: 0, scale: 1,
    transition: { duration: 0.45, delay: i * 0.08, ease: [0.25, 0.1, 0.25, 1] },
  }),
  exit: { opacity: 0, y: -16, scale: 0.97, transition: { duration: 0.25 } },
}

export default function TestimonialCarousel({ t }) {
  const [page, setPage] = useState(0)
  const [direction, setDirection] = useState(1)
  const totalPages = Math.ceil(TESTIMONIALS.length / ITEMS_PER_PAGE)

  const goTo = useCallback((idx) => {
    setDirection(idx > page ? 1 : -1)
    setPage(idx)
  }, [page])

  const next = useCallback(() => {
    const nextPage = (page + 1) % totalPages
    setDirection(1)
    setPage(nextPage)
  }, [page, totalPages])

  useEffect(() => {
    const id = setInterval(next, 5500)
    return () => clearInterval(id)
  }, [next])

  const visible = TESTIMONIALS.slice(page * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE + ITEMS_PER_PAGE)

  return (
    <section className="testimonials-section">
      <motion.h2
        className="section-title"
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
      >
        {t ? t('landing.testimonials_title') : 'What Our Users Say'}
      </motion.h2>
      <motion.p
        className="section-subtitle"
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5, delay: 0.1 }}
      >
        {t ? t('landing.testimonials_subtitle') : 'Trusted by thousands of job seekers and recruiters'}
      </motion.p>

      <div className="testimonials-track" style={{ minHeight: 260 }}>
        <AnimatePresence mode="popLayout" initial={false}>
          {visible.map((item, i) => (
            <motion.div
              key={`${page}-${i}`}
              className="testimonial-card"
              custom={i}
              variants={cardVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
            >
              <div className="testimonial-stars">
                {'★★★★★'.split('').map((s, si) => (
                  <motion.span
                    key={si}
                    initial={{ opacity: 0, scale: 0 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.08 + si * 0.04 + 0.2, type: 'spring', stiffness: 400 }}
                  >
                    {s}
                  </motion.span>
                ))}
              </div>
              <p className="testimonial-text">"{item.text}"</p>
              <div className="testimonial-author">
                <img src={item.avatar} alt={item.name} className="testimonial-avatar" loading="lazy" />
                <div className="testimonial-author-info">
                  <span className="author-name">{item.name}</span>
                  <span className="author-role">{item.role} · {item.company}</span>
                </div>
                <motion.div
                  className="testimonial-score-badge"
                  initial={{ scale: 0.7, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: i * 0.08 + 0.3, type: 'spring', stiffness: 300 }}
                >
                  {item.score}%
                </motion.div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Dots */}
      <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 8 }}>
        {Array.from({ length: totalPages }).map((_, i) => (
          <motion.button
            key={i}
            onClick={() => goTo(i)}
            animate={{
              width: i === page ? 24 : 8,
              background: i === page ? 'var(--color-accent)' : 'var(--color-border)',
            }}
            transition={{ duration: 0.3 }}
            style={{
              height: 8,
              borderRadius: 4,
              border: 'none',
              cursor: 'pointer',
              padding: 0,
            }}
            aria-label={`Page ${i + 1}`}
            whileHover={{ scale: 1.2 }}
            whileTap={{ scale: 0.9 }}
          />
        ))}
      </div>
    </section>
  )
}
