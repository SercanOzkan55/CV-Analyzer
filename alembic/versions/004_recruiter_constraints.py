"""Add recruiter database constraints for data integrity

Revision ID: 004_recruiter_constraints
Revises: None
Create Date: 2026-04-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004_recruiter_constraints'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply database constraints"""
    
    # Check if constraints already exist (for idempotency)
    # Note: PostgreSQL specific constraints
    # For SQLite, these will be silently ignored (SQLite has limited constraint support)
    
    try:
        # Add constraint: future dates for reminders (PostgreSQL only)
        op.execute("""
            ALTER TABLE reminders 
            ADD CONSTRAINT check_future_date 
            CHECK (event_date > NOW());
        """)
    except Exception:
        # SQLite or constraint already exists
        pass
    
    try:
        # Add constraint: email format for reminders (PostgreSQL only)
        op.execute("""
            ALTER TABLE reminders 
            ADD CONSTRAINT check_email_format 
            CHECK (target_email ~ '^[^@]+@[^@]+\\.[^@]+$');
        """)
    except Exception:
        pass
    
    try:
        # Add constraint: title length for reminders
        op.execute("""
            ALTER TABLE reminders 
            ADD CONSTRAINT check_title_length 
            CHECK (length(title) BETWEEN 1 AND 500);
        """)
    except Exception:
        pass
    
    try:
        # Add constraint: description length for reminders
        op.execute("""
            ALTER TABLE reminders 
            ADD CONSTRAINT check_description_length 
            CHECK (length(coalesce(description, '')) <= 1000);
        """)
    except Exception:
        pass


def downgrade() -> None:
    """Remove database constraints"""
    
    # Try to drop constraints (PostgreSQL specific)
    try:
        op.execute("ALTER TABLE reminders DROP CONSTRAINT IF EXISTS check_future_date;")
    except Exception:
        pass
    
    try:
        op.execute("ALTER TABLE reminders DROP CONSTRAINT IF EXISTS check_email_format;")
    except Exception:
        pass
    
    try:
        op.execute("ALTER TABLE reminders DROP CONSTRAINT IF EXISTS check_title_length;")
    except Exception:
        pass
    
    try:
        op.execute("ALTER TABLE reminders DROP CONSTRAINT IF EXISTS check_description_length;")
    except Exception:
        pass
