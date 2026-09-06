<div align="center">

# 🎯 CV Analyzer

### ATS kalibrasyonu · özgeçmiş zekâsı · işe alım akışları · gizlilik öncelikli yerel işleme

*Deterministik bir ayrıştırma çekirdeği üzerine kurulu, yapay zekâyı yalnızca maliyetini hak ettiği yerde kullanan hibrit SaaS + yerel masaüstü platformu.*

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135.1-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18.2-61DAFB?logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-8.0-646CFF?logo=vite&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind-4.3-38BDF8?logo=tailwindcss&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0.47-D71F00)
![Celery](https://img.shields.io/badge/Celery-5.6.2-37814A?logo=celery&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7.2.1-DC382D?logo=redis&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

![Türkçe](https://img.shields.io/badge/T%C3%BCrk%C3%A7e-0969DA?style=for-the-badge)&nbsp;&nbsp;[![English](https://img.shields.io/badge/English-30363D?style=for-the-badge)](README.en.md)

</div>

---

## 📑 İçindekiler

| # | Bölüm | # | Bölüm |
|---|-------|---|-------|
| 1 | [CV Analyzer nedir](#-1-cv-analyzer-nedir) | 10 | [Veri modeli](#-10-veri-modeli) |
| 2 | [Özellik matrisi](#-2-özellik-matrisi) | 11 | [Güvenlik modeli](#-11-güvenlik-modeli) |
| 3 | [Hızlı başlangıç](#-3-hızlı-başlangıç) | 12 | [Ortam değişkenleri](#-12-ortam-değişkenleri) |
| 4 | [Sistem mimarisi](#-4-sistem-mimarisi) | 13 | [Yerel geliştirme](#-13-yerel-geliştirme) |
| 5 | [Teknoloji yığını](#-5-teknoloji-yığını) | 14 | [Testler ve kalite kapıları](#-14-testler-ve-kalite-kapıları) |
| 6 | [Depo haritası](#-6-depo-haritası) | 15 | [CI/CD](#-15-cicd) |
| 7 | [Ayrıştırma hattı](#-7-ayrıştırma-hattı) | 16 | [Dağıtım](#-16-dağıtım) |
| 8 | [Bir isteğin yaşam döngüsü](#-8-bir-isteğin-yaşam-döngüsü) | 17 | [Yol haritası ve teknik borç](#-17-yol-haritası-ve-teknik-borç) |
| 9 | [API yüzeyi](#-9-api-yüzeyi) | 18 | [Katkı ve lisans](#-18-katkı-ve-lisans) |

---

## 🧭 1. CV Analyzer nedir

CV Analyzer, özgeçmişleri **ayrıştıran, puanlayan, yeniden yazan ve ATS (aday takip sistemi) ölçütlerine göre kıyaslayan** bir platformdur.

Temel tasarım kararı şudur: **önce deterministik, gerekirse yapay zekâ.** Kurallar ve sezgisel yöntemler özgeçmişlerin büyük çoğunluğunu ucuza çözer; dil modeli yalnızca bir kalite kapısı düşük nitelikli bir ayrıştırma tespit ettiğinde devreye girer. Böylece token harcaması zorlukla orantılı kalır.

Sistem, tek bir alan modelini paylaşan **dört çalışma zamanından** oluşur:

| Çalışma zamanı | Teknoloji | Sorumluluk |
|----------------|-----------|------------|
| 🖥️ **Backend API** | FastAPI (ASGI) | REST ağ geçidi, ayrıştırma hattı, ATS puanlama, faturalama, kimlik doğrulama, kota, depolama, worker senkronu |
| 🌐 **Web portalı** | React 18 + Vite | Açılış sayfası, panolar, analiz, CV Builder, işe alım çalışma alanı, faturalama arayüzü |
| 📱 **Mobil istemci** | Expo React Native | Yolda kullanım için yükleme + geçmiş iskeleti |
| 🔐 **Yerel Worker** | PySide6 / Qt Quick (QML) | Kullanıcının kendi makinesinde çevrimdışı toplu işleme; yalnızca açık talep üzerine senkron |

Ürün yönü **hibrit SaaS + yerel gizlilik**: bulut tarafı hesapları, faturalamayı, işe alım ekibi iş birliğini ve paylaşılan akışları yürütür; Yerel Worker ise hassas toplu işlemeyi kullanıcı açıkça senkron isteyene kadar makinede tutar.

```mermaid
flowchart LR
    subgraph Istemciler["İstemciler"]
        W[🌐 Web portalı<br/>React + Vite]
        M[📱 Mobil<br/>Expo RN]
        L[🔐 Yerel Worker<br/>PySide6/QML]
    end
    subgraph Bulut["☁️ Bulut backend"]
        API[FastAPI ağ geçidi]
        WK[Celery worker'ları]
    end
    subgraph Veri["🗄️ Durumlu servisler"]
        DB[(PostgreSQL)]
        RD[(Redis)]
        S3[(AWS S3)]
    end
    W -->|JWT REST| API
    M -->|JWT REST| API
    L -->|Worker anahtarı ile senkron| API
    API --> DB
    API --> RD
    API --> S3
    API -.kuyruğa al.-> WK
    WK --> DB
    WK --> S3
```

---

## ✨ 2. Özellik matrisi

### 👤 Aday / bireysel kullanıcı

| Özellik | Açıklama |
|---------|----------|
| ATS analizi | PDF/DOCX/TXT yükle → genel ve bölüm bazlı ATS puanları, tespit edilen/eksik yetkinlikler, öneriler |
| Puan kırılımı | Yapı, anahtar kelimeler, deneyim, eğitim, diller, ATS uyumluluğu, uzunluk |
| Yapay zekâ ile onarım | Önce deterministik onarım; dil modeliyle yeniden yazım yalnızca ayrıştırma kalitesi düşükse veya yeniden inşa istenirse |
| CV Builder | Şablon tabanlı üretim (DOCX / PDF / HTML / Typst), plana göre kilitlenen şablon ve yazı tipleri |
| Ön yazı ve mülakat hazırlığı | Dil modeli destekli ön yazı, mülakat sorusu ve cevap değerlendirme araçları |
| Geçmiş ve paylaşım | Kalıcı analizler, notlar, favoriler, paylaşılabilir bağlantı belirteçleri |

### 🧑‍💼 İşe alım uzmanı

| Özellik | Açıklama |
|---------|----------|
| İlanlar ve partiler | İlan oluştur, iş tanımı yükle, toplu aday alımı |
| Aday sıralama | Anlamsal + anahtar kelime eşleşme puanı, kısa listeye kalma olasılığı, güçlü yönler ve endişeler |
| Kararlar ve raporlar | Aday aksiyonları, yorumlar, hatırlatıcılar, dışa aktarılabilir raporlar |
| Gömü (embedding) arama | CV indeksleme, benzer aday bulma, anlamsal arama |
| Yerel işleme | Worker anahtarı üret, gizli işle, seçilen sonuçları geri senkronla |

### 🔐 Yerel masaüstü

| Özellik | Açıklama |
|---------|----------|
| Klasör toplu işleme | Yerel PDF/DOCX/TXT klasörlerini çevrimdışı öncelikli işleme |
| Yerel dışa aktarım | Yerel çalışma alanında CSV / JSON / HTML çıktıları |
| Kimlik bilgisi güvenliği | API anahtarları, mümkün olan yerde işletim sisteminin kimlik deposunda |
| Açık senkron | Sonuçlar kullanıcı senkron isteyene kadar makineden çıkmaz |

---

## 🚀 3. Hızlı başlangıç

> **Ön koşullar:** Python 3.12, Node.js 20+, (isteğe bağlı) PostgreSQL 15+ ve Redis 7. Geliştirmede veritabanı olarak SQLite, depolama olarak yerel disk yeterlidir.

```bash
# 1) Depoyu klonla
git clone https://github.com/SercanOzkan55/CV-Analyzer.git
cd CV-Analyzer

# 2) Ortam dosyasını hazırla
cp .env.example .env          # Windows: copy .env.example .env

# 3) Backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8001

# 4) Frontend (ikinci bir terminalde)
cd frontend
cp .env.example .env          # Windows: copy .env.example .env
npm install
npm run dev
```

Backend `http://localhost:8001`, web portalı `http://localhost:3000` adresinde açılır.

> ⚠️ **Port 8001 zorunludur.** Frontend'in Vite proxy'si `/api` isteklerini `http://127.0.0.1:8001` adresine yönlendirir (`frontend/vite.config.mjs`), `Dockerfile` de 8001'i açar. Backend'i başka bir portta çalıştırırsanız arayüzden gelen tüm API çağrıları başarısız olur.

---

## 🏗️ 4. Sistem mimarisi

```mermaid
flowchart TD
    Client[["İstemci (Web / Mobil / Worker)"]]

    subgraph Gateway["FastAPI ağ geçidi"]
        MW[Ara katman:<br/>CORS · hız sınırı · kötüye kullanım · CSRF]
        AUTH[Supabase JWT doğrulama<br/>algoritma izin listesi · JWKS önbelleği]
        ROUTE[15 router · 195 uç nokta]
    end

    subgraph Domain["Alan servisleri (52 modül)"]
        PIPE[Hat çalışma zamanı]
        ATS[ATS puanlama + ML kalibratörü]
        BUILD[CV Builder + render'lar]
        REC[İşe alım + gömüler]
        BILL[Faturalama + kota]
    end

    subgraph Infra["Altyapı"]
        DB[(PostgreSQL<br/>SQLAlchemy 2.0)]
        RD[(Redis<br/>önbellek · hız sınırı · kota)]
        S3[(S3 / yerel depolama<br/>SSE-AES256)]
        CEL[Celery + broker]
    end

    EXT[[Stripe · Supabase · LLM API'leri]]

    Client --> MW --> AUTH --> ROUTE
    ROUTE --> PIPE & ATS & BUILD & REC & BILL
    PIPE --> ATS
    BILL --> EXT
    AUTH --> EXT
    ROUTE --> DB & RD & S3
    ROUTE -.uzun işler.-> CEL --> DB & S3
    REC --> EXT
```

### Kullanılan tasarım örüntüleri

| Örüntü | Nerede |
|--------|--------|
| **Repository / servis katmanı** | `services/*`, veri erişimi ve iş mantığını route işleyicilerinin arkasında kapsüller |
| **Factory** | `ai_client_factory`; dosya türü / yerleşime göre çıkarım işleyicisi seçimi |
| **Strategy** | Depolama adaptörü (yerel vs S3), onarım kipi (koru / hafif onar / yeniden inşa et) |
| **Singleton** | DB oturum fabrikası, Redis istemcileri, yüklenmiş ML modelleri, çalışma zamanı ayarları |
| **Pipeline** | `çıkar → normalize et → şema → doğrula → puanla` aşamalı dönüşüm |
| **Devre kesici / kill-switch** | `core/ops_runtime`, `shared._cb_*` dış bağımlılıkları korur |

---

## 🧰 5. Teknoloji yığını

### Backend

| Katman | Kütüphane | Sürüm |
|--------|-----------|-------|
| Web çatısı | FastAPI | `0.135.1` |
| ASGI sunucusu | Uvicorn | `0.42.0` |
| ORM | SQLAlchemy | `2.0.47` |
| Göçler | Alembic | `1.18.4` |
| Doğrulama | Pydantic | `2.12.5` |
| Görev kuyruğu | Celery | `5.6.2` |
| Önbellek / sınırlar | redis-py | `7.2.1` |
| Nesne depolama | boto3 (S3) | `1.42.73` |
| PDF çıkarımı | pdfplumber / pypdf / pypdfium2 | `0.11.9` / `6.16.2` / `5.6.0` |
| ML puanlama | scikit-learn / XGBoost / NumPy | `1.8.0` / `3.2.0` / `2.4.2` |
| JWT | PyJWT | `2.13.0` |
| DB sürücüsü | psycopg2-binary | `2.9.11` |

### Frontend / mobil / masaüstü

| Katman | Kütüphane | Sürüm |
|--------|-----------|-------|
| Arayüz kütüphanesi | React | `18.2` |
| Derleme aracı | Vite | `8.0` |
| Stil | Tailwind CSS | `4.3` |
| Animasyon | Framer Motion | `12.36` |
| Yönlendirme | React Router DOM | `6.21` |
| Kimlik istemcisi | Supabase JS | `2.39` |
| Test | Vitest + Testing Library | `4.1` |
| Mobil | Expo / React Native | — |
| Masaüstü | PySide6 (Qt Quick / QML) | — |

---

## 🗂️ 6. Depo haritası

```text
CV-Analyzer/
├── main.py                 # FastAPI uygulama önyüklemesi (router, ara katman, lifespan)
├── routes/                 # 15 router, 195 uç nokta
│   ├── analysis.py         #   ATS analizi (senkron/asenkron/pdf), sahiplik
│   ├── ai_tools.py         #   otomatik onarım, yeniden yazım, ön yazı, mülakat, gömüler
│   ├── cv_builder.py       #   şablonlar, önizleme, üretim, özet önerisi
│   ├── cv_storage.py       #   S3 yükleme/indirme/silme, puan kırılımı
│   ├── billing.py          #   Stripe ödeme, webhook'lar, yönetici işlemleri
│   ├── recruiter*.py       #   ilanlar, adaylar, sıralama, yerel senkron (3 dosya)
│   ├── dashboard.py        #   kullanım, plan, istatistikler
│   ├── user_data.py        #   kullanıcı verisi, dışa aktarım, silme
│   ├── owner_workflow.py   #   sahip/operatör akışları
│   ├── worker.py           #   yerel worker claim/senkron
│   ├── downloads.py        #   üretilmiş dosya indirmeleri
│   ├── blog.py             #   blog içeriği (bayrakla kapalı)
│   └── system.py           #   sağlık, hazırlık, ops
├── services/               # 52 alan servisi (bkz. §7)
│   ├── pdf_text_extractor.py   # yerleşim farkındalıklı PDF → metin
│   ├── section_classifier.py   # dilden bağımsız bölüm tespiti
│   ├── schema_builder.py       # normalize veri → katı CVSchema
│   ├── extraction_validator.py # ayrıştırma kalite kapısı → AI yedeği
│   ├── cv_autofix_service.py   # deterministik onarım + AI yeniden yazım orkestrasyonu
│   ├── ats_scoring.py          # bölüm ve genel ATS puanlaması
│   └── ...
├── agents/                 # extract_agent, normalize_agent (hat aşamaları)
├── core/                   # http_runtime, ops_runtime, quota, metrics, route_dependencies
├── models.py               # 35 SQLAlchemy modeli
├── schemas/                # Pydantic + CVSchema / CVModel
├── renderers/              # DOCX / PDF / HTML / Typst şablon motorları
├── security/               # file_guard, s3_guard, rate_limit, runtime_guard
├── middleware/             # istek ara katmanı
├── alembic/ · migrations/  # veritabanı göçleri
├── frontend/               # React + Vite web portalı
├── mobile/                 # Expo React Native iskeleti
├── local_worker/           # PySide6 masaüstü uygulaması
├── tests/                  # 125 test dosyası, 981 test, golden fixture'lar
└── .github/workflows/      # CI: ci.yml · security.yml · build-local-worker.yml
```

---

## ⚙️ 7. Ayrıştırma hattı

Ayrıştırma çekirdeği **önce deterministiktir**. Dil modeli yalnızca bir güven kapısı düşük kaliteli ayrıştırma tespit ettiğinde çağrılır.

```mermaid
flowchart TD
    A[📄 PDF/DOCX/TXT yükleme] --> B[Çıkarım<br/>pdf_text_extractor]
    B --> B1{Yerleşim?}
    B1 -->|tek sütun| C[Kelime→satır yeniden inşası]
    B1 -->|çok sütun| C2[Sütun tespiti + yeniden akıtma]
    C --> D[Sayfa mobilyası temizliği<br/>altbilgi / sayfa numarası]
    C2 --> D
    D --> E[Bölüm tespiti<br/>section_classifier]
    E --> F[Çıkarım ajanı<br/>alanlar + kayıtlar]
    F --> G[Normalize ajanı]
    G --> H[Şema inşası<br/>schema_builder → CVSchema]
    H --> I{Kalite kapısı<br/>extraction_validator}
    I -->|puan yeterli| K[ATS puanlama + yük]
    I -->|düşük puan / bozuk| J[🤖 LLM ile yeniden ayrıştırma]
    J --> K
    K --> L[Sonuç: puanlar · yetkinlikler · builder yükü]
```

### Hat aşamaları ve anahtar servisler

| Aşama | Servis(ler) | Ne yapar |
|-------|-------------|----------|
| **Çıkarım** | `pdf_text_extractor` | Yazı tipine göreli kelime toleransı (`x_tolerance_ratio`) sayesinde sıkışık PDF'lerde kelimeler birbirine yapışmaz; çok sütun tespiti ve yeniden akıtma; mojibake onarımı; **sayfa mobilyası temizliği** (altbilgi / `Sayfa N` / şablon künyesi) |
| **Sınıflandırma** | `section_classifier`, `section_resolver` | Takma ad ve yapısal sinyallerle dilden bağımsız bölüm tespiti; niteleyici farkındalıklı başlıklar (`Araştırma Deneyimi`, `Diğer İş Deneyimi`) |
| **Alan çıkarımı** | `agents/extract_agent` | İletişim, özet, deneyimler (iş başına bir kayıt), eğitim, yetkinlikler, projeler, sertifikalar, diller |
| **Normalizasyon** | `agents/normalize_agent` | Tarihleri, madde imlerini, büyük/küçük harfi ve sıralamayı kanonikleştirir |
| **Şema** | `schema_builder` | Normalize veriyi katı bir `CVSchema`'ya eşler; madde imi glif normalizasyonu (`●○◦…`); konuşulan dilleri diller alanına yönlendirir; içeriksiz kayıtları eler |
| **Doğrulama** | `extraction_validator` | **Kalite kapısı** — bozuk ayrıştırmaları (parça başlıklar, aşırı bölünmüş tablolar, kaybolan bölümler, anlamsız yetkinlikler) tespit eder ve `needs_llm_fallback` bayrağını kaldırır |
| **Puanlama** | `ats_scoring`, `ml_calibrator`, `scoring_service` | Bölüm bazlı ve genel ATS puanları; güven değeriyle ML kalibrasyonu |
| **İnşa** | `cv_builder_service`, `renderers/*` | Şablonların DOCX / PDF / HTML / Typst olarak render'lanması |

### Dayanıklılık iyileştirmeleri

| Sorun | Çözüm |
|-------|-------|
| Sıkışık PDF'lerde yapışan kelimeler (`BachelorofScience`) | Yazı tipine göreli `x_tolerance_ratio` ile kelime ayırma |
| `●` imli işlerin tek kayda çökmesi | Tüm madde imi regex'lerine `●○◦` ve gliflerin eklenmesi → iş başına doğru bölme |
| Sayfa altbilgilerinin sahte iş kaydına dönüşmesi | Çıkarım anında sayfa mobilyası temizliği |
| Konuşulan dillerin yetkinliklerde sıkışması | Dil adı / CEFR kontrollü diller alanına yönlendirme |
| Tablo ve standart dışı yerleşimlerin parçalanması | **Parçalanma kalite kapısı** bunları LLM ile yeniden ayrıştırmaya yönlendirir |

---

## 🔄 8. Bir isteğin yaşam döngüsü

```mermaid
sequenceDiagram
    participant U as İstemci
    participant MW as Ara katman
    participant A as Kimlik (Supabase JWT)
    participant Q as Kota / hız sınırı
    participant R as Route işleyici
    participant S as Servisler
    participant DB as PostgreSQL
    participant X as S3 / Redis

    U->>MW: HTTPS isteği (+ Bearer token)
    MW->>MW: CORS · kötüye kullanım kontrolü · CSRF
    MW->>A: JWT doğrula (algoritma izin listesi, JWKS önbelleği)
    A-->>MW: kullanıcı iddiaları
    MW->>Q: günlük kotayı / hız sınırını tüket
    Q-->>MW: izin verildi (ya da 429)
    MW->>R: yönlendir
    R->>S: iş mantığı (ayrıştır / puanla / inşa et)
    S->>X: CV dosyasını oku/yaz, önbellek
    S->>DB: analiz / kullanım kaydet
    DB-->>S: satırlar
    S-->>R: sonuç
    R-->>U: JSON zarfı (+ kota başlıkları)
```

---

## 🌐 9. API yüzeyi

**15 router, 195 uç nokta**, tümü `/api/v1` altında.

| Router | Uç nokta | Amaç |
|--------|---------:|------|
| `recruiter` | 26 | İşe alım çalışma alanı: ilanlar, adaylar, sıralama, raporlar |
| `ai_tools` | 24 | Otomatik onarım, yeniden yazım, ön yazı, mülakat, anlamsal arama, gömüler |
| `dashboard` | 21 | Kullanım, plan, istatistikler |
| `worker` | 19 | Yerel Worker claim / senkron |
| `owner_workflow` | 18 | Sahip ve operatör akışları |
| `user_data` | 15 | Kullanıcı verisi, dışa aktarım, silme (KVKK/GDPR) |
| `system` | 15 | Sağlık, hazırlık, ops uç noktaları |
| `billing` | 14 | Stripe ödeme, webhook'lar, yönetici işlemleri |
| `analysis` | 13 | ATS analizi (senkron, asenkron, dosya) |
| `recruiter_local` | 9 | İşe alım tarafı yerel işleme köprüsü |
| `cv_builder` | 6 | Şablon tabanlı CV üretimi |
| `cv_storage` | 5 | S3 CV depolama + puan kırılımı |
| `blog` | 5 | Blog içeriği (`VITE_ENABLE_BLOG` ile kapalı) |
| `recruiter_extended` | 3 | Genişletilmiş işe alım işlemleri |
| `downloads` | 2 | Üretilmiş dosya indirmeleri |

> Yanıtlar tutarlı bir zarf kullanır (durum, veri, hata, isteğe bağlı sayfalama meta verisi) ve kota başlıkları taşır.

---

## 🗃️ 10. Veri modeli

35 SQLAlchemy modeli. Çekirdek ilişkiler:

```mermaid
erDiagram
    User ||--o{ Analysis : sahibi
    User ||--o{ CVVersion : saklar
    User ||--o{ UsageDaily : ölçer
    User }o--|| Organization : ait
    Organization ||--o{ RecruiterJob : yayınlar
    RecruiterJob ||--o{ Candidate : alır
    RecruiterJob ||--o{ JobApplication : izler
    Candidate ||--o{ CandidateAction : sahip
    Candidate ||--o{ CandidateComment : sahip
    Analysis ||--o{ AnalysisNote : notlanır
    Analysis ||--o{ AnalysisShare : paylaşılır
    User ||--o{ WorkerKey : üretir
    WorkerKey ||--o{ WorkerSession : doğrular
    WorkerSession ||--o{ WorkerAnalysisResult : senkronlar
```

| Alan | Modeller |
|------|----------|
| Hesap ve faturalama | `User`, `Organization`, `APISubscription`, `RolePermission`, `QuotaEvent`, `UsageDaily` |
| Analiz | `Analysis`, `CVVersion`, `AnalysisNote`, `AnalysisShare`, `Favorite` |
| İşe alım | `RecruiterJob`, `Candidate`, `Job`, `JobApplication`, `CandidateAction`, `CandidateComment`, `Reminder`, `JobTemplate`, `EmailTemplate` |
| Kıyaslama | `ATSBenchmarkGlobal`, `ATSBenchmarkProfession`, `ATSBenchmarkScore` |
| Yerel worker | `WorkerKey`, `WorkerSession`, `WorkerClaim`, `WorkerAnalysisResult` |
| Operasyon | `AuditLog`, `FailedTask`, `AsyncTaskOwner` |

---

## 🛡️ 11. Güvenlik modeli

```mermaid
flowchart LR
    A[Yükleme] --> B[Dosya koruması<br/>boyut · uzantı · MIME · sihirli bayt · PDF karmaşıklığı]
    B --> C[Virüs taraması<br/>ClamAV, isteğe bağlı]
    C --> D[Kimlik<br/>Supabase JWT · algoritma izin listesi · token uzunluk koruması]
    D --> E[Hız sınırı + kötüye kullanım<br/>IP ve kullanıcı bazlı]
    E --> F[Kota<br/>günlük + faturalanabilir]
    F --> G[Depolama koruması<br/>S3 anahtar doğrulama · sahiplik · 60sn imzalı URL]
    G --> H[Denetim kaydı + ops olayları]
```

| Katman | Kontrol |
|--------|---------|
| Girdi | Dosya boyutu/uzantı/MIME/sihirli bayt doğrulaması, PDF karmaşıklık sınırları, isteğe bağlı ClamAV |
| Kimlik | Algoritma izin listeli Supabase JWT, JWKS önbelleği, token uzunluk koruması |
| Kötüye kullanım | IP ve kullanıcı bazlı hız sınırları, yasaklar, yinelenen istek tekilleştirmesi |
| Kota | Günlük ve aylık plan limitleri, faturalanabilir kullanım ölçümü, maliyet korumaları |
| Depolama | S3 SSE-AES256, anahtar biçimi doğrulaması, sahiplik zorlaması, 60 saniyelik imzalı URL'ler |
| Sırlar | Yalnızca ortam değişkeni / sır yöneticisi; CI'da **Gitleaks** sır taraması |
| Tedarik zinciri | CI'da `pip-audit` + `npm audit` (kök/frontend/mobil) + Dependency Review |
| Faturalama | Stripe webhook HMAC imza doğrulaması |

---

## 🔑 12. Ortam değişkenleri

`.env.example` dosyasında **176 değişken** tanımlıdır; tam liste ve varsayılanlar için o dosyaya bakın. Sırları asla depoya işlemeyin — zorunlu değerler uygulama açılışında doğrulanır.

### Backend (`.env`)

| Grup | Örnek değişkenler | Amaç |
|------|-------------------|------|
| Çekirdek | `PORT`, `ENV`, `APP_TIMEZONE`, `BUILD_ID`, `GIT_SHA` | Çalışma zamanı kimliği ve meta verisi |
| Veritabanı | `DATABASE_URL` | PostgreSQL bağlantısı (geliştirmede SQLite) |
| Önbellek | `REDIS_URL` | Önbellek, hız sınırlama, kota sayaçları |
| Kimlik | `SUPABASE_URL`, `SUPABASE_JWT_*` | JWT doğrulama / JWKS |
| Faturalama | `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`, `BILLING_ADMIN_TOKEN` | Stripe ve webhook doğrulaması |
| Depolama | `STORAGE_BACKEND`, `AWS_*`, `S3_BUCKET`, `AWS_USE_IAM_ROLE` | Nesne depolama (`s3` veya `local`) |
| Hız sınırı | `RATE_LIMIT_IP_*`, `RATE_LIMIT_USER_*`, `ADMIN_RATE_LIMIT_PER_MIN` | İstek tavanları |
| Kötüye kullanım | `ABUSE_PROTECTION_ENABLED`, `ABUSE_BAN_SECONDS`, `ABUSE_SCORE_*` | Kötüye kullanım tespiti ve yasaklar |
| Kota / plan | `ENTITLE_FREE_DAILY_CV`, `ENTITLE_PRO_DAILY_CV`, `ENTITLE_ENTERPRISE_DAILY_CV`, `AUTO_NEW_USER_PLAN` | Plan hakları |
| Eşzamanlılık | `CONCURRENCY_ANALYZE`, `CONCURRENCY_EMBED`, `CONCURRENCY_REWRITE`, … | Aşama bazlı eşzamanlılık tavanları |
| Yapay zekâ | `AI_TIMEOUT_SECONDS`, `AI_MAX_RETRIES`, `ENABLE_AI_REVIEW`, `AI_FINAL_REVIEW_ATS_THRESHOLD` | LLM davranışı ve maliyet korumaları |
| ATS | `ATS_MODEL_PATH`, `ATS_CONFIG_PATH`, `ATS_WEIGHT`, `ENABLE_CLASSIFIER` | Puanlama modeli ve ağırlıkları |
| Veri saklama | `CV_RETENTION_DAYS`, `CV_RETENTION_BATCH_LIMIT`, `CV_VERSION_TEXT_STORAGE_MODE` | Saklama politikası |
| Güvenlik anahtarları | `CSRF_PROTECTION_ENABLED`, `CLAMAV_ENABLED`, `ADMIN_TOKEN`, `ADMIN_IP_ALLOWLIST` | Güvenlik anahtarları |
| Yedekleme | `BACKUP_DIR`, `BACKUP_RETENTION_DAYS`, `BACKUP_S3_PREFIX` | Yedekleme işleri |
| Devre kesici | `CB_FAILURE_THRESHOLD`, `CB_COOLDOWN_SECONDS` | Dış bağımlılık koruması |

### Frontend (`frontend/.env`)

| Değişken | Amaç |
|----------|------|
| `VITE_API_BASE` | Backend'in temel URL'i (üretim) |
| `VITE_SUPABASE_URL`, `VITE_SUPABASE_KEY` | Supabase istemci kimliği |
| `VITE_PRIVATE_MODE` | Siteyi giriş arkasına kilitler, kaydı kapatır |
| `VITE_REGISTRATION_DISABLED` | Kaydı bağımsız olarak kapatır |
| `VITE_ENABLE_BLOG` | Blog yalnızca localStorage demosudur — gerçek bir backend'i olana dek kapalı tutun |
| `VITE_ENABLE_BILLING` | Stripe üretime hazır olana dek ödeme ve faturalama portalı gizli kalır |

---

## 💻 13. Yerel geliştirme

### Backend

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8001
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # Vite geliştirme sunucusu (port 3000)
npm run build        # üretim paketi + SEO ön render'ı
npm run preview      # üretim paketini yerelde servis et
```

### Arka plan worker'ları (isteğe bağlı)

```bash
celery -A services.tasks worker --loglevel=info
```

### Yerel Worker (masaüstü)

```bash
cd local_worker
pip install -r requirements.txt
python main.py       # PySide6 / Qt Quick uygulaması
```

---

## 🧪 14. Testler ve kalite kapıları

| Paket | Komut | Kapsam |
|-------|-------|--------|
| Backend | `pytest tests/ -q` | 125 dosyada **981 test**: ayrıştırma, puanlama, şema, güvenlik, kiracılık, faturalama |
| Golden CV'ler | `pytest tests/golden/` | Bilinen özgeçmiş biçimleri için regresyon fixture'ları |
| Frontend | `cd frontend && npm test` | 24 dosyada **129 test** (Vitest + Testing Library) |
| Frontend tip kontrolü | `cd frontend && npm run typecheck` | `tsc --noEmit` |
| Lint | `ruff check . --select E9,F63,F7,F82` | Sözdizimi / tanımsız ad kapısı |
| Biçim | `ruff format --check .` | Kod stili |

---

## 🔁 15. CI/CD

```mermaid
flowchart LR
    P[Push / PR] --> CI[ci.yml]
    P --> SEC[security.yml]
    CI --> L[lint]
    CI --> T[test 3.12]
    CI --> B[benchmark]
    CI --> F[frontend]
    CI --> M[mobile]
    CI --> LW[local-worker]
    CI --> D[docker]
    CI --> S[security]
    SEC --> SC[secret-scan]
    SEC --> DR[dependency-review]
    SEC --> PA[python-audit]
    SEC --> NA[node-audit]
    L & T & B & F & M & LW & D & S & SC & DR & PA & NA --> G{Hepsi yeşil mi?}
    G -->|evet| OK[✅ birleştirilebilir]
```

Her PR **12 kontrolden** geçer:

| İş akışı | Job'lar |
|----------|---------|
| `ci.yml` | `lint`, `test (3.12)`, `benchmark`, `frontend`, `mobile`, `local-worker`, `docker`, `security` |
| `security.yml` | `secret-scan` (Gitleaks), `dependency-review`, `python-audit` (pip-audit), `node-audit` (npm audit) |
| `build-local-worker.yml` | `build` — yalnızca elle tetiklenir (`workflow_dispatch`) |

---

## 🚀 16. Dağıtım

```mermaid
flowchart TD
    subgraph Kenar["Kenar"]
        N[nginx ters vekil]
    end
    subgraph App["Docker (çok aşamalı)"]
        FE[Statik frontend paketi]
        BE[Uvicorn worker'ları :8001]
        WK[Celery worker'ları]
    end
    subgraph Yonetilen["Yönetilen servisler"]
        PG[(PostgreSQL)]
        RDS[(Redis)]
        S3[(S3 kovası)]
    end
    Internet --> N
    N --> FE
    N --> BE
    BE --> PG & RDS & S3
    WK --> PG & S3
```

- **Çok aşamalı Docker** yapısı ince bir çalışma imajı üretir; frontend derlenip **nginx** arkasında statik varlık olarak sunulur. Konteyner **8001** portunu açar.
- Veritabanı göçleri sürüm çıkışında **Alembic** ile çalışır (`alembic upgrade head`).
- Depolama arka ucu değiştirilebilir (`STORAGE_BACKEND=local|s3`).
- Ayrıntılı kılavuzlar: [`docs/deploy.md`](docs/deploy.md), [`docs/aws-deploy.md`](docs/aws-deploy.md), [`docs/aws-edge-security.md`](docs/aws-edge-security.md), [`docs/backup-restore.md`](docs/backup-restore.md).

---

## 🗺️ 17. Yol haritası ve teknik borç

| Madde | Durum |
|-------|-------|
| Çoklu iş deneyimi bölme (alt bölüm başlıkları) | ✅ Çözüldü (iş başına kayıt) |
| Sayfa mobilyası / altbilgi gürültüsü temizliği | ✅ Çözüldü |
| Ayrıştırma kalitesi → AI yedeği kapısı | ✅ Eklendi (parçalanmış yerleşimleri LLM'e yönlendirir) |
| Tablo yerleşimli CV ayrıştırma | 🔶 Deterministik ayrıştırıcı zayıf; AI yedeğiyle kapatılıyor |
| Gömülü tarih bölme (`June 2024 to September 2024` → başlangıç/bitiş) | 🔶 Planlandı |
| Deneyim dışı bölümlerin (`Leadership Activities`) deneyime yönlenmesi | 🔶 Planlandı |
| `core/route_dependencies` eski değişebilir durum göçü | 🔶 Sürüyor |
| `datetime.utcnow()` → zaman dilimi farkındalıklı göç | 🔶 Beklemede |

---

## 🤝 18. Katkı ve lisans

### Katkı

1. **Dal aç** — `main` üzerinden (`feat/...`, `fix/...`, `refactor/...`).
2. **Önce test** — testleri yaz/ayarla; dokunulan kodda ≥%80 kapsam koru.
3. **Lint ve biçim** — `ruff check` + `ruff format` geçmeli.
4. **Kapsamlı commit'ler** — conventional commit biçimi (`feat:`, `fix:`, `refactor:`…); yalnızca ilgili dosyaları stage'le.
5. **PR** — inceleme istemeden önce 12 CI kontrolünün de yeşil olduğundan emin ol.

### Lisans

Bu proje **MIT Lisansı** ile yayımlanmıştır. Telif hakkı (c) 2026 Sercan Ozkan.

Yazılımı kullanma, kopyalama, değiştirme, birleştirme, yayımlama, dağıtma, alt lisanslama ve satma hakkınız vardır; tek koşul telif ve lisans bildiriminin korunmasıdır. Tam metin için [LICENSE](LICENSE) dosyasına bakın.

---

<div align="center">

**CV Analyzer** — mümkün olan yerde deterministik, gerekli olan yerde yapay zekâ.

[English documentation →](README.en.md)

</div>
