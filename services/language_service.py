"""
CV language detection and localized string maps for analysis results.
Uses langdetect for automatic language identification from CV text.
"""

try:
    from langdetect import LangDetectException
    from langdetect import detect as _detect_lang

    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False

# Supported languages for result localization
SUPPORTED_LANGS = {
    "en",
    "tr",
    "fr",
    "de",
    "es",
    "ar",
    "pt",
    "it",
    "nl",
    "ru",
    "ja",
    "ko",
    "zh",
}
DEFAULT_LANG = "en"


def detect_language(text: str) -> str:
    """Detect the language of the given text. Returns ISO 639-1 code."""
    if not text or len(text.strip()) < 20:
        return DEFAULT_LANG

    if not HAS_LANGDETECT:
        return DEFAULT_LANG

    try:
        # Use first ~3000 chars for detection (enough for accuracy, fast)
        sample = text[:3000]
        lang = _detect_lang(sample)
        return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG
    except Exception:
        return DEFAULT_LANG


# ── Interpretation labels ────────────────────────────────────────────

INTERPRETATION = {
    "high": {
        "en": "Strong Match",
        "tr": "Güçlü Eşleşme",
        "fr": "Correspondance Forte",
        "de": "Starke Übereinstimmung",
        "es": "Alta Compatibilidad",
        "ar": "توافق قوي",
        "pt": "Correspondência Forte",
        "it": "Corrispondenza Forte",
        "nl": "Sterke Match",
        "ru": "Высокое соответствие",
        "ja": "高い一致",
        "ko": "높은 일치",
        "zh": "高度匹配",
    },
    "moderate": {
        "en": "Moderate Match",
        "tr": "Orta Eşleşme",
        "fr": "Correspondance Modérée",
        "de": "Mäßige Übereinstimmung",
        "es": "Compatibilidad Moderada",
        "ar": "توافق متوسط",
        "pt": "Correspondência Moderada",
        "it": "Corrispondenza Moderata",
        "nl": "Gemiddelde Match",
        "ru": "Среднее соответствие",
        "ja": "中程度の一致",
        "ko": "보통 일치",
        "zh": "中度匹配",
    },
    "low": {
        "en": "Weak Match",
        "tr": "Zayıf Eşleşme",
        "fr": "Faible Correspondance",
        "de": "Schwache Übereinstimmung",
        "es": "Baja Compatibilidad",
        "ar": "توافق ضعيف",
        "pt": "Correspondência Fraca",
        "it": "Corrispondenza Debole",
        "nl": "Zwakke Match",
        "ru": "Низкое соответствие",
        "ja": "低い一致",
        "ko": "낮은 일치",
        "zh": "低度匹配",
    },
}


def interpret_score_localized(score: float, lang: str = "en") -> str:
    if score > 75:
        key = "high"
    elif score > 50:
        key = "moderate"
    else:
        key = "low"
    return INTERPRETATION[key].get(lang, INTERPRETATION[key]["en"])


# ── Risk level labels ────────────────────────────────────────────────

RISK_LEVELS = {
    "Low Risk": {
        "en": "Low Risk",
        "tr": "Düşük Risk",
        "fr": "Risque Faible",
        "de": "Geringes Risiko",
        "es": "Riesgo Bajo",
        "ar": "مخاطر منخفضة",
        "pt": "Risco Baixo",
        "it": "Rischio Basso",
        "nl": "Laag Risico",
        "ru": "Низкий риск",
        "ja": "低リスク",
        "ko": "낮은 위험",
        "zh": "低风险",
    },
    "Medium Risk": {
        "en": "Medium Risk",
        "tr": "Orta Risk",
        "fr": "Risque Moyen",
        "de": "Mittleres Risiko",
        "es": "Riesgo Medio",
        "ar": "مخاطر متوسطة",
        "pt": "Risco Médio",
        "it": "Rischio Medio",
        "nl": "Gemiddeld Risico",
        "ru": "Средний риск",
        "ja": "中リスク",
        "ko": "중간 위험",
        "zh": "中风险",
    },
    "High Risk": {
        "en": "High Risk",
        "tr": "Yüksek Risk",
        "fr": "Risque Élevé",
        "de": "Hohes Risiko",
        "es": "Riesgo Alto",
        "ar": "مخاطر عالية",
        "pt": "Risco Alto",
        "it": "Rischio Alto",
        "nl": "Hoog Risico",
        "ru": "Высокий риск",
        "ja": "高リスク",
        "ko": "높은 위험",
        "zh": "高风险",
    },
}


