from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_add_enhanced_table"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "echo_messages_enhanced",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_message_id", sa.Integer(), sa.ForeignKey("echo_messages.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("enhanced_content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_table("echo_messages_enhanced")

