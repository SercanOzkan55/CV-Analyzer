"""
ATS-Optimized CV Builder Service
Generates professional CVs using OpenAI for content enhancement
and python-docx / fpdf2 for document generation.

ATS Rules enforced:
- Single column layout
- Standard fonts (Arial, Calibri, Times New Roman)
- 10.5-12pt font size
- Standard section headers (Summary, Experience, Education, Skills, etc.)
- Bullet points, not paragraphs
- No graphics, icons, tables, text boxes, multi-column
- Measurable results in experience bullets
- Standard date formats (Mon YYYY - Mon YYYY)
- Skills listed as "Skill - Level" (no star ratings)
- No photo, DOB, marital status
"""

import json
import logging
import os
import re
from datetime import datetime
from io import BytesIO

from .language_service import DEFAULT_LANG

logger = logging.getLogger(__name__)

MOCK_SERVICES_ON = os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes")

# ---------------------------------------------------------------------------
# OpenAI helpers
# ---------------------------------------------------------------------------

_OPENAI_KEY = os.getenv("OPENAI_API_KEY")

def _get_openai_client():
    if MOCK_SERVICES_ON or not _OPENAI_KEY:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=_OPENAI_KEY)
    except Exception:
        return None


def _enhance_cv_with_ai(cv_data: dict, job_description: str, lang: str = DEFAULT_LANG) -> dict:
    """Use OpenAI to enhance CV content: rewrite bullets with metrics,
    tailor summary to job description, optimize keyword placement."""

    client = _get_openai_client()
    if not client:
        return _mock_enhance(cv_data, job_description, lang)

    if lang == "tr":
        lang_instruction = "Turkish"
    elif lang == "en":
        lang_instruction = "English"
    else:
        lang_instruction = (
            "the same language as the source CV unless the job description clearly "
            "requires a different language"
        )

    prompt = f"""You are an expert ATS CV writer. Enhance the following CV data for an ATS-optimized resume.
Language: Write everything in {lang_instruction}.

Job Description:
{job_description[:3000]}

CV Data (JSON):
{json.dumps(cv_data, ensure_ascii=False, default=str)[:4000]}

Rules:
1. Rewrite the summary to be 2-3 sentences, tailored to the job description, using keywords from it.
2. For each experience entry, rewrite bullets to:
   - Start with strong action verbs
   - Include measurable results (%, $, numbers) where possible
   - Incorporate relevant keywords from the job description
3. Optimize the skills list: put the most relevant skills first, use "Skill - Level" format (Advanced/Intermediate/Beginner).
4. Keep education as-is but ensure proper formatting.
5. Do NOT add fake data. Only enhance what's provided.

Return a JSON object with these exact keys:
{{
  "summary": "enhanced summary text",
  "experiences": [
    {{
      "title": "Job Title",
      "company": "Company Name",
      "location": "City, Country",
      "start_date": "Mon YYYY",
      "end_date": "Mon YYYY or Present",
      "bullets": ["bullet 1", "bullet 2", ...]
    }}
  ],
  "skills_categorized": {{
    "category_name": ["Skill - Level", ...]
  }},
  "education": [
    {{
      "degree": "Degree Name",
      "school": "School Name",
      "location": "City, Country",
      "start_date": "Mon YYYY",
      "end_date": "Mon YYYY",
      "gpa": "3.8/4.0 or null",
      "field": "Field of Study"
    }}
  ],
  "certifications": [
    {{
      "name": "Cert Name",
      "issuer": "Issuer",
      "date": "Mon YYYY"
    }}
  ],
  "projects": [
    {{
      "name": "Project Name",
      "description": "One line description",
      "bullets": ["bullet 1", ...]
    }}
  ]
}}

Return ONLY valid JSON, no markdown fences."""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=3000,
        )
        content = resp.choices[0].message.content.strip()
        # Strip markdown fences if present
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        enhanced = json.loads(content)
        # Merge back any fields AI didn't return
        for key in ("full_name", "email", "phone", "location", "languages", "linkedin", "professional_profile"):
            if key in cv_data and key not in enhanced:
                enhanced[key] = cv_data[key]
        return enhanced
    except Exception as e:
        logger.warning(f"OpenAI CV enhancement failed: {e}")
        return _mock_enhance(cv_data, job_description, lang)


