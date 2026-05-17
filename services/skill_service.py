import re
import os
import json
import hashlib

try:
    from redis import Redis as _RedisClient
except Exception:
    _RedisClient = None

# Optional Redis cache for skill extraction. If Redis is unavailable the
# extraction logic will still work normally without caching.
_skills_redis = None
if _RedisClient is not None:
    try:
        _skills_redis = _RedisClient.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/3"),
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        _skills_redis.ping()
    except Exception:
        _skills_redis = None

SKILLS_CACHE_TTL = int(os.getenv("SKILLS_CACHE_TTL", "86400"))


def _hash_text(text: str) -> str:
    if not isinstance(text, str):
        text = str(text or "")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── Comprehensive skill database organized by category ──────────────

SKILL_CATEGORIES = {
    "languages": [
        "python",
        "java",
        "javascript",
        "typescript",
        "c#",
        "c\\+\\+",
        "c",
        "go",
        "golang",
        "rust",
        "ruby",
        "php",
        "swift",
        "kotlin",
        "scala",
        "r",
        "matlab",
        "perl",
        "lua",
        "dart",
        "elixir",
        "haskell",
        "objective-c",
        "groovy",
        "clojure",
        "fortran",
        "cobol",
        "visual basic",
        "vb\\.net",
        "f#",
        "julia",
        "assembly",
    ],
    "frontend": [
        "react",
        "angular",
        "vue",
        "vue\\.js",
        "svelte",
        "next\\.js",
        "nextjs",
        "nuxt",
        "nuxt\\.js",
        "gatsby",
        "remix",
        "astro",
        "html",
        "css",
        "sass",
        "scss",
        "less",
        "tailwind",
        "tailwindcss",
        "bootstrap",
        "material ui",
        "mui",
        "chakra ui",
        "ant design",
        "jquery",
        "webpack",
        "vite",
        "babel",
        "rollup",
        "esbuild",
        "storybook",
        "redux",
        "zustand",
        "mobx",
        "pinia",
        "vuex",
        "three\\.js",
        "d3\\.js",
        "d3",
        "chart\\.js",
    ],
    "backend": [
        "node\\.js",
        "nodejs",
        "express",
        "express\\.js",
        "nestjs",
        "nest\\.js",
        "fastapi",
        "django",
        "flask",
        "spring",
        "spring boot",
        "springboot",
        "asp\\.net",
        "\\.net",
        "dotnet",
        "laravel",
        "symfony",
        "rails",
        "ruby on rails",
        "sinatra",
        "gin",
        "fiber",
        "echo",
        "actix",
        "rocket",
        "axum",
        "phoenix",
        "koa",
        "hapi",
        "graphql",
        "rest",
        "restful",
        "grpc",
        "websocket",
        "microservices",
        "serverless",
        "oauth",
        "jwt",
    ],
    "databases": [
        "sql",
        "postgresql",
        "postgres",
        "mysql",
        "mariadb",
        "sqlite",
        "oracle",
        "sql server",
        "mssql",
        "mongodb",
        "dynamodb",
        "cassandra",
        "couchdb",
        "neo4j",
        "redis",
        "memcached",
        "elasticsearch",
        "opensearch",
        "solr",
        "firebase",
        "supabase",
        "cockroachdb",
        "timescaledb",
        "influxdb",
        "clickhouse",
        "snowflake",
        "bigquery",
        "prisma",
        "sequelize",
        "sqlalchemy",
        "hibernate",
        "typeorm",
        "mongoose",
        "knex",
    ],
    "devops_cloud": [
        "docker",
        "kubernetes",
        "k8s",
        "podman",
        "aws",
        "amazon web services",
        "azure",
        "gcp",
        "google cloud",
        "terraform",
        "pulumi",
        "cloudformation",
        "ansible",
        "chef",
        "puppet",
        "jenkins",
        "github actions",
        "gitlab ci",
        "circle ci",
        "circleci",
        "travis ci",
        "argo cd",
        "argocd",
        "tekton",
        "nginx",
        "apache",
        "caddy",
        "haproxy",
        "linux",
        "ubuntu",
        "centos",
        "debian",
        "rhel",
        "bash",
        "shell",
        "powershell",
        "prometheus",
        "grafana",
        "datadog",
        "new relic",
        "splunk",
        "elk",
        "kibana",
        "logstash",
        "fluentd",
        "helm",
        "istio",
        "envoy",
        "consul",
        "vault",
    ],
    "data_ml": [
        "machine learning",
        "deep learning",
        "nlp",
        "natural language processing",
        "computer vision",
        "tensorflow",
        "pytorch",
        "keras",
        "scikit-learn",
        "sklearn",
        "pandas",
        "numpy",
        "scipy",
        "matplotlib",
        "seaborn",
        "plotly",
        "jupyter",
        "hugging face",
        "huggingface",
        "transformers",
        "bert",
        "gpt",
        "llm",
        "langchain",
        "openai",
        "spark",
        "pyspark",
        "hadoop",
        "hive",
        "airflow",
        "dbt",
        "kafka",
        "flink",
        "beam",
        "tableau",
        "power bi",
        "looker",
        "metabase",
        "etl",
        "data warehouse",
        "data lake",
        "data pipeline",
        "feature engineering",
        "model deployment",
        "mlops",
        "mlflow",
        "kubeflow",
        "sagemaker",
        "vertex ai",
        "onnx",
        "xgboost",
        "lightgbm",
        "catboost",
        "random forest",
    ],
    "mobile": [
        "react native",
        "flutter",
        "ionic",
        "xamarin",
        "android",
        "ios",
        "swiftui",
        "jetpack compose",
        "expo",
        "capacitor",
        "cordova",
    ],
    "testing": [
        "jest",
        "mocha",
        "chai",
        "cypress",
        "playwright",
        "selenium",
        "pytest",
        "unittest",
        "rspec",
        "junit",
        "testng",
        "postman",
        "insomnia",
        "k6",
        "locust",
        "jmeter",
        "tdd",
        "bdd",
        "cucumber",
        "robot framework",
        "sonarqube",
        "codecov",
    ],
    "tools_practices": [
        "git",
        "github",
        "gitlab",
        "bitbucket",
        "svn",
        "jira",
        "confluence",
        "trello",
        "asana",
        "notion",
        "linear",
        "figma",
        "sketch",
        "adobe xd",
        "invision",
        "agile",
        "scrum",
        "kanban",
        "ci/cd",
        "cicd",
        "api design",
        "system design",
        "design patterns",
        "solid",
        "clean architecture",
        "domain driven design",
        "ddd",
        "oauth2",
        "saml",
        "sso",
        "rbac",
    ],
    "security": [
        "owasp",
        "penetration testing",
        "vulnerability assessment",
        "sast",
        "dast",
        "siem",
        "ids",
        "ips",
        "encryption",
        "tls",
        "ssl",
        "pki",
        "nmap",
        "burp suite",
        "wireshark",
        "metasploit",
        "iso 27001",
        "soc 2",
        "gdpr",
        "hipaa",
        "pci dss",
        "zero trust",
        "firewall",
        "waf",
    ],
}

