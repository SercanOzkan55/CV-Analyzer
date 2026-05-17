import os
import re
import json
import hashlib
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()


MAX_INPUT_CHARS = int(os.getenv("REWRITE_MAX_INPUT_CHARS", "8000") or "8000")
MAX_OUTPUT_CHARS = int(os.getenv("REWRITE_MAX_OUTPUT_CHARS", "4000") or "4000")
COVER_LETTER_CACHE_LIMIT = int(os.getenv("COVER_LETTER_CACHE_LIMIT", "100") or "100")
_COVER_LETTER_CACHE: dict[str, str] = {}
LINKEDIN_ALLOWED_MODES = {"junior", "senior", "manager", "tech", "academic"}
REWRITE_ALLOWED_MODES = {
    "junior",
    "senior",
    "manager",
    "academic",
    "tech",
    "simple",
    "ats_strict",
    "short",
    "one_page",
}


def _guard_text(value: str, max_chars: int, field_name: str) -> str:
    if not isinstance(value, str):
        value = str(value or "")
    value = value.strip()
    if len(value) > max_chars:
        # Hard truncate to avoid runaway prompts; caller can surface
        # a warning in the UI if needed.
        value = value[:max_chars]
    if not value:
        raise ValueError(f"{field_name} cannot be empty")
    return value


def _select_provider() -> str:
    """Return the logical provider name.

    For now this supports a built-in mock provider for local/dev. Future
    implementations can route to OpenAI, Anthropic or others without
    changing call sites.
    """

    provider = os.getenv("REWRITE_PROVIDER", "mock").strip().lower()
    if not provider:
        provider = "mock"
    return provider


def _normalize_mode(mode: str) -> str:
    candidate = str(mode or "senior").strip().lower()
    if candidate not in LINKEDIN_ALLOWED_MODES:
        candidate = "senior"
    return candidate


def _normalize_rewrite_mode(mode: str) -> str:
    candidate = str(mode or "senior").strip().lower()
    if candidate not in REWRITE_ALLOWED_MODES:
        candidate = "senior"
    return candidate


def _extract_keywords(text: str, max_items: int = 12) -> List[str]:
    source = str(text or "").lower()
    tokens = re.findall(r"[\w+#.\-]{3,}", source, flags=re.UNICODE)
    stop = {
        "and", "with", "for", "the", "this", "that", "are", "from", "you",
        "your", "job", "role", "cv", "experience", "work", "using", "have",
        "will", "can", "our", "their", "skills", "years", "plus",
        "summary", "name", "highlights", "highlight",
        "computer", "engineering", "student", "junior", "senior", "developer",
        "engineer", "position",
        "bir", "ve", "ile", "için", "olan", "gibi", "iş", "cv", "deneyim",
        "beceri", "yıl", "aday", "pozisyon", "aranan", "nitelikler",
        "bilgisayar", "mühendisliği", "öğrencisiyim", "geliştirme", "gerçek",
        "muhendisligi", "ogrencisiyim", "gelistirme", "gercek",
    }
    seen = set()
    out = []
    for token in tokens:
        token = token.strip(".,;:()[]{}")
        if token in stop:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
        if len(out) >= max_items:
            break
    return out


def _mock_generate(prompt: str, max_tokens: int = 512) -> str:
    # Deterministic and safe stub for tests and local dev.
    snippet = prompt.strip().replace("\n", " ")
    if len(snippet) > MAX_OUTPUT_CHARS:
        snippet = snippet[:MAX_OUTPUT_CHARS]
    return f"[mock-rewrite] {snippet[: max_tokens * 4]}"


def _language_name(lang: str) -> str:
    code = str(lang or "en").strip().lower()
    names = {
        "en": "English",
        "tr": "Turkish",
        "fr": "French",
        "de": "German",
        "es": "Spanish",
        "ar": "Arabic",
        "pt": "Portuguese",
        "it": "Italian",
        "nl": "Dutch",
        "ru": "Russian",
        "ja": "Japanese",
        "ko": "Korean",
        "zh": "Chinese",
    }
    return names.get(code, "English")


