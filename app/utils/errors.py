"""Central error handler registration (401/403/404/500 + CSRF)."""

import logging

from flask import render_template
from flask_wtf.csrf import CSRFError

from app.extensions import db

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    @app.errorhandler(401)
    def unauthorized(_e):
        return render_template("errors/401.html"), 401

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        # Expired/missing/invalid CSRF token on a form submission.
        # Never expose the raw flask_wtf message to the end user.
        logger.warning("CSRF validation failed: %s", e.description)
        return render_template("errors/400.html", reason="Your session security "
                                "token expired or was invalid. Please go back and "
                                "resubmit the form."), 400

    @app.errorhandler(500)
    def internal_error(e):
        # Roll back any half-committed transaction so the DB session isn't
        # left in a broken state, and never leak the exception/traceback or
        # raw DB error text to the client.
        db.session.rollback()
        logger.exception("Unhandled server error: %s", e)
        return render_template("errors/500.html"), 500
