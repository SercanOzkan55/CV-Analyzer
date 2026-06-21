"""Expand benchmark dataset with 20 new diverse entries."""

import json, pathlib

DS = pathlib.Path(__file__).resolve().parent.parent / "tests/benchmark/benchmark_dataset.json"

NEW = [
    {
        "id": "B011",
        "name": "Bad English CV - Grammar Errors",
        "category": "bad_english",
        "cv_text": "Experinced sofware devloper with 3 yers of experiense in Pyhton and Jva. I was working at company for make web aplicatons. I have knowlege of SQL and Git. I am good team playr and fast lerner.\n\nSkils:\nPyhton, Jva, SQL, Git, HTML\n\nEducasion:\nBachelor Computar Sciens\nUniversity 2022",
        "job_description": "Python Developer needed. Requirements: Python, SQL, Git, teamwork skills.",
        "expected": {
            "keyword_score": {"min": 15, "max": 60},
            "ats_score": {"min": 15, "max": 50},
            "final_score": {"min": 15, "max": 55},
        },
        "notes": "CV full of typos/misspellings. Fuzzy matching should catch some but ATS structure very weak.",
    },
    {
        "id": "B012",
        "name": "Typo Heavy CV - Technical Terms",
        "category": "typo_heavy",
        "cv_text": "Alex Dev\nSoftware Engineer\n\nContact: alex@email.com\n\nSummary:\n3 years building web apps with Pythn, Djnago, and PostgrSQL.\n\nExperience:\nSoftware Engineer\nTechCo, 2022 - Present\n- Built REST APis using Djnago REST Framwork\n- Managed Dockerr containers and Kuberntes deployments\n- Used Jenknins for CI/CD pipelnes\n\nSkills:\nPythn, Djnago, PostgrSQL, Dockerr, Kuberntes, Git, AWS",
        "job_description": "Python Developer with Django, PostgreSQL, Docker, Kubernetes experience.",
        "expected": {
            "keyword_score": {"min": 20, "max": 65},
            "ats_score": {"min": 40, "max": 80},
            "final_score": {"min": 30, "max": 70},
        },
        "notes": "Technical terms misspelled. Tests fuzzy matching on common typos.",
    },
    {
        "id": "B013",
        "name": "AI-Generated CV - Verbose",
        "category": "ai_generated",
        "cv_text": "Innovative and results-driven software engineering professional with a proven track record of delivering cutting-edge solutions leveraging state-of-the-art technologies. Adept at collaborating with cross-functional teams to drive digital transformation initiatives and optimize business processes through strategic technology implementation.\n\nCore Competencies:\nStrategic Technology Leadership | Agile Methodologies | Full-Stack Development | Cloud Architecture | Data-Driven Decision Making | Stakeholder Management\n\nProfessional Experience:\nSenior Software Engineer\nInnovaTech Solutions, 2021 - Present\n- Spearheaded the development of a next-generation microservices platform\n- Orchestrated seamless migration of legacy systems to cloud-native architecture\n- Championed best practices in code quality and automated testing\n\nSkills:\nPython, JavaScript, React, Node.js, AWS, Docker, Kubernetes, PostgreSQL, MongoDB, Redis, GraphQL, TypeScript, CI/CD, Agile, Scrum",
        "job_description": "Senior Full Stack Developer. Python, React, Node.js, AWS, Docker required.",
        "expected": {
            "keyword_score": {"min": 50, "max": 90},
            "ats_score": {"min": 55, "max": 90},
            "final_score": {"min": 55, "max": 90},
        },
        "notes": "AI-generated verbose CV. High keyword match but buzzword-heavy content.",
    },
    {
        "id": "B014",
        "name": "Finance Analyst CV vs Finance JD",
        "category": "finance",
        "cv_text": "Emma Chen\nFinancial Analyst\n\nContact: emma.chen@email.com | +1 555-0142\n\nSummary:\n5 years in financial analysis, risk modeling, and portfolio management at top-tier investment banks.\n\nExperience:\nSenior Financial Analyst\nGoldman Sachs, New York, 2021 - Present\n- Built DCF and LBO models for M&A transactions worth $2B+\n- Led quarterly earnings analysis for 15 portfolio companies\n- Developed risk assessment frameworks using VBA and Python\n\nFinancial Analyst\nJP Morgan, New York, 2019 - 2021\n- Created financial reports and dashboards using Excel and Tableau\n- Performed variance analysis and budget forecasting\n\nSkills:\nFinancial Modeling, DCF, LBO, Excel, VBA, Python, SQL, Tableau, Bloomberg Terminal, Risk Analysis\n\nEducation:\nMBA Finance, Wharton, 2019\nBS Economics, NYU, 2017\n\nCertifications:\nCFA Level III, FRM",
        "job_description": "Financial Analyst needed. Requirements: Financial modeling, DCF/LBO analysis, Excel, VBA, Python, SQL. Experience with Bloomberg Terminal and risk management. CFA preferred.",
        "expected": {
            "keyword_score": {"min": 55, "max": 95},
            "ats_score": {"min": 70, "max": 95},
            "final_score": {"min": 65, "max": 95},
        },
        "notes": "Finance domain CV vs matching Finance JD. Good keyword overlap.",
    },
    {
        "id": "B015",
        "name": "Marketing Manager vs Dev JD",
        "category": "cross_sector",
        "cv_text": "Lisa Park\nDigital Marketing Manager\n\nContact: lisa@email.com\n\nSummary:\n7 years in digital marketing, SEO, and brand strategy.\n\nExperience:\nDigital Marketing Manager, BrandCo, 2020-Present\n- Managed $5M annual ad budget across Google, Facebook, LinkedIn\n- Increased organic traffic by 200% through SEO optimization\n- Led team of 6 content creators and designers\n\nSkills:\nSEO, SEM, Google Analytics, Facebook Ads, Content Strategy, Copywriting, HubSpot, Salesforce, A/B Testing, Email Marketing\n\nEducation:\nBA Marketing, UCLA, 2017",
        "job_description": "Backend Python Developer. Requirements: Python, Django, PostgreSQL, Docker, REST APIs, microservices.",
        "expected": {
            "keyword_score": {"min": 0, "max": 15},
            "ats_score": {"min": 45, "max": 80},
            "final_score": {"min": 25, "max": 60},
        },
        "notes": "Complete sector mismatch. Marketing vs Backend Dev. Near-zero keyword overlap.",
    },
    {
        "id": "B016",
        "name": "Same CV Different JD - DevOps",
        "category": "same_cv_diff_jd",
        "cv_text": "John Smith\nSenior Python Developer\n\nContact:\nEmail: john.smith@email.com\nPhone: +1 (555) 123-4567\n\nSkills:\nPython, JavaScript, SQL, Django, Flask, React, Node.js, PostgreSQL, MongoDB, Redis, AWS, Docker, Kubernetes, Terraform, Git, Jenkins, Linux\n\nExperience:\nSenior Python Developer, TechCorp, 2020 - Present\n- Led microservices architecture serving 1M+ users\n- Built ML pipelines using Python, TensorFlow, AWS\n- Reduced deployment time by 60% through CI/CD\n\nEducation:\nMS Computer Science, Stanford, 2015",
        "job_description": "DevOps Engineer needed. Requirements: Terraform, Kubernetes, Docker, AWS, CI/CD pipelines, Jenkins, Linux, monitoring (Prometheus/Grafana), infrastructure as code. 5+ years experience.",
        "expected": {
            "keyword_score": {"min": 25, "max": 65},
            "ats_score": {"min": 55, "max": 85},
            "final_score": {"min": 40, "max": 80},
        },
        "notes": "B001 CV against DevOps JD. Partial overlap (Docker/K8s/AWS/Jenkins) but missing monitoring/IaC focus.",
    },
    {
        "id": "B017",
        "name": "Same CV Different JD - Data Science",
        "category": "same_cv_diff_jd",
        "cv_text": "John Smith\nSenior Python Developer\n\nContact:\nEmail: john.smith@email.com\nPhone: +1 (555) 123-4567\n\nSkills:\nPython, JavaScript, SQL, Django, Flask, React, Node.js, PostgreSQL, MongoDB, Redis, AWS, Docker, Kubernetes, Terraform, Git, Jenkins, Linux\n\nExperience:\nSenior Python Developer, TechCorp, 2020 - Present\n- Led microservices architecture serving 1M+ users\n- Built ML pipelines using Python, TensorFlow, AWS\n\nEducation:\nMS Computer Science, Stanford, 2015",
        "job_description": "Data Scientist needed. Requirements: Python, R, statistical modeling, machine learning, TensorFlow/PyTorch, pandas, numpy, scikit-learn, data visualization, Jupyter notebooks, A/B testing, SQL.",
        "expected": {
            "keyword_score": {"min": 15, "max": 50},
            "ats_score": {"min": 50, "max": 85},
            "final_score": {"min": 35, "max": 70},
        },
        "notes": "B001 CV against Data Science JD. Python/SQL/TensorFlow overlap but missing R, stats, viz tools.",
    },
    {
        "id": "B018",
        "name": "Completely Irrelevant - Chef vs Developer",
        "category": "irrelevant",
        "cv_text": "Marco Rossi\nExecutive Chef\n\nContact: marco@email.com\n\nSummary:\n15 years in fine dining, menu creation, and kitchen management.\n\nExperience:\nExecutive Chef, La Bella Vita, 2018 - Present\n- Managed kitchen staff of 20\n- Created seasonal menus reducing food costs by 15%\n- Maintained 4.8 star rating on Yelp\n\nSkills:\nMenu Planning, Kitchen Management, Food Safety, HACCP, Budgeting, Team Leadership, French Cuisine, Italian Cuisine\n\nEducation:\nCulinary Arts Diploma, Le Cordon Bleu, 2009",
        "job_description": "Senior Python Developer with Django, REST APIs, PostgreSQL, Docker, Kubernetes, AWS experience required.",
        "expected": {
            "keyword_score": {"min": 0, "max": 10},
            "ats_score": {"min": 40, "max": 75},
            "final_score": {"min": 20, "max": 55},
        },
        "notes": "Zero domain overlap. Chef CV vs Python dev JD. Tests complete mismatch handling.",
    },
    {
        "id": "B019",
        "name": "German CV - Multilingual Test",
        "category": "multilingual",
        "cv_text": "Maximilian Weber\nSoftwareentwickler\n\nKontakt:\nE-Mail: max.weber@email.de\nTelefon: +49 176 12345678\nStandort: Berlin, Deutschland\n\nBerufserfahrung:\nSenior Softwareentwickler\nTechGmbH, Berlin, 2020 - Heute\n- Entwicklung von Microservices mit Java und Spring Boot\n- Implementierung von REST APIs und GraphQL Schnittstellen\n- Containerisierung mit Docker und Kubernetes\n\nKenntnisse:\nJava, Spring Boot, Python, Docker, Kubernetes, PostgreSQL, MongoDB, Git, CI/CD, Agile\n\nAusbildung:\nMaster Informatik, TU Berlin, 2020",
        "job_description": "Java Developer needed. Spring Boot, Docker, Kubernetes, PostgreSQL, REST APIs, microservices experience required.",
        "expected": {
            "keyword_score": {"min": 30, "max": 75},
            "ats_score": {"min": 45, "max": 80},
            "final_score": {"min": 35, "max": 75},
        },
        "notes": "German CV text against English JD. Technical terms should match despite language difference.",
    },
    {
        "id": "B020",
        "name": "Empty Skills Section",
        "category": "edge_case",
        "cv_text": "Tom Baker\nDeveloper\n\nContact: tom@email.com\n\nExperience:\nDeveloper, SomeCo, 2023 - Present\n- Worked on various projects\n- Used different technologies\n\nSkills:\n\nEducation:\nBS Computer Science, 2023",
        "job_description": "Python Developer needed. Python, Django, PostgreSQL required.",
        "expected": {
            "keyword_score": {"min": 0, "max": 20},
            "ats_score": {"min": 20, "max": 55},
            "final_score": {"min": 10, "max": 45},
        },
        "notes": "CV with empty skills section and vague experience. Very low scores expected.",
    },
    {
        "id": "B021",
        "name": "Keyword Variant - JS vs JavaScript",
        "category": "fuzzy_test",
        "cv_text": "Dev User\n\nSkills:\nJS, Node, React, TS, Mongo, Postgres, k8s, AWS\n\nExperience:\nDeveloper, Co, 2022 - Present\n- Built web apps with JS and React\n- Used Node for backend services\n- Deployed on k8s with Docker",
        "job_description": "JavaScript Developer. Requirements: JavaScript, Node.js, React, TypeScript, MongoDB, PostgreSQL, Kubernetes, Docker, AWS.",
        "expected": {
            "keyword_score": {"min": 20, "max": 70},
            "ats_score": {"min": 25, "max": 60},
            "final_score": {"min": 20, "max": 60},
        },
        "notes": "Tests abbreviation matching: JS→JavaScript, TS→TypeScript, k8s→Kubernetes, Mongo→MongoDB.",
    },
    {
        "id": "B022",
        "name": "Nurse CV vs Healthcare IT JD",
        "category": "cross_sector",
        "cv_text": "Sarah Johnson RN\nRegistered Nurse\n\nContact: sarah.j@email.com\n\nExperience:\nICU Nurse, City Hospital, 2019 - Present\n- Managed patient care for 8-10 patients per shift\n- Implemented electronic health records (EHR) system training\n- Used Epic and Cerner healthcare software\n\nSkills:\nPatient Care, EHR, Epic, Cerner, HIPAA, Team Collaboration, Critical Thinking\n\nEducation:\nBSN, State University, 2019\n\nCertifications:\nBLS, ACLS, PALS",
        "job_description": "Healthcare IT Developer. Requirements: Python, HL7/FHIR, EHR integration, Epic API, SQL, REST APIs, HIPAA compliance, Docker.",
        "expected": {
            "keyword_score": {"min": 5, "max": 35},
            "ats_score": {"min": 45, "max": 80},
            "final_score": {"min": 25, "max": 60},
        },
        "notes": "Nurse with EHR experience vs Healthcare IT dev. Small overlap (Epic, HIPAA, EHR) but mostly mismatch.",
    },
    {
        "id": "B023",
        "name": "Intern CV - Very Short",
        "category": "minimal",
        "cv_text": "Ali Yilmaz\nStudent\n\nEmail: ali@email.com\n\nEducation:\nComputer Engineering, ITU, 2023-2027\nGPA: 3.5\n\nSkills: Python, Java, C",
        "job_description": "Intern wanted. Python basics, willingness to learn.",
        "expected": {
            "keyword_score": {"min": 20, "max": 70},
            "ats_score": {"min": 15, "max": 50},
            "final_score": {"min": 15, "max": 55},
        },
        "notes": "Very short student CV for intern role. Minimal but matching content.",
    },
    {
        "id": "B024",
        "name": "Senior CV - Multiple Pages Worth",
        "category": "long_cv",
        "cv_text": "Dr. James Wilson\nPrincipal Engineer\n\nContact:\nEmail: james.wilson@email.com\nPhone: +1 (555) 999-0001\nLinkedIn: linkedin.com/in/jameswilson\nGitHub: github.com/jwilson\n\nSummary:\n20+ years building distributed systems, leading engineering teams, and architecting cloud infrastructure.\n\nExperience:\n\nPrincipal Engineer, MegaCorp, 2018 - Present\n- Architected event-driven microservices processing 10B events/day\n- Led migration from on-premise to AWS saving $10M/year\n- Designed API gateway handling 100K requests/second\n- Mentored 30+ engineers across 4 teams\n- Technologies: Java, Python, Go, Kafka, Redis, PostgreSQL, DynamoDB, AWS, Kubernetes, Terraform\n\nSenior Staff Engineer, BigTech, 2014 - 2018\n- Built real-time data pipeline processing 500TB/day\n- Designed distributed caching layer reducing latency by 80%\n- Led adoption of containerization across 200+ services\n- Technologies: Java, Scala, Spark, Cassandra, Docker, Kubernetes\n\nStaff Engineer, StartupCo, 2010 - 2014\n- Built payment processing system handling $1B/year\n- Achieved PCI-DSS and SOC2 compliance\n- Implemented blue-green deployments and canary releases\n- Technologies: Python, Django, PostgreSQL, RabbitMQ, AWS\n\nSenior Engineer, WebCorp, 2006 - 2010\n- Developed search engine indexing 1B+ documents\n- Built recommendation system increasing CTR by 40%\n- Technologies: Java, Lucene, MySQL, Linux\n\nSoftware Engineer, TechStart, 2003 - 2006\n- Full-stack web development\n- Technologies: PHP, MySQL, JavaScript, HTML, CSS\n\nSkills:\nJava, Python, Go, Scala, Kafka, Redis, PostgreSQL, DynamoDB, Cassandra, AWS, GCP, Kubernetes, Terraform, Docker, CI/CD, System Design, Distributed Systems, API Design, Microservices, Event-Driven Architecture\n\nEducation:\nPhD Computer Science, MIT, 2003\nMS Computer Science, Stanford, 2000\nBS Computer Science, UC Berkeley, 1998\n\nPublications:\n- 12 papers in distributed systems conferences\n- 3 patents in data processing\n\nCertifications:\nAWS Solutions Architect Professional, GCP Professional Cloud Architect, Kubernetes CKA",
        "job_description": "Staff Engineer needed. Requirements: Java or Python, distributed systems, Kafka, AWS, Kubernetes, system design, 10+ years experience.",
        "expected": {
            "keyword_score": {"min": 55, "max": 95},
            "ats_score": {"min": 75, "max": 100},
            "final_score": {"min": 70, "max": 100},
        },
        "notes": "Very long senior CV with extensive experience. Strong match to staff engineer JD.",
    },
    {
        "id": "B025",
        "name": "Duplicate Skills Listed",
        "category": "edge_case",
        "cv_text": "Test User\nDeveloper\n\nSkills:\nPython Python Python Django Django Django REST REST API API PostgreSQL PostgreSQL Docker Docker\nPython, Django, REST API, PostgreSQL, Docker\nProgramming: Python\nFrameworks: Django\nDatabases: PostgreSQL\n\nExperience:\nDeveloper, Co, 2023 - Present\n- Built Python Django applications\n- Used PostgreSQL databases\n- Deployed with Docker",
        "job_description": "Python Developer. Django, REST APIs, PostgreSQL, Docker required.",
        "expected": {
            "keyword_score": {"min": 50, "max": 100},
            "ats_score": {"min": 25, "max": 60},
            "final_score": {"min": 30, "max": 65},
        },
        "notes": "CV with duplicate skills listed multiple times. Should not inflate keyword score beyond 100. ATS structure weak.",
    },
    {
        "id": "B026",
        "name": "Remote Work CV - Soft Skills Focus",
        "category": "soft_skills",
        "cv_text": "Emily Rodriguez\nProject Manager\n\nContact: emily.r@email.com\n\nSummary:\nCertified PMP with 6 years managing remote engineering teams. Expert in agile methodologies, stakeholder communication, and cross-cultural collaboration.\n\nExperience:\nSenior Project Manager, RemoteCo, 2021 - Present\n- Managed 3 distributed engineering teams (15 developers)\n- Delivered 12 projects on time and under budget\n- Implemented Jira workflows improving team velocity by 30%\n- Facilitated daily standups, sprint planning, and retrospectives\n\nSkills:\nProject Management, Agile, Scrum, Kanban, Jira, Confluence, Slack, MS Project, Stakeholder Management, Risk Management, Budget Planning, Team Leadership\n\nCertifications:\nPMP, CSM, SAFe Agilist",
        "job_description": "Engineering Manager needed. Requirements: Technical background, Agile/Scrum, team leadership, project management, Jira. Nice to have: Python, system design experience.",
        "expected": {
            "keyword_score": {"min": 25, "max": 65},
            "ats_score": {"min": 55, "max": 85},
            "final_score": {"min": 40, "max": 80},
        },
        "notes": "PM CV vs Engineering Manager JD. Good soft skill overlap but weak technical match.",
    },
    {
        "id": "B027",
        "name": "Freelancer CV - No Company Names",
        "category": "edge_case",
        "cv_text": "Mike Chen\nFreelance Developer\n\nContact: mike@freelance.dev\n\nExperience:\nFreelance Full-Stack Developer, 2020 - Present\n- Built 20+ client websites using React and Node.js\n- Developed mobile apps with React Native\n- Set up cloud infrastructure on AWS and DigitalOcean\n\nFreelance Backend Developer, 2018 - 2020\n- Created REST APIs for various startups\n- Database design with PostgreSQL and MongoDB\n\nSkills:\nReact, Node.js, React Native, Python, Django, PostgreSQL, MongoDB, AWS, Docker, Git\n\nEducation:\nSelf-taught developer\nfreeCodeCamp, Udemy, Coursera certifications",
        "job_description": "Full Stack Developer. React, Node.js, PostgreSQL, AWS, Docker, Git required. 3+ years experience.",
        "expected": {
            "keyword_score": {"min": 45, "max": 85},
            "ats_score": {"min": 50, "max": 80},
            "final_score": {"min": 45, "max": 80},
        },
        "notes": "Freelancer without formal company names. Good skill match but unconventional format.",
    },
    {
        "id": "B028",
        "name": "Bootcamp Grad with Projects Only",
        "category": "entry_level",
        "cv_text": "Jordan Lee\nJunior Developer\n\nContact: jordan@email.com | github.com/jordanlee\n\nProjects:\nE-Commerce Platform (2024)\n- React frontend, Node.js backend, PostgreSQL database\n- Stripe payment integration, JWT authentication\n- Deployed on Heroku with CI/CD\n\nChat Application (2024)\n- Real-time messaging with Socket.io\n- React, Express, MongoDB\n\nWeather App (2024)\n- React, OpenWeather API, responsive design\n\nEducation:\nFull Stack Bootcamp, Codecademy Pro, 2024\nBA English Literature, Boston University, 2022\n\nSkills:\nJavaScript, React, Node.js, Express, PostgreSQL, MongoDB, HTML, CSS, Git, Docker basics",
        "job_description": "Junior Full Stack Developer. JavaScript, React, Node.js required. Portfolio projects valued. Bootcamp grads welcome.",
        "expected": {
            "keyword_score": {"min": 40, "max": 80},
            "ats_score": {"min": 45, "max": 80},
            "final_score": {"min": 40, "max": 80},
        },
        "notes": "Bootcamp grad with projects but no work experience. JD is bootcamp-friendly.",
    },
    {
        "id": "B029",
        "name": "PhD Researcher - Too Academic",
        "category": "academic",
        "cv_text": "Dr. Anna Petrova\nResearch Scientist\n\nContact: anna.petrova@university.edu\n\nResearch Interests:\nReinforcement learning, multi-agent systems, game theory, optimization\n\nPublications:\n- 15 peer-reviewed papers (h-index: 12)\n- 2 best paper awards at AAAI and IJCAI\n- 500+ citations\n\nExperience:\nAssistant Professor, University, 2021 - Present\n- Teaching: Machine Learning, Algorithms, AI Ethics\n- Supervised 8 PhD students\n- $2M in research grants\n\nPostdoc, Research Lab, 2019 - 2021\n- Developed novel RL algorithms\n- Published 5 papers\n\nSkills:\nPython, PyTorch, TensorFlow, MATLAB, LaTeX, statistical analysis, research methodology\n\nEducation:\nPhD Computer Science, ETH Zurich, 2019",
        "job_description": "Machine Learning Engineer. Production ML systems, Python, PyTorch, Docker, Kubernetes, CI/CD, REST APIs, monitoring, A/B testing required. Move fast, ship often.",
        "expected": {
            "keyword_score": {"min": 15, "max": 50},
            "ats_score": {"min": 50, "max": 85},
            "final_score": {"min": 35, "max": 70},
        },
        "notes": "Academic researcher vs industry ML engineer. Python/PyTorch overlap but missing production infra skills.",
    },
    {
        "id": "B030",
        "name": "Tightened Range Test - B001 Narrow",
        "category": "tight_range",
        "cv_text": "John Smith\nSenior Python Developer\n\nContact:\nEmail: john.smith@email.com\nPhone: +1 (555) 123-4567\nLocation: San Francisco, CA\nLinkedIn: linkedin.com/in/johnsmith\n\nProfessional Summary:\nExperienced Python developer with 8+ years in web development, machine learning, and data engineering. Strong background in Django, Flask, React, and cloud technologies.\n\nWork Experience:\nSenior Python Developer\nTechCorp Inc., San Francisco, CA\nJanuary 2020 - Present\n- Led development of microservices architecture serving 1M+ users\n- Built ML pipelines processing 100TB+ data monthly using Python, TensorFlow, and AWS\n- Mentored 5 junior developers and established coding standards\n- Technologies: Python, Django, React, PostgreSQL, Redis, Docker, Kubernetes\n\nSkills:\nPython, JavaScript, SQL, Django, Flask, React, Node.js, PostgreSQL, MongoDB, Redis, AWS, Docker, Kubernetes, Terraform, Git, Jenkins\n\nEducation:\nMS Computer Science, Stanford, 2015\nBS Computer Science, UC Berkeley, 2013\n\nCertifications:\nAWS Certified Solutions Architect (2022)",
        "job_description": "Senior Python Developer with 5+ years. Python, Django, REST APIs, PostgreSQL, Docker, Kubernetes, AWS required.",
        "expected": {
            "keyword_score": {"min": 68, "max": 82},
            "ats_score": {"min": 82, "max": 95},
            "final_score": {"min": 82, "max": 96},
        },
        "notes": "TIGHTENED RANGE TEST. Same as B001 but with narrow expected ranges to test system sensitivity.",
    },
]

with open(DS, "r", encoding="utf-8") as f:
    data = json.load(f)

data["entries"].extend(NEW)
data["version"] = "2.0.0"
data["description"] += f" Expanded to {len(data['entries'])} entries in v2."

with open(DS, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Dataset expanded: {len(data['entries'])} entries total")
