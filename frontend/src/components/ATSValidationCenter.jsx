import React, { useEffect, useMemo, useState } from 'react'
import {
  Check,
  CheckCircle2,
  Download,
  Eye,
  FileClock,
  FileText,
  Save,
  ScanText,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react'
import { applyReviewDecisions, reviewDecisionMap } from '../utils/cvReview'

function copy(lang, tr, en) {
  return lang === 'tr' ? tr : en
}

function ReviewText({ lines }) {
  const text = (Array.isArray(lines) ? lines : []).join('\n').trim()
  return text ? <pre>{text}</pre> : <span className="text-muted">-</span>
}

export default function ATSValidationCenter({
  result,
  editedText,
  onEditedTextChange,
  onExport,
  exportLoading,
  onSaveVersion,
  saveLoading,
  savedVersion,
  jobDescription,
  benchmark,
  lang = 'en',
}) {
  const center = result?.validation_center || {}
  const operations = useMemo(() => center.review_operations || [], [center.review_operations])
  const changedOperations = useMemo(
    () => operations.filter((operation) => operation.kind !== 'equal'),
    [operations],
  )
  const [view, setView] = useState('optimized')
  const [decisions, setDecisions] = useState(() => reviewDecisionMap(operations))

  useEffect(() => {
    setDecisions(reviewDecisionMap(operations))
    setView('optimized')
  }, [operations])

  function applyDecision(nextDecisions) {
    setDecisions(nextDecisions)
    onEditedTextChange(applyReviewDecisions(operations, nextDecisions))
  }

  function decide(operationId, accepted) {
    applyDecision({ ...decisions, [operationId]: accepted })
  }

  function decideAll(accepted) {
    const next = { ...decisions }
    changedOperations.forEach((operation) => { next[operation.id] = accepted })
    applyDecision(next)
  }

  const snapshot = center.recruiter_snapshot || {}
  const checks = center.checks || []
  const blockingIssues = center.blocking_issues || []
  const exportBlocked = blockingIssues.length > 0 && editedText.trim() === String(result?.optimized_cv_text || '').trim()
  const percentile = Number(benchmark?.percentile || 0)

  const views = [
    { id: 'source', icon: FileText, label: copy(lang, 'Orijinal', 'Original') },
    { id: 'optimized', icon: Sparkles, label: copy(lang, 'Düzeltilmiş', 'Optimized') },
    { id: 'ats', icon: ScanText, label: copy(lang, 'ATS Metni', 'ATS Text') },
    { id: 'recruiter', icon: Eye, label: copy(lang, 'Recruiter 10 sn', 'Recruiter 10 sec') },
  ]

  return (
    <div className="ats-validation-center">
      <header className="ats-validation-header">
        <div>
          <span className="ats-validation-kicker">
            <ShieldCheck size={15} /> {copy(lang, 'ATS Doğrulama Merkezi', 'ATS Validation Center')}
          </span>
          <h3>{copy(lang, 'İndirmeden önce her değişikliği denetle', 'Review every change before download')}</h3>
          {jobDescription?.trim() && (
            <span className="ats-variant-badge">
              {copy(lang, 'İlana özel varyant', 'Job-specific variant')}
            </span>
          )}
          {result?.translation_requested && (
            <span className="ats-variant-badge ats-translation-badge">
              {copy(lang, 'İngilizce çıktı', 'English output')}
            </span>
          )}
        </div>
        <div className={`ats-export-state ${exportBlocked ? 'is-blocked' : 'is-safe'}`}>
          {exportBlocked ? <ShieldAlert size={20} /> : <ShieldCheck size={20} />}
          <div>
            <span>{copy(lang, 'Çıktı durumu', 'Export status')}</span>
            <strong>{exportBlocked ? copy(lang, 'İnceleme gerekli', 'Review required') : copy(lang, 'Güvenli', 'Safe')}</strong>
          </div>
        </div>
      </header>

      <div className="ats-score-grid">
        <div><span>{copy(lang, 'Önceki ATS', 'ATS before')}</span><strong>{result?.before_ats?.overall_score ?? 0}</strong></div>
        <div><span>{copy(lang, 'Sonraki ATS', 'ATS after')}</span><strong>{result?.after_ats?.overall_score ?? 0}</strong></div>
        <div><span>{copy(lang, 'Veri kalitesi', 'Data quality')}</span><strong>{center.quality_score ?? '-'}</strong></div>
        <div><span>{copy(lang, 'Sektör yüzdeliği', 'Peer percentile')}</span><strong>{percentile || '-'}</strong></div>
      </div>

      <section className="ats-checks" aria-label={copy(lang, 'Güvenlik kontrolleri', 'Safety checks')}>
        {checks.map((check) => (
          <div key={check.id} className={`ats-check ats-check-${check.status}`}>
            {check.status === 'pass' ? <CheckCircle2 size={17} /> : <ShieldAlert size={17} />}
            <div><strong>{check.label}</strong><span>{check.detail}</span></div>
          </div>
        ))}
      </section>

      <div className="ats-view-tabs" role="tablist" aria-label={copy(lang, 'CV görünümleri', 'CV views')}>
        {views.map(({ id, icon: Icon, label }) => (
          <button
            type="button"
            role="tab"
            aria-selected={view === id}
            className={view === id ? 'active' : ''}
            onClick={() => setView(id)}
            key={id}
          >
            <Icon size={16} /> {label}
          </button>
        ))}
      </div>

      <div className="ats-view-panel" role="tabpanel">
        {view === 'source' && <pre className="ats-text-preview">{result?.original_cv_text || ''}</pre>}
        {view === 'optimized' && (
          <textarea
            className="job-desc-input ats-text-editor"
            value={editedText}
            onChange={(event) => onEditedTextChange(event.target.value)}
            aria-label={copy(lang, 'Düzeltilmiş CV metni', 'Optimized CV text')}
          />
        )}
        {view === 'ats' && <pre className="ats-text-preview">{editedText}</pre>}
        {view === 'recruiter' && (
          <div className="recruiter-snapshot">
            <div className="recruiter-snapshot-main">
              <span>{copy(lang, 'İlk izlenim', 'First impression')}</span>
              <h4>{snapshot.full_name || copy(lang, 'Aday', 'Candidate')}</h4>
              <strong>{snapshot.title || copy(lang, 'Rol belirtilmemiş', 'Role not specified')}</strong>
              <p>{snapshot.summary || copy(lang, 'Profesyonel özet bulunamadı.', 'No professional summary found.')}</p>
            </div>
            <div className="recruiter-snapshot-facts">
              <div><span>{copy(lang, 'Son deneyim', 'Latest experience')}</span><strong>{[snapshot.latest_experience?.title, snapshot.latest_experience?.company].filter(Boolean).join(' | ') || '-'}</strong></div>
              <div><span>{copy(lang, 'Projeler', 'Projects')}</span><strong>{snapshot.project_count ?? 0}</strong></div>
              <div><span>{copy(lang, 'Eğitim', 'Education')}</span><strong>{snapshot.education_count ?? 0}</strong></div>
            </div>
            <div className="recruiter-skill-list">
              {(snapshot.top_skills || []).map((skill) => <span key={skill}>{skill}</span>)}
            </div>
          </div>
        )}
      </div>

      <section className="ats-change-review">
        <div className="ats-change-review-head">
          <div>
            <span>{copy(lang, 'Değişiklik incelemesi', 'Change review')}</span>
            <strong>{changedOperations.length} {copy(lang, 'değişiklik bloğu', 'change blocks')}</strong>
          </div>
          <div>
            <button type="button" className="btn-outline btn-sm" onClick={() => decideAll(false)}><X size={14} /> {copy(lang, 'Tümünü reddet', 'Reject all')}</button>
            <button type="button" className="btn-outline btn-sm" onClick={() => decideAll(true)}><Check size={14} /> {copy(lang, 'Tümünü kabul et', 'Accept all')}</button>
          </div>
        </div>

        <div className="ats-change-list">
          {changedOperations.length === 0 && <p className="text-muted">{copy(lang, 'Metin değişikliği yok.', 'No text changes.')}</p>}
          {changedOperations.map((operation) => {
            const accepted = decisions[operation.id] !== false
            return (
              <article key={operation.id} className={`ats-change-item ${accepted ? 'is-accepted' : 'is-rejected'}`}>
                <div className="ats-change-copy">
                  <div><span>{copy(lang, 'Önce', 'Before')}</span><ReviewText lines={operation.before_lines} /></div>
                  <div><span>{copy(lang, 'Sonra', 'After')}</span><ReviewText lines={operation.after_lines} /></div>
                </div>
                <div className="ats-change-actions" aria-label={copy(lang, 'Değişiklik kararı', 'Change decision')}>
                  <button type="button" className={!accepted ? 'active reject' : ''} onClick={() => decide(operation.id, false)} title={copy(lang, 'Reddet', 'Reject')}><X size={15} /></button>
                  <button type="button" className={accepted ? 'active accept' : ''} onClick={() => decide(operation.id, true)} title={copy(lang, 'Kabul et', 'Accept')}><Check size={15} /></button>
                </div>
              </article>
            )
          })}
        </div>
      </section>

      <footer className="ats-validation-actions">
        <button type="button" className="btn-primary" onClick={() => onExport('pdf')} disabled={exportLoading === 'pdf' || exportBlocked}>
          <Download size={16} /> {exportLoading === 'pdf' ? copy(lang, 'Hazırlanıyor...', 'Preparing...') : copy(lang, 'Güvenli PDF oluştur', 'Create safe PDF')}
        </button>
        <button type="button" className="btn-outline" onClick={() => onExport('docx')} disabled={exportLoading === 'docx' || exportBlocked}>
          <FileText size={16} /> {copy(lang, 'DOCX oluştur', 'Create DOCX')}
        </button>
        <button type="button" className="btn-outline" onClick={onSaveVersion} disabled={saveLoading || !editedText.trim()}>
          {savedVersion ? <FileClock size={16} /> : <Save size={16} />}
          {saveLoading ? copy(lang, 'Kaydediliyor...', 'Saving...') : savedVersion ? savedVersion.version_label : copy(lang, 'Sürüm olarak kaydet', 'Save as version')}
        </button>
      </footer>
    </div>
  )
}
