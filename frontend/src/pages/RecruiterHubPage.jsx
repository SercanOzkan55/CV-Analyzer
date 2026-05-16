import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Users, Upload, FileText, Download, Search, Filter, 
  BarChart3, Settings, CheckCircle2, AlertCircle, Loader2,
  Mail, ExternalLink, ChevronRight, MoreHorizontal, ArrowUpDown
} from 'lucide-react'
import { useLanguage } from '../i18n/LanguageContext'
import { useAuth } from '../context/AuthContext'
import { 
  recruiterListJobs, 
  recruiterDashboardActions, 
  recruiterSaaSBatchUpload, 
  downloadRecruiterReport 
} from '../api'

export default function RecruiterHubPage() {
  const { t } = useLanguage()
  const { user } = useAuth()
  
  const [activeTab, setActiveTab] = useState('candidates') // candidates | batch | jobs
  const [jobs, setJobs] = useState([])
  const [selectedJob, setSelectedJob] = useState(null)
  const [candidates, setCandidates] = useState([])
  const [loading, setLoading] = useState(false)
  
  // Batch Upload State
  const [uploadFiles, setUploadFiles] = useState([])
  const [processing, setProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [taskId, setTaskId] = useState(null)
  
  const fileInputRef = useRef(null)

  useEffect(() => {
    fetchJobs()
  }, [])

  useEffect(() => {
    if (selectedJob) {
      fetchCandidates(selectedJob.id)
    }
  }, [selectedJob])

  const fetchJobs = async () => {
    try {
      const data = await recruiterListJobs(user?.token || '')
      const list = Array.isArray(data) ? data : data?.jobs || []
      setJobs(list)
      if (list.length > 0 && !selectedJob) {
        setSelectedJob(list[0])
      }
    } catch (err) {
      console.error('Failed to fetch jobs', err)
    }
  }

  const fetchCandidates = async (jobId) => {
    setLoading(true)
    try {
      const data = await recruiterDashboardActions(user?.token || '', jobId)
      setCandidates(Array.isArray(data) ? data : data?.actions || [])
    } catch (err) {
      console.error('Failed to fetch candidates', err)
    } finally {
      setLoading(false)
    }
  }

  const handleFileChange = (e) => {
    const selected = Array.from(e.target.files)
    setUploadFiles(prev => [...prev, ...selected])
  }

  const startBatchAnalysis = async () => {
    if (!selectedJob || uploadFiles.length === 0) return
    
    setProcessing(true)
    setProgress(10)
    
    try {
      const res = await recruiterSaaSBatchUpload(user?.token || '', selectedJob.id, uploadFiles)
      setTaskId(res.data_id || res.task_id)
      
      // Simulate progress for UI feel since Celery is async
      let p = 10
      const interval = setInterval(() => {
        p += Math.random() * 5
        if (p > 95) clearInterval(interval)
        setProgress(Math.min(p, 95))
      }, 1000)

      // In real app, we would poll /api/v1/task-status/{taskId}
      // For this demo, we'll wait 5s and refresh
      setTimeout(() => {
        clearInterval(interval)
        setProgress(100)
        setTimeout(() => {
          setProcessing(false)
          setUploadFiles([])
          setActiveTab('candidates')
          fetchCandidates(selectedJob.id)
        }, 1000)
      }, 5000)

    } catch (err) {
      console.error('Batch upload failed', err)
      setProcessing(false)
    }
  }

  const downloadReport = async () => {
    if (!selectedJob) return
    try {
      const blob = await downloadRecruiterReport(user?.token || '', selectedJob.id)
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `Aday_Raporu_${selectedJob.title.replace(/\s+/g, '_')}.xlsx`)
      document.body.appendChild(link)
      link.click()
    } catch (err) {
      console.error('Download failed', err)
    }
  }

  return (
    <div className="recruiter-hub-page page-container">
      <div className="hub-header">
        <div className="hub-title-area">
          <motion.h1 
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
          >
            <Users className="title-icon" /> Recruiter Hub
          </motion.h1>
          <p className="subtitle">Enterprise Batch Analysis & Aday Yönetimi</p>
        </div>

        <div className="job-selector">
          <label>Aktif İlan:</label>
          <select 
            value={selectedJob?.id || ''} 
            onChange={(e) => setSelectedJob(jobs.find(j => j.id === parseInt(e.target.value)))}
          >
            {jobs.map(job => (
              <option key={job.id} value={job.id}>{job.title}</option>
            ))}
            {jobs.length === 0 && <option value="">İlan Bulunamadı</option>}
          </select>
        </div>
      </div>

      <div className="hub-tabs">
        <button 
          className={`hub-tab ${activeTab === 'candidates' ? 'active' : ''}`}
          onClick={() => setActiveTab('candidates')}
        >
          <BarChart3 size={18} /> Adaylar
        </button>
        <button 
          className={`hub-tab ${activeTab === 'batch' ? 'active' : ''}`}
          onClick={() => setActiveTab('batch')}
        >
          <Upload size={18} /> Toplu Analiz
        </button>
        <button 
          className={`hub-tab ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveTab('settings')}
        >
          <Settings size={18} /> Entegrasyon
        </button>
      </div>

      <div className="hub-content">
        <AnimatePresence mode="wait">
          {activeTab === 'candidates' && (
            <motion.div 
              key="candidates"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="candidates-view"
            >
              <div className="view-header">
                <h2>Aday Sıralaması ({candidates.length})</h2>
                <button className="btn-secondary" onClick={downloadReport} disabled={candidates.length === 0}>
                  <Download size={16} /> Excel Raporu Al
                </button>
              </div>

              {loading ? (
                <div className="hub-loader">
                  <Loader2 className="spinner" />
                  <p>Adaylar yükleniyor...</p>
                </div>
              ) : (
                <div className="candidates-table-container">
                  <table className="candidates-table">
                    <thead>
                      <tr>
                        <th>Sıra</th>
                        <th>Aday Bilgisi</th>
                        <th>
                          <div className="th-cell">Skor <ArrowUpDown size={12} /></div>
                        </th>
                        <th>Durum</th>
                        <th>İşlem</th>
                      </tr>
                    </thead>
                    <tbody>
                      {candidates.map((cand, idx) => (
                        <tr key={cand.id}>
                          <td className="rank-cell">#{idx + 1}</td>
                          <td className="info-cell">
                            <div className="name">{cand.candidate_name}</div>
                            <div className="email">{cand.candidate_email || 'E-posta yok'}</div>
                          </td>
                          <td className="score-cell">
                            <div className="score-badge" style={{ '--score-color': cand.final_score > 70 ? '#10b981' : cand.final_score > 40 ? '#f59e0b' : '#ef4444' }}>
                              {Math.round(cand.final_score)}
                            </div>
                          </td>
                          <td className="status-cell">
                            <span className={`status-pill ${cand.action}`}>
                              {cand.action === 'pending' ? 'Beklemede' : cand.action}
                            </span>
                          </td>
                          <td className="action-cell">
                            <button className="btn-icon" title="Detaylar"><ExternalLink size={16} /></button>
                            <button className="btn-icon" title="E-posta Gönder"><Mail size={16} /></button>
                          </td>
                        </tr>
                      ))}
                      {candidates.length === 0 && (
                        <tr>
                          <td colSpan="5" className="empty-table">
                            Henüz bu ilan için analiz edilmiş aday yok.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </motion.div>
          )}

          {activeTab === 'batch' && (
            <motion.div 
              key="batch"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="batch-upload-view"
            >
              <div className="upload-container">
                <div 
                  className={`drop-zone ${uploadFiles.length > 0 ? 'has-files' : ''}`}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload className="upload-icon" />
                  <h3>Toplu CV Yükle</h3>
                  <p>Onlarca PDF dosyasını buraya sürükleyin veya tıklayın</p>
                  <input 
                    type="file" 
                    multiple 
                    hidden 
                    ref={fileInputRef} 
                    onChange={handleFileChange}
                    accept=".pdf"
                  />
                </div>

                {uploadFiles.length > 0 && !processing && (
                  <div className="file-list-area">
                    <div className="list-header">
                      <span>{uploadFiles.length} Dosya Seçildi</span>
                      <button className="btn-text" onClick={() => setUploadFiles([])}>Temizle</button>
                    </div>
                    <div className="file-grid">
                      {uploadFiles.slice(0, 10).map((f, i) => (
                        <div key={i} className="file-chip">
                          <FileText size={14} /> {f.name}
                        </div>
                      ))}
                      {uploadFiles.length > 10 && <div className="file-chip">+{uploadFiles.length - 10} daha...</div>}
                    </div>
                    <button className="btn-primary start-btn" onClick={startBatchAnalysis}>
                      Analizi Başlat ({uploadFiles.length} CV)
                    </button>
                  </div>
                )}

                {processing && (
                  <div className="processing-area">
                    <div className="progress-info">
                      <Loader2 className="spinner" />
                      <h3>CV'ler İşleniyor...</h3>
                      <p>%{Math.round(progress)} tamamlandı</p>
                    </div>
                    <div className="progress-bar-container">
                      <motion.div 
                        className="progress-bar-fill"
                        initial={{ width: 0 }}
                        animate={{ width: `${progress}%` }}
                      />
                    </div>
                    <p className="hint">Bu işlem aday sayısına göre birkaç dakika sürebilir. Sayfadan ayrılabilirsiniz.</p>
                  </div>
                )}
              </div>
            </motion.div>
          )}
          
          {activeTab === 'settings' && (
            <motion.div 
              key="settings"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="integration-view"
            >
              <div className="integration-cards">
                <div className="integration-card">
                  <div className="card-header">
                    <div className="icon-box linkedin"><ExternalLink size={20} /></div>
                    <h3>LinkedIn Recruiter</h3>
                  </div>
                  <p>Adayları doğrudan LinkedIn projelerinizden senkronize edin.</p>
                  <button className="btn-secondary" disabled>Entegre Et (Yakında)</button>
                </div>
                
                <div className="integration-card">
                  <div className="card-header">
                    <div className="icon-box database"><MoreHorizontal size={20} /></div>
                    <h3>Corporate DB</h3>
                  </div>
                  <p>Şirket içi veritabanınızdaki (Postgres/S3) CV havuzunu bağlayın.</p>
                  <button className="btn-secondary" disabled>Entegre Et (Yakında)</button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