def localize_risk_level(risk_level: str, lang: str = "en") -> str:
    mapping = RISK_LEVELS.get(risk_level, RISK_LEVELS["High Risk"])
    return mapping.get(lang, mapping["en"])


# ── Recommendation templates ─────────────────────────────────────────

RECOMMENDATIONS = {
    "semantic_low": {
        "en": "Your CV structure does not align well with this job description. Rewrite your experience section using similar terminology.",
        "tr": "CV yapınız bu iş tanımıyla iyi uyuşmuyor. Deneyim bölümünüzü benzer terimler kullanarak yeniden yazın.",
        "fr": "La structure de votre CV ne correspond pas bien à cette description de poste. Réécrivez votre section expérience en utilisant une terminologie similaire.",
        "de": "Ihre Lebenslaufstruktur passt nicht gut zur Stellenbeschreibung. Schreiben Sie Ihren Erfahrungsabschnitt mit ähnlicher Terminologie um.",
        "es": "La estructura de tu CV no se alinea bien con esta descripción del puesto. Reescribe tu sección de experiencia usando terminología similar.",
        "ar": "هيكل سيرتك الذاتية لا يتوافق جيداً مع هذا الوصف الوظيفي. أعد كتابة قسم الخبرات باستخدام مصطلحات مماثلة.",
        "pt": "A estrutura do seu currículo não está alinhada com esta descrição de vaga. Reescreva sua seção de experiência usando terminologia semelhante.",
        "it": "La struttura del tuo CV non è allineata con questa descrizione del lavoro. Riscrivi la sezione esperienza usando una terminologia simile.",
        "nl": "Uw CV-structuur komt niet goed overeen met deze functieomschrijving. Herschrijf uw ervaringssectie met vergelijkbare terminologie.",
        "ru": "Структура вашего резюме не соответствует данному описанию вакансии. Перепишите раздел опыта, используя аналогичную терминологию.",
        "ja": "CV の構造がこの求人説明とよく合っていません。類似の用語を使用して経験セクションを書き直してください。",
        "ko": "이력서 구조가 이 직무 설명과 잘 맞지 않습니다. 유사한 용어를 사용하여 경력 섹션을 다시 작성하세요.",
        "zh": "您的简历结构与此职位描述不太匹配。请使用类似的术语重写您的经验部分。",
    },
    "add_skill": {
        "en": "Add measurable project experience demonstrating {}.",
        "tr": "{} becerisini gösteren ölçülebilir proje deneyimi ekleyin.",
        "fr": "Ajoutez une expérience de projet mesurable démontrant {}.",
        "de": "Fügen Sie messbare Projekterfahrung hinzu, die {} demonstriert.",
        "es": "Agrega experiencia de proyecto medible que demuestre {}.",
        "ar": "أضف خبرة مشروع قابلة للقياس توضح {}.",
        "pt": "Adicione experiência de projeto mensurável demonstrando {}.",
        "it": "Aggiungi esperienza di progetto misurabile che dimostri {}.",
        "nl": "Voeg meetbare projectervaring toe die {} aantoont.",
        "ru": "Добавьте измеримый опыт проектов, демонстрирующий {}.",
        "ja": "{} を示す測定可能なプロジェクト経験を追加してください。",
        "ko": "{}를 보여주는 측정 가능한 프로젝트 경험을 추가하세요.",
        "zh": "添加展示 {} 的可量化项目经验。",
    },
    "keyword_low": {
        "en": "Improve keyword matching by explicitly mentioning required technologies.",
        "tr": "Gerekli teknolojileri açıkça belirterek anahtar kelime eşleşmesini iyileştirin.",
        "fr": "Améliorez la correspondance des mots-clés en mentionnant explicitement les technologies requises.",
        "de": "Verbessern Sie die Keyword-Übereinstimmung, indem Sie die erforderlichen Technologien explizit erwähnen.",
        "es": "Mejora la coincidencia de palabras clave mencionando explícitamente las tecnologías requeridas.",
        "ar": "حسّن مطابقة الكلمات المفتاحية بذكر التقنيات المطلوبة صراحة.",
        "pt": "Melhore a correspondência de palavras-chave mencionando explicitamente as tecnologias necessárias.",
        "it": "Migliora la corrispondenza delle parole chiave menzionando esplicitamente le tecnologie richieste.",
        "nl": "Verbeter de keyword-matching door vereiste technologieën expliciet te noemen.",
        "ru": "Улучшите соответствие ключевых слов, явно упоминая требуемые технологии.",
        "ja": "必要な技術を明示的に言及してキーワードマッチングを改善してください。",
        "ko": "필요한 기술을 명시적으로 언급하여 키워드 매칭을 개선하세요.",
        "zh": "通过明确提及所需技术来改善关键词匹配。",
    },
    "all_good": {
        "en": "Your CV is generally aligned. Focus on adding quantified achievements.",
        "tr": "CV'niz genel olarak uyumlu. Sayısal başarılar eklemeye odaklanın.",
        "fr": "Votre CV est généralement aligné. Concentrez-vous sur l'ajout de réalisations quantifiées.",
        "de": "Ihr Lebenslauf ist generell gut aufgestellt. Konzentrieren Sie sich auf quantifizierte Erfolge.",
        "es": "Tu CV está generalmente alineado. Concéntrate en agregar logros cuantificados.",
        "ar": "سيرتك الذاتية متوافقة بشكل عام. ركز على إضافة إنجازات قابلة للقياس.",
        "pt": "Seu currículo está geralmente alinhado. Concentre-se em adicionar conquistas quantificadas.",
        "it": "Il tuo CV è generalmente allineato. Concentrati sull'aggiunta di risultati quantificati.",
        "nl": "Uw CV is over het algemeen goed afgestemd. Focus op het toevoegen van gekwantificeerde prestaties.",
        "ru": "Ваше резюме в целом соответствует. Сосредоточьтесь на добавлении измеримых достижений.",
        "ja": "CVは概ね適合しています。定量的な実績の追加に注力してください。",
        "ko": "이력서가 전반적으로 잘 맞습니다. 수량화된 성과 추가에 집중하세요.",
        "zh": "您的简历总体上是匹配的。专注于添加量化的成就。",
    },
}


