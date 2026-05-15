# Hybrid Privacy Model - CV İçeriklerini Tutmama Ama Puanlamaları Tutma

## 🎯 Konsept

**Zero Data Retention + Analytics & Workflow**

```
CV İçeriği: ❌ Saklanmaz (Privacy)
CV Puanlaması: ✅ Saklanır (Analytics)
İş Akışı: ✅ Saklanır (Workflow)
Mail Gönderme: ✅ Otomatik/Manuel
```

## 🏗️ Veritabanı Tasarımı

### Saklanan Veriler

```sql
-- CV içeriği yok, sadece metadata + scoring
CREATE TABLE cv_analyses (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER REFERENCES organizations(id),
    job_id INTEGER REFERENCES recruiter_jobs(id),

    -- CV metadata (içerik yok)
    filename VARCHAR(255),
    file_size INTEGER,
    file_type VARCHAR(10), -- pdf, docx, txt
    processed_at TIMESTAMP DEFAULT NOW(),

    -- Scoring data (analytics için)
    final_score DECIMAL(5,2),
    ats_score DECIMAL(5,2),
    skills_match_score DECIMAL(5,2),
    experience_match_score DECIMAL(5,2),
    education_match_score DECIMAL(5,2),

    -- Structured data (içerik olmadan)
    detected_skills JSONB, -- ["python", "fastapi"]
    experience_years INTEGER,
    education_level VARCHAR(50),

    -- Workflow status
    status VARCHAR(20) DEFAULT 'pending', -- pending, approved, rejected
    recruiter_notes TEXT,
    decision_at TIMESTAMP,
    decision_by INTEGER REFERENCES app_users(id),

    -- Auto-delete after 30 days
    expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '30 days'),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Meslek grubu ortalamaları
CREATE TABLE profession_averages (
    id SERIAL PRIMARY KEY,
    profession VARCHAR(100),
    organization_id INTEGER REFERENCES organizations(id),

    avg_final_score DECIMAL(5,2),
    avg_ats_score DECIMAL(5,2),
    avg_experience_years DECIMAL(5,2),

    sample_size INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT NOW(),

    UNIQUE(profession, organization_id)
);

-- Recruiter actions (onay/red workflow)
CREATE TABLE recruiter_actions (
    id SERIAL PRIMARY KEY,
    cv_analysis_id INTEGER REFERENCES cv_analyses(id),
    recruiter_id INTEGER REFERENCES app_users(id),
    organization_id INTEGER REFERENCES organizations(id),

    action VARCHAR(20), -- approved, rejected, shortlisted
    notes TEXT,
    email_sent BOOLEAN DEFAULT FALSE,
    email_template_id INTEGER,

    created_at TIMESTAMP DEFAULT NOW()
);
```

### Saklanmayan Veriler

❌ **CV İçeriği** - Text, PDF bytes
❌ **Kişisel Bilgiler** - Ad, soyad, email, telefon
❌ **Dosya İçeriği** - Raw file data
❌ **Detaylı CV Data** - Section contents

## 🔄 İş Akışı

### 1. CV İşleme (Zero Retention)

```python
async def process_cv_local(
    file: UploadFile,
    job_id: int,
    organization_id: int,
    api_key: str
) -> Dict[str, Any]:
    """
    CV'yi işle, sonuçları sakla, içeriği sil
    """

    # 1. Dosyayı oku ve işle
    content = await file.read()
    text = extract_text_from_file(content, file.filename)

    # 2. CV analiz et (pipeline)
    analysis_result = await process_cv_pipeline(text, job_description)

    # 3. Sadece scoring data + metadata sakla
    cv_analysis = CVAnalysis(
        organization_id=organization_id,
        job_id=job_id,
        filename=file.filename,
        file_size=len(content),
        file_type=file.filename.split('.')[-1],

        final_score=analysis_result['final_score'],
        ats_score=analysis_result['ats_score'],
        skills_match_score=analysis_result['skills_match'],
        experience_match_score=analysis_result['experience_match'],
        education_match_score=analysis_result['education_match'],

        detected_skills=analysis_result['detected_skills'],
        experience_years=analysis_result['experience_years'],
        education_level=analysis_result['education_level']
    )

    db.add(cv_analysis)
    db.commit()

    # 4. CV içeriğini hemen sil (memory'den)
    del content
    del text
    del analysis_result['cv_text']  # Eğer varsa

    # 5. Meslek ortalamasını güncelle
    update_profession_averages(cv_analysis)

    return {
        'analysis_id': cv_analysis.id,
        'final_score': cv_analysis.final_score,
        'status': 'processed'
    }
```

### 2. Recruiter Dashboard

