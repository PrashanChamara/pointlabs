"""add configurable approval workflows and HR service catalogue

Revision ID: b9e5c2a67d42
Revises: a8d4e0f25b31
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

revision = "b9e5c2a67d42"
down_revision = "a8d4e0f25b31"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("approval_workflow",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("applies_to", sa.String(40), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("user.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_approval_workflow_applies_to", "approval_workflow", ["applies_to"])
    op.create_index("ix_approval_workflow_is_active", "approval_workflow", ["is_active"])
    op.create_table("approval_workflow_step",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("approval_workflow.id"), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("approval_mode", sa.String(12), nullable=False, server_default="any"),
        sa.Column("approver_kind", sa.String(24), nullable=False, server_default="designation"),
        sa.Column("designation_id", sa.Integer(), sa.ForeignKey("designation.id")),
        sa.Column("approver_user_id", sa.Integer(), sa.ForeignKey("user.id")),
        sa.UniqueConstraint("workflow_id", "step_order", name="uq_approval_workflow_step_order"),
    )
    op.create_index("ix_approval_workflow_step_workflow_id", "approval_workflow_step", ["workflow_id"])
    op.create_table("approval_instance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("approval_workflow.id"), nullable=False),
        sa.Column("subject_type", sa.String(40), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("requester_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("current_step_order", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
        sa.UniqueConstraint("subject_type", "subject_id", name="uq_approval_subject"),
    )
    for name, fields in (("ix_approval_instance_workflow_id", ["workflow_id"]), ("ix_approval_instance_subject_type", ["subject_type"]), ("ix_approval_instance_subject_id", ["subject_id"]), ("ix_approval_instance_status", ["status"])):
        op.create_index(name, "approval_instance", fields)
    op.create_table("approval_decision",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("approval_instance_id", sa.Integer(), sa.ForeignKey("approval_instance.id"), nullable=False),
        sa.Column("workflow_step_id", sa.Integer(), sa.ForeignKey("approval_workflow_step.id"), nullable=False),
        sa.Column("approver_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("comment", sa.Text()), sa.Column("acted_at", sa.DateTime()),
        sa.UniqueConstraint("approval_instance_id", "workflow_step_id", "approver_id", name="uq_approval_decision"),
    )
    for name, fields in (("ix_approval_decision_approval_instance_id", ["approval_instance_id"]), ("ix_approval_decision_approver_id", ["approver_id"]), ("ix_approval_decision_status", ["status"])):
        op.create_index(name, "approval_decision", fields)
    op.create_table("request_type",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500)), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("approval_workflow.id")), sa.Column("created_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("name"),
    )
    op.create_index("ix_request_type_is_active", "request_type", ["is_active"])
    request_types = sa.table("request_type", sa.column("name", sa.String), sa.column("description", sa.String), sa.column("is_active", sa.Boolean), sa.column("created_at", sa.DateTime))
    op.bulk_insert(request_types, [
        {"name": name, "description": "Initial Pointlabs HR service catalogue item.", "is_active": True, "created_at": datetime.utcnow()}
        for name in (
            "Salary Certificate", "Employment / Experience Certificate", "Employment Verification Letter",
            "NOC Request", "Salary Transfer Letter", "Personal Information Update",
            "Employee Document Copy Request", "Visa Application Support Letter", "Other HR Request",
        )
    ])
    with op.batch_alter_table("other_request") as batch:
        batch.add_column(sa.Column("request_type_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_other_request_request_type", "request_type", ["request_type_id"], ["id"])
    op.create_index("ix_other_request_request_type_id", "other_request", ["request_type_id"])


def downgrade():
    op.drop_index("ix_other_request_request_type_id", table_name="other_request")
    with op.batch_alter_table("other_request") as batch:
        batch.drop_column("request_type_id")
    op.drop_index("ix_request_type_is_active", table_name="request_type"); op.drop_table("request_type")
    for name in ("ix_approval_decision_status", "ix_approval_decision_approver_id", "ix_approval_decision_approval_instance_id"): op.drop_index(name, table_name="approval_decision")
    op.drop_table("approval_decision")
    for name in ("ix_approval_instance_status", "ix_approval_instance_subject_id", "ix_approval_instance_subject_type", "ix_approval_instance_workflow_id"): op.drop_index(name, table_name="approval_instance")
    op.drop_table("approval_instance")
    op.drop_index("ix_approval_workflow_step_workflow_id", table_name="approval_workflow_step"); op.drop_table("approval_workflow_step")
    op.drop_index("ix_approval_workflow_is_active", table_name="approval_workflow"); op.drop_index("ix_approval_workflow_applies_to", table_name="approval_workflow"); op.drop_table("approval_workflow")
