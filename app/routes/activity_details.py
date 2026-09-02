"""
Module 6: routes for Activity Types 1-5 (Ramp Inspection, Spot Checks,
Audit, Occurrence Reporting, Training).

Each type gets its own create route (GET renders the form, POST validates
and saves) plus a shared View Details route and a shared Edit route that
dispatch on `activity.activity_type`. Permission is enforced server-side
via `app.utils.authz.can_view_activity` / `app.utils.activity_details.can_edit_activity`
- never by hiding a link.

All writes (create, edit, status change) get an audit log entry via
`app.utils.audit.log_action`, committed atomically with the change.
"""

from datetime import date

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.activity import Activity, ActivityStatus, ActivityType
from app.models.airline import Airline
from app.models.aircraft import Aircraft
from app.models.shift import Shift
from app.models.user import Role

from app.models.ramp_inspection import RampInspectionDetail, RampInspectionOption
from app.models.spot_check import SpotCheckDetail, SpotCheckType, SpotCheckArea
from app.models.audit_detail import AuditDetail, AuditType, AuditSection, AuditStage
from app.models.occurrence import OccurrenceDetail, OccurrenceReportType, OccurrenceCategory
from app.models.training_detail import TrainingDetail, TrainingMode, TrainingKind
from app.models.competence_assessment import CompetenceAssessmentDetail, PersonnelType
from app.models.certificate_authorization import (
    CertificateAuthorizationDetail,
    CertificateAuthorizationOption,
)
from app.models.aml_application import (
    AmlApplicationDetail,
    AmlApplicationType,
    AmlScreening,
    AmlOutcome,
)
from app.models.maintenance_experience import (
    MaintenanceExperienceDetail,
    MaintenanceExperienceOption,
    MaintenanceExperienceAction,
)
from app.models.investigation import InvestigationDetail, InvestigationType, MorAircraftType
from app.models.pcaa import PcaaDetail, PcaaOption
from app.models.surveillance import SurveillanceDetail, SurveillanceOption
from app.models.sms import SmsDetail, SmsOption
from app.models.office_activity import OfficeActivityDetail, OfficeActivityOption

from app.utils.authz import roles_required, can_view_activity
from app.utils.activity_forms import (
    get_selectable_stations,
    default_station_id,
    station_field_is_locked,
)
from app.utils.activity_details import (
    validate_ramp_inspection,
    validate_spot_check,
    validate_audit,
    validate_occurrence,
    validate_training,
    validate_competence_assessment,
    validate_certificate_authorization,
    validate_aml_application,
    validate_maintenance_experience,
    validate_investigation,
    validate_pcaa,
    validate_surveillance,
    validate_sms,
    validate_office_activity,
    can_edit_activity,
    can_delete_activity,
)
from app.utils.audit import log_action

bp = Blueprint("act", __name__, url_prefix="/activities")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _common_form_values(activity=None):
    if activity:
        return {
            "activity_date": activity.activity_date.isoformat(),
            "shift_id": str(activity.shift_id),
            "station_id": str(activity.station_id),
            "status": activity.status,
            "remarks": activity.remarks or "",
        }
    return {
        "activity_date": date.today().isoformat(),
        "shift_id": "",
        "station_id": str(default_station_id(current_user) or ""),
        "status": ActivityStatus.OPEN,
        "remarks": "",
    }


def _validate_common(form, user):
    """Validates just the fields common to every activity (date/shift/station/status/remarks)."""
    from app.utils.activity_forms import _parse_date  # reuse the same parser

    errors = {}
    cleaned = {}

    activity_date = _parse_date(form.get("activity_date", ""))
    if activity_date is None:
        errors["activity_date"] = "Date is required and must be a valid date."
    else:
        cleaned["activity_date"] = activity_date

    shift_raw = (form.get("shift_id") or "").strip()
    shift = None
    if not shift_raw:
        errors["shift_id"] = "Shift is required."
    else:
        try:
            shift = db.session.get(Shift, int(shift_raw))
        except (TypeError, ValueError):
            shift = None
        if shift is None or not shift.is_active:
            errors["shift_id"] = "Select a valid, active shift."
        else:
            cleaned["shift_id"] = shift.id

    allowed_stations = {s.id: s for s in get_selectable_stations(user)}
    station_raw = (form.get("station_id") or "").strip()
    if not station_raw:
        errors["station_id"] = "Station is required."
    else:
        try:
            station_id = int(station_raw)
        except ValueError:
            station_id = None
        if station_id is None or station_id not in allowed_stations:
            errors["station_id"] = "Select a station you're authorized to log activities for."
        else:
            cleaned["station_id"] = station_id
    if not allowed_stations and "station_id" not in errors:
        errors["station_id"] = "Your account has no station assigned. Contact an administrator."

    status = (form.get("status") or ActivityStatus.OPEN).strip().upper()
    if status not in ActivityStatus.ALL:
        errors["status"] = "Select a valid status."
    else:
        cleaned["status"] = status

    remarks = (form.get("remarks") or "").strip()
    if len(remarks) > 4000:
        errors["remarks"] = "Remarks must be 4000 characters or fewer."
    else:
        cleaned["remarks"] = remarks or None

    return cleaned, errors


def _lookup_ctx():
    return {
        "shifts": Shift.query.filter_by(is_active=True).order_by(Shift.name).all(),
        "stations": get_selectable_stations(current_user),
        "station_locked": station_field_is_locked(current_user),
        "statuses": ActivityStatus.ALL,
        "airlines": Airline.query.filter_by(is_active=True).order_by(Airline.code).all(),
        "aircraft_list": Aircraft.query.filter_by(is_active=True).order_by(Aircraft.registration).all(),
    }


def _get_activity_or_404(activity_id):
    activity = db.session.get(Activity, activity_id)
    if activity is None:
        abort(404)
    return activity


