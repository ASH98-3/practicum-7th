"""
Central configuration. Everything that might change between dev/staging/prod,
or between "I have API keys" and "offline demo mode", lives here.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM (Groq) ──────────────────────────────────────────────────────────────
# Used for: resume/JD structured extraction, skill-equivalence judgment,
# match rationale generation. NOT used for embeddings (see below).
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
USE_LLM = bool(GROQ_API_KEY)  # auto-detected: if no key, fall back to offline heuristics

# ── Embeddings (local NLP model, separate from the LLM) ─────────────────────
# sentence-transformers model used for resume <-> JD semantic similarity.
# 'all-MiniLM-L6-v2' is fast and small (384 dims); swap for 'BAAI/bge-small-en-v1.5'
# for a small accuracy bump at similar speed.
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

# ── Vector store (Chroma) ────────────────────────────────────────────────────
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
JD_COLLECTION_NAME = "job_descriptions"
DB_PATH = os.getenv("DB_PATH", "./data/app.db")   # users, sessions, resumes, matches (SQLite)

# ── ATS scoring ───────────────────────────────────────────────────────────
ATS_WEIGHTS = {"skill_overlap": 0.5, "experience_fit": 0.3, "education_fit": 0.2}
SHORTLIST_THRESHOLD = 75.0
MANUAL_REVIEW_THRESHOLD = 50.0
# Minimum ATS score before a candidate is shown to a company. Must be above 50: experience+education
# alone already score 50 with ZERO skill overlap, which recruiters should never see.
SEND_TO_COMPANY_THRESHOLD = 60.0
TOP_K_MATCHES = 3        # how many results we show
RETRIEVE_K = 15          # how many JDs we pull by similarity BEFORE ATS re-scoring

DEGREE_RANK = {
    "B.TECH": 1, "B.S.": 1, "B.A.": 1, "BACHELOR": 1,
    "M.TECH": 2, "M.S.": 2, "M.A.": 2, "MASTER": 2,
    "PHD": 3,
}

SKILL_VOCAB = [
    "python", "go", "java", "javascript", "typescript", "c++", "c#", "rust", "ruby", "php", "scala", "kotlin", "swift",
    "react", "next.js", "vue", "angular", "node.js", "html", "css", "tailwind",
    "django", "flask", "fastapi", "spring", "express", ".net",
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "kafka", "snowflake", "bigquery",
    "aws", "ec2", "lambda", "s3", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible", "jenkins",
    "ci/cd", "github actions", "linux", "git", "rest api", "graphql", "microservices", "grpc",
    "pandas", "numpy", "scikit-learn", "pytorch", "tensorflow", "spark", "hadoop", "airflow", "dbt",
    "machine learning", "deep learning", "nlp", "llm", "computer vision", "data analysis", "statistics",
    "tableau", "power bi", "excel", "looker", "figma", "agile", "scrum", "jira", "salesforce",
    "android", "ios", "react native", "flutter", "selenium", "pytest", "devops", "sre",
]
