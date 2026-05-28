"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String, nullable=False, unique=True),
        sa.Column("oauth_subject", sa.String, nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False, unique=True),
        sa.Column("default_el", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default="true"),
    )

    op.create_table(
        "profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("topic", sa.String, nullable=False),
        sa.Column("el", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("last_seen", sa.DateTime),
        sa.Column(
            "contribute_to_corpus",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.UniqueConstraint("user_id", "topic", name="uq_profiles_user_topic"),
    )

    op.create_table(
        "facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.Enum("A", "B", "C", "D", name="factcategory"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("why_it_matters", sa.Text),
        sa.Column("reviewed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("accuracy_score", sa.Float),
        sa.Column(
            "source",
            sa.Enum("official", "community", name="factsource"),
            nullable=False,
            server_default="official",
        ),
        sa.Column(
            "contributed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
    )

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("surface_id", sa.String, nullable=False),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("ended_at", sa.DateTime),
        sa.Column(
            "status",
            sa.Enum("active", "ended", name="sessionstatus"),
            nullable=False,
            server_default="active",
        ),
    )
    op.create_index("ix_sessions_user_surface", "sessions", ["user_id", "surface_id"])

    op.create_table(
        "fact_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "fact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("facts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("shown_at", sa.DateTime, nullable=False),
        sa.Column("was_repeat", sa.Boolean, nullable=False, server_default="false"),
    )

    op.create_table(
        "quiz_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "fact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("facts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("locked_answer", sa.Text, nullable=False),
        sa.Column("user_answer", sa.Text),
        sa.Column(
            "verdict",
            sa.Enum("correct", "incorrect", "pending", name="quizverdict"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("quiz_attempts")
    op.drop_table("fact_events")
    op.drop_index("ix_sessions_user_surface", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("facts")
    op.drop_table("profiles")
    op.drop_table("topics")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS quizverdict")
    op.execute("DROP TYPE IF EXISTS sessionstatus")
    op.execute("DROP TYPE IF EXISTS factsource")
    op.execute("DROP TYPE IF EXISTS factcategory")