def _save_activity_and_log(activity_type, common_cleaned, is_new, activity=None, before_status=None):
    """
    Creates or updates the parent Activity row and writes the matching
    audit log entry. Returns the Activity instance (not yet committed -
    caller commits after also saving/updating the detail row, so create is
    atomic with its detail row and edit is atomic with its detail update).
    """
    if is_new:
        activity = Activity(
            activity_date=common_cleaned["activity_date"],
            shift_id=common_cleaned["shift_id"],
            activity_type=activity_type,
            station_id=common_cleaned["station_id"],
            created_by=current_user.id,
            status=common_cleaned["status"],
            remarks=common_cleaned["remarks"],
        )
        db.session.add(activity)
        db.session.flush()
        log_action(
            "CREATE",
            "Activity",
            activity.id,
            f"Created {ActivityType.LABELS.get(activity_type, activity_type)} activity for station {activity.station_id}",
        )
    else:
        activity.activity_date = common_cleaned["activity_date"]
        activity.shift_id = common_cleaned["shift_id"]
        activity.station_id = common_cleaned["station_id"]
        activity.status = common_cleaned["status"]
        activity.remarks = common_cleaned["remarks"]
        activity.updated_by = current_user.id
        log_action(
            "UPDATE",
            "Activity",
            activity.id,
            f"Updated {ActivityType.LABELS.get(activity_type, activity_type)} activity #{activity.id}",
        )
        if before_status and before_status != common_cleaned["status"]:
            log_action(
                "STATUS_CHANGE",
                "Activity",
                activity.id,
                f"Status changed from {before_status} to {common_cleaned['status']}",
            )
    return activity


# ===========================================================================
# 1. RAMP INSPECTION
# ===========================================================================

