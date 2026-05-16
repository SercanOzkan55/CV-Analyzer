import React, { useState } from 'react'
import { motion } from 'framer-motion'
import {
  TrendingUp, Award, Target, Zap, AlertCircle, CheckCircle,
  Briefcase, BookOpen, Award as AwardIcon, Globe, Mail, Phone,
  MapPin, Download, Share2, MoreVertical, FileText
} from 'lucide-react'
import ScoreCircle from './ScoreCircle'
import ScoreBars from './ScoreBars'
import SkillTags from './SkillTags'

function MetricCard({ icon: Icon, label, value, unit = '', trend = null, color = 'var(--color-accent)' }) {
  return (
    <motion.div
      className="metric-card"
      whileHover={{ y: -4 }}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        background: 'linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: '12px',
        padding: '16px',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        cursor: 'pointer',
      }}
    >
      <div style={{
        width: '40px',
        height: '40px',
        borderRadius: '10px',
        background: `${color}20`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: color,
      }}>
        <Icon size={20} />
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</div>
        <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
          {value}
          {unit && <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginLeft: '4px' }}>{unit}</span>}
        </div>
      </div>
      {trend && (
        <div style={{
          fontSize: '0.85rem',
          fontWeight: 600,
          color: trend > 0 ? '#22c55e' : '#ef4444',
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
        }}>
          <TrendingUp size={14} style={{ transform: trend < 0 ? 'rotate(180deg)' : 'none' }} />
          {Math.abs(trend)}%
        </div>
      )}
    </motion.div>
  )
}

function ExperienceTimeline({ experiences = [] }) {
  if (!experiences || experiences.length === 0) return null

  return (
    <div style={{ marginTop: '24px' }}>
      <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', fontSize: '1rem', fontWeight: 700 }}>
        <Briefcase size={18} style={{ color: '#8b5cf6' }} />
        Experience Timeline
      </h4>
      <div style={{ position: 'relative', paddingLeft: '24px' }}>
        {experiences.slice(0, 4).map((exp, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.1 }}
            style={{
              marginBottom: '16px',
              paddingBottom: '16px',
              borderBottom: idx < Math.min(3, experiences.length - 1) ? '1px solid rgba(255,255,255,0.1)' : 'none',
              position: 'relative',
            }}
          >
            <div style={{
              position: 'absolute',
              left: '-26px',
              top: '2px',
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              background: '#8b5cf6',
              border: '3px solid var(--bg-secondary)',
            }} />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: '12px' }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {exp.title || exp.position || 'Position'}
                </div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  {exp.company || 'Company'} • {exp.location || 'Location'}
                </div>
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                {exp.duration || exp.years || '2+ years'}
              </div>
            </div>
            {exp.description && (
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '8px', lineHeight: 1.5 }}>
                {exp.description}
              </div>
            )}
          </motion.div>
        ))}
        {experiences.length > 4 && (
          <div style={{ fontSize: '0.85rem', color: 'var(--color-accent)', fontWeight: 600, paddingLeft: '8px' }}>
            +{experiences.length - 4} more positions
          </div>
        )}
      </div>
    </div>
  )
}

