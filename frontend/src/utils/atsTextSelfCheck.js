const SECTION_RULES = [
  {
    id: 'experience',
    label: 'Deneyim',
    weight: 8,
    pattern: /(^|\n)[ \t]*(iş[ \t]+deneyimi|profesyonel[ \t]+deneyim|deneyim|work[ \t]+experience|experience)[ \t]*:?[ \t]*($|\n)/imu,
  },
  {
    id: 'education',
    label: 'Eğitim',
    weight: 5,
    pattern: /(^|\n)[ \t]*(eğitim|öğrenim|education|academic[ \t]+background)[ \t]*:?[ \t]*($|\n)/imu,
  },
  {
    id: 'skills',
    label: 'Beceriler',
    weight: 7,
    pattern: /(^|\n)[ \t]*(beceriler|teknik[ \t]+beceriler|yetkinlikler|skills|technical[ \t]+skills|competencies)[ \t]*:?[ \t]*($|\n)/imu,
  },
  {
    id: 'summary',
    label: 'Özet',
    weight: 5,
    pattern: /(^|\n)[ \t]*(profesyonel[ \t]+özet|kariyer[ \t]+özeti|özet|profil|professional[ \t]+summary|summary|profile)[ \t]*:?[ \t]*($|\n)/imu,
  },
  {
    id: 'projects',
    label: 'Projeler veya sertifikalar',
    weight: 5,
    pattern: /(^|\n)[ \t]*(projeler|sertifikalar|projects|certifications?)[ \t]*:?[ \t]*($|\n)/imu,
  },
]

const ACTION_VERBS = [
  'geliştirdi', 'tasarladı', 'uyguladı', 'iyileştirdi', 'azalttı', 'artırdı',
  'yönetti', 'analiz etti', 'oluşturdu', 'otomatikleştirdi', 'koordine etti',
  'developed', 'designed', 'implemented', 'improved', 'reduced', 'increased',
  'managed', 'analysed', 'analyzed', 'created', 'automated', 'coordinated',
]

export const SAMPLE_ATS_TEXT = `PROFESYONEL ÖZET
React ve Python tabanlı ürünlerde kullanıcı akışları ve API entegrasyonları geliştiren yazılım geliştirici.

İŞ DENEYİMİ
Yazılım Geliştirici — Örnek Teknoloji, 2023–2026
- Başvuru formundaki gereksiz adımları azaltarak tamamlama oranını %18 artırdı.
- Haftalık hata raporunu otomatikleştirdi ve ekip için yaklaşık 4 saatlik manuel işi kaldırdı.
- 6 kişilik ürün ekibiyle erişilebilir arayüz bileşenleri geliştirdi.

PROJELER
CV metin kontrol aracı
- PDF'den çıkarılan metindeki bölüm başlıklarını ve okuma sırasını kontrol eden bir prototip oluşturdu.

TEKNİK BECERİLER
React, JavaScript, Python, REST API, PostgreSQL, Vitest

EĞİTİM
Bilgisayar Mühendisliği Lisans Programı, 2019–2023

İLETİŞİM
ornek.aday@example.com | +90 555 000 00 00`

export const CASE_STUDY = {
  before: 'Raporlardan ve müşterilerle iletişimden sorumluydum.',
  after: 'CRM kayıtlarından haftalık destek raporu oluşturdu; tekrar eden 6 sorun türünü ürün ekibine aktararak takip süresini kısalttı.',
}

