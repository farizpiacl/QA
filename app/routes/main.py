from datetime import date

from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file, abort, jsonify
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.activity import Activity, ActivityStatus, ActivityType
from app.models.shift import Shift
from app.models.station import Station
from app.models.user import Role
from app.utils.authz import roles_required, station_scope_required, apply_activity_scope
from app.utils.dashboard import get_dashboard_stats
from app.utils.activity_registry import get_spec
from app.utils.analytics import get_analytics_filter_choices, build_analytics_payload
from app.utils.activity_forms import (
    get_selectable_stations,
    default_station_id,
    station_field_is_locked,
    validate_activity_form,
)
from app.utils.audit import log_action
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

bp = Blueprint("main", __name__)


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------

@bp.route("/")
@login_required
def dashboard():
    """
    Role-specific dashboard.

      SUPER_ADMIN         -> redirected to the dedicated admin dashboard,
                              which carries the full admin sidebar.
      CE_QA               -> Pakistan-wide activity statistics.
      DCE_QA              -> own station's statistics (+ anything OPEN).
      AIRCRAFT_ENGINEER    -> own activities (+ anything OPEN).

    All counts come from `get_dashboard_stats`, which reads the database
    through the same role-scoping rule used everywhere else - nothing here
    is a placeholder or hardcoded figure.
    """
    if current_user.is_super_admin:
        return redirect(url_for("admin.dashboard"))

    is_engineer = current_user.role == Role.AIRCRAFT_ENGINEER
    is_dce = current_user.role == Role.DCE_QA

    # Engineers get a personal-only dashboard: KPI totals cover just their
    # own activities (the shared station-wide OPEN pool is intentionally
    # excluded here - it now lives on its own "Open Activities in Station"
    # page). CE_QA/DCE_QA/SUPER_ADMIN are unaffected - `include_open_pool`
    # only ever changes AIRCRAFT_ENGINEER's scope.
    #
    # DCE_QA additionally gets a filter bar (Date, Station, Shift, Engineer,
    # Status) above its 14 Activity Type cards - `request.args` is passed
    # straight through to `get_dashboard_stats`, which layers the same
    # `apply_common_filters` used by the Activities list on top of the
    # normal role scope, so the counts shown always match what clicking
    # through to the list (with the same query string) would show.
    dashboard_filters = request.args if is_dce else None
    stats = get_dashboard_stats(
        current_user, include_open_pool=not is_engineer, filters=dashboard_filters
    )

    recent_activities = None
    if is_engineer:
        recent_activities = (
            apply_activity_scope(Activity.query, current_user, include_open_pool=False)
            .options(joinedload(Activity.station))
            .order_by(Activity.created_at.desc())
            .limit(5)
            .all()
        )

    return render_template(
        "main/dashboard.html",
        user=current_user,
        stats=stats,
        recent_activities=recent_activities,
        filter_choices=get_filter_choices(current_user) if is_dce else None,
        dashboard_query=dashboard_filters.to_dict() if is_dce else {},
    )


# --------------------------------------------------------------------------
# Activities (list / open / recent / add) - shared across CE_QA, DCE_QA and
# AIRCRAFT_ENGINEER. Each role only ever sees what `apply_activity_scope`
# allows, regardless of which nav label or query string got them here.
# --------------------------------------------------------------------------

