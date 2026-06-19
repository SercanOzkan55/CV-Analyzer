# CV Analyzer Yerel Proje Denetim Raporu

Tarih: 2026-06-19
Kapsam: Sadece `C:\Users\ASUS\Desktop\cv-analyzer` yerel klasoru incelendi. GitHub, internet veya remote repo kaynak alinmadi.
Mod: Okuma agirlikli audit. Bu rapor dosyasi disinda kod degisikligi yapilmadi.

## Kullanilan Ajanlar ve Yontem

- Backend / guvenlik ajani: FastAPI, auth, tenant izolasyonu, upload, privacy, worker API.
- Frontend / UI ajani: React/Vite, localStorage, route guard, API helper, accessibility, motion.
- Local Worker / QML ajani: `local_worker`, QML UI, offline sync, paketleme, CSV/HTML export.
- Test / deploy / dependency ajani: Docker, nginx, CI, dependency, migration, repo hijyeni.
- UI skill setleri: design review, frontend UI polish, frontend implementation, UI QA review talimatlari okundu.

## Kisa Sonuc

Projenin temeli guclu: JWT dogrulamasi, upload guard altyapisi, S3 guard, SSRF korumalari, React route yapisi, modal/toast accessibility, QML tarafa gecis ve kapsamli test klasoru iyi durumda.

Ama su an ship oncesi cozulmesi gereken ciddi blokajlar var:

1. Semantic search tarafinda tenant/user izolasyonu eksik. Baska organizasyon adaylari donme riski var.
2. Local worker bazi yollarda raw CV metnini sakliyor ve sync edebiliyor; UI "metadata only" algisi veriyor.
3. Local worker HTML raporu local stored XSS'e acik.
4. Docker/nginx production konfigleri hem cok buyuk local artifactleri image context'e alabilir hem de SPA/API'yi kirabilir.
5. Local API subscription key'leri plaintext tutuluyor ve tekrar gosteriliyor.
6. `.env` yerel dosyasinda canli gibi duran gizli anahtarlar var. Degerler rapora yazilmadi; bu anahtarlar rotasyona alinmali.

## Proje Envanteri

Ana teknoloji yiginlari:

- Backend: Python, FastAPI, SQLAlchemy, Alembic, Supabase JWT, Redis/Celery, S3 opsiyonel storage.
- Frontend: React 18, Vite, Framer Motion, lucide-react, Supabase client.
- Local desktop worker: Python, Qt Quick / QML, PySide6, local SQLite workspace, PyInstaller build.
- Mobile: Expo / React Native.
- Ops: Docker, docker-compose, nginx, GitHub Actions configleri.

Yaklasik satir dokumu, generated ve vendor klasorleri dislanarak:

| Tur | Dosya | Satir |
| --- | ---: | ---: |
| `.py` | 339 | 75,970 |
| `.json` | 65 | 33,053 |
| `.jsx` | 96 | 22,351 |
| `.css` | 7 | 16,096 |
| `.md` | 51 | 10,712 |
| `.tsx` | 25 | 3,701 |
| `.qml` | 5 | 3,393 |
| `.js` | 18 | 2,695 |
| `.ts` | 8 | 731 |

Yerel workspace hijyeni:

- Dirty worktree var: bircok modified tracked dosya ve cok sayida untracked dosya mevcut.
- Buyuk lokal dosyalar var: `cv-analyzer (4) (1).zip`, venv DLL'leri, local worker build/dist ciktilari, `.npm-cache`, node_modules.
- `.gitignore` genelde iyi ama `.dockerignore` ayni kadar guclu degil.
- `resume_model.pkl` tracked gorunuyor; `.gitignore` sonradan `*.pkl` ignore ediyor ama tracked dosya halen tarihcede/durumda kalabilir.

## Kritik Bulgular