```jsx
function RecruiterDashboard() {
    const [analyses, setAnalyses] = useState([]);
    const [selectedAnalysis, setSelectedAnalysis] = useState(null);

    useEffect(() => {
        loadAnalyses();
        loadProfessionAverages();
    }, []);

    return (
        <div className="recruiter-dashboard">
            {/* CV Analizleri Listesi */}
            <div className="analyses-list">
                <h2>İşlenen CV'ler</h2>
                {analyses.map(analysis => (
                    <AnalysisCard
                        key={analysis.id}
                        analysis={analysis}
                        onSelect={() => setSelectedAnalysis(analysis)}
                        onAction={handleAction}
                    />
                ))}
            </div>

            {/* Detay Görünümü (içerik yok) */}
            {selectedAnalysis && (
                <AnalysisDetail
                    analysis={selectedAnalysis}
                    onApprove={() => handleApprove(selectedAnalysis)}
                    onReject={() => handleReject(selectedAnalysis)}
                />
            )}

            {/* Meslek Ortalamaları */}
            <ProfessionAveragesChart data={professionAverages} />
        </div>
    );
}
```

### 3. Onay/Red İşlemi

```python
@app.post("/api/v1/recruiter/analyses/{analysis_id}/approve")
async def approve_cv(
    analysis_id: int,
    notes: str = Form(""),
    template_id: int = Form(None),
    recruiter=Depends(recruiter_required),
    db: Session = Depends(get_db)
):
    """
    CV'yi onayla ve otomatik mail gönder
    """

    # Analysis'i bul
    analysis = db.query(CVAnalysis).filter(
        CVAnalysis.id == analysis_id,
        CVAnalysis.organization_id == recruiter['organization_id']
    ).first()

    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Status güncelle
    analysis.status = 'approved'
    analysis.decision_at = datetime.utcnow()
    analysis.decision_by = recruiter['user_id']
    analysis.recruiter_notes = notes

    # Recruiter action kaydet
    action = RecruiterAction(
        cv_analysis_id=analysis_id,
        recruiter_id=recruiter['user_id'],
        organization_id=recruiter['organization_id'],
        action='approved',
        notes=notes,
        email_template_id=template_id
    )
    db.add(action)

    # BURADA MAIL GÖNDERME YOK!
    # Çünkü kişisel bilgiler saklanmıyor
    # Recruiter manuel olarak mail gönderecek

    db.commit()

    return {"message": "CV approved", "analysis_id": analysis_id}
```

## 📊 Analytics & Insights

### Meslek Grubu Ortalamaları

```python
def update_profession_averages(cv_analysis: CVAnalysis):
    """Meslek ortalamasını güncelle"""

    # CV'den meslek çıkar (skills'dan)
    profession = infer_profession(cv_analysis.detected_skills)

    # Mevcut ortalamayı al veya oluştur
    avg = db.query(ProfessionAverage).filter(
        ProfessionAverage.profession == profession,
        ProfessionAverage.organization_id == cv_analysis.organization_id
    ).first()

    if not avg:
        avg = ProfessionAverage(
            profession=profession,
            organization_id=cv_analysis.organization_id
        )
        db.add(avg)

    # Ortalamayı güncelle (rolling average)
    total_scores = avg.avg_final_score * avg.sample_size
    total_scores += cv_analysis.final_score
    avg.sample_size += 1
    avg.avg_final_score = total_scores / avg.sample_size

    # Diğer metrikler için de aynı
    # avg_experience_years, avg_ats_score vs.

    avg.last_updated = datetime.utcnow()
    db.commit()
```

### Dashboard Analytics

```jsx
function AnalyticsDashboard() {
    const [averages, setAverages] = useState([]);
    const [trends, setTrends] = useState([]);

    return (
        <div className="analytics-dashboard">
            {/* Meslek Ortalamaları */}
            <div className="profession-averages">
                <h3>Meslek Grubu Performans Ortalamaları</h3>
                <BarChart data={averages} />
            </div>

            {/* Trend Analizi */}
            <div className="trends">
                <h3>Aylık Trendler</h3>
                <LineChart data={trends} />
            </div>

            {/* İş İlanı Bazlı */}
            <div className="job-performance">
                <h3>İş İlanı Başarı Oranları</h3>
                <JobPerformanceTable />
            </div>
        </div>
    );
}
```

## 📧 Mail Sistemi (Manuel)

### Recruiter Tarafından Mail Gönderme

```jsx
function SendEmailModal({ analysis, onClose }) {
    const [template, setTemplate] = useState('');
    const [customMessage, setCustomMessage] = useState('');
    const [recipientEmail, setRecipientEmail] = useState('');

    // BU ÇOK ÖNEMLİ: Email adresi saklanmıyor!
    // Recruiter manuel olarak girecek

    const handleSend = async () => {
        if (!recipientEmail) {
            alert('Email adresi gerekli!');
            return;
        }

        await api.post('/recruiter/send-email', {
            to: recipientEmail,
            subject: template.subject,
            body: customMessage,
            analysis_id: analysis.id
        });

        onClose();
    };

    return (
        <Modal>
            <h2>Mail Gönder</h2>

            <div className="email-form">
                <input
                    type="email"
                    placeholder="Aday email adresi"
                    value={recipientEmail}
                    onChange={(e) => setRecipientEmail(e.target.value)}
                    required
                />

                <select value={template.id} onChange={handleTemplateChange}>
                    <option>Email şablonları...</option>
                    {templates.map(t => (
                        <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                </select>

                <textarea
                    placeholder="Özel mesaj..."
                    value={customMessage}
                    onChange={(e) => setCustomMessage(e.target.value)}
                />

                <button onClick={handleSend}>Gönder</button>
            </div>
        </Modal>
    );
}
```

