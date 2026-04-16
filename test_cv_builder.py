"""
Hızlı CV Builder test scripti.
python test_cv_builder.py  komutuyla çalıştırın.
Oluşturulan DOCX ve PDF dosyaları proje klasörüne kaydedilir.
"""

from services.cv_builder_service import build_cv

SAMPLE_CV = {
    "full_name": "Ahmet Yılmaz",
    "email": "ahmet.yilmaz@gmail.com",
    "phone": "+90 532 123 4567",
    "location": "İstanbul, Türkiye",
    "linkedin": "linkedin.com/in/ahmetyilmaz",
    "summary": (
        "7+ yıl deneyimli Full Stack Yazılım Mühendisi. "
        "Python, React ve bulut teknolojileri konularında uzman. "
        "Yüksek trafikli mikroservis mimarileri tasarlama, "
        "CI/CD pipeline kurulumu ve ekip liderliği konularında güçlü yetkinliklere sahip. "
        "Performans optimizasyonu ile mevcut sistemlerde %40 hız artışı sağladı."
    ),
    "experiences": [
        {
            "title": "Senior Software Engineer",
            "company": "Trendyol Group",
            "location": "İstanbul, Türkiye",
            "start_date": "Mar 2022",
            "end_date": "Present",
            "bullets": [
                "Led a team of 5 engineers building a real-time recommendation engine serving 2M+ daily users",
                "Designed and deployed microservices with FastAPI, reducing API response times by 35%",
                "Implemented CI/CD pipelines using GitHub Actions, cutting deployment time from 2 hours to 15 minutes",
                "Migrated legacy monolith to Kubernetes-based architecture on AWS ECS",
            ],
        },
        {
            "title": "Software Engineer",
            "company": "Getir Teknoloji A.Ş.",
            "location": "İstanbul, Türkiye",
            "start_date": "Jun 2019",
            "end_date": "Feb 2022",
            "bullets": [
                "Built customer-facing React dashboard handling 500K monthly active users",
                "Developed RESTful APIs with Django and PostgreSQL, achieving 99.9% uptime",
                "Integrated Elasticsearch for product search, improving search relevance by 60%",
                "Collaborated with data team to build A/B testing framework for feature rollouts",
            ],
        },
        {
            "title": "Junior Developer",
            "company": "Insider",
            "location": "İstanbul, Türkiye",
            "start_date": "Sep 2017",
            "end_date": "May 2019",
            "bullets": [
                "Developed internal tools using Python and Flask, automating manual processes",
                "Wrote unit and integration tests, increasing code coverage from 45% to 82%",
                "Participated in code reviews and agile ceremonies as part of a 12-person team",
            ],
        },
    ],
    "education": [
        {
            "degree": "B.Sc. Computer Engineering",
            "field": "Computer Engineering",
            "school": "Boğaziçi Üniversitesi",
            "location": "İstanbul, Türkiye",
            "start_date": "Sep 2013",
            "end_date": "Jun 2017",
            "gpa": "3.72",
        }
    ],
    "skills": [
        "Python",
        "JavaScript",
        "TypeScript",
        "SQL",
        "HTML",
        "CSS",
        "React",
        "Next.js",
        "Django",
        "FastAPI",
        "Flask",
        "Node.js",
        "PostgreSQL",
        "Redis",
        "MongoDB",
        "Elasticsearch",
        "Docker",
        "Kubernetes",
        "AWS",
        "GitHub Actions",
        "Terraform",
        "Linux",
        "Git",
        "Jira",
        "Figma",
    ],
    "certifications": [
        {
            "name": "AWS Certified Solutions Architect ? Associate",
            "issuer": "Amazon Web Services",
            "date": "2023",
        },
        {
            "name": "Certified Kubernetes Administrator (CKA)",
            "issuer": "CNCF",
            "date": "2022",
        },
    ],
    "projects": [
        {
            "name": "cv-analyzer",
            "description": "AI-powered CV analysis and scoring platform with ATS optimization",
            "bullets": [
                "Built with FastAPI, React, and PostgreSQL with pgvector for semantic search",
                "Integrated OpenAI GPT-4o for intelligent CV enhancement and scoring",
                "Deployed on Docker with CI/CD via GitHub Actions",
            ],
        }
    ],
    "languages": [
        {"name": "Türkçe", "level": "Native"},
        {"name": "English", "level": "Professional (C1)"},
        {"name": "Almanca", "level": "Basic (A2)"},
    ],
}

JOB_DESCRIPTION = (
    "Senior Full Stack Developer - Python/React. "
    "Responsibilities: Design scalable microservices, "
    "mentor junior developers, implement CI/CD, work with AWS. "
    "Requirements: 5+ years Python, React, PostgreSQL, Docker, Kubernetes."
)


def main():
    # DOCX oluştur
    for fmt in ("docx", "pdf"):
        for tpl in ("classic", "modern", "executive", "tech"):
            result = build_cv(
                cv_data=dict(SAMPLE_CV),
                job_description=JOB_DESCRIPTION,
                template=tpl,
                output_format=fmt,
                lang="en",
                plan="enterprise",
            )
            fname = f"test_output_{tpl}.{fmt}"
            with open(fname, "wb") as f:
                f.write(result["buffer"].read())
            print(f"✓  {fname}  ({result['content_type']})")

    print("\nTüm dosyalar oluşturuldu! Açıp kontrol edebilirsiniz.")


if __name__ == "__main__":
    main()
