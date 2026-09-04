"""Compiled regexes and header-hint patterns for the CV section classifier.

Pure pattern data extracted from ``section_classifier.py`` (no logic). Imported
back there; kept together because the regexes reference one another.
"""

import re
from typing import Dict

_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?"
    r"|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?"
    r"|dec(?:ember)?)"
)
# Generic month-like word: any 3-12 letter word (captures non-English months)
_MONTH_WORD = r"[A-Za-z\u00C0-\u024F\u0400-\u04FF]{3,12}\.?"
_YEAR = r"(?:19|20)\d{2}"
# Numeric date prefix: 01/2020, 2020-01, 01.2020
_NUMERIC_DATE = r"(?:\d{1,2}[/.]\s*)"
# Language-agnostic "present": any non-year word of 3+ letters (covers all languages)
_PRESENT_WORD = r"(?![12]\d{3}\b)[A-Za-z\u00C0-\u024F\u0400-\u04FF]{3,}(?:\s+[A-Za-z\u00C0-\u024F]{2,})?"
_DATE_RANGE_RE = re.compile(
    rf"(?:(?:{_MONTH}|{_MONTH_WORD})\s+|{_NUMERIC_DATE})?{_YEAR}\s*(?:[-–—]|to)\s*"
    rf"(?:(?:(?:{_MONTH}|{_MONTH_WORD})\s+|{_NUMERIC_DATE})?{_YEAR}"
    rf"|{_PRESENT_WORD})",
    re.I,
)
# Open-ended date: "2020 –" at end of line (handles any language's "present")
_OPEN_DATE_RE = re.compile(rf"{_YEAR}\s*[-–—]\s*$", re.MULTILINE)
_SINGLE_YEAR_RE = re.compile(rf"\b{_YEAR}\b")

_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(?:\+\d{1,3}[\s.-]?)?"  # optional country code: +1, +90, +44
    r"\(?\d{2,4}\)?[\s.-]?"  # area code: (555), 555, 0555
    r"\d{2,4}[\s.-]?"  # middle digits
    r"\d{2,4}"  # last digits
    r"(?!\d)"
)
_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com|[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?:/\S*)?",
    re.I,
)

# Education indicators — international degree abbreviations + structural
_EDUCATION_KEYWORDS = re.compile(
    r"\b(?:university|institute|college|school|faculty|academy"
    r"|bachelor|master|mba|ph\.?d"
    r"|b\.?sc|m\.?sc|b\.?a|m\.?a|diploma|associate|degree"
    r"|gpa|cgpa)\b",
    re.I,
)

# Company type indicators — international legal entity suffixes
_EXPERIENCE_KEYWORDS = re.compile(
    r"\b(?:inc|ltd|llc|gmbh|corp|co\.|pvt|pty"
    r"|s\.?a\.?|s\.?l\.?|sarl|sas|s\.?r\.?l\.?|a\.?g\.?)\b",
    re.I,
)

# Project indicators — URL patterns + universal keywords
_PROJECT_KEYWORDS = re.compile(
    r"(?:github\.com|gitlab\.com|bitbucket\.org)"
    r"|\b(?:project|repository|repo"
    r"|tech\s+stack|used\s+technolog\w*|tools?\s+used|built\s+with"
    r"|personal\s+project)\b",
    re.I,
)

# Contextual project hints (sentence-level patterns)
_PROJECT_CONTEXT_RE = re.compile(
    r"\b(?:tech\s+stack|used\s+technolog\w*|tools?\s*(?:used|:)|built\s+with"
    r"|developed\s+(?:with|using)|implemented\s+(?:with|using)|stack\s*:)\b",
    re.I,
)

# Certification indicators — international cert names
_CERT_KEYWORDS = re.compile(
    r"\b(?:certified|certification|certificate|license|credential"
    r"|comptia|pmp|cissp|cka|ckad|ccna|ccnp|togaf|itil|scrum\s+master)\b",
    re.I,
)

# Well-known cert provider + title combos (each line is a cert on its own)
_CERT_PROVIDER_RE = re.compile(
    r"\b(?:aws|amazon|google\s+cloud|gcp|azure|microsoft|cisco|oracle"
    r"|red\s*hat|hashicorp|terraform|kubernetes|salesforce|comptia)\b",
    re.I,
)

