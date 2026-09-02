from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models.user import User
from app.utils.audit import log_action

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash("Invalid username or password.", "danger")
            return render_template("auth/login.html"), 401

        if not user.is_active:
            flash("This account has been deactivated. Contact your administrator.", "danger")
            return render_template("auth/login.html"), 403

        login_user(user, remember=bool(request.form.get("remember")))
        log_action("LOGIN", "User", user.id, f"User {user.username} logged in")
        db.session.commit()

        if user.must_change_password:
            flash("You're using a default password. Please set a new one to continue.", "warning")
            return redirect(url_for("auth.change_password"))

        next_page = request.args.get("next")
        return redirect(next_page or url_for("main.dashboard"))

    return render_template("auth/login.html")


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    forced = current_user.must_change_password

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        errors = []

        if not current_user.check_password(current_password):
            errors.append("Current password is incorrect.")
        if not new_password or len(new_password) < 6:
            errors.append("New password must be at least 6 characters.")
        if new_password != confirm_password:
            errors.append("New passwords do not match.")
        if new_password and current_user.check_password(new_password):
            errors.append("New password must be different from the current password.")

        if not errors:
            current_user.set_password(new_password)
            current_user.must_change_password = False
            log_action(
                "PASSWORD_CHANGE",
                "User",
                current_user.id,
                f"User {current_user.username} changed their password",
            )
            db.session.commit()
            flash("Password updated successfully.", "success")
            return redirect(url_for("main.dashboard") if forced else url_for("main.profile"))

        for e in errors:
            flash(e, "danger")

    return render_template("auth/change_password.html", forced=forced)


@bp.route("/logout")
@login_required
def logout():
    log_action("LOGOUT", "User", current_user.id, f"User {current_user.username} logged out")
    db.session.commit()
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
