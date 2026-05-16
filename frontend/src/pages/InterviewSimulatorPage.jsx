import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Mic, MicOff, FileText, Briefcase, Sparkles, ChevronRight, ChevronLeft,
  Upload, Clipboard, Check, AlertCircle, MessageSquare, Star, TrendingUp,
  GraduationCap, Users, Code2, BookOpen, Zap, Target, HelpCircle,
  Send, RotateCcw, Volume2, Award, ThumbsUp, Lightbulb, Clock,
  ListChecks, SlidersHorizontal, Save, RefreshCw, Copy,
} from 'lucide-react'
import Navbar from '../components/Navbar'
import DragDropUpload from '../components/DragDropUpload'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { useToast } from '../components/Toast'
import { generateInterviewQuestions, evaluateInterviewAnswer, autoFixCv } from '../api'

const containerVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07 } },
}
const itemVariants = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.4, 0, 0.2, 1] } },
}

const MODE_OPTIONS = [
  { value: 'junior', icon: GraduationCap, color: '#60a5fa' },
  { value: 'senior', icon: TrendingUp, color: '#a78bfa' },
  { value: 'manager', icon: Users, color: '#34d399' },
  { value: 'tech', icon: Code2, color: '#f97316' },
  { value: 'academic', icon: BookOpen, color: '#ec4899' },
]

const CATEGORY_COLORS = {
  behavioral: '#60a5fa',
  technical: '#f97316',
  situational: '#a78bfa',
  competency: '#34d399',
}
const DIFFICULTY_COLORS = { easy: '#34d399', medium: '#fbbf24', hard: '#ef4444' }
const QUESTION_COUNT_OPTIONS = [3, 5, 7, 10]
const INTERVIEW_SESSION_KEY = 'cv-analyzer:interview-session-v2'

function readSavedInterviewSession() {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem(INTERVIEW_SESSION_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    const questions = Array.isArray(parsed.questions) ? parsed.questions : []
    const phase = questions.length && ['questions', 'practice', 'review'].includes(parsed.phase)
      ? parsed.phase
      : 'setup'
    return {
      ...parsed,
      phase,
      questions,
      currentIdx: Math.max(0, Math.min(Number(parsed.currentIdx || 0), Math.max(questions.length - 1, 0))),
      questionCount: QUESTION_COUNT_OPTIONS.includes(Number(parsed.questionCount)) ? Number(parsed.questionCount) : 5,
      answeredQuestions: parsed.answeredQuestions && typeof parsed.answeredQuestions === 'object' ? parsed.answeredQuestions : {},
      answerDrafts: parsed.answerDrafts && typeof parsed.answerDrafts === 'object' ? parsed.answerDrafts : {},
    }
  } catch {
    return {}
  }
}

function wordCount(text) {
  return text.trim() ? text.trim().split(/\s+/).length : 0
}