@bp.route("/activities")
@login_required
@roles_required(Role.SUPER_ADMIN, Role.CE_QA, Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def activities_list():
    status_filter = request.args.get("status", "").strip().upper()
    type_filter = request.args.get("type", "").strip().upper()
    when = request.args.get("when", "").strip().lower()
    recent = request.args.get("recent") == "1"
    page = request.args.get("page", 1, type=int)

    # AIRCRAFT_ENGINEER: the shared OPEN-task pool (other engineers' OPEN
    # activities) is only ever mixed in when this list IS the Open
    # Activities view - never in the default "My Activities" list, so one
    # engineer's own list can't leak another engineer's task.
    query = apply_activity_scope(
        Activity.query, current_user, include_open_pool=(status_filter == ActivityStatus.OPEN)
    )
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
        title = {
            Role.SUPER_ADMIN: "All Activities",
            Role.CE_QA: "All Activities",
            Role.DCE_QA: "Station Activities",
            Role.AIRCRAFT_ENGINEER: "My Activities",
        }[current_user.role]
        if status_filter == ActivityStatus.OPEN:
            title = "Open Activities"

    pagination = query.paginate(page=page, per_page=25, error_out=False)

    deletable_ids = {
        activity.id for activity in pagination.items if can_delete_activity(current_user, activity)
    }
    editable_ids = {
        activity.id for activity in pagination.items if can_edit_activity(current_user, activity)
    }

    return render_template(
        "main/activities_list.html",
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
@login_required
@roles_required(Role.SUPER_ADMIN, Role.CE_QA, Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def open_activities():
    return redirect(url_for("main.activities_list", status=ActivityStatus.OPEN))


@bp.route("/activities/open-in-station")
@login_required
@roles_required(Role.AIRCRAFT_ENGINEER)
def open_activities_station():
    """
    Engineer-only "Open Activities in Station" page.

    This is where the shared OPEN-task pool (any engineer's OPEN activity,
    scoped through `apply_activity_scope(..., include_open_pool=True)`)
    now lives, having been moved off the Dashboard KPI totals. Engineers
    can narrow it down to a single station with the Station filter -
    reusing the same `apply_common_filters` helper (and therefore the
    same `station_id` query param) as Activities/Reports, so behavior
    stays consistent across the app. Nothing here changes what an
    engineer is allowed to see - `apply_activity_scope` still enforces
    that, exactly as it does for the existing `/activities/open` route.
    """
    station_id = request.args.get("station_id", "").strip()
    page = request.args.get("page", 1, type=int)

    query = apply_activity_scope(Activity.query, current_user, include_open_pool=True)
    query = query.filter(Activity.status == ActivityStatus.OPEN)
    query = apply_common_filters(query, request.args)
    query = query.options(joinedload(Activity.station), joinedload(Activity.creator))
    query = query.order_by(Activity.station_id, Activity.activity_date.desc())

    pagination = query.paginate(page=page, per_page=25, error_out=False)

    return render_template(
        "main/open_activities_station.html",
        pagination=pagination,
        activities=pagination.items,
        station_id=station_id,
        filter_choices=get_filter_choices(current_user),
        sub_type_label=sub_type_label,
    )


@bp.route("/activities/recent")
@login_required
@roles_required(Role.SUPER_ADMIN, Role.CE_QA, Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def recent_activities():
    return redirect(url_for("main.activities_list", recent="1"))


@bp.route("/activities/add", methods=["GET", "POST"])
@login_required
@roles_required(Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def add_activity():
    """
    Module 5: reusable Activity Type-driven form engine.

    GET  -> render the form. Activity Type selection dynamically reveals
            the correct next fields client-side; only the fields relevant
            to the chosen type are ever submitted as "shown".
    POST -> re-validate everything server-side (never trust the client),
            create the parent Activity row, and stop there — the
            specialized per-type detail tables are added in Modules 6-8,
            which plug into this same route via
            `app.utils.activity_registry.register_activity_type` with no
            changes needed here.

    Shifts are loaded fresh from the DB (no hardcoded list, matches the
    rest of the app) and only active ones are offered.
    """
    # Module 6: Activity Types 1-5 use their own specialized forms/routes
    # (registered in app.routes.activity_details) instead of this generic
    # engine, since their conditional structure goes beyond a flat field
    # list. The type-selector cards below link straight to those routes;
    # every other type still flows through the generic engine unchanged.
    specialized_create_urls = {
        ActivityType.RAMP_INSPECTION: url_for("act.add_ramp_inspection"),
        ActivityType.SPOT_CHECKS: url_for("act.add_spot_check"),
        ActivityType.AUDIT: url_for("act.add_audit"),
        ActivityType.OCCURRENCE_REPORTING: url_for("act.add_occurrence"),
        ActivityType.TRAINING: url_for("act.add_training"),
        ActivityType.COMPETENCE_ASSESSMENT: url_for("act.add_competence_assessment"),
        ActivityType.CERTIFICATE_AUTHORIZATION: url_for("act.add_certificate_authorization"),
        ActivityType.AML_APPLICATION: url_for("act.add_aml_application"),
        ActivityType.MAINTENANCE_EXPERIENCE: url_for("act.add_maintenance_experience"),
        ActivityType.INVESTIGATION: url_for("act.add_investigation"),
        ActivityType.PCAA: url_for("act.add_pcaa"),
        ActivityType.SURVEILLANCE: url_for("act.add_surveillance"),
        ActivityType.SMS: url_for("act.add_sms"),
        ActivityType.OFFICE_ACTIVITY: url_for("act.add_office_activity"),
    }

    shifts = Shift.query.filter_by(is_active=True).order_by(Shift.name).all()
    stations = get_selectable_stations(current_user)
    station_locked = station_field_is_locked(current_user)

    form_values = {
        "activity_date": date.today().isoformat(),
        "shift_id": "",
        "activity_type": "",
        "station_id": str(default_station_id(current_user) or ""),
        "status": ActivityStatus.OPEN,
        "remarks": "",
    }
    errors = {}

    if request.method == "POST":
        cleaned, errors = validate_activity_form(request.form, current_user)

        # Keep whatever the user typed so a failed submission doesn't force
        # them to re-enter everything.
        for key in form_values:
            form_values[key] = request.form.get(key, form_values[key])

        if not errors:
            activity = Activity(
                activity_date=cleaned["activity_date"],
                shift_id=cleaned["shift_id"],
                activity_type=cleaned["activity_type"],
                station_id=cleaned["station_id"],
                created_by=current_user.id,
                status=cleaned["status"],
                remarks=cleaned["remarks"],
            )
            db.session.add(activity)
            db.session.flush()  # get activity.id before the audit row/commit

            # Specialized detail tables plug in here in Modules 6-8, e.g.:
            #   spec = get_spec(cleaned["activity_type"])
            #   if spec.detail_model:
            #       db.session.add(spec.detail_model(activity_id=activity.id, **cleaned["extra_fields"]))
            # Intentionally not implemented yet (out of scope for Module 5).

            log_action(
                "CREATE",
                "Activity",
                activity.id,
                f"Created {ActivityType.LABELS.get(activity.activity_type, activity.activity_type)} "
                f"activity for station {activity.station_id}",
            )
            db.session.commit()

            flash("Activity saved successfully.", "success")
            return redirect(url_for("main.activities_list"))
        else:
            flash("Please fix the errors below and try again.", "danger")

    # Field specs for every activity type, serialized for the client-side
    # engine (data-driven show/hide + generic field rendering). Empty field
    # lists today; Modules 6-8 populate them via register_activity_type
    # with zero changes to this route or template.
    type_field_specs = {
        code: [
            {
                "name": f.name,
                "label": f.label,
                "field_type": f.field_type,
                "required": f.required,
                "choices": f.choices or [],
                "help_text": f.help_text,
            }
            for f in get_spec(code).fields
        ]
        for code in ActivityType.ALL
    }

    return render_template(
        "main/add_activity.html",
        activity_types=ActivityType.CHOICES,
        shifts=shifts,
        stations=stations,
        station_locked=station_locked,
        statuses=ActivityStatus.ALL,
        form_values=form_values,
        errors=errors,
        type_field_specs=type_field_specs,
        specialized_create_urls=specialized_create_urls,
    )


@bp.route("/profile")
@login_required
def profile():
    """
    My Profile — available to every role. Shows the signed-in user's own
    account details (read-only; edits to name/role/station stay an
    Administration function) alongside the Password Change form, which
    posts to `auth.change_password` so validation stays in one place.
    """
    return render_template("main/profile.html", user=current_user)


@bp.route("/reports")
@login_required
@roles_required(Role.SUPER_ADMIN, Role.CE_QA, Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def reports():
    """
    Reports section: pick one of the 19 report types, narrow it with the
    shared filter set, and view it on-screen (paginated for row-level
    reports) before exporting. Every report reads live from the database
    through the same `apply_activity_scope` rule as everywhere else -
    CE_QA sees Pakistan-wide, DCE_QA their station (+OPEN), engineers their
    own records (+OPEN) - filters only ever narrow that further.
    """
    report_code = request.args.get("report", "").strip()
    page = request.args.get("page", 1, type=int)

    context = {
        "report_types": REPORT_TYPES,
        "filter_choices": get_filter_choices(current_user),
        "selected_report": report_code,
        "report_label": REPORT_LABELS.get(report_code),
        "result_kind": None,
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

    return render_template("main/reports.html", **context)


@bp.route("/reports/export/<fmt>")
@login_required
@roles_required(Role.SUPER_ADMIN, Role.CE_QA, Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def report_export(fmt):
    """Excel / PDF export for the currently selected report + filters."""
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


# --------------------------------------------------------------------------
# Analytics — reporting dashboard for CE_QA / DCE_QA / AIRCRAFT_ENGINEER.
# Every chart reads live from the database through the same
# `apply_activity_scope` + shared filter set used by Activities/Reports -
# CE_QA sees Pakistan-wide, DCE_QA their own station (+OPEN), engineers
# their own activities (+OPEN) - a filter can only ever narrow that
# further, never widen it. This also carries the Activity Type breakdown
# that used to live on the Dashboard as "Analytics Overview" - it's been
# moved here in full rather than duplicated.
# --------------------------------------------------------------------------

@bp.route("/analytics")
@login_required
@roles_required(Role.CE_QA, Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def analytics():
    return render_template(
        "main/analytics.html",
        filter_choices=get_analytics_filter_choices(current_user),
        stats=get_dashboard_stats(current_user),
    )


@bp.route("/analytics/data")
@login_required
@roles_required(Role.CE_QA, Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def analytics_data():
    """JSON payload consumed by the Analytics charts (fetched on load and
    whenever the filter bar changes) so the section updates without a full
    page reload."""
    return jsonify(build_analytics_payload(current_user, request.args))


# --- Role/permission demonstration + test routes ----------------------------
#
# These exist to prove out the authorization layer end-to-end (per the
# module spec's own test list) ahead of the real Activity module. Each one
# is guarded server-side with `roles_required` / `station_scope_required` —
# never by hiding a nav link — so a manually-typed URL from an
# unauthorized role gets a 403, not a rendered page.

@bp.route("/admin")
@login_required
@roles_required(Role.SUPER_ADMIN)
def admin_panel():
    """
    Legacy Module-1/2 placeholder URL. The full Super Admin dashboard now
    lives in the `admin` blueprint (Module 3) — redirect here so any
    existing bookmarks/links keep working.
    """
    return redirect(url_for("admin.dashboard"))


@bp.route("/stations")
@login_required
@roles_required(Role.SUPER_ADMIN, Role.CE_QA)
def stations_list():
    """Pakistan-wide station listing — SUPER_ADMIN and CE_QA only."""
    stations = Station.query.order_by(Station.code).all()
    return render_template("main/stations_list.html", stations=stations)


@bp.route("/stations/<int:station_id>")
@login_required
@station_scope_required(lambda station_id: station_id)
def station_detail(station_id):
    """
    Single-station view. SUPER_ADMIN/CE_QA can view any station; DCE_QA can
    only view their own assigned station — enforced in station_scope_required
    against the station_id actually in the URL, so changing the URL param
    cannot be used to view another station's data.
    """
    from app.extensions import db

    station = db.get_or_404(Station, station_id)
    return render_template("main/station_detail.html", station=station)


@bp.route("/my-area")
@login_required
@roles_required(Role.AIRCRAFT_ENGINEER, Role.SUPER_ADMIN)
def my_area():
    """Legacy Module-1/2 placeholder URL — the engineer landing area is now the dashboard."""
    return render_template("main/my_area.html")
