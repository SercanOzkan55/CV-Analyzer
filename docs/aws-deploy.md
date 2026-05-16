# AWS Deployment Guide — CV Analyzer (Private Mode)

Bu kılavuz, CV Analyzer'ı AWS üzerinde özel domain ile sadece senin kullanabileceğin şekilde deploy etmeni sağlar.

## Mimari

```
[Route 53] → [EC2 + Docker Compose]
                ├── nginx (80/443) → Frontend SPA + Backend Proxy
                ├── app (FastAPI :8001)
                ├── db (PostgreSQL + pgvector)
                └── redis
```

---

## 1. Domain Satın Alma (Route 53)

```bash
# AWS Console → Route 53 → Register Domain
# Veya CLI ile:
aws route53domains register-domain \
  --domain-name cvanalyzer.com \
  --duration-in-years 1 \
  --admin-contact file://contact.json \
  --registrant-contact file://contact.json \
  --tech-contact file://contact.json
```

> `.com` ~$12/yıl, `.app` ~$14/yıl, `.dev` ~$12/yıl  
> Zaten bir domainin varsa Route 53 Hosted Zone oluşturup nameserver'ları yönlendir.

---

## 2. EC2 Instance Oluşturma

### 2a. Instance Başlatma

```bash
# t3.small yeterli (2 vCPU, 2GB RAM)
aws ec2 run-instances \
  --image-id ami-0c02fb55956c7d316 \
  --instance-type t3.small \
  --key-name my-key-pair \
  --security-group-ids sg-xxxxxxxx \
  --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":30}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=cv-analyzer}]'
```

### 2b. Security Group Ayarları

| Port | Kaynak | Açıklama |
|------|--------|----------|
| 22   | Senin IP (x.x.x.x/32) | SSH |
| 80   | 0.0.0.0/0 | HTTP → HTTPS redirect |
| 443  | 0.0.0.0/0 | HTTPS |

```bash
# Sadece kendi IP'ni SSH'ye izin ver
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxxxxx \
  --protocol tcp --port 22 \
  --cidr YOUR_IP/32
```

### 2c. Elastic IP (Sabit IP)

```bash
aws ec2 allocate-address --domain vpc
aws ec2 associate-address --instance-id i-xxxxxxxx --allocation-id eipalloc-xxxxxxxx
```

---

## 3. DNS Ayarları (Route 53)

```bash
# A kaydı ekle → Elastic IP'ye yönlendir
aws route53 change-resource-record-sets \
  --hosted-zone-id ZXXXXXXXXXXXXX \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "app.senindomain.com",
        "Type": "A",
        "TTL": 300,
        "ResourceRecords": [{"Value": "ELASTIC_IP"}]
      }
    }]
  }'
```

---

## 4. Sunucu Kurulumu

```bash
# EC2'ye bağlan
ssh -i my-key-pair.pem ec2-user@ELASTIC_IP

# Docker ve Docker Compose kur
sudo yum update -y
sudo yum install -y docker git
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# Docker Compose v2
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Yeniden bağlan (grup değişikliği için)
exit
ssh -i my-key-pair.pem ec2-user@ELASTIC_IP
```

---

## 5. SSL Sertifikası (Let's Encrypt)

```bash
# Certbot kur
sudo yum install -y certbot

# Önce nginx'i geçici olarak durdur (80 portu boş olmalı)
# Sertifika al
sudo certbot certonly --standalone \
  -d app.senindomain.com \
  --email ozkansercan55@gmail.com \
  --agree-tos --non-interactive

# Sertifikaları ssl/ klasörüne kopyala
mkdir -p ~/cv-analyzer/ssl
sudo cp /etc/letsencrypt/live/app.senindomain.com/fullchain.pem ~/cv-analyzer/ssl/cert.pem
sudo cp /etc/letsencrypt/live/app.senindomain.com/privkey.pem ~/cv-analyzer/ssl/key.pem
sudo chown ec2-user:ec2-user ~/cv-analyzer/ssl/*
```

