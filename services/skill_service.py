import re

# ── Comprehensive skill database organized by category ──────────────

SKILL_CATEGORIES = {
    "languages": [
        "python", "java", "javascript", "typescript", "c#", "c\\+\\+", "c",
        "go", "golang", "rust", "ruby", "php", "swift", "kotlin", "scala",
        "r", "matlab", "perl", "lua", "dart", "elixir", "haskell",
        "objective-c", "groovy", "clojure", "fortran", "cobol",
        "visual basic", "vb\\.net", "f#", "julia", "assembly",
    ],
    "frontend": [
        "react", "angular", "vue", "vue\\.js", "svelte", "next\\.js", "nextjs",
        "nuxt", "nuxt\\.js", "gatsby", "remix", "astro",
        "html", "css", "sass", "scss", "less", "tailwind", "tailwindcss",
        "bootstrap", "material ui", "mui", "chakra ui", "ant design",
        "jquery", "webpack", "vite", "babel", "rollup", "esbuild",
        "storybook", "redux", "zustand", "mobx", "pinia", "vuex",
        "three\\.js", "d3\\.js", "d3", "chart\\.js",
    ],
    "backend": [
        "node\\.js", "nodejs", "express", "express\\.js", "nestjs", "nest\\.js",
        "fastapi", "django", "flask", "spring", "spring boot", "springboot",
        "asp\\.net", "\\.net", "dotnet", "laravel", "symfony", "rails",
        "ruby on rails", "sinatra", "gin", "fiber", "echo",
        "actix", "rocket", "axum", "phoenix", "koa", "hapi",
        "graphql", "rest", "restful", "grpc", "websocket",
        "microservices", "serverless", "oauth", "jwt",
    ],
    "databases": [
        "sql", "postgresql", "postgres", "mysql", "mariadb", "sqlite",
        "oracle", "sql server", "mssql", "mongodb", "dynamodb",
        "cassandra", "couchdb", "neo4j", "redis", "memcached",
        "elasticsearch", "opensearch", "solr",
        "firebase", "supabase", "cockroachdb", "timescaledb",
        "influxdb", "clickhouse", "snowflake", "bigquery",
        "prisma", "sequelize", "sqlalchemy", "hibernate", "typeorm",
        "mongoose", "knex",
    ],
    "devops_cloud": [
        "docker", "kubernetes", "k8s", "podman",
        "aws", "amazon web services", "azure", "gcp", "google cloud",
        "terraform", "pulumi", "cloudformation", "ansible", "chef", "puppet",
        "jenkins", "github actions", "gitlab ci", "circle ci", "circleci",
        "travis ci", "argo cd", "argocd", "tekton",
        "nginx", "apache", "caddy", "haproxy",
        "linux", "ubuntu", "centos", "debian", "rhel",
        "bash", "shell", "powershell",
        "prometheus", "grafana", "datadog", "new relic", "splunk",
        "elk", "kibana", "logstash", "fluentd",
        "helm", "istio", "envoy", "consul", "vault",
    ],
    "data_ml": [
        "machine learning", "deep learning", "nlp",
        "natural language processing", "computer vision",
        "tensorflow", "pytorch", "keras", "scikit-learn", "sklearn",
        "pandas", "numpy", "scipy", "matplotlib", "seaborn", "plotly",
        "jupyter", "hugging face", "huggingface", "transformers",
        "bert", "gpt", "llm", "langchain", "openai",
        "spark", "pyspark", "hadoop", "hive", "airflow",
        "dbt", "kafka", "flink", "beam",
        "tableau", "power bi", "looker", "metabase",
        "etl", "data warehouse", "data lake", "data pipeline",
        "feature engineering", "model deployment", "mlops",
        "mlflow", "kubeflow", "sagemaker", "vertex ai",
        "onnx", "xgboost", "lightgbm", "catboost", "random forest",
    ],
    "mobile": [
        "react native", "flutter", "ionic", "xamarin",
        "android", "ios", "swiftui", "jetpack compose",
        "expo", "capacitor", "cordova",
    ],
    "testing": [
        "jest", "mocha", "chai", "cypress", "playwright", "selenium",
        "pytest", "unittest", "rspec", "junit", "testng",
        "postman", "insomnia", "k6", "locust", "jmeter",
        "tdd", "bdd", "cucumber", "robot framework",
        "sonarqube", "codecov",
    ],
    "tools_practices": [
        "git", "github", "gitlab", "bitbucket", "svn",
        "jira", "confluence", "trello", "asana", "notion", "linear",
        "figma", "sketch", "adobe xd", "invision",
        "agile", "scrum", "kanban", "ci/cd", "cicd",
        "api design", "system design", "design patterns",
        "solid", "clean architecture", "domain driven design", "ddd",
        "oauth2", "saml", "sso", "rbac",
    ],
    "security": [
        "owasp", "penetration testing", "vulnerability assessment",
        "sast", "dast", "siem", "ids", "ips",
        "encryption", "tls", "ssl", "pki",
        "nmap", "burp suite", "wireshark", "metasploit",
        "iso 27001", "soc 2", "gdpr", "hipaa", "pci dss",
        "zero trust", "firewall", "waf",
    ],
}

# Build a flat list of (pattern, canonical_name, category)
_SKILL_REGISTRY = []
for category, skills in SKILL_CATEGORIES.items():
    for skill in skills:
        # canonical name = the human-readable version (unescaped)
        canonical = skill.replace("\\", "")
        _SKILL_REGISTRY.append((skill, canonical, category))

# Pre-compile regex patterns for word-boundary matching
_COMPILED_SKILLS = [
    (re.compile(r'\b' + pattern + r'\b', re.IGNORECASE), canonical, category)
    for pattern, canonical, category in _SKILL_REGISTRY
]


def extract_skills(text: str) -> dict:
    """
    Extract skills from text. Returns dict with:
      - found: set of canonical skill names
      - by_category: dict[category] -> set of skills
    """
    found = set()
    by_category = {}

    for regex, canonical, category in _COMPILED_SKILLS:
        if regex.search(text):
            found.add(canonical)
            by_category.setdefault(category, set()).add(canonical)

    return {"found": found, "by_category": by_category}


def skill_coverage_score(cv_text: str, job_text: str):
    """
    Calculate skill coverage score.
    Returns (score, missing_skills_list).
    """
    cv_result = extract_skills(cv_text)
    job_result = extract_skills(job_text)

    cv_skills = cv_result["found"]
    job_skills = job_result["found"]

    if not job_skills:
        return 0.0, []

    matched = cv_skills & job_skills
    coverage = (len(matched) / len(job_skills)) * 100
    missing = sorted(job_skills - cv_skills)

    return round(coverage, 2), missing