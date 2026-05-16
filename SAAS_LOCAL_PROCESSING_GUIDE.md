# SaaS Local Processing Mode - Kurulum Gerektirmeyen Çözüm

Bu dokümantasyon, **kurulum gerektirmeyen** SaaS tabanlı local processing mode'unu açıklar. Müşteriler Docker kurulumla uğraşmadan, sadece API key ile güvenli CV işleme yapabilir.

## 🎯 Konsept

### Mevcut Durum
- Müşteriler kendi sunucularına kurulum yapıyor
- Docker, PostgreSQL, Python kurulumu gerekli
- Teknik altyapı yönetimi müşteriye ait

### SaaS Modeli
- Biz (sağlayıcı) altyapıyı yönetiyoruz
- Müşteriler sadece API kullanıyor
- Kurulum yok, sadece entegrasyon

## 🏗️ Mimari

### SaaS Altyapısı

```
[Müşteri Sistemi] ──── API Key ────► [Bizim SaaS Altyapısı]
    │                                       │
    ├── Web App                            ├── Load Balancer
    ├── CRM Sistemi                        ├── API Gateway
    └── HR Yazılımı                        ├── Processing Workers
                                            ├── PostgreSQL Cluster
                                            ├── Redis Cache
                                            └── File Storage (S3)
```

### Güvenlik Modeli

```
1. API Key Authentication
   ├── JWT tabanlı oturum
   └── Organization bazlı izolasyon

2. Zero Data Retention Guarantee
   ├── CV'ler bellekte işlenir
   ├── Sonuçlar geçici olarak saklanır
   └── Otomatik temizlik (1 saat)

3. Enterprise Security
   ├── SOC 2 Type II compliance
   ├── End-to-end encryption
   └── Audit logging (metadata only)
```

## 🚀 SaaS Kurulumu

### 1. Multi-Tenant Database Schema

```sql
-- Organization bazlı izolasyon
CREATE TABLE organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) UNIQUE,
    plan_type VARCHAR(50) DEFAULT 'pro',
    billing_status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    settings JSONB DEFAULT '{}'
);

-- API key yönetimi
CREATE TABLE api_subscriptions (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER REFERENCES organizations(id),
    api_key VARCHAR(255) UNIQUE NOT NULL,
    monthly_limit INTEGER DEFAULT 1000,
    monthly_usage INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tenant bazlı job'lar
CREATE TABLE recruiter_jobs (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER REFERENCES organizations(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Geçici sonuçlar (auto-cleanup)
CREATE TABLE temp_results (
    id VARCHAR(255) PRIMARY KEY,
    organization_id INTEGER REFERENCES organizations(id),
    data JSONB,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 2. Docker Compose (Bizim Altyapı)

```yaml
version: '3.8'
services:
  # API Gateway
  gateway:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx/ssl:/etc/ssl/certs
      - ./nginx/conf.d:/etc/nginx/conf.d
    depends_on:
      - api

  # FastAPI Backend
  api:
    build: .
    environment:
      - ENV=production
      - DATABASE_URL=postgresql://user:pass@db/cv_analyzer
      - REDIS_URL=redis://redis:6379
      - S3_BUCKET=cv-processing-results
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1.0'
          memory: 2G
    depends_on:
      - db
      - redis

  # PostgreSQL Cluster
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=cv_analyzer
      - POSTGRES_USER=cv_user
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    deploy:
      replicas: 2

  # Redis Cache
  redis:
    image: redis:7-alpine
    deploy:
      replicas: 2

  # Background Workers
  worker:
    build: .
    command: celery worker -A tasks --loglevel=info
    environment:
      - DATABASE_URL=postgresql://user:pass@db/cv_analyzer
    deploy:
      replicas: 5

  # Monitoring
  prometheus:
    image: prom/prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
```

### 3. API Gateway Konfigürasyonu

```nginx
# nginx/conf.d/api.conf
upstream api_backend {
    server api:8001;
    server api:8002;
    server api:8003;
}