# ── Common abbreviation → canonical name expansion ──────────────────────
# Maps short forms people write on CVs to the canonical skill name so
# that both "JS" and "JavaScript" count as the same skill.
_ABBREVIATION_MAP: dict[str, str] = {
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "rb": "ruby",
    "k8s": "kubernetes",
    "tf": "terraform",
    "gha": "github actions",
    "pg": "postgresql",
    "mongo": "mongodb",
    "es": "elasticsearch",
    "rn": "react native",
    "rds": "aws",
    "ec2": "aws",
    "s3": "aws",
    "ml": "machine learning",
    "dl": "deep learning",
    "cv": "computer vision",
    "ai": "machine learning",
    "ci": "ci/cd",
    "cd": "ci/cd",
    "nosql": "mongodb",
    "gke": "kubernetes",
    "eks": "kubernetes",
    "aks": "kubernetes",
    "cdk": "cloudformation",
    "sqs": "aws",
    "sns": "aws",
    "ecs": "aws",
    "drf": "django",
    "orm": "sqlalchemy",
}

# Pre-compile abbreviation regex patterns (standalone word matches)
_COMPILED_ABBREVIATIONS = [
    (re.compile(r"\b" + re.escape(abbr) + r"\b", re.IGNORECASE), canonical)
    for abbr, canonical in _ABBREVIATION_MAP.items()
]

