"""Canonical section keys and alias maps for the CV section classifier.

Pure data extracted from ``section_classifier.py`` to shrink that module.
No logic here — only the canonical key list, the global alias map, and the
fuzzy substring fragments used by ``canonicalize_section_key``.
"""

from typing import Dict

_CANONICAL_KEYS = [
    "summary",
    "experience",
    "education",
    "skills",
    "projects",
    "certifications",
    "languages",
    "interests",
    "contact",
    "misc",
]

# Exhaustive alias → canonical map.  Used by _canonicalize_section_key as
# first-pass exact lookup before falling back to substring matching.
_GLOBAL_ALIASES: Dict[str, str] = {
    # ── summary ──────────────────────────────────────────────────────
    "personal information": "summary",
    "profile": "summary",
    "about": "summary",
    "about me": "summary",
    "objective": "summary",
    "career objective": "summary",
    "personal": "summary",
    "personal statement": "summary",
    "personal profile": "summary",
    "professional summary": "summary",
    "executive summary": "summary",
    "executive profile": "summary",
    "career summary": "summary",
    "introduction": "summary",
    # TR
    "özet": "summary",
    "kişisel bilgiler": "summary",
    "kariyer özeti": "summary",
    # FR
    "résumé professionnel": "summary",
    "profil professionnel": "summary",
    # DE
    "persönliche zusammenfassung": "summary",
    "zusammenfassung": "summary",
    "über mich": "summary",
    "kurzprofil": "summary",
    # ES
    "resumen profesional": "summary",
    "perfil profesional": "summary",
    "resumen": "summary",
    "perfil": "summary",
    # PT
    "resumo profissional": "summary",
    "perfil profissional": "summary",
    "resumo": "summary",
    "objetivo profissional": "summary",
    # IT
    "profilo professionale": "summary",
    "riepilogo": "summary",
    "sommario": "summary",
    # NL
    "samenvatting": "summary",
    "profiel": "summary",
    "persoonlijk profiel": "summary",
    # RU
    "резюме": "summary",
    "профиль": "summary",
    "о себе": "summary",
    "краткое описание": "summary",
    # PL
    "podsumowanie": "summary",
    "podsumowanie zawodowe": "summary",
    "profil zawodowy": "summary",
    "o mnie": "summary",
    # SV
    "sammanfattning": "summary",
    "personlig profil": "summary",
    # NO/DA
    "sammendrag": "summary",
    # FI
    "yhteenveto": "summary",
    "profiili": "summary",
    "henkilöprofiili": "summary",
    # CS
    "shrnutí": "summary",
    "osobní profil": "summary",
    # HU
    "összefoglaló": "summary",
    "személyes profil": "summary",
    # RO
    "rezumat": "summary",
    "profil personal": "summary",
    "obiectiv": "summary",
    # AR
    "ملخص": "summary",
    "نبذة شخصية": "summary",
    "الملف الشخصي": "summary",
    "هدف وظيفي": "summary",
    # ZH
    "个人简介": "summary",
    "个人概述": "summary",
    "自我介绍": "summary",
    "职业目标": "summary",
    "摘要": "summary",
    "个人总结": "summary",
    # JA
    "概要": "summary",
    "自己紹介": "summary",
    "プロフィール": "summary",
    "職務要約": "summary",
    # KO
    "요약": "summary",
    "자기소개": "summary",
    "프로필": "summary",
    "경력 요약": "summary",
    # HI
    "सारांश": "summary",
    "प्रोफ़ाइल": "summary",
    "परिचय": "summary",
    "व्यक्तिगत विवरण": "summary",
    # ID
    "ringkasan": "summary",
    "tentang saya": "summary",
    "ikhtisar": "summary",
    # VI
    "tóm tắt": "summary",
    "hồ sơ": "summary",
    "giới thiệu bản thân": "summary",
    # TH
    "สรุป": "summary",
    "โปรไฟล์": "summary",
    "ประวัติย่อ": "summary",
    # ── contact ──────────────────────────────────────────────────────
    "communication": "contact",
    "contact information": "contact",
    "contact info": "contact",
    "personal info": "contact",
    "details": "contact",
    # TR
    "iletişim": "contact",
    "iletişim bilgileri": "contact",
    # FR
    "coordonnées": "contact",
    "informations de contact": "contact",
    # DE
    "kontakt": "contact",
    "kontaktdaten": "contact",
    "kontaktinformationen": "contact",
    # ES
    "contacto": "contact",
    "información de contacto": "contact",
    "datos de contacto": "contact",
    # PT
    "contato": "contact",
    "informações de contato": "contact",
    # IT
    "contatto": "contact",
    "contatti": "contact",
    "informazioni di contatto": "contact",
    # NL
    "contactgegevens": "contact",
    # RU
    "контакт": "contact",
    "контакты": "contact",
    "контактная информация": "contact",
    # PL
    "dane kontaktowe": "contact",
    # SV
    "kontaktinformation": "contact",
    "kontaktuppgifter": "contact",
    # NO
    "kontaktopplysninger": "contact",
    # FI
    "yhteystiedot": "contact",
    # CS
    "kontaktní údaje": "contact",
    # HU
    "kapcsolat": "contact",
    "elérhetőség": "contact",
    "elérhetőségek": "contact",
    # RO
    "date de contact": "contact",
    # AR
    "الاتصال": "contact",
    "التواصل": "contact",
    "معلومات الاتصال": "contact",
    "بيانات التواصل": "contact",
    # ZH
    "联系方式": "contact",
    "联系信息": "contact",
    # JA
    "連絡先": "contact",
    "連絡情報": "contact",
    # KO
    "연락처": "contact",
    "연락 정보": "contact",
    # HI
    "संपर्क": "contact",
    "संपर्क जानकारी": "contact",
    # ID
    "kontak": "contact",
    "informasi kontak": "contact",
    # VI
    "liên hệ": "contact",
    "thông tin liên hệ": "contact",
    # TH
    "ติดต่อ": "contact",
    "ข้อมูลติดต่อ": "contact",
    # ── experience ───────────────────────────────────────────────────
    "work": "experience",
    "employment": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "career history": "experience",
    "work history": "experience",
    "work background": "experience",
    "employment history": "experience",
    "professional background": "experience",
    "training": "experience",
    "trainings": "experience",
    # TR
    "deneyim": "experience",
    "iş deneyimi": "experience",
    "mesleki deneyim": "experience",
    # FR
    "expérience": "experience",
    "expérience professionnelle": "experience",
    "parcours professionnel": "experience",
    # DE
    "erfahrung": "experience",
    "berufserfahrung": "experience",
    "beruflicher werdegang": "experience",
    # ES
    "experiencia": "experience",
    "experiencia laboral": "experience",
    "experiencia profesional": "experience",
    "trayectoria profesional": "experience",
    # PT
    "experiência": "experience",
    "experiência profissional": "experience",
    "histórico profissional": "experience",
    # IT
    "esperienza": "experience",
    "esperienza lavorativa": "experience",
    "esperienze professionali": "experience",
    # NL
    "ervaring": "experience",
    "werkervaring": "experience",
    "professionele ervaring": "experience",
    # RU
    "опыт": "experience",
    "опыт работы": "experience",
    "трудовой стаж": "experience",
    "профессиональный опыт": "experience",
    # PL
    "doświadczenie": "experience",
    "doświadczenie zawodowe": "experience",
    "historia zatrudnienia": "experience",
    # SV
    "erfarenhet": "experience",
    "arbetslivserfarenhet": "experience",
    "yrkeserfarenhet": "experience",
    # NO
    "erfaring": "experience",
    "arbeidserfaring": "experience",
    "yrkeserfaring": "experience",
    # DA
    "erhvervserfaring": "experience",
    "arbejdserfaring": "experience",
    # FI
    "kokemus": "experience",
    "työkokemus": "experience",
    "työhistoria": "experience",
    # CS
    "zkušenosti": "experience",
    "pracovní zkušenosti": "experience",
    # HU
    "tapasztalat": "experience",
    "munkatapasztalat": "experience",
    "szakmai tapasztalat": "experience",
    # RO
    "experiență": "experience",
    "experiență profesională": "experience",
    # AR
    "الخبرة": "experience",
    "الخبرة المهنية": "experience",
    "الخبرات": "experience",
    "خبرة العمل": "experience",
    # ZH
    "工作经验": "experience",
    "工作经历": "experience",
    "职业经历": "experience",
    "工作履历": "experience",
    # JA
    "職歴": "experience",
    "経験": "experience",
    "職務経歴": "experience",
    # KO
    "경력": "experience",
    "경험": "experience",
    "직무 경험": "experience",
    "업무 경험": "experience",
    # HI
    "अनुभव": "experience",
    "कार्य अनुभव": "experience",
    # ID
    "pengalaman": "experience",
    "pengalaman kerja": "experience",
    "riwayat pekerjaan": "experience",
    # VI
    "kinh nghiệm": "experience",
    "kinh nghiệm làm việc": "experience",
    # TH
    "ประสบการณ์": "experience",
    "ประสบการณ์ทำงาน": "experience",
    # ── education ────────────────────────────────────────────────────
    "academic": "education",
    "academics": "education",
    "qualifications": "education",
    "academic qualifications": "education",
    "studies": "education",
    "academic background": "education",
    "educational background": "education",
    # TR
    "eğitim": "education",
    "akademik geçmiş": "education",
    # FR
    "formation": "education",
    "études": "education",
    "parcours académique": "education",
    # DE
    "ausbildung": "education",
    "bildung": "education",
    "studium": "education",
    "akademische ausbildung": "education",
    # ES
    "educación": "education",
    "formación": "education",
    "formación académica": "education",
    # PT
    "educação": "education",
    "formação acadêmica": "education",
    # IT
    "istruzione": "education",
    "formazione": "education",
    # NL
    "opleiding": "education",
    "onderwijs": "education",
    "opleidingen": "education",
    # RU
    "образование": "education",
    "обучение": "education",
    # PL
    "wykształcenie": "education",
    "edukacja": "education",
    # SV
    "utbildning": "education",
    "akademisk bakgrund": "education",
    # NO
    "utdanning": "education",
    "utdannelse": "education",
    # DA
    "uddannelse": "education",
    "akademisk baggrund": "education",
    # FI
    "koulutus": "education",
    "opinnot": "education",
    # CS
    "vzdělání": "education",
    # HU
    "végzettség": "education",
    "tanulmányok": "education",
    "oktatás": "education",
    # RO
    "educație": "education",
    "studii": "education",
    # AR
    "التعليم": "education",
    "المؤهلات الأكاديمية": "education",
    "الدراسة": "education",
    # ZH
    "教育": "education",
    "学历": "education",
    "教育背景": "education",
    "学习经历": "education",
    # JA
    "学歴": "education",
    # KO
    "학력": "education",
    "교육": "education",
    # HI
    "शिक्षा": "education",
    "शैक्षिक योग्यता": "education",
    # ID
    "pendidikan": "education",
    "riwayat pendidikan": "education",
    # VI
    "học vấn": "education",
    "trình độ học vấn": "education",
    # TH
    "การศึกษา": "education",
    "ประวัติการศึกษา": "education",
    # ── skills ───────────────────────────────────────────────────────
    "technical skills": "skills",
    "core competencies": "skills",
    "skill set": "skills",
    "skills set": "skills",
    "competencies": "skills",
    "technologies": "skills",
    "abilities": "skills",
    "key skills": "skills",
    "professional skills": "skills",
    "it skills": "skills",
    "hard skills": "skills",
    "soft skills": "skills",
    # TR
    "beceriler": "skills",
    "yetenekler": "skills",
    "teknik beceriler": "skills",
    "yetkinlikler": "skills",
    # FR
    "compétences": "skills",
    "compétences techniques": "skills",
    "aptitudes": "skills",
    # DE
    "fähigkeiten": "skills",
    "kenntnisse": "skills",
    "kompetenzen": "skills",
    "technische fähigkeiten": "skills",
    # ES
    "habilidades": "skills",
    "competencias": "skills",
    "habilidades técnicas": "skills",
    # PT
    "competências": "skills",
    "aptidões": "skills",
    # IT
    "competenze": "skills",
    "abilità": "skills",
    "competenze tecniche": "skills",
    # NL
    "vaardigheden": "skills",
    "competenties": "skills",
    "technische vaardigheden": "skills",
    # RU
    "навыки": "skills",
    "умения": "skills",
    "компетенции": "skills",
    "технические навыки": "skills",
    # PL
    "umiejętności": "skills",
    "kompetencje": "skills",
    # SV
    "färdigheter": "skills",
    "kompetenser": "skills",
    # NO
    "ferdigheter": "skills",
    "kompetanser": "skills",
    # DA
    "færdigheder": "skills",
    "kompetencer": "skills",
    # FI
    "taidot": "skills",
    "osaaminen": "skills",
    # CS
    "dovednosti": "skills",
    "schopnosti": "skills",
    # HU
    "készségek": "skills",
    "képességek": "skills",
    "szaktudás": "skills",
    # RO
    "competențe": "skills",
    "abilități": "skills",
    # AR
    "المهارات": "skills",
    "المهارات التقنية": "skills",
    "القدرات": "skills",
    # ZH
    "技能": "skills",
    "专业技能": "skills",
    "核心能力": "skills",
    # JA
    "スキル": "skills",
    "技術": "skills",
    "能力": "skills",
    # KO
    "기술": "skills",
    "스킬": "skills",
    "역량": "skills",
    "핵심 역량": "skills",
    # HI
    "कौशल": "skills",
    "दक्षता": "skills",
    "तकनीकी कौशल": "skills",
    # ID
    "keahlian": "skills",
    "keterampilan": "skills",
    "kemampuan": "skills",
    # VI
    "kỹ năng": "skills",
    "năng lực": "skills",
    # TH
    "ทักษะ": "skills",
    "ความสามารถ": "skills",
    # ── projects ─────────────────────────────────────────────────────
    "project": "projects",
    "portfolio": "projects",
    "personal projects": "projects",
    "academic projects": "projects",
    "key projects": "projects",
    "project experience": "projects",
    # TR
    "projeler": "projects",
    "kişisel projeler": "projects",
    # FR
    "projets": "projects",
    "projets personnels": "projects",
    # DE
    "projekte": "projects",
    # ES
    "proyectos": "projects",
    # PT
    "projetos": "projects",
    "projectos": "projects",
    # IT
    "progetti": "projects",
    # NL
    "projecten": "projects",
    # RU
    "проекты": "projects",
    "личные проекты": "projects",
    # PL/CS
    "projekty": "projects",
    # SV/DA
    "projekter": "projects",
    # NO
    "prosjekter": "projects",
    # FI
    "projektit": "projects",
    # HU
    "projektek": "projects",
    # RO
    "proiecte": "projects",
    # AR
    "المشاريع": "projects",
    "مشاريع": "projects",
    # ZH
    "项目": "projects",
    "项目经验": "projects",
    "个人项目": "projects",
    # JA
    "プロジェクト": "projects",
    # KO
    "프로젝트": "projects",
    # HI
    "परियोजनाएं": "projects",
    "परियोजना": "projects",
    # ID
    "proyek": "projects",
    # VI
    "dự án": "projects",
    # TH
    "โครงการ": "projects",
    # ── certifications ───────────────────────────────────────────────
    "certification": "certifications",
    "certificates": "certifications",
    "certificate": "certifications",
    "licenses": "certifications",
    "awards": "certifications",
    "awards and certifications": "certifications",
    # TR
    "sertifikalar": "certifications",
    "belgeler": "certifications",
    # FR
    "diplômes": "certifications",
    # DE
    "zertifizierungen": "certifications",
    "zertifikate": "certifications",
    # ES
    "certificaciones": "certifications",
    "certificados": "certifications",
    # PT
    "certificações": "certifications",
    # IT
    "certificazioni": "certifications",
    # NL
    "certificeringen": "certifications",
    "certificaten": "certifications",
    # RU
    "сертификаты": "certifications",
    "дипломы": "certifications",
    # PL
    "certyfikaty": "certifications",
    # SV
    "certifieringar": "certifications",
    # NO
    "sertifiseringer": "certifications",
    # DA
    "certificeringer": "certifications",
    # FI
    "sertifikaatit": "certifications",
    "todistukset": "certifications",
    # CS
    "certifikáty": "certifications",
    # HU
    "tanúsítványok": "certifications",
    "minősítések": "certifications",
    # RO
    "certificări": "certifications",
    # AR
    "الشهادات": "certifications",
    "شهادات": "certifications",
    # ZH
    "证书": "certifications",
    "资格证书": "certifications",
    "认证": "certifications",
    # JA
    "資格": "certifications",
    "認定": "certifications",
    # KO
    "자격증": "certifications",
    "인증": "certifications",
    # HI
    "प्रमाणपत्र": "certifications",
    # ID
    "sertifikasi": "certifications",
    "sertifikat": "certifications",
    # VI
    "chứng chỉ": "certifications",
    # TH
    "ใบรับรอง": "certifications",
    "ประกาศนียบัตร": "certifications",
    # ── languages ────────────────────────────────────────────────────
    "language": "languages",
    "language skills": "languages",
    "foreign languages": "languages",
    "linguistic": "languages",
    # TR
    "diller": "languages",
    "yabancı diller": "languages",
    # FR
    "langues": "languages",
    "compétences linguistiques": "languages",
    # DE
    "sprachen": "languages",
    "sprachkenntnisse": "languages",
    # ES
    "idiomas": "languages",
    "lenguas": "languages",
    # PT
    "línguas": "languages",
    # IT
    "lingue": "languages",
    "competenze linguistiche": "languages",
    # NL
    "talen": "languages",
    "talenkennis": "languages",
    # RU
    "языки": "languages",
    "знание языков": "languages",
    "владение языками": "languages",
    # PL
    "języki": "languages",
    "języki obce": "languages",
    # SV/NO
    "språk": "languages",
    # DA
    "sprog": "languages",
    # FI
    "kielet": "languages",
    "kielitaito": "languages",
    # CS
    "jazyky": "languages",
    "jazykové znalosti": "languages",
    # HU
    "nyelvek": "languages",
    "nyelvtudás": "languages",
    "idegen nyelvek": "languages",
    # RO
    "limbi": "languages",
    "limbi străine": "languages",
    # AR
    "اللغات": "languages",
    "المهارات اللغوية": "languages",
    # ZH
    "语言": "languages",
    "语言能力": "languages",
    "外语": "languages",
    # JA
    "言語": "languages",
    "語学": "languages",
    # KO
    "언어": "languages",
    "외국어": "languages",
    # HI
    "भाषाएं": "languages",
    "भाषा कौशल": "languages",
    # ID
    "bahasa": "languages",
    # VI
    "ngôn ngữ": "languages",
    "ngoại ngữ": "languages",
    # TH
    "ภาษา": "languages",
    "ทักษะทางภาษา": "languages",
    # ── interests ────────────────────────────────────────────────────
    "interest": "interests",
    "hobbies": "interests",
    "personal interest": "interests",
    "personal interests": "interests",
    # TR
    "ilgi alanları": "interests",
    "hobiler": "interests",
    # FR
    "centres d'intérêt": "interests",
    "loisirs": "interests",
    "passions": "interests",
    # DE
    "interessen": "interests",
    "hobbys": "interests",
    # ES
    "intereses": "interests",
    "aficiones": "interests",
    "pasatiempos": "interests",
    # PT
    "interesses": "interests",
    "passatempos": "interests",
    # IT
    "interessi": "interests",
    "hobby": "interests",
    "passioni": "interests",
    "tempo libero": "interests",
    # NL
    "hobby's": "interests",
    # RU
    "интересы": "interests",
    "хобби": "interests",
    "увлечения": "interests",
    # PL
    "zainteresowania": "interests",
    # SV
    "intressen": "interests",
    # NO/DA
    "interesser": "interests",
    # FI
    "kiinnostukset": "interests",
    "harrastukset": "interests",
    # CS
    "zájmy": "interests",
    "koníčky": "interests",
    # HU
    "érdeklődés": "interests",
    "hobbik": "interests",
    # RO
    "interese": "interests",
    "hobby-uri": "interests",
    # AR
    "الاهتمامات": "interests",
    "الهوايات": "interests",
    # ZH
    "兴趣": "interests",
    "爱好": "interests",
    "兴趣爱好": "interests",
    # JA
    "趣味": "interests",
    "興味": "interests",
    "関心": "interests",
    # KO
    "관심사": "interests",
    "취미": "interests",
    # HI
    "रुचियां": "interests",
    "शौक": "interests",
    # ID
    "minat": "interests",
    "hobi": "interests",
    # VI
    "sở thích": "interests",
    "đam mê": "interests",
    # TH
    "ความสนใจ": "interests",
    "งานอดิเรก": "interests",
}