| ID | Alan | Bulgu | Etki | Kanit | Oneri |
| --- | --- | --- | --- | --- | --- |
| SEC-01 | Backend / tenant izolasyonu | `find_similar_candidates` tum aday embedding'leri uzerinde org/user filtresi olmadan ariyor; route sonra global candidate id'lerini donuyor. | Cross-tenant aday verisi sizabilir. Bu en kritik guvenlik bulgusu. | `services/embedding_service.py:243`, `services/embedding_service.py:259`, `routes/ai_tools.py:76`, `routes/ai_tools.py:95`, `routes/ai_tools.py:165` | Vector search SQL'ine `organization_id`/owner scope ekle. Candidate fetch sorgularini da ayni scope ile kilitle. Cross-tenant regression testi yaz. |
| SEC-02 | Local worker privacy | Classic GUI/CLI/QML sync yollarinda raw `cv_text` persist/sync edilebiliyor; QML UI metadata-only algisi veriyor. | Yerel/gizli CV icerigi disk, JSON, SQLite veya sunucuya gidebilir. | `local_worker/gui.py:567`, `local_worker/gui.py:878`, `local_worker/worker.py:1613`, `local_worker/worker.py:1636`, `local_worker/qml_gui.py:552`, `local_worker/qml/Main.qml:2725` | Basarili row, JSON, HTML, SQLite ve sync payload'undan raw `cv_text` kaldir. Mevcut DB/JSON icin purge/migration araci ekle. |
| SEC-03 | Local worker report | HTML report job title/JSON/candidate alanlarini guvensiz basiyor; `innerHTML` kullanimlari var. | Malicious filename/job/skill ile lokal stored XSS. | `local_worker/worker.py:472`, `local_worker/worker.py:1126`, `local_worker/worker.py:1207` | HTML'i `textContent/createElement` ile kur veya escaping/template sanitizer kullan. Script icine gomulen JSON'u script-safe encode et. |
| OPS-01 | Docker/nginx | `Dockerfile` `COPY . /app` yapiyor; `.dockerignore` buyuk zip/cache/sqlite/build ciktilarini yeterince dislamiyor. Nginx CSP `script-src 'none'` Vite JS'i bloklar; `/api/` proxy path'i `/api` prefix'ini strip ediyor. | Production build devasa/sizintili olabilir; production site/API calismayabilir. | `Dockerfile:42`, `.dockerignore`, `nginx.conf:63`, `nginx.conf:111`, `nginx.conf:113` | `.dockerignore`'i `.gitignore` artifactleriyle guclendir. CSP'yi self-hosted JS/CSS'e uygun yap. `proxy_pass http://backend;` ile `/api/v1` path'ini koru. |
| SEC-04 | Secret hygiene | Yerel `.env` dosyasinda canli gibi duran OpenAI/Supabase/AWS/DB secretleri var. Dosya gitignored ama auditte goruldu. | Workspace/log/paylasim durumunda credential compromise riski. | Yerel `.env`, degerler redakte edildi. | Kullanilan anahtarlari rotate et. `.env`'i paylasma. Secret scanning'i lokal pre-commit veya CI gate yap. |

## Yuksek Oncelik Bulgular

