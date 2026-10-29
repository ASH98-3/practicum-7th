"""
Pre-load demo company accounts + JDs into local SQLite + Chroma before a panel demo.

    python seed_demo.py

Safe to re-run: existing emails are skipped; JDs are upserted by stable id.

Demo logins (password for all: Demo@1234)
  company@nimbus.dev   → Nimbus Systems
  company@brightpath.dev → Brightpath Health
  candidate@demo.dev   → sample candidate (no resume preloaded)

During the live demo you can still:
  - log in as a company and paste a new JD
  - register a brand-new company in front of the panel
"""
from typing import Optional

from app.auth import hash_password
from app.db import conn, init_db
from app.ingestion.service import ingest_jd, _slug
from app.vectorstore.company_store import collection_size

PASSWORD = "Demo@1234"

ACCOUNTS = [
    {
        "email": "company@nimbus.dev",
        "name": "Nimbus Recruiter",
        "role": "company",
        "company_name": "Nimbus Systems",
    },
    {
        "email": "company@brightpath.dev",
        "name": "Brightpath Recruiter",
        "role": "company",
        "company_name": "Brightpath Health",
    },
    {
        "email": "candidate@demo.dev",
        "name": "Priya Sharma",
        "role": "candidate",
        "company_name": None,
    },
]

JDS = [
    {
        "company": "Nimbus Systems",
        "title": "Backend Engineer",
        "text": """Backend Engineer — Nimbus Systems

We are looking for a Backend Engineer with 3+ years of experience building
scalable REST APIs in Python. You will work with PostgreSQL, design service
boundaries, and ship production services on AWS.

Requirements:
- Strong Python (FastAPI or Django/Flask)
- Relational databases (PostgreSQL / SQL)
- Docker; Kubernetes is a plus
- AWS (EC2, Lambda, S3) experience preferred
- Bachelor's degree in Computer Science or related field

Nice to have: CI/CD, observability, microservices.""",
    },
    {
        "company": "Nimbus Systems",
        "title": "Senior Platform Engineer",
        "text": """Senior Platform Engineer — Nimbus Systems

5+ years designing distributed backend systems in Python or Go.
Deep AWS expertise (EC2, Lambda, S3) and hands-on Kubernetes required.
Experience mentoring engineers is a plus.
B.Tech / B.S. in Computer Science required.

You will own platform reliability, deployment pipelines, and internal developer tooling.""",
    },
    {
        "company": "Brightpath Health",
        "title": "Frontend Engineer",
        "text": """Frontend Engineer — Brightpath Health

Seeking a Frontend Engineer with 2+ years of React and TypeScript experience
to build accessible, high-quality patient-facing interfaces.

Requirements:
- React and TypeScript
- Strong HTML/CSS; Tailwind or similar design systems
- Experience with REST APIs
- Next.js preferred
- Bachelor's degree preferred, not required

You will collaborate with product and design on healthcare workflows.""",
    },
    {
        "company": "Brightpath Health",
        "title": "Full Stack Engineer",
        "text": """Full Stack Engineer — Brightpath Health

3+ years building full stack applications with Node.js or Python, React, and
PostgreSQL. Experience with microservices and CI/CD (GitHub Actions) required.
B.S. in Computer Science or equivalent experience.

You will ship features end-to-end across our clinical operations product.""",
    },
]


def upsert_user(email: str, name: str, role: str, company_name: Optional[str]) -> None:
    email = email.strip().lower()
    company_id = _slug(company_name) if role == "company" and company_name else None
    with conn() as c:
        existing = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            print(f"  skip account  {email} (already exists)")
            return
        c.execute(
            "INSERT INTO users(email,password_hash,role,name,company_name,company_id) VALUES(?,?,?,?,?,?)",
            (email, hash_password(PASSWORD), role, name, company_name, company_id),
        )
        print(f"  + account     {email}  ({role}" + (f", {company_name})" if company_name else ")"))


def main():
    init_db()
    print("Seeding demo accounts…")
    for a in ACCOUNTS:
        upsert_user(a["email"], a["name"], a["role"], a["company_name"])

    print("\nSeeding job descriptions into Chroma…")
    for jd in JDS:
        ingest_jd(jd["company"], jd["title"], jd["text"])
        print(f"  + JD          {jd['company']} — {jd['title']}")

    print(f"\nDone. Vector store holds {collection_size()} JDs.")
    print("\nDemo logins (password: Demo@1234)")
    print("  company@nimbus.dev")
    print("  company@brightpath.dev")
    print("  candidate@demo.dev")
    print("\nLive demo still works: log in as company and paste a new JD anytime.")


if __name__ == "__main__":
    main()
