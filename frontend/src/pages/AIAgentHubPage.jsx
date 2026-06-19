import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Sparkles, Send, Bot, User, GraduationCap, TrendingUp,
  Code2, ArrowLeft, History, FileText, ChevronRight,
  MessageSquare, Loader2, AlertCircle, RefreshCw, X
} from 'lucide-react'
import Navbar from '../components/Navbar'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { agentChat, listCvVersions, getCvVersion } from '../api'

const AGENT_TYPES = [
  {
    id: 'recruiter',
    name: 'Selin',
    title: 'HR Recruiter Agent',
    color: 'emerald',
    themeColor: '#10b981',
    icon: GraduationCap,
    desc: 'Expert in resume screening, candidate fit, and behavioral evaluation.',
    tagline: 'Let\'s test if you\'d pass a first HR interview round.',
    suggestions: [
      'Screen my CV for a Developer position',
      'What HR questions should I expect for my target role?',
      'Identify potential red flags or gaps in my experience'
    ]
  },
  {
    id: 'tech_lead',
    name: 'Devrim',
    title: 'Tech Lead Agent',
    color: 'blue',
    themeColor: '#3b82f6',
    icon: Code2,
    desc: 'Senior Architect. Tech stack review, system design, and coding standards.',
    tagline: 'Tell me about your tech stack and architectural challenges.',
    suggestions: [
      'Ask me a system design interview question',
      'Review my technical skill alignment on my CV',
      'How should I explain technical debt to stakeholders?'
    ]
  },
  {
    id: 'coach',
    name: 'Canan',
    title: 'Career Coach Agent',
    color: 'purple',
    themeColor: '#8b5cf6',
    icon: Sparkles,
    desc: 'Empathetic advisor. CV narrative builder, summary rewrite, and roadmaps.',
    tagline: 'Let\'s align your CV summary with your dream target role.',
    suggestions: [
      'Help me rewrite my CV summary to sound more senior',
      'Suggest a 6-month career roadmap to learn system design',
      'Which ATS keywords should I add to my profile?'
    ]
  }
]