# Build a flat list of (pattern, canonical_name, category)
_SKILL_REGISTRY = []
for category, skills in SKILL_CATEGORIES.items():
    for skill in skills:
        # canonical name = the human-readable version (unescaped)
        canonical = skill.replace("\\", "")
        _SKILL_REGISTRY.append((skill, canonical, category))

# Pre-compile regex patterns for word-boundary matching
_COMPILED_SKILLS = [
    (re.compile(r"\b" + pattern + r"\b", re.IGNORECASE), canonical, category)
    for pattern, canonical, category in _SKILL_REGISTRY
]


def extract_skills(text: str) -> dict:
    """Extract skills from text with optional Redis caching.

    Returns dict with:
      - found: set of canonical skill names
      - by_category: dict[category] -> set of skills
    """

    cache_key = None
    if _skills_redis is not None:
        try:
            cache_key = f"skills:{_hash_text(text or '')}"
            cached = _skills_redis.get(cache_key)
        except Exception:
            cached = None
        if cached:
            try:
                data = json.loads(cached)
                found = set(data.get("found", []))
                by_category = {
                    k: set(v) for k, v in (data.get("by_category", {}) or {}).items()
                }
                return {"found": found, "by_category": by_category}
            except Exception:
                # Ignore cache decode errors and fall back to fresh computation
                pass

    found = set()
    by_category = {}

    for regex, canonical, category in _COMPILED_SKILLS:
        if regex.search(text):
            found.add(canonical)
            by_category.setdefault(category, set()).add(canonical)

    # Abbreviation expansion: if "JS" is found, add "javascript" etc.
    # Look up the canonical skill's category from the registry.
    _canonical_to_category = {}
    for _, canon, cat in _SKILL_REGISTRY:
        _canonical_to_category.setdefault(canon.lower(), cat)

    for abbr_re, abbr_canonical in _COMPILED_ABBREVIATIONS:
        if abbr_re.search(text) and abbr_canonical not in found:
            found.add(abbr_canonical)
            cat = _canonical_to_category.get(abbr_canonical.lower(), "tools_practices")
            by_category.setdefault(cat, set()).add(abbr_canonical)

    result = {"found": found, "by_category": by_category}

    # --- Auto-detect previously-unknown skill-like tokens from free text.
    # We don't persist these into the static registry; they are returned
    # as runtime-detected candidates so new technologies are still matched.
    try:
        STOPWORDS = {
            "and",
            "or",
            "with",
            "the",
            "a",
            "an",
            "for",
            "in",
            "on",
            "of",
            "to",
            "by",
            "experience",
            "years",
            "year",
            "skills",
            "skill",
            "tools",
            "using",
            "knowledge",
            "proficient",
            "familiar",
            "including",
            "etc",
            "and/or",
            "strong",
            "ability",
            "able",
            "responsible",
            "worked",
        }

        def _is_techy_token(tok: str) -> bool:
            # tokens with special chars commonly found in tech names
            if re.search(r"[\+#\.\-]", tok):
                return True
            # tokens containing digits (eg. ES6, S3, EC2)
            if re.search(r"\d", tok):
                return True
            # camelCase or PascalCase detection (ReactNative, NextJS)
            if re.search(r"[A-Z][a-z]+[A-Z]", tok):
                return True
            # common suffixes
            if tok.lower().endswith(("js", "sql", "db", "css", "html", "net", "py", "cpp", "rb")):
                return True
            # do not auto-accept purely alphabetic short words to avoid false positives
            return False

        candidates = set()

        # 1) Prefer explicit "Skills:" lines when present
        for m in re.finditer(r"(?mi)^(?:skills|technical skills|technologies|tech stack|skills and technologies)\s*[:\-]\s*(.+)$", text, re.MULTILINE):
            chunk = m.group(1)
            parts = re.split(r"[,\|;/\\•\u2022]+", chunk)
            for p in parts:
                p = p.strip().strip(".\n\r")
                if not p:
                    continue
                tok = re.sub(r"[^A-Za-z0-9\+#\.\- ]", "", p).strip()
                if not tok:
                    continue
                tok_low = tok.lower()
                if tok_low not in STOPWORDS and tok_low not in found:
                    candidates.add(tok_low)

        # 2) Global token scan with heuristics (catch inline or bullet lists)
        raw_tokens = re.findall(r"\b[A-Za-z0-9\+\#\.\-]{2,}\b", text)
        for tok in raw_tokens:
            tok_clean = tok.strip().strip(".,;:()[]")
            tok_low = tok_clean.lower()
            if not tok_low or tok_low in found or tok_low in STOPWORDS:
                continue
            if _is_techy_token(tok_clean):
                # avoid picking very common words
                if len(tok_low) <= 2 and not re.search(r"[\d\+#\.\-]", tok_clean):
                    continue
                candidates.add(tok_low)

        # Remove obvious false positives (short common English words)
        candidates = {c for c in candidates if c not in STOPWORDS and not c.isdigit()}

        # Add candidates into result under an 'auto_detected' category so
        # downstream code can choose to use or ignore them. Do not modify
        # registry or persistent storage.
        if candidates:
            auto_cat = "auto_detected"
            by_category.setdefault(auto_cat, set()).update(sorted(candidates))
            found.update(candidates)
            result = {"found": found, "by_category": by_category}
    except Exception:
        # Best-effort: do not fail extraction if auto-detect has issues
        pass

    if cache_key and _skills_redis is not None:
        try:
            serializable = {
                "found": sorted(found),
                "by_category": {k: sorted(list(v)) for k, v in by_category.items()},
            }
            _skills_redis.setex(cache_key, SKILLS_CACHE_TTL, json.dumps(serializable))
        except Exception:
            pass

    return result


