"""knowledge base documents

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("source_name", sa.String(255), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_documents")),
        sa.UniqueConstraint("content_hash", name=op.f("uq_knowledge_documents_content_hash")),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], name=op.f("fk_knowledge_documents_uploaded_by_users"), ondelete="SET NULL"),
    )


def downgrade() -> None:
    op.drop_table("knowledge_documents")
