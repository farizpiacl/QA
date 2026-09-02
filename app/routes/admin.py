"""
Module 3: Super Admin dashboard + User/Station/Shift/Airline/Aircraft
management, and the audit log viewer.

Every route in this blueprint is SUPER_ADMIN-only, enforced with
`roles_required` (server-side — never relies on the nav being hidden), same
pattern as the rest of the app.

Activity forms are explicitly out of scope for this module (per spec) — the
"Activities" nav entry links to a placeholder page.
"""

from datetime import date, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.activity import Activity, ActivityStatus, ActivityType
from app.models.user import User, Role
from app.models.station import Station
from app.models.shift import Shift
from app.models.airline import Airline
from app.models.aircraft import Aircraft
from app.models.audit_log import AuditLog
from app.utils.authz import roles_required, apply_activity_scope
from app.utils.audit import log_action
from app.utils.dashboard import get_dashboard_stats
from app.utils.activity_details import can_edit_activity, can_delete_activity
from app.utils.reports import (
    get_filter_choices,
    apply_common_filters,
    sub_type_label,
    REPORT_TYPES,
    REPORT_LABELS,
    run_report,
    export_excel,
    export_pdf,
    list_export_rows,
    aggregate_export_rows,
    LIST_HEADERS,
    AGGREGATE_HEADERS,
)

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _parse_time(value):
    """Parse an HTML <input type=time> value ('HH:MM') into a Python time, or None."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        return None


# Roles a SUPER_ADMIN may assign through the normal "create/edit user" form.
# SUPER_ADMIN is intentionally excluded here — creating another Super Admin
# account is a separate, more heavily-guarded action (see
# create_super_admin below), per spec: "Do not allow normal users to create
# Super Admin accounts unless explicitly designed as a protected Super
# Admin function."
ASSIGNABLE_ROLES = [Role.CE_QA, Role.DCE_QA, Role.AIRCRAFT_ENGINEER]


@bp.before_request
@login_required
@roles_required(Role.SUPER_ADMIN)
def _guard():
    """Applies the same login+role guard to every route in this blueprint."""
    return None


# --------------------------------------------------------------------------
# Dashboard shell
# --------------------------------------------------------------------------

@bp.route("/")
def dashboard():
    stats = {
        "users": User.query.count(),
        "active_users": User.query.filter_by(is_active=True).count(),
        "stations": Station.query.count(),
        "shifts": Shift.query.count(),
        "airlines": Airline.query.count(),
        "aircraft": Aircraft.query.count(),
    }
    activity_stats = get_dashboard_stats(current_user)
    recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(8).all()
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        activity_stats=activity_stats,
        recent_logs=recent_logs,
    )


# --------------------------------------------------------------------------
# Activities — Super Admin sees Pakistan-wide data. The 14 entry forms
# themselves are built in a later module; this list/filter view is real and
# reads live from the database like every other list page in this module.
# --------------------------------------------------------------------------

@bp.route("/activities")
def activities_list():
    status_filter = request.args.get("status", "").strip().upper()
    type_filter = request.args.get("type", "").strip().upper()
    when = request.args.get("when", "").strip().lower()
    recent = request.args.get("recent") == "1"
    page = request.args.get("page", 1, type=int)

    # SUPER_ADMIN is Pakistan-wide and unrestricted (same branch
    # `apply_activity_scope` takes for CE_QA) - routed through it anyway so
    # every Activities surface in the app shares one scoping rule.
    query = apply_activity_scope(Activity.query, current_user)
    query = query.options(joinedload(Activity.station), joinedload(Activity.creator))
    query = apply_common_filters(query, request.args)

    if when == "today":
        query = query.filter(Activity.activity_date == date.today())
    elif when == "month":
        query = query.filter(Activity.activity_date >= date.today().replace(day=1))

    if recent:
        query = query.order_by(Activity.created_at.desc())
        title = "Recent Activities"
    else:
        query = query.order_by(Activity.activity_date.desc())
        title = "Open Activities" if status_filter == ActivityStatus.OPEN else "All Activities"

    pagination = query.paginate(page=page, per_page=25, error_out=False)

    deletable_ids = {
        activity.id for activity in pagination.items if can_delete_activity(current_user, activity)
    }
    editable_ids = {
        activity.id for activity in pagination.items if can_edit_activity(current_user, activity)
    }

    return render_template(
        "admin/activities_list.html",
        title=title,
        pagination=pagination,
        activities=pagination.items,
        status_filter=status_filter,
        type_filter=type_filter,
        activity_types=ActivityType.CHOICES,
        deletable_ids=deletable_ids,
        editable_ids=editable_ids,
        recent=recent,
        filter_choices=get_filter_choices(current_user),
        sub_type_label=sub_type_label,
    )


@bp.route("/activities/open")
def open_activities():
    return redirect(url_for("admin.activities_list", status=ActivityStatus.OPEN))


@bp.route("/activities/recent")
def recent_activities():
    return redirect(url_for("admin.activities_list", recent="1"))


@bp.route("/reports")
def reports_placeholder():
    """Pakistan-wide Reports section for Super Admin, sharing the same
    report registry / filters / exports as the main blueprint's Reports
    page (see app.utils.reports)."""
    report_code = request.args.get("report", "").strip()
    page = request.args.get("page", 1, type=int)

    context = {
        "report_types": REPORT_TYPES,
        "filter_choices": get_filter_choices(current_user),
        "selected_report": report_code,
        "report_label": REPORT_LABELS.get(report_code),
        "result_kind": None,
        "export_endpoint": "admin.report_export",
    }

    if report_code:
        kind, data = run_report(report_code, current_user, request.args)
        if kind == "list":
            pagination = data.paginate(page=page, per_page=25, error_out=False)
            context.update(
                result_kind="list",
                pagination=pagination,
                activities=pagination.items,
                sub_type_label=sub_type_label,
            )
        else:
            context.update(result_kind="aggregate", aggregate_rows=data)

    return render_template("admin/reports.html", **context)


@bp.route("/reports/export/<fmt>")
def report_export(fmt):
    report_code = request.args.get("report", "").strip() or "overall"
    kind, data = run_report(report_code, current_user, request.args)
    title = REPORT_LABELS.get(report_code, "Report")

    if kind == "list":
        from app.utils.reports import EXPORT_ROW_LIMIT

        activities = data.limit(EXPORT_ROW_LIMIT).all()
        headers, rows = LIST_HEADERS, list_export_rows(activities)
    else:
        headers, rows = AGGREGATE_HEADERS, aggregate_export_rows(data)

    filename_stub = report_code.lower().replace(" ", "_")

    if fmt == "excel":
        buf = export_excel(headers, rows, title=title)
        return send_file(
            buf,
            as_attachment=True,
            download_name=f"{filename_stub}_report.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    if fmt == "pdf":
        buf = export_pdf(headers, rows, title=title)
        return send_file(
            buf,
            as_attachment=True,
            download_name=f"{filename_stub}_report.pdf",
            mimetype="application/pdf",
        )

    abort(404)


@bp.route("/settings")
def settings_placeholder():
    return render_template("admin/placeholder.html", section="Settings",
                            note="System settings will be added in a later module.")


@bp.route("/administration")
def administration():
    """
    Single "Administration" hub combining what used to be six separate
    sidebar entries (Users, Stations, Shifts, Airlines, Aircraft, Audit) -
    per spec. Each card below still links to its existing, fully-functional
    list route; nothing about those pages changed, only how they're reached
    from the sidebar.
    """
    return render_template("admin/administration.html")


# --------------------------------------------------------------------------
# User management
# --------------------------------------------------------------------------

@bp.route("/users")
def users_list():
    q = request.args.get("q", "").strip()
    role_filter = request.args.get("role", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(User.full_name.ilike(like), User.username.ilike(like), User.employee_no.ilike(like))
        )
    if role_filter in Role.ALL:
        query = query.filter(User.role == role_filter)
    if status_filter == "active":
        query = query.filter(User.is_active.is_(True))
    elif status_filter == "inactive":
        query = query.filter(User.is_active.is_(False))

    users = query.order_by(User.full_name).all()
    stations = Station.query.order_by(Station.code).all()
    return render_template(
        "admin/users_list.html",
        users=users,
        stations=stations,
        roles=Role.ALL,
        q=q,
        role_filter=role_filter,
        status_filter=status_filter,
    )


def _user_form_context(user=None):
    return {
        "user": user,
        "stations": Station.query.filter_by(is_active=True).order_by(Station.code).all(),
        "roles": ASSIGNABLE_ROLES,
    }


def _values_from_user(user):
    return {
        "full_name": user.full_name,
        "username": user.username,
        "employee_no": user.employee_no,
        "designation": user.designation or "",
        "role": user.role,
        "station_id": str(user.station_id) if user.station_id else "",
        "is_active": user.is_active,
    }


def _values_from_form(form, default_active=True):
    return {
        "full_name": form.get("full_name", ""),
        "username": form.get("username", ""),
        "employee_no": form.get("employee_no", ""),
        "designation": form.get("designation", ""),
        "role": form.get("role", ""),
        "station_id": form.get("station_id", ""),
        "is_active": bool(form.get("is_active")) if "is_active" in form or form else default_active,
    }


@bp.route("/users/new", methods=["GET", "POST"])
def user_create():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        employee_no = request.form.get("employee_no", "").strip()
        designation = request.form.get("designation", "").strip()
        role = request.form.get("role", "").strip()
        station_id = request.form.get("station_id") or None
        password = request.form.get("password", "")
        is_active = bool(request.form.get("is_active"))

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not username:
            errors.append("Username is required.")
        if not employee_no:
            errors.append("PNO/CNO is required.")
        if role not in ASSIGNABLE_ROLES:
            errors.append("A valid role is required.")
        if not password or len(password) < 6:
            errors.append("Password is required and must be at least 6 characters.")

        if not errors:
            user = User(
                full_name=full_name,
                username=username,
                employee_no=employee_no,
                designation=designation or None,
                role=role,
                station_id=int(station_id) if station_id else None,
                is_active=is_active,
            )
            user.set_password(password)
            db.session.add(user)
            try:
                db.session.flush()
                log_action("USER_CREATED", "User", user.id,
                           f"Created user {user.username} ({user.role})")
                db.session.commit()
                flash(f"User '{user.username}' created successfully.", "success")
                return redirect(url_for("admin.users_list"))
            except IntegrityError:
                db.session.rollback()
                errors.append("Username or PNO/CNO is already in use.")
        for e in errors:
            flash(e, "danger")
        return render_template("admin/user_form.html", mode="create", **_user_form_context(),
                                values=_values_from_form(request.form, default_active=True))

    return render_template("admin/user_form.html", mode="create", **_user_form_context(),
                            values=_values_from_form({}, default_active=True))


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
def user_edit(user_id):
    user = db.get_or_404(User, user_id)

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        employee_no = request.form.get("employee_no", "").strip()
        designation = request.form.get("designation", "").strip()
        role = request.form.get("role", "").strip()
        station_id = request.form.get("station_id") or None
        is_active = bool(request.form.get("is_active"))

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not username:
            errors.append("Username is required.")
        if not employee_no:
            errors.append("PNO/CNO is required.")
        # A Super Admin account keeps its role fixed here; role changes for
        # non-Super-Admin accounts are limited to the assignable role set.
        if user.role != Role.SUPER_ADMIN and role not in ASSIGNABLE_ROLES:
            errors.append("A valid role is required.")

        if not errors:
            user.full_name = full_name
            user.username = username
            user.employee_no = employee_no
            user.designation = designation or None
            if user.role != Role.SUPER_ADMIN:
                user.role = role
            user.station_id = int(station_id) if station_id else None
            user.is_active = is_active
            try:
                log_action("USER_EDITED", "User", user.id, f"Edited user {user.username}")
                db.session.commit()
                flash(f"User '{user.username}' updated.", "success")
                return redirect(url_for("admin.users_list"))
            except IntegrityError:
                db.session.rollback()
                errors.append("Username or PNO/CNO is already in use.")
        for e in errors:
            flash(e, "danger")
        return render_template("admin/user_form.html", mode="edit", **_user_form_context(user),
                                values=_values_from_form(request.form, default_active=user.is_active))

    return render_template("admin/user_form.html", mode="edit", **_user_form_context(user),
                            values=_values_from_user(user))


@bp.route("/users/<int:user_id>/activate", methods=["POST"])
def user_activate(user_id):
    user = db.get_or_404(User, user_id)
    user.is_active = True
    log_action("USER_ACTIVATED", "User", user.id, f"Activated user {user.username}")
    db.session.commit()
    flash(f"User '{user.username}' activated.", "success")
    return redirect(url_for("admin.users_list"))


@bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
def user_deactivate(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "danger")
        return redirect(url_for("admin.users_list"))
    user.is_active = False
    log_action("USER_DEACTIVATED", "User", user.id, f"Deactivated user {user.username}")
    db.session.commit()
    flash(f"User '{user.username}' deactivated.", "warning")
    return redirect(url_for("admin.users_list"))


@bp.route("/users/<int:user_id>/reset-password", methods=["GET", "POST"])
def user_reset_password(user_id):
    user = db.get_or_404(User, user_id)

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        errors = []
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        if not errors:
            user.set_password(password)
            log_action("PASSWORD_RESET", "User", user.id, f"Password reset for {user.username}")
            db.session.commit()
            flash(f"Password reset for '{user.username}'.", "success")
            return redirect(url_for("admin.users_list"))
        for e in errors:
            flash(e, "danger")

    return render_template("admin/user_reset_password.html", user=user)


# --- Protected Super Admin creation ---------------------------------------
# Deliberately separate from the normal user-creation flow above (which
# cannot assign the SUPER_ADMIN role at all). Requires the acting Super
# Admin to re-enter their own password as an extra confirmation step before
# a new Super Admin account is minted.

@bp.route("/users/create-super-admin", methods=["GET", "POST"])
def create_super_admin():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        employee_no = request.form.get("employee_no", "").strip()
        password = request.form.get("password", "")
        confirming_password = request.form.get("confirming_password", "")

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not username:
            errors.append("Username is required.")
        if not employee_no:
            errors.append("PNO/CNO is required.")
        if not password or len(password) < 6:
            errors.append("Password is required and must be at least 6 characters.")
        if not current_user.check_password(confirming_password):
            errors.append("Your current password is incorrect — Super Admin creation was not confirmed.")

        if not errors:
            user = User(
                full_name=full_name,
                username=username,
                employee_no=employee_no,
                designation="Super Administrator",
                role=Role.SUPER_ADMIN,
                station_id=None,
                is_active=True,
            )
            user.set_password(password)
            db.session.add(user)
            try:
                db.session.flush()
                log_action("USER_CREATED", "User", user.id,
                           f"Created SUPER_ADMIN user {user.username} by {current_user.username}")
                db.session.commit()
                flash(f"Super Admin '{user.username}' created successfully.", "success")
                return redirect(url_for("admin.users_list"))
            except IntegrityError:
                db.session.rollback()
                errors.append("Username or PNO/CNO is already in use.")
        for e in errors:
            flash(e, "danger")
        return render_template("admin/create_super_admin.html", form=request.form)

    return render_template("admin/create_super_admin.html", form={})


# --------------------------------------------------------------------------
# Station management
# --------------------------------------------------------------------------

@bp.route("/stations")
def stations_list():
    stations = Station.query.order_by(Station.code).all()
    return render_template("admin/stations_list.html", stations=stations)


@bp.route("/stations/new", methods=["GET", "POST"])
def station_create():
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        name = request.form.get("name", "").strip()
        is_active = bool(request.form.get("is_active"))

        errors = []
        if not code:
            errors.append("Station code is required.")
        if not name:
            errors.append("Station name is required.")

        if not errors:
            station = Station(code=code, name=name, is_active=is_active)
            db.session.add(station)
            try:
                db.session.flush()
                log_action("STATION_CREATED", "Station", station.id, f"Created station {station.code}")
                db.session.commit()
                flash(f"Station '{station.code}' created.", "success")
                return redirect(url_for("admin.stations_list"))
            except IntegrityError:
                db.session.rollback()
                errors.append("A station with that code already exists.")
        for e in errors:
            flash(e, "danger")
        return render_template("admin/station_form.html", mode="create", form=request.form)

    return render_template("admin/station_form.html", mode="create", form={})


@bp.route("/stations/<int:station_id>/edit", methods=["GET", "POST"])
def station_edit(station_id):
    station = db.get_or_404(Station, station_id)

    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        name = request.form.get("name", "").strip()
        is_active = bool(request.form.get("is_active"))

        errors = []
        if not code:
            errors.append("Station code is required.")
        if not name:
            errors.append("Station name is required.")

        if not errors:
            station.code = code
            station.name = name
            station.is_active = is_active
            try:
                log_action("STATION_EDITED", "Station", station.id, f"Edited station {station.code}")
                db.session.commit()
                flash(f"Station '{station.code}' updated.", "success")
                return redirect(url_for("admin.stations_list"))
            except IntegrityError:
                db.session.rollback()
                errors.append("A station with that code already exists.")
        for e in errors:
            flash(e, "danger")
        return render_template("admin/station_form.html", mode="edit", form=request.form, station=station)

    return render_template("admin/station_form.html", mode="edit", form=station, station=station)


@bp.route("/stations/<int:station_id>/toggle-active", methods=["POST"])
def station_toggle_active(station_id):
    station = db.get_or_404(Station, station_id)
    station.is_active = not station.is_active
    action = "STATION_ACTIVATED" if station.is_active else "STATION_DEACTIVATED"
    log_action(action, "Station", station.id, f"{'Activated' if station.is_active else 'Deactivated'} station {station.code}")
    db.session.commit()
    flash(f"Station '{station.code}' is now {'active' if station.is_active else 'inactive'}.", "success")
    return redirect(url_for("admin.stations_list"))


# --------------------------------------------------------------------------
# Shift management
# --------------------------------------------------------------------------

@bp.route("/shifts")
def shifts_list():
    shifts = Shift.query.order_by(Shift.name).all()
    return render_template("admin/shifts_list.html", shifts=shifts)


@bp.route("/shifts/new", methods=["GET", "POST"])
def shift_create():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        start_time = request.form.get("start_time") or None
        end_time = request.form.get("end_time") or None
        is_active = bool(request.form.get("is_active"))

        errors = []
        if not name:
            errors.append("Shift name is required.")

        if not errors:
            shift = Shift(name=name, start_time=_parse_time(start_time), end_time=_parse_time(end_time), is_active=is_active)
            db.session.add(shift)
            try:
                db.session.flush()
                log_action("SHIFT_CREATED", "Shift", shift.id, f"Created shift {shift.name}")
                db.session.commit()
                flash(f"Shift '{shift.name}' created.", "success")
                return redirect(url_for("admin.shifts_list"))
            except IntegrityError:
                db.session.rollback()
                errors.append("A shift with that name already exists.")
        for e in errors:
            flash(e, "danger")
        return render_template("admin/shift_form.html", mode="create", form=request.form)

    return render_template("admin/shift_form.html", mode="create", form={})


@bp.route("/shifts/<int:shift_id>/edit", methods=["GET", "POST"])
def shift_edit(shift_id):
    shift = db.get_or_404(Shift, shift_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        start_time = request.form.get("start_time") or None
        end_time = request.form.get("end_time") or None
        is_active = bool(request.form.get("is_active"))

        errors = []
        if not name:
            errors.append("Shift name is required.")

        if not errors:
            shift.name = name
            shift.start_time = _parse_time(start_time)
            shift.end_time = _parse_time(end_time)
            shift.is_active = is_active
            try:
                log_action("SHIFT_EDITED", "Shift", shift.id, f"Edited shift {shift.name}")
                db.session.commit()
                flash(f"Shift '{shift.name}' updated.", "success")
                return redirect(url_for("admin.shifts_list"))
            except IntegrityError:
                db.session.rollback()
                errors.append("A shift with that name already exists.")
        for e in errors:
            flash(e, "danger")
        return render_template("admin/shift_form.html", mode="edit", form=request.form, shift=shift)

    shift_values = {
        "name": shift.name,
        "start_time": shift.start_time.strftime("%H:%M") if shift.start_time else "",
        "end_time": shift.end_time.strftime("%H:%M") if shift.end_time else "",
        "is_active": shift.is_active,
    }
    return render_template("admin/shift_form.html", mode="edit", form=shift_values, shift=shift)


@bp.route("/shifts/<int:shift_id>/toggle-active", methods=["POST"])
def shift_toggle_active(shift_id):
    shift = db.get_or_404(Shift, shift_id)
    shift.is_active = not shift.is_active
    action = "SHIFT_ACTIVATED" if shift.is_active else "SHIFT_DEACTIVATED"
    log_action(action, "Shift", shift.id, f"{'Activated' if shift.is_active else 'Deactivated'} shift {shift.name}")
    db.session.commit()
    flash(f"Shift '{shift.name}' is now {'active' if shift.is_active else 'inactive'}.", "success")
    return redirect(url_for("admin.shifts_list"))


# --------------------------------------------------------------------------
# Airline management
# --------------------------------------------------------------------------

@bp.route("/airlines")
def airlines_list():
    airlines = Airline.query.order_by(Airline.code).all()
    return render_template("admin/airlines_list.html", airlines=airlines)


@bp.route("/airlines/new", methods=["GET", "POST"])
def airline_create():
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        name = request.form.get("name", "").strip()
        is_active = bool(request.form.get("is_active"))

        errors = []
        if not code:
            errors.append("Airline code is required.")
        if not name:
            errors.append("Airline name is required.")

        if not errors:
            airline = Airline(code=code, name=name, is_active=is_active)
            db.session.add(airline)
            try:
                db.session.flush()
                log_action("AIRLINE_CREATED", "Airline", airline.id, f"Created airline {airline.code}")
                db.session.commit()
                flash(f"Airline '{airline.code}' created.", "success")
                return redirect(url_for("admin.airlines_list"))
            except IntegrityError:
                db.session.rollback()
                errors.append("An airline with that code already exists.")
        for e in errors:
            flash(e, "danger")
        return render_template("admin/airline_form.html", mode="create", form=request.form)

    return render_template("admin/airline_form.html", mode="create", form={})


@bp.route("/airlines/<int:airline_id>/edit", methods=["GET", "POST"])
def airline_edit(airline_id):
    airline = db.get_or_404(Airline, airline_id)

    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        name = request.form.get("name", "").strip()
        is_active = bool(request.form.get("is_active"))

        errors = []
        if not code:
            errors.append("Airline code is required.")
        if not name:
            errors.append("Airline name is required.")

        if not errors:
            airline.code = code
            airline.name = name
            airline.is_active = is_active
            try:
                log_action("AIRLINE_EDITED", "Airline", airline.id, f"Edited airline {airline.code}")
                db.session.commit()
                flash(f"Airline '{airline.code}' updated.", "success")
                return redirect(url_for("admin.airlines_list"))
            except IntegrityError:
                db.session.rollback()
                errors.append("An airline with that code already exists.")
        for e in errors:
            flash(e, "danger")
        return render_template("admin/airline_form.html", mode="edit", form=request.form, airline=airline)

    return render_template("admin/airline_form.html", mode="edit", form=airline, airline=airline)


@bp.route("/airlines/<int:airline_id>/toggle-active", methods=["POST"])
def airline_toggle_active(airline_id):
    airline = db.get_or_404(Airline, airline_id)
    airline.is_active = not airline.is_active
    action = "AIRLINE_ACTIVATED" if airline.is_active else "AIRLINE_DEACTIVATED"
    log_action(action, "Airline", airline.id, f"{'Activated' if airline.is_active else 'Deactivated'} airline {airline.code}")
    db.session.commit()
    flash(f"Airline '{airline.code}' is now {'active' if airline.is_active else 'inactive'}.", "success")
    return redirect(url_for("admin.airlines_list"))


# --------------------------------------------------------------------------
# Aircraft management
# --------------------------------------------------------------------------

@bp.route("/aircraft")
def aircraft_list():
    aircraft = Aircraft.query.order_by(Aircraft.registration).all()
    return render_template("admin/aircraft_list.html", aircraft=aircraft)


def _aircraft_form_context():
    # Airline choices always loaded live from the database — never hardcoded.
    return {"airlines": Airline.query.filter_by(is_active=True).order_by(Airline.code).all()}


@bp.route("/aircraft/new", methods=["GET", "POST"])
def aircraft_create():
    if request.method == "POST":
        registration = request.form.get("registration", "").strip().upper()
        model = request.form.get("type", "").strip()
        airline_id = request.form.get("airline_id") or None
        is_active = bool(request.form.get("is_active"))

        errors = []
        if not registration:
            errors.append("Registration is required.")

        if not errors:
            aircraft = Aircraft(
                registration=registration,
                type=model or None,
                airline_id=int(airline_id) if airline_id else None,
                is_active=is_active,
            )
            db.session.add(aircraft)
            try:
                db.session.flush()
                log_action("AIRCRAFT_CREATED", "Aircraft", aircraft.id, f"Created aircraft {aircraft.registration}")
                db.session.commit()
                flash(f"Aircraft '{aircraft.registration}' created.", "success")
                return redirect(url_for("admin.aircraft_list"))
            except IntegrityError:
                db.session.rollback()
                errors.append("An aircraft with that registration already exists.")
        for e in errors:
            flash(e, "danger")
        return render_template("admin/aircraft_form.html", mode="create", form=request.form, **_aircraft_form_context())

    return render_template("admin/aircraft_form.html", mode="create", form={}, **_aircraft_form_context())


@bp.route("/aircraft/<int:aircraft_id>/edit", methods=["GET", "POST"])
def aircraft_edit(aircraft_id):
    aircraft = db.get_or_404(Aircraft, aircraft_id)

    if request.method == "POST":
        registration = request.form.get("registration", "").strip().upper()
        model = request.form.get("type", "").strip()
        airline_id = request.form.get("airline_id") or None
        is_active = bool(request.form.get("is_active"))

        errors = []
        if not registration:
            errors.append("Registration is required.")

        if not errors:
            aircraft.registration = registration
            aircraft.type = model or None
            aircraft.airline_id = int(airline_id) if airline_id else None
            aircraft.is_active = is_active
            try:
                log_action("AIRCRAFT_EDITED", "Aircraft", aircraft.id, f"Edited aircraft {aircraft.registration}")
                db.session.commit()
                flash(f"Aircraft '{aircraft.registration}' updated.", "success")
                return redirect(url_for("admin.aircraft_list"))
            except IntegrityError:
                db.session.rollback()
                errors.append("An aircraft with that registration already exists.")
        for e in errors:
            flash(e, "danger")
        return render_template("admin/aircraft_form.html", mode="edit", form=request.form, aircraft=aircraft, **_aircraft_form_context())

    return render_template("admin/aircraft_form.html", mode="edit", form=aircraft, aircraft=aircraft, **_aircraft_form_context())


@bp.route("/aircraft/<int:aircraft_id>/toggle-active", methods=["POST"])
def aircraft_toggle_active(aircraft_id):
    aircraft = db.get_or_404(Aircraft, aircraft_id)
    aircraft.is_active = not aircraft.is_active
    action = "AIRCRAFT_ACTIVATED" if aircraft.is_active else "AIRCRAFT_DEACTIVATED"
    log_action(action, "Aircraft", aircraft.id,
               f"{'Activated' if aircraft.is_active else 'Deactivated'} aircraft {aircraft.registration}")
    db.session.commit()
    flash(f"Aircraft '{aircraft.registration}' is now {'active' if aircraft.is_active else 'inactive'}.", "success")
    return redirect(url_for("admin.aircraft_list"))


# --------------------------------------------------------------------------
# Audit log
# --------------------------------------------------------------------------

@bp.route("/audit-logs")
def audit_logs():
    action_filter = request.args.get("action", "").strip()
    entity_filter = request.args.get("entity_type", "").strip()
    page = request.args.get("page", 1, type=int)

    query = AuditLog.query
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    if entity_filter:
        query = query.filter(AuditLog.entity_type == entity_filter)

    pagination = query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=25, error_out=False)

    actions = [row[0] for row in db.session.query(AuditLog.action).distinct().order_by(AuditLog.action).all()]
    entity_types = [row[0] for row in db.session.query(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type).all()]

    return render_template(
        "admin/audit_logs.html",
        pagination=pagination,
        logs=pagination.items,
        actions=actions,
        entity_types=entity_types,
        action_filter=action_filter,
        entity_filter=entity_filter,
    )