@bp.route("/add/ramp-inspection", methods=["GET", "POST"])
@login_required
@roles_required(Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def add_ramp_inspection():
    form_values = _common_form_values()
    form_values.update({"option": "", "airline_id": "", "aircraft_id": "", "flight_number": "",
                         "email_done": False, "qa_db_update_done": False})
    errors = {}

    if request.method == "POST":
        common_cleaned, errors = _validate_common(request.form, current_user)
        detail_cleaned, detail_errors = validate_ramp_inspection(request.form)
        errors.update(detail_errors)

        for key in form_values:
            if key in ("email_done", "qa_db_update_done"):
                form_values[key] = (request.form.get(key) or "").strip().upper() == "YES"
            else:
                form_values[key] = request.form.get(key, form_values[key])

        if not errors:
            activity = _save_activity_and_log(ActivityType.RAMP_INSPECTION, common_cleaned, is_new=True)
            detail = RampInspectionDetail(
                activity_id=activity.id,
                option=detail_cleaned["option"],
                airline_id=detail_cleaned["airline_id"],
                aircraft_id=detail_cleaned["aircraft_id"],
                flight_number=detail_cleaned["flight_number"],
                email_done=detail_cleaned["email_done"],
                qa_db_update_done=detail_cleaned["qa_db_update_done"],
            )
            db.session.add(detail)
            db.session.commit()
            flash("Ramp Inspection saved successfully.", "success")
            return redirect(url_for("act.view_activity", activity_id=activity.id))
        flash("Please fix the errors below and try again.", "danger")

    ctx = _lookup_ctx()
    return render_template(
        "main/activity_types/ramp_inspection_form.html",
        activity=None,
        form_values=form_values,
        errors=errors,
        option_choices=RampInspectionOption.CHOICES,
        **ctx,
    )


# ===========================================================================
# 2. SPOT CHECKS
# ===========================================================================

@bp.route("/add/spot-checks", methods=["GET", "POST"])
@login_required
@roles_required(Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def add_spot_check():
    form_values = _common_form_values()
    form_values.update({"spot_check_type": "", "area": "", "airline_id": "", "aircraft_id": "",
                         "flight_number": "", "email_done": False, "qa_db_update_done": False})
    errors = {}

    if request.method == "POST":
        common_cleaned, errors = _validate_common(request.form, current_user)
        detail_cleaned, detail_errors = validate_spot_check(request.form)
        errors.update(detail_errors)

        for key in form_values:
            if key in ("email_done", "qa_db_update_done"):
                form_values[key] = (request.form.get(key) or "").strip().upper() == "YES"
            else:
                form_values[key] = request.form.get(key, form_values[key])

        if not errors:
            activity = _save_activity_and_log(ActivityType.SPOT_CHECKS, common_cleaned, is_new=True)
            detail = SpotCheckDetail(
                activity_id=activity.id,
                spot_check_type=detail_cleaned["spot_check_type"],
                area=detail_cleaned.get("area"),
                airline_id=detail_cleaned.get("airline_id"),
                aircraft_id=detail_cleaned.get("aircraft_id"),
                flight_number=detail_cleaned.get("flight_number"),
                email_done=detail_cleaned["email_done"],
                qa_db_update_done=detail_cleaned["qa_db_update_done"],
            )
            db.session.add(detail)
            db.session.commit()
            flash("Spot Check saved successfully.", "success")
            return redirect(url_for("act.view_activity", activity_id=activity.id))
        flash("Please fix the errors below and try again.", "danger")

    ctx = _lookup_ctx()
    return render_template(
        "main/activity_types/spot_checks_form.html",
        activity=None,
        form_values=form_values,
        errors=errors,
        type_choices=SpotCheckType.CHOICES,
        area_choices=SpotCheckArea.CHOICES,
        aircraft_areas=SpotCheckArea.REQUIRES_AIRCRAFT_FIELDS,
        **ctx,
    )


# ===========================================================================
# 3. AUDIT
# ===========================================================================

@bp.route("/add/audit", methods=["GET", "POST"])
@login_required
@roles_required(Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def add_audit():
    form_values = _common_form_values()
    form_values.update({
        "audit_type": "", "section": "", "authority": "", "operator": "",
        "audit_stage": AuditStage.AUDIT_PREPARATION,
        "stage_status": ActivityStatus.OPEN, "stage_remarks": "",
    })
    errors = {}

    if request.method == "POST":
        common_cleaned, errors = _validate_common(request.form, current_user)
        detail_cleaned, detail_errors = validate_audit(request.form)
        errors.update(detail_errors)

        for key in form_values:
            form_values[key] = request.form.get(key, form_values[key])

        if not errors:
            activity = _save_activity_and_log(ActivityType.AUDIT, common_cleaned, is_new=True)
            detail = AuditDetail(
                activity_id=activity.id,
                audit_type=detail_cleaned["audit_type"],
                section=detail_cleaned["section"],
                authority=detail_cleaned.get("authority"),
                operator=detail_cleaned.get("operator"),
                audit_stage=detail_cleaned["audit_stage"],
                stage_status=detail_cleaned["stage_status"],
                stage_remarks=detail_cleaned["stage_remarks"],
            )
            db.session.add(detail)
            db.session.commit()
            flash("Audit saved successfully.", "success")
            return redirect(url_for("act.view_activity", activity_id=activity.id))
        flash("Please fix the errors below and try again.", "danger")

    ctx = _lookup_ctx()
    return render_template(
        "main/activity_types/audit_form.html",
        activity=None,
        form_values=form_values,
        errors=errors,
        audit_type_choices=AuditType.CHOICES,
        section_choices=AuditSection.CHOICES,
        audit_stage_choices=AuditStage.CHOICES,
        **ctx,
    )


# ===========================================================================
# 4. OCCURRENCE REPORTING
# ===========================================================================

@bp.route("/add/occurrence-reporting", methods=["GET", "POST"])
@login_required
@roles_required(Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def add_occurrence():
    form_values = _common_form_values()
    form_values.update({"report_type": "", "category": ""})
    errors = {}

    if request.method == "POST":
        common_cleaned, errors = _validate_common(request.form, current_user)
        detail_cleaned, detail_errors = validate_occurrence(request.form)
        errors.update(detail_errors)

        for key in form_values:
            form_values[key] = request.form.get(key, form_values[key])

        if not errors:
            activity = _save_activity_and_log(ActivityType.OCCURRENCE_REPORTING, common_cleaned, is_new=True)
            detail = OccurrenceDetail(
                activity_id=activity.id,
                report_type=detail_cleaned["report_type"],
                category=detail_cleaned["category"],
            )
            db.session.add(detail)
            db.session.commit()
            flash("Occurrence report saved successfully.", "success")
            return redirect(url_for("act.view_activity", activity_id=activity.id))
        flash("Please fix the errors below and try again.", "danger")

    ctx = _lookup_ctx()
    return render_template(
        "main/activity_types/occurrence_form.html",
        activity=None,
        form_values=form_values,
        errors=errors,
        report_type_choices=OccurrenceReportType.CHOICES,
        category_choices=OccurrenceCategory.CHOICES,
        **ctx,
    )


# ===========================================================================
# 5. TRAINING
# ===========================================================================

@bp.route("/add/training", methods=["GET", "POST"])
@login_required
@roles_required(Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def add_training():
    form_values = _common_form_values()
    form_values.update({"mode": "", "kind": ""})
    errors = {}

    if request.method == "POST":
        common_cleaned, errors = _validate_common(request.form, current_user)
        detail_cleaned, detail_errors = validate_training(request.form)
        errors.update(detail_errors)

        for key in form_values:
            form_values[key] = request.form.get(key, form_values[key])

        if not errors:
            activity = _save_activity_and_log(ActivityType.TRAINING, common_cleaned, is_new=True)
            detail = TrainingDetail(
                activity_id=activity.id,
                mode=detail_cleaned["mode"],
                kind=detail_cleaned["kind"],
            )
            db.session.add(detail)
            db.session.commit()
            flash("Training record saved successfully.", "success")
            return redirect(url_for("act.view_activity", activity_id=activity.id))
        flash("Please fix the errors below and try again.", "danger")

    ctx = _lookup_ctx()
    return render_template(
        "main/activity_types/training_form.html",
        activity=None,
        form_values=form_values,
        errors=errors,
        mode_choices=TrainingMode.CHOICES,
        kind_choices=TrainingKind.CHOICES,
        conduct_allowed=TrainingKind.ALLOWED_FOR_CONDUCT,
        **ctx,
    )


# ===========================================================================
# 6. COMPETENCE ASSESSMENT OF PERSONNEL
# ===========================================================================

@bp.route("/add/competence-assessment", methods=["GET", "POST"])
@login_required
@roles_required(Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def add_competence_assessment():
    form_values = _common_form_values()
    form_values.update({"personnel_type": "", "name": "", "pno_cno": ""})
    errors = {}

    if request.method == "POST":
        common_cleaned, errors = _validate_common(request.form, current_user)
        detail_cleaned, detail_errors = validate_competence_assessment(request.form)
        errors.update(detail_errors)

        for key in form_values:
            form_values[key] = request.form.get(key, form_values[key])

        if not errors:
            activity = _save_activity_and_log(ActivityType.COMPETENCE_ASSESSMENT, common_cleaned, is_new=True)
            detail = CompetenceAssessmentDetail(
                activity_id=activity.id,
                personnel_type=detail_cleaned["personnel_type"],
                name=detail_cleaned["name"],
                pno_cno=detail_cleaned["pno_cno"],
            )
            db.session.add(detail)
            db.session.commit()
            flash("Competence Assessment saved successfully.", "success")
            return redirect(url_for("act.view_activity", activity_id=activity.id))
        flash("Please fix the errors below and try again.", "danger")

    ctx = _lookup_ctx()
    return render_template(
        "main/activity_types/competence_assessment_form.html",
        activity=None,
        form_values=form_values,
        errors=errors,
        personnel_type_choices=PersonnelType.CHOICES,
        **ctx,
    )


# ===========================================================================
# 7. CERTIFICATE AUTHORIZATION
# ===========================================================================

@bp.route("/add/certificate-authorization", methods=["GET", "POST"])
@login_required
@roles_required(Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def add_certificate_authorization():
    form_values = _common_form_values()
    form_values.update({"option": ""})
    errors = {}

    if request.method == "POST":
        common_cleaned, errors = _validate_common(request.form, current_user)
        detail_cleaned, detail_errors = validate_certificate_authorization(request.form)
        errors.update(detail_errors)

        for key in form_values:
            form_values[key] = request.form.get(key, form_values[key])

        if not errors:
            activity = _save_activity_and_log(ActivityType.CERTIFICATE_AUTHORIZATION, common_cleaned, is_new=True)
            detail = CertificateAuthorizationDetail(
                activity_id=activity.id,
                option=detail_cleaned["option"],
            )
            db.session.add(detail)
            db.session.commit()
            flash("Certification Authorization saved successfully.", "success")
            return redirect(url_for("act.view_activity", activity_id=activity.id))
        flash("Please fix the errors below and try again.", "danger")

    ctx = _lookup_ctx()
    return render_template(
        "main/activity_types/certificate_authorization_form.html",
        activity=None,
        form_values=form_values,
        errors=errors,
        option_choices=CertificateAuthorizationOption.CHOICES,
        **ctx,
    )


# ===========================================================================
# 8. AML APPLICATION
# ===========================================================================

@bp.route("/add/aml-application", methods=["GET", "POST"])
@login_required
@roles_required(Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def add_aml_application():
    form_values = _common_form_values()
    form_values.update({"aml_type": "", "screening": "", "outcome": ""})
    errors = {}

    if request.method == "POST":
        common_cleaned, errors = _validate_common(request.form, current_user)
        detail_cleaned, detail_errors = validate_aml_application(request.form)
        errors.update(detail_errors)

        for key in form_values:
            form_values[key] = request.form.get(key, form_values[key])

        if not errors:
            activity = _save_activity_and_log(ActivityType.AML_APPLICATION, common_cleaned, is_new=True)
            detail = AmlApplicationDetail(
                activity_id=activity.id,
                aml_type=detail_cleaned["aml_type"],
                screening=detail_cleaned["screening"],
                outcome=detail_cleaned["outcome"],
            )
            db.session.add(detail)
            db.session.commit()
            flash("AML Application saved successfully.", "success")
            return redirect(url_for("act.view_activity", activity_id=activity.id))
        flash("Please fix the errors below and try again.", "danger")

    ctx = _lookup_ctx()
    return render_template(
        "main/activity_types/aml_application_form.html",
        activity=None,
        form_values=form_values,
        errors=errors,
        type_choices=AmlApplicationType.CHOICES,
        screening_choices=AmlScreening.CHOICES,
        outcome_choices=AmlOutcome.CHOICES,
        **ctx,
    )


# ===========================================================================
# 9. MAINTENANCE EXPERIENCE
# ===========================================================================

@bp.route("/add/maintenance-experience", methods=["GET", "POST"])
@login_required
@roles_required(Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def add_maintenance_experience():
    form_values = _common_form_values()
    form_values.update({"option": "", "name": "", "pno_cno": "", "action": ""})
    errors = {}

    if request.method == "POST":
        common_cleaned, errors = _validate_common(request.form, current_user)
        detail_cleaned, detail_errors = validate_maintenance_experience(request.form)
        errors.update(detail_errors)

        for key in form_values:
            form_values[key] = request.form.get(key, form_values[key])

        if not errors:
            activity = _save_activity_and_log(ActivityType.MAINTENANCE_EXPERIENCE, common_cleaned, is_new=True)
            detail = MaintenanceExperienceDetail(
                activity_id=activity.id,
                option=detail_cleaned["option"],
                name=detail_cleaned["name"],
                pno_cno=detail_cleaned["pno_cno"],
                action=detail_cleaned["action"],
            )
            db.session.add(detail)
            db.session.commit()
            flash("Maintenance Experience saved successfully.", "success")
            return redirect(url_for("act.view_activity", activity_id=activity.id))
        flash("Please fix the errors below and try again.", "danger")

    ctx = _lookup_ctx()
    return render_template(
        "main/activity_types/maintenance_experience_form.html",
        activity=None,
        form_values=form_values,
        errors=errors,
        option_choices=MaintenanceExperienceOption.CHOICES,
        action_choices=MaintenanceExperienceAction.CHOICES,
        **ctx,
    )


# ===========================================================================
# 10. INVESTIGATION
# ===========================================================================

@bp.route("/add/investigation", methods=["GET", "POST"])
@login_required
@roles_required(Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def add_investigation():
    form_values = _common_form_values()
    form_values.update({"investigation_type": "", "mor_aircraft_type": ""})
    errors = {}

    if request.method == "POST":
        common_cleaned, errors = _validate_common(request.form, current_user)
        detail_cleaned, detail_errors = validate_investigation(request.form)
        errors.update(detail_errors)

        for key in form_values:
            form_values[key] = request.form.get(key, form_values[key])

        if not errors:
            activity = _save_activity_and_log(ActivityType.INVESTIGATION, common_cleaned, is_new=True)
            detail = InvestigationDetail(
                activity_id=activity.id,
                investigation_type=detail_cleaned["investigation_type"],
                mor_aircraft_type=detail_cleaned.get("mor_aircraft_type"),
            )
            db.session.add(detail)
            db.session.commit()
            flash("Investigation saved successfully.", "success")
            return redirect(url_for("act.view_activity", activity_id=activity.id))
        flash("Please fix the errors below and try again.", "danger")

    ctx = _lookup_ctx()
    return render_template(
        "main/activity_types/investigation_form.html",
        activity=None,
        form_values=form_values,
        errors=errors,
        type_choices=InvestigationType.CHOICES,
        mor_aircraft_choices=MorAircraftType.CHOICES,
        **ctx,
    )


# ===========================================================================
# 11. PCAA
# ===========================================================================

@bp.route("/add/pcaa", methods=["GET", "POST"])
@login_required
@roles_required(Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def add_pcaa():
    form_values = _common_form_values()
    form_values.update({"option": ""})
    errors = {}

    if request.method == "POST":
        common_cleaned, errors = _validate_common(request.form, current_user)
        detail_cleaned, detail_errors = validate_pcaa(request.form)
        errors.update(detail_errors)

        for key in form_values:
            form_values[key] = request.form.get(key, form_values[key])

        if not errors:
            activity = _save_activity_and_log(ActivityType.PCAA, common_cleaned, is_new=True)
            detail = PcaaDetail(
                activity_id=activity.id,
                option=detail_cleaned["option"],
            )
            db.session.add(detail)
            db.session.commit()
            flash("PCAA activity saved successfully.", "success")
            return redirect(url_for("act.view_activity", activity_id=activity.id))
        flash("Please fix the errors below and try again.", "danger")

    ctx = _lookup_ctx()
    return render_template(
        "main/activity_types/pcaa_form.html",
        activity=None,
        form_values=form_values,
        errors=errors,
        option_choices=PcaaOption.CHOICES,
        **ctx,
    )


# ===========================================================================
# 12. SURVEILLANCE
# ===========================================================================

@bp.route("/add/surveillance", methods=["GET", "POST"])
@login_required
@roles_required(Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def add_surveillance():
    form_values = _common_form_values()
    form_values.update({"option": ""})
    errors = {}

    if request.method == "POST":
        common_cleaned, errors = _validate_common(request.form, current_user)
        detail_cleaned, detail_errors = validate_surveillance(request.form)
        errors.update(detail_errors)

        for key in form_values:
            form_values[key] = request.form.get(key, form_values[key])

        if not errors:
            activity = _save_activity_and_log(ActivityType.SURVEILLANCE, common_cleaned, is_new=True)
            detail = SurveillanceDetail(
                activity_id=activity.id,
                option=detail_cleaned["option"],
            )
            db.session.add(detail)
            db.session.commit()
            flash("Surveillance activity saved successfully.", "success")
            return redirect(url_for("act.view_activity", activity_id=activity.id))
        flash("Please fix the errors below and try again.", "danger")

    ctx = _lookup_ctx()
    return render_template(
        "main/activity_types/surveillance_form.html",
        activity=None,
        form_values=form_values,
        errors=errors,
        option_choices=SurveillanceOption.CHOICES,
        **ctx,
    )


# ===========================================================================
# 13. SMS
# ===========================================================================

@bp.route("/add/sms", methods=["GET", "POST"])
@login_required
@roles_required(Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def add_sms():
    form_values = _common_form_values()
    form_values.update({"option": ""})
    errors = {}

    if request.method == "POST":
        common_cleaned, errors = _validate_common(request.form, current_user)
        detail_cleaned, detail_errors = validate_sms(request.form)
        errors.update(detail_errors)

        for key in form_values:
            form_values[key] = request.form.get(key, form_values[key])

        if not errors:
            activity = _save_activity_and_log(ActivityType.SMS, common_cleaned, is_new=True)
            detail = SmsDetail(
                activity_id=activity.id,
                option=detail_cleaned["option"],
            )
            db.session.add(detail)
            db.session.commit()
            flash("SMS activity saved successfully.", "success")
            return redirect(url_for("act.view_activity", activity_id=activity.id))
        flash("Please fix the errors below and try again.", "danger")

    ctx = _lookup_ctx()
    return render_template(
        "main/activity_types/sms_form.html",
        activity=None,
        form_values=form_values,
        errors=errors,
        option_choices=SmsOption.CHOICES,
        **ctx,
    )


# ===========================================================================
# 14. OFFICE ACTIVITY
# ===========================================================================

@bp.route("/add/office-activity", methods=["GET", "POST"])
@login_required
@roles_required(Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def add_office_activity():
    form_values = _common_form_values()
    form_values.update({"option": ""})
    errors = {}

    if request.method == "POST":
        common_cleaned, errors = _validate_common(request.form, current_user)
        detail_cleaned, detail_errors = validate_office_activity(request.form)
        errors.update(detail_errors)

        for key in form_values:
            form_values[key] = request.form.get(key, form_values[key])

        if not errors:
            activity = _save_activity_and_log(ActivityType.OFFICE_ACTIVITY, common_cleaned, is_new=True)
            detail = OfficeActivityDetail(
                activity_id=activity.id,
                option=detail_cleaned["option"],
            )
            db.session.add(detail)
            db.session.commit()
            flash("Office Activity saved successfully.", "success")
            return redirect(url_for("act.view_activity", activity_id=activity.id))
        flash("Please fix the errors below and try again.", "danger")

    ctx = _lookup_ctx()
    return render_template(
        "main/activity_types/office_activity_form.html",
        activity=None,
        form_values=form_values,
        errors=errors,
        option_choices=OfficeActivityOption.CHOICES,
        **ctx,
    )


# ===========================================================================
# View Details (shared, dispatches on activity_type)
# ===========================================================================

_DETAIL_ATTR = {
    ActivityType.RAMP_INSPECTION: "ramp_inspection_detail",
    ActivityType.SPOT_CHECKS: "spot_check_detail",
    ActivityType.AUDIT: "audit_detail",
    ActivityType.OCCURRENCE_REPORTING: "occurrence_detail",
    ActivityType.TRAINING: "training_detail",
    ActivityType.COMPETENCE_ASSESSMENT: "competence_assessment_detail",
    ActivityType.CERTIFICATE_AUTHORIZATION: "certificate_authorization_detail",
    ActivityType.AML_APPLICATION: "aml_application_detail",
    ActivityType.MAINTENANCE_EXPERIENCE: "maintenance_experience_detail",
    ActivityType.INVESTIGATION: "investigation_detail",
    ActivityType.PCAA: "pcaa_detail",
    ActivityType.SURVEILLANCE: "surveillance_detail",
    ActivityType.SMS: "sms_detail",
    ActivityType.OFFICE_ACTIVITY: "office_activity_detail",
}


def _detail_labels(activity_type, detail):
    if activity_type == ActivityType.RAMP_INSPECTION:
        return {"option": RampInspectionOption.LABELS.get(detail.option, detail.option)}
    if activity_type == ActivityType.SPOT_CHECKS:
        return {
            "spot_check_type": SpotCheckType.LABELS.get(detail.spot_check_type, detail.spot_check_type),
            "area": SpotCheckArea.LABELS.get(detail.area, detail.area) if detail.area else None,
        }
    if activity_type == ActivityType.AUDIT:
        return {
            "audit_type": AuditType.LABELS.get(detail.audit_type, detail.audit_type),
            "section": AuditSection.LABELS.get(detail.section, detail.section),
            "audit_stage": AuditStage.LABELS.get(detail.audit_stage, detail.audit_stage),
        }
    if activity_type == ActivityType.OCCURRENCE_REPORTING:
        return {
            "report_type": OccurrenceReportType.LABELS.get(detail.report_type, detail.report_type),
            "category": OccurrenceCategory.LABELS.get(detail.category, detail.category),
        }
    if activity_type == ActivityType.TRAINING:
        return {
            "mode": TrainingMode.LABELS.get(detail.mode, detail.mode),
            "kind": TrainingKind.LABELS.get(detail.kind, detail.kind),
        }
    if activity_type == ActivityType.COMPETENCE_ASSESSMENT:
        return {"personnel_type": PersonnelType.LABELS.get(detail.personnel_type, detail.personnel_type)}
    if activity_type == ActivityType.CERTIFICATE_AUTHORIZATION:
        return {
            "option": CertificateAuthorizationOption.LABELS.get(detail.option, detail.option)
        }
    if activity_type == ActivityType.AML_APPLICATION:
        return {
            "aml_type": AmlApplicationType.LABELS.get(detail.aml_type, detail.aml_type),
            "screening": AmlScreening.LABELS.get(detail.screening, detail.screening),
            "outcome": AmlOutcome.LABELS.get(detail.outcome, detail.outcome),
        }
    if activity_type == ActivityType.MAINTENANCE_EXPERIENCE:
        return {
            "option": MaintenanceExperienceOption.LABELS.get(detail.option, detail.option),
            "action": MaintenanceExperienceAction.LABELS.get(detail.action, detail.action),
        }
    if activity_type == ActivityType.INVESTIGATION:
        return {
            "investigation_type": InvestigationType.LABELS.get(
                detail.investigation_type, detail.investigation_type
            ),
            "mor_aircraft_type": (
                MorAircraftType.LABELS.get(detail.mor_aircraft_type, detail.mor_aircraft_type)
                if detail.mor_aircraft_type
                else None
            ),
        }
    if activity_type == ActivityType.PCAA:
        return {"option": PcaaOption.LABELS.get(detail.option, detail.option)}
    if activity_type == ActivityType.SURVEILLANCE:
        return {"option": SurveillanceOption.LABELS.get(detail.option, detail.option)}
    if activity_type == ActivityType.SMS:
        return {"option": SmsOption.LABELS.get(detail.option, detail.option)}
    if activity_type == ActivityType.OFFICE_ACTIVITY:
        return {"option": OfficeActivityOption.LABELS.get(detail.option, detail.option)}
    return {}


@bp.route("/<int:activity_id>")
@login_required
@roles_required(Role.CE_QA, Role.DCE_QA, Role.AIRCRAFT_ENGINEER, Role.SUPER_ADMIN)
def view_activity(activity_id):
    activity = _get_activity_or_404(activity_id)
    if not can_view_activity(current_user, activity):
        abort(403)

    detail_attr = _DETAIL_ATTR.get(activity.activity_type)
    if detail_attr is None:
        # Not one of Module 6's 5 types (e.g. still-generic types from
        # Module 5) - no specialized detail view exists yet.
        abort(404)

    detail = getattr(activity, detail_attr)
    if detail is None:
        abort(404)

    return render_template(
        "main/activity_types/activity_detail_view.html",
        activity=activity,
        detail=detail,
        detail_labels=_detail_labels(activity.activity_type, detail),
        type_label=ActivityType.LABELS.get(activity.activity_type, activity.activity_type),
        can_edit=can_edit_activity(current_user, activity),
        can_delete=can_delete_activity(current_user, activity),
    )


# ===========================================================================
# Edit (shared, dispatches on activity_type)
# ===========================================================================

_EDIT_TEMPLATE = {
    ActivityType.RAMP_INSPECTION: "main/activity_types/ramp_inspection_form.html",
    ActivityType.SPOT_CHECKS: "main/activity_types/spot_checks_form.html",
    ActivityType.AUDIT: "main/activity_types/audit_form.html",
    ActivityType.OCCURRENCE_REPORTING: "main/activity_types/occurrence_form.html",
    ActivityType.TRAINING: "main/activity_types/training_form.html",
    ActivityType.COMPETENCE_ASSESSMENT: "main/activity_types/competence_assessment_form.html",
    ActivityType.CERTIFICATE_AUTHORIZATION: "main/activity_types/certificate_authorization_form.html",
    ActivityType.AML_APPLICATION: "main/activity_types/aml_application_form.html",
    ActivityType.MAINTENANCE_EXPERIENCE: "main/activity_types/maintenance_experience_form.html",
    ActivityType.INVESTIGATION: "main/activity_types/investigation_form.html",
    ActivityType.PCAA: "main/activity_types/pcaa_form.html",
    ActivityType.SURVEILLANCE: "main/activity_types/surveillance_form.html",
    ActivityType.SMS: "main/activity_types/sms_form.html",
    ActivityType.OFFICE_ACTIVITY: "main/activity_types/office_activity_form.html",
}


@bp.route("/<int:activity_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required(Role.CE_QA, Role.DCE_QA, Role.AIRCRAFT_ENGINEER, Role.SUPER_ADMIN)
def edit_activity(activity_id):
    activity = _get_activity_or_404(activity_id)
    activity_type = activity.activity_type

    if activity_type not in _EDIT_TEMPLATE:
        abort(404)
    if not can_edit_activity(current_user, activity):
        abort(403)

    detail = getattr(activity, _DETAIL_ATTR[activity_type])
    if detail is None:
        abort(404)

    before_status = activity.status

    if activity_type == ActivityType.RAMP_INSPECTION:
        form_values = _common_form_values(activity)
        form_values.update({
            "option": detail.option, "airline_id": str(detail.airline_id),
            "aircraft_id": str(detail.aircraft_id), "flight_number": detail.flight_number,
            "email_done": detail.email_done, "qa_db_update_done": detail.qa_db_update_done,
        })
    elif activity_type == ActivityType.SPOT_CHECKS:
        form_values = _common_form_values(activity)
        form_values.update({
            "spot_check_type": detail.spot_check_type, "area": detail.area or "",
            "airline_id": str(detail.airline_id or ""), "aircraft_id": str(detail.aircraft_id or ""),
            "flight_number": detail.flight_number or "",
            "email_done": detail.email_done, "qa_db_update_done": detail.qa_db_update_done,
        })
    elif activity_type == ActivityType.AUDIT:
        form_values = _common_form_values(activity)
        form_values.update({
            "audit_type": detail.audit_type, "section": detail.section,
            "authority": detail.authority or "", "operator": detail.operator or "",
            "audit_stage": detail.audit_stage,
            "stage_status": detail.stage_status, "stage_remarks": detail.stage_remarks or "",
        })
    elif activity_type == ActivityType.OCCURRENCE_REPORTING:
        form_values = _common_form_values(activity)
        form_values.update({"report_type": detail.report_type, "category": detail.category})
    elif activity_type == ActivityType.TRAINING:
        form_values = _common_form_values(activity)
        form_values.update({"mode": detail.mode, "kind": detail.kind})
    elif activity_type == ActivityType.COMPETENCE_ASSESSMENT:
        form_values = _common_form_values(activity)
        form_values.update({
            "personnel_type": detail.personnel_type, "name": detail.name, "pno_cno": detail.pno_cno,
        })
    elif activity_type == ActivityType.CERTIFICATE_AUTHORIZATION:
        form_values = _common_form_values(activity)
        form_values.update({"option": detail.option})
    elif activity_type == ActivityType.AML_APPLICATION:
        form_values = _common_form_values(activity)
        form_values.update({
            "aml_type": detail.aml_type, "screening": detail.screening, "outcome": detail.outcome,
        })
    elif activity_type == ActivityType.MAINTENANCE_EXPERIENCE:
        form_values = _common_form_values(activity)
        form_values.update({
            "option": detail.option, "name": detail.name, "pno_cno": detail.pno_cno,
            "action": detail.action,
        })
    elif activity_type == ActivityType.INVESTIGATION:
        form_values = _common_form_values(activity)
        form_values.update({
            "investigation_type": detail.investigation_type,
            "mor_aircraft_type": detail.mor_aircraft_type or "",
        })
    elif activity_type == ActivityType.PCAA:
        form_values = _common_form_values(activity)
        form_values.update({"option": detail.option})
    elif activity_type == ActivityType.SURVEILLANCE:
        form_values = _common_form_values(activity)
        form_values.update({"option": detail.option})
    elif activity_type == ActivityType.SMS:
        form_values = _common_form_values(activity)
        form_values.update({"option": detail.option})
    else:  # OFFICE_ACTIVITY
        form_values = _common_form_values(activity)
        form_values.update({"option": detail.option})

    errors = {}

    if request.method == "POST":
        common_cleaned, errors = _validate_common(request.form, current_user)

        if activity_type == ActivityType.RAMP_INSPECTION:
            detail_cleaned, detail_errors = validate_ramp_inspection(request.form)
        elif activity_type == ActivityType.SPOT_CHECKS:
            detail_cleaned, detail_errors = validate_spot_check(request.form)
        elif activity_type == ActivityType.AUDIT:
            detail_cleaned, detail_errors = validate_audit(request.form)
        elif activity_type == ActivityType.OCCURRENCE_REPORTING:
            detail_cleaned, detail_errors = validate_occurrence(request.form)
        elif activity_type == ActivityType.TRAINING:
            detail_cleaned, detail_errors = validate_training(request.form)
        elif activity_type == ActivityType.COMPETENCE_ASSESSMENT:
            detail_cleaned, detail_errors = validate_competence_assessment(request.form)
        elif activity_type == ActivityType.CERTIFICATE_AUTHORIZATION:
            detail_cleaned, detail_errors = validate_certificate_authorization(request.form)
        elif activity_type == ActivityType.AML_APPLICATION:
            detail_cleaned, detail_errors = validate_aml_application(request.form)
        elif activity_type == ActivityType.MAINTENANCE_EXPERIENCE:
            detail_cleaned, detail_errors = validate_maintenance_experience(request.form)
        elif activity_type == ActivityType.INVESTIGATION:
            detail_cleaned, detail_errors = validate_investigation(request.form)
        elif activity_type == ActivityType.PCAA:
            detail_cleaned, detail_errors = validate_pcaa(request.form)
        elif activity_type == ActivityType.SURVEILLANCE:
            detail_cleaned, detail_errors = validate_surveillance(request.form)
        elif activity_type == ActivityType.SMS:
            detail_cleaned, detail_errors = validate_sms(request.form)
        else:
            detail_cleaned, detail_errors = validate_office_activity(request.form)
        errors.update(detail_errors)

        for key in form_values:
            if key in ("email_done", "qa_db_update_done"):
                form_values[key] = (request.form.get(key) or "").strip().upper() == "YES"
            else:
                form_values[key] = request.form.get(key, form_values[key])

        if not errors:
            _save_activity_and_log(
                activity_type, common_cleaned, is_new=False, activity=activity, before_status=before_status
            )

            if activity_type == ActivityType.RAMP_INSPECTION:
                detail.option = detail_cleaned["option"]
                detail.airline_id = detail_cleaned["airline_id"]
                detail.aircraft_id = detail_cleaned["aircraft_id"]
                detail.flight_number = detail_cleaned["flight_number"]
                detail.email_done = detail_cleaned["email_done"]
                detail.qa_db_update_done = detail_cleaned["qa_db_update_done"]
            elif activity_type == ActivityType.SPOT_CHECKS:
                detail.spot_check_type = detail_cleaned["spot_check_type"]
                detail.area = detail_cleaned.get("area")
                detail.airline_id = detail_cleaned.get("airline_id")
                detail.aircraft_id = detail_cleaned.get("aircraft_id")
                detail.flight_number = detail_cleaned.get("flight_number")
                detail.email_done = detail_cleaned["email_done"]
                detail.qa_db_update_done = detail_cleaned["qa_db_update_done"]
            elif activity_type == ActivityType.AUDIT:
                detail.audit_type = detail_cleaned["audit_type"]
                detail.section = detail_cleaned["section"]
                detail.authority = detail_cleaned.get("authority")
                detail.operator = detail_cleaned.get("operator")
                detail.audit_stage = detail_cleaned["audit_stage"]
                detail.stage_status = detail_cleaned["stage_status"]
                detail.stage_remarks = detail_cleaned["stage_remarks"]
            elif activity_type == ActivityType.OCCURRENCE_REPORTING:
                detail.report_type = detail_cleaned["report_type"]
                detail.category = detail_cleaned["category"]
            elif activity_type == ActivityType.TRAINING:
                detail.mode = detail_cleaned["mode"]
                detail.kind = detail_cleaned["kind"]
            elif activity_type == ActivityType.COMPETENCE_ASSESSMENT:
                detail.personnel_type = detail_cleaned["personnel_type"]
                detail.name = detail_cleaned["name"]
                detail.pno_cno = detail_cleaned["pno_cno"]
            elif activity_type == ActivityType.CERTIFICATE_AUTHORIZATION:
                detail.option = detail_cleaned["option"]
            elif activity_type == ActivityType.AML_APPLICATION:
                detail.aml_type = detail_cleaned["aml_type"]
                detail.screening = detail_cleaned["screening"]
                detail.outcome = detail_cleaned["outcome"]
            elif activity_type == ActivityType.MAINTENANCE_EXPERIENCE:
                detail.option = detail_cleaned["option"]
                detail.name = detail_cleaned["name"]
                detail.pno_cno = detail_cleaned["pno_cno"]
                detail.action = detail_cleaned["action"]
            elif activity_type == ActivityType.INVESTIGATION:
                detail.investigation_type = detail_cleaned["investigation_type"]
                detail.mor_aircraft_type = detail_cleaned.get("mor_aircraft_type")
            elif activity_type == ActivityType.PCAA:
                detail.option = detail_cleaned["option"]
            elif activity_type == ActivityType.SURVEILLANCE:
                detail.option = detail_cleaned["option"]
            elif activity_type == ActivityType.SMS:
                detail.option = detail_cleaned["option"]
            else:  # OFFICE_ACTIVITY
                detail.option = detail_cleaned["option"]

            db.session.commit()
            flash("Activity updated successfully.", "success")
            return redirect(url_for("act.view_activity", activity_id=activity.id))
        flash("Please fix the errors below and try again.", "danger")

    ctx = _lookup_ctx()
    extra = {}
    if activity_type == ActivityType.RAMP_INSPECTION:
        extra["option_choices"] = RampInspectionOption.CHOICES
    elif activity_type == ActivityType.SPOT_CHECKS:
        extra["type_choices"] = SpotCheckType.CHOICES
        extra["area_choices"] = SpotCheckArea.CHOICES
        extra["aircraft_areas"] = SpotCheckArea.REQUIRES_AIRCRAFT_FIELDS
    elif activity_type == ActivityType.AUDIT:
        extra["audit_type_choices"] = AuditType.CHOICES
        extra["section_choices"] = AuditSection.CHOICES
        extra["audit_stage_choices"] = AuditStage.CHOICES
    elif activity_type == ActivityType.OCCURRENCE_REPORTING:
        extra["report_type_choices"] = OccurrenceReportType.CHOICES
        extra["category_choices"] = OccurrenceCategory.CHOICES
    elif activity_type == ActivityType.TRAINING:
        extra["mode_choices"] = TrainingMode.CHOICES
        extra["kind_choices"] = TrainingKind.CHOICES
        extra["conduct_allowed"] = TrainingKind.ALLOWED_FOR_CONDUCT
    elif activity_type == ActivityType.COMPETENCE_ASSESSMENT:
        extra["personnel_type_choices"] = PersonnelType.CHOICES
    elif activity_type == ActivityType.CERTIFICATE_AUTHORIZATION:
        extra["option_choices"] = CertificateAuthorizationOption.CHOICES
    elif activity_type == ActivityType.AML_APPLICATION:
        extra["type_choices"] = AmlApplicationType.CHOICES
        extra["screening_choices"] = AmlScreening.CHOICES
        extra["outcome_choices"] = AmlOutcome.CHOICES
    elif activity_type == ActivityType.MAINTENANCE_EXPERIENCE:
        extra["option_choices"] = MaintenanceExperienceOption.CHOICES
        extra["action_choices"] = MaintenanceExperienceAction.CHOICES
    elif activity_type == ActivityType.INVESTIGATION:
        extra["type_choices"] = InvestigationType.CHOICES
        extra["mor_aircraft_choices"] = MorAircraftType.CHOICES
    elif activity_type == ActivityType.PCAA:
        extra["option_choices"] = PcaaOption.CHOICES
    elif activity_type == ActivityType.SURVEILLANCE:
        extra["option_choices"] = SurveillanceOption.CHOICES
    elif activity_type == ActivityType.SMS:
        extra["option_choices"] = SmsOption.CHOICES
    else:  # OFFICE_ACTIVITY
        extra["option_choices"] = OfficeActivityOption.CHOICES

    return render_template(
        _EDIT_TEMPLATE[activity_type],
        activity=activity,
        form_values=form_values,
        errors=errors,
        **ctx,
        **extra,
    )


# ===========================================================================
# Delete (shared, dispatches on activity_type only to find/remove the
# specialized detail row - the parent Activity row cascades detail deletion
# at the DB level too, but we drop both explicitly so the audit log entry
# below is written before either is gone).
# ===========================================================================

@bp.route("/<int:activity_id>/delete", methods=["POST"])
@login_required
@roles_required(Role.SUPER_ADMIN, Role.CE_QA, Role.DCE_QA, Role.AIRCRAFT_ENGINEER)
def delete_activity(activity_id):
    """
    Permanently removes an Activity (and its specialized detail row, via
    ON DELETE CASCADE). Authorization is enforced twice - once at the
    coarse role level via `roles_required` (only authenticated, known
    roles can reach this route at all) and again via
    `can_delete_activity`, which restricts every role - including
    AIRCRAFT_ENGINEER - to activities they themselves created (and, for
    AIRCRAFT_ENGINEER, only while still OPEN) - mirroring the same
    defense-in-depth pattern used by `view_activity` / `edit_activity`.
    This is the check that actually matters: it runs against the
    activity loaded from the database, not anything the client sent, so
    a forged POST to another user's activity id is rejected here even if
    the Edit/Delete buttons were never shown for it.
    """
    activity = _get_activity_or_404(activity_id)

    if not can_delete_activity(current_user, activity):
        abort(403)

    log_action(
        "DELETE",
        "Activity",
        activity.id,
        f"Deleted {ActivityType.LABELS.get(activity.activity_type, activity.activity_type)} "
        f"activity #{activity.id} (station {activity.station_id})",
    )

    # Delete the specialized detail row first (if any) - the ORM's default
    # relationship cascade would otherwise try to NULL out its NOT NULL
    # activity_id FK before deleting the parent, which violates that
    # column's constraint. The DB-level ON DELETE CASCADE would handle this
    # fine for a raw SQL delete, but the ORM's unit-of-work doesn't know to
    # rely on it here since the object is already loaded/tracked.
    detail_attr = _DETAIL_ATTR.get(activity.activity_type)
    if detail_attr:
        detail = getattr(activity, detail_attr)
        if detail is not None:
            db.session.delete(detail)

    db.session.delete(activity)
    db.session.commit()

    flash("Activity deleted successfully.", "success")
    if current_user.role == Role.SUPER_ADMIN:
        return redirect(url_for("admin.activities_list"))
    return redirect(url_for("main.activities_list"))
