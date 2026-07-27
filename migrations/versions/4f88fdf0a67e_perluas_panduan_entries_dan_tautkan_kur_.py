"""perluas panduan_entries dan tautkan kur_outcomes

Revision ID: 4f88fdf0a67e
Revises: c9f0a1b2d3e4
Create Date: 2026-07-27 15:09:13.943989
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f88fdf0a67e'
down_revision: Union[str, None] = 'c9f0a1b2d3e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FK_KUR_OUTCOME_PANDUAN = "fk_kur_outcomes_panduan_entry"
FK_PANDUAN_DIGANTIKAN_OLEH = "fk_panduan_entries_digantikan_oleh"


def upgrade() -> None:
    # FK WAJIB dinamai: autogenerate menulis `None`, dan `drop_constraint(None)`
    # di downgrade akan gagal (pelajaran yang berulang di repo ini — lihat
    # 12e4f362ee11 & c9f0a1b2d3e4).
    with op.batch_alter_table('kur_outcomes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('panduan_entry_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            FK_KUR_OUTCOME_PANDUAN, 'panduan_entries', ['panduan_entry_id'], ['id']
        )

    with op.batch_alter_table('panduan_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pertanyaan_kanonik', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('tingkat_sumber', sa.Enum('resmi_regulasi', 'resmi_bank', 'lainnya', name='tingkat_sumber'), nullable=False))
        batch_op.add_column(sa.Column('versi_regulasi', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('pasal_rujukan', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('tanggal_berlaku', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('tanggal_tinjau', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('status', sa.Enum('aktif', 'superseded', name='status_panduan'), nullable=False))
        batch_op.add_column(sa.Column('digantikan_oleh', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            FK_PANDUAN_DIGANTIKAN_OLEH, 'panduan_entries', ['digantikan_oleh'], ['id']
        )
        batch_op.drop_column('berlaku_sampai')


def downgrade() -> None:
    with op.batch_alter_table('panduan_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('berlaku_sampai', sa.DATE(), nullable=True))
        batch_op.drop_constraint(FK_PANDUAN_DIGANTIKAN_OLEH, type_='foreignkey')
        batch_op.drop_column('digantikan_oleh')
        batch_op.drop_column('status')
        batch_op.drop_column('tanggal_tinjau')
        batch_op.drop_column('tanggal_berlaku')
        batch_op.drop_column('pasal_rujukan')
        batch_op.drop_column('versi_regulasi')
        batch_op.drop_column('tingkat_sumber')
        batch_op.drop_column('pertanyaan_kanonik')

    with op.batch_alter_table('kur_outcomes', schema=None) as batch_op:
        batch_op.drop_constraint(FK_KUR_OUTCOME_PANDUAN, type_='foreignkey')
        batch_op.drop_column('panduan_entry_id')
