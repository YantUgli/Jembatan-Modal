"""sub-produk: recipe_items boleh menunjuk produk

Satu baris resep kini menunjuk **salah satu** dari dua hal:
  - `cost_item_id` → bahan yang dibeli
  - `product_id`   → sub-produk (barang setengah jadi dengan resep sendiri)

CHECK constraint ditulis tangan: alembic autogenerate tidak mendeteksi
CheckConstraint, jadi tanpa baris ini skema akan menerima baris resep yang
mengisi dua-duanya atau kosong dua-duanya.

Revision ID: 1c754871498c
Revises: 3d659af26c6b
Create Date: 2026-07-19 00:03:30.912739
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c754871498c'
down_revision: Union[str, None] = '3d659af26c6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CK_NAMA = "ck_recipe_items_bahan_atau_subproduk"
FK_NAMA = "fk_recipe_items_product_id_products"


def upgrade() -> None:
    with op.batch_alter_table('recipe_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('product_id', sa.Integer(), nullable=True))
        batch_op.alter_column('cost_item_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.create_index(batch_op.f('ix_recipe_items_product_id'), ['product_id'], unique=False)
        batch_op.create_foreign_key(FK_NAMA, 'products', ['product_id'], ['id'])
        batch_op.create_check_constraint(
            CK_NAMA,
            "(cost_item_id IS NOT NULL) <> (product_id IS NOT NULL)",
        )


def downgrade() -> None:
    # Baris resep yang menunjuk sub-produk tidak punya padanan di skema lama —
    # dibuang, kalau tidak `cost_item_id NOT NULL` akan gagal.
    op.execute("DELETE FROM recipe_items WHERE product_id IS NOT NULL")
    with op.batch_alter_table('recipe_items', schema=None) as batch_op:
        batch_op.drop_constraint(CK_NAMA, type_='check')
        batch_op.drop_constraint(FK_NAMA, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_recipe_items_product_id'))
        batch_op.alter_column('cost_item_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.drop_column('product_id')
