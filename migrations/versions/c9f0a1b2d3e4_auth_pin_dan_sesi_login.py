"""auth: PIN pada users + tabel sessions (login no.HP+PIN)

Revision ID: c9f0a1b2d3e4
Revises: 12e4f362ee11
Create Date: 2026-07-26 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9f0a1b2d3e4'
down_revision: Union[str, None] = '12e4f362ee11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pin_hash', sa.String(length=255), nullable=True))
        # Kolom NOT NULL pada tabel berisi data butuh server_default.
        batch_op.add_column(
            sa.Column('percobaan_gagal', sa.Integer(), nullable=False, server_default='0')
        )
        batch_op.add_column(
            sa.Column('terkunci_sampai', sa.DateTime(timezone=True), nullable=True)
        )

    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('dibuat_pada', sa.DateTime(timezone=True), nullable=False),
        sa.Column('kedaluwarsa_pada', sa.DateTime(timezone=True), nullable=False),
        # FK WAJIB dinamai (pelajaran repo: `drop_constraint(None)` gagal saat downgrade).
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_sessions_user'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)
    op.create_index(op.f('ix_sessions_token_hash'), 'sessions', ['token_hash'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_sessions_token_hash'), table_name='sessions')
    op.drop_index(op.f('ix_sessions_user_id'), table_name='sessions')
    op.drop_table('sessions')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('terkunci_sampai')
        batch_op.drop_column('percobaan_gagal')
        batch_op.drop_column('pin_hash')