### Otomatik Yenileme (crontab)

```bash
echo "0 3 * * * certbot renew --quiet && cp /etc/letsencrypt/live/app.senindomain.com/fullchain.pem /home/ec2-user/cv-analyzer/ssl/cert.pem && cp /etc/letsencrypt/live/app.senindomain.com/privkey.pem /home/ec2-user/cv-analyzer/ssl/key.pem && cd /home/ec2-user/cv-analyzer && docker compose restart nginx" | sudo crontab -
```

---

## 6. Proje Deploy

```bash
cd ~
git clone https://github.com/SENIN_REPO/cv-analyzer.git
cd cv-analyzer

# .env dosyasını oluştur
cat > .env << 'EOF'
ENV=production
DATABASE_URL=postgresql://testuser:testpass@db:5432/testdb
POSTGRES_USER=GÜÇLÜ_KULLANICI
POSTGRES_PASSWORD=GÜÇLÜ_ŞİFRE
POSTGRES_DB=cvanalyzer
REDIS_PASSWORD=GÜÇLÜ_REDIS_ŞİFRESİ
REDIS_URL=redis://:GÜÇLÜ_REDIS_ŞİFRESİ@redis:6379/1
SUPABASE_JWT_SECRET=senin_supabase_jwt_secret
SUPABASE_URL=https://oanidolrgdukiqxvvbzd.supabase.co
EOF

# Frontend .env
cat > frontend/.env << 'EOF'
VITE_API_BASE=https://app.senindomain.com
VITE_SUPABASE_URL=https://oanidolrgdukiqxvvbzd.supabase.co
VITE_SUPABASE_KEY=sb_publishable_jtUrR1fRO7YbWwecyeGcVQ_00jbDGfo
VITE_BILLING_ADMIN_EMAILS=ozkansercan55@gmail.com
VITE_PRIVATE_MODE=true
EOF

# Build ve başlat
docker compose up -d --build
```

---

## 7. Supabase'de Kayıt Kapatma (ÖNEMLİ)

1. [Supabase Dashboard](https://supabase.com/dashboard) → Projen → **Authentication** → **Settings**
2. **Enable Sign Ups** → **OFF** yap
3. Bu sayede yeni kullanıcı kaydı tamamen engellenecek
4. Sadece mevcut hesabınla (ozkansercan55@gmail.com) giriş yapabilirsin

---

## 8. nginx.conf'ta Domain Güncelle

`nginx.conf` dosyasında `server_name _` satırlarını domain adınla değiştir:

```nginx
server_name app.senindomain.com;
```

---

## 9. Kontrol Listesi

- [ ] Domain satın alındı / DNS yönlendirildi
- [ ] EC2 instance çalışıyor
- [ ] Elastic IP atandı
- [ ] Route 53 A kaydı eklendi
- [ ] SSL sertifikası alındı
- [ ] Security Group sadece 22 (kendi IP), 80, 443 açık
- [ ] `.env` dosyaları oluşturuldu
- [ ] `docker compose up -d --build` çalıştı
- [ ] Supabase'de kayıt kapatıldı
- [ ] `https://app.senindomain.com` erişilebilir
- [ ] Login sayfasına yönlendiriyor (private mode)

---

## Faydalı Komutlar

```bash
# Logları görüntüle
docker compose logs -f app
docker compose logs -f nginx

# Yeniden başlat
docker compose restart

# Güncelleme
git pull && docker compose up -d --build

# Backup (PostgreSQL)
# Detayli runbook: docs/backup-restore.md
docker compose exec app ./scripts/backup_db.sh
```

---

## Tahmini Maliyet (aylık)

| Hizmet | Maliyet |
|--------|---------|
| EC2 t3.small | ~$15 |
| Domain (.com) | ~$1/ay |
| Elastic IP | $0 (instance'a bağlıysa) |
| EBS 30GB | ~$2.40 |
| **Toplam** | **~$18/ay** |

> İpucu: 1 yıllık Reserved Instance ile EC2 %30-40 ucuzlar.
