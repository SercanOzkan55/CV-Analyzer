// Privacy and terms content. Shared by the React pages and the prerenderer so
// the published HTML carries the full text before hydration.
//
// The advertising sections exist to satisfy Google's publisher requirements:
// third-party vendor cookie disclosure, the Google Ads Settings and
// aboutads.info opt-out routes, and the EU consent position. Do not trim them
// without checking the AdSense programme policies first.

// Explicit .js extension: the prerender script imports this module in plain
// Node ESM, which does not resolve extensionless paths the way Vite does.
import { CONTACT_EMAIL, CONTACT_OPERATOR } from './contactInfo.js'

export const POLICY_UPDATED_AT = '2026-08-22'

export const PRIVACY_TR = {
  path: '/privacy/',
  seoTitle: 'Gizlilik Politikası | CV Analyzer',
  title: 'Gizlilik Politikası',
  description:
    'CV Analyzer’ın hesap verilerini, CV dosyalarını, analiz sonuçlarını, çerezleri ve reklam teknolojilerini nasıl işlediğini, haklarınızı ve tercih yönetimini ayrıntılı olarak inceleyin.',
  intro:
    'Bu politika; CV Analyzer’ı kullandığınızda hangi verilerin toplandığını, bu verilerin hangi amaçlarla ve hangi hukuki dayanaklarla işlendiğini, ne kadar süreyle saklandığını, kimlerle paylaşıldığını ve sahip olduğunuz hakları açıklar. Reklam ve çerez teknolojilerine ilişkin tercihlerinizi nasıl yöneteceğinizi de burada bulabilirsiniz.',
  sections: [
    {
      heading: 'Veri sorumlusu ve kapsam',
      paragraphs: [
        `CV Analyzer, kurucu geliştirici ${CONTACT_OPERATOR} tarafından işletilen bağımsız bir üründür ve bu politika kapsamında veri sorumlusu sıfatını taşır. Politika, cvanalyzer.dev alan adı üzerinden sunulan web sitesi ve uygulama için geçerlidir.`,
        `Politikaya ilişkin her türlü soru ve talebinizi ${CONTACT_EMAIL} adresine iletebilirsiniz.`,
      ],
    },
    {
      heading: 'Topladığımız veriler',
      paragraphs: [
        'Hizmeti sunabilmek için yalnızca gerekli olan verileri topluyoruz. Toplanan veriler kaynaklarına göre şu başlıklarda toplanır:',
      ],
      bullets: [
        'Hesap verileri: e-posta adresiniz, şifrelenmiş kimlik doğrulama bilgileriniz ve hesap tercihleriniz.',
        'İçerik verileri: analiz için yüklediğiniz CV dosyaları, girdiğiniz iş ilanı metinleri ve oluşturulan analiz sonuçları.',
        'Kullanım verileri: analiz sayısı, özellik kullanımı ve hata kayıtları gibi hizmetin çalışmasını izlemeye yarayan teknik kayıtlar.',
        'Teknik veriler: IP adresi, tarayıcı ve cihaz bilgisi, dil tercihi ve güvenlik amaçlı erişim kayıtları.',
        'Çerez ve reklam verileri: aşağıda ayrıntılı açıklanan zorunlu ve isteğe bağlı tanımlayıcılar.',
      ],
    },
    {
      heading: 'İşleme amaçları ve hukuki dayanak',
      paragraphs: [
        'Verilerinizi yalnızca aşağıdaki amaçlarla ve belirtilen hukuki dayanaklara göre işleriz:',
      ],
      bullets: [
        'Sözleşmenin ifası: hesabınızı oluşturmak, CV analizini üretmek ve sonuçları size sunmak.',
        'Meşru menfaat: hizmet güvenliğini sağlamak, kötüye kullanımı önlemek, hataları gidermek ve ürünü iyileştirmek.',
        'Açık rıza: isteğe bağlı çerezler, kişiselleştirilmiş reklamlar ve pazarlama iletişimi.',
        'Hukuki yükümlülük: mevzuatın gerektirdiği saklama, raporlama ve resmi taleplere yanıt verme.',
      ],
    },
    {
      heading: 'CV dosyalarınız ve analiz sonuçları',
      paragraphs: [
        'Yüklediğiniz CV dosyaları analiz üretmek için işlenir ve hesabınızla ilişkilendirilerek saklanır; böylece geçmiş analizlerinize dönebilirsiniz. Dosyalarınızı ve analiz kayıtlarınızı uygulamadaki Veri Merkezi ekranından tek tek silebilir veya hesabınızı tamamen kapatabilirsiniz.',
        'CV içeriğinizi reklam hedeflemesi için kullanmayız, üçüncü taraf reklam ağlarına aktarmayız ve reklam profili oluşturmak amacıyla işlemeyiz.',
        'CV’nizde işe başvuru için gerekli olmayan hassas bilgileri (kimlik numarası, sağlık bilgisi, inanç veya siyasi görüş gibi) paylaşmamanızı öneririz.',
      ],
    },
    {
      heading: 'Çerezler ve benzer teknolojiler',
      paragraphs: [
        'Çerezler, tarayıcınıza yerleştirilen küçük metin dosyalarıdır. Sitede iki tür kullanım söz konusudur:',
      ],
      bullets: [
        'Zorunlu çerezler: oturum açma, güvenlik ve dil tercihi gibi hizmetin çalışması için gereken tanımlayıcılar. Bunlar rıza gerektirmez, çünkü onlarsız hizmet sunulamaz.',
        'İsteğe bağlı çerezler: ölçümleme ve reklam amaçlı tanımlayıcılar. Bunlar yalnızca onay verdiğinizde çalışır ve onayınızı istediğiniz zaman geri alabilirsiniz.',
      ],
    },
    {
      heading: 'Reklamlar ve üçüncü taraf sağlayıcılar',
      paragraphs: [
        'Bu sitede Google AdSense aracılığıyla reklam gösterilebilir. Google dahil üçüncü taraf sağlayıcılar, sizin bu siteye veya internetteki diğer sitelere yaptığınız önceki ziyaretlere dayanarak reklam sunmak amacıyla çerezleri kullanır.',
        'Google’ın reklam çerezlerini (DoubleClick DART çerezi dahil) kullanması, Google ve iş ortaklarının bu siteye ve internetteki diğer sitelere yaptığınız ziyaretlere göre size reklam sunmasına olanak tanır.',
        'Reklam sağlayıcıları bu kapsamda IP adresinizi, cihaz ve tarayıcı bilgilerinizi ve reklam etkileşimlerinizi işleyebilir. Bu işleme Google’ın kendi gizlilik politikası kapsamında gerçekleşir.',
      ],
    },
    {
      heading: 'Reklam tercihlerinizi yönetme',
      paragraphs: [
        'Kişiselleştirilmiş reklamları dilediğiniz zaman kapatabilirsiniz. Aşağıdaki bağlantılar tercihlerinizi doğrudan yönetmenizi sağlar:',
      ],
      bullets: [
        'Google reklam ayarlarından kişiselleştirilmiş reklamları kapatabilirsiniz: https://www.google.com/settings/ads',
        'Üçüncü taraf sağlayıcıların çerezlerini toplu olarak devre dışı bırakabilirsiniz: https://www.aboutads.info/choices',
        'Avrupa Birliği kullanıcıları için ek seçenekler: https://www.youronlinechoices.com',
        'Google’ın reklamlarda veri kullanımına ilişkin açıklaması: https://policies.google.com/technologies/ads',
        'Site üzerindeki çerez tercih panelinden onayınızı istediğiniz zaman güncelleyebilir veya geri çekebilirsiniz.',
      ],
    },
    {
      heading: 'Avrupa Birliği ve Birleşik Krallık kullanıcıları',
      paragraphs: [
        'Avrupa Ekonomik Alanı, Birleşik Krallık ve İsviçre’deki kullanıcılar için, zorunlu olmayan çerezler ve kişiselleştirilmiş reklamlar yalnızca geçerli bir onay alındıktan sonra çalıştırılır. Onay yönetimi, Google’ın AB kullanıcı onayı politikasına uygun bir onay yönetim platformu üzerinden yürütülür.',
        'Onayınızı vermediğiniz durumda kişiselleştirilmemiş reklamlar gösterilebilir; bu reklamlar ilgi alanı profiline değil, yalnızca sayfanın içeriğine ve genel bağlama dayanır.',
      ],
    },
    {
      heading: 'Veri paylaşımı ve hizmet sağlayıcılar',
      paragraphs: [
        'Verilerinizi satmayız. Hizmeti sunabilmek için yalnızca aşağıdaki kategorilerdeki sağlayıcılarla, sözleşmesel gizlilik yükümlülükleri altında ve gerekli olduğu ölçüde paylaşırız:',
      ],
      bullets: [
        'Kimlik doğrulama ve veritabanı altyapısı sağlayıcısı (Supabase).',
        'Sunucu, depolama ve içerik dağıtım sağlayıcıları (Google Cloud, Cloudflare).',
        'Reklam sağlayıcısı (Google AdSense) — yalnızca çerez ve reklam verileri; CV içeriğiniz paylaşılmaz.',
        'Ödeme altyapısı sağlayıcısı — yalnızca ücretli plan kullanıyorsanız ve yalnızca ödeme için gerekli veriler.',
        'Yetkili makamlar — yalnızca hukuken zorunlu olduğu durumlarda.',
      ],
    },
    {
      heading: 'Yurt dışına aktarım',
      paragraphs: [
        'Kullandığımız altyapı sağlayıcılarının sunucuları Avrupa Birliği ve Amerika Birleşik Devletleri’nde bulunabilir. Bu aktarımlar, standart sözleşme hükümleri gibi mevzuatın öngördüğü uygun güvenceler kapsamında gerçekleştirilir.',
      ],
    },
    {
      heading: 'Saklama süreleri',
      paragraphs: [
        'Hesap verileriniz ve kaydedilmiş analizleriniz, siz silene veya hesabınızı kapatana kadar saklanır. Hesap kapatıldığında içerik verileri en geç 30 gün içinde kalıcı olarak silinir.',
        'Güvenlik ve hata kayıtları en fazla 12 ay, mevzuat gereği tutulması zorunlu kayıtlar ise ilgili yasal süre boyunca saklanır.',
      ],
    },
    {
      heading: 'Veri güvenliği',
      paragraphs: [
        'Verileriniz aktarım sırasında TLS ile şifrelenir, parolalar geri döndürülemez biçimde saklanır ve yönetimsel erişim yetkilendirme ile sınırlandırılır. Buna rağmen internet üzerinden yapılan hiçbir aktarımın mutlak güvenlik garantisi veremeyeceğini belirtmek isteriz.',
      ],
    },
    {
      heading: 'Haklarınız',
      paragraphs: [
        'KVKK ve GDPR kapsamında; verilerinize erişme, düzeltilmesini isteme, silinmesini talep etme, işlemenin kısıtlanmasını isteme, verilerinizi taşınabilir biçimde alma ve işlemeye itiraz etme haklarına sahipsiniz. Rızaya dayalı işlemelerde rızanızı dilediğiniz zaman geri çekebilirsiniz.',
        `Taleplerinizi ${CONTACT_EMAIL} adresine iletebilirsiniz; başvurunuz en geç 30 gün içinde sonuçlandırılır. Sonuçtan memnun kalmazsanız Türkiye’de Kişisel Verileri Koruma Kurumu’na, Avrupa Birliği’nde ise bulunduğunuz ülkenin veri koruma otoritesine şikâyette bulunma hakkınız saklıdır.`,
      ],
    },
    {
      heading: 'Çocukların gizliliği',
      paragraphs: [
        'Hizmet 16 yaşın altındaki kişilere yönelik değildir ve bu yaş grubundan bilerek veri toplamayız. Böyle bir verinin işlendiğini fark edersek gecikmeksizin sileriz.',
      ],
    },
    {
      heading: 'Politikadaki değişiklikler',
      paragraphs: [
        'Bu politikayı hizmetteki veya mevzuattaki değişikliklere göre güncelleyebiliriz. Güncel sürüm her zaman bu sayfada yayımlanır ve sayfanın başındaki tarih son güncelleme tarihini gösterir. Önemli değişikliklerde hesabınızda kayıtlı e-posta adresi üzerinden bilgilendirme yaparız.',
      ],
    },
  ],
}

