"""
Default Super Admin bootstrap.

Creates the fixed PIA super-admin account automatically during app
initialization, if (and only if) it doesn't already exist. Idempotent and
safe to run on every app start - it never touches the row once it exists,
so an operator can freely rename/deactivate/reset it later without this
code re-creating or overwriting it.
"""

import logging

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models.user import Role, User

logger = logging.getLogger(__name__)

DEFAULT_SUPER_ADMIN_USERNAME = "PIA"
DEFAULT_SUPER_ADMIN_PASSWORD = "QA@12345"


def create_default_super_admin() -> None:
    """
    Idempotently ensure the default SUPER_ADMIN account exists.

    Must be called inside an app context. Swallows database errors (e.g.
    migrations not yet applied on a fresh checkout) so that importing/
    booting the app never crashes because of this bootstrap step - it
    simply logs and skips, and will succeed on the next start once the
    schema is in place.
    """
    try:
        existing = User.query.filter_by(username=DEFAULT_SUPER_ADMIN_USERNAME).first()
        if existing is not None:
            return

        admin = User(
            full_name="PIA Super Administrator",
            username=DEFAULT_SUPER_ADMIN_USERNAME,
            employee_no="PIA-SUPERADMIN",
            role=Role.SUPER_ADMIN,
            designation="Super Administrator",
            station_id=None,  # SUPER_ADMIN is not station-scoped
            is_active=True,
            must_change_password=True,
        )
        admin.set_password(DEFAULT_SUPER_ADMIN_PASSWORD)
        db.session.add(admin)
        db.session.commit()
        logger.info("Created default super admin account (username: %s)", DEFAULT_SUPER_ADMIN_USERNAME)
    except SQLAlchemyError:
        db.session.rollback()
        logger.warning(
            "Could not create default super admin - schema may not be migrated yet. "
            "It will be created automatically on the next successful startup."
        )
