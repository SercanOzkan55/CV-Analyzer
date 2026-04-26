import React from 'react'
import { motion } from 'framer-motion'
import { useLanguage } from '../i18n/LanguageContext'
import PageTransition from '../components/PageTransition'
import { Target, Eye, History, Award, Shield, Zap, Mail, Github, Linkedin } from 'lucide-react'

export default function AboutPage() {
  const { t } = useLanguage()

  const values = [
    { icon: Zap, title: t('about.v1_title'), text: t('about.v1_text') },
    { icon: Eye, title: t('about.v2_title'), text: t('about.v2_text') },
    { icon: Shield, title: t('about.v3_title'), text: t('about.v3_text') }
  ]

  return (
    <PageTransition>
      <div className="main-content about-page">
        {/* Hero Section */}
        <motion.div 
          className="about-hero"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <h1 className="section-title">{t('about.title')}</h1>
          <p className="section-subtitle">{t('about.subtitle')}</p>
        </motion.div>

        <div className="about-grid">
          {/* Mission & Vision */}
          <motion.div 
            className="card mission-card"
            whileHover={{ y: -5 }}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
          >
            <div className="icon-box"><Target size={32} /></div>
            <h2>{t('about.mission_title')}</h2>
            <p>{t('about.mission_text')}</p>
          </motion.div>

          <motion.div 
            className="card vision-card"
            whileHover={{ y: -5 }}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 }}
          >
            <div className="icon-box"><Eye size={32} /></div>
            <h2>{t('about.vision_title')}</h2>
            <p>{t('about.vision_text')}</p>
          </motion.div>
        </div>

        {/* Founder Section */}
        <motion.section 
          className="about-story section-alt"
          initial={{ opacity: 0, scale: 0.98 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          style={{ padding: '60px 32px', background: 'var(--bg-card)', border: '1px solid var(--color-border)' }}
        >
          <div className="story-content">
            <motion.div 
              className="founder-avatar"
              whileHover={{ scale: 1.05 }}
              style={{ 
                width: '120px', 
                height: '120px', 
                borderRadius: '50%', 
                background: 'var(--color-accent-glow)', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                fontSize: '48px',
                marginBottom: '24px',
                border: '4px solid var(--bg-primary)',
                boxShadow: 'var(--shadow-lg)'
              }}
            >
              👨‍💻
            </motion.div>
            
            <h2 style={{ fontSize: '2rem', marginBottom: '12px' }}>{t('about.story_title')}</h2>
            <div style={{ 
              background: 'var(--color-accent-glow)', 
              color: 'var(--color-accent)', 
              padding: '6px 16px', 
              borderRadius: '99px', 
              fontSize: '0.85rem', 
              fontWeight: '700',
              marginBottom: '24px',
              letterSpacing: '0.05em',
              textTransform: 'uppercase'
            }}>
              {t('about.founder_open_to_work')}
            </div>

            <p style={{ maxWidth: '700px', fontSize: '1.1rem', lineHeight: '1.7', color: 'var(--color-text-secondary)', marginBottom: '32px' }}>
              {t('about.story_text')}
            </p>

            <div className="founder-links" style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', justifyContent: 'center' }}>
              <a href="https://github.com/SercanOzkan55" target="_blank" rel="noopener noreferrer" className="btn-outline" style={{ borderRadius: 'var(--radius-md)' }}>
                <Github size={20} /> GitHub
              </a>
              <a href="https://linkedin.com/in/sercan-özkan-a205852a7/" target="_blank" rel="noopener noreferrer" className="btn-outline" style={{ borderRadius: 'var(--radius-md)' }}>
                <Linkedin size={20} /> LinkedIn
              </a>
              <a href="mailto:ozkansercan55@gmail.com" className="btn-outline" style={{ borderRadius: 'var(--radius-md)' }}>
                <Mail size={20} /> Mail
              </a>
              <a 
                href="/cv_sercan_ozkan.pdf" 
                download 
                className="btn-primary" 
                style={{ borderRadius: 'var(--radius-md)', padding: '12px 24px' }}
              >
                <Zap size={20} /> {t('about.download_cv')}
              </a>
            </div>
          </div>
        </motion.section>

        {/* Values Section */}
        <section className="about-values">
          <h2 className="section-title" style={{ marginTop: '60px' }}>{t('about.values_title')}</h2>
          <div className="values-grid">
            {values.map((v, i) => (
              <motion.div 
                key={i}
                className="value-card card"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
              >
                <v.icon size={24} className="text-accent" />
                <h3>{v.title}</h3>
                <p className="text-muted">{v.text}</p>
              </motion.div>
            ))}
          </div>
        </section>
      </div>

      <style jsx>{`
        .about-page {
          padding-bottom: 100px;
        }
        .about-hero {
          text-align: center;
          margin-bottom: 64px;
        }
        .about-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 32px;
          margin-bottom: 64px;
        }
        .icon-box {
          color: var(--color-accent);
          margin-bottom: 20px;
          background: var(--color-accent-glow);
          width: 64px;
          height: 64px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: var(--radius-md);
        }
        .about-story {
          padding: 80px 40px;
          border-radius: var(--radius-lg);
          text-align: center;
          background: var(--bg-card);
          border: 1px solid var(--color-border);
        }
        .story-content {
          max-width: 800px;
          margin: 0 auto;
          display: flex;
          flex-direction: column;
          align-items: center;
        }
        .story-content p {
          font-size: 1.1rem;
          line-height: 1.8;
          color: var(--color-text-secondary);
        }
        .values-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 24px;
          margin-top: 40px;
        }
        .value-card h3 {
          margin: 16px 0 10px;
        }
        @media (max-width: 768px) {
          .about-grid, .values-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </PageTransition>
  )
}
