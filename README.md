# 🎯 CV Analyzer - Intelligent Resume Intelligence Platform

> **Yapay zeka destekli, kurumsal düzeyde CV analiz, ATS uyumluluğu kontrol ve akıllı iş eşleştirme platformu.**

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-green.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React 18+](https://img.shields.io/badge/React-18+-61DAFB.svg?logo=react)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791.svg?logo=postgresql)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 İçerik

- [Genel Bakış](#-genel-bakış)
- [Güncel Değişiklikler](#-güncel-değişiklikler)
- [Özellikler](#-özellikler)
- [Teknoloji Stack](#-teknoloji-stack)
- [Mimari](#-mimari)
- [Hızlı Başlangıç](#-hızlı-başlangıç)
- [Kurulum](#-kurulum)
- [Kullanım](#-kullanım)
- [API Dokümantasyonu](#-api-dokümantasyonu)
- [Proje Yapısı](#-proje-yapısı)
- [Geliştiriciler için](#-geliştiriciler-için)

---

## 🎯 Genel Bakış

**CV Analyzer**, modern işletmeler için tasarlanmış, kurumsal düzeyde bir CV analiz ve akıllı eşleştirme platformudur. Platform, herhangi bir formattaki CV'leri otomatik olarak parse eder, standardize eder ve yapılandırılmış veri haline dönüştürür.

### Ana Amaçlar:
- ✅ **Otomatik CV Analizi**: Herhangi bir format ve dilden CV'leri anlaşılan şekilde parse etme
- ✅ **ATS Uyumluluğu**: Başvuru Takip Sistemleri (ATS) standartlarına uyumu kontrol etme
- ✅ **Akıllı İş Eşleştirmesi**: Yapay zeka ile CV'ler ve iş ilanları arasında semantik eşleştirme
- ✅ **Profil Optimizasyonu**: CV'leri target pozisyonlar için otomatik olarak optimize etme
- ✅ **Çok Dil Desteği**: Türkçe, İngilizce ve diğer dillerde CV analizi

---

## 🆕 Güncel Değişiklikler

Bu sürümde proje sağlığı, test kapsamı, CV Builder akışı ve recruiter deneyimi için kapsamlı düzeltmeler yapıldı.

### Backend ve API

- CV Builder endpointleri aktif hale getirildi:
  - `GET /api/v1/cv-builder/templates`
  - `POST /api/v1/cv-builder/preview`
  - `POST /api/v1/cv-builder/preview-html`
  - `POST /api/v1/cv-builder/generate`
  - `POST /api/v1/cv-builder/suggest-summary`
- Benchmark rota çakışması giderildi: dinamik rota artık `/api/v1/benchmark/{analysis_id:int}` olarak sınırlandırıldı.
- Eski paylaşım endpointleri yeni DB tabanlı paylaşım endpointleriyle çakışmaması için legacy path'e taşındı:
  - `/api/v1/share-legacy/{analysis_id}`
  - `/api/v1/shared-legacy/{token}`
- Recruiter local route yetkilendirme import'u doğru recruiter auth helper'ına bağlandı.

### Frontend

- Recruiter session state localStorage ile daha tutarlı hale getirildi.
- Batch ranking export yardımcıları CSV/HTML/JSON akışları için test edilebilir ve geriye uyumlu hale getirildi.
- Frontend test paketi Vitest + jsdom ile çalışır durumda.
- Vite vendor chunk ayrımı eklendi; production build'de ana JS chunk boyutu düşürüldü.

### Test, CI ve Docker

- Pytest fixture düzeni iyileştirildi; test veritabanı SQLite fallback ile temiz başlıyor.
- Sandbox'lı Windows ortamında `tmp_path` kullanımı workspace-local hale getirildi.
- CI'da hata gizleyen `|| true` / `|| echo` kullanımları kaldırıldı.
- `pytest.ini` tek pytest konfigürasyonu olarak bırakıldı.
- Dockerfile final stage dependency kurulumu düzeltildi.
- Docker healthcheck `wget` yerine Python stdlib ile çalışacak şekilde güncellendi.
- Redis healthcheck parola kullanılan compose kurulumuyla uyumlu hale getirildi.

Doğrulanan komutlar:

```bash
cd frontend
npm test
npm run build

cd ..
python -m pytest --collect-only -q
python -m pytest tests/test_api.py::test_analyze_endpoint tests/test_api.py::test_cv_builder_preview_html_returns_template_html tests/test_endpoint_coverage.py::TestCVBuilderEndpoints::test_list_templates -q --tb=short
python -m pytest tests/test_ats_config.py tests/test_train_model.py -q --tb=short
```

---

## ✨ Özellikler

### 📄 CV İşleme
- **Çok Format Desteği**: PDF, DOCX, TXT ve yapılandırılmış JSON formatları
- **Akıllı Parsing**: Multi-stage normalizasyon pipeline'ı ile herhangi bir CV layoutunu anlaşılan formata dönüştürme
- **Veri Standardizasyonu**: Tüm CV verileri canonical ATS-safe schema'ya normalize edilir
- **Otomatik Düzeltme**: Eksik veya hatalı verileri otomatik olarak tespit ve düzeltme

### 🎓 Veri Çıkarma
- **Kişisel Bilgiler**: İsim, iletişim, konum tespiti
- **Eğitim**: Okul, derece, alan, tarihler
- **Deneyim**: İşletme, konum, görev, açıklama, tarihler, başarılar
- **Beceriler**: Teknik ve yumuşak beceriler otomatik tespiti
- **Dilbilgisi**: Kişi başına konuşulan diller

### 🔍 Analiz & Puanlama
- **ATS Puanlaması**: Başvuru Takip Sistemleri tarafından okunabilirlik ve uyumluluk analizi
- **Yetkinlik Analizi**: Bulunduğu endüstri bazında yetkinlik seviyeleri
- **Deneyim Puanlaması**: Toplam ve ilgili deneyim hesaplaması
- **Endüstri Tespiti**: Otomatik endüstri ve uzmanlık alanı tanıması

### 🤖 Yapay Zeka & Matching
- **Semantik Eşleştirme**: OpenAI embeddings kullanarak yapay zeka destekli iş eşleştirmesi
- **Anahtar Kelime Analizi**: İş ilanı ve CV arasında anahtar kelimelerin karşılaştırılması
- **Beceri Boşluğu Analizi**: CV'de eksik olan ancak pozisyon için gerekli beceriler
- **Aday Sıralaması**: Kurumsal arama ve aday ranking sistemi

### ✏️ CV Optimizasyonu
- **Otomatik Rewrite**: CV'leri hedef pozisyonlar için optimize etme
- **Gramer Kontrolü**: Dil hatalarının tespiti ve düzeltilmesi
- **Format Önerileri**: ATS uyumluluğu için format önerileri
- **Çoklu Dil Desteği**: Çeşitli dillerde optimizasyon

### 🎨 CV Oluşturma
- **Şablon Tabanlı Rendering**: Profesyonel CV şablonları
- **Çoklu Format Çıktı**: PDF, DOCX, HTML export
- **Özel Tasarım**: Tema ve renk özelleştirmesi
- **Responsive Design**: Mobil ve masaüstü uyumlu tasarım

### 👥 İşveren Yönetimi
- **Recruiter Paneli**: İşverenler için dedike yönetim paneli
- **Aday Havuzu**: Merkezi aday veritabanı ve aramast
- **Toplu İşleme**: Çoklu CV'leri bir seferde analiz etme
- **Raporlama**: Detaylı analiz ve eşleştirme raporları

### 💳 SaaS Özellikleri
- **Faturalandırma**: Stripe entegrasyonu ile esnek faturalandırma planları
- **Kullanıcı Yönetimi**: Supabase ile kimlik doğrulama ve authorization
- **Kota Yönetimi**: Günlük ve aylık kullanım limitleri
- **Kuruluş Desteği**: Kurumsal kullanıcılar için ekip yönetimi

### 🔒 Güvenlik
- **JWT Authentication**: Supabase JWT tabanlı güvenlik
- **Rate Limiting**: DDoS koruması için API rate limiting
- **Veri Şifreleme**: S3'te şifrelenmiş depolama
- **GDPR Uyumu**: Veri gizliliği ve kullanıcı haklarına saygı

---

## 🛠️ Teknoloji Stack

### Backend
| Teknoloji | Amaç | Versiyon |
|-----------|------|---------|
| **FastAPI** | High-performance async web framework | 0.135+ |
| **Python** | Backend programlama dili | 3.12+ |
| **SQLAlchemy** | ORM ve database abstraction | Latest |
| **Alembic** | Database migrations | 1.18+ |
| **Celery** | Distributed task queue | 5.6+ |
| **Redis** | Caching ve rate limiting | Latest |

### Database & Storage
| Teknoloji | Amaç |
|-----------|------|
| **PostgreSQL** | İlişkisel veri yönetimi |
| **pgvector** | Vector embeddings depolama |
| **AWS S3** | Dosya depolama (CV'ler, PDF'ler) |
| **SQLAlchemy** | ORM ve query builder |

### Frontend
| Teknoloji | Amaç | Versiyon |
|-----------|------|---------|
| **React** | UI framework | 18+ |
| **TypeScript** | Type-safe JavaScript | Latest |
| **Vite** | Build tool ve dev server | Latest |
| **Tailwind CSS** | Utility-first CSS framework | Latest |
| **Vitest** | Unit testing framework | Latest |

### Mobile
| Teknoloji | Amaç |
|-----------|------|
| **React Native** | Cross-platform mobile app |
| **Expo** | React Native framework |
| **TypeScript** | Type-safe development |

### ML/AI & NLP
| Teknoloji | Amaç |
|-----------|------|
| **OpenAI API** | Embeddings ve NLP işlemleri |
| **scikit-learn** | Machine Learning algoritmaları |
| **spaCy** | NLP ve Named Entity Recognition |
| **NLTK** | Doğal Dil İşleme kütüphanesi |
| **transformers** | Pre-trained NLP modelleri |

### DevOps & Deployment
| Teknoloji | Amaç |
|-----------|------|
| **Docker** | Containerization |
| **Docker Compose** | Multi-container orchestration |
| **Gunicorn** | WSGI application server |
| **Nginx** | Reverse proxy ve load balancer |
| **Prometheus** | Metrics monitoring |

### Authentication & Authorization
| Teknoloji | Amaç |
|-----------|------|
| **Supabase** | Backend-as-a-Service (BaaS) |
| **JWT** | Token-based authentication |
| **OAuth 2.0** | Third-party authentication |

### Integrations
| Hizmet | Kullanım |
|-------|---------|
| **OpenAI** | Embeddings ve LLM işlemleri |
| **Stripe** | Payment processing |
| **Supabase** | Auth ve realtime features |
| **AWS** | S3 storage ve deployment |
| **SendGrid** | Email notifications |

### Development Tools
| Araç | Amaç |
|------|------|
| **Ruff** | Fast Python linter |
| **Black** | Code formatter |
| **Pytest** | Testing framework |
| **Coverage** | Code coverage analysis |
| **Bandit** | Security analyzer |

---

## 🏗️ Mimari

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend Layer                           │
│                  React 18 + Vite + TypeScript                   │
│                  (Dashboard, Upload, Reports)                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   API Gateway│
                    │ (Nginx/CORS) │
                    └──────┬──────┘
                           │
┌─────────────────────────────────────────────────────────────────┐
│                      Backend Layer                              │
│                  FastAPI + Async/Await                          │
├──────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Auth Service│  │ CV Parse Svc │  │ Job Match Svc│          │
│  │  (Supabase)  │  │  (Multi-stage)  │  (Embeddings)  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ ATS Analyzer │  │ Skill Detect │  │ Language Det │          │
│  │  (Scoring)   │  │  (NLP/spaCy) │  │  (NLP)       │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ CV Optimizer │  │ Recommendation│ │ Layout Engine│          │
│  │  (Rewrite)   │  │   (ML Model)  │  │  (Rendering) │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└───────┬────────────────────────────┬───────────────────────────┘
        │                            │
   ┌────▼──────┐           ┌─────────▼──────┐
   │ PostgreSQL │           │ Redis Cache    │
   │  + pgvector│           │ + Rate Limiter │
   └────────────┘           └────────────────┘
        │
   ┌────▼──────────┐
   │ Celery Queue   │
   │ (Background)   │
   └────────────────┘
        │
   ┌────▼──────────┐
   │ AWS S3         │
   │ (File Storage) │
   └────────────────┘
```

### Parser Pipeline (Detaylı)

```
Raw CV Input
     │
     ▼
1. Format Detection
   (PDF, DOCX, TXT, JSON)
     │
     ▼
2. Raw Text Extraction
   (Optical char recognition + text parsing)
     │
     ▼
3. Section Classification
   (Bölüm tanıma: Kişi, Eğitim, Deneyim, etc.)
     │
     ▼
4. Data Extraction (NER)
   (Named Entity Recognition + Pattern matching)
     │
     ▼
5. Normalization
   (Tarih format, telefon, e-mail normalize etme)
     │
     ▼
6. Validation
   (Mantık kontrolleri ve consistency)
     │
     ▼
7. Enrichment
   (Konum, endüstri, beceri tespiti)
     │
     ▼
Canonical JSON Schema
```

---

## 🚀 Hızlı Başlangıç

### Ön Koşullar

- Python 3.12 veya üzeri
- Node.js 18+ ve npm
- PostgreSQL 14+ (pgvector uzantısı)
- Docker & Docker Compose (isteğe bağlı)
- AWS S3 erişimi (dosya depolama için)
- OpenAI API anahtarı (embeddings için)
- Stripe API anahtarı (faturalandırma için)
- Supabase projesi (kimlik doğrulama için)

### 1️⃣ Repository'yi Klonlayın

```bash
git clone https://github.com/yourusername/cv-analyzer.git
cd cv-analyzer
```

### 2️⃣ Python Environment Kurulumu

```bash
# Virtual environment oluştur
python -m venv venv

# Environment'i aktif et
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# Gerekli paketleri yükle
pip install -r requirements.txt
```

### 3️⃣ Environment Değişkenleri

`.env` dosyası oluştur (`.env.example` görmek için):

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/cv_analyzer
REDIS_URL=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=sk-xxx...

# AWS S3
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=xxx...
AWS_REGION=us-east-1
S3_BUCKET_NAME=cv-analyzer-bucket

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=xxx...
SUPABASE_SERVICE_KEY=xxx...

# Stripe
STRIPE_SECRET_KEY=sk_xxx...
STRIPE_PUBLISHABLE_KEY=pk_xxx...

# Environment
ENV=development
DEBUG=True
```

### 4️⃣ Database Kurulumu

```bash
# Alembic migrations'ları çalıştır
alembic upgrade head

# (İsteğe bağlı) Database'i seed et
python setup_db.py
```

### 5️⃣ Backend'i Başlat

```bash
# FastAPI dev server (hot-reload ile)
uvicorn main:app --reload --port 8001

# veya Gunicorn (production için)
gunicorn -c gunicorn_config.py main:app
```

Backend'e erişim: http://localhost:8001

### 6️⃣ Frontend'i Başlat

```bash
cd frontend
npm install
npm run dev
```

Frontend'e erişim: http://localhost:5173

### 7️⃣ ML Model Eğitimi

`train_model.py` hem sentetik hem gerçek CSV verisi üzerinden model eğitebilir.

```bash
# Root dizinde çalıştırın
python train_model.py --data-csv my_real_data.csv --hire-threshold 70
```

Gerçek CSV veri seti için dikkat:

- `sample_training_data.csv` içinde listelenen 29 özellik sütunu gereklidir
- `score` veya `hire` hedef sütunu bulunmalıdır
- `data-csv` sağlanmışsa en az 30 kayıt ve hem `hire=0` hem `hire=1` örnekleri tavsiye edilir
- Eğer `hire` sütunu yoksa, `score >= --hire-threshold` kullanılarak etiketler türetilir

Eğer CSV verisi sağlanmazsa, script sentetik veri üreterek modelleri eğitir.

### 8️⃣ (İsteğe bağlı) Mobile Uygulaması

```bash
cd mobile
npm install
npm start
```

---

## 📖 Kurulum

### Docker ile Kurulum

```bash
# Tüm servisleri başlat (PostgreSQL, Redis, Backend, Frontend)
docker-compose up -d

# Logs kontrol et
docker-compose logs -f

# Servisleri durdur
docker-compose down
```

Notlar:

- Backend image final stage'de `requirements.txt` kopyalayarak wheel cache üzerinden kurulum yapar.
- Backend container healthcheck'i `http://localhost:8001/health` endpointini Python stdlib ile kontrol eder.
- Redis servisi `REDIS_PASSWORD` ile başlatılır ve healthcheck aynı parolayı kullanır.

### Detaylı Kurulum Rehberi

Ayrıntılı kurulum adımları için bkz: [Kurulum Dokümantasyonu](./docs/deploy.md)

### AWS Deployment

AWS'ye deployment için bkz: [AWS Deployment Rehberi](./docs/aws-deploy.md)

---

## 💡 Kullanım

### API Örnekleri

#### 1. CV Upload ve Analiz

```bash
curl -X POST http://localhost:8001/api/cv/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@resume.pdf" \
  -F "job_id=123" \
  -F "language=tr"
```

Response:
```json
{
  "cv_id": "cv_abc123",
  "status": "analyzed",
  "extracted_data": {
    "personal": {
      "name": "Ahmet Yılmaz",
      "email": "ahmet@example.com",
      "phone": "+90 555 123 4567",
      "location": "İstanbul, Türkiye"
    },
    "summary": "10+ yıl yazılım geliştirme deneyimi...",
    "education": [...],
    "experience": [...],
    "skills": [...]
  },
  "scores": {
    "ats_compatibility": 0.92,
    "job_match": 0.87,
    "skill_match": 0.91
  },
  "recommendations": [...]
}
```

#### 2. İş Eşleştirmesi

```bash
curl -X GET http://localhost:8001/api/match/candidates \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d "job_id=123&limit=10&threshold=0.8"
```

#### 3. CV Optimizasyonu

```bash
curl -X POST http://localhost:8001/api/cv/optimize \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cv_id": "cv_abc123",
    "job_id": "job_xyz789",
    "optimization_focus": ["skills", "keywords", "formatting"]
  }'
```

#### 4. CV Render Etme

```bash
curl -X POST http://localhost:8001/api/cv/render \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cv_id": "cv_abc123",
    "template": "professional",
    "format": "pdf",
    "theme": "blue"
  }'
```

#### 5. CV Builder HTML Preview

```bash
curl -X POST http://localhost:8001/api/v1/cv-builder/preview-html \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Ada Lovelace",
    "email": "ada@example.com",
    "title": "Software Engineer",
    "summary": "Backend and AI product engineer.",
    "skills": ["Python", "FastAPI", "React"],
    "experiences": [],
    "education": [],
    "projects": [],
    "languages": ["English"],
    "template": "classic",
    "output_format": "pdf",
    "lang": "en"
  }'
```

#### 6. Recruiter Batch Export

Recruiter batch ranking sonuçları frontend tarafında CSV, HTML ve JSON olarak export edilebilir. Export yardımcıları `frontend/src/utils/exportUtils.js` içinde tutulur ve Vitest ile test edilir.

### Web Dashboard Kullanımı

1. **Dashboard'a Giriş**
   - https://localhost:5173 adresine gidin
   - Email/şifre veya OAuth ile giriş yapın

2. **CV Yükleyin**
   - "New Analysis" butonuna tıklayın
   - CV dosyasını seçin
   - Dili ve iş ilanı seçin (isteğe bağlı)

3. **Sonuçları Görüntüleyin**
   - ATS puanı, beceri analizi, öneriler
   - CV'yi optimize edin
   - Yeni formatlar ile indirin

4. **Recruiter Özellikleri** (Kuruluşlar için)
   - Aday havuzunda ara
   - Toplu CV analizi yap
   - Raporlar oluştur

---

## 📚 API Dokümantasyonu

Tam API dokümantasyonu: http://localhost:8001/docs

### Ana Endpoints

| Metod | Endpoint | Açıklama |
|-------|----------|---------|
| **POST** | `/api/cv/upload` | CV yükleme ve analiz |
| **GET** | `/api/cv/{cv_id}` | CV detaylarını getir |
| **POST** | `/api/cv/optimize` | CV optimizasyonu |
| **POST** | `/api/cv/render` | CV render etme (PDF/DOCX) |
| **GET** | `/api/match/candidates` | İş için eşleşen adaylar |
| **POST** | `/api/job/create` | İş ilanı oluştur |
| **GET** | `/api/analyze/ats` | ATS analizi |
| **GET** | `/api/user/profile` | Kullanıcı profili |
| **POST** | `/api/billing/subscribe` | Subscription oluştur |

### Aktif v1 Endpointleri

| Metod | Endpoint | Açıklama |
|-------|----------|---------|
| **GET** | `/api/v1/cv-builder/templates` | Kullanıcı planına göre CV şablonlarını listeler |
| **POST** | `/api/v1/cv-builder/preview` | CV Builder verisini normalize edip preview payload döner |
| **POST** | `/api/v1/cv-builder/preview-html` | Seçilen şablonla HTML preview üretir |
| **POST** | `/api/v1/cv-builder/generate` | CV çıktısını PDF/DOCX olarak üretir |
| **POST** | `/api/v1/cv-builder/suggest-summary` | CV summary önerileri üretir |
| **GET** | `/api/v1/benchmark/global` | Global benchmark istatistikleri |
| **GET** | `/api/v1/benchmark/professions` | Meslek bazlı benchmark istatistikleri |
| **GET** | `/api/v1/benchmark/specializations` | Uzmanlık bazlı benchmark istatistikleri |
| **GET** | `/api/v1/benchmark/{analysis_id:int}` | Analize özel benchmark sonucu |
| **POST** | `/api/v1/share` | DB tabanlı paylaşım linki oluşturur |
| **GET** | `/api/v1/shared/{share_token}` | Paylaşılan analiz görünümü |

Detaylı endpoint referansı: [API Reference](./docs/api-reference.md)

---

## 📁 Proje Yapısı

```
cv-analyzer/
├── 📄 main.py                    # FastAPI uygulaması ana giriş noktası
├── 📄 requirements.txt           # Python dependencies
├── 📄 pyproject.toml             # Project metadata
├── 📄 pytest.ini                 # Pytest konfigürasyonu
├── 🔧 .env.example               # Environment template
│
├── 🗂️ agents/                    # ML agents
│   ├── extract_agent.py          # CV extraction agent
│   └── normalize_agent.py        # Normalization agent
│
├── 🗂️ services/                  # Business logic services
│   ├── ats_service.py            # ATS compatibility analysis
│   ├── cv_builder_service.py     # CV rendering ve building
│   ├── cv_optimizer_service.py   # CV optimization logic
│   ├── embedding_service.py      # OpenAI embeddings
│   ├── skill_service.py          # Skill detection
│   ├── job_match_service.py      # Job matching logic
│   ├── language_service.py       # Multi-language support
│   ├── s3_service.py             # AWS S3 integration
│   ├── billing_service.py        # Stripe integration
│   └── [20+ more services]
│
├── 🗂️ models/                    # SQLAlchemy ORM models
│   └── models.py                 # Database models
│
├── 🗂️ schemas/                   # Pydantic request/response schemas
│   └── [Schema definitions]
│
├── 🗂️ utils/                     # Utility fonksiyonları
│   ├── validators.py             # Input validators
│   └── [Helper functions]
│
├── 🗂️ templates/                 # CV templates (Typst)
│   ├── creative/
│   ├── professional/
│   └── modern/
│
├── 🗂️ migrations/                # Alembic DB migrations
│   ├── env.py                    # Alembic config
│   └── versions/
│
├── 🗂️ tests/                     # Unit & integration tests
│   ├── test_api.py
│   ├── test_services.py
│   └── conftest.py
│
├── 📄 database.py                # SQLAlchemy session & engine
├── 📄 auth.py                    # Authentication helpers
├── 📄 shared.py                  # Shared constants ve utilities
├── 📄 logging_config.py          # Logging konfigürasyonu
├── 📄 docker-compose.yml         # Multi-container setup
├── 📄 Dockerfile                 # Backend container image
├── 📄 nginx.conf                 # Nginx reverse proxy config
│
├── 📁 frontend/                  # React + Vite frontend
│   ├── src/
│   │   ├── components/           # React components
│   │   ├── pages/                # Page components
│   │   ├── hooks/                # Custom React hooks
│   │   ├── services/             # API service clients
│   │   ├── utils/                # Utility functions
│   │   └── App.tsx
│   ├── package.json
│   ├── vite.config.mjs
│   └── tailwind.config.js
│
├── 📁 mobile/                    # React Native mobile app
│   ├── src/
│   │   ├── components/
│   │   ├── screens/
│   │   ├── services/
│   │   └── App.tsx
│   ├── app.json
│   └── package.json
│
├── 📁 docs/                      # Dokümantasyon
│   ├── README.md
│   ├── api-reference.md
│   ├── deploy.md
│   ├── aws-deploy.md
│   └── usage.md
│
├── 📁 scripts/                   # Utility scripts
│   ├── setup_db.sh
│   └── pin_requirements.sh
│
└── 📁 config/                    # Configuration files
    ├── aws.py
    └── ats_config.yaml
```

---

## 🧑‍💻 Geliştiriciler için

### Geliştirme Ortamı Kurulumu

```bash
# Tüm geliştirici araçlarını yükle
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Pre-commit hooks'u kur
pre-commit install

# Kodu format et
black .

# Linting kontrol et
ruff check .

# Type checking
mypy services/
```

### Testing

```bash
# Tüm testleri çalıştır
pytest

# Coverage raporu ile
pytest --cov=. --cov-report=html

# Belirli test dosyasını çalıştır
pytest tests/test_api.py -v

# Belirli test'i çalıştır
pytest tests/test_api.py::test_cv_upload -v

# Test collection/import kontrolü
pytest --collect-only -q

# Frontend testleri
cd frontend
npm test
npm run build
```

Son doğrulamada backend collection `622` test topladı; frontend test paketi `50` testi geçti. Docker CLI yerel ortamda bulunmuyorsa Docker doğrulaması CI veya Docker kurulu bir makinede çalıştırılmalıdır.

### Code Quality

```bash
# Security scanning
bandit -r . --exclude venv

# Code formatting
black . --check

# Lint raporu
ruff check . --output-format json > lint-report.json

# Type hints kontrolü
mypy . --ignore-missing-imports
```

### Database Migrations

```bash
# Yeni migration oluştur
alembic revision --autogenerate -m "Add new column"

# Migration'ları uygula
alembic upgrade head

# Belirli versiyona geri dön
alembic downgrade -1
```

### Debugging

```bash
# Debug mode ile çalıştır
DEBUG=1 uvicorn main:app --reload

# Detaylı logging ile
LOGLEVEL=DEBUG python -m uvicorn main:app --reload

# Database queries loggla
SQLALCHEMY_ECHO=1 uvicorn main:app --reload
```

### Performance Profiling

```bash
# Flame graph oluştur
python -m pyflame -t -o flame.txt python main.py

# Memory profiling
python -m memory_profiler main.py
```

---

## 📊 Monitoring & Observability

### Metrics

- Prometheus metrikleri: http://localhost:8001/metrics
- Grafana dashboard: http://localhost:3000

### Logging

- JSON structured logging tüm request'ler için
- Logs: `logs/` directory veya stdout
- Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`

### Error Tracking

- Sentry integration (isteğe bağlı)
- Error reports: `err_trace.txt`

---

## 🔐 Güvenlik

### Yapı Kontrolleri

- ✅ OWASP Top 10 uyumu
- ✅ SQL injection koruması (SQLAlchemy)
- ✅ CORS configuration
- ✅ Rate limiting (SlowAPI + Redis)
- ✅ JWT token validation
- ✅ Input sanitization ve validation
- ✅ Secret management (environment variables)

### Best Practices

```python
# ✅ Input validation
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    password: str

# ✅ Rate limiting
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/cv/upload")
@limiter.limit("5/minute")
async def upload_cv():
    pass

# ✅ Auth required
from fastapi import Depends

@app.get("/api/user/profile")
async def get_profile(user=Depends(get_current_user)):
    pass
```

### Secrets Management

```bash
# .env dosyasını asla commit etme
echo ".env" >> .gitignore

# Production'da environment variables kullan
export DATABASE_URL=postgresql://...
export OPENAI_API_KEY=sk_...
```

---

## 🚢 Deployment

### Production Checklist

- [ ] Environment variables konfigüresi
- [ ] SSL/TLS sertifikaları
- [ ] Database backups kurulumu
- [ ] CDN configuration (S3 + CloudFront)
- [ ] Monitoring ve alerting
- [ ] Log aggregation (CloudWatch/ELK)
- [ ] Auto-scaling policies
- [ ] CI/CD pipeline setup

### Docker Deployment

```bash
# Production image build
docker build -t cv-analyzer:latest -f Dockerfile .

# Docker registry'e push et
docker tag cv-analyzer:latest gcr.io/project/cv-analyzer
docker push gcr.io/project/cv-analyzer

# Kubernetes deployment (örnek)
kubectl apply -f k8s/deployment.yaml
```

### AWS Deployment

Bkz: [AWS Deployment Rehberi](./docs/aws-deploy.md)

---

## 📈 Performance İpuçları

### Database Optimizasyonu

```python
# Index'leri kulla
class CV(Base):
    __tablename__ = "cvs"
    user_id = Column(Integer, index=True)  # Index user queries için
    created_at = Column(DateTime, index=True)  # Range queries için

# Query optimization
from sqlalchemy import select

# ❌ N+1 problem
for cv in session.query(CV).all():
    print(cv.user.name)

# ✅ Eager loading
cvs = session.query(CV).options(
    joinedload(CV.user)
).all()
```

### Caching Strategy

```python
# Redis caching
from functools import lru_cache

@app.get("/api/job/{job_id}")
async def get_job(job_id: int):
    # Redis'te kontrol et
    cached = redis_client.get(f"job:{job_id}")
    if cached:
        return json.loads(cached)
    
    # Database'ten al ve cache et
    job = db.query(Job).get(job_id)
    redis_client.setex(f"job:{job_id}", 3600, json.dumps(job))
    return job
```

### Async/Await Kullanımı

```python
# ✅ Async I/O maksimize et
@app.post("/api/cv/bulk-analyze")
async def bulk_analyze(files: List[UploadFile]):
    # Paralel olarak işle
    results = await asyncio.gather(*[
        process_cv(file) for file in files
    ])
    return results
```

---

## 🤝 Katkı Sağlama

Projede katkı sağlamak istiyorsanız:

1. Repository'yi fork edin
2. Feature branch'i oluşturun (`git checkout -b feature/amazing-feature`)
3. Değişiklikleri commit edin (`git commit -m 'Add amazing feature'`)
4. Branch'i push edin (`git push origin feature/amazing-feature`)
5. Pull Request oluşturun

### Kod Standartları

- PEP 8 compliance (Black + Ruff)
- Type hints kullanımı
- Docstring'ler her fonksiyon için
- Unit test coverage > 80%
- Descriptive commit messages

---

## 📝 Lisans

Bu proje MIT Lisansı altında lisanslanmıştır. Ayrıntılar için [LICENSE](LICENSE) dosyasına bakın.

---

## 🆘 Destek & İletişim

- 📧 Email: support@cvanalyzer.io
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/cv-analyzer/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/yourusername/cv-analyzer/discussions)
- 📖 Dokümantasyon: [docs/](./docs/)

---

## 📚 İlgili Kaynaklar

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [OpenAI API](https://platform.openai.com/docs/)
- [PostgreSQL pgvector](https://github.com/pgvector/pgvector)
- [Supabase Documentation](https://supabase.com/docs)

---

## 🙏 Teşekkürler

Bu proje aşağıdaki harika open-source projelerden yararlanmaktadır:

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [React](https://react.dev/)
- [OpenAI Python](https://github.com/openai/openai-python)
- Ve diğer birçok...

---

<div align="center">

**⭐ Eğer bu proje faydalı olduysa, lütfen yıldız verin!**

[GitHub'da Yıldız Ver](https://github.com/SercanOzkan55/CV-Analyzer) • [Sorun Bildir](https://github.com/SercanOzkan55/CV-Analyzer) • [Feature İste](https://github.com/SercanOzkan55/CV-Analyzer)

Made with ❤️ by [Sercan Özkan](https://github.com/SercanOzkan55)

</div>