| ID | Alan | Bulgu | Etki | Kanit | Oneri |
| --- | --- | --- | --- | --- | --- |
| SEC-05 | Recruiter local API | `APISubscription.api_key` plaintext saklaniyor, plaintext sorgulaniyor ve mevcut key tekrar donuyor. | DB dump veya log sizintisinda kalici API key compromise. | `models.py:57`, `routes/recruiter_local.py:41`, `routes/recruiter_local.py:47`, `routes/recruiter_local.py:95`, `routes/recruiter_local.py:116` | Key'i hashle, sadece ilk olusturmada goster, rotation/revoke ekle. |
| SEC-06 | ZIP import | LinkedIn ZIP import sadece extension kontrolu yapiyor; archive tamamini memory'ye aliyor, file count/ratio/path limit yok. | Zip bomb / memory DoS / traversal riski. | `routes/recruiter_local.py:300`, `routes/recruiter_local.py:411`, `utils/cv_processor.py:560`, `utils/cv_processor.py:645` | Merkezi ZIP guard: max archive bytes, max uncompressed bytes, max file count, compression ratio, path normalization. |
| SEC-07 | Recruiter quota | Batch kredi kontrolu ve `monthly_usage` artisi atomic degil. | Paralel isteklerle kota asimi. | `routes/recruiter.py:1153`, `routes/recruiter.py:1156`, `routes/recruiter.py:1170` | `SELECT ... FOR UPDATE` veya conditional `UPDATE ... WHERE monthly_usage + requested <= limit`. |
| SEC-08 | Privacy delete/export | Raw CV `Candidate` ve `CVVersion` tarafinda saklanirken privacy delete/export tum raw store'lari kapsamiyor. | KVKK/GDPR silme/indirme eksik kalabilir. | `routes/analysis.py:388`, `routes/analysis.py:390`, `routes/analysis.py:987`, `routes/user_data.py:513`, `routes/user_data.py:546` | Candidate, worker result, temp download ve raw CV retention yollarini export/delete kapsamına al. |
| SEC-09 | DOCX upload | `routes/analysis.py` DOCX'i central file guard yerine direkt extractor'a veriyor. | DOCX zip-bomb/hardening bypass. | `routes/analysis.py:34`, `routes/analysis.py:65`, `routes/analysis.py:70`, `security/file_guard.py:133` | Tum upload entrypoint'lerini tek hardened validation/extraction katmanindan gecir. |
| SEC-10 | Worker download URL | Server-provided absolute `download_url` isteklerinde bearer token tasiyan session kullaniliyor. | Compromised API worker'i farkli hosta yonlendirirse Authorization header sizabilir. | `local_worker/worker.py:1367`, `local_worker/worker.py:1410`, `local_worker/worker.py:1478` | Download hostunu API base ile ayni origin'e kilitle; foreign hostlara bearer gonderme. |
| SEC-11 | CSV export | Untrusted field'lar Excel-friendly CSV'ye direkt yaziliyor. | CSV formula injection. | `local_worker/qml_gui.py:297`, `local_worker/qml_gui.py:320`, `local_worker/worker.py:1637` | `=`, `+`, `-`, `@`, tab, CR/LF ile baslayan cell'leri sanitize et. |
| SEC-12 | Frontend job URL | Job tracker `href={job.url}` ile herhangi string'i linke basiyor. | Stored/client-side XSS veya unexpected scheme. | `frontend/src/pages/JobTrackerPage.jsx:181`, `frontend/src/pages/JobTrackerPage.jsx:311` | `sanitizeHttpUrl()` ekle; sadece `http:`/`https:` render et. |
| SEC-13 | Frontend localStorage | Recruiter session global monthly key'lerle tutuluyor, user'a scope edilmiyor ve sign-out'ta temizlenmiyor. | Ayni browser'da hesaplar arasi aday/email/action sizintisi. | `frontend/src/context/RecruiterSessionContext.jsx:44`, `frontend/src/context/RecruiterSessionContext.jsx:97`, `frontend/src/context/AuthContext.jsx:186` | Key'leri `user.id` ile scope et; sign-out'ta hassas recruiter/job/interview key'lerini temizle. |
| BUG-01 | Frontend API helpers | Bazi legacy recruiter API helper'lari `res.ok` kontrol etmeden `res.json()` donuyor. | Backend fail olsa bile UI "basarili" gosterebilir; mail/job aksiyonlari yaniltici olur. | `frontend/src/api.js:1538`, `frontend/src/api.js:1583`, `frontend/src/utils/recruiterErrorHandling.js:71`, `frontend/src/pages/RecruiterPage.jsx:855` | Tum helper'larda ortak request wrapper ve `!res.ok` throw davranisi kullan. |
| OPS-02 | Runtime drift | Docker Python 3.14, pyproject/CI Python 3.12; frontend Docker Node 20, CI Node 24. | Dev/CI/prod farkli davranabilir. | `Dockerfile:1`, `pyproject.toml:4`, `.github/workflows/ci.yml:18`, `frontend/Dockerfile:1`, `.github/workflows/ci.yml:195` | Python/Node version matrix'ini tek karara indir. |
| OPS-03 | CI advisory gates | Ruff format, Bandit, mypy, pip-audit, dependency-review non-blocking. | Kritik issue CI'da gorunur ama merge'i engellemez. | `.github/workflows/ci.yml:35`, `.github/workflows/ci.yml:39`, `.github/workflows/ci.yml:50`, `.github/workflows/security.yml:44`, `.github/workflows/security.yml:66` | Release branch'te block et; advisory istiyorsan ayri job/status yap. |
| DIST-01 | Local worker package | `run_gui.cmd` `qml_gui.py` calistiriyor ama server ZIP package hala `qt_gui.py` ve QML dosyalarini package listesine almiyor. README de `qt_gui.py` referansi tasiyor. | Indirilen local worker yeni QML arayuzuyle calismayabilir. | `local_worker/run_gui.cmd`, `routes/worker.py:357`, `routes/worker.py:599`, `routes/worker.py:601` | ZIP package'a `qml_gui.py` ve `qml/` klasorunu ekle; README/CI verify listesini guncelle. |
| OPS-04 | Feedback email | Feedback JSONL'e yaziliyor ama mail icin `SMTP_HOST` veya `SENDGRID_API_KEY` yoksa sadece `emailed: false` donuyor. Kullanici "mail attim" sanabilir. | Support mailbox'a dusmeme, ops takip kaybi. | `services/email_service.py:83`, `services/email_service.py:117`, `services/email_service.py:124`, `routes/ai_tools.py:689`, `routes/ai_tools.py:732` | UI'da email backend durumunu goster; admin ops testini kullan; SMTP/SendGrid env'lerini kur; inbox'ta son 5/limitli gorunum ekle. |

