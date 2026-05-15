# Local Processing Mode - Deployment & Usage Guide

Bu kılavuz, **sıfır veri saklama** özelliği ile CV analiz sistemi'nin local processing mode'unu nasıl deploy edeceğinizi ve kullanacağınızı adım adım açıklar.

## 🚀 Hızlı Başlangıç

### 1. Sistem Gereksinimleri

```bash
# Minimum Gereksinimler
- Python 3.9+
- Node.js 18+
- PostgreSQL 13+
- 4GB RAM
- 10GB Disk

# Önerilen
- Python 3.11+
- Node.js 20+
- PostgreSQL 15+
- 8GB RAM
- 50GB SSD
```

### 2. Proje Kurulumu

```bash
# 1. Projeyi klonlayın
git clone <repository-url>
cd cv-analyzer

# 2. Python ortamını hazırlayın
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Bağımlılıkları yükleyin
pip install -r requirements.txt

# 4. Node.js bağımlılıklarını yükleyin
cd frontend
npm install
cd ..

# 5. Veritabanını hazırlayın
createdb cv_analyzer_db
export DATABASE_URL="postgresql://user:pass@localhost/cv_analyzer_db"

# 6. Veritabanı tablolarını oluşturun
python -m alembic upgrade head

# 7. Sistemi başlatın
python main.py  # Backend
# Yeni terminalde:
cd frontend && npm run dev  # Frontend
```

## ⚙️ Konfigürasyon

### Environment Variables

```bash
# .env dosyası oluşturun
DATABASE_URL=postgresql://user:password@localhost:5432/cv_analyzer
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_JWT_SECRET=your-jwt-secret
ENV=production
LOG_LEVEL=INFO

# Opsiyonel
REDIS_URL=redis://localhost:6379  # Rate limiting için
S3_BUCKET=your-bucket  # Eski özellikler için
OPENAI_API_KEY=sk-...  # AI özellikler için
```

### Güvenlik Ayarları

```bash
# API Key güvenliği
API_KEY_ROTATION_DAYS=30
API_KEY_LENGTH=32

# Kota limitleri
DEFAULT_MONTHLY_LIMIT=1000
MAX_FILES_PER_REQUEST=50
FILE_SIZE_LIMIT_MB=5

# Otomatik temizlik
DOWNLOAD_EXPIRY_HOURS=1
TEMP_FILE_CLEANUP_INTERVAL=3600
```

## 🏢 Enterprise Kurulumu

### Docker ile Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN python -m alembic upgrade head

EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

```bash
# Docker Compose
version: '3.8'
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: cv_analyzer
      POSTGRES_USER: cv_user
      POSTGRES_PASSWORD: secure_password

  redis:
    image: redis:7-alpine

  app:
    build: .
    environment:
      DATABASE_URL: postgresql://cv_user:secure_password@db/cv_analyzer
      REDIS_URL: redis://redis:6379
    ports:
      - "8001:8001"
    depends_on:
      - db
      - redis
```

### Nginx Reverse Proxy

```nginx
# nginx.conf
server {
    listen 80;
    server_name your-domain.com;

    location /api/ {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        proxy_pass http://localhost:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### SSL Sertifikası

```bash
# Let's Encrypt ile ücretsiz SSL
sudo certbot --nginx -d your-domain.com
```

## 👥 Kullanıcı Yönetimi

### Organizasyon Oluşturma

```python
# Python shell'de
from database import get_db
from models import Organization, User

db = next(get_db())

# Organizasyon oluştur
org = Organization(
    name="ABC Şirketi",
    domain="abc.com",
    plan_type="enterprise",
    billing_status="active"
)
db.add(org)
db.commit()

# Admin kullanıcı oluştur
user = User(
    supabase_id="admin-uuid",
    email="admin@abc.com",
    organization_id=org.id
)
db.add(user)
db.commit()
```

### Supabase Entegrasyonu

```javascript
// Supabase Auth kurulumu
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  'https://your-project.supabase.co',
  'your-anon-key'
)

