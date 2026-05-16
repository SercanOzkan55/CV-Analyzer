import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Sparkles, BarChart2, FileText, Rocket, ChevronRight, ChevronLeft, X } from 'lucide-react'
import { useLanguage } from '../i18n/LanguageContext'

const ONBOARDING_KEY = 'cv_analyzer_onboarding_done'

function useOnboarding() {
  const [show, setShow] = useState(false)

  useEffect(() => {
    try {
      if (!localStorage.getItem(ONBOARDING_KEY)) {
        setShow(true)
      }
    } catch { /* ignore */ }
  }, [])

  function dismiss() {
    setShow(false)
    try { localStorage.setItem(ONBOARDING_KEY, '1') } catch { /* ignore */ }
  }

  return { show, dismiss }
}

const stepIcons = [Sparkles, BarChart2, FileText, Rocket]

export default function OnboardingModal() {
  const { show, dismiss } = useOnboarding()
  const { t } = useLanguage()
  const [step, setStep] = useState(0)

  const steps = [
    {
      icon: stepIcons[0],
      color: 'var(--color-accent)',
      title: t('onboarding.step1_title'),
      desc: t('onboarding.step1_desc'),
    },
    {
      icon: stepIcons[1],
      color: '#a78bfa',
      title: t('onboarding.step2_title'),
      desc: t('onboarding.step2_desc'),
    },
    {
      icon: stepIcons[2],
      color: '#34d399',
      title: t('onboarding.step3_title'),
      desc: t('onboarding.step3_desc'),
    },
    {
      icon: stepIcons[3],
      color: '#f472b6',
      title: t('onboarding.step4_title'),
      desc: t('onboarding.step4_desc'),
    },
  ]

  if (!show) return null

  const isLast = step === steps.length - 1
  const current = steps[step]
  const Icon = current.icon

  return (
    <AnimatePresence>
      <motion.div
        className="onboarding-overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={dismiss}
      >
        <motion.div
          className="onboarding-modal"
          initial={{ opacity: 0, scale: 0.9, y: 30 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 30 }}
          transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
          onClick={(e) => e.stopPropagation()}
        >
          <button className="onboarding-close" onClick={dismiss} aria-label="Close">
            <X size={18} />
          </button>

          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              className="onboarding-step"
              initial={{ opacity: 0, x: 40 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -40 }}
              transition={{ duration: 0.25 }}
            >
              <div className="onboarding-icon" style={{ '--ob-color': current.color }}>
                <Icon size={32} strokeWidth={1.5} style={{ color: current.color }} />
              </div>
              <h2>{current.title}</h2>
              <p className="text-muted">{current.desc}</p>
            </motion.div>
          </AnimatePresence>

          <div className="onboarding-dots">
            {steps.map((_, i) => (
              <span
                key={i}
                className={`onboarding-dot ${i === step ? 'active' : ''}`}
                onClick={() => setStep(i)}
              />
            ))}
          </div>

          <div className="onboarding-actions">
            {step > 0 && (
              <button className="btn-outline btn-sm" onClick={() => setStep(step - 1)}>
                <ChevronLeft size={14} /> {t('onboarding.back')}
              </button>
            )}
            <div style={{ flex: 1 }} />
            {isLast ? (
              <button className="btn-primary btn-sm" onClick={dismiss}>
                {t('onboarding.start')} <Rocket size={14} />
              </button>
            ) : (
              <button className="btn-primary btn-sm" onClick={() => setStep(step + 1)}>
                {t('onboarding.next')} <ChevronRight size={14} />
              </button>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