function EducationSection({ education = [] }) {
  if (!education || education.length === 0) return null

  return (
    <div style={{ marginTop: '24px' }}>
      <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', fontSize: '1rem', fontWeight: 700 }}>
        <BookOpen size={18} style={{ color: '#06b6d4' }} />
        Education
      </h4>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {education.slice(0, 3).map((edu, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: idx * 0.1 }}
            style={{
              padding: '12px',
              borderRadius: '8px',
              background: 'rgba(6, 182, 212, 0.05)',
              border: '1px solid rgba(6, 182, 212, 0.2)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: '12px' }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {edu.degree || 'Degree'} in {edu.field || 'Field'}
                </div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  {edu.school || 'University'}
                </div>
              </div>
              {edu.year && (
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                  {edu.year}
                </div>
              )}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

function MatchBreakdown({ result }) {
  if (!result) return null

  const safeNum = (val) => isNaN(Number(val)) ? 0 : Number(val);

  const scores = [
    { label: 'Semantic Match', value: safeNum(result.final_score_breakdown?.ml_score || result.semantic_score || result.details?.title_match || result.ml_score || 0), color: '#06b6d4' },
    { label: 'Keyword Match', value: safeNum(result.keyword_score || result.details?.keyword_coverage_pct || result.ats?.content?.keyword_score || 0), color: '#8b5cf6' },
    { label: 'Skill Match', value: safeNum(result.skill_score || (result.details?.skills_found?.length ? 100 : 0) || 0), color: '#22c55e' },
    { label: 'Experience Match', value: safeNum(result.experience_score || result.ats?.section_scores?.find(s => s.name === 'experience')?.score || result.details?.experience_score || result.details?.seniority_match || 0), color: '#f59e0b' },
    { label: 'ATS Score', value: safeNum(result.ats_score || result.details?.ats_score || result.ats?.overall_score || 0), color: '#ef4444' },
  ]

  const maxScore = Math.max(...scores.map(s => s.value))

  return (
    <div style={{ marginTop: '24px' }}>
      <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '16px' }}>Detailed Score Breakdown</h4>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px' }}>
        {scores.map((score, idx) => {
          const isMax = score.value === maxScore && score.value > 0
          return (
            <motion.div
              key={idx}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: idx * 0.05 }}
              style={{
                padding: '14px',
                borderRadius: '10px',
                background: isMax
                  ? `linear-gradient(135deg, ${score.color}20 0%, ${score.color}10 100%)`
                  : 'rgba(255, 255, 255, 0.03)',
                border: `1.5px solid ${isMax ? score.color + '40' : 'rgba(255,255,255,0.1)'}`,
                transition: 'all 0.3s ease',
              }}
            >
              <div style={{
                fontSize: '0.7rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
                color: 'var(--text-muted)',
                marginBottom: '8px',
              }}>
                {score.label}
              </div>
              <div style={{
                fontSize: '1.8rem',
                fontWeight: 800,
                color: score.color,
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                {Math.round(score.value)}
              </div>
              <div style={{
                fontSize: '0.75rem',
                color: 'var(--text-muted)',
                marginTop: '4px',
              }}>
                {score.value >= 75 ? '✓ Strong' : score.value >= 50 ? '◐ Moderate' : '✗ Weak'}
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

function CandidateHeaderBanner({ candidate, result, onClose }) {
  const score = result?.final_score || 0
  const getInterpretation = (s) => {
    if (s >= 75) return { text: 'Excellent Match', icon: CheckCircle, color: '#22c55e' }
    if (s >= 50) return { text: 'Good Match', icon: Target, color: '#f59e0b' }
    return { text: 'Needs Review', icon: AlertCircle, color: '#ef4444' }
  }
  
  const interp = getInterpretation(score)
  const InterpIcon = interp.icon

  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)',
      backdropFilter: 'blur(10px)',
      border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: '16px',
      padding: '24px',
      marginBottom: '24px',
      display: 'flex',
      alignItems: 'center',
      gap: '24px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px', flex: 1 }}>
        <div style={{
          width: '120px',
          height: '120px',
          borderRadius: '50%',
          background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.2) 0%, rgba(6, 182, 212, 0.2) 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          position: 'relative',
          border: '3px solid rgba(255,255,255,0.1)',
        }}>
          <ScoreCircle score={score} size={100} />
        </div>
        <div style={{ flex: 1 }}>
          <div>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-primary)' }}>
              {candidate?.candidate_name || candidate?.name || 'Candidate'}
            </div>
            {candidate?.email && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
                <Mail size={14} />
                {candidate.email}
              </div>
            )}
          </div>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            marginTop: '12px',
            padding: '10px 14px',
            borderRadius: '8px',
            background: `${interp.color}20`,
            border: `1px solid ${interp.color}40`,
            width: 'fit-content',
          }}>
            <InterpIcon size={16} style={{ color: interp.color }} />
            <span style={{ color: interp.color, fontWeight: 700, fontSize: '0.9rem' }}>
              {interp.text}
            </span>
          </div>
        </div>
      </div>
      <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
        <button 
          type="button"
          onClick={() => window.print()}
          style={{
            padding: '8px 12px',
            borderRadius: '8px',
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.1)',
            color: 'var(--text-primary)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.85rem',
            fontWeight: 600,
            transition: 'all 0.2s',
          }}
        >
          <Download size={14} /> Export
        </button>
        {onClose && (
          <button 
            type="button"
            onClick={onClose}
            style={{
              padding: '8px 12px',
              borderRadius: '8px',
              background: 'rgba(239,68,68,0.1)',
              border: '1px solid rgba(239,68,68,0.2)',
              color: '#ef4444',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.85rem',
              fontWeight: 600,
              transition: 'all 0.2s',
            }}
          >
            Close
          </button>
        )}
      </div>
    </div>
  )
}