def get_recommendation(key: str, lang: str = "en", skill: str = "") -> str:
    template = RECOMMENDATIONS.get(key, {})
    text = template.get(lang, template.get("en", ""))
    if skill and "{}" in text:
        text = text.format(skill)
    return text


# ── ATS suggestion templates ─────────────────────────────────────────

ATS_SUGGESTIONS = {
    "keyword_low": {
        "en": "Incorporate keywords from the job posting naturally into your CV.",
        "tr": "İş ilanındaki anahtar kelimeleri CV'nize doğal biçimde ekleyin.",
        "fr": "Intégrez naturellement les mots-clés de l'offre d'emploi dans votre CV.",
        "de": "Integrieren Sie Schlüsselwörter aus der Stellenanzeige natürlich in Ihren Lebenslauf.",
        "es": "Incorpora naturalmente las palabras clave de la oferta de trabajo en tu CV.",
        "ar": "أدرج الكلمات المفتاحية من إعلان الوظيفة بشكل طبيعي في سيرتك الذاتية.",
        "pt": "Incorpore naturalmente as palavras-chave do anúncio de emprego no seu currículo.",
        "it": "Incorpora naturalmente le parole chiave dell'annuncio di lavoro nel tuo CV.",
        "nl": "Verwerk de trefwoorden uit de vacature op een natuurlijke manier in uw CV.",
        "ru": "Естественно включите ключевые слова из вакансии в свое резюме.",
        "ja": "求人情報のキーワードをCVに自然に取り入れてください。",
        "ko": "채용 공고의 키워드를 이력서에 자연스럽게 포함시키세요.",
        "zh": "将招聘信息中的关键词自然地融入您的简历中。",
    },
    "action_low": {
        "en": "Use strong action verbs and measurable achievements for each role.",
        "tr": "Her görev için ölçülebilir başarılara ve güçlü eylem fiillerine yer verin.",
        "fr": "Utilisez des verbes d'action forts et des réalisations mesurables pour chaque poste.",
        "de": "Verwenden Sie starke Aktionsverben und messbare Erfolge für jede Rolle.",
        "es": "Usa verbos de acción fuertes y logros medibles para cada rol.",
        "ar": "استخدم أفعال عمل قوية وإنجازات قابلة للقياس لكل دور.",
        "pt": "Use verbos de ação fortes e conquistas mensuráveis para cada função.",
        "it": "Usa verbi d'azione forti e risultati misurabili per ogni ruolo.",
        "nl": "Gebruik sterke actiewerkwoorden en meetbare prestaties voor elke rol.",
        "ru": "Используйте сильные глаголы действия и измеримые достижения для каждой роли.",
        "ja": "各役職に強いアクション動詞と測定可能な実績を使用してください。",
        "ko": "각 역할에 대해 강력한 행동 동사와 측정 가능한 성과를 사용하세요.",
        "zh": "为每个职位使用强有力的行动动词和可量化的成就。",
    },
    "sections_missing": {
        "en": "Add clear section headers: Education, Experience, Skills, Contact.",
        "tr": "Başlıklar: Education, Experience, Skills, Contact gibi net bölümler ekleyin.",
        "fr": "Ajoutez des en-têtes de section clairs : Formation, Expérience, Compétences, Contact.",
        "de": "Fügen Sie klare Abschnittsüberschriften hinzu: Bildung, Erfahrung, Fähigkeiten, Kontakt.",
        "es": "Agrega encabezados de sección claros: Educación, Experiencia, Habilidades, Contacto.",
        "ar": "أضف عناوين أقسام واضحة: التعليم، الخبرة، المهارات، التواصل.",
        "pt": "Adicione cabeçalhos de seção claros: Educação, Experiência, Habilidades, Contato.",
        "it": "Aggiungi intestazioni di sezione chiare: Istruzione, Esperienza, Competenze, Contatti.",
        "nl": "Voeg duidelijke sectiekoppen toe: Opleiding, Ervaring, Vaardigheden, Contact.",
        "ru": "Добавьте четкие заголовки разделов: Образование, Опыт, Навыки, Контакты.",
        "ja": "明確なセクションヘッダーを追加してください：学歴、経験、スキル、連絡先。",
        "ko": "명확한 섹션 헤더를 추가하세요: 학력, 경력, 기술, 연락처.",
        "zh": "添加清晰的部分标题：教育、经验、技能、联系方式。",
    },
    "contact_missing": {
        "en": "Add your email and phone number (and LinkedIn if available) at the top of your CV.",
        "tr": "CV üst kısmına e-posta ve telefon numarası (ve varsa LinkedIn) ekleyin.",
        "fr": "Ajoutez votre e-mail et numéro de téléphone (et LinkedIn si disponible) en haut de votre CV.",
        "de": "Fügen Sie Ihre E-Mail und Telefonnummer (und LinkedIn falls vorhanden) oben in Ihren Lebenslauf ein.",
        "es": "Agrega tu correo electrónico y número de teléfono (y LinkedIn si está disponible) en la parte superior de tu CV.",
        "ar": "أضف بريدك الإلكتروني ورقم هاتفك (ولينكدإن إن وجد) في أعلى سيرتك الذاتية.",
        "pt": "Adicione seu e-mail e número de telefone (e LinkedIn se disponível) no topo do seu currículo.",
        "it": "Aggiungi la tua email e numero di telefono (e LinkedIn se disponibile) in cima al tuo CV.",
        "nl": "Voeg uw e-mail en telefoonnummer (en LinkedIn indien beschikbaar) bovenaan uw CV toe.",
        "ru": "Добавьте email и номер телефона (и LinkedIn при наличии) в верхнюю часть резюме.",
        "ja": "CVの上部にメールアドレスと電話番号（利用可能であればLinkedIn）を追加してください。",
        "ko": "이력서 상단에 이메일과 전화번호(가능하면 LinkedIn)를 추가하세요.",
        "zh": "在简历顶部添加您的电子邮件和电话号码（如有LinkedIn也请添加）。",
    },
    "bullets_low": {
        "en": "Use bullet points for achievements; avoid long paragraphs.",
        "tr": "Kazanımları madde listesi ile yazın; uzun paragraflardan kaçının.",
        "fr": "Utilisez des puces pour les réalisations ; évitez les longs paragraphes.",
        "de": "Verwenden Sie Aufzählungszeichen für Erfolge; vermeiden Sie lange Absätze.",
        "es": "Usa viñetas para los logros; evita párrafos largos.",
        "ar": "استخدم النقاط النقطية للإنجازات؛ تجنب الفقرات الطويلة.",
        "pt": "Use marcadores para conquistas; evite parágrafos longos.",
        "it": "Usa elenchi puntati per i risultati; evita paragrafi lunghi.",
        "nl": "Gebruik opsommingstekens voor prestaties; vermijd lange alinea's.",
        "ru": "Используйте маркированные списки для достижений; избегайте длинных абзацев.",
        "ja": "実績には箇条書きを使用し、長い段落を避けてください。",
        "ko": "성과에는 글머리 기호를 사용하고 긴 단락은 피하세요.",
        "zh": "使用项目符号列出成就；避免长段落。",
    },
    "length_bad": {
        "en": "Keep your CV length between 1-2 pages.",
        "tr": "CV uzunluğunu 1-2 sayfa aralığında tutmaya çalışın.",
        "fr": "Gardez votre CV entre 1 et 2 pages.",
        "de": "Halten Sie Ihren Lebenslauf auf 1-2 Seiten.",
        "es": "Mantén tu CV entre 1 y 2 páginas.",
        "ar": "حافظ على طول سيرتك الذاتية بين صفحة وصفحتين.",
        "pt": "Mantenha seu currículo entre 1 e 2 páginas.",
        "it": "Mantieni il tuo CV tra 1 e 2 pagine.",
        "nl": "Houd uw CV op 1-2 pagina's.",
        "ru": "Длина резюме должна быть 1-2 страницы.",
        "ja": "CVの長さを1〜2ページに保ってください。",
        "ko": "이력서 길이를 1-2페이지로 유지하세요.",
        "zh": "将简历长度保持在1-2页之间。",
    },
    "quantify_achievements": {
        "en": "Quantify your achievements with numbers, percentages, or dollar amounts (e.g., 'increased revenue by 25%').",
        "tr": "Başarılarınızı sayılarla, yüzdelerle veya parasal değerlerle destekleyin (ör. 'geliri %25 artırdı').",
        "fr": "Quantifiez vos réalisations avec des chiffres, pourcentages ou montants (ex : 'augmenté le chiffre d'affaires de 25%').",
        "de": "Quantifizieren Sie Ihre Erfolge mit Zahlen, Prozentsätzen oder Geldbeträgen (z.B. 'Umsatz um 25% gesteigert').",
        "es": "Cuantifica tus logros con números, porcentajes o montos (ej: 'aumentó los ingresos en un 25%').",
        "ar": "حدد إنجازاتك بالأرقام أو النسب المئوية أو المبالغ المالية (مثال: 'زيادة الإيرادات بنسبة 25%').",
        "pt": "Quantifique suas conquistas com números, porcentagens ou valores monetários (ex: 'aumentou a receita em 25%').",
        "it": "Quantifica i tuoi risultati con numeri, percentuali o importi (es: 'aumentato il fatturato del 25%').",
        "nl": "Kwantificeer uw prestaties met cijfers, percentages of bedragen (bijv. 'omzet met 25% verhoogd').",
        "ru": "Подкрепите достижения цифрами, процентами или суммами (напр. 'увеличил выручку на 25%').",
        "ja": "数値、パーセント、金額で実績を定量化してください（例：「売上を25%増加」）。",
        "ko": "숫자, 백분율, 금액으로 성과를 정량화하세요 (예: '매출 25% 증가').",
        "zh": "用数字、百分比或金额量化您的成就（例如：'收入增长25%'）。",
    },
    "formatting_inconsistent": {
        "en": "Use consistent formatting throughout: same date format, same bullet style, and avoid excessive whitespace.",
        "tr": "Tutarlı bir biçimlendirme kullanın: aynı tarih formatı, aynı madde işareti stili ve aşırı boşluklardan kaçının.",
        "fr": "Utilisez un formatage cohérent : même format de date, même style de puces, et évitez les espaces excessifs.",
        "de": "Verwenden Sie einheitliche Formatierung: gleiches Datumsformat, gleicher Aufzählungsstil, vermeiden Sie übermäßige Leerzeichen.",
        "es": "Usa un formato consistente: mismo formato de fecha, mismo estilo de viñetas, y evita espacios excesivos.",
        "ar": "استخدم تنسيقاً متسقاً: نفس صيغة التاريخ، نفس نمط النقاط، وتجنب الفراغات المفرطة.",
        "pt": "Use formatação consistente: mesmo formato de data, mesmo estilo de marcadores, e evite espaços excessivos.",
        "it": "Usa una formattazione coerente: stesso formato di data, stesso stile di elenco, ed evita spazi eccessivi.",
        "nl": "Gebruik consistente opmaak: zelfde datumformaat, zelfde opsommingsstijl, en vermijd overmatige witruimte.",
        "ru": "Используйте единообразное форматирование: одинаковый формат дат, стиль маркеров и избегайте лишних пробелов.",
        "ja": "一貫したフォーマットを使用してください：同じ日付形式、同じ箇条書きスタイル、過度な空白を避ける。",
        "ko": "일관된 서식을 사용하세요: 동일한 날짜 형식, 동일한 글머리 기호 스타일, 과도한 공백 피하기.",
        "zh": "使用一致的格式：相同的日期格式、相同的项目符号样式，并避免过多的空白。",
    },
}