def _mock_enhance(cv_data: dict, job_description: str, lang: str = DEFAULT_LANG) -> dict:
    """Fallback: return structured data without AI enhancement."""
    result = dict(cv_data)

    # Ensure required structure exists
    if "summary" not in result or not result["summary"]:
        result["summary"] = cv_data.get("summary", "")

    if "experiences" not in result:
        result["experiences"] = []
    for exp in result["experiences"]:
        if "bullets" not in exp:
            exp["bullets"] = []

    if "skills_categorized" not in result:
        raw_skills = cv_data.get("skills", [])
        if isinstance(raw_skills, list) and raw_skills:
            # Categorize skills automatically for ATS compliance
            categories = {
                "Languages": [],
                "Backend & Frameworks": [],
                "Databases": [],
                "DevOps & Cloud": [],
                "Tools & Platforms": [],
            }
            lang_kw = {"python", "java", "javascript", "typescript", "c++", "c#", "go", "rust", "ruby", "php", "swift", "kotlin", "scala", "r", "matlab", "sql", "html", "css", "dart", "perl", "bash", "shell", "lua", "elixir", "haskell", "objective-c"}
            backend_kw = {"django", "flask", "fastapi", "spring", "express", "nestjs", "rails", "laravel", "react", "vue", "angular", "next", "nuxt", "svelte", "node", "asp.net", ".net", "graphql", "rest", "grpc", "celery", "gin", "fiber", "actix"}
            db_kw = {"postgresql", "postgres", "mysql", "mongodb", "redis", "sqlite", "oracle", "dynamodb", "cassandra", "elasticsearch", "neo4j", "mariadb", "supabase", "firebase", "firestore", "couchdb", "influxdb", "mssql", "pgvector"}
            devops_kw = {"docker", "kubernetes", "k8s", "aws", "gcp", "azure", "terraform", "ansible", "jenkins", "ci/cd", "github actions", "gitlab", "linux", "nginx", "prometheus", "grafana", "helm", "argocd", "cloudflare", "vercel", "heroku", "digitalocean", "lambda", "ec2", "s3", "ecs", "fargate"}

            for skill in raw_skills:
                s_lower = skill.lower().strip()
                if s_lower in lang_kw:
                    categories["Languages"].append(skill)
                elif s_lower in backend_kw or any(k in s_lower for k in backend_kw):
                    categories["Backend & Frameworks"].append(skill)
                elif s_lower in db_kw or any(k in s_lower for k in db_kw):
                    categories["Databases"].append(skill)
                elif s_lower in devops_kw or any(k in s_lower for k in devops_kw):
                    categories["DevOps & Cloud"].append(skill)
                else:
                    categories["Tools & Platforms"].append(skill)

            # Only include non-empty categories
            result["skills_categorized"] = {k: v for k, v in categories.items() if v}
            if not result["skills_categorized"]:
                result["skills_categorized"] = {"Technical Skills": raw_skills}
        elif isinstance(raw_skills, dict):
            result["skills_categorized"] = raw_skills
        else:
            result["skills_categorized"] = {}

    if "education" not in result:
        result["education"] = []
    if "certifications" not in result:
        result["certifications"] = []
    if "projects" not in result:
        result["projects"] = []

    return result


# ---------------------------------------------------------------------------
# DOCX Generation (ATS-optimized)
# ---------------------------------------------------------------------------