# Substring fragments → canonical key for fuzzy fallback
_FUZZY_FRAGMENTS: list[tuple[str, str]] = [
    # EN
    ("summar", "summary"),
    ("profile", "summary"),
    ("objective", "summary"),
    ("about", "summary"),
    ("personal info", "summary"),
    ("contact", "contact"),
    ("communic", "contact"),
    ("details", "contact"),
    ("experi", "experience"),
    ("employ", "experience"),
    ("work", "experience"),
    ("career", "experience"),
    ("educat", "education"),
    ("academ", "education"),
    ("studies", "education"),
    ("qualif", "education"),
    ("skill", "skills"),
    ("competen", "skills"),
    ("abilit", "skills"),
    ("project", "projects"),
    ("portfolio", "projects"),
    ("certif", "certifications"),
    ("licens", "certifications"),
    ("language", "languages"),
    ("linguist", "languages"),
    ("interest", "interests"),
    ("hobbi", "interests"),
    # FR
    ("résumé", "summary"),
    ("profil professionnel", "summary"),
    ("expérience", "experience"),
    ("parcours", "experience"),
    ("formation", "education"),
    ("études", "education"),
    ("compétence", "skills"),
    ("aptitude", "skills"),
    ("projet", "projects"),
    ("diplôme", "certifications"),
    ("langue", "languages"),
    ("loisir", "interests"),
    ("coordonnée", "contact"),
    # DE
    ("zusammenfassung", "summary"),
    ("kurzprofil", "summary"),
    ("erfahrung", "experience"),
    ("beruf", "experience"),
    ("ausbildung", "education"),
    ("bildung", "education"),
    ("studium", "education"),
    ("fähigkeit", "skills"),
    ("kenntnis", "skills"),
    ("kompetenz", "skills"),
    ("projekte", "projects"),
    ("zertifik", "certifications"),
    ("sprach", "languages"),
    ("kontakt", "contact"),
    # ES/PT
    ("experiencia", "experience"),
    ("experiência", "experience"),
    ("educación", "education"),
    ("educação", "education"),
    ("formación", "education"),
    ("formação", "education"),
    ("habilidad", "skills"),
    ("competência", "skills"),
    ("proyecto", "projects"),
    ("idioma", "languages"),
    ("certificacion", "certifications"),
    ("certificação", "certifications"),
    # IT
    ("esperienza", "experience"),
    ("istruzione", "education"),
    ("competenz", "skills"),
    ("progetti", "projects"),
    ("certificazion", "certifications"),
    ("lingu", "languages"),
    # NL
    ("ervaring", "experience"),
    ("opleiding", "education"),
    ("vaardighe", "skills"),
    ("projecten", "projects"),
    # RU
    ("опыт", "experience"),
    ("образован", "education"),
    ("навык", "skills"),
    ("умен", "skills"),
    ("проект", "projects"),
    ("сертификат", "certifications"),
    ("язык", "languages"),
    ("интерес", "interests"),
    ("хобби", "interests"),
    ("резюме", "summary"),
    ("профил", "summary"),
    # PL
    ("doświadczeni", "experience"),
    ("wykształceni", "education"),
    ("umiejętnoś", "skills"),
    ("zainteresowania", "interests"),
    # SV/NO/DA
    ("erfarenhet", "experience"),
    ("utbildning", "education"),
    ("utdanning", "education"),
    ("uddannelse", "education"),
    ("färdighet", "skills"),
    ("ferdighet", "skills"),
    # FI
    ("kokemus", "experience"),
    ("koulutus", "education"),
    ("taido", "skills"),
    ("osaaminen", "skills"),
    # CS/HU/RO
    ("zkušenost", "experience"),
    ("tapasztalat", "experience"),
    ("vzdělán", "education"),
    ("végzettség", "education"),
    ("dovednost", "skills"),
    ("készség", "skills"),
    # AR
    ("الخبر", "experience"),
    ("التعليم", "education"),
    ("المهار", "skills"),
    ("المشاريع", "projects"),
    ("الشهاد", "certifications"),
    ("اللغ", "languages"),
    ("الاهتمام", "interests"),
    ("ملخص", "summary"),
    # ZH
    ("经验", "experience"),
    ("经历", "experience"),
    ("教育", "education"),
    ("学历", "education"),
    ("技能", "skills"),
    ("项目", "projects"),
    ("证书", "certifications"),
    ("语言", "languages"),
    ("兴趣", "interests"),
    ("简介", "summary"),
    # JA
    ("職歴", "experience"),
    ("学歴", "education"),
    ("スキル", "skills"),
    ("プロジェクト", "projects"),
    ("資格", "certifications"),
    ("言語", "languages"),
    ("趣味", "interests"),
    ("概要", "summary"),
    # KO
    ("경력", "experience"),
    ("학력", "education"),
    ("기술", "skills"),
    ("프로젝트", "projects"),
    ("자격증", "certifications"),
    ("언어", "languages"),
    ("취미", "interests"),
    ("요약", "summary"),
    # HI
    ("अनुभव", "experience"),
    ("शिक्षा", "education"),
    ("कौशल", "skills"),
    ("परियोजना", "projects"),
    ("प्रमाणपत्र", "certifications"),
    ("भाषा", "languages"),
    ("रुचि", "interests"),
    ("सारांश", "summary"),
    # ID
    ("pengalaman", "experience"),
    ("pendidikan", "education"),
    ("keahlian", "skills"),
    ("keterampilan", "skills"),
    ("proyek", "projects"),
    ("sertifikas", "certifications"),
    ("ringkasan", "summary"),
    # VI
    ("kinh nghiệm", "experience"),
    ("học vấn", "education"),
    ("kỹ năng", "skills"),
    ("dự án", "projects"),
    ("chứng chỉ", "certifications"),
    ("ngôn ngữ", "languages"),
    ("tóm tắt", "summary"),
    # TH
    ("ประสบการณ์", "experience"),
    ("การศึกษา", "education"),
    ("ทักษะ", "skills"),
    ("โครงการ", "projects"),
    ("ใบรับรอง", "certifications"),
    ("ภาษา", "languages"),
    ("ความสนใจ", "interests"),
    ("สรุป", "summary"),
]
