"""Expand benchmark dataset from 37 to 50+ entries with real-world edge cases."""

import json, pathlib

DS = pathlib.Path(__file__).resolve().parent.parent / "tests/benchmark/benchmark_dataset.json"

NEW = [
    # ── Very Short JD (1-2 lines) ──
    {
        "id": "B038",
        "name": "Ultra Short JD",
        "category": "short_jd",
        "cv_text": "Alex Rivera\nFull Stack Developer\n\nContact: alex@email.com\n\nExperience:\nFull Stack Developer, WebCo, 2020 - Present\n- Built React/Node.js apps serving 200K users\n- PostgreSQL database design and optimization\n- AWS deployment (EC2, S3, Lambda)\n- CI/CD with GitHub Actions\n\nSkills:\nReact, Node.js, TypeScript, PostgreSQL, AWS, Docker, Git, Python\n\nEducation:\nBS Computer Science, 2020",
        "job_description": "Looking for a developer. Python required.",
        "expected": {
            "keyword_score": {"min": 5, "max": 40},
            "ats_score": {"min": 45, "max": 80},
            "final_score": {"min": 25, "max": 65},
        },
        "notes": "Ultra short JD (1 line). System should still produce meaningful score without crashing.",
    },
    # ── Very Long JD (200+ words) ──
    {
        "id": "B039",
        "name": "Very Long JD - Enterprise Architect",
        "category": "long_jd",
        "cv_text": "Marcus Chen\nSenior Software Engineer\n\nContact: marcus.chen@email.com\n\nExperience:\nSenior Software Engineer, BigTech, 2019 - Present\n- Led migration of monolith to microservices architecture\n- Python, Java, Go backend services\n- AWS (ECS, RDS, SQS, SNS, Lambda, CloudFormation)\n- Kafka event-driven architecture\n- Terraform infrastructure as code\n- Led team of 8 engineers\n\nSoftware Engineer, StartupABC, 2016 - 2019\n- Full stack development with Python/Django and React\n- PostgreSQL, Redis, Elasticsearch\n- Docker, Kubernetes deployments\n\nSkills:\nPython, Java, Go, AWS, Terraform, Kafka, Docker, Kubernetes, PostgreSQL, Redis, React, Django\n\nEducation:\nMS Computer Science, MIT, 2016\nBS Computer Science, Georgia Tech, 2014",
        "job_description": "Enterprise Solutions Architect needed for global fintech platform. Requirements: 10+ years experience in distributed systems design and implementation. Deep expertise in cloud architecture (AWS preferred: ECS, EKS, Lambda, Step Functions, CloudFormation, CDK). Strong background in microservices architecture, event-driven design patterns, CQRS, and domain-driven design. Experience with multiple programming languages (Java, Python, Go, Kotlin). Database expertise spanning SQL (PostgreSQL, Aurora) and NoSQL (DynamoDB, MongoDB, Cassandra). Message broker experience (Kafka, RabbitMQ, SQS/SNS). Infrastructure as Code (Terraform, CloudFormation, Pulumi). Container orchestration (Kubernetes, ECS). CI/CD pipeline design (Jenkins, GitHub Actions, ArgoCD). Security best practices (IAM, VPC design, encryption at rest/transit, SOC2 compliance). Performance optimization and capacity planning. Team leadership and mentoring experience. Excellent communication for C-suite stakeholder management. Nice to have: Financial services experience, real-time trading systems, regulatory compliance (PCI-DSS, GDPR).",
        "expected": {
            "keyword_score": {"min": 15, "max": 55},
            "ats_score": {"min": 55, "max": 90},
            "final_score": {"min": 40, "max": 75},
        },
        "notes": "Very long JD (200+ words). Tests phrase dilution cap and keyword normalization.",
    },
    # ── Employment Gap ──
    {
        "id": "B040",
        "name": "Employment Gap - 3 Years",
        "category": "employment_gap",
        "cv_text": "Lisa Park\nWeb Developer\n\nContact: lisa.park@email.com\n\nExperience:\nFrontend Developer, DigitalCo, 2023 - Present\n- React and TypeScript development\n- REST API integration\n- Git version control\n\n[Career Break: 2020 - 2023 - Family caregiving]\n\nJunior Developer, WebAgency, 2018 - 2020\n- HTML, CSS, JavaScript development\n- jQuery and Bootstrap projects\n- Basic PHP backend work\n\nSkills:\nReact, TypeScript, JavaScript, HTML, CSS, Git, REST APIs\n\nEducation:\nBS Information Technology, 2018",
        "job_description": "Frontend Developer needed. 3+ years React experience. TypeScript, Next.js, testing (Jest/RTL), CSS-in-JS, accessibility required.",
        "expected": {
            "keyword_score": {"min": 10, "max": 45},
            "ats_score": {"min": 40, "max": 75},
            "final_score": {"min": 30, "max": 65},
        },
        "notes": "3-year employment gap. React experience exists but interrupted. Missing Next.js, testing, a11y.",
    },
    # ── Contractor/Multiple Short Roles ──
    {
        "id": "B041",
        "name": "Contractor - Many Short Roles",
        "category": "contractor",
        "cv_text": "Jake Morrison\nSoftware Contractor\n\nContact: jake@email.com\n\nExperience:\nPython Developer, ClientA (Contract), Jan 2024 - Mar 2024\n- FastAPI microservice development\n- PostgreSQL query optimization\n\nReact Developer, ClientB (Contract), Sep 2023 - Dec 2023\n- Next.js e-commerce frontend\n- Stripe payment integration\n\nDevOps Engineer, ClientC (Contract), May 2023 - Aug 2023\n- AWS infrastructure setup\n- Docker/Kubernetes deployment\n- Terraform IaC\n\nBackend Developer, ClientD (Contract), Jan 2023 - Apr 2023\n- Node.js REST API development\n- MongoDB data modeling\n\nFull Stack Developer, ClientE (Contract), 2022\n- Django + React application\n- CI/CD pipeline setup\n\nSkills:\nPython, FastAPI, Django, React, Next.js, Node.js, AWS, Docker, Kubernetes, Terraform, PostgreSQL, MongoDB, Git\n\nEducation:\nBS Computer Science, 2021",
        "job_description": "Senior Python Developer. 5+ years Python. Django or FastAPI. PostgreSQL. Docker. AWS. CI/CD. Team leadership preferred.",
        "expected": {
            "keyword_score": {"min": 30, "max": 70},
            "ats_score": {"min": 50, "max": 85},
            "final_score": {"min": 40, "max": 80},
        },
        "notes": "Contractor with many short roles. Skills match but tenure at each role is short.",
    },
    # ── Non-English JD (fully Turkish JD) ──
    {
        "id": "B042",
        "name": "Full Turkish JD + Turkish CV",
        "category": "multilingual",
        "cv_text": "Elif Yilmaz\nYazilim Muhendisi\n\nIletisim: elif.yilmaz@email.com | Ankara\n\nDeneyim:\nKidemli Yazilim Muhendisi, TeknoCo, 2021 - Halen\n- Python ve Django ile web uygulamalari gelistirme\n- PostgreSQL veritabani tasarimi ve optimizasyonu\n- Docker ve Kubernetes ile konteyner yonetimi\n- REST API tasarimi ve dokumantasyonu\n- Git ve CI/CD surec yonetimi\n\nYazilim Muhendisi, StartupTR, 2019 - 2021\n- Flask ile mikroservis mimarisi\n- Redis cache implementasyonu\n- AWS altyapi yonetimi\n\nBeceriler:\nPython, Django, Flask, PostgreSQL, Docker, Kubernetes, AWS, Redis, Git, Linux, REST API\n\nEgitim:\nBilgisayar Muhendisligi Lisans, ODTU, 2019",
        "job_description": "Kidemli Python Gelistirici ariyoruz. Gereksinimler: 4+ yil Python deneyimi. Django veya Flask framework bilgisi. PostgreSQL veritabani yonetimi. Docker ve konteyner teknolojileri. AWS bulut servisleri. CI/CD pipeline kurulumu. REST API tasarimi. Takim calismasina yatkinlik.",
        "expected": {
            "keyword_score": {"min": 35, "max": 80},
            "ats_score": {"min": 40, "max": 80},
            "final_score": {"min": 40, "max": 80},
        },
        "notes": "Both CV and JD fully in Turkish. Technical keywords should still match.",
    },
    # ── Designer applying to Dev role ──
    {
        "id": "B043",
        "name": "UI Designer to Frontend Dev",
        "category": "career_change",
        "cv_text": "Maria Santos\nUI/UX Designer\n\nContact: maria@email.com\n\nExperience:\nSenior UI/UX Designer, DesignStudio, 2020 - Present\n- Designed mobile and web interfaces for 15+ clients\n- Figma, Sketch, Adobe XD prototyping\n- User research and usability testing\n- Design system creation and maintenance\n- Basic HTML/CSS for design handoff\n- Collaborated with development teams\n\nJunior Designer, AgencyCo, 2018 - 2020\n- Visual design for marketing materials\n- Brand identity projects\n- Basic WordPress customization\n\nSkills:\nFigma, Sketch, Adobe XD, HTML, CSS, Design Systems, User Research, Prototyping, WordPress\n\nEducation:\nBA Graphic Design, 2018",
        "job_description": "Frontend Developer. React, TypeScript, CSS-in-JS, responsive design, accessibility, Git, npm, REST APIs. Design background is a plus.",
        "expected": {
            "keyword_score": {"min": 5, "max": 30},
            "ats_score": {"min": 35, "max": 75},
            "final_score": {"min": 25, "max": 60},
        },
        "notes": "Designer transitioning to dev. CSS/design overlap but missing React/TypeScript/Git core skills.",
    },
    # ── Overloaded with certifications ──
    {
        "id": "B044",
        "name": "Certification Heavy CV",
        "category": "certification_heavy",
        "cv_text": "David Kim\nCloud Solutions Architect\n\nContact: david.kim@email.com\n\nCertifications:\nAWS Solutions Architect Professional (2024)\nAWS DevOps Engineer Professional (2023)\nAWS Security Specialty (2023)\nGoogle Cloud Professional Architect (2023)\nAzure Solutions Architect Expert (2022)\nKubernetes Administrator (CKA) (2022)\nTerraform Associate (2022)\nCISSP (2021)\n\nExperience:\nCloud Architect, CloudCorp, 2021 - Present\n- Multi-cloud architecture design\n- Infrastructure as Code with Terraform\n- Kubernetes cluster management\n\nSkills:\nAWS, GCP, Azure, Terraform, Kubernetes, Docker, Python, Linux\n\nEducation:\nBS Computer Science, 2020",
        "job_description": "Cloud Engineer needed. AWS experience required. Terraform, Docker, Kubernetes. Python scripting. CI/CD. Linux administration.",
        "expected": {
            "keyword_score": {"min": 35, "max": 75},
            "ats_score": {"min": 50, "max": 85},
            "final_score": {"min": 45, "max": 80},
        },
        "notes": "Heavy on certifications, lighter on experience details. Should still score well on keyword match.",
    },
    # ── Student with only projects ──
    {
        "id": "B045",
        "name": "Student - Projects Only",
        "category": "entry_level",
        "cv_text": "Emma Wilson\nComputer Science Student\n\nContact: emma.w@email.com | GitHub: github.com/emmaw\n\nProjects:\nE-Commerce Platform (2024)\n- Full-stack app with React frontend and Node.js/Express backend\n- MongoDB database, JWT authentication\n- Stripe payment integration\n- Deployed on AWS EC2\n\nChat Application (2024)\n- Real-time messaging with Socket.io\n- React frontend with TypeScript\n- PostgreSQL database\n\nWeather Dashboard (2023)\n- React app consuming OpenWeather API\n- Chart.js data visualization\n- Responsive design\n\nSkills:\nJavaScript, TypeScript, React, Node.js, Express, MongoDB, PostgreSQL, AWS, Docker, Git\n\nEducation:\nBS Computer Science (Expected 2025), State University\nGPA: 3.7/4.0",
        "job_description": "Junior Full Stack Developer. JavaScript, React, Node.js required. MongoDB or PostgreSQL. Git. Docker is a plus.",
        "expected": {
            "keyword_score": {"min": 35, "max": 75},
            "ats_score": {"min": 35, "max": 75},
            "final_score": {"min": 35, "max": 75},
        },
        "notes": "Student with strong projects but no work experience. Skills match the JD well.",
    },
    # ── Completely empty sections ──
    {
        "id": "B046",
        "name": "Sparse CV - Only Name and Skills",
        "category": "minimal",
        "cv_text": "Tom Brown\n\nSkills: Python, SQL, Excel\n\nEmail: tom@email.com",
        "job_description": "Data Analyst. Python, SQL, Tableau, Excel, statistics, data visualization required.",
        "expected": {
            "keyword_score": {"min": 10, "max": 50},
            "ats_score": {"min": 10, "max": 40},
            "final_score": {"min": 10, "max": 45},
        },
        "notes": "Extremely sparse CV with no experience or education. ATS should flag heavily.",
    },
    # ── Management role mismatch ──
    {
        "id": "B047",
        "name": "Engineering Manager vs IC Dev",
        "category": "seniority_mismatch",
        "cv_text": "Robert Zhang\nEngineering Manager\n\nContact: robert.z@email.com\n\nExperience:\nEngineering Manager, BigCorp, 2021 - Present\n- Managing 3 teams (15 engineers total)\n- Roadmap planning and OKR setting\n- Budget management ($2M annual)\n- Hiring: conducted 100+ interviews\n- Stakeholder management with C-suite\n- Sprint planning and retrospectives\n\nSenior Software Engineer, MidCorp, 2018 - 2021\n- Python/Django backend development\n- AWS infrastructure\n- Code reviews and mentoring\n\nSkills:\nPeople Management, Strategic Planning, Python, Django, AWS, Agile, Scrum\n\nEducation:\nMS Computer Science, 2018",
        "job_description": "Senior Python Developer. Hands-on coding daily. Python, FastAPI, PostgreSQL, Docker, Kubernetes, microservices. Must write production code.",
        "expected": {
            "keyword_score": {"min": 10, "max": 40},
            "ats_score": {"min": 45, "max": 80},
            "final_score": {"min": 30, "max": 65},
        },
        "notes": "Manager applying for IC role. Python/Django overlap but missing hands-on tech stack.",
    },
    # ── Same industry different role ──
    {
        "id": "B048",
        "name": "Backend Dev vs Frontend JD",
        "category": "role_mismatch",
        "cv_text": "Sarah Lee\nBackend Developer\n\nContact: sarah.lee@email.com\n\nExperience:\nSenior Backend Developer, APICorp, 2020 - Present\n- Python/FastAPI microservices\n- PostgreSQL and Redis\n- Kafka event streaming\n- Docker/Kubernetes\n- AWS (ECS, RDS, SQS)\n\nSkills:\nPython, FastAPI, PostgreSQL, Redis, Kafka, Docker, Kubernetes, AWS, Git, Linux\n\nEducation:\nBS Computer Science, 2019",
        "job_description": "Senior Frontend Developer. React, TypeScript, Next.js, CSS-in-JS, testing (Jest/Cypress), accessibility, responsive design, GraphQL, state management (Redux/Zustand).",
        "expected": {
            "keyword_score": {"min": 0, "max": 20},
            "ats_score": {"min": 45, "max": 80},
            "final_score": {"min": 25, "max": 60},
        },
        "notes": "Backend dev vs Frontend JD. Almost zero keyword overlap despite being in same industry.",
    },
    # ── CV with GitHub/Portfolio links ──
    {
        "id": "B049",
        "name": "Portfolio-Heavy CV",
        "category": "portfolio",
        "cv_text": "Nina Patel\nFull Stack Developer\n\nContact: nina@email.com\nGitHub: github.com/ninapatel (50+ repos, 2K+ stars)\nPortfolio: ninapatel.dev\nLinkedIn: linkedin.com/in/ninapatel\n\nOpen Source:\n- Contributor to React (3 merged PRs)\n- Maintainer of express-validator (500+ stars)\n- Created next-auth-helpers (200+ stars)\n\nExperience:\nFull Stack Developer, OpenSourceCo, 2021 - Present\n- React/Next.js frontend development\n- Node.js/Express backend APIs\n- TypeScript throughout the stack\n- PostgreSQL and MongoDB\n- Docker containerization\n- AWS deployment\n\nSkills:\nReact, Next.js, TypeScript, Node.js, Express, PostgreSQL, MongoDB, Docker, AWS, Git\n\nEducation:\nBS Computer Science, 2021",
        "job_description": "Senior Full Stack Developer. React, Next.js, TypeScript, Node.js, PostgreSQL, Docker, AWS. Open source contribution is highly valued.",
        "expected": {
            "keyword_score": {"min": 40, "max": 85},
            "ats_score": {"min": 55, "max": 90},
            "final_score": {"min": 50, "max": 85},
        },
        "notes": "Strong portfolio and open source. High keyword match with JD.",
    },
    # ── Duplicate/repeated content in CV ──
    {
        "id": "B050",
        "name": "Repetitive CV Content",
        "category": "edge_case",
        "cv_text": "Mike Johnson\nDeveloper\n\nSkills: Python, Python programming, Python development, Python scripting, Python coding\nMore Skills: Django, Django framework, Django web development\nAdditional: SQL, SQL databases, SQL queries, PostgreSQL, PostgreSQL database\n\nExperience:\nPython Developer, Company, 2022 - Present\n- Python development\n- Django development\n- SQL database work\n\nEducation:\nCS Degree, 2022",
        "job_description": "Python Developer. Python, Django, PostgreSQL, Docker, Git required.",
        "expected": {
            "keyword_score": {"min": 20, "max": 65},
            "ats_score": {"min": 30, "max": 70},
            "final_score": {"min": 25, "max": 65},
        },
        "notes": "Repetitive/padded CV. Should not get inflated scores from keyword stuffing variation.",
    },
]

with open(DS, "r", encoding="utf-8") as f:
    data = json.load(f)

# Check for ID conflicts
existing_ids = {e["id"] for e in data["entries"]}
for entry in NEW:
    if entry["id"] in existing_ids:
        print(f"WARNING: Duplicate ID {entry['id']}, skipping")
        continue
    data["entries"].append(entry)

data["version"] = "3.0.0"

with open(DS, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Dataset: {len(data['entries'])} entries")
cats = {}
for e in data["entries"]:
    cats[e["category"]] = cats.get(e["category"], 0) + 1
for cat, count in sorted(cats.items()):
    print(f"  {cat}: {count}")
