# CV Analyzer — cvanalyzer.dev Production Launch Runbook

Single-domain deploy: one VM runs `docker compose` (Redis, backend, nginx
serving the built frontend and proxying `/api`). PostgreSQL and authentication
stay on Supabase. Payments and blog stay hidden for beta
(`VITE_ENABLE_BILLING=false`, `VITE_ENABLE_BLOG=false`).

## 1. Google Cloud VM

Run from Cloud Shell or a machine with `gcloud` authenticated:

```bash
gcloud compute instances create cvanalyzer-prod \
  --zone=europe-west3-a \
  --machine-type=e2-standard-2 \
  --image-family=ubuntu-2404-lts-amd64 --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB --boot-disk-type=pd-balanced \
  --tags=http-server,https-server

gcloud compute firewall-rules create allow-http  --allow tcp:80  --target-tags=http-server
gcloud compute firewall-rules create allow-https --allow tcp:443 --target-tags=https-server

# Static IP (so DNS never breaks on VM restart)
gcloud compute addresses create cvanalyzer-ip --region=europe-west3
gcloud compute instances delete-access-config cvanalyzer-prod --zone=europe-west3-a
gcloud compute instances add-access-config cvanalyzer-prod --zone=europe-west3-a \
  --address=$(gcloud compute addresses describe cvanalyzer-ip --region=europe-west3 --format='value(address)')
```

`e2-standard-2` (2 vCPU / 8 GB) ≈ $50/ay; parser + model worker RAM'i için
minimum bu. Daha ucuz başlangıç istersen `e2-medium` (4 GB) dener, izlersin.

## 2. Server bootstrap

```bash
gcloud compute ssh cvanalyzer-prod --zone=europe-west3-a

sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER && newgrp docker

git clone <REPO_URL> cv-analyzer && cd cv-analyzer
cp .env.production.example .env            # fill EVERY empty value
cp frontend/.env.production.example frontend/.env.production  # fill Supabase values

# Cloudflare Dashboard -> SSL/TLS -> Origin Server -> Create certificate.
# Cover cvanalyzer.dev and *.cvanalyzer.dev, then save the PEM files locally:
mkdir -p deploy/ssl
nano deploy/ssl/origin.pem
nano deploy/ssl/origin-key.pem
chmod 600 deploy/ssl/origin-key.pem

docker compose -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f app
```

Alembic migrations: the app self-creates missing tables, but run
`docker compose -f docker-compose.prod.yml exec app alembic upgrade heads` once
to be explicit.

## 3. Cloudflare DNS and TLS

Cloudflare -> cvanalyzer.dev -> DNS -> Records:

| Type  | Host | Answer            | TTL  | Proxy   |
|-------|------|-------------------|------|---------|
| A     | @    | `<cvanalyzer-ip>` | Auto | Proxied |
| CNAME | www  | `cvanalyzer.dev`  | Auto | Proxied |

Cloudflare -> SSL/TLS -> Overview altında encryption mode **Full (strict)**
olmalı. `nslookup cvanalyzer.dev` Cloudflare IP'lerini döndürür; origin IP'nin
gizli kalması normaldir. Origin certificate yalnızca Cloudflare ile origin
arasındaki bağlantı içindir.

## 4. Supabase redirect URLs

Supabase Dashboard → Authentication → URL Configuration:

- **Site URL:** `https://cvanalyzer.dev`
- **Redirect URLs:**
  - `https://cvanalyzer.dev/login` (password reset — `resetPasswordForEmail` redirects here)
  - `https://cvanalyzer.dev/dashboard`
  - `https://cvanalyzer.dev` (Google OAuth dönüşü `window.location.origin`)
  - Lokal geliştirme için `http://localhost:5173` girişlerini koru.

Google OAuth kullanılıyorsa Google Cloud Console → OAuth client'a da
`https://<project-ref>.supabase.co/auth/v1/callback` zaten kayıtlı olmalı
(Supabase tarafı değişmiyor, sadece redirect listesi genişliyor).

## 5. Production smoke test

```bash
./deploy/smoke_prod.sh https://cvanalyzer.dev
```

Sonra elle (gerçek Supabase hesabıyla): kayıt → giriş → CV analizi → geçmişte
sonucu görme → Data Center export → Ayarlar'dan test hesabını silme (hesap ve
verilerin gerçekten gittiğini `/api/v1/me/data-summary` 401/404 ile doğrula).

## 6. Beta launch checklist

- [ ] `ENV=production`, `MOCK_SERVICES=0` (aksi halde auth mock'a düşer — kritik)
- [ ] Stripe anahtarları boş ve `VITE_ENABLE_BILLING=false`
- [ ] `VITE_ENABLE_BLOG=false`
- [ ] `ADMIN_TOKEN`, `BILLING_ADMIN_TOKEN`, `WORKER_DOWNLOAD_SIGNING_SECRET` set
- [ ] Smoke script yeşil + elle akış tamam
- [ ] Sentry DSN girildi, ilk hata görünüyor
- [ ] DNS + TLS: `curl -I https://cvanalyzer.dev` → 200, HSTS başlığı var