def _infer_role(job_description: str) -> str:
    text = str(job_description or "").strip()
    patterns = [
        r"\b((?:junior|senior|lead|staff|principal)?\s*(?:software|backend|frontend|full stack|data|ml|ai|devops|mobile)?\s*(?:developer|engineer|analyst|specialist|manager|intern))\b",
        r"\b((?:junior|senior|kıdemli|lider)?\s*(?:backend|frontend|full stack|yazılım|veri|mobil)?\s*(?:geliştirici|mühendis|uzman|stajyer))\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(1).strip()

    for line in text.splitlines():
        candidate = re.sub(r"[*#:_]+", " ", line).strip()
        candidate = re.split(r"[.!?]", candidate, maxsplit=1)[0]
        candidate = re.sub(r"\b(job description|iş tanımı|position|role|pozisyonu?)\b", "", candidate, flags=re.I).strip(" -|")
        if 4 <= len(candidate) <= 90:
            return candidate
    return "the role"


def _cover_letter_skill_text(cv_text: str, job_description: str, lang: str) -> str:
    cv_keywords = _extract_keywords(cv_text, max_items=12)
    job_keywords = set(_extract_keywords(job_description, max_items=16))
    keywords = [kw for kw in cv_keywords if kw in job_keywords]
    for keyword in cv_keywords:
        if keyword not in keywords:
            keywords.append(keyword)
        if len(keywords) >= 5:
            break
    if not keywords:
        return "relevant skills" if lang != "tr" else "ilgili yetkinlikler"
    if lang == "tr":
        return ", ".join(keywords[:4])
    return ", ".join(keywords[:4])


def _mock_cover_letter(
    cv_text: str,
    job_description: str,
    lang: str,
    tone: str,
    company_name: str,
    mode: str,
) -> str:
    """Local deterministic cover letter fallback that never returns the prompt."""
    code = str(lang or "en").strip().lower()
    role = _infer_role(job_description)
    company = str(company_name or "").strip()
    company_target = company or ("your team" if code != "tr" else "ekibiniz")
    skill_text = _cover_letter_skill_text(cv_text, job_description, code)

    if code == "tr":
        role_text = role if role != "the role" else "bu pozisyon"
        return (
            "Sayın İşe Alım Ekibi,\n\n"
            f"{company_target} bünyesindeki {role_text} için başvurmaktan memnuniyet duyuyorum. "
            f"CV'mde öne çıkan {skill_text} deneyimim ve öğrenmeye açık çalışma tarzımın bu pozisyonun beklentileriyle uyumlu olduğuna inanıyorum.\n\n"
            "Teknik konulara analitik yaklaşan, sorumluluk almaktan çekinmeyen ve ekip içinde net iletişime önem veren bir adayım. "
            "İş tanımında yer alan gereksinimleri dikkatle inceledim; mevcut deneyimimi bu ihtiyaçlara hızlıca uyarlayarak değer üretebileceğime inanıyorum.\n\n"
            "Bu fırsatı daha detaylı konuşmaktan mutluluk duyarım. Zamanınız ve değerlendirmeniz için teşekkür ederim.\n\n"
            "Saygılarımla,"
        )

    if code == "de":
        return (
            "Sehr geehrtes Recruiting-Team,\n\n"
            f"ich bewerbe mich mit großem Interesse auf die Position {role} bei {company_target}. "
            f"Meine Erfahrung mit {skill_text} sowie meine strukturierte Arbeitsweise passen gut zu den Anforderungen der Stelle.\n\n"
            "Ich arbeite analytisch, lerne schnell und übernehme Verantwortung für saubere, nachvollziehbare Ergebnisse. "
            "Gerne würde ich meine Fähigkeiten in Ihr Team einbringen und gemeinsam nachhaltige Lösungen entwickeln.\n\n"
            "Vielen Dank für Ihre Zeit und die Prüfung meiner Bewerbung.\n\n"
            "Mit freundlichen Grüßen,"
        )

    if code == "fr":
        return (
            "Madame, Monsieur,\n\n"
            f"Je souhaite vous présenter ma candidature pour le poste {role} au sein de {company_target}. "
            f"Mon expérience autour de {skill_text} et ma capacité d'apprentissage correspondent aux attentes du poste.\n\n"
            "Je suis une personne rigoureuse, curieuse et orientée résolution de problèmes. "
            "Je serais heureux de mettre mes compétences au service de votre équipe.\n\n"
            "Je vous remercie pour votre temps et votre considération.\n\n"
            "Cordialement,"
        )

    if code == "es":
        return (
            "Estimado equipo de selección,\n\n"
            f"Me gustaría postularme para el puesto de {role} en {company_target}. "
            f"Mi experiencia en {skill_text} y mi forma de trabajo orientada al aprendizaje encajan con las necesidades del puesto.\n\n"
            "Soy una persona analítica, responsable y enfocada en aportar resultados claros. "
            "Me entusiasma la posibilidad de contribuir al equipo y seguir creciendo profesionalmente.\n\n"
            "Gracias por su tiempo y consideración.\n\n"
            "Atentamente,"
        )

    return (
        "Dear Hiring Team,\n\n"
        f"I am excited to apply for the {role} position at {company_target}. "
        f"My background in {skill_text}, together with a practical and {tone} working style, aligns well with the needs described in the job posting.\n\n"
        "I approach technical work with curiosity, ownership, and clear communication. "
        f"As a {mode}-level candidate, I am eager to contribute quickly, learn from the team, and help deliver reliable results for the role.\n\n"
        "Thank you for your time and consideration. I would welcome the opportunity to discuss how my experience can support your team.\n\n"
        "Sincerely,"
    )


def _clean_cover_letter_output(raw: str) -> str:
    text = str(raw or "").strip()
    text = re.sub(r"^\[mock-rewrite\]\s*", "", text, flags=re.I).strip()

    prompt_echo_markers = (
        "Draft a tailored cover letter",
        "Write a tailored cover letter",
        "Rewrite mode:",
        "Job description:",
        "Candidate context:",
        "Job context:",
        "Rules:",
        "CV:",
    )
    if sum(1 for marker in prompt_echo_markers if marker.lower() in text.lower()) >= 2:
        return ""

    text = re.sub(r"^(cover letter|ön yazı|motivation letter)\s*[:\-]\s*", "", text, flags=re.I).strip()
    return text[:MAX_OUTPUT_CHARS].strip()


def _truncate_words(text: str, max_chars: int) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= max_chars:
        return value
    cut = value[:max_chars].rsplit(" ", 1)[0].strip()
    return cut or value[:max_chars].strip()


def _flatten_text_items(value, limit: int = 8) -> list[str]:
    items: list[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                parts = []
                for key in ("title", "company", "degree", "school", "name", "description"):
                    part = str(item.get(key) or "").strip()
                    if part:
                        parts.append(part)
                bullets = item.get("bullets") or item.get("highlights") or []
                if isinstance(bullets, list):
                    parts.extend(str(b).strip() for b in bullets[:2] if str(b).strip())
                text = " - ".join(parts)
            else:
                text = str(item or "").strip()
            if text:
                items.append(_truncate_words(text, 260))
            if len(items) >= limit:
                break
    elif value:
        items.append(_truncate_words(str(value), 260))
    return items


def _compact_job_context(job_description: str) -> str:
    text = _guard_text(job_description, MAX_INPUT_CHARS, "job_description")
    role = _infer_role(text)
    keywords = _extract_keywords(text, max_items=14)
    lines = []
    for raw_line in re.split(r"[\r\n]+", text):
        line = re.sub(r"\s+", " ", raw_line).strip(" -\t")
        if not line:
            continue
        lines.append(_truncate_words(line, 220))
        if len(lines) >= 8:
            break
    return "\n".join(
        part for part in (
            f"Target role: {role}",
            "Important job keywords: " + ", ".join(keywords[:12]) if keywords else "",
            "Relevant job context:\n- " + "\n- ".join(lines[:6]) if lines else "",
        )
        if part
    )[:1400]


def _compact_builder_context(builder_payload: dict, fallback_text: str = "") -> str:
    data = builder_payload if isinstance(builder_payload, dict) else {}
    lines: list[str] = []
    for key, label in (("full_name", "Name"), ("summary", "Summary"), ("headline", "Headline")):
        value = str(data.get(key) or "").strip()
        if value:
            lines.append(f"{label}: {_truncate_words(value, 420)}")

    skills = data.get("skills") or []
    if isinstance(skills, list) and skills:
        lines.append("Skills: " + ", ".join(str(s).strip() for s in skills if str(s).strip())[:500])

    categorized = data.get("skills_categorized") or {}
    if isinstance(categorized, dict) and not skills:
        flat = []
        for values in categorized.values():
            if isinstance(values, list):
                flat.extend(str(v).strip() for v in values if str(v).strip())
        if flat:
            lines.append("Skills: " + ", ".join(flat[:18])[:500])

    experiences = _flatten_text_items(data.get("experiences"), limit=4)
    if experiences:
        lines.append("Experience highlights:\n- " + "\n- ".join(experiences))

    projects = _flatten_text_items(data.get("projects"), limit=3)
    if projects:
        lines.append("Project highlights:\n- " + "\n- ".join(projects))

    education = _flatten_text_items(data.get("education"), limit=2)
    if education:
        lines.append("Education:\n- " + "\n- ".join(education))

    compact = "\n".join(lines).strip()
    if compact:
        return compact[:1900]
    return _truncate_words(fallback_text, 1900)


def _cover_letter_cache_key(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _cover_letter_cache_get(payload: dict) -> str | None:
    return _COVER_LETTER_CACHE.get(_cover_letter_cache_key(payload))


def _cover_letter_cache_set(payload: dict, value: str) -> None:
    if COVER_LETTER_CACHE_LIMIT <= 0:
        return
    if len(_COVER_LETTER_CACHE) >= COVER_LETTER_CACHE_LIMIT:
        try:
            _COVER_LETTER_CACHE.pop(next(iter(_COVER_LETTER_CACHE)))
        except Exception:
            _COVER_LETTER_CACHE.clear()
    _COVER_LETTER_CACHE[_cover_letter_cache_key(payload)] = value


def _generate(prompt: str, max_tokens: int = 512) -> str:
    provider = _select_provider()
    if provider == "mock":
        return _mock_generate(prompt, max_tokens=max_tokens)

    api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        return _mock_generate(prompt, max_tokens=max_tokens)

    try:
        from openai import OpenAI
    except Exception:
        return _mock_generate(prompt, max_tokens=max_tokens)

    model = str(os.getenv("REWRITE_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
    base_url = os.getenv("OPENAI_API_BASE")
    timeout_seconds = float(os.getenv("REWRITE_TIMEOUT_SECONDS", "25") or "25")
    client = OpenAI(api_key=api_key, base_url=base_url)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=max_tokens,
            timeout=timeout_seconds,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        raise RuntimeError(f"AI provider error: {exc}")


def ai_rewrite_available() -> bool:
    provider = _select_provider()
    if provider == "mock":
        return False
    if provider in {"openai", "openai-compatible"}:
        return bool(str(os.getenv("OPENAI_API_KEY", "")).strip())
    return False


def ai_rewrite_cv(
    cv_text: str,
    job_description: str = "",
    lang: str = "en",
    tone: str = "professional",
    mode: str = "senior",
) -> str:
    cv_text = _guard_text(cv_text, MAX_INPUT_CHARS, "cv_text")
    job_description = job_description or ""
    rewrite_mode = _normalize_rewrite_mode(mode)

    prompt = (
        f"Rewrite the following CV in a {tone} tone, optimized for ATS and the target job.\n"
        f"Rewrite mode: {rewrite_mode}.\n"
        f"Language: {lang}.\n"
        f"Job description (optional): {job_description}\n\n"
        f"CV:\n{cv_text}\n"
    )
    return _generate(prompt)


def rewrite_cv_for_ats(
    cv_text: str,
    job_description: str = "",
    lang: str = "en",
    tone: str = "professional",
    mode: str = "ats_strict",
) -> str:
    cv_text = _guard_text(cv_text, MAX_INPUT_CHARS, "cv_text")
    job_description = job_description or ""
    rewrite_mode = _normalize_rewrite_mode(mode)

    prompt = (
        f"Rewrite the following CV to improve ATS compatibility and professional wording in a {tone} tone.\n"
        f"Rewrite mode: {rewrite_mode}.\n"
        f"Language: {lang}.\n"
        "Rules:\n"
        "1. Preserve all factual details from the source CV.\n"
        "2. Do not invent employers, dates, metrics, certifications, degrees, or skills.\n"
        "3. Keep only ATS-relevant sections such as contact, summary, experience, education, skills, certifications, projects, and languages.\n"
        "4. Prefer standard section headings and concise bullet points.\n"
        "5. Remove clearly irrelevant sections such as references, hobbies, marital status, date of birth, and photo mentions.\n"
        f"6. Use job-description keywords only when they are already supported by the CV or clearly implied by the source text.\n"
        "7. CRITICAL: If the CV text appears to be a corrupted multi-column layout where text from the left and right columns are mixed on the same line (e.g. 'SQL PROJECT NAME' or 'HTML / CSS FARM GAME'), you MUST disentangle them and reconstruct the sections logically into a single-column format.\n"
        "8. Rewrite the professional summary into 2-4 concise lines that state role/level, core strengths, and supported target direction.\n"
        "9. Rewrite weak experience and project bullets using strong, truthful action verbs such as contributed, developed, implemented, designed, optimized, analyzed, collaborated, and maintained.\n"
        "10. For each experience/project bullet, prefer action + scope/tool + result/purpose. If no measurable metric exists in the source, describe the purpose or contribution without inventing numbers.\n"
        "11. Fix grammar, awkward phrasing, broken line wraps, repeated words, and sentence flow across all sections.\n"
        "12. Keep the CV in the same language as the input/requested language. Return only the rewritten CV text, no commentary or markdown fences.\n"
        f"Job description (optional): {job_description}\n\n"
        f"CV:\n{cv_text}\n"
    )
    return _generate(prompt, max_tokens=1024)


def rewrite_bullets(
    bullets: List[str],
    job_description: str = "",
    lang: str = "en",
    tone: str = "professional",
) -> List[str]:
    if not isinstance(bullets, list) or not bullets:
        raise ValueError("bullets must be a non-empty list")
    joined = "\n".join(str(b).strip() for b in bullets if str(b).strip())
    joined = _guard_text(joined, MAX_INPUT_CHARS, "bullets")
    job_description = job_description or ""

    prompt = (
        f"Rewrite the following CV bullet points in a {tone} tone, using strong action verbs and quantification where possible.\n"
        f"Language: {lang}.\n"
        f"Job description (optional): {job_description}\n\n"
        f"Bullets:\n{joined}\n"
    )
    raw = _generate(prompt)
    # In mock mode we simply return a single rewritten text; in real
    # providers this can be parsed into separate bullets.
    return [raw]


def rewrite_cover_letter(
    cv_text: str,
    job_description: str,
    lang: str = "en",
    tone: str = "professional",
    company_name: str = "",
    mode: str = "senior",
    low_token: bool = True,
) -> str:
    cv_text = _guard_text(cv_text, MAX_INPUT_CHARS, "cv_text")
    job_description = _guard_text(job_description, MAX_INPUT_CHARS, "job_description")
    rewrite_mode = _normalize_rewrite_mode(mode)
    company_name = str(company_name or "").strip()
    lang_name = _language_name(lang)
    cache_payload = {
        "cv": cv_text,
        "jd": job_description,
        "lang": lang,
        "tone": tone,
        "company": company_name,
        "mode": rewrite_mode,
        "low_token": bool(low_token),
    }
    cached = _cover_letter_cache_get(cache_payload)
    if cached:
        return cached

    if low_token:
        candidate_context = _truncate_words(cv_text, 1900)
        job_context = _compact_job_context(job_description)
        prompt = (
            "Write a tailored cover letter from compact context.\n"
            f"Language: {lang_name}. Tone: {tone}. Candidate level/mode: {rewrite_mode}.\n"
            f"Company: {company_name or 'the company'}.\n"
            "Rules:\n"
            "- Use only facts supported by the candidate context.\n"
            "- Preserve the target role and align with the job context.\n"
            "- Do not invent employers, dates, degrees, metrics, or skills.\n"
            "- 3 concise paragraphs, 150-220 words, no headings, no markdown, no metadata.\n\n"
            f"Candidate context:\n{candidate_context}\n\n"
            f"Job context:\n{job_context}\n"
        )
        raw = _generate(prompt, max_tokens=520)
    else:
        company_hint = f"Company: {company_name}.\n" if company_name else ""
        prompt = (
            f"Draft a tailored cover letter in a {tone} tone based on the CV and job description.\n"
            f"Rewrite mode: {rewrite_mode}.\n"
            f"Language: {lang_name}.\n"
            "Return only the finished cover letter body. Do not include labels, analysis notes, markdown fences, prompt text, or metadata.\n\n"
            f"{company_hint}"
            f"Job description:\n{job_description}\n\n"
            f"CV:\n{cv_text}\n"
        )
        raw = _generate(prompt, max_tokens=900)
    cleaned = _clean_cover_letter_output(raw)
    if cleaned:
        _cover_letter_cache_set(cache_payload, cleaned)
        return cleaned
    fallback = _mock_cover_letter(
        cv_text=cv_text,
        job_description=job_description,
        lang=lang,
        tone=tone,
        company_name=company_name,
        mode=rewrite_mode,
    )
    _cover_letter_cache_set(cache_payload, fallback)
    return fallback


def rewrite_cover_letter_from_builder_payload(
    builder_payload: dict,
    job_description: str,
    company_name: str = "",
    lang: str = "en",
    tone: str = "professional",
    mode: str = "senior",
    low_token: bool = True,
) -> str:
    if not isinstance(builder_payload, dict):
        raise ValueError("builder_payload must be a dictionary")

    name = str(builder_payload.get("full_name") or "").strip()
    summary = str(builder_payload.get("summary") or "").strip()
    skills = builder_payload.get("skills") or []
    experiences = builder_payload.get("experiences") or []

    lines = []
    if name:
        lines.append(f"Name: {name}")
    if summary:
        lines.append(f"Summary: {summary}")
    if skills:
        lines.append("Skills: " + ", ".join(str(s).strip() for s in skills if str(s).strip())[:600])

    if isinstance(experiences, list) and experiences:
        lines.append("Experience Highlights:")
        for exp in experiences[:4]:
            if isinstance(exp, dict):
                title = str(exp.get("title") or "").strip()
                company = str(exp.get("company") or "").strip()
                bullets = exp.get("bullets") or []
                head = " - ".join(part for part in (title, company) if part)
                if head:
                    lines.append(f"- {head}")
                for bullet in bullets[:2]:
                    text = str(bullet or "").strip()
                    if text:
                        lines.append(f"  • {text}")

    synthesized_cv = "\n".join(lines).strip()
    if low_token:
        synthesized_cv = _compact_builder_context(builder_payload, synthesized_cv)
    return rewrite_cover_letter(
        cv_text=synthesized_cv or json.dumps(builder_payload)[:MAX_INPUT_CHARS],
        job_description=job_description,
        lang=lang,
        tone=tone,
        company_name=company_name,
        mode=mode,
        low_token=low_token,
    )


def optimize_linkedin_profile(
    cv_text: str,
    target_role: str = "",
    lang: str = "en",
    mode: str = "senior",
    current_headline: str = "",
) -> dict:
    cv_text = _guard_text(cv_text, MAX_INPUT_CHARS, "cv_text")
    target_role = _guard_text(target_role or "Generalist", 120, "target_role")
    normalized_mode = _normalize_mode(mode)
    current_headline = str(current_headline or "").strip()

    mode_guidance = {
        "junior": "entry-level, growth mindset, coachable tone",
        "senior": "impact-oriented, ownership, delivery",
        "manager": "leadership, team outcomes, business alignment",
        "tech": "deep technical depth, architecture, systems",
        "academic": "research rigor, publications, analytical depth",
    }

    prompt = (
        "Create a concise LinkedIn optimization pack in JSON. "
        "Return keys: headline, about, top_skills (array). "
        f"Language: {lang}. Target role: {target_role}. "
        f"Profile mode: {normalized_mode} ({mode_guidance.get(normalized_mode, '')}). "
        f"Current headline: {current_headline}. "
        f"CV:\n{cv_text}"
    )

    provider = _select_provider()
    if provider == "mock":
        kws = _extract_keywords(cv_text + " " + target_role, max_items=10)
        kw3 = " • ".join(kws[:3])
        kw6 = ", ".join(kws[:6])

        mock_headline = {
            "junior": f"Aspiring {target_role} | Eager Learner | {kw3}",
            "senior": f"Senior {target_role} | {kw3} | Driving Impact at Scale",
            "manager": f"{target_role} Leader | Building High-Performance Teams | {kw3}",
            "tech": f"Staff/Principal {target_role} | {kw3} | System Design & Architecture",
            "academic": f"{target_role} Researcher | {kw3} | Publications & Analysis",
        }
        mock_about = {
            "junior": (
                f"Motivated early-career professional pursuing {target_role} opportunities. "
                f"Currently developing expertise in {kw6}. "
                "Passionate about learning, open to mentorship, and eager to contribute to innovative teams. "
                "Strong academic foundation with hands-on project experience."
            ),
            "senior": (
                f"Results-driven {target_role} with a track record of delivering high-impact solutions. "
                f"Deep expertise in {kw6}. "
                "Known for taking ownership, mentoring junior team members, and driving projects from concept to production. "
                "Focused on measurable business outcomes and technical excellence."
            ),
            "manager": (
                f"Engineering leader with experience managing cross-functional teams in the {target_role} domain. "
                f"Strategic focus areas: {kw6}. "
                "Proven ability to align technical execution with business objectives, scale teams, "
                "and foster a culture of accountability and continuous improvement."
            ),
            "tech": (
                f"Hands-on technologist specializing in {target_role} with deep systems expertise. "
                f"Core technical stack: {kw6}. "
                "Passionate about distributed systems, performance optimization, and building robust architectures. "
                "Contributor to open-source projects and technical community."
            ),
            "academic": (
                f"Research-oriented professional in the {target_role} space with analytical rigor. "
                f"Research interests and expertise: {kw6}. "
                "Published author with experience in data-driven methodologies, peer-reviewed research, "
                "and bridging the gap between academic insights and industry applications."
            ),
        }
        mock_bullets = {
            "junior": [
                f"Completed coursework and projects in {kws[0] if kws else 'relevant technologies'}, gaining practical skills.",
                f"Collaborated on team projects involving {kws[1] if len(kws) > 1 else 'modern tools'} with a focus on learning best practices.",
            ],
            "senior": [
                f"Led end-to-end delivery of {kws[0] if kws else 'key'} initiatives, achieving 30% efficiency gains.",
                f"Mentored 5+ engineers and established {kws[1] if len(kws) > 1 else 'engineering'} best practices across the team.",
            ],
            "manager": [
                f"Managed a team of 8-12 engineers delivering {kws[0] if kws else 'critical'} platform features on schedule.",
                f"Defined technical roadmap and OKRs for {kws[1] if len(kws) > 1 else 'product'} initiatives, aligning with company strategy.",
            ],
            "tech": [
                f"Architected scalable {kws[0] if kws else 'distributed'} systems handling 10K+ requests/sec with 99.9% uptime.",
                f"Deep-dived into {kws[1] if len(kws) > 1 else 'infrastructure'} performance, reducing latency by 40% through systematic optimization.",
            ],
            "academic": [
                f"Published peer-reviewed research on {kws[0] if kws else 'novel'} methodologies in top-tier conferences.",
                f"Conducted rigorous quantitative analysis using {kws[1] if len(kws) > 1 else 'statistical'} frameworks to validate hypotheses.",
            ],
        }

        headline = mock_headline.get(normalized_mode, mock_headline["senior"])
        about = mock_about.get(normalized_mode, mock_about["senior"])
        experience_rewrite = mock_bullets.get(normalized_mode, mock_bullets["senior"])

        return {
            "headline": headline[:220],
            "linkedin_summary": headline[:220],
            "about": about[:1400],
            "experience_rewrite": experience_rewrite,
            "top_skills": kws[:12],
            "mode": normalized_mode,
        }

    raw = _generate(prompt, max_tokens=900)
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("invalid response")
    except Exception:
        kws = _extract_keywords(raw or cv_text, max_items=10)
        parsed = {
            "headline": (current_headline or f"{target_role} | {normalized_mode.title()}")[:220],
            "about": str(raw or "")[:1400],
            "top_skills": kws,
        }

    parsed["headline"] = str(parsed.get("headline", "")).strip()[:220]
    parsed["linkedin_summary"] = str(parsed.get("linkedin_summary") or parsed.get("headline") or "").strip()[:220]
    parsed["about"] = str(parsed.get("about", "")).strip()[:1400]
    experience_rewrite = parsed.get("experience_rewrite")
    if not isinstance(experience_rewrite, list):
        experience_rewrite = []
    parsed["experience_rewrite"] = [str(item).strip() for item in experience_rewrite if str(item).strip()][:8]
    skills = parsed.get("top_skills")
    if not isinstance(skills, list):
        skills = _extract_keywords(cv_text + " " + target_role, max_items=12)
    parsed["top_skills"] = [str(s).strip() for s in skills if str(s).strip()][:12]
    parsed["mode"] = normalized_mode
    return parsed


def _extract_json_object(raw: str) -> dict:
    text = str(raw or "").strip()
    if not text:
        raise ValueError("empty ai response")

    candidates = [text]
    if text.startswith("```"):
        no_fence = re.sub(r"^```(?:json)?\s*", "", text)
        no_fence = re.sub(r"\s*```$", "", no_fence)
        candidates.append(no_fence.strip())

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidates.append(match.group(0).strip())

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    raise ValueError("invalid ai json response")


def _merge_reviewed_payload(original: dict, reviewed: dict) -> dict:
    merged = dict(original or {})
    critical_keys = {
        "summary",
        "experiences",
        "education",
        "skills",
        "skills_categorized",
        "certifications",
        "projects",
        "languages",
        "full_name",
        "email",
        "phone",
        "location",
        "linkedin",
    }

    for key, value in (reviewed or {}).items():
        if key in critical_keys and value in (None, "", [], {}):
            continue
        merged[key] = value

    for key in critical_keys:
        if merged.get(key) in (None, "", [], {}):
            fallback = (original or {}).get(key)
            if fallback not in (None, "", [], {}):
                merged[key] = fallback

    return merged


def ai_review_cv_payload(payload: dict, job_description: str = "", lang: str = "en") -> dict:
    """Final ATS review pass that fixes gaps without deleting valid data.

    This is intentionally conservative: if AI is unavailable or response is invalid,
    original payload is returned unchanged.
    """
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dictionary")

    source_payload = dict(payload)
    if _select_provider() == "mock":
        return source_payload

    api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        return source_payload

    try:
        from openai import OpenAI
    except Exception:
        return source_payload

    model = str(os.getenv("AI_FINAL_REVIEW_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
    timeout_seconds = float(os.getenv("AI_FINAL_REVIEW_TIMEOUT_SECONDS", "20") or "20")
    client = OpenAI(api_key=api_key)

    safe_payload = json.dumps(source_payload, ensure_ascii=False)
    safe_payload = safe_payload[: MAX_INPUT_CHARS * 2]
    safe_jd = str(job_description or "")[: MAX_INPUT_CHARS]

    prompt = (
        "You are an ATS CV final reviewer. Review the JSON CV payload and fix only missing/format issues.\n"
        "Rules:\n"
        "- Keep all valid information.\n"
        "- Do NOT remove experience entries.\n"
        "- Do NOT remove projects.\n"
        "- Do NOT remove education, GPA, links, dates, job titles, or certifications.\n"
        "- Do NOT invent fake employers, dates, metrics, schools, or certificates.\n"
        "- If skills section is missing, infer skills from available content and add them.\n"
        "- If summary is missing, generate a short ATS-safe summary from existing facts.\n"
        "- Preserve output schema and return only valid JSON object.\n"
        f"Language: {lang}.\n"
        f"Job description (optional): {safe_jd}\n\n"
        f"CV Payload JSON:\n{safe_payload}\n"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2500,
            timeout=timeout_seconds,
        )
        content = (response.choices[0].message.content or "").strip()
        reviewed_payload = _extract_json_object(content)
        return _merge_reviewed_payload(source_payload, reviewed_payload)
    except Exception:
        return source_payload


def suggest_summaries(
    summary: str,
    job_description: str = "",
    lang: str = "en",
    count: int = 3,
) -> List[str]:
    """Generate *count* alternative professional summaries.

    Returns a list of rewritten summary strings (mock or real AI).
    """
    summary = _guard_text(summary, MAX_INPUT_CHARS, "summary")
    job_description = (job_description or "").strip()

    provider = _select_provider()
    if provider == "mock":
        return _mock_suggest_summaries(summary, job_description, lang, count)

    api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        return _mock_suggest_summaries(summary, job_description, lang, count)

    try:
        from openai import OpenAI
    except Exception:
        return _mock_suggest_summaries(summary, job_description, lang, count)

    model = str(os.getenv("AI_SUGGEST_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
    timeout_seconds = float(os.getenv("AI_SUGGEST_TIMEOUT_SECONDS", "15") or "15")
    client = OpenAI(api_key=api_key)

    lang_map = {"en": "English", "tr": "Turkish", "de": "German", "fr": "French", "es": "Spanish", "ar": "Arabic"}
    lang_name = lang_map.get(lang, "English")
    jd_hint = f"\nTarget job description:\n{job_description[:2000]}" if job_description else ""

    prompt = (
        f"You are an expert CV writer. Rewrite the following professional summary in {count} different styles.\n"
        f"Language: {lang_name}.\n"
        f"Original summary:\n{summary}\n"
        f"{jd_hint}\n\n"
        f"Return a JSON array with exactly {count} strings — each a distinct rewritten summary (2-3 sentences).\n"
        "Style variations: 1) concise & impactful, 2) detailed & technical, 3) leadership & results-oriented.\n"
        "Do NOT invent facts. Rephrase and enhance the original content only.\n"
        "Return ONLY the JSON array, no markdown fences."
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1200,
            timeout=timeout_seconds,
        )
        content = (resp.choices[0].message.content or "").strip()
        parsed = json.loads(content)
        if isinstance(parsed, list) and len(parsed) >= 1:
            return [str(s).strip() for s in parsed[:count] if str(s).strip()]
    except Exception:
        pass

    return _mock_suggest_summaries(summary, job_description, lang, count)


def _mock_suggest_summaries(
    summary: str,
    job_description: str,
    lang: str,
    count: int,
) -> List[str]:
    """Deterministic mock: rephrase summary in 3 styles."""
    base = summary.strip()
    kws = _extract_keywords(job_description, max_items=4) if job_description else []
    kw_str = ", ".join(kws[:3]) if kws else "key technologies"

    suggestions = [
        f"Results-driven professional with a proven track record. {base.rstrip('. ')}. Specializing in {kw_str}.",
        f"Highly motivated expert delivering measurable impact. {base.rstrip('. ')}. Leveraging expertise in {kw_str} to drive business outcomes.",
        f"Strategic leader focused on innovation and excellence. {base.rstrip('. ')}. Combining deep knowledge of {kw_str} with a passion for continuous improvement.",
    ]
    return suggestions[:count]


# Backward-compat alias — old callers may still use rewrite_cv
rewrite_cv = ai_rewrite_cv


# ── Interview Simulator ──────────────────────────────────────────────────

INTERVIEW_ALLOWED_MODES = {"junior", "senior", "manager", "tech", "academic"}


def generate_interview_questions(
    cv_text: str,
    job_description: str = "",
    lang: str = "en",
    mode: str = "senior",
    count: int = 5,
) -> list[dict]:
    """Generate realistic interview questions based on CV and optional JD.

    Returns a list of dicts: {question, category, difficulty, tip}
    """
    cv_text = _guard_text(cv_text, MAX_INPUT_CHARS, "cv_text")
    job_description = (job_description or "").strip()
    normalized_mode = str(mode or "senior").strip().lower()
    if normalized_mode not in INTERVIEW_ALLOWED_MODES:
        normalized_mode = "senior"
    count = max(3, min(count, 10))

    provider = _select_provider()
    if provider == "mock" or not str(os.getenv("OPENAI_API_KEY", "")).strip():
        return _mock_interview_questions(cv_text, job_description, lang, normalized_mode, count)

    lang_map = {"en": "English", "tr": "Turkish", "de": "German", "fr": "French", "es": "Spanish", "ar": "Arabic"}
    lang_name = lang_map.get(lang, "English")
    jd_hint = f"\nTarget job description:\n{job_description[:2000]}" if job_description else ""

    prompt = (
        f"You are an expert interviewer. Generate {count} realistic interview questions "
        f"for a {normalized_mode}-level candidate based on their CV and the job description.\n"
        f"Language: {lang_name}.\n"
        f"CV:\n{cv_text[:3000]}\n"
        f"{jd_hint}\n\n"
        f"Return a JSON array with exactly {count} objects. Each object must have:\n"
        '- "question": the interview question\n'
        '- "category": one of "behavioral", "technical", "situational", "competency"\n'
        '- "difficulty": one of "easy", "medium", "hard"\n'
        '- "tip": a short hint for how to approach this question\n\n'
        "Mix question categories. Include both technical and behavioral questions.\n"
        "Do NOT invent facts not present in the CV.\n"
        "Return ONLY the JSON array, no markdown fences."
    )

    try:
        raw = _generate(prompt, max_tokens=1500)
        parsed = json.loads(raw)
        if isinstance(parsed, list) and len(parsed) >= 1:
            result = []
            for item in parsed[:count]:
                if isinstance(item, dict) and item.get("question"):
                    result.append({
                        "question": str(item.get("question", "")).strip(),
                        "category": str(item.get("category", "behavioral")).strip().lower(),
                        "difficulty": str(item.get("difficulty", "medium")).strip().lower(),
                        "tip": str(item.get("tip", "")).strip(),
                    })
            if result:
                return result
    except Exception:
        pass

    return _mock_interview_questions(cv_text, job_description, lang, normalized_mode, count)


def _mock_interview_questions(
    cv_text: str,
    job_description: str,
    lang: str,
    mode: str,
    count: int,
) -> list[dict]:
    """Deterministic mock interview questions for dev/test."""
    kws = _extract_keywords(cv_text + " " + job_description, max_items=8)
    kw1 = kws[0] if kws else "your main skill"
    kw2 = kws[1] if len(kws) > 1 else "your secondary skill"
    kw3 = kws[2] if len(kws) > 2 else "teamwork"

    is_tr = lang == "tr"

    mode_questions = {
        "junior": [
            {"question": f"Tell me about a project where you used {kw1}. What was your contribution?" if not is_tr else f"{kw1} kullandığınız bir proje hakkında bana anlatır mısınız? Katkınız neydi?", "category": "behavioral", "difficulty": "easy", "tip": "Use the STAR method: Situation, Task, Action, Result." if not is_tr else "STAR yöntemini kullanın: Durum, Görev, Eylem, Sonuç."},
            {"question": f"How do you approach learning a new technology like {kw2}?" if not is_tr else f"{kw2} gibi yeni bir teknolojiyi öğrenmeye nasıl yaklaşırsınız?", "category": "competency", "difficulty": "easy", "tip": "Show curiosity and structured approach to learning." if not is_tr else "Merak ve yapılandırılmış öğrenme yaklaşımınızı gösterin."},
            {"question": f"Describe a challenging bug you encountered. How did you debug it?" if not is_tr else "Karşılaştığınız zorlu bir hatayı anlatın. Nasıl hata ayıkladınız?", "category": "technical", "difficulty": "medium", "tip": "Walk through your systematic debugging process." if not is_tr else "Sistematik hata ayıklama sürecinizi anlatın."},
            {"question": "How do you handle feedback from senior team members?" if not is_tr else "Kıdemli ekip üyelerinden gelen geri bildirimleri nasıl karşılarsınız?", "category": "behavioral", "difficulty": "easy", "tip": "Show openness and growth mindset." if not is_tr else "Açıklık ve gelişim odaklı düşünce yapınızı gösterin."},
            {"question": f"What excites you most about {kw3} in your career?" if not is_tr else f"Kariyerinizde {kw3} konusunda sizi en çok ne heyecanlandırıyor?", "category": "behavioral", "difficulty": "easy", "tip": "Be genuine and connect to your career goals." if not is_tr else "Samimi olun ve kariyer hedeflerinizle bağlantı kurun."},
        ],
        "senior": [
            {"question": f"Describe a complex system you designed using {kw1}. What trade-offs did you consider?" if not is_tr else f"{kw1} kullanarak tasarladığınız karmaşık bir sistemi anlatın. Hangi trade-off'ları değerlendirdiniz?", "category": "technical", "difficulty": "hard", "tip": "Focus on architectural decisions, scalability, and real constraints." if not is_tr else "Mimari kararlar, ölçeklenebilirlik ve gerçek kısıtlamalara odaklanın."},
            {"question": f"Tell me about a time you mentored a junior developer on {kw2}." if not is_tr else f"{kw2} konusunda bir junior geliştiriciye mentorluk yaptığınız bir deneyimi anlatın.", "category": "behavioral", "difficulty": "medium", "tip": "Show leadership and knowledge transfer ability." if not is_tr else "Liderlik ve bilgi aktarım becerilerinizi gösterin."},
            {"question": "How do you handle technical debt in a fast-paced environment?" if not is_tr else "Hızlı tempolu bir ortamda teknik borçları nasıl yönetirsiniz?", "category": "situational", "difficulty": "hard", "tip": "Balance between shipping features and maintaining code quality." if not is_tr else "Özellik çıkarma ve kod kalitesini koruma arasındaki dengeyi anlatın."},
            {"question": f"Walk me through how you'd optimize a slow {kw3} query/process." if not is_tr else f"Yavaş bir {kw3} sorgusu/sürecini nasıl optimize edersiniz, adım adım anlatın.", "category": "technical", "difficulty": "hard", "tip": "Show systematic profiling, measurement, and iterative improvement." if not is_tr else "Sistematik profil çıkarma, ölçüm ve iteratif iyileştirme gösterin."},
            {"question": "Describe a production incident you handled. What was your approach?" if not is_tr else "Üstlendiğiniz bir production kesintisini anlatın. Yaklaşımınız neydi?", "category": "situational", "difficulty": "medium", "tip": "Demonstrate calm under pressure and post-mortem thinking." if not is_tr else "Baskı altında sakinliğinizi ve post-mortem düşünce yapınızı gösterin."},
        ],
        "manager": [
            {"question": f"How do you build and scale engineering teams in {kw1} domain?" if not is_tr else f"{kw1} alanında mühendislik ekiplerini nasıl kurar ve büyütürsünüz?", "category": "competency", "difficulty": "hard", "tip": "Cover hiring, culture, and team structure." if not is_tr else "İşe alım, kültür ve ekip yapısını kapsayın."},
            {"question": "Tell me about a time you resolved a conflict between team members." if not is_tr else "Ekip üyeleri arasındaki bir çatışmayı çözdüğünüz bir zamanı anlatın.", "category": "behavioral", "difficulty": "medium", "tip": "Show empathy, active listening, and resolution skills." if not is_tr else "Empati, aktif dinleme ve çözüm becerilerinizi gösterin."},
            {"question": "How do you align technical roadmap with business objectives?" if not is_tr else "Teknik yol haritasını iş hedefleriyle nasıl hizalarsınız?", "category": "situational", "difficulty": "hard", "tip": "Demonstrate strategic thinking and stakeholder communication." if not is_tr else "Stratejik düşünme ve paydaş iletişimi gösterin."},
            {"question": "Describe how you handle underperforming team members." if not is_tr else "Düşük performans gösteren ekip üyelerini nasıl yönetirsiniz?", "category": "behavioral", "difficulty": "hard", "tip": "Show coaching approach, clear expectations, and support." if not is_tr else "Koçluk yaklaşımı, net beklentiler ve destek gösterin."},
            {"question": f"How do you evaluate new {kw2} technologies for your team?" if not is_tr else f"Ekibiniz için yeni {kw2} teknolojilerini nasıl değerlendirirsiniz?", "category": "competency", "difficulty": "medium", "tip": "Balance innovation with stability and team capacity." if not is_tr else "İnovasyonu stabilite ve ekip kapasitesiyle dengeleyin."},
        ],
        "tech": [
            {"question": f"Design a scalable architecture for a {kw1}-based system handling 100K requests/sec." if not is_tr else f"Saniyede 100K istek işleyen {kw1} tabanlı bir sistem için ölçeklenebilir mimari tasarlayın.", "category": "technical", "difficulty": "hard", "tip": "Cover load balancing, caching, database sharding, and failure modes." if not is_tr else "Yük dengeleme, önbellek, veritabanı parçalama ve hata modlarını kapsayın."},
            {"question": f"Explain the difference between {kw1} and {kw2} at a deep level." if not is_tr else f"{kw1} ve {kw2} arasındaki farkları derin düzeyde açıklayın.", "category": "technical", "difficulty": "medium", "tip": "Show depth of understanding beyond surface-level comparisons." if not is_tr else "Yüzeysel karşılaştırmaların ötesinde derin anlayış gösterin."},
            {"question": "How do you ensure code quality in a microservices environment?" if not is_tr else "Mikroservis ortamında kod kalitesini nasıl sağlarsınız?", "category": "technical", "difficulty": "medium", "tip": "Cover testing strategies, CI/CD, code review, and observability." if not is_tr else "Test stratejileri, CI/CD, kod inceleme ve gözlemlenebilirlik konularını kapsayın."},
            {"question": f"Describe a performance bottleneck in {kw3} that you identified and resolved." if not is_tr else f"{kw3}'daki tespit edip çözdüğünüz bir performans darboğazını anlatın.", "category": "technical", "difficulty": "hard", "tip": "Show profiling methodology and measurable improvements." if not is_tr else "Profil çıkarma metodolojisi ve ölçülebilir iyileştirmeleri gösterin."},
            {"question": "What's your approach to API design and versioning?" if not is_tr else "API tasarımı ve sürümlendirme konusundaki yaklaşımınız nedir?", "category": "technical", "difficulty": "medium", "tip": "Cover RESTful principles, backward compatibility, and documentation." if not is_tr else "RESTful ilkeleri, geriye dönük uyumluluk ve dokümantasyonu kapsayın."},
        ],
        "academic": [
            {"question": f"Describe your research methodology in {kw1}." if not is_tr else f"{kw1} konusundaki araştırma metodolojinizi anlatın.", "category": "competency", "difficulty": "hard", "tip": "Cover hypothesis formation, data collection, and validation." if not is_tr else "Hipotez oluşturma, veri toplama ve doğrulamayı kapsayın."},
            {"question": "How do you handle conflicting findings in your research?" if not is_tr else "Araştırmanızdaki çelişkili bulguları nasıl ele alırsınız?", "category": "behavioral", "difficulty": "medium", "tip": "Show intellectual honesty and rigorous analysis." if not is_tr else "Entelektüel dürüstlük ve titiz analiz gösterin."},
            {"question": f"Explain how {kw2} impacts your field of study." if not is_tr else f"{kw2}'nin çalışma alanınızı nasıl etkilediğini açıklayın.", "category": "technical", "difficulty": "medium", "tip": "Connect theoretical knowledge to practical implications." if not is_tr else "Teorik bilgiyi pratik etkilerle bağlantılandırın."},
            {"question": "How do you communicate complex findings to non-expert stakeholders?" if not is_tr else "Karmaşık bulguları uzman olmayan paydaşlara nasıl iletirsiniz?", "category": "behavioral", "difficulty": "medium", "tip": "Show ability to simplify without oversimplifying." if not is_tr else "Aşırı basitleştirmeden sadeleştirme yeteneğinizi gösterin."},
            {"question": "Describe a collaborative research project and your role in it." if not is_tr else "İşbirliğine dayalı bir araştırma projesini ve bu projedeki rolünüzü anlatın.", "category": "behavioral", "difficulty": "easy", "tip": "Highlight teamwork, your unique contribution, and outcomes." if not is_tr else "Takım çalışması, özgün katkınız ve sonuçları vurgulayın."},
        ],
    }

    questions = mode_questions.get(mode, mode_questions["senior"])
    return questions[:count]


def evaluate_interview_answer(
    question: str,
    answer: str,
    cv_text: str = "",
    job_description: str = "",
    lang: str = "en",
) -> dict:
    """Evaluate a user's interview answer and provide AI feedback.

    Returns dict: {score, feedback, strengths, improvements, sample_answer}
    """
    question = _guard_text(question, 1000, "question")
    answer = _guard_text(answer, MAX_INPUT_CHARS, "answer")
    cv_text = (cv_text or "").strip()
    job_description = (job_description or "").strip()

    provider = _select_provider()
    if provider == "mock" or not str(os.getenv("OPENAI_API_KEY", "")).strip():
        return _mock_evaluate_answer(question, answer, lang)

    lang_map = {"en": "English", "tr": "Turkish", "de": "German", "fr": "French", "es": "Spanish", "ar": "Arabic"}
    lang_name = lang_map.get(lang, "English")

    prompt = (
        "You are an expert interview coach. Evaluate this interview answer.\n"
        f"Language: {lang_name}.\n\n"
        f"Question: {question}\n\n"
        f"Candidate's Answer: {answer}\n\n"
        f"CV Context: {cv_text[:1500]}\n\n"
        f"Job Description: {job_description[:1000]}\n\n"
        "Return a JSON object with:\n"
        '- "score": integer 1-10\n'
        '- "feedback": 2-3 sentence overall feedback\n'
        '- "strengths": array of 2-3 strengths\n'
        '- "improvements": array of 2-3 areas to improve\n'
        '- "sample_answer": a model answer (3-4 sentences)\n\n'
        "Be constructive and encouraging.\n"
        "Return ONLY the JSON object, no markdown fences."
    )

    try:
        raw = _generate(prompt, max_tokens=800)
        parsed = _extract_json_object(raw)
        return {
            "score": max(1, min(10, int(parsed.get("score", 5)))),
            "feedback": str(parsed.get("feedback", "")).strip(),
            "strengths": [str(s).strip() for s in (parsed.get("strengths") or [])[:3]],
            "improvements": [str(s).strip() for s in (parsed.get("improvements") or [])[:3]],
            "sample_answer": str(parsed.get("sample_answer", "")).strip(),
        }
    except Exception:
        pass

    return _mock_evaluate_answer(question, answer, lang)


def _mock_evaluate_answer(question: str, answer: str, lang: str) -> dict:
    """Deterministic mock evaluation for dev/test."""
    is_tr = lang == "tr"
    word_count = len(answer.split())

    if word_count >= 50:
        score = 7
    elif word_count >= 25:
        score = 5
    else:
        score = 3

    if is_tr:
        return {
            "score": score,
            "feedback": f"Yanıtınız {word_count} kelime içeriyor. {'İyi detay seviyesi.' if word_count >= 50 else 'Daha fazla detay ve örnek ekleyerek geliştirebilirsiniz.'}",
            "strengths": ["Konuya odaklanmış yanıt", "Net iletişim", "İlgili deneyimlerden bahsetme"],
            "improvements": ["STAR yöntemini daha aktif kullanın", "Somut örnekler ve metrikler ekleyin", "Sonuçları ölçülebilir şekilde ifade edin"],
            "sample_answer": f"[Örnek yanıt] '{question[:60]}...' sorusu için ideal bir yanıt, belirli bir proje veya deneyimle başlamalı, attığınız adımları açıklamalı ve ölçülebilir bir sonuçla bitmelidir.",
        }

    return {
        "score": score,
        "feedback": f"Your answer contains {word_count} words. {'Good level of detail.' if word_count >= 50 else 'Consider adding more specific examples and measurable results.'}",
        "strengths": ["Focused response to the question", "Clear communication", "Relevant experience mentioned"],
        "improvements": ["Use the STAR method more actively", "Add specific metrics and numbers", "End with measurable outcomes"],
        "sample_answer": f"[Sample answer] For '{question[:60]}...', an ideal response should start with a specific project or experience, explain the actions you took, and end with a measurable result.",
    }
