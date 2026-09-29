"""create users table

Revision ID: 5df423b7be36
Revises:
Create Date: 2026-09-29
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "5df423b7be36"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
	op.create_table(
		"users",
		sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
		sa.Column("email", sa.String(length=255), nullable=False),
		sa.Column("hashed_password", sa.String(length=255), nullable=False),
		sa.Column("is_active", sa.Boolean(), nullable=False),
		sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
		sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
	)
	op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
	op.drop_index("ix_users_email", table_name="users")
	op.drop_table("users")