def skill_coverage_score(cv_text: str, job_text: str):
    """
    Calculate skill coverage score.
    Returns (score, missing_skills_list).
    """
    cv_result = extract_skills(cv_text)
    job_result = extract_skills(job_text)

    cv_skills = {s.lower() for s in (cv_result.get("found") or set())}
    job_skills = {s.lower() for s in (job_result.get("found") or set())}

    if not job_skills:
        return 0.0, []

    # Normalized raw text for fuzzy checks
    def _normalize(text: str) -> str:
        if not isinstance(text, str):
            text = str(text or "")
        t = text.lower()
        t = re.sub(r"[^a-z0-9\s]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    norm_cv = _normalize(cv_text)
    cv_words = set(norm_cv.split())

    matched = set()
    missing = []

    for job_skill in sorted(job_skills):
        js = job_skill.lower()
        is_matched = False

        # 1) Exact canonical match already detected
        if js in cv_skills:
            is_matched = True

        # 2) Exact substring presence in normalized CV text
        if not is_matched and js and js in norm_cv:
            is_matched = True

        # 3) Token overlap heuristic: if most tokens of the job skill appear in CV text
        if not is_matched:
            tokens = re.findall(r"[a-z0-9]{2,}", js)
            if tokens:
                found_tokens = sum(1 for t in tokens if t in cv_words)
                if found_tokens / max(1, len(tokens)) >= 0.7:
                    is_matched = True

        # 4) Substring relation with any extracted CV skill (e.g., "react" vs "reactjs")
        if not is_matched:
            for cvs in cv_skills:
                if cvs and (cvs in js or js in cvs):
                    is_matched = True
                    break

        if is_matched:
            matched.add(js)
        else:
            missing.append(js)

    coverage = (len(matched) / len(job_skills)) * 100
    return round(float(coverage), 2), sorted(missing)