def generate_docx(cv_data: dict, template: str = "classic") -> BytesIO:
    """Generate an ATS-friendly DOCX file. Returns BytesIO buffer."""
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # -- Page margins
    for section in doc.sections:
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # -- Style helpers
    style = doc.styles["Normal"]
    font = style.font
    font.size = Pt(11)

    # Template-specific fonts and styling
    template_config = {
        "modern": {"font": "Calibri", "accent_color": (0x2B, 0x6C, 0xB0)},
        "executive": {"font": "Times New Roman", "accent_color": (0x8B, 0x45, 0x13)},
        "professional": {"font": "Georgia", "accent_color": (0x2F, 0x4F, 0x4F)},
        "creative": {"font": "Garamond", "accent_color": (0x9B, 0x59, 0xB6)},
        "corporate": {"font": "Cambria", "accent_color": (0x1F, 0x4E, 0x79)},
        "tech": {"font": "Consolas", "accent_color": (0x00, 0x7A, 0xCC)},
        "consulting": {"font": "Book Antiqua", "accent_color": (0x5D, 0x4E, 0x75)},
        "classic": {"font": "Arial", "accent_color": (0x00, 0x00, 0x00)},
    }
    
    config = template_config.get(template, template_config["classic"])
    font.name = config["font"]

    # Keep paragraph rhythm consistent to avoid visual drift between sections.
    style.paragraph_format.space_before = Pt(0)
    style.paragraph_format.space_after = Pt(4)
    style.paragraph_format.line_spacing = 1.15

    # -- Name
    name = cv_data.get("full_name", "")
    if name:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(name.upper())
        run.bold = True
        run.font.size = Pt(16)
        run.font.name = font.name

    # -- Contact line
    contact_parts = []
    if cv_data.get("email"):
        contact_parts.append(cv_data["email"])
    if cv_data.get("phone"):
        contact_parts.append(cv_data["phone"])
    if cv_data.get("location"):
        contact_parts.append(cv_data["location"])
    profile_url = cv_data.get("professional_profile") or cv_data.get("linkedin")
    if profile_url:
        if profile_url and not profile_url.startswith("http"):
            profile_url = f"https://{profile_url}"
        contact_parts.append(profile_url)

    if contact_parts:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("  |  ".join(contact_parts))
        run.font.size = Pt(10)
        run.font.name = font.name

    def add_section_header(title):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(title.upper())
        run.bold = True
        run.font.size = Pt(12)
        run.font.name = font.name
        
        # Apply template-specific accent color
        color = config["accent_color"]
        if color != (0x00, 0x00, 0x00):  # Not black (classic default)
            run.font.color.rgb = RGBColor(*color)
            
        # Template-specific styling
        if template in ["corporate", "consulting", "executive"]:
            # Professional templates get thicker border
            border_size = "6"
            border_color = f"{color[0]:02x}{color[1]:02x}{color[2]:02x}"
        elif template in ["creative", "tech"]:
            # Modern templates get colored border
            border_size = "4"
            border_color = f"{color[0]:02x}{color[1]:02x}{color[2]:02x}"
        else:
            # Classic styling
            border_size = "4"
            border_color = "999999"
            
        # Add separator line
        from docx.oxml.ns import qn
        pPr = p._p.get_or_add_pPr()
        pBdr = pPr.makeelement(qn("w:pBdr"), {})
        bottom = pBdr.makeelement(qn("w:bottom"), {
            qn("w:val"): "single",
            qn("w:sz"): border_size,
            qn("w:space"): "1",
            qn("w:color"): border_color,
        })
        pBdr.append(bottom)
        pPr.append(pBdr)

    def add_bullet(text_content):
        # Clean text content to avoid special characters
        clean_text = text_content.strip() if text_content else ""
        if not clean_text:
            return
        # Remove any existing bullet markers 
        clean_text = re.sub(r'^[-\-\*]\s*', '', clean_text)
        
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.2)
        p.paragraph_format.first_line_indent = Inches(-0.15)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.space_before = Pt(0)
        run = p.add_run(f"- {clean_text}")
        run.font.size = Pt(10.5)
        run.font.name = font.name

    # -- Professional Summary
    summary = cv_data.get("summary", "")
    if summary:
        add_section_header("Professional Summary")
        p = doc.add_paragraph()
        run = p.add_run(summary)
        run.font.size = Pt(10.5)
        run.font.name = font.name

    # -- Experience
    experiences = cv_data.get("experiences", [])
    if experiences:
        add_section_header("Experience")
        for exp in experiences:
            # Title + Company line
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(1)

            title_run = p.add_run(exp.get("title", ""))
            title_run.bold = True
            title_run.font.size = Pt(11)
            title_run.font.name = font.name

            company = exp.get("company", "")
            if company:
                sep_run = p.add_run("  --  ")
                sep_run.font.name = font.name
                sep_run.font.size = Pt(11)
                c_run = p.add_run(company)
                c_run.font.size = Pt(11)
                c_run.font.name = font.name

            # Date + Location on a SEPARATE line to prevent overflow
            start = exp.get("start_date", "")
            end = exp.get("end_date", "")
            location = exp.get("location", "")
            meta_parts = []
            if start or end:
                date_str = f"{start} - {end}" if start and end else (start or end)
                meta_parts.append(date_str)
            if location:
                meta_parts.append(location)
            if meta_parts:
                mp = doc.add_paragraph()
                mp.paragraph_format.space_before = Pt(0)
                mp.paragraph_format.space_after = Pt(1)
                mp_run = mp.add_run("  |  ".join(meta_parts))
                mp_run.font.size = Pt(10)
                mp_run.font.name = font.name
                mp_run.italic = True

            for bullet in exp.get("bullets", []):
                if bullet and bullet.strip():
                    add_bullet(bullet)

    # -- Education
    education = cv_data.get("education", [])
    if education:
        add_section_header("Education")
        for edu in education:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(0)

            degree = edu.get("degree", "")
            field = edu.get("field", "")
            degree_text = f"{degree}" + (f" in {field}" if field else "")
            d_run = p.add_run(degree_text)
            d_run.bold = True
            d_run.font.size = Pt(11)
            d_run.font.name = font.name

            school = edu.get("school", "")
            if school:
                sep_run = p.add_run("  --  ")
                sep_run.font.name = font.name
                sep_run.font.size = Pt(11)
                s_run = p.add_run(school)
                s_run.font.size = Pt(11)
                s_run.font.name = font.name

            # Date + Location + GPA on a separate line
            start = edu.get("start_date", "")
            end = edu.get("end_date", "")
            gpa = edu.get("gpa", "")
            loc = edu.get("location", "")
            meta_parts = []
            if start or end:
                date_str = f"{start} - {end}" if start and end else (start or end)
                meta_parts.append(date_str)
            if loc:
                meta_parts.append(loc)
            if gpa:
                meta_parts.append(f"GPA: {gpa}")
            if meta_parts:
                mp = doc.add_paragraph()
                mp.paragraph_format.space_before = Pt(0)
                mp.paragraph_format.space_after = Pt(1)
                mp_run = mp.add_run("  |  ".join(meta_parts))
                mp_run.font.size = Pt(10)
                mp_run.font.name = font.name
                mp_run.italic = True

    # -- Skills
    skills_cat = cv_data.get("skills_categorized", {})
    if skills_cat:
        add_section_header("Skills")
        for category, items in skills_cat.items():
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(1)
            cat_run = p.add_run(f"{category}: ")
            cat_run.bold = True
            cat_run.font.size = Pt(10.5)
            cat_run.font.name = font.name
            skills_text = ", ".join(items) if isinstance(items, list) else str(items)
            sk_run = p.add_run(skills_text)
            sk_run.font.size = Pt(10.5)
            sk_run.font.name = font.name

    # -- Certifications
    certs = cv_data.get("certifications", [])
    if certs:
        add_section_header("Certifications")
        for cert in certs:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            c_name = cert.get("name", "")
            # Clean special characters for ATS
            c_name = c_name.replace("?", "-").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
            c_issuer = cert.get("issuer", "")
            c_date = cert.get("date", "")
            run = p.add_run(c_name)
            run.bold = True
            run.font.size = Pt(10.5)
            run.font.name = font.name
            meta = []
            if c_issuer:
                meta.append(c_issuer)
            if c_date:
                meta.append(c_date)
            if meta:
                sep_run = p.add_run(f"  --  {', '.join(meta)}")
                sep_run.font.name = font.name
                sep_run.font.size = Pt(10.5)

    # -- Projects
    projects = cv_data.get("projects", [])
    if projects:
        add_section_header("Projects")
        for proj in projects:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            pn_run = p.add_run(proj.get("name", ""))
            pn_run.bold = True
            pn_run.font.size = Pt(11)
            pn_run.font.name = font.name

            desc = proj.get("description", "")
            if desc:
                dp = doc.add_paragraph()
                dp_run = dp.add_run(desc)
                dp_run.font.size = Pt(10.5)
                dp_run.font.name = font.name
                dp_run.italic = True

            for bullet in proj.get("bullets", []):
                if bullet and bullet.strip():
                    add_bullet(bullet)

    # -- Languages
    languages = cv_data.get("languages", [])
    if languages:
        add_section_header("Languages")
        p = doc.add_paragraph()
        lang_parts = []
        for l in languages:
            if isinstance(l, dict):
                lang_parts.append(f"{l.get('name', '')} - {l.get('level', '')}")
            else:
                lang_parts.append(str(l))
        run = p.add_run(", ".join(lang_parts))
        run.font.size = Pt(10.5)
        run.font.name = font.name

    # Save to buffer
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# PDF Generation (ATS-optimized, single-column, clean)
# ---------------------------------------------------------------------------

