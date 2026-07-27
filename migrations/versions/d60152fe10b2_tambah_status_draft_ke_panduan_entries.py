"""tambah status draft ke panduan entries

Revision ID: d60152fe10b2
Revises: 4f88fdf0a67e
Create Date: 2026-07-27 15:58:11.010812
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd60152fe10b2'
down_revision: Union[str, None] = '4f88fdf0a67e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite (dev): enum ini tersimpan sebagai VARCHAR tanpa CHECK constraint
    # (autogenerate tidak mendeteksi diff apa pun di sini) — tak ada yang
    # perlu diubah. Postgres (target produksi): tipe enum asli butuh nilai
    # baru ditambahkan eksplisit.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE status_panduan ADD VALUE IF NOT EXISTS 'draft'")


def downgrade() -> None:
    # Postgres tidak mendukung penghapusan nilai enum tanpa membangun ulang
    # tipe (rename → buat baru → cast kolom → hapus lama); belum ada
    # database produksi nyata yang butuh ini, jadi downgrade sengaja no-op.
    # SQLite: upgrade() tidak mengubah apa pun, jadi tak ada yang dikembalikan.
    pass