def get_ats_suggestion(key: str, lang: str = "en") -> str:
    template = ATS_SUGGESTIONS.get(key, {})
    return template.get(lang, template.get("en", ""))


def clean_lower(text: str) -> str:
    """Global ve dil bağımsız küçük harfe dönüştürme fonksiyonu.
    Türkçe'deki noktalı büyük İ harfinin (U+0130) bozulmasını ve regex eşleşmelerinin kaçırılmasını engeller.
    """
    if not text:
        return ""
    # Noktalı büyük İ harfini standart küçük 'i' ile değiştir
    text = text.replace("\u0130", "i")
    lowered = text.lower()
    # Olası birleşen karakter bozulmalarını düzelt
    lowered = lowered.replace("i\u0307", "i").replace("i̇", "i")
    return lowered


SECTION_ALIASES = {
    "summary": {
        "summary",
        "professional summary",
        "personal information",
        "profile",
        "about",
        "objective",
        "career summary",
        # TR
        "özet",
        "profil",
        "kişisel bilgiler",
        "kariyer özeti",
        # FR
        "résumé professionnel",
        "profil professionnel",
        # DE
        "zusammenfassung",
        "über mich",
        "kurzprofil",
        # ES
        "resumen profesional",
        "perfil profesional",
        "resumen",
        "perfil",
        # PT
        "resumo profissional",
        "resumo",
        # IT
        "profilo professionale",
        "riepilogo",
        "sommario",
        # NL
        "samenvatting",
        "profiel",
        "persoonlijk profiel",
        # RU
        "резюме",
        "профиль",
        "о себе",
        # PL
        "podsumowanie",
        "podsumowanie zawodowe",
        "profil zawodowy",
        # SV/NO/DA/FI
        "sammanfattning",
        "sammendrag",
        "yhteenveto",
        "profiili",
        # CS/HU/RO
        "shrnutí",
        "összefoglaló",
        "rezumat",
        # AR/ZH/JA/KO/HI
        "ملخص",
        "الملف الشخصي",
        "个人简介",
        "摘要",
        "概要",
        "プロフィール",
        "요약",
        "프로필",
        "सारांश",
        # ID/VI/TH
        "ringkasan",
        "tóm tắt",
        "สรุป",
        "โปรไฟล์",
    },
    "experience": {
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "work history",
        # TR
        "deneyim",
        "iş deneyimi",
        "mesleki deneyim",
        # FR
        "expérience",
        "expérience professionnelle",
        # DE
        "erfahrung",
        "berufserfahrung",
        # ES
        "experiencia",
        "experiencia laboral",
        "experiencia profesional",
        # PT
        "experiência",
        "experiência profissional",
        # IT
        "esperienza",
        "esperienza lavorativa",
        # NL
        "ervaring",
        "werkervaring",
        # RU
        "опыт",
        "опыт работы",
        # PL
        "doświadczenie",
        "doświadczenie zawodowe",
        # SV/NO/DA/FI
        "erfarenhet",
        "erfaring",
        "kokemus",
        "työkokemus",
        # CS/HU/RO
        "zkušenosti",
        "tapasztalat",
        "experiență",
        # AR/ZH/JA/KO/HI
        "الخبرة",
        "الخبرة المهنية",
        "工作经验",
        "工作经历",
        "職歴",
        "경력",
        "경험",
        "अनुभव",
        # ID/VI/TH
        "pengalaman",
        "pengalaman kerja",
        "kinh nghiệm",
        "předchozí zaměstnání",
        "geçmiş işler",
        "professional history",
        "pengalaman",
        "pengalaman kerja",
        "kinh nghiệm",
        "ประสบการณ์",
    },
    "education": {
        "education",
        "academic background",
        "qualifications",
        # TR
        "eğitim",
        "akademik geçmiş",
        # FR
        "formation",
        "études",
        # DE
        "ausbildung",
        "bildung",
        "studium",
        # ES
        "educación",
        "formación",
        # PT
        "educação",
        "formação acadêmica",
        # IT
        "istruzione",
        "formazione",
        # NL
        "opleiding",
        "onderwijs",
        # RU
        "образование",
        # PL
        "wykształcenie",
        "edukacja",
        # SV/NO/DA/FI
        "utbildning",
        "utdanning",
        "uddannelse",
        "koulutus",
        # CS/HU/RO
        "vzdělání",
        "végzettség",
        "educație",
        "studii",
        # AR/ZH/JA/KO/HI
        "التعليم",
        "教育",
        "学历",
        "学歴",
        "학력",
        "शिक्षा",
        # ID/VI/TH
        "pendidikan",
        "học vấn",
        "การศึกษา",
    },
    "skills": {
        "skills",
        "technical skills",
        "core competencies",
        "competencies",
        "technologies",
        # TR
        "beceriler",
        "yetenekler",
        "teknik beceriler",
        "yetkinlikler",
        # FR
        "compétences",
        "compétences techniques",
        # DE
        "fähigkeiten",
        "kenntnisse",
        "kompetenzen",
        # ES
        "habilidades",
        "competencias",
        # PT
        "competências",
        # IT
        "competenze",
        "abilità",
        # NL
        "vaardigheden",
        "competenties",
        # RU
        "навыки",
        "умения",
        "компетенции",
        # PL
        "umiejętności",
        "kompetencje",
        # SV/NO/DA/FI
        "färdigheter",
        "ferdigheter",
        "færdigheder",
        "taidot",
        "osaaminen",
        # CS/HU/RO
        "dovednosti",
        "készségek",
        "competențe",
        # AR/ZH/JA/KO/HI
        "المهارات",
        "技能",
        "スキル",
        "기술",
        "कौशल",
        # ID/VI/TH
        "keahlian",
        "keterampilan",
        "kỹ năng",
        "ทักษะ",
    },
    "projects": {
        "project",
        "projects",
        "project experience",
        "personal projects",
        # TR
        "projeler",
        # FR
        "projets",
        # DE
        "projekte",
        # ES
        "proyectos",
        # PT/IT/NL
        "projetos",
        "progetti",
        "projecten",
        # RU
        "проекты",
        # PL/CS/HU
        "projekty",
        "projektek",
        # SV/DA/NO/FI/RO
        "projekter",
        "prosjekter",
        "projektit",
        "proiecte",
        # AR/ZH/JA/KO/HI
        "المشاريع",
        "项目",
        "プロジェクト",
        "프로젝트",
        "परियोजनाएं",
        # ID/VI/TH
        "proyek",
        "dự án",
        "โครงการ",
    },
    "certifications": {
        "certifications",
        "certificates",
        "licenses",
        # TR
        "sertifikalar",
        "belgeler",
        # FR
        "diplômes",
        # DE
        "zertifizierungen",
        "zertifikate",
        # ES
        "certificaciones",
        # PT
        "certificações",
        # IT/NL
        "certificazioni",
        "certificeringen",
        # RU
        "сертификаты",
        # PL/CS/HU
        "certyfikaty",
        "certifikáty",
        "tanúsítványok",
        # SV/NO/DA/FI/RO
        "certifieringar",
        "sertifiseringer",
        "sertifikaatit",
        "certificări",
        # AR/ZH/JA/KO/HI
        "الشهادات",
        "证书",
        "資格",
        "자격증",
        "प्रमाणपत्र",
        # ID/VI/TH
        "sertifikasi",
        "chứng chỉ",
        "ใบรับรอง",
    },
    "languages": {
        "languages",
        "language skills",
        # TR
        "diller",
        "yabancı diller",
        # FR
        "langues",
        # DE
        "sprachen",
        # ES/PT
        "idiomas",
        # IT
        "lingue",
        # NL
        "talen",
        # RU
        "языки",
        # PL
        "języki",
        # SV/NO
        "språk",
        # DA
        "sprog",
        # FI
        "kielet",
        # CS/HU
        "jazyky",
        "nyelvek",
        # RO
        "limbi",
        # AR/ZH/JA/KO/HI
        "اللغات",
        "语言",
        "言語",
        "언어",
        "भाषाएं",
        # ID/VI/TH
        "bahasa",
        "ngôn ngữ",
        "ภาษา",
    },
    "contact": {
        "contact",
        "contact information",
        "communication",
        # TR
        "iletişim",
        # FR
        "coordonnées",
        # DE
        "kontakt",
        "kontaktdaten",
        # ES
        "contacto",
        # PT/IT
        "contato",
        "contatto",
        # NL
        "contactgegevens",
        # RU
        "контакты",
        # PL
        "dane kontaktowe",
        # FI
        "yhteystiedot",
        # HU
        "kapcsolat",
        "elérhetőség",
        # AR/ZH/JA/KO/HI
        "الاتصال",
        "联系方式",
        "連絡先",
        "연락처",
        "संपर्क",
        # ID/VI/TH
        "kontak",
        "liên hệ",
        "ติดต่อ",
    },
    "interests": {
        "interests",
        "hobbies",
        "personal interests",
        # TR
        "ilgi alanları",
        "hobiler",
        # FR
        "centres d'intérêt",
        "loisirs",
        # DE
        "interessen",
        "hobbys",
        # ES
        "intereses",
        "aficiones",
        # PT/IT
        "interesses",
        "interessi",
        # NL
        "hobby's",
        # RU
        "интересы",
        "хобби",
        # PL
        "zainteresowania",
        # SV/NO/DA
        "intressen",
        "interesser",
        # FI
        "kiinnostukset",
        "harrastukset",
        # CS/HU/RO
        "zájmy",
        "érdeklődés",
        "interese",
        # AR/ZH/JA/KO/HI
        "الاهتمامات",
        "兴趣",
        "趣味",
        "취미",
        "रुचियां",
        # ID/VI/TH
        "minat",
        "sở thích",
        "ความสนใจ",
    },
}
