import React from 'react';
import BlogPostForm from '../components/BlogPostForm';
import Navbar from '../components/Navbar';
import MembershipBadge from '../components/MembershipBadge';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../i18n/LanguageContext';
import './BlogPage.social.css';
export default function BlogPage() {
  const { user, plan, role } = useAuth();
  const { t, lang } = useLanguage();
  const userName = user?.email?.split('@')[0] || 'Anonim';
  const [messages, setMessages] = React.useState([
    { id: 1, user: { name: 'ozkan', plan: 'premium', role: 'recruiter' }, text: t('blog.welcome') || 'Hoş geldiniz! Blog ve sohbet burada.' },
    { id: 2, user: { name: 'admin', plan: 'admin', role: 'admin' }, text: t('blog.badge_info') || 'Her mesajda üyelik badge görünecek.' }
  ]);
  const [input, setInput] = React.useState('');
  const [lastSent, setLastSent] = React.useState(0);

  function handleSend(e) {
    e.preventDefault();
    const now = Date.now();
    if (!input.trim()) return;
    if (now - lastSent < 30000) return;
    setMessages([...messages, {
      id: now,
      user: { name: userName, plan, role },
      text: input.trim()
    }]);
    setInput('');
    setLastSent(now);
  }

  const canSend = input.trim() && Date.now() - lastSent > 30000;

  function handleDelete(id, user) {
    setMessages(messages.filter(msg => msg.id !== id));
  }

  return (
    <>
      <Navbar />
      <main className="blog-page" id="main-content">
        <section className="blog-header">
          <h1>{t('blog.title') || 'Blog & Sohbet'}</h1>
          <p className="blog-subtitle">{t('blog.welcome') || 'Hoş geldiniz! Blog ve sohbet burada.'}</p>
        </section>
        <section className="blog-post-section">
          <BlogPostForm onPost={post => {
            setMessages([...messages, {
              id: Date.now(),
              user: { name: userName, plan, role },
              text: post.text,
              image: post.image ? URL.createObjectURL(post.image) : null
            }]);
          }} />
        </section>
        <section className="blog-feed">
          {messages.slice().reverse().map(msg => (
            <div key={msg.id} className="blog-card">
              <div className="blog-card-header">
                {/* Avatar placeholder */}
                <div className="blog-card-avatar" style={{width:32,height:32,borderRadius:'50%',background:'#e3e3e3',display:'flex',alignItems:'center',justifyContent:'center',fontWeight:700,fontSize:'1.1rem'}}>
                  {msg.user.name[0] ? msg.user.name[0].toUpperCase() : 'A'}
                </div>
                <span className="blog-card-user">{msg.user.name}</span>
                <span className="blog-card-badge"><MembershipBadge plan={msg.user.plan} role={msg.user.role} /></span>
                <span className="blog-card-date">{new Date(msg.id).toLocaleString()}</span>
              </div>
              <div className="blog-card-text">{msg.text}</div>
              {msg.image && (
                <img className="blog-card-image" src={msg.image} alt="Post görseli" />
              )}
              {(role === 'admin' || msg.user.name === userName) && (
                <button className="blog-card-delete" onClick={() => handleDelete(msg.id, msg.user)} title={t('blog.delete') || 'Sil'}>🗑</button>
              )}
              {/* Etkileşim butonları (dummy) */}
              <div className="blog-card-actions" style={{display:'flex',gap:'16px',marginTop:'8px'}}>
                <button style={{background:'none',border:'none',color:'#1976d2',cursor:'pointer'}}>👍</button>
                <button style={{background:'none',border:'none',color:'#1976d2',cursor:'pointer'}}>💬</button>
                <button style={{background:'none',border:'none',color:'#1976d2',cursor:'pointer'}}>🔗</button>
              </div>
            </div>
          ))}
        </section>
        <section className="blog-input-section">
          <form onSubmit={handleSend} style={{display:'flex',gap:'8px',marginTop:'16px'}}>
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder={canSend ? (t('blog.input_placeholder') || 'اكتب رسالتك...') : (t('blog.wait') || 'انتظر 30 ثانية...')}
              autoFocus
              disabled={!canSend}
            />
            <button type="submit" disabled={!canSend}>{t('blog.send') || 'إرسال'}</button>
          </form>
        </section>
      </main>
    </>
  );
}