export default function AIAgentHubPage() {
  const { token } = useAuth()
  const { t } = useLanguage()

  const [selectedAgent, setSelectedAgent] = useState(AGENT_TYPES[0])
  const [messages, setMessages] = useState([])
  const [inputText, setInputText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // CV contexts
  const [cvList, setCvList] = useState([])
  const [selectedCvId, setSelectedCvId] = useState('')
  const [cvText, setCvText] = useState('')
  const [cvLoading, setCvLoading] = useState(false)
  const [showCvPanel, setShowCvPanel] = useState(false)

  const messagesEndRef = useRef(null)

  // Load CV versions on mount
  useEffect(() => {
    async function loadCVs() {
      try {
        const res = await listCvVersions(token)
        if (res?.items?.length > 0) {
          setCvList(res.items)
          // Default select the latest
          setSelectedCvId(res.items[0].id)
          fetchFullCv(res.items[0].id)
        }
      } catch (err) {
        console.error('Failed to load CV versions', err)
      }
    }
    loadCVs()
  }, [token])

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function fetchFullCv(id) {
    if (!id) return
    try {
      setCvLoading(true)
      const res = await getCvVersion(token, id)
      setCvText(res?.cv_text || res?.optimized_cv_text || '')
    } catch (err) {
      console.error('Failed to fetch CV text', err)
    } finally {
      setCvLoading(false)
    }
  }

  // Handle CV change
  function handleCvChange(e) {
    const id = e.target.value
    setSelectedCvId(id)
    fetchFullCv(id)
  }

  // Send message
  async function handleSend(textToSend) {
    const text = textToSend || inputText
    if (!text.trim() || loading) return

    setError(null)
    const userMsg = { role: 'user', content: text }
    const updatedMessages = [...messages, userMsg]

    setMessages(updatedMessages)
    if (!textToSend) setInputText('')

    try {
      setLoading(true)
      // Call backend agent chat endpoint
      const res = await agentChat(token, {
        message: text,
        agent_type: selectedAgent.id,
        cv_context: cvText,
        history: messages.slice(-10) // Send last 10 messages for context
      })

      if (res?.response) {
        setMessages(prev => [...prev, { role: 'assistant', content: res.response }])
      } else {
        throw new Error('Invalid response from agent')
      }
    } catch (err) {
      setError(err.message || 'Failed to get a response from agent')
    } finally {
      setLoading(false)
    }
  }

  function handleAgentSelect(agent) {
    setSelectedAgent(agent)
    setMessages([]) // Reset chat
    setError(null)
  }

  return (
    <div className="app-container">
      <Navbar />

      <div className="agent-hub-content" style={{ marginTop: '72px', minHeight: 'calc(100vh - 72px)', display: 'flex' }}>
        {/* Left Panel: Agent Selection */}
        <aside className="agent-sidebar" style={{ width: '320px', borderRight: '1px solid var(--surface-border)', padding: '24px', background: 'rgba(255,255,255,0.02)' }}>
          <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={20} className="text-primary" /> AI Agent Hub
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '24px' }}>
            Select a specialized agent powered by Gemini Flash for target review.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {AGENT_TYPES.map((agent) => {
              const IconComp = agent.icon
              const isSelected = selectedAgent.id === agent.id
              return (
                <button
                  key={agent.id}
                  onClick={() => handleAgentSelect(agent)}
                  className={`agent-card ${isSelected ? 'active' : ''}`}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                    padding: '16px',
                    borderRadius: '12px',
                    background: isSelected ? `rgba(${agent.id === 'recruiter' ? '16, 185, 129' : agent.id === 'tech_lead' ? '59, 130, 246' : '139, 92, 246'}, 0.1)` : 'rgba(255,255,255,0.03)',
                    border: isSelected ? `1px solid ${agent.themeColor}` : '1px solid var(--surface-border)',
                    textAlign: 'left',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '8px',
                      background: agent.themeColor,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#fff'
                    }}>
                      <IconComp size={18} />
                    </div>
                    <div>
                      <h3 style={{ fontSize: '15px', fontWeight: 600 }}>{agent.name}</h3>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{agent.title}</span>
                    </div>
                  </div>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: '1.4' }}>{agent.desc}</p>
                </button>
              )
            })}
          </div>

          {/* CV Selector */}
          <div style={{ marginTop: '32px', paddingTop: '24px', borderTop: '1px solid var(--surface-border)' }}>
            <h4 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <FileText size={16} /> CV Context
            </h4>
            {cvList.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <select
                  value={selectedCvId}
                  onChange={handleCvChange}
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid var(--surface-border)',
                    borderRadius: '8px',
                    color: 'inherit',
                    fontSize: '13px'
                  }}
                >
                  {cvList.map((cv) => (
                    <option key={cv.id} value={cv.id}>
                      {cv.version_label} ({cv.match_score}%)
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => setShowCvPanel(!showCvPanel)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    fontSize: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    cursor: 'pointer',
                    alignSelf: 'flex-start'
                  }}
                >
                  {showCvPanel ? 'Hide text view' : 'Show text view'} <ChevronRight size={12} style={{ transform: showCvPanel ? 'rotate(90deg)' : 'none' }} />
                </button>
              </div>
            ) : (
              <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                No CV versions found. Upload a CV on the dashboard to chat with CV context.
              </p>
            )}
          </div>
        </aside>

        {/* Middle Panel: Chat Interface */}
        <main style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
          {/* Header */}
          <header style={{
            padding: '16px 24px',
            borderBottom: '1px solid var(--surface-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'rgba(255,255,255,0.01)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                background: `rgba(${selectedAgent.id === 'recruiter' ? '16, 185, 129' : selectedAgent.id === 'tech_lead' ? '59, 130, 246' : '139, 92, 246'}, 0.15)`,
                border: `1px solid ${selectedAgent.themeColor}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: selectedAgent.themeColor
              }}>
                <selectedAgent.icon size={20} />
              </div>
              <div>
                <h3 style={{ fontSize: '16px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {selectedAgent.name} <span style={{ fontSize: '11px', fontWeight: 400, color: 'var(--text-muted)' }}>({selectedAgent.title})</span>
                </h3>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{selectedAgent.tagline}</p>
              </div>
            </div>
          </header>

          {/* Messages list */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {messages.length === 0 && (
              <div style={{
                margin: 'auto',
                maxWidth: '480px',
                textAlign: 'center',
                padding: '40px 20px',
                borderRadius: '16px',
                background: 'rgba(255,255,255,0.01)',
                border: '1px solid var(--surface-border)'
              }}>
                <div style={{
                  width: '56px',
                  height: '56px',
                  borderRadius: '50%',
                  background: `rgba(${selectedAgent.id === 'recruiter' ? '16, 185, 129' : selectedAgent.id === 'tech_lead' ? '59, 130, 246' : '139, 92, 246'}, 0.1)`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 16px',
                  color: selectedAgent.themeColor
                }}>
                  <MessageSquare size={24} />
                </div>
                <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '8px' }}>
                  Start a conversation with {selectedAgent.name}
                </h3>
                <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '24px' }}>
                  Select one of the quick suggestions below or type your own question regarding your CV and target role.
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {selectedAgent.suggestions.map((s, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSend(s)}
                      style={{
                        padding: '10px 14px',
                        background: 'rgba(255,255,255,0.03)',
                        border: '1px solid var(--surface-border)',
                        borderRadius: '8px',
                        fontSize: '12.5px',
                        color: 'inherit',
                        cursor: 'pointer',
                        textAlign: 'left',
                        transition: 'background 0.2s',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between'
                      }}
                      onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.06)'}
                      onMouseOut={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
                    >
                      <span>{s}</span>
                      <ChevronRight size={14} className="text-muted" />
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, idx) => {
              const isUser = msg.role === 'user'
              return (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '12px',
                    alignSelf: isUser ? 'flex-end' : 'flex-start',
                    maxWidth: '80%',
                    flexDirection: isUser ? 'row-reverse' : 'row'
                  }}
                >
                  <div style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    background: isUser ? 'rgba(255,255,255,0.1)' : selectedAgent.themeColor,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#fff',
                    flexShrink: 0
                  }}>
                    {isUser ? <User size={16} /> : <selectedAgent.icon size={16} />}
                  </div>

                  <div style={{
                    padding: '12px 16px',
                    borderRadius: '12px',
                    background: isUser ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.02)',
                    border: isUser ? '1px solid var(--surface-border)' : `1px solid rgba(${selectedAgent.id === 'recruiter' ? '16, 185, 129' : selectedAgent.id === 'tech_lead' ? '59, 130, 246' : '139, 92, 246'}, 0.2)`,
                    fontSize: '14px',
                    lineHeight: '1.5',
                    whiteSpace: 'pre-wrap'
                  }}>
                    {msg.content}
                  </div>
                </div>
              )
            })}

            {loading && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', alignSelf: 'flex-start' }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: selectedAgent.themeColor,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff'
                }}>
                  <selectedAgent.icon size={16} />
                </div>
                <div style={{
                  padding: '12px 16px',
                  borderRadius: '12px',
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid var(--surface-border)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}>
                  <Loader2 size={16} className="animate-spin text-primary" />
                  <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{selectedAgent.name} is thinking...</span>
                </div>
              </div>
            )}

            {error && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '12px 16px',
                borderRadius: '8px',
                background: 'rgba(220,38,38,0.1)',
                border: '1px solid rgba(220,38,38,0.3)',
                color: '#ef4444',
                fontSize: '13px',
                alignSelf: 'center'
              }}>
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Footer Input Bar */}
          <footer style={{
            padding: '16px 24px',
            borderTop: '1px solid var(--surface-border)',
            background: 'rgba(255,255,255,0.01)'
          }}>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                handleSend()
              }}
              style={{ display: 'flex', gap: '10px' }}
            >
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder={`Ask ${selectedAgent.name} a question...`}
                style={{
                  flex: 1,
                  padding: '12px 16px',
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid var(--surface-border)',
                  borderRadius: '10px',
                  color: 'inherit',
                  fontSize: '14px',
                  outline: 'none'
                }}
              />
              <button
                type="submit"
                disabled={!inputText.trim() || loading}
                style={{
                  padding: '12px 20px',
                  background: selectedAgent.themeColor,
                  color: '#fff',
                  border: 'none',
                  borderRadius: '10px',
                  cursor: 'pointer',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  opacity: (!inputText.trim() || loading) ? 0.6 : 1,
                  transition: 'opacity 0.2s'
                }}
              >
                <Send size={16} /> Send
              </button>
            </form>
          </footer>
        </main>

        {/* Right Panel: CV Context Viewer (Optional drawer) */}
        {showCvPanel && (
          <aside className="cv-preview-panel" style={{
            width: '360px',
            borderLeft: '1px solid var(--surface-border)',
            padding: '24px',
            background: 'rgba(255,255,255,0.01)',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 600 }}>CV Context Text</h3>
              <button
                onClick={() => setShowCvPanel(false)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={16} />
              </button>
            </div>
            {cvLoading ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
                <Loader2 size={24} className="animate-spin text-primary" />
              </div>
            ) : (
              <pre style={{
                flex: 1,
                fontSize: '11px',
                color: 'var(--text-muted)',
                whiteSpace: 'pre-wrap',
                fontFamily: 'monospace',
                background: 'rgba(0,0,0,0.2)',
                padding: '12px',
                borderRadius: '8px',
                border: '1px solid var(--surface-border)',
                overflowX: 'auto'
              }}>
                {cvText || 'CV text is empty. Pick a CV version or edit CV content.'}
              </pre>
            )}
          </aside>
        )}
      </div>
    </div>
  )
}
