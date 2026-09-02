from flask_login import current_user

from app.extensions import db
from app.models.audit_log import AuditLog


def log_action(action: str, entity_type: str, entity_id=None, details: str = None):
    """
    Write a single audit log row. Call this from route/service code whenever
    a meaningful state change happens (create/update/delete/login/etc).

    Does NOT commit — callers should commit as part of their existing
    transaction so the audit entry is atomic with the change it describes.
    """
    user_id = None
    try:
        if current_user and current_user.is_authenticated:
            user_id = current_user.id
    except RuntimeError:
        # Outside of an app/request context (e.g. CLI/seed scripts).
        user_id = None

    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    db.session.add(entry)
    return entry
