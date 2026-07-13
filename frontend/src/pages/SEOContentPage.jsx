import React from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, CheckCircle2, Clock3, FileSearch, ShieldCheck } from 'lucide-react'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'

export default function SEOContentPage({ page }) {
  return (
    <div className="seo-page">
      <Navbar />
      <main id="main-content">
        <header className="seo-hero">
          <div className="seo-container seo-hero-grid">
            <div className="seo-hero-copy">
              <p className="seo-eyebrow">{page.eyebrow}</p>
              <h1>{page.title}</h1>
              <p className="seo-lead">{page.intro}</p>
              <div className="seo-hero-actions">
                <Link to="/register" className="btn-primary">
                  CV’mi ücretsiz analiz et <ArrowRight size={17} aria-hidden="true" />
                </Link>
                <Link to="/ats-cv-kontrol/" className="btn-outline">
                  ATS rehberini incele
                </Link>
              </div>
              <div className="seo-meta" aria-label="İçerik bilgileri">
                <span><Clock3 size={15} aria-hidden="true" /> {page.readingTime}</span>
                <span>Güncellendi: 14 Temmuz 2026</span>
              </div>
            </div>

            <div className="seo-product-visual" aria-label="CV Analyzer değerlendirme özeti">
              <div className="seo-product-head">
                <span><FileSearch size={18} aria-hidden="true" /> Analiz özeti</span>
                <strong>84/100</strong>
              </div>
              <div className="seo-score-track" aria-hidden="true"><span /></div>
              <div className="seo-product-checks">
                <p><CheckCircle2 size={17} /> İletişim bilgileri okunabilir</p>
                <p><CheckCircle2 size={17} /> Standart bölüm başlıkları</p>
                <p><ShieldCheck size={17} /> Güvenli ATS metin çıktısı</p>
              </div>
              <div className="seo-product-note">
                Öneriler, CV’de bulunan kanıtlara ve hedef ilanın gereksinimlerine göre açıklanır.
              </div>
            </div>
          </div>
        </header>

        <nav className="seo-jump-band" aria-label="Sayfa özeti">
          <div className="seo-container seo-highlight-grid">
            {page.highlights.map((item) => (
              <span key={item}><CheckCircle2 size={16} aria-hidden="true" /> {item}</span>
            ))}
          </div>
        </nav>

        <article className="seo-container seo-article">
          <div className="seo-article-main">
            {page.sections.map((section) => (
              <section key={section.heading}>
                <h2>{section.heading}</h2>
                {section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
                {section.bullets && (
                  <ul>
                    {section.bullets.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                )}
              </section>
            ))}

            <section className="seo-faq" aria-labelledby={`${page.slug}-faq-title`}>
              <p className="seo-eyebrow">Sık sorulan sorular</p>
              <h2 id={`${page.slug}-faq-title`}>{page.title} hakkında sorular</h2>
              {page.faq.map((item) => (
                <details key={item.question}>
                  <summary>{item.question}</summary>
                  <p>{item.answer}</p>
                </details>
              ))}
            </section>
          </div>

          <aside className="seo-related" aria-label="İlgili CV rehberleri">
            <h2>Sonraki adım</h2>
            <p>CV’nizi hazırladıktan sonra metin akışını ve ATS sinyallerini gerçek dosyanız üzerinden kontrol edin.</p>
            <Link to="/cv-analiz/">CV analiz rehberi <ArrowRight size={15} /></Link>
            <Link to="/ats-uyumlu-cv/">ATS uyumlu CV hazırlama <ArrowRight size={15} /></Link>
            <Link to="/rehber/cv-nasil-hazirlanir/">CV hazırlama rehberi <ArrowRight size={15} /></Link>
            <Link to="/cv-ornekleri/yeni-mezun/">Yeni mezun CV örneği <ArrowRight size={15} /></Link>
          </aside>
        </article>

        <section className="seo-final-cta">
          <div className="seo-container">
            <div>
              <p className="seo-eyebrow">Dosyanız üzerinden kontrol edin</p>
              <h2>CV’nizin nasıl okunduğunu görün</h2>
              <p>ATS görünümü, iş ilanı eşleşmesi ve uygulanabilir geliştirme önerileri tek analizde.</p>
            </div>
            <Link to="/register" className="btn-primary">
              Ücretsiz hesap oluştur <ArrowRight size={17} aria-hidden="true" />
            </Link>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  )
}