// Kullanıcı kaydı
const { data, error } = await supabase.auth.signUp({
  email: 'user@company.com',
  password: 'secure-password'
})
```

## 🔑 API Key Yönetimi

### API Key Oluşturma

```bash
# JWT token ile API key oluştur
curl -X POST "http://localhost:8001/api/v1/recruiter/subscriptions/generate-key" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Response:
{
  "api_key": "cv_abc123def456...",
  "monthly_limit": 1000,
  "expires_at": "2024-12-31T23:59:59Z"
}
```

### Kota Takibi

```bash
# Kullanım durumunu kontrol et
curl -X GET "http://localhost:8001/api/v1/recruiter/subscriptions/usage" \
  -H "X-API-Key: cv_abc123def456..."

# Response:
{
  "monthly_limit": 1000,
  "monthly_usage": 45,
  "remaining": 955,
  "is_active": true
}
```

## 📤 CV İşleme

### Tek Dosya İşleme

```bash
curl -X POST "http://localhost:8001/api/v1/recruiter/process-local" \
  -H "X-API-Key: cv_abc123def456..." \
  -F "job_id=1" \
  -F "files=@cv.pdf"

# Response:
{
  "results": [{
    "filename": "cv.pdf",
    "final_score": 85.5,
    "ats_score": 78.2,
    "status": "success"
  }],
  "downloads": {
    "csv": "/api/v1/downloads/csv_abc123...",
    "json": "/api/v1/downloads/json_def456..."
  }
}
```

### Çoklu Dosya İşleme

```bash
curl -X POST "http://localhost:8001/api/v1/recruiter/process-local" \
  -H "X-API-Key: cv_abc123def456..." \
  -F "job_id=1" \
  -F "files=@cv1.pdf" \
  -F "files=@cv2.docx" \
  -F "files=@cv3.txt"
```

### Sonuç İndirme

```bash
# CSV indir
curl -X GET "http://localhost:8001/api/v1/downloads/csv_abc123..." \
  -o results.csv

# JSON indir
curl -X GET "http://localhost:8001/api/v1/downloads/json_def456..." \
  -o results.json
```

## 🎨 Frontend Entegrasyonu

### React Bileşeni Kullanımı

```jsx
import BatchUploadLocalMode from './components/BatchUploadLocalMode'

function LocalProcessingPage() {
  const [apiKey, setApiKey] = useState('')
  const [jobs, setJobs] = useState([])

  return (
    <BatchUploadLocalMode
      apiKey={apiKey}
      jobs={jobs}
      onSuccess={(results) => {
        console.log('İşleme tamamlandı:', results)
      }}
      onError={(error) => {
        console.error('Hata:', error)
      }}
    />
  )
}
```

### API Client Kurulumu

```javascript
// api.js
const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8001'

export const api = {
  generateApiKey: () => axios.post(`${API_BASE}/api/v1/recruiter/subscriptions/generate-key`),

  processLocal: (formData) => axios.post(`${API_BASE}/api/v1/recruiter/process-local`, formData),

  getUsage: (apiKey) => axios.get(`${API_BASE}/api/v1/recruiter/subscriptions/usage`, {
    headers: { 'X-API-Key': apiKey }
  }),

  downloadFile: (downloadId) => axios.get(`${API_BASE}/api/v1/downloads/${downloadId}`)
}
```

## 🔒 Güvenlik

### API Key Güvenliği

```python
# Güvenli API key validasyonu
def validate_api_key(api_key: str, db: Session) -> APISubscription:
    if not api_key.startswith('cv_'):
        raise HTTPException(status_code=401, detail="Invalid API key format")

    subscription = db.query(APISubscription).filter(
        APISubscription.api_key == api_key,
        APISubscription.is_active == True
    ).first()

    if not subscription:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Kota kontrolü
    if subscription.monthly_usage >= subscription.monthly_limit:
        raise HTTPException(status_code=429, detail="Monthly quota exceeded")

    return subscription
