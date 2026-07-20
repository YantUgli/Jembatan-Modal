"""faktor kehilangan pada resep

Revision ID: 558cbb5a8d3e
Revises: 1c754871498c
Create Date: 2026-07-19 01:13:52.324126
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '558cbb5a8d3e'
down_revision: Union[str, None] = '1c754871498c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CK_NAMA = "ck_recipes_faktor_kehilangan_wajar"


def upgrade() -> None:
    # CHECK constraint ditulis tangan — autogenerate alembic tidak mendeteksi
    # CheckConstraint (pelajaran yang sama dengan migrasi 1c754871498c).
    with op.batch_alter_table('recipes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('faktor_kehilangan', sa.Numeric(precision=6, scale=4), nullable=True))
        batch_op.create_check_constraint(
            CK_NAMA,
            "faktor_kehilangan IS NULL OR (faktor_kehilangan >= 0 AND faktor_kehilangan < 1)",
        )


def downgrade() -> None:
    with op.batch_alter_table('recipes', schema=None) as batch_op:
        batch_op.drop_constraint(CK_NAMA, type_='check')
        batch_op.drop_column('faktor_kehilangan')