export const PRIVACY_EN = {
  path: '/en/privacy/',
  seoTitle: 'Privacy Policy | CV Analyzer',
  title: 'Privacy Policy',
  description:
    'Read how CV Analyzer handles account data, CV files, analysis results, cookies and advertising technologies, and how to exercise your data rights.',
  intro:
    'This policy explains what data CV Analyzer collects, why and on what legal basis it is processed, how long it is kept, who it is shared with, and the rights available to you. It also sets out how to manage your cookie and advertising preferences.',
  sections: [
    {
      heading: 'Controller and scope',
      paragraphs: [
        `CV Analyzer is an independent product operated by founder-developer ${CONTACT_OPERATOR}, who acts as the data controller for the purposes of this policy. It applies to the website and application provided at cvanalyzer.dev.`,
        `Questions and requests about this policy can be sent to ${CONTACT_EMAIL}.`,
      ],
    },
    {
      heading: 'Data we collect',
      paragraphs: [
        'We collect only what is needed to provide the service. By source, that is:',
      ],
      bullets: [
        'Account data: your email address, hashed authentication credentials and account preferences.',
        'Content data: the CV files you upload, the vacancy text you paste and the analysis results produced from them.',
        'Usage data: technical records such as analysis counts, feature usage and error logs.',
        'Technical data: IP address, browser and device information, language preference and security access logs.',
        'Cookie and advertising data: the essential and optional identifiers described below.',
      ],
    },
    {
      heading: 'Purposes and legal bases',
      paragraphs: [
        'We process your data only for the purposes below, on the legal bases stated:',
      ],
      bullets: [
        'Performance of a contract: creating your account, producing the analysis and delivering results.',
        'Legitimate interests: keeping the service secure, preventing abuse, fixing faults and improving the product.',
        'Consent: optional cookies, personalised advertising and marketing communications.',
        'Legal obligation: retention, reporting and responding to lawful requests.',
      ],
    },
    {
      heading: 'Your CV files and analysis results',
      paragraphs: [
        'Uploaded CV files are processed to produce an analysis and stored against your account so you can return to earlier results. You can delete individual files and analysis records from the Data Centre screen in the application, or close your account entirely.',
        'We do not use your CV content for ad targeting, do not pass it to third-party advertising networks, and do not process it to build an advertising profile.',
        'We recommend not including sensitive details that are unnecessary for a job application, such as national identity numbers, health information, religious belief or political opinion.',
      ],
    },
    {
      heading: 'Cookies and similar technologies',
      paragraphs: [
        'Cookies are small text files placed on your browser. This site uses two categories:',
      ],
      bullets: [
        'Essential cookies: identifiers needed for sign-in, security and language preference. These do not require consent because the service cannot function without them.',
        'Optional cookies: measurement and advertising identifiers. These run only if you consent, and you can withdraw that consent at any time.',
      ],
    },
    {
      heading: 'Advertising and third-party vendors',
      paragraphs: [
        'This site may display advertising through Google AdSense. Third-party vendors, including Google, use cookies to serve ads based on your prior visits to this website or other websites.',
        'Google’s use of advertising cookies, including the DoubleClick DART cookie, enables Google and its partners to serve ads to you based on your visit to this site and other sites on the internet.',
        'In that context advertising vendors may process your IP address, device and browser information and your interactions with ads. That processing takes place under Google’s own privacy policy.',
      ],
    },
    {
      heading: 'Managing your advertising choices',
      paragraphs: [
        'You can turn off personalised advertising at any time. The following links let you manage your preferences directly:',
      ],
      bullets: [
        'Opt out of personalised advertising in Google Ads Settings: https://www.google.com/settings/ads',
        'Opt out of third-party vendor cookies in bulk: https://www.aboutads.info/choices',
        'Additional options for users in Europe: https://www.youronlinechoices.com',
        'How Google uses data in advertising: https://policies.google.com/technologies/ads',
        'You can update or withdraw your consent at any time from the cookie preferences panel on this site.',
      ],
    },
    {
      heading: 'Users in the EEA and the United Kingdom',
      paragraphs: [
        'For users in the European Economic Area, the United Kingdom and Switzerland, non-essential cookies and personalised advertising run only after valid consent has been obtained. Consent is handled through a consent management platform that complies with Google’s EU user consent policy.',
        'If you do not consent, non-personalised advertising may still be shown. Such ads are based on the content of the page and general context rather than an interest profile.',
      ],
    },
    {
      heading: 'Sharing and service providers',
      paragraphs: [
        'We do not sell your data. To operate the service we share it only with the categories of provider below, under contractual confidentiality obligations and only to the extent necessary:',
      ],
      bullets: [
        'Authentication and database infrastructure (Supabase).',
        'Server, storage and content delivery providers (Google Cloud, Cloudflare).',
        'Advertising provider (Google AdSense) — cookie and advertising data only; your CV content is never shared.',
        'Payment infrastructure — only if you use a paid plan, and only the data required for payment.',
        'Competent authorities — only where legally required.',
      ],
    },
    {
      heading: 'International transfers',
      paragraphs: [
        'Our infrastructure providers may host servers in the European Union and the United States. Such transfers are carried out under appropriate safeguards required by law, such as standard contractual clauses.',
      ],
    },
    {
      heading: 'Retention periods',
      paragraphs: [
        'Account data and saved analyses are retained until you delete them or close your account. When an account is closed, content data is permanently deleted within 30 days at the latest.',
        'Security and error logs are kept for up to 12 months. Records that must be retained by law are kept for the applicable statutory period.',
      ],
    },
    {
      heading: 'Security',
      paragraphs: [
        'Data is encrypted with TLS in transit, passwords are stored in a non-reversible form, and administrative access is restricted by authorisation. Even so, no transmission over the internet can be guaranteed to be absolutely secure.',
      ],
    },
    {
      heading: 'Your rights',
      paragraphs: [
        'Under the GDPR and applicable local law you have the right to access your data, request correction or erasure, request restriction of processing, receive your data in a portable format and object to processing. Where processing is based on consent, you may withdraw it at any time.',
        `Send requests to ${CONTACT_EMAIL}; we respond within 30 days at the latest. If you are not satisfied with the outcome, you have the right to complain to the data protection authority in your country of residence.`,
      ],
    },
    {
      heading: 'Children’s privacy',
      paragraphs: [
        'The service is not directed at people under 16 and we do not knowingly collect data from that age group. If we become aware of such data, we delete it without delay.',
      ],
    },
    {
      heading: 'Changes to this policy',
      paragraphs: [
        'We may update this policy to reflect changes in the service or in applicable law. The current version is always published on this page, and the date at the top shows when it was last updated. We notify you by email about significant changes.',
      ],
    },
  ],
}

