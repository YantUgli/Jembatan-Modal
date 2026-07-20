"""jalur reseller: susut & konversi satuan

Revision ID: f680a7bfc3e3
Revises: 558cbb5a8d3e
Create Date: 2026-07-19 01:54:35.207268
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f680a7bfc3e3'
down_revision: Union[str, None] = '558cbb5a8d3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CK_FAKTOR = "ck_products_faktor_kehilangan_wajar"
CK_ISI = "ck_products_isi_positif"
CK_SATUAN = "ck_products_konversi_butuh_satuan"


def upgrade() -> None:
    # CHECK constraint ditulis tangan — autogenerate alembic tidak mendeteksinya.
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('satuan_beli', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('satuan_jual', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('isi_per_satuan_beli', sa.Numeric(precision=14, scale=3), nullable=True))
        batch_op.add_column(sa.Column('faktor_kehilangan', sa.Numeric(precision=6, scale=4), nullable=True))
        batch_op.create_check_constraint(
            CK_FAKTOR,
            "faktor_kehilangan IS NULL OR (faktor_kehilangan >= 0 AND faktor_kehilangan < 1)",
        )
        batch_op.create_check_constraint(
            CK_ISI, "isi_per_satuan_beli IS NULL OR isi_per_satuan_beli > 0"
        )
        batch_op.create_check_constraint(
            CK_SATUAN,
            "isi_per_satuan_beli IS NULL "
            "OR (satuan_beli IS NOT NULL AND satuan_jual IS NOT NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_constraint(CK_SATUAN, type_='check')
        batch_op.drop_constraint(CK_ISI, type_='check')
        batch_op.drop_constraint(CK_FAKTOR, type_='check')
        batch_op.drop_column('faktor_kehilangan')
        batch_op.drop_column('isi_per_satuan_beli')
        batch_op.drop_column('satuan_jual')
        batch_op.drop_column('satuan_beli')
