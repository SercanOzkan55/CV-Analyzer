// Contact details shown on /iletisim/ and /en/contact/ and reused by the
// prerenderer so the page has real text before React hydrates. AdSense reviews
// look for reachable, specific contact information — keep every value here
// accurate and do not add channels that are not actually monitored.

export const CONTACT_EMAIL = 'support@cvanalyzer.dev'
export const CONTACT_OPERATOR = 'Sercan Özkan'
export const CONTACT_UPDATED_AT = '2026-08-22'

export const CONTACT_TR = {
  path: '/iletisim/',
  seoTitle: 'İletişim | CV Analyzer',
  title: 'İletişim',
  description:
    'CV Analyzer ekibine ürün, gizlilik, içerik veya iş birliği konularında nasıl ulaşabileceğinizi ve yanıt sürelerimizi öğrenin.',
  intro:
    'CV Analyzer ile ilgili her konuda bize doğrudan yazabilirsiniz. Aşağıda hangi konuyu kime ve nasıl ileteceğinizi, yanıt sürelerimizi ve talebinizi hızlandırmak için paylaşmanız gereken bilgileri bulabilirsiniz.',
  sections: [
    {
      heading: 'E-posta ile ulaşın',
      paragraphs: [
        `Tüm talepleriniz için tek adres: ${CONTACT_EMAIL}. Bu kutuyu ürünü geliştiren ekip doğrudan takip eder; aracı bir çağrı merkezi bulunmaz.`,
        'Mesajlarınızı Türkçe veya İngilizce gönderebilirsiniz.',
      ],
    },
    {
      heading: 'Yanıt sürelerimiz',
      paragraphs: [
        'Genel ürün ve kullanım sorularını hafta içi 1-2 iş günü içinde yanıtlıyoruz. Gizlilik ve veri silme talepleri yasal süreler içinde, en geç 30 gün içinde sonuçlandırılır.',
        'Ödeme veya hesap erişimiyle ilgili acil durumlarda konu satırına “Acil” yazmanız talebinizi öne almamıza yardımcı olur.',
      ],
    },
    {
      heading: 'Hangi konuda yazabilirsiniz?',
      paragraphs: [
        'Aşağıdaki başlıkların tamamı aynı e-posta adresine iletilir; konu satırında başlığı belirtmeniz yeterlidir.',
      ],
      bullets: [
        'Ürün desteği: analiz sonuçları, dosya yükleme sorunları, hesap erişimi.',
        'Gizlilik ve veri talepleri: verilerinize erişme, düzeltme, silme veya dışa aktarma.',
        'İçerik geri bildirimi: rehberlerdeki hatalı, eksik veya güncelliğini yitirmiş bilgiler.',
        'Reklam ve iş birliği: sponsorluk, içerik ortaklığı ve kurumsal kullanım talepleri.',
        'Hukuki bildirimler: telif, marka ve diğer hak sahipliği başvuruları.',
      ],
    },
    {
      heading: 'Talebinizi hızlandırmak için',
      paragraphs: [
        'Bir sorunu bildiriyorsanız hesabınızda kayıtlı e-posta adresini, sorunun yaşandığı tarihi ve mümkünse ekran görüntüsünü paylaşın. CV dosyanızın kendisini göndermeniz gerekmez; analiz kimliğini iletmeniz yeterlidir.',
        'Güvenliğiniz için hiçbir koşulda parolanızı, ödeme kartı bilgilerinizi veya doğrulama kodlarınızı e-posta ile paylaşmayın. Ekibimiz bu bilgileri sizden asla istemez.',
      ],
    },
    {
      heading: 'Hizmeti işleten',
      paragraphs: [
        `CV Analyzer, kurucu geliştirici ${CONTACT_OPERATOR} tarafından bağımsız bir ürün olarak işletilmektedir. Yazışma adresi talep üzerine, ilgili yasal başvurularda paylaşılır.`,
        'Hizmetin nasıl çalıştığını ve içerik ilkelerimizi editoryal politika sayfamızda ayrıntılı olarak açıklıyoruz.',
      ],
    },
  ],
}

export const CONTACT_EN = {
  path: '/en/contact/',
  seoTitle: 'Contact | CV Analyzer',
  title: 'Contact',
  description:
    'Reach the CV Analyzer team about product support, privacy requests, editorial corrections or partnership enquiries, and see our response times.',
  intro:
    'You can write to the CV Analyzer team directly about any topic. Below you will find where to send each type of request, how quickly we reply, and what to include so we can help on the first response.',
  sections: [
    {
      heading: 'Email us',
      paragraphs: [
        `Every request goes to a single address: ${CONTACT_EMAIL}. The team that builds the product reads this inbox directly — there is no outsourced call centre in between.`,
        'You are welcome to write in English or Turkish.',
      ],
    },
    {
      heading: 'Response times',
      paragraphs: [
        'General product and usage questions are answered within 1-2 working days. Privacy and deletion requests are completed within the applicable statutory period and no later than 30 days.',
        'For urgent billing or account-access problems, adding “Urgent” to the subject line helps us prioritise your message.',
      ],
    },
    {
      heading: 'What you can write about',
      paragraphs: [
        'All of the topics below reach the same address; naming the topic in the subject line is enough.',
      ],
      bullets: [
        'Product support: analysis results, upload failures, account access.',
        'Privacy and data requests: access, correction, deletion or export of your data.',
        'Editorial feedback: incorrect, incomplete or outdated information in a guide.',
        'Advertising and partnerships: sponsorship, content partnerships and business use.',
        'Legal notices: copyright, trademark and other rights-holder claims.',
      ],
    },
    {
      heading: 'Helping us resolve it faster',
      paragraphs: [
        'When reporting a problem, include the email address registered to your account, the date it happened and a screenshot if you have one. You do not need to send the CV file itself — the analysis id is enough.',
        'For your own safety, never send passwords, payment card details or verification codes by email. Our team will never ask you for them.',
      ],
    },
    {
      heading: 'Who operates the service',
      paragraphs: [
        `CV Analyzer is operated as an independent product by founder-developer ${CONTACT_OPERATOR}. A postal address is provided on request for formal legal correspondence.`,
        'Our editorial policy page explains in detail how the guidance is produced and reviewed.',
      ],
    },
  ],
}