# Interest / hobby indicators
_INTEREST_KEYWORDS = re.compile(
    r"\b(?:hobbies?|interests?|volunteer(?:ing)?|swimming|reading|traveling"
    r"|gaming|photography|cooking|music|sport|yoga|chess|hiking"
    r"|writing|drawing|painting|gardening|cycling|running|fishing"
    r"|camping|dancing|singing|meditation)\b",
    re.I,
)

# Language proficiency indicators — CEFR levels + universal English terms
_LANGUAGE_KEYWORDS = re.compile(
    r"\b(?:A[12]|B[12]|C[12]"
    r"|native|fluent|intermediate|beginner|proficient|basic|advanced"
    r"|elementary|upper[\s-]?intermediate"
    r"|ana\s*dil|ileri\s*d[uü]zey|orta\s*d[uü]zey"
    r"|ba[sş]lang[ıi][cç]|temel)\b",
    re.I,
)

# Structural: capitalized multi-word phrase (institution/company name in any language)
# Matches "Istanbul Technical University", "東京大学", "Société Générale" etc.
_CAPITALIZED_PHRASE_RE = re.compile(
    r"(?:[A-ZÀ-ÖØ-Þ\u0100-\u024F][\w\u00C0-\u024F'-]+(?:\s+(?:of|de|di|du|des|für|van|von|der|den|and|&|the)\s+)?){2,}",
)

# Tech/tool names — language-agnostic signal for projects/skills
_TECH_NAMES_RE = re.compile(
    r"\b(?:python|java(?:script)?|typescript|react|angular|vue|node\.?js"
    r"|django|flask|fastapi|spring|express|docker|kubernetes|aws|azure|gcp"
    r"|sql|postgresql|mysql|mongodb|redis|git|linux|html|css|c\+\+|c#|rust"
    r"|go(?:lang)?|swift|kotlin|flutter|tensorflow|pytorch|pandas|numpy"
    r"|\.net|graphql|rest(?:\s*api)?|ci/?cd|terraform|jenkins|nginx|apache"
    r"|rabbitmq|kafka|elasticsearch|sass|webpack|vite|tailwind)\b",
    re.I,
)

# Bullet line pattern (any bullet marker)
_BULLET_RE = re.compile(r"^\s*[-*\u2022\u2013\u2014\u2023\u25aa\u25a0]\s")

# Noise sections to discard (minimal set)
_NOISE_KEYWORDS = re.compile(
    r"\b(?:references|marital|nationality|photo)\b",
    re.I,
)

# Skill-style: short comma/pipe-separated items, or "Category: item, item"
_SKILL_DELIMITER_RE = re.compile(r"[,;|/]")

# Qualifier words that commonly precede "experience" in CV section headers
# ("Research Experience", "Health-Related Experience", "Other Work
# Experience"). Because the experience hint is anchored with ``$``, only lines
# that *end* in "experience" match — job titles such as "User Experience
# Designer" are unaffected.
_EXP_QUALIFIER = (
    r"(?:research|relevant|clinical|teaching|volunteer|voluntary|additional|other"
    r"|related|industry|industrial|laboratory|lab|technical|healthcare"
    r"|health[\s-]?related|field|military|international|leadership|internship"
    r"|hands[\s-]?on|summer|key|academic|project|career|professional|work)"
)