def generate_pdf(cv_data: dict, template: str = "classic") -> BytesIO:
    """Generate an ATS-friendly PDF. Returns BytesIO buffer."""
    from fpdf import FPDF

    class ATSPDF(FPDF):
        def __init__(self, font_family="Helvetica"):
            super().__init__()
            self._font_family = font_family

        def header(self):
            pass

        def footer(self):
            self.set_y(-15)
            self.set_font(self._font_family, "I", 8)
            self.cell(0, 10, f"Page {self.page_no()}", align="C")

    # Template-specific PDF styling
    pdf_template_config = {
        "modern": {"font": "Helvetica", "accent_color": (43, 108, 176)},
        "executive": {"font": "Times", "accent_color": (139, 69, 19)},
        "professional": {"font": "Times", "accent_color": (47, 79, 79)},
        "creative": {"font": "Helvetica", "accent_color": (155, 89, 182)},
        "corporate": {"font": "Times", "accent_color": (31, 78, 121)},
        "tech": {"font": "Courier", "accent_color": (0, 122, 204)},
        "consulting": {"font": "Times", "accent_color": (93, 78, 117)},
        "classic": {"font": "Helvetica", "accent_color": (0, 0, 0)},
    }
    
    pdf_config = pdf_template_config.get(template, pdf_template_config["classic"])
    font_family = pdf_config["font"]
    accent_color = pdf_config["accent_color"]

    pdf = ATSPDF(font_family=font_family)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(20, 15, 20)

    effective_width = pdf.w - pdf.l_margin - pdf.r_margin

    def safe_text(text):
        """Sanitize text for latin-1 encoding used by fpdf2."""
        if not text:
            return ""
        # Replace common Unicode chars with latin-1 equivalents
        text = text.replace("\u2022", "-")   # bullet -
        text = text.replace("\u2013", "-")   # en dash -
        text = text.replace("\u2014", "-")   # em dash --
        text = text.replace("\u2018", "'")   # left single quote
        text = text.replace("\u2019", "'")   # right single quote
        text = text.replace("\u201c", '"')   # left double quote
        text = text.replace("\u201d", '"')   # right double quote
        text = text.replace("\u2026", "...") # ellipsis
        return text.encode("latin-1", errors="replace").decode("latin-1")

    # -- Name
    name = cv_data.get("full_name", "")
    if name:
        pdf.set_font(font_family, "B", 16)
        pdf.cell(effective_width, 8, safe_text(name.upper()), align="C", ln=True)
        pdf.ln(2)

    # -- Contact
    contact_parts = []
    if cv_data.get("email"):
        contact_parts.append(cv_data["email"])
    if cv_data.get("phone"):
        contact_parts.append(cv_data["phone"])
    if cv_data.get("location"):
        contact_parts.append(cv_data["location"])
    profile_url = cv_data.get("professional_profile") or cv_data.get("linkedin")
    if profile_url:
        if profile_url and not profile_url.startswith("http"):
            profile_url = f"https://{profile_url}"
        contact_parts.append(profile_url)
    if contact_parts:
        pdf.set_font(font_family, "", 10)
        # multi_cell prevents long contact lines from overflowing/cropping.
        pdf.multi_cell(effective_width, 5, safe_text("  |  ".join(contact_parts)), align="C")
        pdf.ln(4)

    def section_header(title):
        pdf.ln(3)
        pdf.set_font(font_family, "B", 12)
        
        # Apply template-specific text color for section headers
        if accent_color != (0, 0, 0):  # Not black (classic default)
            pdf.set_text_color(*accent_color)
        
        pdf.cell(effective_width, 6, safe_text(title.upper()), ln=True)
        
        # Reset text color to black for normal content
        pdf.set_text_color(0, 0, 0)
        
        # Template-specific line styling
        if template in ["corporate", "consulting", "executive"]:
            # Thicker line for professional templates
            pdf.set_line_width(0.7)
            pdf.set_draw_color(*accent_color)
        elif template in ["creative", "tech"]:
            # Colored line for modern templates  
            pdf.set_line_width(0.5)
            pdf.set_draw_color(*accent_color)
        else:
            # Classic gray line
            pdf.set_line_width(0.3)
            pdf.set_draw_color(150, 150, 150)
            
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(3)

    def add_bullet(text_content):
        # Clean text and use consistent bullet marker
        clean_text = text_content.strip() if text_content else ""
        if not clean_text:
            return
        # Remove any existing bullet markers
        clean_text = re.sub(r'^[-\-\*]\s*', '', clean_text)
        
        pdf.set_font(font_family, "", 10)
        pdf.set_x(pdf.l_margin + 3)
        pdf.cell(3, 5, "-")
        pdf.multi_cell(effective_width - 8, 5, safe_text(clean_text))
        pdf.ln(1)

    # -- Summary
    summary = cv_data.get("summary", "")
    if summary:
        section_header("Professional Summary")
        pdf.set_font(font_family, "", 10.5)
        pdf.multi_cell(effective_width, 5, safe_text(summary))
        pdf.ln(2)

    # -- Experience
    experiences = cv_data.get("experiences", [])
    if experiences:
        section_header("Experience")
        for exp in experiences:
            pdf.set_font(font_family, "B", 11)
            title_line = exp.get("title", "")
            company = exp.get("company", "")
            if company:
                title_line += f"  --  {company}"
            pdf.multi_cell(effective_width, 5, safe_text(title_line))

            # Date + Location on separate line
            start = exp.get("start_date", "")
            end = exp.get("end_date", "")
            location = exp.get("location", "")
            meta_parts = []
            if start or end:
                date_str = f"{start} - {end}" if start and end else (start or end)
                meta_parts.append(date_str)
            if location:
                meta_parts.append(location)
            if meta_parts:
                pdf.set_font(font_family, "I", 10)
                pdf.cell(effective_width, 5, safe_text("  |  ".join(meta_parts)), ln=True)
            pdf.ln(1)

            for bullet in exp.get("bullets", []):
                if bullet and bullet.strip():
                    add_bullet(bullet)
            pdf.ln(2)

    # -- Education
    education = cv_data.get("education", [])
    if education:
        section_header("Education")
        for edu in education:
            pdf.set_font(font_family, "B", 11)
            degree = edu.get("degree", "")
            field = edu.get("field", "")
            deg_text = degree + (f" in {field}" if field else "")
            school = edu.get("school", "")
            loc = edu.get("location", "")
            line = deg_text
            if school:
                line += f"  --  {school}"
            pdf.multi_cell(effective_width, 5, safe_text(line))

            meta = []
            s = edu.get("start_date", "")
            e = edu.get("end_date", "")
            if s or e:
                date_str = f"{s} - {e}" if s and e else (s or e)
                meta.append(date_str)
            loc = edu.get("location", "")
            if loc:
                meta.append(loc)
            gpa = edu.get("gpa", "")
            if gpa:
                meta.append(f"GPA: {gpa}")
            if meta:
                pdf.set_font(font_family, "I", 10)
                pdf.cell(effective_width, 5, safe_text("  |  ".join(meta)), ln=True)
            pdf.ln(3)

    # -- Skills
    skills_cat = cv_data.get("skills_categorized", {})
    if skills_cat:
        section_header("Skills")
        for category, items in skills_cat.items():
            skills_text = ", ".join(items) if isinstance(items, list) else str(items)
            pdf.set_font(font_family, "B", 10.5)
            cat_label = safe_text(f"{category}: ")
            cat_width = min(pdf.get_string_width(cat_label) + 2, effective_width * 0.45)
            pdf.cell(cat_width, 5, cat_label, ln=False)
            pdf.set_font(font_family, "", 10.5)
            pdf.multi_cell(effective_width - cat_width, 5, safe_text(skills_text))
            pdf.ln(1)

    # -- Certifications
    certs = cv_data.get("certifications", [])
    if certs:
        section_header("Certifications")
        for cert in certs:
            cert_name = cert.get("name", "")
            # Clean special characters for ATS
            cert_name = cert_name.replace("?", "\u2013").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
            cert_name = safe_text(cert_name)
            meta = []
            if cert.get("issuer"):
                meta.append(cert["issuer"])
            if cert.get("date"):
                meta.append(cert["date"])
            if meta:
                line = f"{cert_name}  --  {', '.join(meta)}"
            else:
                line = cert_name
            pdf.set_font(font_family, "B", 10.5)
            pdf.multi_cell(effective_width, 5, safe_text(line))
            pdf.ln(2)

    # -- Projects
    projects = cv_data.get("projects", [])
    if projects:
        section_header("Projects")
        for proj in projects:
            pdf.set_font(font_family, "B", 11)
            pdf.cell(effective_width, 5, safe_text(proj.get("name", "")), ln=True)
            desc = proj.get("description", "")
            if desc:
                pdf.set_font(font_family, "I", 10)
                pdf.multi_cell(effective_width, 5, safe_text(desc))
            for bullet in proj.get("bullets", []):
                if bullet and bullet.strip():
                    add_bullet(bullet)
            pdf.ln(2)

    # -- Languages
    languages = cv_data.get("languages", [])
    if languages:
        section_header("Languages")
        pdf.set_font(font_family, "", 10.5)
        lang_parts = []
        for l in languages:
            if isinstance(l, dict):
                lang_parts.append(f"{l.get('name', '')} - {l.get('level', '')}")
            else:
                lang_parts.append(str(l))
        pdf.cell(effective_width, 5, safe_text(", ".join(lang_parts)), ln=True)

    buf = BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# All CV templates are ATS-compliant (Application Tracking System)