export const TERMS_TR = {
  path: '/terms/',
  seoTitle: 'Kullanım Koşulları | CV Analyzer',
  title: 'Kullanım Koşulları',
  description:
    'CV Analyzer’ı kullanırken geçerli olan koşulları, kullanıcı sorumluluklarını, hizmet sınırlarını, ücretlendirmeyi ve hesap kapatma kurallarını inceleyin.',
  intro:
    'Bu koşullar, CV Analyzer web sitesini ve uygulamasını kullanımınızı düzenler. Hizmeti kullanarak aşağıdaki koşulları kabul etmiş sayılırsınız. Koşulları kabul etmiyorsanız hizmeti kullanmamanızı rica ederiz.',
  sections: [
    {
      heading: 'Hizmetin tanımı',
      paragraphs: [
        'CV Analyzer; yüklediğiniz özgeçmişin okunabilirliğini, bölüm yapısını, deneyim ve beceri anlatımını ve hedef iş ilanıyla ilişkisini otomatik olarak değerlendiren ve geliştirme önerileri üreten bir yazılım hizmetidir.',
        'Hizmet bilgilendirme ve karar destek amaçlıdır; kariyer danışmanlığı, hukuki görüş veya istihdam garantisi niteliği taşımaz.',
      ],
    },
    {
      heading: 'Hesap ve uygunluk',
      paragraphs: [
        'Hesap oluşturmak için 16 yaşını doldurmuş olmanız gerekir. Hesap bilgilerinizin gizliliğinden ve hesabınız üzerinden gerçekleştirilen işlemlerden siz sorumlusunuz.',
        'Yetkisiz bir erişim fark ederseniz gecikmeksizin bizimle iletişime geçmelisiniz.',
      ],
    },
    {
      heading: 'Kullanıcı sorumluluğu',
      paragraphs: [
        'Yüklediğiniz içeriğin doğruluğundan ve bu içeriği paylaşmaya yetkili olduğunuzdan siz sorumlusunuz. Başkasına ait bir CV’yi yüklüyorsanız, ilgili kişinin bilgisi ve uygun hukuki dayanak bulunmalıdır.',
        'Üretilen önerileri kullanmadan önce gözden geçirmeniz beklenir. CV’nizde gerçekte bulunmayan deneyim, sonuç veya nitelikleri beyan etmek yalnızca sizin sorumluluğunuzdadır.',
      ],
    },
    {
      heading: 'Yasak kullanımlar',
      paragraphs: [
        'Hizmeti aşağıdaki amaçlarla kullanamazsınız:',
      ],
      bullets: [
        'Hukuka aykırı, yanıltıcı veya başkalarının haklarını ihlal eden içerik yüklemek.',
        'Sistemi otomatik araçlarla aşırı yüklemek, tersine mühendislik yapmak veya güvenlik önlemlerini aşmaya çalışmak.',
        'Hizmeti izinsiz olarak yeniden satmak, çoğaltmak veya türev bir hizmet olarak sunmak.',
        'Kötü amaçlı yazılım içeren dosyalar yüklemek veya başka kullanıcıların erişimini engellemek.',
      ],
    },
    {
      heading: 'Hizmet sınırları ve sorumluluk reddi',
      paragraphs: [
        'Analiz sonuçları otomatik değerlendirmelerdir ve piyasadaki her ATS ürününün, işverenin veya yerel işe alım uygulamasının davranışını birebir yansıtmaz. Puanlar ve öneriler mutlak doğruluk iddiası taşımaz.',
        'Hizmet “olduğu gibi” sunulur. Uygulanabilir mevzuatın izin verdiği azami ölçüde, hizmetin kullanımından doğan dolaylı zararlardan, kâr kaybından veya iş fırsatı kaybından sorumlu değiliz.',
      ],
    },
    {
      heading: 'Ücretler ve planlar',
      paragraphs: [
        'Ücretsiz plan belirli kullanım sınırlarıyla sunulur. Ücretli planların kapsamı, fiyatı ve limitleri fiyatlandırma sayfasında ve satın alma ekranında gösterilir; satın almadan önce bunları doğrulamanız beklenir.',
        'Fiyatlar ve limitler değişebilir. Yürürlükteki bir abonelik döneminde yapılan değişiklikler, o dönem sona erene kadar aleyhinize uygulanmaz.',
      ],
    },
    {
      heading: 'Reklamlar',
      paragraphs: [
        'Herkese açık içerik sayfalarında üçüncü taraf reklamlar gösterilebilir. Reklam içerikleri reklam verenlere aittir; bunların doğruluğundan veya reklamı yapılan ürün ve hizmetlerden sorumlu değiliz.',
        'Reklam ve çerez tercihlerinizi nasıl yöneteceğiniz Gizlilik Politikası sayfasında açıklanmıştır.',
      ],
    },
    {
      heading: 'Fikri mülkiyet',
      paragraphs: [
        'Yüklediğiniz içeriğin hakları size aittir. Hizmeti sunabilmemiz için, içeriğinizi yalnızca analiz üretmek ve sonucu size göstermek amacıyla işleme yetkisi vermiş olursunuz.',
        'Hizmetin yazılımı, arayüz tasarımı, rehber içerikleri ve marka unsurları CV Analyzer’a aittir ve izinsiz kullanılamaz.',
      ],
    },
    {
      heading: 'Askıya alma ve fesih',
      paragraphs: [
        'Bu koşulların ihlali hâlinde hesabınızı askıya alabilir veya kapatabiliriz. Hesabınızı dilediğiniz zaman uygulama üzerinden kapatabilirsiniz.',
        'Hesap kapatıldığında verilerinizin silinmesi Gizlilik Politikası’ndaki saklama sürelerine göre yürütülür.',
      ],
    },
    {
      heading: 'Değişiklikler ve uygulanacak hukuk',
      paragraphs: [
        'Bu koşulları güncelleyebiliriz; güncel sürüm bu sayfada yayımlanır ve önemli değişiklikler kayıtlı e-posta adresinize bildirilir.',
        'Bu koşullara Türkiye Cumhuriyeti hukuku uygulanır. Tüketici mevzuatından doğan haklarınız saklıdır.',
      ],
    },
  ],
}