function formatDuration(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

export default function InterviewSimulatorPage() {
  const { token } = useAuth()
  const { t, lang } = useLanguage()
  const { addToast } = useToast()
  const savedSessionRef = useRef(null)
  if (savedSessionRef.current === null) savedSessionRef.current = readSavedInterviewSession()
  const savedSession = savedSessionRef.current || {}

  // ── Setup State ──
  const [cvText, setCvText] = useState(savedSession.cvText || '')
  const [jobDescription, setJobDescription] = useState(savedSession.jobDescription || '')
  const [mode, setMode] = useState(savedSession.mode || 'senior')
  const [questionCount, setQuestionCount] = useState(savedSession.questionCount || 5)
  const [inputTab, setInputTab] = useState('paste')
  const [pdfFile, setPdfFile] = useState(null)
  const [pdfLoading, setPdfLoading] = useState(false)

  // ── Session State ──
  const [phase, setPhase] = useState(savedSession.phase || 'setup') // setup | questions | practice | review
  const [questions, setQuestions] = useState(savedSession.questions || [])
  const [currentIdx, setCurrentIdx] = useState(savedSession.currentIdx || 0)
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // ── Answer State ──
  const [userAnswer, setUserAnswer] = useState(savedSession.userAnswer || '')
  const [evaluating, setEvaluating] = useState(false)
  const [evaluation, setEvaluation] = useState(savedSession.evaluation || null)
  const [answeredQuestions, setAnsweredQuestions] = useState(savedSession.answeredQuestions || {})
  const [answerDrafts, setAnswerDrafts] = useState(savedSession.answerDrafts || {})
  const [showTip, setShowTip] = useState(false)

  // ── Voice State ──
  const [isListening, setIsListening] = useState(false)
  const [speechSupported, setSpeechSupported] = useState(false)
  const recognitionRef = useRef(null)
  const answerRef = useRef(null)

  useEffect(() => {
    document.title = `${t('iv.title')} — CV Analyzer`
    const supported = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window
    setSpeechSupported(supported)
  }, [t])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const snapshot = {
      cvText,
      jobDescription,
      mode,
      questionCount,
      phase,
      questions,
      currentIdx,
      answeredQuestions,
      answerDrafts,
      userAnswer,
      evaluation,
    }
    try {
      window.localStorage.setItem(INTERVIEW_SESSION_KEY, JSON.stringify(snapshot))
    } catch {}
  }, [cvText, jobDescription, mode, questionCount, phase, questions, currentIdx, answeredQuestions, answerDrafts, userAnswer, evaluation])

  useEffect(() => {
    if (phase !== 'practice' || evaluating) return undefined
    const timer = window.setInterval(() => setElapsedSeconds(seconds => seconds + 1), 1000)
    return () => window.clearInterval(timer)
  }, [phase, currentIdx, evaluating])

  // ── PDF Upload ──
  async function handlePdfUpload(file) {
    setPdfFile(file)
    if (!file) return
    try {
      setPdfLoading(true)
      setError(null)
      const res = await autoFixCv(token, file, '', { lang, useAi: false })
      const text = res?.optimized_cv_text || res?.original_cv_text || res?.optimized_text || res?.original_text || ''
      if (text) {
        setCvText(text)
        setInputTab('paste')
        addToast(t('iv.pdf_extracted'), 'success')
      } else {
        setError(t('iv.pdf_empty'))
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setPdfLoading(false)
    }
  }

  // ── Generate Questions ──
  async function handleGenerateQuestions(e) {
    e?.preventDefault()
    if (!cvText.trim()) { setError(t('iv.error_no_cv')); return }
    setError(null)
    try {
      setLoading(true)
      const data = await generateInterviewQuestions(token, {
        cv_text: cvText.trim(),
        job_description: jobDescription.trim(),
        lang,
        mode,
        count: questionCount,
      })
      setQuestions(data.questions || [])
      setCurrentIdx(0)
      setPhase('questions')
      setAnsweredQuestions({})
      setAnswerDrafts({})
      setEvaluation(null)
      setUserAnswer('')
      setCategoryFilter('all')
      addToast(t('iv.questions_generated'), 'success')
    } catch (err) {
      setError(err.message || t('iv.error_generic'))
    } finally {
      setLoading(false)
    }
  }

  // ── Start Practice ──
  function handleStartPractice(idx) {
    const savedAnswer = answeredQuestions[idx]
    setCurrentIdx(idx)
    setUserAnswer(savedAnswer?.answer || answerDrafts[idx] || '')
    setEvaluation(savedAnswer?.evaluation || null)
    setShowTip(false)
    setElapsedSeconds(0)
    setPhase(savedAnswer?.evaluation ? 'review' : 'practice')
  }

  function handleAnswerChange(value) {
    setUserAnswer(value)
    setAnswerDrafts(prev => ({ ...prev, [currentIdx]: value }))
  }

  // ── Submit Answer ──
  async function handleSubmitAnswer() {
    if (!userAnswer.trim()) return
    setEvaluating(true)
    setEvaluation(null)
    try {
      const data = await evaluateInterviewAnswer(token, {
        question: questions[currentIdx]?.question || '',
        answer: userAnswer.trim(),
        cv_text: cvText.trim(),
        job_description: jobDescription.trim(),
        lang,
      })
      const evalResult = data.evaluation || {}
      setEvaluation(evalResult)
      setAnsweredQuestions(prev => ({ ...prev, [currentIdx]: { answer: userAnswer, evaluation: evalResult } }))
      setAnswerDrafts(prev => ({ ...prev, [currentIdx]: userAnswer }))
      setPhase('review')
    } catch (err) {
      setError(err.message)
    } finally {
      setEvaluating(false)
    }
  }

  // ── Voice Input ──
  function toggleVoice() {
    if (!speechSupported) return
    if (isListening) {
      recognitionRef.current?.stop()
      setIsListening(false)
      return
    }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    const recognition = new SpeechRecognition()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = lang === 'tr' ? 'tr-TR' : 'en-US'
    recognition.onresult = (event) => {
      let transcript = ''
      for (let i = 0; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript
      }
      handleAnswerChange(transcript)
    }
    recognition.onerror = () => setIsListening(false)
    recognition.onend = () => setIsListening(false)
    recognitionRef.current = recognition
    recognition.start()
    setIsListening(true)
  }

  // ── TTS Read Question ──
  function readQuestionAloud() {
    const q = questions[currentIdx]?.question
    if (!q || !('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    const utter = new SpeechSynthesisUtterance(q)
    utter.lang = lang === 'tr' ? 'tr-TR' : 'en-US'
    utter.rate = 0.9
    window.speechSynthesis.speak(utter)
  }

  // ── Navigation ──
  function handleNextQuestion() {
    if (currentIdx < questions.length - 1) {
      handleStartPractice(currentIdx + 1)
    }
  }
  function handlePrevQuestion() {
    if (currentIdx > 0) {
      handleStartPractice(currentIdx - 1)
    }
  }
  function handleBackToQuestions() {
    setPhase('questions')
    setEvaluation(null)
    setUserAnswer('')
  }
  function handleReset() {
    setPhase('setup')
    setQuestions([])
    setCurrentIdx(0)
    setAnsweredQuestions({})
    setAnswerDrafts({})
    setEvaluation(null)
    setUserAnswer('')
    setError(null)
    setElapsedSeconds(0)
    setCategoryFilter('all')
    setQuestionCount(5)
    try { window.localStorage.removeItem(INTERVIEW_SESSION_KEY) } catch {}
  }

  function handleRetryCurrent() {
    setEvaluation(null)
    setPhase('practice')
    setElapsedSeconds(0)
  }

  async function handleCopySampleAnswer() {
    const sample = evaluation?.sample_answer || ''
    if (!sample) return
    try {
      await navigator.clipboard.writeText(sample)
      addToast(t('iv.sample_copied'), 'success')
    } catch {
      addToast(t('iv.copy_failed'), 'error')
    }
  }

  const currentQ = questions[currentIdx]
  const completedCount = Object.keys(answeredQuestions).length
  const avgScore = completedCount > 0
    ? Math.round(Object.values(answeredQuestions).reduce((s, a) => s + (a.evaluation?.score || 0), 0) / completedCount)
    : 0
  const remainingCount = Math.max(questions.length - completedCount, 0)
  const answerWords = wordCount(userAnswer)
  const answerGoalPercent = Math.min(100, Math.round((answerWords / 90) * 100))
  const answerMinutes = answerWords > 0 ? Math.max(1, Math.ceil(answerWords / 140)) : 0
  const categories = ['all', ...Array.from(new Set(questions.map(q => q.category).filter(Boolean)))]
  const filteredQuestions = questions
    .map((question, idx) => ({ question, idx }))
    .filter(item => categoryFilter === 'all' || item.question.category === categoryFilter)

  function categoryLabel(category) {
    return t(`iv.cat_${category}`) || category
  }

  function difficultyLabel(difficulty) {
    return t(`iv.diff_${difficulty}`) || difficulty
  }

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content" id="main-content">
        <motion.div initial="hidden" animate="show" variants={containerVariants}>

          {/* ── Hero Header ──────────────────── */}
          <motion.div className="iv-header" variants={itemVariants}>
            <div className="iv-header-icon">
              <MessageSquare size={28} strokeWidth={1.6} />
              <div className="iv-header-icon-glow" />
            </div>
            <div>
              <h1 className="iv-title">{t('iv.title')}</h1>
              <p className="iv-subtitle">{t('iv.subtitle')}</p>
            </div>
            {phase !== 'setup' && (
              <motion.button className="iv-reset-btn" onClick={handleReset} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                <RotateCcw size={14} /> {t('iv.new_session')}
              </motion.button>
            )}
          </motion.div>

          {/* ── Progress Bar (when in session) ── */}
          {phase !== 'setup' && questions.length > 0 && (
            <motion.div className="iv-progress-wrap" variants={itemVariants}>
              <div className="iv-progress-bar">
                <div className="iv-progress-fill" style={{ width: `${(completedCount / questions.length) * 100}%` }} />
              </div>
              <div className="iv-progress-info">
                <span>{completedCount}/{questions.length} {t('iv.completed')}</span>
                {avgScore > 0 && <span className="iv-avg-score"><Star size={12} /> {t('iv.avg_score')}: {avgScore}/10</span>}
              </div>
              <div className="iv-session-stats">
                <div className="iv-session-stat">
                  <ListChecks size={15} />
                  <span>{t('iv.remaining')}</span>
                  <strong>{remainingCount}</strong>
                </div>
                <div className="iv-session-stat">
                  <Clock size={15} />
                  <span>{t('iv.current_time')}</span>
                  <strong>{phase === 'practice' ? formatDuration(elapsedSeconds) : '--'}</strong>
                </div>
                <div className="iv-session-stat">
                  <Target size={15} />
                  <span>{t('iv.mode_label')}</span>
                  <strong>{t(`iv.mode_${mode}`)}</strong>
                </div>
              </div>
            </motion.div>
          )}

          <AnimatePresence mode="wait">

          {/* ════════ PHASE: SETUP ════════ */}
          {phase === 'setup' && (
            <motion.form key="setup" onSubmit={handleGenerateQuestions}
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.4 }}>

              <div className="iv-grid">
                {/* Left: CV Input */}
                <motion.div className="iv-card" variants={itemVariants}>
                  <div className="iv-card-accent" />
                  <div className="iv-card-header">
                    <FileText size={18} className="iv-card-icon" />
                    <h2 className="iv-card-title">{t('iv.cv_input')}</h2>
                  </div>
                  <div className="iv-tab-bar">
                    <button type="button" className={`iv-tab ${inputTab === 'paste' ? 'iv-tab-active' : ''}`} onClick={() => setInputTab('paste')}>
                      <Clipboard size={14} /> {t('iv.tab_paste')}
                    </button>
                    <button type="button" className={`iv-tab ${inputTab === 'upload' ? 'iv-tab-active' : ''}`} onClick={() => setInputTab('upload')}>
                      <Upload size={14} /> {t('iv.tab_upload')}
                    </button>
                  </div>
                  <AnimatePresence mode="wait">
                    {inputTab === 'paste' ? (
                      <motion.div key="paste" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                        <textarea className="iv-textarea" rows={12} value={cvText} onChange={e => setCvText(e.target.value)} placeholder={t('iv.cv_placeholder')} />
                      </motion.div>
                    ) : (
                      <motion.div key="upload" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                        <DragDropUpload onFileSelect={handlePdfUpload} file={pdfFile} onRemove={() => setPdfFile(null)} />
                        {pdfLoading && <p className="iv-extracting"><span className="iv-spinner" /> {t('iv.extracting')}</p>}
                      </motion.div>
                    )}
                  </AnimatePresence>
                  {cvText && (
                    <div className="iv-cv-status"><Check size={14} /> {t('iv.cv_loaded')} — {cvText.length.toLocaleString()} {t('iv.chars')}</div>
                  )}
                </motion.div>

                {/* Right: Settings */}
                <motion.div className="iv-card" variants={itemVariants}>
                  <div className="iv-card-accent" />
                  <div className="iv-card-header">
                    <Target size={18} className="iv-card-icon" />
                    <h2 className="iv-card-title">{t('iv.settings_title')}</h2>
                  </div>
                  <div className="iv-field">
                    <label className="iv-label">{t('iv.jd_label')}</label>
                    <textarea className="iv-textarea iv-textarea-sm" rows={6} value={jobDescription} onChange={e => setJobDescription(e.target.value)} placeholder={t('iv.jd_placeholder')} />
                  </div>
                  <div className="iv-field">
                    <label className="iv-label">{t('iv.mode_label')}</label>
                    <div className="iv-mode-grid">
                      {MODE_OPTIONS.map(opt => {
                        const Icon = opt.icon
                        const active = mode === opt.value
                        return (
                          <button key={opt.value} type="button"
                            className={`iv-mode-btn ${active ? 'iv-mode-active' : ''}`}
                            style={active ? { '--mode-color': opt.color } : {}}
                            onClick={() => setMode(opt.value)}>
                            <Icon size={14} /> <span>{t(`iv.mode_${opt.value}`)}</span>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                  <div className="iv-field">
                    <label className="iv-label">{t('iv.question_count')}</label>
                    <div className="iv-count-grid">
                      {QUESTION_COUNT_OPTIONS.map(count => (
                        <button
                          key={count}
                          type="button"
                          className={`iv-count-btn ${questionCount === count ? 'iv-count-active' : ''}`}
                          onClick={() => setQuestionCount(count)}
                        >
                          <ListChecks size={14} />
                          <span>{count}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                  {/* Feature highlights */}
                  <div className="iv-features">
                    <div className="iv-feature"><Mic size={14} /> {t('iv.feature_voice')}</div>
                    <div className="iv-feature"><Sparkles size={14} /> {t('iv.feature_ai')}</div>
                    <div className="iv-feature"><Target size={14} /> {t('iv.feature_personalized')}</div>
                  </div>
                </motion.div>
              </div>

              <AnimatePresence>
                {error && (
                  <motion.div className="iv-error" initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
                    <AlertCircle size={16} /> {error}
                  </motion.div>
                )}
              </AnimatePresence>

              <motion.div className="iv-submit-wrap" variants={itemVariants}>
                <button type="submit" className="iv-submit-btn" disabled={loading || !cvText.trim()}>
                  {loading ? (<><span className="iv-spinner" /> {t('iv.generating')}</>) : (<><Sparkles size={18} /> {t('iv.generate_btn')}</>)}
                </button>
              </motion.div>
            </motion.form>
          )}

          {/* ════════ PHASE: QUESTIONS LIST ════════ */}
          {phase === 'questions' && (
            <motion.div key="questions" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
              <div className="iv-question-board-head">
                <div>
                  <h2>{t('iv.question_board')}</h2>
                  <span>{questions.length} {t('iv.questions_ready')}</span>
                </div>
                <div className="iv-filter-tabs" aria-label={t('iv.category_filter')}>
                  {categories.map(category => (
                    <button
                      key={category}
                      type="button"
                      className={`iv-filter-tab ${categoryFilter === category ? 'iv-filter-active' : ''}`}
                      onClick={() => setCategoryFilter(category)}
                    >
                      <SlidersHorizontal size={13} />
                      {category === 'all' ? t('iv.all_categories') : categoryLabel(category)}
                    </button>
                  ))}
                </div>
              </div>
              <div className="iv-questions-grid">
                {filteredQuestions.map(({ question: q, idx }) => {
                  const answered = answeredQuestions[idx]
                  return (
                    <motion.div key={idx} className={`iv-question-card ${answered ? 'iv-question-answered' : ''}`}
                      initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: idx * 0.08 }}
                      onClick={() => handleStartPractice(idx)}>
                      <div className="iv-question-top">
                        <span className="iv-question-num">Q{idx + 1}</span>
                        <span className="iv-badge" style={{ '--badge-color': CATEGORY_COLORS[q.category] || '#60a5fa' }}>{categoryLabel(q.category)}</span>
                        <span className="iv-badge iv-badge-diff" style={{ '--badge-color': DIFFICULTY_COLORS[q.difficulty] || '#fbbf24' }}>{difficultyLabel(q.difficulty)}</span>
                        {answered && <span className="iv-badge iv-badge-score"><Star size={10} /> {answered.evaluation?.score}/10</span>}
                      </div>
                      <p className="iv-question-text">{q.question}</p>
                      <div className="iv-question-footer">
                        {answered ? <span className="iv-answered-label"><Check size={12} /> {t('iv.answered')}</span> : <span className="iv-start-label"><ChevronRight size={14} /> {t('iv.start_answering')}</span>}
                      </div>
                    </motion.div>
                  )
                })}
              </div>
            </motion.div>
          )}

          {/* ════════ PHASE: PRACTICE ════════ */}
          {phase === 'practice' && currentQ && (
            <motion.div key="practice" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
              <div className="iv-practice-layout">
              <div className="iv-practice-card">
                <div className="iv-practice-header">
                  <div className="iv-practice-meta">
                    <span className="iv-question-num">Q{currentIdx + 1}/{questions.length}</span>
                    <span className="iv-badge" style={{ '--badge-color': CATEGORY_COLORS[currentQ.category] || '#60a5fa' }}>{categoryLabel(currentQ.category)}</span>
                    <span className="iv-badge iv-badge-diff" style={{ '--badge-color': DIFFICULTY_COLORS[currentQ.difficulty] || '#fbbf24' }}>{difficultyLabel(currentQ.difficulty)}</span>
                    <span className="iv-badge iv-badge-time"><Clock size={10} /> {formatDuration(elapsedSeconds)}</span>
                  </div>
                  <div className="iv-practice-actions-top">
                    <motion.button type="button" className="iv-icon-btn" onClick={readQuestionAloud} title={t('iv.read_aloud')} whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
                      <Volume2 size={16} />
                    </motion.button>
                    <motion.button type="button" className="iv-icon-btn" onClick={() => setShowTip(v => !v)} title={t('iv.show_tip')} whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
                      <HelpCircle size={16} />
                    </motion.button>
                  </div>
                </div>

                <h2 className="iv-practice-question">{currentQ.question}</h2>

                <AnimatePresence>
                  {showTip && currentQ.tip && (
                    <motion.div className="iv-tip" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
                      <Lightbulb size={14} /> {currentQ.tip}
                    </motion.div>
                  )}
                </AnimatePresence>

                <div className="iv-answer-section">
                  <label className="iv-label">{t('iv.your_answer')}</label>
                  <div className="iv-answer-wrap">
                    <textarea ref={answerRef} className="iv-answer-textarea" rows={8} value={userAnswer} onChange={e => handleAnswerChange(e.target.value)}
                      placeholder={t('iv.answer_placeholder')} disabled={evaluating} />
                    {speechSupported && (
                      <motion.button type="button" className={`iv-voice-btn ${isListening ? 'iv-voice-active' : ''}`}
                        onClick={toggleVoice} whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
                        {isListening ? <MicOff size={18} /> : <Mic size={18} />}
                      </motion.button>
                    )}
                  </div>
                  {isListening && <div className="iv-listening-indicator"><span className="iv-listening-dot" /> {t('iv.listening')}</div>}
                  <div className="iv-answer-meter" aria-hidden="true">
                    <span style={{ width: `${answerGoalPercent}%` }} />
                  </div>
                  <div className="iv-answer-footer">
                    <span className="iv-word-count">{answerWords} {t('iv.words')} - {answerMinutes} {t('iv.minutes')}</span>
                    <span className="iv-autosave"><Save size={12} /> {t('iv.draft_saved')}</span>
                    <div className="iv-answer-actions">
                      <button type="button" className="iv-nav-btn" onClick={handleBackToQuestions}>{t('iv.back_to_list')}</button>
                      <motion.button type="button" className="iv-submit-answer-btn" disabled={!userAnswer.trim() || evaluating}
                        onClick={handleSubmitAnswer} whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
                        {evaluating ? (<><span className="iv-spinner" /> {t('iv.evaluating')}</>) : (<><Send size={16} /> {t('iv.submit_answer')}</>)}
                      </motion.button>
                    </div>
                  </div>
                </div>
              </div>
              <aside className="iv-session-panel">
                <div className="iv-side-section">
                  <h3><ListChecks size={15} /> {t('iv.session_queue')}</h3>
                  <div className="iv-question-rail">
                    {questions.map((q, idx) => {
                      const answered = answeredQuestions[idx]
                      return (
                        <button
                          key={idx}
                          type="button"
                          className={`iv-rail-btn ${idx === currentIdx ? 'iv-rail-current' : ''} ${answered ? 'iv-rail-done' : ''}`}
                          onClick={() => handleStartPractice(idx)}
                          title={q.question}
                        >
                          {answered ? <Check size={12} /> : idx + 1}
                        </button>
                      )
                    })}
                  </div>
                </div>
                <div className="iv-side-section">
                  <h3><Target size={15} /> {t('iv.answer_targets')}</h3>
                  <div className="iv-target-row">
                    <span>{t('iv.depth')}</span>
                    <strong>{answerWords}/90</strong>
                  </div>
                  <div className="iv-side-meter"><span style={{ width: `${answerGoalPercent}%` }} /></div>
                  <div className="iv-structure-list">
                    <span>{t('iv.star_situation')}</span>
                    <span>{t('iv.star_action')}</span>
                    <span>{t('iv.star_result')}</span>
                    <span>{t('iv.star_metric')}</span>
                  </div>
                </div>
              </aside>
              </div>
            </motion.div>
          )}

          {/* ════════ PHASE: REVIEW ════════ */}
          {phase === 'review' && evaluation && currentQ && (
            <motion.div key="review" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
              <div className="iv-review-card">
                {/* Score */}
                <div className="iv-review-score-section">
                  <div className={`iv-score-ring ${evaluation.score >= 7 ? 'iv-score-good' : evaluation.score >= 4 ? 'iv-score-mid' : 'iv-score-low'}`}>
                    <span className="iv-score-value">{evaluation.score}</span>
                    <span className="iv-score-max">/10</span>
                  </div>
                  <p className="iv-review-feedback">{evaluation.feedback}</p>
                </div>

                {/* Question recap */}
                <div className="iv-review-question">
                  <span className="iv-review-q-label">{t('iv.question_label')}</span>
                  <p>{currentQ.question}</p>
                </div>

                {/* Your answer */}
                <div className="iv-review-your-answer">
                  <span className="iv-review-a-label">{t('iv.your_answer_label')}</span>
                  <p>{userAnswer}</p>
                </div>

                {/* Strengths & Improvements */}
                <div className="iv-review-grid">
                  <div className="iv-review-box iv-review-strengths">
                    <h4><ThumbsUp size={14} /> {t('iv.strengths')}</h4>
                    <ul>{(evaluation.strengths || []).map((s, i) => <li key={i}>{s}</li>)}</ul>
                  </div>
                  <div className="iv-review-box iv-review-improvements">
                    <h4><TrendingUp size={14} /> {t('iv.improvements')}</h4>
                    <ul>{(evaluation.improvements || []).map((s, i) => <li key={i}>{s}</li>)}</ul>
                  </div>
                </div>

                {/* Sample answer */}
                {evaluation.sample_answer && (
                  <div className="iv-review-sample">
                    <div className="iv-review-sample-head">
                      <h4><Award size={14} /> {t('iv.sample_answer')}</h4>
                      <button type="button" className="iv-mini-action" onClick={handleCopySampleAnswer}>
                        <Copy size={13} /> {t('iv.copy_sample')}
                      </button>
                    </div>
                    <p>{evaluation.sample_answer}</p>
                  </div>
                )}

                {/* Navigation */}
                <div className="iv-review-nav">
                  <div className="iv-review-nav-left">
                    <button type="button" className="iv-nav-btn" onClick={handleBackToQuestions}>{t('iv.back_to_list')}</button>
                    <button type="button" className="iv-nav-btn" onClick={handleRetryCurrent}><RefreshCw size={14} /> {t('iv.retry_answer')}</button>
                  </div>
                  <div className="iv-review-nav-arrows">
                    {currentIdx > 0 && <button type="button" className="iv-nav-btn" onClick={handlePrevQuestion}><ChevronLeft size={14} /> {t('iv.prev')}</button>}
                    {currentIdx < questions.length - 1 && (
                      <motion.button type="button" className="iv-submit-answer-btn" onClick={handleNextQuestion} whileHover={{ scale: 1.03 }}>
                        {t('iv.next_question')} <ChevronRight size={14} />
                      </motion.button>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          </AnimatePresence>

          {/* ── Empty State ── */}
          {phase === 'setup' && !loading && !cvText && (
            <motion.div className="iv-empty" variants={itemVariants}>
              <MessageSquare size={40} strokeWidth={1.2} />
              <h3>{t('iv.empty_title')}</h3>
              <p>{t('iv.empty_desc')}</p>
            </motion.div>
          )}

        </motion.div>
      </main>
    </div>
  )
}