export default function EnhancedCandidatePreview({ candidate, result, previewData, onClose }) {
  const [activeTab, setActiveTab] = useState('overview')

  if (!result) return null

  const finalScore = result.final_score || 0
  const experience = previewData?.experience || candidate?.experience || []
  const education = previewData?.education || candidate?.education || []
  
  // Filter out numbers that were mistakenly added as strengths
  let rawStrengths = previewData?.strengths || result?.details?.strong_keywords || result?.details?.skills_found || []
  let strengths = rawStrengths.filter(s => typeof s === 'string' && isNaN(Number(s)))
  
  let rawWeaknesses = previewData?.weaknesses || result?.details?.weak_signals || result?.details?.missing_skills || []
  let weaknesses = rawWeaknesses.filter(s => typeof s === 'string' && isNaN(Number(s)))

  const tabs = [
    { id: 'overview', label: 'Overview', icon: Target },
    { id: 'experience', label: 'Experience & Edu', icon: Briefcase },
    { id: 'skills', label: 'Skills Match', icon: Award },
    { id: 'cv', label: 'Raw CV', icon: FileText },
  ]

  const detectedSkills = result.detected_skills || result.extracted_skills || result.details?.skills_found || []
  const missingSkills = result.missing_skills || result.details?.missing_skills || []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header Banner */}
      <CandidateHeaderBanner candidate={candidate || previewData} result={result} onClose={onClose} />

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '12px' }}>
        {tabs.map(tab => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '8px 16px',
                borderRadius: '8px',
                background: isActive ? 'rgba(255,255,255,0.1)' : 'transparent',
                color: isActive ? '#fff' : 'var(--text-muted)',
                border: 'none',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '0.9rem',
                transition: 'all 0.2s'
              }}
            >
              <Icon size={16} /> {tab.label}
            </button>
          )
        })}
      </div>

      {activeTab === 'overview' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Metrics Grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: '12px',
          }}>
            <MetricCard
              icon={TrendingUp}
              label="Match Score"
              value={Math.round(finalScore)}
              unit="%"
              color="#22c55e"
            />
            <MetricCard
              icon={Target}
              label="Semantic"
              value={Math.round(result.semantic_score || result.details?.title_match || result.ml_score || 0)}
              unit="%"
              color="#06b6d4"
            />
            <MetricCard
              icon={Zap}
              label="Keywords"
              value={Math.round(result.keyword_score || result.details?.keyword_coverage_pct || result.ats?.content?.keyword_score || 0)}
              unit="%"
              color="#8b5cf6"
            />
            <MetricCard
              icon={Award}
              label="Skills"
              value={Math.round(result.skill_score || (detectedSkills.length ? 100 : 0) || 0)}
              unit="%"
              color="#f59e0b"
            />
          </div>

          {/* Strengths & Weaknesses */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            {strengths && strengths.length > 0 && (
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                style={{
                  padding: '16px',
                  borderRadius: '12px',
                  background: 'rgba(34, 197, 94, 0.05)',
                  border: '1px solid rgba(34, 197, 94, 0.2)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                  <CheckCircle size={16} style={{ color: '#22c55e' }} />
                  <h4 style={{ fontWeight: 700, fontSize: '0.95rem', color: '#22c55e' }}>Strengths</h4>
                </div>
                <ul style={{ paddingLeft: 0, margin: 0, listStyle: 'none' }}>
                  {strengths.slice(0, 8).map((s, i) => (
                    <li key={i} style={{
                      fontSize: '0.85rem',
                      color: 'var(--text-primary)',
                      paddingLeft: '20px',
                      position: 'relative',
                      marginBottom: '6px',
                    }}>
                      <span style={{
                        position: 'absolute',
                        left: 0,
                        color: '#22c55e',
                      }}>✓</span>
                      {s}
                    </li>
                  ))}
                </ul>
              </motion.div>
            )}
            {weaknesses && weaknesses.length > 0 && (
              <motion.div
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                style={{
                  padding: '16px',
                  borderRadius: '12px',
                  background: 'rgba(239, 68, 68, 0.05)',
                  border: '1px solid rgba(239, 68, 68, 0.2)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                  <AlertCircle size={16} style={{ color: '#ef4444' }} />
                  <h4 style={{ fontWeight: 700, fontSize: '0.95rem', color: '#ef4444' }}>Areas for Improvement</h4>
                </div>
                <ul style={{ paddingLeft: 0, margin: 0, listStyle: 'none' }}>
                  {weaknesses.slice(0, 8).map((w, i) => (
                    <li key={i} style={{
                      fontSize: '0.85rem',
                      color: 'var(--text-primary)',
                      paddingLeft: '20px',
                      position: 'relative',
                      marginBottom: '6px',
                    }}>
                      <span style={{
                        position: 'absolute',
                        left: 0,
                        color: '#ef4444',
                      }}>!</span>
                      {w}
                    </li>
                  ))}
                </ul>
              </motion.div>
            )}
          </div>

          {/* Match Breakdown */}
          <MatchBreakdown result={result} />
        </motion.div>
      )}

      {activeTab === 'skills' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Skills Section */}
          {detectedSkills && detectedSkills.length > 0 && (
            <div>
              <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', fontSize: '1rem', fontWeight: 700 }}>
                <Award size={18} style={{ color: '#f59e0b' }} />
                Detected Skills ({detectedSkills.length})
              </h4>
              <SkillTags skills={detectedSkills.slice(0, 30)} variant="normal" />
              {detectedSkills.length > 30 && (
                <div style={{ marginTop: '8px', fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600 }}>
                  +{detectedSkills.length - 30} more skills
                </div>
              )}
            </div>
          )}

          {/* Missing Skills */}
          {missingSkills && missingSkills.length > 0 && (
            <div>
              <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', fontSize: '1rem', fontWeight: 700 }}>
                <AlertCircle size={18} style={{ color: '#ef4444' }} />
                Missing Skills ({missingSkills.length})
              </h4>
              <SkillTags skills={missingSkills} variant="missing" />
            </div>
          )}
        </motion.div>
      )}

      {activeTab === 'experience' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Experience Timeline */}
          {experience.length > 0 ? (
            <ExperienceTimeline experiences={experience} />
          ) : (
            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', background: 'rgba(255,255,255,0.02)', borderRadius: '12px' }}>
              No experience data successfully extracted.
            </div>
          )}

          {/* Education Section */}
          {education.length > 0 && <EducationSection education={education} />}
        </motion.div>
      )}

      {activeTab === 'cv' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <div style={{
            background: 'rgba(0,0,0,0.2)',
            borderRadius: '12px',
            border: '1px solid rgba(255,255,255,0.05)',
            height: '600px',
            overflow: 'hidden',
          }}>
            {previewData?.pdfUrl || candidate?.pdfUrl ? (
              <iframe 
                src={previewData?.pdfUrl || candidate?.pdfUrl} 
                width="100%" 
                height="100%" 
                style={{ border: 'none' }} 
                title="CV PDF Preview" 
              />
            ) : (
              <div style={{
                padding: '24px',
                height: '100%',
                overflowY: 'auto',
                fontSize: '0.9rem',
                lineHeight: '1.6',
                color: 'var(--text-primary)',
                whiteSpace: 'pre-wrap',
                fontFamily: "'Inter', sans-serif"
              }}>
                {candidate?.cv_text || previewData?.cv_text || result?.cv_text || 'Original CV text or PDF not available.'}
              </div>
            )}
          </div>
        </motion.div>
      )}
    </div>
  )
}