function wordCount(text) {
  return (text.match(/[\p{L}\p{N}]+(?:['’.-][\p{L}\p{N}]+)*/gu) || []).length
}

function statusFromScore(earned, maximum, warningThreshold = 0.45) {
  if (earned >= maximum) return 'pass'
  if (earned >= maximum * warningThreshold) return 'warning'
  return 'fail'
}

export function analyzeATSText(input = '') {
  const text = String(input).replace(/\r\n?/g, '\n').trim()
  if (!text) {
    return {
      score: 0,
      wordCount: 0,
      checks: [],
      recommendations: [],
      detectedSections: [],
      actionVerbCount: 0,
      metricCount: 0,
    }
  }

  const lines = text.split('\n').map((line) => line.trimEnd())
  const words = wordCount(text)
  const normalizedText = text.toLocaleLowerCase('tr-TR').replaceAll('ı', 'i')
  const detectedSections = SECTION_RULES.filter((rule) => rule.pattern.test(normalizedText))
  const sectionScore = detectedSections.reduce((sum, rule) => sum + rule.weight, 0)

  const hasEmail = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/iu.test(text)
  const hasPhone = /(?:\+?\d[\d\s().-]{8,}\d)/u.test(text)
  const contactScore = (hasEmail ? 8 : 0) + (hasPhone ? 7 : 0)

  const longLineCount = lines.filter((line) => line.length > 120).length
  const tableCharacterCount = (text.match(/[|\t]/g) || []).length
  const layoutPenalty = Math.min(12, longLineCount * 3) + Math.min(8, Math.floor(tableCharacterCount / 3) * 2)
  const layoutScore = Math.max(0, 20 - layoutPenalty)

  let lengthScore = 3
  if (words >= 150 && words <= 1000) lengthScore = 15
  else if ((words >= 80 && words < 150) || (words > 1000 && words <= 1300)) lengthScore = 8

  const lowerText = text.toLocaleLowerCase('tr-TR')
  const actionVerbCount = ACTION_VERBS.filter((verb) => lowerText.includes(verb)).length
  const metricMatches = text.match(/(?:%\s?\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s?%|\b\d+\s*(?:kişi|kişilik|saat|gün|hafta|ay|kullanıcı|müşteri|proje|person|people|hours?|days?|weeks?|months?|users?|customers?|projects?)\b)/giu) || []
  const metricCount = metricMatches.length
  const evidenceScore = Math.min(10, metricCount * 5) + Math.min(10, actionVerbCount * 2)

  const score = sectionScore + contactScore + layoutScore + lengthScore + evidenceScore
  const checks = [
    {
      id: 'sections',
      label: 'Standart bölüm başlıkları',
      status: statusFromScore(sectionScore, 30),
      detail: detectedSections.length
        ? `${detectedSections.map((item) => item.label).join(', ')} algılandı.`
        : 'Deneyim, eğitim, beceriler, özet veya proje başlığı algılanamadı.',
      earned: sectionScore,
      maximum: 30,
    },
    {
      id: 'contact',
      label: 'Seçilebilir iletişim bilgisi',
      status: statusFromScore(contactScore, 15),
      detail: `E-posta ${hasEmail ? 'bulundu' : 'bulunamadı'}; telefon ${hasPhone ? 'bulundu' : 'bulunamadı'}.`,
      earned: contactScore,
      maximum: 15,
    },
    {
      id: 'length',
      label: 'Metin kapsamı',
      status: statusFromScore(lengthScore, 15),
      detail: `${words} kelime algılandı. Bu yalnızca okunabilir metin için bir ön kontroldür; ideal uzunluk role göre değişir.`,
      earned: lengthScore,
      maximum: 15,
    },
    {
      id: 'layout',
      label: 'Düz metin okuma düzeni',
      status: statusFromScore(layoutScore, 20, 0.7),
      detail: `${longLineCount} çok uzun satır ve ${tableCharacterCount} tablo/ayırıcı karakteri algılandı.`,
      earned: layoutScore,
      maximum: 20,
    },
    {
      id: 'evidence',
      label: 'Eylem ve ölçülebilir kanıt',
      status: statusFromScore(evidenceScore, 20),
      detail: `${actionVerbCount} farklı eylem ifadesi ve ${metricCount} ölçüm/kapsam ifadesi algılandı.`,
      earned: evidenceScore,
      maximum: 20,
    },
  ]

  const recommendations = []
  if (detectedSections.length < 4) recommendations.push('Deneyim, eğitim, beceriler ve özet/proje bölümlerini açık metin başlıklarıyla ayırın.')
  if (!hasEmail || !hasPhone) recommendations.push('İletişim bilgisini görsel veya üstbilgi yerine seçilebilir gövde metninde gösterin.')
  if (words < 150) recommendations.push('Görev adları yerine kapsamı ve katkıyı açıklayan deneyim maddeleri ekleyin.')
  if (words > 1300) recommendations.push('Hedef rolle ilgisiz tekrarları çıkarın; her maddeyi tek bir katkıya odaklayın.')
  if (longLineCount || tableCharacterCount > 6) recommendations.push('Kopyalanan düz metindeki sütun ve tablo sırasını kontrol edin; birleşen satırları sadeleştirin.')
  if (actionVerbCount < 2 || metricCount < 1) recommendations.push('En az birkaç deneyim maddesinde eylemi, bağlamı ve doğrulanabilir sonucu birlikte yazın.')

  return {
    score,
    wordCount: words,
    checks,
    recommendations,
    detectedSections: detectedSections.map((item) => item.id),
    actionVerbCount,
    metricCount,
  }
}
