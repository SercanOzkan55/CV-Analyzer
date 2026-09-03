import React, { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  FileText,
  FlaskConical,
  LockKeyhole,
  RotateCcw,
  ScanText,
  ShieldCheck,
  Sparkles,
  XCircle,
} from 'lucide-react'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { analyzeATSText, CASE_STUDY, SAMPLE_ATS_TEXT } from '../utils/atsTextSelfCheck'

const STATUS_ICON = {
  pass: CheckCircle2,
  warning: AlertTriangle,
  fail: XCircle,
}

function scoreLabel(score) {
  if (score >= 80) return 'Güçlü başlangıç'
  if (score >= 55) return 'Gözden geçirilmeli'
  return 'Temel eksikler var'
}

export default function ATSTextCheckPage() {
  const [text, setText] = useState('')
  const result = useMemo(() => analyzeATSText(text), [text])
  const hasText = text.trim().length > 0

  return (
    <div className="seo-page ats-lab-page">
      <Navbar />
      <main id="main-content">
        <header className="seo-hero ats-lab-hero">
          <div className="seo-container seo-hero-grid">
            <div className="seo-hero-copy">
              <p className="seo-eyebrow">Herkese açık ve ücretsiz araç</p>
              <h1>ATS Metin Ön Kontrolü</h1>
              <p className="seo-lead">
                CV’nizden kopyaladığınız düz metni standart bölüm başlıkları, iletişim bilgileri,
                okuma düzeni ve kanıta dayalı deneyim anlatımı açısından tarayın. Sonuç tarayıcınızda
                hesaplanır; metin sunucuya gönderilmez.
              </p>
              <div className="ats-lab-trust" role="list" aria-label="Araç özellikleri">
                <span role="listitem"><LockKeyhole size={17} aria-hidden="true" /> Yerel analiz</span>
                <span role="listitem"><ScanText size={17} aria-hidden="true" /> Açıklanabilir kontroller</span>
                <span role="listitem"><ShieldCheck size={17} aria-hidden="true" /> İşe alınma vaadi yok</span>
              </div>
            </div>

            <aside className="ats-lab-method-card" aria-labelledby="ats-lab-method-title">
              <FlaskConical size={24} aria-hidden="true" />
              <h2 id="ats-lab-method-title">Bu puan neyi gösterir?</h2>
              <p>
                Beş görünür kontrolün toplamıdır: bölüm yapısı 30, iletişim 15, metin kapsamı 15,
                okuma düzeni 20 ve kanıt anlatımı 20 puan. Bir işverenin özel ATS sıralamasını taklit etmez.
              </p>
              <Link to="/metodoloji/cv-analizi/">
                Ürün metodolojisini inceleyin <ArrowRight size={16} aria-hidden="true" />
              </Link>
            </aside>
          </div>
        </header>

        <section className="seo-container ats-lab-workspace" aria-labelledby="ats-lab-input-title">
          <div className="ats-lab-editor-card">
            <div className="ats-lab-section-heading">
              <div>
                <p className="seo-eyebrow">1. Metni ekleyin</p>
                <h2 id="ats-lab-input-title">PDF veya DOCX içeriğini düz metin olarak yapıştırın</h2>
              </div>
              <span>{result.wordCount} kelime</span>
            </div>
            <label className="ats-lab-label" htmlFor="ats-text-input">
              CV metni
            </label>
            <textarea
              id="ats-text-input"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="CV’nizdeki metni buraya yapıştırın. Ad, telefon ve e-posta gibi gerçek kişisel bilgileri örnek değerlerle değiştirebilirsiniz."
              spellCheck="false"
            />
            <div className="ats-lab-editor-actions">
              <button type="button" className="btn-primary" onClick={() => setText(SAMPLE_ATS_TEXT)}>
                <Sparkles size={17} aria-hidden="true" /> Kurgusal örneği yükle
              </button>
              <button type="button" className="btn-outline" onClick={() => setText('')} disabled={!hasText}>
                <RotateCcw size={17} aria-hidden="true" /> Temizle
              </button>
            </div>
            <p className="ats-lab-privacy-note">
              <LockKeyhole size={15} aria-hidden="true" /> Yazdığınız CV metni herhangi bir ağ isteğine eklenmez ve kaydedilmez.
            </p>
          </div>

          <div className="ats-lab-results-card" aria-live="polite" aria-atomic="false">
            <div className="ats-lab-section-heading">
              <div>
                <p className="seo-eyebrow">2. Bulguları inceleyin</p>
                <h2>Ön kontrol sonucu</h2>
              </div>
              {hasText && (
                <div className={`ats-lab-score ats-lab-score-${result.score >= 80 ? 'pass' : result.score >= 55 ? 'warning' : 'fail'}`}>
                  <strong>{result.score}</strong><span>/100</span>
                </div>
              )}
            </div>

            {!hasText ? (
              <div className="ats-lab-empty">
                <FileText size={32} aria-hidden="true" />
                <h3>Sonuç için metin ekleyin</h3>
                <p>İsterseniz kurgusal örneği yükleyerek her kontrolün nasıl açıklandığını görebilirsiniz.</p>
              </div>
            ) : (
              <>
                <p className="ats-lab-score-summary">{scoreLabel(result.score)}. Puan yerine her bulgunun açıklamasını önceliklendirin.</p>
                <div className="ats-lab-checks">
                  {result.checks.map((check) => {
                    const Icon = STATUS_ICON[check.status]
                    return (
                      <article className={`ats-lab-check ats-lab-check-${check.status}`} key={check.id}>
                        <Icon size={20} aria-hidden="true" />
                        <div>
                          <div className="ats-lab-check-title">
                            <h3>{check.label}</h3>
                            <span>{check.earned}/{check.maximum}</span>
                          </div>
                          <p>{check.detail}</p>
                        </div>
                      </article>
                    )
                  })}
                </div>
                {result.recommendations.length > 0 && (
                  <section className="ats-lab-recommendations" aria-labelledby="ats-lab-recommendations-title">
                    <h3 id="ats-lab-recommendations-title">Öncelikli düzenlemeler</h3>
                    <ol>
                      {result.recommendations.map((item) => <li key={item}>{item}</li>)}
                    </ol>
                  </section>
                )}
              </>
            )}
          </div>
        </section>

        <article className="seo-container ats-lab-evidence">
          <section aria-labelledby="ats-case-title">
            <p className="seo-eyebrow">Kurgusal vaka çalışması</p>
            <h2 id="ats-case-title">Genel görev cümlesini doğrulanabilir kanıta dönüştürme</h2>
            <p>
              Aşağıdaki örnek gerçek bir adaya ait değildir. Amaç, yalnızca olumlu görünen bir cümle ile
              okuyucunun doğrulayabileceği kapsamı gösteren bir cümle arasındaki farkı açıklamaktır.
            </p>
            <div className="ats-lab-comparison">
              <div>
                <span>Önce</span>
                <p>{CASE_STUDY.before}</p>
                <ul>
                  <li>Eylemin kapsamı belirsiz.</li>
                  <li>Üretilen çıktı veya kullanıcı görünmüyor.</li>
                  <li>CV’nin devamında doğrulanacak ayrıntı yok.</li>
                </ul>
              </div>
              <div>
                <span>Sonra</span>
                <p>{CASE_STUDY.after}</p>
                <ul>
                  <li>Veri kaynağı ve çıktı açık.</li>
                  <li>Kapsam, temsili bir sayı ile görünür.</li>
                  <li>Sonuç abartılı bir işe alınma vaadine dönüşmüyor.</li>
                </ul>
              </div>
            </div>
          </section>

          <section aria-labelledby="ats-lab-limits-title">
            <p className="seo-eyebrow">Kapsam ve sınırlar</p>
            <h2 id="ats-lab-limits-title">Bu kontrolün bilinçli olarak yapmadıkları</h2>
            <div className="ats-lab-limit-grid">
              <div><strong>Dosyayı ayrıştırmaz</strong><p>Yalnızca yapıştırdığınız metni değerlendirir; PDF sütunlarını veya görsel katmanını göremez.</p></div>
              <div><strong>İşe alınma olasılığı üretmez</strong><p>Puan bir işveren kararı, mülakat ihtimali veya evrensel ATS geçiş eşiği değildir.</p></div>
              <div><strong>Gerçekleri doğrulamaz</strong><p>Yazdığınız şirket, tarih, görev ve ölçümlerin doğruluğunu sizin kontrol etmeniz gerekir.</p></div>
              <div><strong>Özel ATS ürününü taklit etmez</strong><p>İşveren sistemlerinin ayrıştırma ve sıralama davranışları birbirinden farklıdır.</p></div>
            </div>
          </section>

          <section className="ats-lab-next" aria-labelledby="ats-lab-next-title">
            <div>
              <p className="seo-eyebrow">Sonraki kontrol</p>
              <h2 id="ats-lab-next-title">Metin sırası doğruysa CV’nin tamamını değerlendirin</h2>
              <p>Dosya ayrıştırması, iş ilanı eşleşmesi ve bölüm bazlı açıklamalar için tam analiz çalışma alanına geçebilirsiniz.</p>
            </div>
            <div className="ats-lab-next-actions">
              <Link className="btn-primary" to="/register">Ücretsiz hesap oluştur <ArrowRight size={17} aria-hidden="true" /></Link>
              <Link className="btn-outline" to="/rehber/">CV rehberlerini incele</Link>
            </div>
          </section>
        </article>
      </main>
      <Footer />
    </div>
  )
}