# They use standard fonts, clean formatting, and proper structure
# to ensure compatibility with automated resume scanning systems
TEMPLATES = {
    "free": ["classic"],
    "pro": ["classic", "modern", "executive", "professional", "creative"],
    "enterprise": ["classic", "modern", "executive", "professional", "creative", "corporate", "tech", "consulting"],
}


def get_available_templates(plan: str) -> list:
    return TEMPLATES.get(plan, TEMPLATES["free"])


def build_cv(
    cv_data: dict,
    job_description: str,
    template: str = "classic",
    output_format: str = "docx",
    lang: str = DEFAULT_LANG,
    plan: str = "free",
) -> dict:
    """
    Main entry: enhance CV data with AI, generate document.
    Returns dict with 'buffer' (BytesIO), 'filename', 'content_type'.
    """
    # Validate template access
    allowed = get_available_templates(plan)
    if template not in allowed:
        template = "classic"

    # Enhance with AI
    enhanced = _enhance_cv_with_ai(cv_data, job_description, lang)

    # Generate document
    full_name = enhanced.get("full_name", cv_data.get("full_name", "CV"))
    safe_name = re.sub(r"[^a-zA-Z0-9_\- ]", "", full_name).strip().replace(" ", "_")
    if not safe_name:
        safe_name = "CV"

    if output_format == "pdf":
        buf = generate_pdf(enhanced, template)
        filename = f"{safe_name}_CV.pdf"
        content_type = "application/pdf"
    else:
        buf = generate_docx(enhanced, template)
        filename = f"{safe_name}_CV.docx"
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    return {
        "buffer": buf,
        "filename": filename,
        "content_type": content_type,
        "enhanced_data": enhanced,
    }