```

### Dosya Güvenliği

```python
# Dosya türü validasyonu
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def validate_file(file: UploadFile) -> bool:
    # Uzantı kontrolü
    if not any(file.filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS):
        return False

    # Boyut kontrolü
    if file.size > MAX_FILE_SIZE:
        return False

    return True
```

## 📊 İzleme ve Loglama

### Sistem Metrikleri

```python
# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
PROCESSING_TIME = Histogram('cv_processing_duration', 'CV processing time')
API_KEY_USAGE = Counter('api_key_usage_total', 'API key usage by organization')
```

### Log Yapılandırması

```python
# logging_config.py
LOGGING_CONFIG = {
    'version': 1,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        }
    },
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'logs/cv_analyzer.log',
            'formatter': 'detailed'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['file']
    }
}
```

## 🚨 Sorun Giderme

### Yaygın Problemler

**API Key Hatası:**
```bash
# API key'i kontrol et
curl -X GET "http://localhost:8001/api/v1/recruiter/subscriptions/usage" \
  -H "X-API-Key: YOUR_API_KEY"
```

**Dosya İşleme Hatası:**
```bash
# Logları kontrol et
tail -f logs/cv_analyzer.log

# Dosya formatını kontrol et
file your_cv.pdf
```

**Veritabanı Bağlantı Hatası:**
```bash
# PostgreSQL durumunu kontrol et
sudo systemctl status postgresql

# Bağlantıyı test et
psql -h localhost -U cv_user -d cv_analyzer
```

### Performans Optimizasyonu

```python
# Worker sayısı ayarı
WORKER_COUNT = multiprocessing.cpu_count()

# Batch işleme
BATCH_SIZE = 10

# Cache ayarları
REDIS_CACHE_TTL = 3600
```

## 📈 Ölçeklendirme

### Horizontal Scaling

```bash
# Load balancer arkasında multiple instance
docker-compose up --scale app=3

# Redis cluster
redis-cli --cluster create 127.0.0.1:7001 127.0.0.1:7002 127.0.0.1:7003
```

### Veritabanı Optimizasyonu

```sql
-- Index'ler
CREATE INDEX CONCURRENTLY idx_api_subscriptions_api_key ON api_subscriptions(api_key);
CREATE INDEX CONCURRENTLY idx_api_subscriptions_org ON api_subscriptions(organization_id);

-- Partitioning (büyük ölçekte)
CREATE TABLE api_subscriptions_y2024 PARTITION OF api_subscriptions
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
```

## 🔄 Bakım

### Otomatik Backup

```bash
# Cron job
0 2 * * * pg_dump cv_analyzer > /backups/cv_analyzer_$(date +\%Y\%m\%d).sql

# Dosya temizliği
0 * * * * find /tmp/downloads -name "*.csv" -mmin +60 -delete
0 * * * * find /tmp/downloads -name "*.json" -mmin +60 -delete
```

### Güncelleme Prosedürü

```bash
# 1. Backup al
pg_dump cv_analyzer > backup.sql

# 2. Yeni kodu deploy et
git pull origin main
pip install -r requirements.txt --upgrade

# 3. Migration çalıştır
alembic upgrade head

# 4. Servisleri yeniden başlat
docker-compose restart app

# 5. Test et
curl -X GET "http://localhost:8001/health"
```

## 📞 Destek

### Dokümantasyon
- [API Reference](http://localhost:8001/docs)
- [LOCAL_PROCESSING_GUIDE.md](./LOCAL_PROCESSING_GUIDE.md)
- [TEST_DOCUMENTATION.md](./TEST_DOCUMENTATION.md)

### Hata Bildirimi
```bash
# Sistem bilgilerini topla
python -c "import sys; print(f'Python: {sys.version}')"

# Log dosyalarını incele
tail -n 100 logs/cv_analyzer.log

# Veritabanı durumunu kontrol et
psql -d cv_analyzer -c "SELECT version();"
```

---

**Bu kılavuz ile herhangi bir developer veya IT ekibi, local processing mode'u kurup çalıştırabilir.** 🚀