## Orta Oncelik Bulgular

| ID | Alan | Bulgu | Oneri |
| --- | --- | --- | --- |
| SEC-14 | Diagnostics | `/health`, `/health/full`, `/metrics` fazla operasyonel bilgi veriyor; `/metrics` auth guard'siz. | Full health/metrics'i admin/internal yap; public health'i minimal tut. |
| SEC-15 | CORS/CSRF | CORS origins bos ise wildcard + credentials; CSRF default off. | Production'da explicit CORS zorunlu yap; cookie/session auth girerse CSRF'i zorunlu kıl. |
| SEC-16 | Error leaks | Birden fazla route raw exception message'i client'a donuyor. | Merkezi error sanitizer ve redacted logging kullan. |
| SEC-17 | Worker sync payload | Offline sync result alanlarinda string/list bound'lari zayif. | Pydantic max length/count ekle; raw CV retention'i en bastan engelle. |
| FE-01 | Client admin checks | Admin/recruiter UI public Vite env ile saklanip gosteriliyor; admin token sessionStorage'da. | Backend'i tek otorite tut; admin token yerine server-side role/session modeli tercih et. |
| FE-02 | Third-party calls | IP language detection, blog translation, Google fonts client-side dis servislere gidiyor. | Privacy mod/consent gate veya backend proxy; fontlari local bundle et. |
| FE-03 | Upload a11y | DragDropUpload clickable `div` + hidden input; keyboard path zayif. | Gercek `<label>`/button pattern, immediate validation ve focus state. |
| FE-04 | Reduced motion | Bazi motion alanlari `prefers-reduced-motion` ile uyumlu, bazilari degil. | Global `MotionConfig reducedMotion="user"` veya ortak wrapper. |
| FE-05 | Object URL leak | PDF/blog preview object URL'leri revoke edilmiyor. | Modal close, file change, unmount ve `window.open` sonrasi revoke. |
| DATA-01 | Local DB/output | SQLite/result dosyalari predictable klasorlerde ve sifresiz. | `%LOCALAPPDATA%`, tighter permissions, opsiyonel encryption-at-rest. |
| DATA-02 | Recursive scans | Output folder CV klasoru altina yazilabiliyor, sonraki recursive scan'de tekrar islenebilir. | Output klasorlerini scan disina al; symlink/out-of-root skip. |
| OPS-05 | Migration | `migrations/` aktifken ayrica orphan `alembic/versions` var. | Tek migration tree tut; orphan migration'i tasima veya silme karari ver. |
| OPS-06 | Requirements | Production requirements dev/test/security araclarini da iceriyor. | `requirements-prod.txt` / `requirements-dev.txt` ayir. |
| OPS-07 | Mobile coverage | Mobile package Dependabot/audit/typecheck/test kapsaminda degil. | `/mobile` icin audit, typecheck ve minimum test scriptleri ekle. |
| OPS-08 | Docs stale | Test/deploy docs missing dosyalara veya eski workflow'a referans veriyor. | Docs'lari mevcut script/workflow ile hizala. |
| CODE-01 | Main monolith | `main.py` cok buyuk import/re-export yapiyor; encoding mojibake izleri var. | App factory/router wiring ve legacy re-export'lari azalt; encoding temizligi yap. |
| CODE-02 | JWKS cache | Asimetrik JWT JWKS fetch caching zayif gorunuyor. | TTL cache + kid bazli cache ekle. |

## Dusuk Oncelik / Bakim Notlari

- Root `package.json` sadece dependency tasiyor, script yok; frontend React 18 iken root type package'lari React 19 tarafina kaymis.
- `VITE_API_BASE_URL` ve `VITE_API_BASE` isimleri dev script/app arasinda karisik.
- Global `overflow-x: hidden/clip` mobil overflow bug'larini QA'da saklayabilir.
- QML worker key'i UI/in-memory state'te save sonrasi kaliyor; classic GUI temizliyor.
- Crash/progress loglari path ve error text icerebilir; redaction/purge politikasi eklenebilir.
- Local worker build pipeline broad `>=` dependency, package upgrade scriptleri, UPX ve unsigned EXE ile reproducible degil.

