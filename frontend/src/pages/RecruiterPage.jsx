import { motion } from 'framer-motion'
import { Users } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import Navbar from '../components/Navbar'
import LocalWorkerPanel from '../components/LocalWorkerPanel'

export default function RecruiterPage() {
  const { t } = useLanguage()
  const { user } = useAuth()

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">

        {/* ── Page header ────────────────────── */}
        <motion.div
          className="recruiter-page-header"
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="recruiter-header-icon-wrap">
            <Users size={28} />
          </div>
          <div>
            <h1 className="recruiter-page-title">{t('recruiter.title')}</h1>
            <p className="recruiter-page-subtitle">{t('recruiter.subtitle')}</p>
          </div>
        </motion.div>

        <LocalWorkerPanel organizationId={user?.organization_id || user?.organizationId} />
      </main>
    </div>
  )
}