# Known section header aliases — BONUS signal, English only.
# Non-English headers are detected structurally (short/ALL-CAPS/Title Case)
# and classified by block content instead.
_HEADER_HINTS: Dict[str, re.Pattern] = {
    "summary": re.compile(
        r"^(?:summary|professional\s+summary|profile|about(?:\s+me)?|objective"
        r"|career\s+summary|career\s+objective|personal\s+statement"
        r"|personal\s+profile|personal\s+summary|executive\s+summary"
        r"|executive\s+profile"
        r"|personal\s+information|introduction|personal"
        # TR
        r"|(?:profesyonel\s+)?[öo]zet|profil|ki[şs]isel\s+bilgiler|kariyer\s+[öo]zeti"
        # FR
        r"|r[ée]sum[ée](?:\s+professionnel)?|profil\s+professionnel"
        # DE
        r"|pers[öo]nliche\s+zusammenfassung|zusammenfassung|[üu]ber\s+mich|kurzprofil"
        # ES
        r"|resumen(?:\s+profesional)?|perfil(?:\s+profesional)?|objetivo"
        # PT
        r"|resumo(?:\s+profissional)?|objetivo\s+profissional"
        # IT
        r"|profilo\s+professionale|riepilogo|sommario"
        # NL
        r"|samenvatting|profiel|persoonlijk\s+profiel"
        # RU
        r"|резюме|профиль|о\s+себе|краткое\s+описание"
        # PL
        r"|podsumowanie(?:\s+zawodowe)?|profil\s+zawodowy|o\s+mnie"
        # SV
        r"|sammanfattning|personlig\s+profil"
        # NO/DA
        r"|sammendrag"
        # FI
        r"|yhteenveto|profiili|henkil[öo]profiili"
        # CS
        r"|shrnut[ií]|osobn[ií]\s+profil"
        # HU
        r"|[öo]sszefoglal[óo]|szem[ée]lyes\s+profil"
        # RO
        r"|rezumat|profil\s+personal|obiectiv"
        # AR
        r"|ملخص|نبذة\s+شخصية|الملف\s+الشخصي|هدف\s+وظيفي"
        # ZH
        r"|个人简介|个人概述|自我介绍|职业目标|摘要|个人总结"
        # JA
        r"|概要|自己紹介|プロフィール|職務要約"
        # KO
        r"|요약|자기소개|프로필|경력\s*요약"
        # HI
        r"|सारांश|प्रोफ़ाइल|परिचय|व्यक्तिगत\s+विवरण"
        # ID
        r"|ringkasan|tentang\s+saya|ikhtisar"
        # VI
        r"|tóm\s+tắt|hồ\s+sơ|giới\s+thiệu\s+bản\s+thân"
        # TH
        r"|สรุป|โปรไฟล์|ประวัติย่อ|เกี่ยวกับฉัน"
        r")$",
        re.I,
    ),
    "experience": re.compile(
        # One or two qualifier words before "experience" (e.g. "research
        # experience", "other work experience"); the trailing ``$`` keeps job
        # titles like "User Experience Designer" from matching.
        r"^(?:" + _EXP_QUALIFIER + r"[\s-]+){1,2}experience$"
        r"|^(?:experience|work\s+experience|professional\s+experience|employment"
        r"|employment\s+history|work\s+history|work\s+background|career\s+history|professional\s+background|industrial\s+training(?:\s+attended)?|trainings?|training"
        # TR
        r"|deneyim|i[sş]\s*deneyimi|mesleki\s*deneyim"
        # FR
        r"|exp[ée]rience(?:\s+professionnelle)?|parcours\s+professionnel"
        # DE
        r"|erfahrung|berufserfahrung|beruflicher\s+werdegang"
        # ES
        r"|experiencia(?:\s+laboral|\s+profesional)?|trayectoria\s+profesional"
        # PT
        r"|experi[êe]ncia(?:\s+profissional)?|hist[óo]rico\s+profissional"
        # IT
        r"|esperienza(?:\s+lavorativa|\s+professionale)?|esperienze\s+professionali"
        # NL
        r"|ervaring|werkervaring|professionele\s+ervaring"
        # RU
        r"|опыт(?:\s+работы)?|трудовой\s+стаж|профессиональный\s+опыт"
        # PL
        r"|do[śs]wiadczenie(?:\s+zawodowe)?|historia\s+zatrudnienia"
        # SV
        r"|erfarenhet|arbetslivserfarenhet|yrkeserfarenhet"
        # NO
        r"|arbeidserfaring|yrkeserfaring"
        # DA
        r"|erhvervserfaring|arbejdserfaring"
        # FI
        r"|kokemus|ty[öo]kokemus|ty[öo]historia"
        # CS
        r"|zku[šs]enosti|pracovn[ií]\s+zku[šs]enosti"
        # HU
        r"|tapasztalat|munkatapasztalat|szakmai\s+tapasztalat"
        # RO
        r"|experien[țt][ăa](?:\s+profesional[ăa])?"
        # AR
        r"|الخبرة(?:\s+المهنية)?|الخبرات|خبرة\s+العمل"
        # ZH
        r"|工作经验|工作经历|职业经历|工作履历"
        # JA
        r"|職歴|職務経歴"
        # KO
        r"|경력|경험|직무\s*경험|업무\s*경험"
        # HI
        r"|अनुभव|कार्य\s+अनुभव|कार्यानुभव"
        # ID
        r"|pengalaman(?:\s+kerja)?|riwayat\s+pekerjaan"
        # VI
        r"|kinh\s+nghi[ệe]m(?:\s+l[àa]m\s+vi[ệe]c)?"
        # TH
        r"|ประสบการณ์(?:ทำงาน|การทำงาน)?"
        r")$",
        re.I,
    ),
    "education": re.compile(
        r"^(?:education|academic\s+background|academic\s+qualifications?|educational\s+background|qualifications?|academic|academics"
        # "Educational Qualification", "Education Qualification", "Academic
        # Details" — standard headings in South-Asian CV templates.
        r"|education(?:al)?\s+qualifications?|education(?:al)?\s+details?|academic\s+details?"
        r"|education(?:al)?\s+background\s+details?"
        # TR
        r"|e[gğ]itim|akademik\s*ge[cç]mi[sş]"
        # FR
        r"|formation|[ée]tudes|parcours\s+acad[ée]mique"
        # DE
        r"|ausbildung|bildung|studium|akademische\s+ausbildung"
        # ES
        r"|educaci[óo]n|formaci[óo]n(?:\s+acad[ée]mica)?"
        # PT
        r"|educa[çc][ãa]o|forma[çc][ãa]o(?:\s+acad[êe]mica)?"
        # IT
        r"|istruzione|formazione|percorso\s+accademico"
        # NL
        r"|opleiding|onderwijs|opleidingen"
        # RU
        r"|образование|обучение"
        # PL
        r"|wykszta[łl]cenie|edukacja"
        # SV
        r"|utbildning|akademisk\s+bakgrund"
        # NO
        r"|utdanning|utdannelse"
        # DA
        r"|uddannelse|akademisk\s+baggrund"
        # FI
        r"|koulutus|opinnot"
        # CS
        r"|vzd[ěe]l[áa]n[ií]|studium"
        # HU
        r"|v[ée]gzetts[ée]g|tanulm[áa]nyok|oktat[áa]s"
        # RO
        r"|educa[țt]ie|studii"
        # AR
        r"|التعليم|المؤهلات\s+الأكاديمية|الدراسة"
        # ZH
        r"|教育|学历|教育背景|学习经历"
        # JA
        r"|学歴"
        # KO
        r"|학력|교육"
        # HI
        r"|शिक्षा|शैक्षिक\s+योग्यता"
        # ID
        r"|pendidikan|riwayat\s+pendidikan"
        # VI
        r"|h[ọo]c\s+v[ấa]n|tr[ìi]nh\s+đ[ộo]\s+h[ọo]c\s+v[ấa]n"
        # TH
        r"|การศึกษา|ประวัติการศึกษา"
        r")$",
        re.I,
    ),
    "skills": re.compile(
        r"^(?:skills|technical\s+skills|core\s+competencies|competencies|technologies"
        r"|key\s+skills|professional\s+skills|it\s+skills|hard\s+skills|soft\s+skills|skill\s+set|skills?\s+set|skills?\s+and\s+abilities"
        # TR
        r"|beceriler|yetenekler|teknik\s*beceriler|teknik\s*yetenekler|yetkinlikler"
        # FR
        r"|comp[ée]tences(?:\s+techniques)?|aptitudes"
        # DE
        r"|f[äa]higkeiten|kenntnisse|kompetenzen|technische\s+f[äa]higkeiten"
        # ES
        r"|habilidades|competencias|habilidades\s+t[ée]cnicas"
        # PT
        r"|compet[êe]ncias|aptid[õo]es"
        # IT
        r"|competenze|abilit[àa]|competenze\s+tecniche"
        # NL
        r"|vaardigheden|competenties|technische\s+vaardigheden"
        # RU
        r"|навыки|умения|компетенции|технические\s+навыки"
        # PL
        r"|umiej[ęe]tno[śs]ci|kompetencje"
        # SV
        r"|f[äa]rdigheter|kompetenser"
        # NO
        r"|ferdigheter|kompetanser"
        # DA
        r"|f[æa]rdigheder|kompetencer"
        # FI
        r"|taidot|osaaminen"
        # CS
        r"|dovednosti|schopnosti"
        # HU
        r"|k[ée]szs[ée]gek|k[ée]pess[ée]gek|szaktud[áa]s"
        # RO
        r"|competen[țt]e|abilit[ăa][țt]i"
        # AR
        r"|المهارات(?:\s+التقنية)?|القدرات"
        # ZH
        r"|技能|专业技能|核心能力"
        # JA
        r"|スキル|技術|能力"
        # KO
        r"|기술|스킬|역량|핵심\s*역량"
        # HI
        r"|कौशल|दक्षता|तकनीकी\s+कौशल"
        # ID
        r"|keahlian|keterampilan|kemampuan"
        # VI
        r"|k[ỹy]\s+n[ăa]ng|n[ăa]ng\s+l[ựu]c"
        # TH
        r"|ทักษะ|ความสามารถ|ทักษะเทคนิค"
        r")$",
        re.I,
    ),
    "projects": re.compile(
        r"^(?:projects?|project\s+experience|personal\s+projects?|academic\s+projects?"
        r"|key\s+projects"
        # TR
        r"|projeler|ki[sş]isel\s*projeler"
        # FR
        r"|projets?|projets\s+personnels"
        # DE
        r"|projekte?"
        # ES
        r"|proyectos?"
        # PT
        r"|projetos?|projectos?"
        # IT
        r"|progetti?"
        # NL
        r"|projecten?"
        # RU
        r"|проекты?|личные\s+проекты"
        # PL/CS
        r"|projekty?"
        # SV/DA
        r"|projekter"
        # NO
        r"|prosjekter"
        # FI
        r"|projektit?"
        # HU
        r"|projektek?"
        # RO
        r"|proiecte?"
        # AR
        r"|المشاريع|مشاريع"
        # ZH
        r"|项目|项目经验|个人项目"
        # JA
        r"|プロジェクト"
        # KO
        r"|프로젝트"
        # HI
        r"|परियोजनाएं|परियोजना"
        # ID
        r"|proyek"
        # VI
        r"|d[ựu]\s+[áa]n"
        # TH
        r"|โครงการ"
        r")$",
        re.I,
    ),
    "other": re.compile(
        r"^(?:achievements|awards|volunteer|activities|other\s+activities|publications|misc|other|personal\s+details)$",
        re.I,
    ),
    "certifications": re.compile(
        r"^(?:certifications?|certificates?|licenses?|awards?(?:\s+[&and]+\s+certifications?)?"
        # TR
        r"|sertifikalar|belgeler"
        # FR
        r"|dipl[ôo]mes?"
        # DE
        r"|zertifizierungen?|zertifikate?"
        # ES
        r"|certificaciones?|certificados?"
        # PT
        r"|certifica[çc][õo]es"
        # IT
        r"|certificazioni?"
        # NL
        r"|certificeringen?|certificaten?"
        # RU
        r"|сертификаты?|дипломы?"
        # PL
        r"|certyfikaty?"
        # SV
        r"|certifieringar?"
        # NO
        r"|sertifiseringer?"
        # DA
        r"|certificeringer?"
        # FI
        r"|sertifikaatit?|todistukset?"
        # CS
        r"|certifik[áa]ty?"
        # HU
        r"|tan[úu]s[ií]tv[áa]nyok?"
        # RO
        r"|certific[ăa]ri?"
        # AR
        r"|الشهادات|شهادات"
        # ZH
        r"|证书|资格证书|认证"
        # JA
        r"|資格|認定"
        # KO
        r"|자격증|인증"
        # HI
        r"|प्रमाणपत्र"
        # ID
        r"|sertifikasi|sertifikat"
        # VI
        r"|ch[ứu]ng\s+ch[ỉi]"
        # TH
        r"|ใบรับรอง|ประกาศนียบัตร"
        r")$",
        re.I,
    ),
    "languages": re.compile(
        r"^(?:languages?|language\s+skills|foreign\s+languages"
        # TR
        r"|diller|yabanc[ıi]\s*dil(?:ler)?"
        # FR
        r"|langues|comp[ée]tences\s+linguistiques"
        # DE
        r"|sprachen|sprachkenntnisse"
        # ES
        r"|idiomas|lenguas"
        # PT
        r"|l[íi]nguas"
        # IT
        r"|lingue|competenze\s+linguistiche"
        # NL
        r"|talen|talenkennis"
        # RU
        r"|языки|знание\s+языков|владение\s+языками"
        # PL
        r"|j[ęe]zyki(?:\s+obce)?"
        # SV/NO
        r"|spr[åa]k"
        # DA
        r"|sprog"
        # FI
        r"|kielet|kielitaito"
        # CS
        r"|jazyky|jazykov[ée]\s+znalosti"
        # HU
        r"|nyelvek|nyelvtud[áa]s|idegen\s+nyelvek"
        # RO
        r"|limbi(?:\s+str[ăa]ine)?"
        # AR
        r"|اللغات|المهارات\s+اللغوية"
        # ZH
        r"|语言|语言能力|外语"
        # JA
        r"|言語|語学"
        # KO
        r"|언어|외국어"
        # HI
        r"|भाषाएं|भाषा\s+कौशल"
        # ID
        r"|bahasa"
        # VI
        r"|ng[ôo]n\s+ng[ữu]|ngo[ạa]i\s+ng[ữu]"
        # TH
        r"|ภาษา|ทักษะทางภาษา"
        r")$",
        re.I,
    ),
    "contact": re.compile(
        r"^(?:contact|contact\s+information|communication"
        # TR
        r"|ileti[şs]im|ileti[şs]im\s+bilgileri"
        # FR
        r"|coordonn[ée]es|informations?\s+de\s+contact"
        # DE
        r"|kontakt|kontaktdaten|kontaktinformationen"
        # ES
        r"|contacto|informaci[óo]n\s+de\s+contacto|datos\s+de\s+contacto"
        # PT
        r"|conta[tc]to|informa[çc][õo]es\s+de\s+conta[tc]to"
        # IT
        r"|contatt[oi]|informazioni\s+di\s+contatto"
        # NL
        r"|contactgegevens"
        # RU
        r"|контакт(?:ы|ная\s+информация)?"
        # PL
        r"|dane\s+kontaktowe"
        # SV/NO/DA
        r"|kontakt(?:information|uppgifter|opplysninger)?"
        # FI
        r"|yhteystiedot"
        # CS
        r"|kontaktn[ií]\s+[úu]daje"
        # HU
        r"|kapcsolat|el[ée]rhet[őo]s[ée]g(?:ek)?"
        # RO
        r"|date\s+de\s+contact"
        # AR
        r"|الاتصال|التواصل|معلومات\s+الاتصال|بيانات\s+التواصل"
        # ZH
        r"|联系方式|联系信息|个人信息"
        # JA
        r"|連絡先|連絡情報"
        # KO
        r"|연락처|연락\s*정보"
        # HI
        r"|संपर्क|संपर्क\s+जानकारी"
        # ID
        r"|kontak|informasi\s+kontak"
        # VI
        r"|li[êe]n\s+h[ệe]|th[ôo]ng\s+tin\s+li[êe]n\s+h[ệe]"
        # TH
        r"|ติดต่อ|ข้อมูลติดต่อ"
        r")$",
        re.I,
    ),
    "interests": re.compile(
        r"^(?:interests?|hobbies|hobbies\s+and\s+interests|personal\s+interests?"
        # TR
        r"|ilgi\s+alanlar[ıi]|hobiler"
        # FR
        r"|centres?\s+d['']\s*int[ée]r[êe]t|loisirs|passions"
        # DE
        r"|interessen|hobbys?"
        # ES
        r"|intereses|aficiones|pasatiempos"
        # PT
        r"|interesses|passatempos"
        # IT
        r"|interessi|hobby|passioni|tempo\s+libero"
        # NL
        r"|interesses|hobby'?s"
        # RU
        r"|интересы|хобби|увлечения"
        # PL
        r"|zainteresowania"
        # SV
        r"|intressen"
        # NO/DA
        r"|interesser"
        # FI
        r"|kiinnostukset|harrastukset"
        # CS
        r"|z[áa]jmy|kon[ií][čc]ky"
        # HU
        r"|[ée]rdekl[őo]d[ée]s|hobbik?"
        # RO
        r"|interese|hobby-?uri"
        # AR
        r"|الاهتمامات|الهوايات"
        # ZH
        r"|兴趣|爱好|兴趣爱好"
        # JA
        r"|趣味|興味|関心"
        # KO
        r"|관심사|취미"
        # HI
        r"|रुचियां|शौक"
        # ID
        r"|minat|hobi"
        # VI
        r"|s[ởo]\s+th[ií]ch|đam\s+m[êe]"
        # TH
        r"|ความสนใจ|งานอดิเรก"
        r")$",
        re.I,
    ),
}
