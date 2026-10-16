"""initial schema

Revision ID: 3c2c83456a09
Revises: 
Create Date: 2026-10-16 15:33:42.296558

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c2c83456a09'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('photographers',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=True),
    sa.Column('ftp_username', sa.String(), nullable=False),
    sa.Column('ftp_password_hash', sa.String(), nullable=True),
    sa.Column('active_event_id', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('ftp_username')
    )
    op.create_table('events',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('photographer_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('gallery_token', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('full_album', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['photographer_id'], ['photographers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_events_gallery_token'), 'events', ['gallery_token'], unique=True)
    op.create_index(op.f('ix_events_photographer_id'), 'events', ['photographer_id'], unique=False)
    with op.batch_alter_table('photographers') as batch:
        batch.create_foreign_key(
            'photographers_active_event_id_fkey', 'events',
            ['active_event_id'], ['id'], ondelete='SET NULL',
        )
    op.create_table('guests',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('token', sa.String(), nullable=False),
    sa.Column('event_id', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('selfie_embedding', sa.Text(), nullable=False),
    sa.Column('match_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_guests_event_id'), 'guests', ['event_id'], unique=False)
    op.create_index(op.f('ix_guests_token'), 'guests', ['token'], unique=True)
    op.create_table('photos',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('photographer_id', sa.String(), nullable=False),
    sa.Column('event_id', sa.String(), nullable=True),
    sa.Column('s3_raw_key', sa.String(), nullable=False),
    sa.Column('s3_thumb_key', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('face_count', sa.Integer(), nullable=False),
    sa.Column('shot_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['photographer_id'], ['photographers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_photos_event_id'), 'photos', ['event_id'], unique=False)
    op.create_index(op.f('ix_photos_photographer_id'), 'photos', ['photographer_id'], unique=False)
    op.create_table('faces',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('photo_id', sa.String(), nullable=False),
    sa.Column('event_id', sa.String(), nullable=True),
    sa.Column('embedding', sa.Text(), nullable=False),
    sa.Column('bbox', sa.Text(), nullable=True),
    sa.Column('det_score', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['photo_id'], ['photos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_faces_event_id'), 'faces', ['event_id'], unique=False)
    op.create_index(op.f('ix_faces_photo_id'), 'faces', ['photo_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_faces_photo_id'), table_name='faces')
    op.drop_index(op.f('ix_faces_event_id'), table_name='faces')
    op.drop_table('faces')
    op.drop_index(op.f('ix_photos_photographer_id'), table_name='photos')
    op.drop_index(op.f('ix_photos_event_id'), table_name='photos')
    op.drop_table('photos')
    op.drop_index(op.f('ix_guests_token'), table_name='guests')
    op.drop_index(op.f('ix_guests_event_id'), table_name='guests')
    op.drop_table('guests')
    with op.batch_alter_table('photographers') as batch:
        batch.drop_constraint('photographers_active_event_id_fkey', type_='foreignkey')
    op.drop_index(op.f('ix_events_photographer_id'), table_name='events')
    op.drop_index(op.f('ix_events_gallery_token'), table_name='events')
    op.drop_table('events')
    op.drop_table('photographers')
