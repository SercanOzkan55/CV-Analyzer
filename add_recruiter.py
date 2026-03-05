"""Add a test organization and recruiter user to the database.

Usage:
  python add_recruiter.py --supabase-id test-user-1 --email you@example.com

This uses the project's SQLAlchemy `SessionLocal` and models.
"""
import argparse
from database import SessionLocal, engine
from models import Organization, User, Base


def ensure_tables():
    # Ensure ORM tables exist (non-destructive)
    Base.metadata.create_all(bind=engine)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--supabase-id', required=True)
    p.add_argument('--email', required=True)
    p.add_argument('--org-name', default='Test Org')
    p.add_argument('--org-domain', default='testorg.local')
    args = p.parse_args()

    ensure_tables()

    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.domain == args.org_domain).first()
        if not org:
            org = Organization(name=args.org_name, domain=args.org_domain)
            db.add(org)
            db.commit()
            db.refresh(org)
            print(f"Created organization id={org.id}")
        else:
            print(f"Found organization id={org.id}")

        user = db.query(User).filter(User.supabase_id == args.supabase_id).first()
        if not user:
            user = User(supabase_id=args.supabase_id, email=args.email, role='recruiter', organization_id=org.id)
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Created user id={user.id} supabase_id={user.supabase_id}")
        else:
            print(f"Found user id={user.id} supabase_id={user.supabase_id}")

    finally:
        db.close()


if __name__ == '__main__':
    main()