## Iyi Calisan Kisimlar

- JWT dogrulama token length, exp, audience/issuer destegi ve production mock-auth guard iceriyor.
- `security/file_guard.py` kullanildigi yerlerde PDF/DOCX magic, page/object, zip-bomb ve path/encryption kontrolleri guclu.
- CV storage tarafinda file guard + ownership kontrolleri var.
- S3 config kucuk upload defaultlari, kisa presigned expiry, SSE/KMS ve production validation tasiyor.
- Job import SSRF savunmalari iyi: scheme, credentials, DNS, private/reserved IP ve redirect kontrolleri var.
- Frontend route lazy loading, Suspense, ErrorBoundary, PrivateRoute/PublicRoute yapisi iyi.
- Modal component Escape, focus restore ve tab trap ile iyi durumda.
- Toast live-region semantigi var.
- Analyze upload tarafinda temel tip ve 10 MB limit var.
- QML ana analiz yolu basarili row'larda raw `cv_text` saklamamaya baslamis; bu dogru yon.
- Local worker credentials OS keyring kullanabiliyor.
- SQLite write'lari parameterized query ile yapiliyor.
- CI genis kapsamli: backend tests, frontend build/test/typecheck, benchmark, Docker build, Trivy/Gitleaks/pip-audit/npm audit mevcut.
- `.gitignore` secret/db/log/cache/model/scratch dosyalari icin genel olarak iyi.

## Tavsiye Edilen Duzeltme Sirasi

1. **Tenant izolasyonu**: `find_similar_candidates` ve route candidate fetch'lerini org/user scope ile kilitle; test yaz.
2. **Raw CV retention**: local worker DB/JSON/HTML/sync payload'larindan `cv_text` kaldir; purge/migration ekle.
3. **Local report XSS + CSV injection**: HTML escaping, script-safe JSON ve CSV formula sanitize.
4. **Production deploy unblock**: `.dockerignore`, nginx CSP ve `/api` proxy fix.
5. **API key modeli**: `APISubscription.api_key` hash/rotation/show-once modeline gecir.
6. **ZIP/DOCX hardening**: LinkedIn ZIP guard ve tum upload path'lerini central file guard'a bagla.
7. **Privacy delete/export**: Candidate, worker result, temp download ve raw stores kapsamlarini tamamla.
8. **Quota atomicity**: recruiter batch kota artisini DB seviyesinde atomic hale getir.
9. **Frontend XSS/localStorage/API errors**: job URL sanitize, localStorage user scope, `res.ok` wrapper.
10. **Feedback email ops**: SMTP/SendGrid konfigurasyonu, UI'da `emailed:false` gorunurlugu, inbox'ta son 5 kompakt liste.
11. **CI/dependency hardening**: blocking security gates, version alignment, mobile CI, prod/dev requirements ayrimi.
12. **Repo hijyeni**: buyuk lokal artifactleri temizle, stale docs/root package/duplicate migrations duzenle.

## Test ve Dogrulama Durumu

- Frontend ajanindan gelen bilgi: `npm.cmd run typecheck` basarili.
- Bu ana audit turunda build/test calistirmadim; cunku kullanici audit istedi ve build/coverage komutlari `dist`, cache veya coverage ciktilari uretebilir. Mevcut worktree zaten dirty.
- GitHub/remote kaynak kullanilmadi.
- Secret degerleri rapora yazilmadi.

## Notlar

Bu rapor "hemen kodu degistir" degil, "ne var, ne kotu, ne kritik, ne iyi" dokumudur. Duzeltmeye baslanacaksa ilk PR/commit grubu backend tenant izolasyonu + local worker raw CV retention + Docker/nginx unblock olmalidir. UI polish ve animasyonlar bu guvenlik/ops blokajlarindan sonra daha rahat ilerler.

## Claude Raporu ile Birlesik Uygulama Notu

Claude raporundaki bulgular bu raporla karsilastirildi. Asagidaki maddeler bu turda kodla kapatildi veya guvenli ilk adimlari atildi:

