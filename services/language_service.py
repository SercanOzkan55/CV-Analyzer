"""
Language detection and localized response text.

The analyzer must not silently treat every unknown CV as English. This module
keeps language detection separate from output localization:
- "auto" means detect from the supplied text when possible.
- "neutral" means the text language is unknown or unsupported.
- localized UI/result text currently has audited English and Turkish copy.
- other supported languages safely fall back to English text until translations
  are reviewed.
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    from langdetect import LangDetectException
    from langdetect import detect as _detect_lang

    HAS_LANGDETECT = True
except ImportError:  # pragma: no cover - depends on optional runtime package
    LangDetectException = Exception
    HAS_LANGDETECT = False


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

LOCALIZED_LANGS = {"en", "tr"}
DEFAULT_LANG = "auto"
FALLBACK_LANG = "en"
NEUTRAL_LANG = "neutral"

LANGUAGE_ALIASES = {
    "": DEFAULT_LANG,
    "auto": DEFAULT_LANG,
    "detect": DEFAULT_LANG,
    "detected": DEFAULT_LANG,
    "default": DEFAULT_LANG,
    "browser": DEFAULT_LANG,
    "eng": "en",
    "english": "en",
    "turkish": "tr",
    "turkce": "tr",
    "türkçe": "tr",
    "pt-br": "pt",
    "pt-pt": "pt",
    "zh-cn": "zh",
    "zh-tw": "zh",
    "zh-hans": "zh",
    "zh-hant": "zh",
}

MOJIBAKE_MARKERS = ("Ã", "Ä", "Å", "Ð", "Ñ", "Ø", "Ù", "ã", "ë", "ì", "�")


@dataclass(frozen=True)
class LanguageContext:
    requested: str
    detected: str
    output: str
    supported: bool


def contains_mojibake(text: str) -> bool:
    """Return True when text looks like double-encoded Unicode."""
    return any(marker in text for marker in MOJIBAKE_MARKERS)


def _base_lang(lang: str) -> str:
    normalized = str(lang or "").strip().lower().replace("_", "-")
    normalized = LANGUAGE_ALIASES.get(normalized, normalized)
    if "-" in normalized and normalized not in LANGUAGE_ALIASES:
        normalized = normalized.split("-", 1)[0]
    return LANGUAGE_ALIASES.get(normalized, normalized)


def detect_language(text: str) -> str:
    """Detect the language of text, returning "neutral" when uncertain."""
    if not text or len(text.strip()) < 20:
        return NEUTRAL_LANG

    if not HAS_LANGDETECT:
        return NEUTRAL_LANG

    try:
        sample = text[:3000]
        lang = _base_lang(_detect_lang(sample))
        return lang if lang in SUPPORTED_LANGS else NEUTRAL_LANG
    except (LangDetectException, Exception):
        return NEUTRAL_LANG


def normalize_language(lang: str | None = None, text: str = "") -> str:
    """Normalize an explicit language code or auto-detect from text."""
    requested = _base_lang(lang or DEFAULT_LANG)
    if requested == DEFAULT_LANG:
        return detect_language(text)
    return requested if requested in SUPPORTED_LANGS else NEUTRAL_LANG


def resolve_output_language(lang: str | None = None, text: str = "") -> str:
    """Return a language code with audited localized copy available."""
    normalized = normalize_language(lang, text)
    return normalized if normalized in LOCALIZED_LANGS else FALLBACK_LANG


def build_language_context(lang: str | None = None, text: str = "") -> LanguageContext:
    """Expose language decisions for APIs that need transparent metadata."""
    requested = _base_lang(lang or DEFAULT_LANG)
    detected = detect_language(text) if requested == DEFAULT_LANG else normalize_language(requested)
    output = resolve_output_language(detected)
    return LanguageContext(
        requested=requested,
        detected=detected,
        output=output,
        supported=detected in SUPPORTED_LANGS,
    )


def _localized(mapping: dict[str, str], lang: str | None = None, text: str = "") -> str:
    output_lang = resolve_output_language(lang, text)
    value = mapping.get(output_lang) or mapping.get(FALLBACK_LANG, "")
    if contains_mojibake(value):
        return mapping.get(FALLBACK_LANG, "")
    return value


INTERPRETATION = {
    "high": {
        "en": "Strong Match",
        "tr": "Güçlü Eşleşme",
    },
    "moderate": {
        "en": "Moderate Match",
        "tr": "Orta Eşleşme",
    },
    "low": {
        "en": "Weak Match",
        "tr": "Zayıf Eşleşme",
    },
}


def interpret_score_localized(score: float, lang: str = DEFAULT_LANG) -> str:
    if score > 75:
        key = "high"
    elif score > 50:
        key = "moderate"
    else:
        key = "low"
    return _localized(INTERPRETATION[key], lang)


RISK_LEVELS = {
    "Low Risk": {
        "en": "Low Risk",
        "tr": "Düşük Risk",
    },
    "Medium Risk": {
        "en": "Medium Risk",
        "tr": "Orta Risk",
    },
    "High Risk": {
        "en": "High Risk",
        "tr": "Yüksek Risk",
    },
}


def localize_risk_level(risk_level: str, lang: str = DEFAULT_LANG) -> str:
    mapping = RISK_LEVELS.get(risk_level, RISK_LEVELS["High Risk"])
    return _localized(mapping, lang)


RECOMMENDATIONS = {
    "semantic_low": {
        "en": "Your CV structure does not align well with this job description. Rewrite your experience section using similar terminology.",
        "tr": "CV yapınız bu iş tanımıyla iyi uyuşmuyor. Deneyim bölümünüzü benzer terimler kullanarak yeniden yazın.",
    },
    "add_skill": {
        "en": "Add measurable project experience demonstrating {}.",
        "tr": "{} becerisini gösteren ölçülebilir proje deneyimi ekleyin.",
    },
    "keyword_low": {
        "en": "Improve keyword matching by explicitly mentioning required technologies.",
        "tr": "Gerekli teknolojileri açıkça belirterek anahtar kelime eşleşmesini iyileştirin.",
    },
    "all_good": {
        "en": "Your CV is generally aligned. Focus on adding quantified achievements.",
        "tr": "CV'niz genel olarak uyumlu. Sayısal başarılar eklemeye odaklanın.",
    },
}


def get_recommendation(
    key: str,
    lang: str = DEFAULT_LANG,
    skill: str = "",
    text: str = "",
) -> str:
    template = RECOMMENDATIONS.get(key, {})
    value = _localized(template, lang, text)
    if skill and "{}" in value:
        value = value.format(skill)
    return value


ATS_SUGGESTIONS = {
    "keyword_low": {
        "en": "Incorporate keywords from the job posting naturally into your CV.",
        "tr": "İş ilanındaki anahtar kelimeleri CV'nize doğal biçimde ekleyin.",
    },
    "action_low": {
        "en": "Use strong action verbs and measurable achievements for each role.",
        "tr": "Her görev için ölçülebilir başarılara ve güçlü eylem fiillerine yer verin.",
    },
    "sections_missing": {
        "en": "Add clear section headers such as Education, Experience, Skills, and Contact.",
        "tr": "Education, Experience, Skills ve Contact gibi net bölüm başlıkları ekleyin.",
    },
    "contact_missing": {
        "en": "Add your email and phone number, plus a relevant professional profile if available, at the top of your CV.",
        "tr": "CV üst kısmına e-posta, telefon ve varsa ilgili profesyonel profil bağlantınızı ekleyin.",
    },
    "bullets_low": {
        "en": "Use bullet points for achievements; avoid long paragraphs.",
        "tr": "Kazanımları madde listesi ile yazın; uzun paragraflardan kaçının.",
    },
    "length_bad": {
        "en": "Keep your CV concise for the role and region; avoid unnecessary repeated pages.",
        "tr": "CV'nizi rol ve bölge beklentisine göre öz tutun; gereksiz tekrar eden sayfalardan kaçının.",
    },
    "quantify_achievements": {
        "en": "Quantify your achievements with numbers, percentages, time saved, quality improvements, or business impact.",
        "tr": "Başarılarınızı sayı, yüzde, kazanılan süre, kalite iyileşmesi veya iş etkisiyle ölçülendirin.",
    },
    "formatting_inconsistent": {
        "en": "Use consistent formatting throughout: date style, bullet style, spacing, and section order.",
        "tr": "Tarih stili, madde işaretleri, boşluklar ve bölüm sırası boyunca tutarlı biçimlendirme kullanın.",
    },
}


def get_ats_suggestion(key: str, lang: str = DEFAULT_LANG, text: str = "") -> str:
    template = ATS_SUGGESTIONS.get(key, {})
    return _localized(template, lang, text)
