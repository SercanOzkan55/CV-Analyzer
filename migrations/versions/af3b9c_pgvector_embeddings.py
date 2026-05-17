"""add pgvector embeddings

Revision ID: af3b9c_pgvector_embeddings
Revises: add_billing_status_orgs
Create Date: 2026-03-04 12:00:00

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "af3b9c_pgvector_embeddings"
down_revision = "add_billing_status_orgs"
branch_labels = None
depends_on = None


def upgrade():
    # Create pgvector extension if missing
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # Fresh CI/dev databases may not have the legacy jobs table because early
    # Alembic revisions were written as production baselines. Create the small
    # table shape needed by the embedding migration without touching existing
    # production tables.
    op.execute(
        "CREATE TABLE IF NOT EXISTS jobs ("
        "id serial PRIMARY KEY,"
        "raw_text text,"
        "created_at timestamptz DEFAULT now()"
        ");"
    )

    # Create candidates table (if the project does not already manage it)
    op.execute(
        "CREATE TABLE IF NOT EXISTS candidates ("
        "id serial PRIMARY KEY,"
        "organization_id integer,"
        "name varchar,"
        "email varchar,"
        "phone varchar,"
        "cv_text text,"
        "cv_embedding vector(1536),"
        "created_at timestamptz DEFAULT now()"
        ");"
    )

    # Ensure columns exist for databases created before name/email/phone were added
    op.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS name varchar;")
    op.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS email varchar;")
    op.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS phone varchar;")

    # Add job_embedding column to existing jobs table if missing
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS job_embedding vector(1536);")

    # Create ivfflat indexes for efficient similarity search
    op.execute(
        "CREATE INDEX IF NOT EXISTS candidates_cv_embedding_idx ON candidates USING ivfflat (cv_embedding vector_cosine_ops) WITH (lists = 100);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS jobs_job_embedding_idx ON jobs USING ivfflat (job_embedding vector_cosine_ops) WITH (lists = 100);"
    )


def downgrade():
    # Drop indexes and columns/tables added in upgrade
    op.execute("DROP INDEX IF EXISTS candidates_cv_embedding_idx;")
    op.execute("DROP INDEX IF EXISTS jobs_job_embedding_idx;")
    # Remove job_embedding column
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS job_embedding;")
    # Drop candidates table
    op.execute("DROP TABLE IF EXISTS candidates;")
    # Note: we do not drop the pgvector extension on downgrade to avoid
    # removing it while other objects may depend on it.
