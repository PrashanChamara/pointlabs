"""Idempotent operational reminders intended for a scheduler/cron invocation."""
from datetime import datetime

from app.extensions import db
from app.models.hr import Notification, WorkspaceTask


def process_due_task_reminders(now=None):
    now = now or datetime.utcnow()
    tasks = WorkspaceTask.query.filter(
        WorkspaceTask.due_at.isnot(None), WorkspaceTask.due_at <= now,
        WorkspaceTask.completed_at.is_(None), WorkspaceTask.reminder_sent_at.is_(None),
    ).all()
    for task in tasks:
        db.session.add(Notification(user_id=task.user_id, message=f"Reminder: {task.title} is due."))
        task.reminder_sent_at = now
    db.session.commit()
    return len(tasks)