server {
    listen 443 ssl http2;
    server_name api.cv-processor.com;

    ssl_certificate /etc/ssl/certs/api.crt;
    ssl_certificate_key /etc/ssl/certs/api.key;

    # Rate limiting
    limit_req zone=api burst=10 nodelay;

    location /api/v1/ {
        proxy_pass http://api_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeout ayarları
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # Health check
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
```

## 👥 Müşteri Onboarding

### 1. Self-Service Portal

```html
<!-- customer-portal.html -->
<div class="onboarding">
    <h1>CV Processing API</h1>

    <div class="step">
        <h3>1. Organizasyon Oluştur</h3>
        <form id="org-form">
            <input type="text" placeholder="Şirket Adı" required>
            <input type="email" placeholder="Admin Email" required>
            <select name="plan">
                <option value="starter">Starter (100 CV/ay)</option>
                <option value="pro">Pro (1000 CV/ay)</option>
                <option value="enterprise">Enterprise (Sınırsız)</option>
            </select>
            <button type="submit">Oluştur</button>
        </form>
    </div>

    <div class="step">
        <h3>2. API Key Al</h3>
        <div id="api-key-display" style="display:none;">
            <code id="api-key">cv_xxxxxxxxxxxxxxxx</code>
            <button onclick="copyApiKey()">Kopyala</button>
        </div>
    </div>

    <div class="step">
        <h3>3. Test Et</h3>
        <button onclick="testApi()">API Test</button>
        <pre id="test-result"></pre>
    </div>
</div>
```

### 2. API Key Dağıtımı

```javascript
// Otomatik API key oluşturma
app.post('/api/v1/organizations', async (req, res) => {
    const { name, email, plan } = req.body;

    // Organizasyon oluştur
    const org = await createOrganization({ name, email, plan });

    // API key oluştur
    const apiKey = await generateApiKey(org.id, plan);

    // Email gönder
    await sendWelcomeEmail(email, {
        organization: org,
        apiKey: apiKey,
        documentation: 'https://docs.cv-processor.com'
    });

    res.json({
        organization_id: org.id,
        api_key: apiKey.key,
        monthly_limit: apiKey.limit,
        dashboard_url: `https://dashboard.cv-processor.com/org/${org.id}`
    });
});
```

## 💰 Pricing & Billing

### Planlar

```javascript
const PLANS = {
    starter: {
        name: 'Starter',
        monthly_limit: 100,
        price: 29,
        features: ['Basic CV Analysis', 'CSV Export', 'Email Support']
    },
    pro: {
        name: 'Professional',
        monthly_limit: 1000,
        price: 99,
        features: ['Advanced Analysis', 'JSON Export', 'Priority Support', 'Custom Scoring']
    },
    enterprise: {
        name: 'Enterprise',
        monthly_limit: -1, // Unlimited
        price: 299,
        features: ['Unlimited Processing', 'Custom Integration', 'Dedicated Support', 'SLA Guarantee']
    }
};
```

### Stripe Entegrasyonu

```python
import stripe

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

def create_subscription(customer_id, plan_id):
    """Stripe subscription oluştur"""
    subscription = stripe.Subscription.create(
        customer=customer_id,
        items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': f'CV Processing - {PLANS[plan_id]["name"]}',
                },
                'unit_amount': PLANS[plan_id]['price'] * 100,
                'recurring': {
                    'interval': 'month',
                },
            },
        }],
        metadata={
            'plan_id': plan_id,
        }
    )
    return subscription
```

## 🔧 Teknik Detaylar

### Multi-Tenant Isolation

```python
def get_tenant_db(organization_id):
    """Tenant bazlı database connection"""
    # Row Level Security ile izolasyon
    engine = create_engine(DATABASE_URL)
    connection = engine.connect()

    # Tenant context ayarla
    connection.execute(text("SET app.organization_id = :org_id"), {
        'org_id': organization_id
    })

    return connection

def validate_api_key(api_key):
    """API key validasyonu ve tenant bilgisi"""
    subscription = db.query(APISubscription).filter(
        APISubscription.api_key == api_key,
        APISubscription.is_active == True
    ).first()

    if not subscription:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return {
        'organization_id': subscription.organization_id,
        'monthly_limit': subscription.monthly_limit,
        'monthly_usage': subscription.monthly_usage
    }
```

### Auto-Scaling

```python
# Kubernetes HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: cv-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: cv-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Monitoring & Alerting

```yaml
# Prometheus alerts
groups:
- name: cv-processing
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"

  - alert: LowQuotaRemaining
    expr: (api_key_limit - api_key_usage) / api_key_limit < 0.1
    for: 1h
    labels:
      severity: warning
    annotations:
      summary: "API key quota running low"
```

