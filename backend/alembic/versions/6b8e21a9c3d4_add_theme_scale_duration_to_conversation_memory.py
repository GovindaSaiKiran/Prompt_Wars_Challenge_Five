"""add_theme_scale_duration_to_conversation_memory

Revision ID: 6b8e21a9c3d4
Revises: 43dcd9beb2eb
Create Date: 2026-11-01 02:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b8e21a9c3d4'
down_revision: Union[str, Sequence[str], None] = '43dcd9beb2eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to support flexible theme, scale, duration, and format attributes."""
    with op.batch_alter_table('conversation_memories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('theme', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('scale', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('duration', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('format_type', sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('conversation_memories', schema=None) as batch_op:
        batch_op.drop_column('format_type')
        batch_op.drop_column('duration')
        batch_op.drop_column('scale')
        batch_op.drop_column('theme')
