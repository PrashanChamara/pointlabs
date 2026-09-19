"""backfill leave type codes

Revision ID: ac19c777da37
Revises: b7e4f2a9d301
Create Date: 2026-09-19 11:57:24.247460

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ac19c777da37'
down_revision = 'b7e4f2a9d301'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    mappings = {
        "Annual Leave": "ANNUAL",
        "Sick Leave": "SICK",
        "Paternity Leave": "PATERNITY",
        "Maternity Leave": "MATERNITY",
        "Compassionate Leave": "COMPASSIONATE",
        "Off in Lieu": "OFF_IN_LIEU",
        "WFH": "WFH",
        "Leave Without Pay": "LWP",
    }

    for name, code in mappings.items():
        bind.execute(
            sa.text(
                """
                UPDATE leave_type
                SET code = :code
                WHERE name = :name
                  AND (code IS NULL OR TRIM(code) = '')
                """
            ),
            {"name": name, "code": code},
        )

def downgrade():
    """Deliberately leave repaired codes intact.

    This is a data-repair migration.  Clearing a code during downgrade could
    erase an administrator's later, intentional code change, so downgrade is
    safely non-destructive.
    """
    pass
