"""Batch 2: AI-generated (5) + Long CV (5)."""

import json, pathlib

DS = pathlib.Path(__file__).resolve().parent.parent / "tests/benchmark/benchmark_dataset.json"

NEW = [
    # ── AI-GENERATED (5) ──
    {
        "id": "B061",
        "name": "AI Generated - Generic Dev",
        "category": "ai_generated",
        "cv_text": "John Smith\nHighly Motivated Software Engineer\n\nAs a results-driven and innovative software engineer with a proven track record of delivering cutting-edge solutions, I bring a wealth of experience in developing robust, scalable applications. My passion for technology and commitment to excellence drive me to continuously push the boundaries of what's possible.\n\nProfessional Experience:\nSenior Software Engineer, InnovateTech Solutions, 2020 - Present\n- Spearheaded the development of mission-critical applications leveraging Python and Django\n- Orchestrated seamless deployment pipelines utilizing Docker and Kubernetes\n- Championed best practices in code quality through comprehensive code reviews\n- Fostered cross-functional collaboration to deliver transformative solutions\n\nSkills: Python, Django, Docker, Kubernetes, AWS, PostgreSQL, Git, Agile, CI/CD\nEducation: Bachelor of Science in Computer Science, 2019",
        "job_description": "Python Developer. Django, PostgreSQL, Docker, AWS. 3+ years. Agile environment.",
        "expected": {
            "keyword_score": {"min": 30, "max": 80},
            "ats_score": {"min": 50, "max": 85},
            "final_score": {"min": 45, "max": 80},
        },
    },
    {
        "id": "B062",
        "name": "AI Generated - Data Scientist",
        "category": "ai_generated",
        "cv_text": "Emily Johnson\nData Science Professional\n\nDynamic and analytical data science professional with extensive experience in leveraging advanced machine learning algorithms and statistical methodologies to extract actionable insights from complex datasets. Demonstrated expertise in translating business requirements into data-driven solutions that maximize organizational value.\n\nProfessional Experience:\nLead Data Scientist, DataDriven Corp, 2019 - Present\n- Engineered sophisticated machine learning models achieving unprecedented accuracy metrics\n- Pioneered innovative approaches to natural language processing and computer vision\n- Orchestrated end-to-end data pipelines processing petabytes of structured data\n\nSkills: Python, TensorFlow, PyTorch, Scikit-learn, SQL, Spark, AWS SageMaker, Pandas, NumPy\nEducation: Master of Science in Data Science, MIT, 2019",
        "job_description": "Data Scientist. Python, TensorFlow/PyTorch, SQL, ML pipelines, NLP. 3+ years.",
        "expected": {
            "keyword_score": {"min": 25, "max": 75},
            "ats_score": {"min": 50, "max": 85},
            "final_score": {"min": 45, "max": 80},
        },
    },
    {
        "id": "B063",
        "name": "AI Generated - Product Manager",
        "category": "ai_generated",
        "cv_text": "Michael Williams\nVisionary Product Manager\n\nTransformative product leader with an exceptional ability to identify market opportunities and translate them into groundbreaking product strategies. Proven expertise in driving cross-functional alignment and delivering products that delight customers and exceed business objectives.\n\nProfessional Experience:\nSenior Product Manager, TechVision Inc, 2018 - Present\n- Conceptualized and launched revolutionary products generating $50M+ in annual revenue\n- Cultivated strategic partnerships with industry-leading technology providers\n- Spearheaded agile transformation initiatives across multiple product teams\n\nSkills: Product Strategy, Agile, Scrum, JIRA, Data Analytics, A/B Testing, User Research\nEducation: MBA, Stanford Graduate School of Business, 2018",
        "job_description": "Product Manager. Agile/Scrum, data-driven decisions, user research, roadmap planning. Technical background preferred.",
        "expected": {
            "keyword_score": {"min": 20, "max": 65},
            "ats_score": {"min": 45, "max": 80},
            "final_score": {"min": 40, "max": 75},
        },
    },
    {
        "id": "B064",
        "name": "AI Generated - DevOps",
        "category": "ai_generated",
        "cv_text": "David Brown\nDevOps Architect & Cloud Infrastructure Specialist\n\nInnovative DevOps architect with a distinguished career in designing and implementing enterprise-grade cloud infrastructure solutions. Recognized thought leader in containerization, infrastructure as code, and continuous delivery methodologies.\n\nProfessional Experience:\nPrincipal DevOps Engineer, CloudScale Solutions, 2019 - Present\n- Architected revolutionary multi-cloud infrastructure serving millions of concurrent users\n- Pioneered zero-downtime deployment strategies reducing incident rates by 99.9%\n- Mentored and developed a world-class team of 12 infrastructure engineers\n\nSkills: AWS, GCP, Azure, Terraform, Kubernetes, Docker, Jenkins, Ansible, Prometheus, Grafana\nEducation: BS Computer Engineering, Georgia Tech, 2018",
        "job_description": "DevOps Engineer. AWS, Terraform, Kubernetes, Docker, CI/CD, monitoring. Infrastructure as code.",
        "expected": {
            "keyword_score": {"min": 35, "max": 80},
            "ats_score": {"min": 50, "max": 85},
            "final_score": {"min": 45, "max": 80},
        },
    },
    {
        "id": "B065",
        "name": "AI Generated - Cybersecurity",
        "category": "ai_generated",
        "cv_text": "Jessica Davis\nCybersecurity Expert & Information Security Leader\n\nAccomplished cybersecurity professional with an unwavering commitment to safeguarding organizational assets against evolving threat landscapes. Extensive experience in implementing comprehensive security frameworks and leading incident response operations.\n\nProfessional Experience:\nChief Information Security Officer, SecureNet Corp, 2018 - Present\n- Orchestrated enterprise-wide security transformation reducing vulnerabilities by 95%\n- Implemented cutting-edge zero-trust architecture across global infrastructure\n- Led crisis management during critical security incidents with zero data loss\n\nSkills: CISSP, CEH, Penetration Testing, SIEM, Incident Response, ISO 27001, NIST, Firewall, IDS/IPS\nEducation: MS Cybersecurity, Carnegie Mellon, 2017",
        "job_description": "Security Engineer. Penetration testing, SIEM, incident response, cloud security, compliance (ISO 27001/NIST).",
        "expected": {
            "keyword_score": {"min": 25, "max": 70},
            "ats_score": {"min": 50, "max": 85},
            "final_score": {"min": 40, "max": 80},
        },
    },
    # ── LONG CV 3-5 PAGES (5) ──
    {
        "id": "B066",
        "name": "Long CV - Senior Architect",
        "category": "long_cv",
        "cv_text": "Alexander Thompson\nPrincipal Software Architect\nEmail: alex.t@email.com | Phone: +1-555-0101 | LinkedIn: linkedin.com/in/alexthompson | GitHub: github.com/alexthompson\n\nProfessional Summary:\nSeasoned software architect with 15+ years of experience designing and implementing enterprise-scale distributed systems. Deep expertise in cloud-native architectures, microservices, and domain-driven design.\n\nExperience:\n\nPrincipal Architect, MegaCorp Technologies, 2020 - Present\n- Designed and implemented event-driven microservices architecture serving 50M+ daily active users\n- Led migration from monolith to microservices reducing deployment time from 2 weeks to 2 hours\n- Established architectural decision records and technical governance processes\n- Mentored 25+ engineers across 5 teams on distributed systems best practices\n- Reduced infrastructure costs by 40% through optimization and right-sizing\n- Implemented chaos engineering practices improving system resilience by 300%\n\nSenior Software Architect, TechGiant Inc, 2017 - 2020\n- Architected real-time data processing pipeline handling 1M+ events per second\n- Designed multi-region active-active deployment strategy with 99.99% uptime\n- Led technical due diligence for 3 acquisitions worth $200M+\n- Created company-wide API design standards adopted by 15+ teams\n- Built internal developer platform reducing onboarding time by 60%\n\nLead Software Engineer, InnoSoft Solutions, 2014 - 2017\n- Led team of 12 engineers building cloud-native SaaS platform\n- Implemented CQRS and event sourcing patterns for financial transaction processing\n- Designed and deployed Kubernetes clusters across AWS and GCP\n- Established CI/CD pipelines with automated testing achieving 95% code coverage\n\nSoftware Engineer, StartupXYZ, 2010 - 2014\n- Full-stack development with Java/Spring and Angular\n- Database design and optimization for PostgreSQL and MongoDB\n- Integration with third-party APIs and payment processors\n\nJunior Developer, CodeFactory, 2008 - 2010\n- Web application development with PHP and MySQL\n- Frontend development with HTML, CSS, JavaScript\n\nTechnical Skills:\nLanguages: Java, Python, Go, TypeScript, Kotlin, Scala\nFrameworks: Spring Boot, FastAPI, Django, React, Angular, Node.js\nCloud: AWS (ECS, EKS, Lambda, DynamoDB, SQS, SNS, CloudFormation), GCP, Azure\nData: PostgreSQL, MongoDB, Cassandra, Redis, Elasticsearch, Kafka, RabbitMQ\nInfrastructure: Kubernetes, Docker, Terraform, Ansible, ArgoCD\nPractices: DDD, CQRS, Event Sourcing, TDD, Microservices, API Design\n\nCertifications:\n- AWS Solutions Architect Professional (2023)\n- Google Cloud Professional Architect (2022)\n- Certified Kubernetes Administrator (2021)\n- TOGAF 9 Certified (2020)\n\nEducation:\nMS Computer Science, Stanford University, 2008\nBS Computer Science, UC Berkeley, 2006\n\nPublications:\n- 'Scaling Microservices at MegaCorp' - InfoQ, 2023\n- 'Event-Driven Architecture Patterns' - O'Reilly Media, 2022\n\nSpeaking:\n- KubeCon 2023: 'Zero-Downtime Migrations at Scale'\n- QCon 2022: 'Building Resilient Distributed Systems'",
        "job_description": "Principal Software Architect. 10+ years experience. Microservices, cloud-native, Kubernetes, AWS. Team leadership. DDD, event-driven architecture.",
        "expected": {
            "keyword_score": {"min": 35, "max": 85},
            "ats_score": {"min": 55, "max": 90},
            "final_score": {"min": 55, "max": 90},
        },
    },
    {
        "id": "B067",
        "name": "Long CV - Engineering Director",
        "category": "long_cv",
        "cv_text": "Patricia Chen\nVP of Engineering\npatchen@email.com | San Francisco, CA\n\nSummary:\n20+ years in software engineering leadership. Built and scaled engineering organizations from 10 to 200+ engineers. Expert in organizational design, technical strategy, and delivery excellence.\n\nExperience:\n\nVP Engineering, ScaleUp Inc, 2019 - Present\n- Built engineering org from 30 to 180 engineers across 6 offices\n- Established engineering career ladder and promotion framework\n- Reduced time-to-market by 50% through platform engineering investments\n- Led $15M annual engineering budget with 20% YoY efficiency improvement\n- Implemented OKR framework achieving 85% goal completion rate\n\nSenior Director Engineering, BigTech Corp, 2015 - 2019\n- Managed 8 engineering managers and 60+ engineers\n- Delivered 3 major product launches generating $100M+ revenue\n- Established SRE practice reducing incidents by 70%\n- Led technical interviews for 200+ candidates\n\nEngineering Manager, MidSize Tech, 2012 - 2015\n- Managed 3 teams building consumer-facing products\n- Introduced agile practices increasing velocity by 40%\n- Built CI/CD infrastructure from scratch\n\nSenior Software Engineer, StartupABC, 2008 - 2012\n- Full-stack development with Python/Django and React\n- AWS infrastructure management\n- Database design PostgreSQL\n\nSoftware Engineer, WebAgency, 2004 - 2008\n- PHP, MySQL web development\n- Client project delivery\n\nSkills:\nLeadership: Org Design, Hiring, Mentoring, OKRs, Budget Management\nTechnical: Python, Java, AWS, Kubernetes, System Design\nMethodologies: Agile, Scrum, Kanban, SAFe\n\nEducation:\nMS Computer Science, MIT, 2004\nBS Computer Science, CalTech, 2002",
        "job_description": "VP of Engineering. 15+ years. Engineering org scaling. Budget management. Technical strategy. Cloud infrastructure knowledge.",
        "expected": {
            "keyword_score": {"min": 20, "max": 65},
            "ats_score": {"min": 55, "max": 90},
            "final_score": {"min": 45, "max": 85},
        },
    },
    {
        "id": "B068",
        "name": "Long CV - Full Stack Senior",
        "category": "long_cv",
        "cv_text": "Roberto Martinez\nSenior Full Stack Engineer\nroberto@email.com | GitHub: github.com/robertom\n\nSummary:\n12 years of full-stack development experience across startups and enterprises.\n\nExperience:\n\nSenior Full Stack Engineer, FinTech Pro, 2020 - Present\n- React/Next.js frontend with TypeScript\n- Node.js/Express microservices\n- PostgreSQL and Redis data layer\n- AWS deployment (ECS, RDS, ElastiCache)\n- Stripe payment integration processing $5M/month\n- Led frontend architecture migration to Next.js 14\n\nFull Stack Developer, E-Commerce Giant, 2017 - 2020\n- Vue.js storefront serving 2M monthly visitors\n- Python/FastAPI backend services\n- MongoDB and Elasticsearch\n- Docker/Kubernetes deployment\n- Performance optimization reducing load time by 60%\n\nWeb Developer, Digital Agency, 2014 - 2017\n- React and Angular SPAs for 20+ clients\n- Node.js REST APIs\n- MySQL and PostgreSQL databases\n- AWS S3, CloudFront CDN setup\n\nJunior Developer, LocalCo, 2012 - 2014\n- PHP/Laravel backend development\n- jQuery frontend work\n- Basic DevOps (Linux, Nginx)\n\nSkills:\nFrontend: React, Next.js, Vue.js, TypeScript, Tailwind CSS\nBackend: Node.js, Python, FastAPI, Express, Django\nDatabase: PostgreSQL, MongoDB, Redis, Elasticsearch\nCloud: AWS, Docker, Kubernetes, CI/CD\n\nEducation:\nBS Software Engineering, 2012",
        "job_description": "Senior Full Stack Developer. React/Next.js, Node.js, PostgreSQL, AWS. 8+ years. E-commerce experience preferred.",
        "expected": {
            "keyword_score": {"min": 35, "max": 80},
            "ats_score": {"min": 55, "max": 90},
            "final_score": {"min": 50, "max": 85},
        },
    },
    {
        "id": "B069",
        "name": "Long CV - ML Engineer",
        "category": "long_cv",
        "cv_text": "Dr. Yuki Tanaka\nMachine Learning Engineer\nyuki.t@email.com | Scholar: scholar.google.com/yuki\n\nSummary:\nML engineer and researcher with 10+ years experience in NLP, computer vision, and MLOps. Published 15+ papers in top venues.\n\nExperience:\n\nStaff ML Engineer, AI Startup, 2021 - Present\n- Built production NLP pipeline processing 10M documents daily\n- Fine-tuned LLMs (GPT, LLaMA) for domain-specific applications\n- Designed RAG system with vector databases (Pinecone, Weaviate)\n- MLflow experiment tracking and model registry\n- Reduced model inference latency by 70% with quantization\n\nSenior ML Engineer, BigTech AI, 2018 - 2021\n- Computer vision models for autonomous driving\n- PyTorch model training on multi-GPU clusters\n- A/B testing framework for model deployments\n- Mentored 5 junior ML engineers\n\nResearch Scientist, University Lab, 2015 - 2018\n- Published 8 papers in NeurIPS, ICML, ACL\n- Developed novel attention mechanisms\n- Teaching assistant for ML and NLP courses\n\nSkills:\nML: PyTorch, TensorFlow, Scikit-learn, Hugging Face, LangChain\nNLP: Transformers, BERT, GPT, RAG, Vector DBs\nMLOps: MLflow, Kubeflow, AWS SageMaker, Docker\nLanguages: Python, C++, Julia\n\nEducation:\nPhD Computer Science (ML focus), Tokyo University, 2015\nMS Computer Science, Kyoto University, 2012",
        "job_description": "ML Engineer. PyTorch/TensorFlow, NLP, LLMs, MLOps, Python. Production ML systems. 5+ years.",
        "expected": {
            "keyword_score": {"min": 30, "max": 80},
            "ats_score": {"min": 55, "max": 90},
            "final_score": {"min": 50, "max": 85},
        },
    },
    {
        "id": "B070",
        "name": "Long CV - Platform Engineer",
        "category": "long_cv",
        "cv_text": "Daniel O'Brien\nPlatform Engineer\ndaniel@email.com\n\nSummary:\n8 years building internal developer platforms and infrastructure.\n\nExperience:\n\nSenior Platform Engineer, ScaleCo, 2021 - Present\n- Built internal developer platform serving 200+ engineers\n- Kubernetes multi-cluster management with ArgoCD\n- Terraform modules for self-service infrastructure\n- Observability stack (Datadog, PagerDuty, Grafana)\n- Reduced deployment time from 30 min to 3 min\n\nDevOps Engineer, CloudFirst, 2018 - 2021\n- AWS infrastructure automation\n- CI/CD with GitHub Actions and Jenkins\n- Docker container orchestration\n- Security scanning and compliance automation\n\nSystems Administrator, EnterpriseCo, 2016 - 2018\n- Linux server administration (Ubuntu, CentOS)\n- Network configuration and monitoring\n- Backup and disaster recovery\n\nSkills:\nPlatform: Kubernetes, Docker, Terraform, Helm, ArgoCD\nCloud: AWS, GCP\nCI/CD: GitHub Actions, Jenkins, GitLab CI\nMonitoring: Datadog, Grafana, Prometheus, PagerDuty\nLanguages: Go, Python, Bash\n\nEducation:\nBS Information Systems, 2016",
        "job_description": "Platform Engineer. Kubernetes, Terraform, AWS, CI/CD, observability. Internal developer platform experience. Go or Python.",
        "expected": {
            "keyword_score": {"min": 35, "max": 80},
            "ats_score": {"min": 50, "max": 85},
            "final_score": {"min": 50, "max": 85},
        },
    },
]

with open(DS, "r", encoding="utf-8") as f:
    data = json.load(f)
existing = {e["id"] for e in data["entries"]}
added = 0
for e in NEW:
    if e["id"] not in existing:
        data["entries"].append(e)
        added += 1
with open(DS, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f"Added {added}, total: {len(data['entries'])}")