### Mail Template Sistemi

```python
# Email templates (içerik olmadan)
class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    name = Column(String(100))
    subject = Column(String(200))
    body_template = Column(Text)  # Variables: {score}, {job_title}, etc.

    # Variables that can be used (no personal data)
    available_vars = Column(JSONB, default=[
        'final_score', 'ats_score', 'job_title',
        'organization_name', 'decision_date'
    ])
```

## 🔒 Privacy & Security

### Saklanan Veri Haritası

```
✅ Analytics Data:
├── Final scores & sub-scores
├── Skills list (anonymized)
├── Experience years
├── Education level
├── Processing metadata

❌ Personal Data:
├── CV content/text
├── Names, emails, phones
├── Addresses, photos
├── Detailed work history
├── Personal statements

✅ Workflow Data:
├── Approval/rejection status
├── Recruiter notes
├── Decision timestamps
├── Job associations
```

### Auto-Cleanup

```python
# 30 gün sonra analysis'leri sil
def cleanup_old_analyses():
    cutoff_date = datetime.utcnow() - timedelta(days=30)

    deleted = db.query(CVAnalysis).filter(
        CVAnalysis.created_at < cutoff_date
    ).delete()

    logger.info(f"Cleaned up {deleted} old analyses")

    # İlgili actions'ları da sil
    db.query(RecruiterAction).filter(
        RecruiterAction.created_at < cutoff_date
    ).delete()
```

## 🎯 Kullanım Senaryosu

### Tipik İş Akışı

1. **CV Yükleme**: Aday CV'sini yükler → İçerik işlenir, puanlanır
2. **Veri Saklama**: Sadece puanlama + metadata saklanır, içerik silinir
3. **Recruiter Review**: Dashboard'da puanları görür, karşılaştırır
4. **Karar**: Onay/red kararı verir (manuel mail için email adresi sorulur)
5. **Mail Gönderme**: Recruiter manuel olarak mail gönderir
6. **Analytics**: Sistem meslek ortalamalarını günceller

### Recruiter Arayüzü

```jsx
function CVReviewCard({ analysis }) {
    return (
        <div className="cv-review-card">
            {/* İçerik yok, sadece skorlar */}
            <div className="scores">
                <ScoreBar label="Final Score" value={analysis.final_score} />
                <ScoreBar label="ATS Score" value={analysis.ats_score} />
                <ScoreBar label="Skills Match" value={analysis.skills_match_score} />
            </div>

            {/* Metadata */}
            <div className="metadata">
                <span>Dosya: {analysis.filename}</span>
                <span>Boyut: {analysis.file_size} bytes</span>
                <span>İşlendi: {analysis.processed_at}</span>
            </div>

            {/* Skills (anonymized) */}
            <div className="skills">
                {analysis.detected_skills.map(skill => (
                    <Badge key={skill}>{skill}</Badge>
                ))}
            </div>

            {/* Action buttons */}
            <div className="actions">
                <button onClick={() => onApprove(analysis)}>
                    ✅ Onayla
                </button>
                <button onClick={() => onReject(analysis)}>
                    ❌ Reddet
                </button>
                <button onClick={() => onSendEmail(analysis)}>
                    📧 Mail Gönder
                </button>
            </div>
        </div>
    );
}
```

## 💰 Business Benefits

### Privacy Compliance
- **GDPR Compliant**: Kişisel veri saklanmaz
- **Zero Data Breach Risk**: İçerik yok
- **Trust Building**: Privacy-first approach

### Analytics Value
- **Trend Analysis**: Meslek ortalamaları
- **Performance Insights**: İş ilanı başarıları
- **Recruiter Efficiency**: Data-driven decisions

### Operational Benefits
- **Storage Cost**: Çok az veri saklanır
- **Legal Safety**: Privacy riskleri minimum
- **Scalability**: Daha az data = daha hızlı

## 🚀 Implementation

### Mevcut Sisteme Entegrasyon

```python
# process_cv_batch'i modifiye et
async def process_cv_batch_local(
    files: List[UploadFile],
    job_id: int,
    organization_id: int,
    save_to_db: bool = False  # Bu artık farklı anlamlı
) -> List[Dict[str, Any]]:

    results = []

    for file in files:
        # İşle
        analysis_result = await process_cv_pipeline(file)

        if save_to_db:
            # Sadece scoring data sakla
            cv_analysis = CVAnalysis(
                organization_id=organization_id,
                job_id=job_id,
                # ... scoring fields only
            )
            db.add(cv_analysis)

        results.append({
            'analysis_id': cv_analysis.id if save_to_db else None,
            'final_score': analysis_result['final_score'],
            # İçerik dahil etme!
        })

    return results
```

Bu model ile **privacy'yi korurken analytics ve workflow'u** sağlayabiliriz! 🎯

Ne düşünüyorsunuz, bu yaklaşım uygun mu? 🤔