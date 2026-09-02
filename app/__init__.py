import os

from flask import Flask

from config import config_by_name
from app.extensions import db, migrate, login_manager, csrf


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name.get(config_name, config_by_name["development"]))

    # --- Initialize extensions ---------------------------------------------
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Ensure every model is registered on db.metadata before migrations run.
    from app import models  # noqa: F401

    # --- Template filters ----------------------------------------------------
    # UI-only label mask for the Users admin page: the seeded bootstrap
    # account's name/designation contain the literal text "Super
    # Administrator", which per spec should never be shown to users on that
    # page. This only affects display - the underlying SUPER_ADMIN role and
    # the stored full_name/designation values are untouched.
    @app.template_filter("mask_super_admin_label")
    def mask_super_admin_label(value):
        if value and "Super Administrator" in value:
            return "—"
        return value

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User

        return db.session.get(User, int(user_id))

    # Manual URL access to a protected endpoint by an unauthenticated user
    # should behave like any other unauthorized access (see error handlers
    # below) rather than silently redirecting past the login page.
    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import redirect, request, url_for

        return redirect(url_for("auth.login", next=request.path))

    # --- Register blueprints -------------------------------------------------
    from app.routes.auth import bp as auth_bp
    from app.routes.main import bp as main_bp
    from app.routes.admin import bp as admin_bp
    from app.routes.activity_details import bp as act_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(act_bp)

    # --- Error handlers -------------------------------------------------------
    from app.utils.errors import register_error_handlers

    register_error_handlers(app)

    # --- Force password change for accounts still on a default password ------
    # Server-side gate (not just hiding nav links): an authenticated user
    # flagged must_change_password can only reach the change-password page,
    # logout, static assets, or the health check until they set a new
    # password.
    _ALLOWED_WHILE_MUST_CHANGE_PASSWORD = {
        "auth.change_password",
        "auth.logout",
        "static",
        "healthz",
    }

    @app.before_request
    def _enforce_password_change():
        from flask import request, redirect, url_for
        from flask_login import current_user

        if (
            current_user.is_authenticated
            and getattr(current_user, "must_change_password", False)
            and request.endpoint not in _ALLOWED_WHILE_MUST_CHANGE_PASSWORD
        ):
            return redirect(url_for("auth.change_password"))

    # --- Default Super Admin bootstrap ----------------------------------------
    # "Create automatically during initialization" per spec - runs on every
    # app start, is idempotent, and never recreates/overwrites an existing
    # account. Safe no-op if the schema isn't migrated yet.
    with app.app_context():
        from app.utils.init_data import create_default_super_admin

        create_default_super_admin()

    # --- Health check (useful for verifying deploy + DB connectivity) -------
    @app.get("/healthz")
    def healthz():
        from sqlalchemy import text

        try:
            db.session.execute(text("SELECT 1"))
            db_status = "ok"
        except Exception as exc:  # noqa: BLE001
            db_status = f"error: {exc}"
        return {"status": "ok", "database": db_status}

    return app