## 📊 Dashboard & Analytics

### Müşteri Dashboard

```jsx
function OrganizationDashboard({ organizationId }) {
    const [usage, setUsage] = useState({});
    const [jobs, setJobs] = useState([]);

    useEffect(() => {
        loadUsage();
        loadJobs();
    }, [organizationId]);

    return (
        <div className="dashboard">
            <div className="usage-card">
                <h3>Aylık Kullanım</h3>
                <ProgressBar
                    current={usage.monthly_usage}
                    total={usage.monthly_limit}
                />
                <p>{usage.remaining} CV kaldı</p>
            </div>

            <div className="jobs-list">
                <h3>İş İlanları</h3>
                {jobs.map(job => (
                    <JobCard key={job.id} job={job} />
                ))}
            </div>

            <div className="api-keys">
                <h3>API Keys</h3>
                <ApiKeyManager organizationId={organizationId} />
            </div>
        </div>
    );
}
```

### Admin Dashboard

```jsx
function AdminDashboard() {
    const [organizations, setOrganizations] = useState([]);
    const [metrics, setMetrics] = useState({});

    return (
        <div className="admin-dashboard">
            <div className="metrics-grid">
                <MetricCard title="Total Organizations" value={metrics.orgs} />
                <MetricCard title="Total CVs Processed" value={metrics.cvs} />
                <MetricCard title="Revenue" value={`$${metrics.revenue}`} />
                <MetricCard title="Active API Keys" value={metrics.keys} />
            </div>

            <div className="organizations-table">
                <h3>Organizations</h3>
                <DataTable
                    data={organizations}
                    columns={['name', 'plan', 'usage', 'status', 'actions']}
                />
            </div>
        </div>
    );
}
```

## 🔒 Güvenlik & Compliance

### SOC 2 Type II

```yaml
# Security controls
encryption:
  data_at_rest: AES-256
  data_in_transit: TLS 1.3
  database_encryption: enabled

access_control:
  multi_factor_auth: required
  role_based_access: enabled
  audit_logging: enabled

monitoring:
  intrusion_detection: enabled
  log_aggregation: centralized
  alerting: real_time

backup:
  daily_backups: enabled
  encrypted_backups: enabled
  backup_retention: 30_days
```

### GDPR Compliance

```python
def handle_data_deletion(organization_id):
    """GDPR right to erasure"""
    # Tüm verileri soft delete yap
    db.query(APISubscription).filter(
        APISubscription.organization_id == organization_id
    ).update({'is_active': False})

    # Geçici dosyaları sil
    delete_temp_files(organization_id)

    # Audit log tut (metadata only)
    audit_log('organization_deleted', {
        'organization_id': organization_id,
        'deleted_at': datetime.utcnow(),
        'gdpr_compliant': True
    })
```

## 🚀 Deployment Pipeline

### CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: |
          python -m pytest tests/ -v --cov=.
          coverage report --fail-under=90

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to staging
        run: |
          docker build -t cv-processor:${{ github.sha }} .
          docker push cv-processor:${{ github.sha }}
          kubectl set image deployment/cv-api cv-api=cv-processor:${{ github.sha }}

      - name: Run integration tests
        run: |
          npm run test:e2e

      - name: Deploy to production
        run: |
          kubectl set image deployment/cv-api cv-api=cv-processor:${{ github.sha }} --namespace production
```

## 📞 Destek & SLA

### SLA Garantileri

```
Response Time:
- Critical Issues: < 1 hour
- High Priority: < 4 hours
- Normal: < 24 hours

Uptime: 99.9%
Data Retention: 0 days (processing only)
Backup: Daily encrypted backups
```

### Destek Kanalları

```javascript
// Intercom integration
window.Intercom('boot', {
    app_id: 'your-app-id',
    email: user.email,
    organization_id: organization.id,
    plan: organization.plan
});
```

---

## 💡 Sonuç

Bu SaaS modeli ile:

✅ **Müşteriler kurulum yapmadan kullanabilir**
✅ **Biz altyapıyı yönetiriz**
✅ **Enterprise güvenlik ve compliance**
✅ **Scalable ve reliable**
✅ **Zero data retention guarantee**

Müşteriler sadece API key alıp, sistemi kullanmaya başlayabilir! 🚀