export const TERMS_EN = {
  path: '/en/terms/',
  seoTitle: 'Terms of Use | CV Analyzer',
  title: 'Terms of Use',
  description:
    'Review the terms that apply when using CV Analyzer, including user responsibilities, service limitations, fees, advertising and account closure.',
  intro:
    'These terms govern your use of the CV Analyzer website and application. By using the service you accept them. If you do not accept them, please do not use the service.',
  sections: [
    {
      heading: 'What the service does',
      paragraphs: [
        'CV Analyzer is a software service that automatically reviews an uploaded CV for readability, section structure, how experience and skills are described, and its relevance to a target vacancy, and produces suggestions for improvement.',
        'The service is informational and supports your own decision-making. It is not career advice, legal advice, or a guarantee of employment.',
      ],
    },
    {
      heading: 'Accounts and eligibility',
      paragraphs: [
        'You must be at least 16 years old to create an account. You are responsible for keeping your credentials confidential and for activity carried out through your account.',
        'If you notice unauthorised access, you must contact us without delay.',
      ],
    },
    {
      heading: 'Your responsibilities',
      paragraphs: [
        'You are responsible for the accuracy of the content you upload and for having the authority to share it. If you upload someone else’s CV, that person must be aware of it and an appropriate legal basis must exist.',
        'You are expected to review generated suggestions before using them. Stating experience, results or qualifications you do not actually hold is solely your responsibility.',
      ],
    },
    {
      heading: 'Prohibited use',
      paragraphs: [
        'You may not use the service to:',
      ],
      bullets: [
        'Upload unlawful or misleading content, or content that infringes the rights of others.',
        'Overload the system with automated tools, reverse-engineer it, or attempt to bypass security controls.',
        'Resell, reproduce or repackage the service without permission.',
        'Upload files containing malware or otherwise interfere with other users’ access.',
      ],
    },
    {
      heading: 'Limitations and disclaimer',
      paragraphs: [
        'Analysis results are automated assessments and do not reproduce the exact behaviour of every ATS product, employer or local hiring practice. Scores and suggestions make no claim to absolute accuracy.',
        'The service is provided "as is". To the maximum extent permitted by applicable law, we are not liable for indirect damages, lost profits or lost business opportunities arising from use of the service.',
      ],
    },
    {
      heading: 'Fees and plans',
      paragraphs: [
        'A free plan is offered with defined usage limits. The scope, price and limits of paid plans are shown on the pricing page and at checkout; you are expected to confirm them before purchasing.',
        'Prices and limits may change. Changes made during an active subscription period do not take effect to your disadvantage until that period ends.',
      ],
    },
    {
      heading: 'Advertising',
      paragraphs: [
        'Third-party advertising may be displayed on public content pages. Advertising content belongs to the advertisers; we are not responsible for its accuracy or for the products and services advertised.',
        'How to manage your advertising and cookie preferences is explained in the Privacy Policy.',
      ],
    },
    {
      heading: 'Intellectual property',
      paragraphs: [
        'You retain the rights to the content you upload. To let us provide the service, you grant permission to process that content solely to produce an analysis and show the result to you.',
        'The software, interface design, guide content and brand elements of the service belong to CV Analyzer and may not be used without permission.',
      ],
    },
    {
      heading: 'Suspension and termination',
      paragraphs: [
        'We may suspend or close your account if these terms are breached. You may close your account at any time from within the application.',
        'When an account is closed, deletion of your data follows the retention periods set out in the Privacy Policy.',
      ],
    },
    {
      heading: 'Changes and governing law',
      paragraphs: [
        'We may update these terms; the current version is published on this page and significant changes are notified to your registered email address.',
        'These terms are governed by the laws of the Republic of Türkiye. Your rights under applicable consumer legislation are unaffected.',
      ],
    },
  ],
}
