"""add knowledge base tables

Revision ID: 20260519_0006
Revises: 20260519_0005
Create Date: 2026-05-19 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision: str = "20260519_0006"
down_revision: Union[str, None] = "20260519_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("factory_id", sa.BigInteger(), sa.ForeignKey("factories.id"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("document_type", sa.String(length=30), nullable=False),
        sa.Column("equipment_model_id", sa.BigInteger(), sa.ForeignKey("equipment_models.id"), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_uri", sa.Text(), nullable=True),
        sa.Column("source_label", sa.String(length=200), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_knowledge_documents_factory", "knowledge_documents", ["factory_id"])
    op.create_index("idx_knowledge_documents_equipment_model", "knowledge_documents", ["equipment_model_id"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "document_id",
            sa.BigInteger(),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_no", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(length=200), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_knowledge_chunks_document", "knowledge_chunks", ["document_id", "chunk_no"])
    op.create_index("idx_knowledge_chunks_metadata", "knowledge_chunks", ["metadata"], postgresql_using="gin")
    op.execute(
        "CREATE INDEX idx_knowledge_chunks_embedding "
        "ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.drop_index("idx_knowledge_chunks_embedding", table_name="knowledge_chunks")
    op.drop_index("idx_knowledge_chunks_metadata", table_name="knowledge_chunks")
    op.drop_index("idx_knowledge_chunks_document", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index("idx_knowledge_documents_equipment_model", table_name="knowledge_documents")
    op.drop_index("idx_knowledge_documents_factory", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
