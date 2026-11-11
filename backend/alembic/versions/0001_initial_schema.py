"""Initial Phase 1 schema: users, auth methods, sessions, and cards.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-02 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Create users table if not exists
    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("username", sa.String(length=64), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False, server_default="USER"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_users_username", "users", ["username"], unique=True)
        op.create_index("ix_users_email", "users", ["email"], unique=True)
        op.create_index("ix_users_role", "users", ["role"], unique=False)
        op.create_index("ix_users_is_active", "users", ["is_active"], unique=False)

    # 2. Create user_auth_methods table if not exists
    if "user_auth_methods" not in existing_tables:
        op.create_table(
            "user_auth_methods",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_user_auth_methods_user_id"), nullable=False),
            sa.Column("auth_provider", sa.String(length=32), nullable=False, server_default="local"),
            sa.Column("password_hash", sa.String(length=255), nullable=True),
            sa.Column("provider_subject", sa.String(length=255), nullable=True),
            sa.Column("provider_metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_user_auth_methods_user_id", "user_auth_methods", ["user_id"], unique=False)
        op.create_index("ix_user_auth_methods_provider_subject", "user_auth_methods", ["provider_subject"], unique=False)

    # 3. Create user_sessions table if not exists
    if "user_sessions" not in existing_tables:
        op.create_table(
            "user_sessions",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_user_sessions_user_id"), nullable=False),
            sa.Column("session_token_hash", sa.String(length=64), nullable=False),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("user_agent", sa.String(length=512), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"], unique=False)
        op.create_index("ix_user_sessions_session_token_hash", "user_sessions", ["session_token_hash"], unique=True)
        op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"], unique=False)

    # 4. Handle cards table (legacy upgrade or fresh create)
    if "cards" not in existing_tables:
        op.create_table(
            "cards",
            sa.Column("public_id", sa.String(length=64), primary_key=True, nullable=False),
            sa.Column("serial", sa.Text(), nullable=False),
            sa.Column("game_id", sa.String(length=64), nullable=True),
            sa.Column("grid", sa.JSON(), nullable=False),
            sa.Column("owner_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_cards_owner_id"), nullable=True),
            sa.Column("is_persistent", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_cards_game_id", "cards", ["game_id"], unique=False)
        op.create_index("ix_cards_owner_id", "cards", ["owner_id"], unique=False)
    else:
        # Legacy cards table existed: add new columns if not present
        columns = [col["name"] for col in inspector.get_columns("cards")]
        with op.batch_alter_table("cards") as batch_op:
            if "owner_id" not in columns:
                batch_op.add_column(
                    sa.Column("owner_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_cards_owner_id"), nullable=True)
                )
                batch_op.create_index("ix_cards_owner_id", ["owner_id"], unique=False)
            if "is_persistent" not in columns:
                batch_op.add_column(
                    sa.Column("is_persistent", sa.Boolean(), nullable=False, server_default=sa.true())
                )
            if "created_at" not in columns:
                batch_op.add_column(
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
                )
            if "game_id" in columns:
                existing_indexes = [idx["name"] for idx in inspector.get_indexes("cards")]
                if "ix_cards_game_id" not in existing_indexes:
                    batch_op.create_index("ix_cards_game_id", ["game_id"], unique=False)


def downgrade() -> None:
    op.drop_table("user_sessions")
    op.drop_table("user_auth_methods")
    op.drop_table("users")
    # We do not drop cards completely to protect card data on rollback
