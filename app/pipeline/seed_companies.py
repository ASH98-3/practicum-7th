"""
Registers sample companies' JDs into the persistent Chroma store. Run this once
(or whenever a company posts a new JD) before running the resume pipeline.

In a real backend this logic lives behind a "company posts JD" API endpoint —
this script simulates that for local development/demo purposes.
"""
from app.schemas.models import JDData
from app.parsing.llm_extractor import extract_jd_fields
from app.vectorstore.company_store import register_jds_bulk

RAW_JDS = [
    {
        "jd_id": "jd_001", "company_id": "comp_nimbus", "company": "Nimbus Systems",
        "raw_text": """Backend Engineer — Nimbus Systems
        We are looking for a Backend Engineer with 3+ years of experience in Python,
        building scalable REST APIs and working with relational databases (PostgreSQL).
        Experience with AWS and containerization (Docker/Kubernetes) is a strong plus.
        Bachelor's degree in Computer Science or related field required.""",
    },
    {
        "jd_id": "jd_002", "company_id": "comp_brightpath", "company": "Brightpath Health",
        "raw_text": """Frontend Engineer — Brightpath Health
        Seeking a Frontend Engineer with 2+ years of React and TypeScript experience to
        build accessible, high-quality patient-facing interfaces. Next.js experience
        preferred. Bachelor's degree preferred, not required.""",
    },
    {
        "jd_id": "jd_003", "company_id": "comp_solace", "company": "Solace Data",
        "raw_text": """Senior Platform Engineer — Solace Data
        5+ years of experience designing distributed backend systems in Python or Go.
        Deep AWS expertise (EC2, Lambda, S3) and hands-on Kubernetes required. Experience
        leading engineers is a plus. B.Tech/B.S. in Computer Science required.""",
    },
    {
        "jd_id": "jd_004", "company_id": "comp_ledgerly", "company": "Ledgerly",
        "raw_text": """Data Analyst — Ledgerly
        1+ years of experience with SQL and Excel for financial reporting. No coding
        background required. Bachelor's degree in any field.""",
    },
    {
        "jd_id": "jd_005", "company_id": "comp_orbital", "company": "Orbital Fintech",
        "raw_text": """Full Stack Engineer — Orbital Fintech
        3+ years building full stack applications with Node.js, React, and PostgreSQL.
        Experience with microservices and CI/CD pipelines (GitHub Actions) required.
        B.S. in Computer Science or equivalent experience.""",
    },
]


def seed():
    jds = []
    for raw in RAW_JDS:
        fields = extract_jd_fields(raw["raw_text"])
        jds.append(JDData(
            jd_id=raw["jd_id"],
            company_id=raw["company_id"],
            company=raw["company"],
            raw_text=raw["raw_text"],
            required_skills=fields["skills"],
            min_experience_years=fields["experience_years"],
            education_requirement=(fields["education"][0] if fields["education"] else "Not specified"),
            parsed_summary=fields["summary"],
        ))
    register_jds_bulk(jds)
    print(f"Registered {len(jds)} JDs from {len(set(j.company for j in jds))} companies.")


if __name__ == "__main__":
    seed()
