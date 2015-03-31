"""empty message

Revision ID: 2b08988270a4
Revises: None
Create Date: 2015-03-30 22:29:39.600471

"""

# revision identifiers, used by Alembic.
revision = '2b08988270a4'
down_revision = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('servers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('url', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('services',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('server_id', sa.Integer(), nullable=True),
    sa.Column('service_data', postgresql.JSON(), nullable=True),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('service_type', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['server_id'], ['servers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('layers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('service_id', sa.Integer(), nullable=True),
    sa.Column('layer_data', postgresql.JSON(), nullable=True),
    sa.Column('name', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['service_id'], ['services.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('layers')
    op.drop_table('services')
    op.drop_table('servers')
    ### end Alembic commands ###