| Durum | Bulgu | Yapilan |
| --- | --- | --- |
| Kapatildi | Supabase JWKS her token validation'da fetch ediliyor. | `auth.py` icine TTL'li in-memory JWKS cache ve stale-cache fallback eklendi. |
| Kapatildi | `services/model_worker.py` response queue thrash / CPU spin riski. | Shared response queue yerine request-id bazli pending registry + dispatcher thread eklendi. |
| Kapatildi | `useWebSocketProgress.js` reconnect loop. | WebSocket state yerine `useRef` kullanildi; cleanup artik state degisiminden tetiklenmiyor. |
| Kapatildi | Semantic search cross-tenant candidate leakage. | `find_similar_candidates` organization scope zorunlu hale getirildi; route fetch'leri ayni org filtresiyle sinirlandi. |
| Kapatildi | `nginx.conf` CSP Vite JS'i blokluyor ve `/api/` proxy prefix'i strip ediyor. | CSP self-hosted JS/CSS icin duzeltildi; `/api/` proxy path'i korunuyor. |
| Kapatildi | Docker context buyuk/local artifactleri alabilir. | `.dockerignore` zip/sqlite/cache/runtime/build/local worker artifactlerini dislayacak sekilde genisletildi. |
| Kapatildi | Local worker ZIP paketi QML UI dosyalarini icermiyor. | `routes/worker.py` package listesine `qml_gui.py` ve `qml/` dosyalari eklendi; README komutu QML'e cekildi. |
| Kapatildi | Local worker OpenAI fallback invalid model/endpoint kullaniyor. | Varsayilan model `gpt-4o-mini`, endpoint `chat/completions`, messages payload ve JSON response format kullanacak sekilde guncellendi. |
| Kapatildi | `qt_gui.py` paint loop'larinda theme dosyasi tekrar okunabiliyor. | Aktif theme bellek cache'i eklendi; disk okuma explicit theme degisiminde yenileniyor. |
| Kapatildi | `qt_gui.py` bulk email thread sahte basari bildiriyor. | Direkt mail gondermedigi durumda artik success degil, acik "email was not sent" uyarisi donuyor. |
| Kapatildi | Job tracker URL alanlari `javascript:` gibi semalara acik. | URL sanitize helper eklendi; sadece `http:`/`https:` kaydedilip render ediliyor. |
| Kapatildi | Legacy recruiter API helper'lari `res.ok` kontrol etmiyor. | Kritik helper'lar `jsonOrThrow` ile backend hatalarini throw edecek sekilde guncellendi. |
| Kapatildi | RecruiterPage `selectedJob` stale closure. | `loadJobs` aktif isi functional state ile koruyor; reload sonrasi yanlis reset riski azaldi. |
| Kapatildi | Local worker relative SQLite path. | Varsayilan workspace DB `%LOCALAPPDATA%\CV Analyzer Local Worker` altina alindi; legacy DB varsa hedefe kopyalanir. |
| Kapatildi | CSV formula injection. | QML ve CLI CSV export'larinda riskli baslangic karakterleri apostrofla sanitize ediliyor. |
| Kismen kapatildi | Local worker raw `cv_text` retention/sync. | Yeni local result row'lari ve QML/classic GUI sync payload'lari raw `cv_text` gondermiyor; server offline-sync yeni `Candidate`/`CandidateAction` kayitlarina raw CV yazmiyor. Eski DB/JSON kayitlari icin purge/migration hala gerekli. |
| Kismen kapatildi | Local HTML report XSS. | Script-safe JSON, escaped title, card metinlerinde HTML escaping ve decision class whitelist eklendi. Tam DOM-builder rewrite ileride daha temiz olur. |

Bu turda bilerek ertelenen buyuk maddeler:

- `APISubscription.api_key` plaintext -> hashed key migration: DB migration, backward compatibility ve key rotation akisi gerektiriyor.
- LinkedIn ZIP guard: merkezi archive scanner tasarimi ve test fixture'lariyla ele alinmali.
- Recruiter quota atomicity: DB transaction/lock stratejisiyle ayrica yapilmali.
- Privacy export/delete tam kapsami: mevcut raw store'larin migration/purge araci ile birlikte yapilmali.
- Client-side admin email exposure: backend role claim ve UI route modelinin yeniden duzenlenmesi gerekiyor.
- Mobile CI/dependency audit ve prod/dev requirements ayrimi: CI/release pipeline isi.

Ek dogrulama:

- `python -m py_compile` hedeflenen Python dosyalarinda basarili.
- `frontend`: `npm run typecheck` basarili.
- `frontend`: `npm run build` basarili.
- `.venv`: `pytest tests/test_model_worker.py -q` basarili, 2 test.
- `.venv`: `pytest tests/test_local_worker_cli.py -q` basarili, 6 test.
