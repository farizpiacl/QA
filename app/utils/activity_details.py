"""
Module 6: server-side validation + edit-permission rules for Activity
Types 1-5 (Ramp Inspection, Spot Checks, Audit, Occurrence Reporting,
Training).

Each `validate_*` function takes a `request.form`-like mapping and returns
`(cleaned, errors)`, exactly like `app.utils.activity_forms.validate_activity_form`
- `cleaned` is only populated with values that passed validation, `errors`
maps field name -> message. Every conditional combination described in the
Module 6 spec is re-checked here; nothing is trusted from the client (a
disabled/hidden field can still be POSTed directly).
"""

from app.extensions import db
from app.models.activity import ActivityStatus
from app.models.airline import Airline
from app.models.aircraft import Aircraft
from app.models.ramp_inspection import RampInspectionOption
from app.models.spot_check import SpotCheckType, SpotCheckArea
from app.models.audit_detail import AuditType, AuditSection, AuditStage
from app.models.occurrence import OccurrenceReportType, OccurrenceCategory
from app.models.training_detail import TrainingMode, TrainingKind
from app.models.competence_assessment import PersonnelType
from app.models.certificate_authorization import CertificateAuthorizationOption
from app.models.aml_application import AmlApplicationType, AmlScreening, AmlOutcome
from app.models.maintenance_experience import MaintenanceExperienceOption, MaintenanceExperienceAction
from app.models.investigation import InvestigationType, MorAircraftType
from app.models.pcaa import PcaaOption
from app.models.surveillance import SurveillanceOption
from app.models.sms import SmsOption
from app.models.office_activity import OfficeActivityOption
from app.models.user import Role


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _require_choice(form, field, choices, label, errors, cleaned):
    raw = (form.get(field) or "").strip().upper()
    if not raw:
        errors[field] = f"{label} is required."
        return None
    if raw not in choices:
        errors[field] = f"Select a valid {label.lower()}."
        return None
    cleaned[field] = raw
    return raw


def _require_text(form, field, label, errors, cleaned, max_length=100):
    raw = (form.get(field) or "").strip()
    if not raw:
        errors[field] = f"{label} is required."
        return None
    if len(raw) > max_length:
        errors[field] = f"{label} must be {max_length} characters or fewer."
        return None
    cleaned[field] = raw
    return raw


def _require_airline(form, errors, cleaned, field="airline_id"):
    raw = (form.get(field) or "").strip()
    if not raw:
        errors[field] = "Airline is required."
        return None
    try:
        airline = db.session.get(Airline, int(raw))
    except (TypeError, ValueError):
        airline = None
    if airline is None or not airline.is_active:
        errors[field] = "Select a valid airline."
        return None
    cleaned[field] = airline.id
    return airline


def _require_aircraft(form, errors, cleaned, field="aircraft_id"):
    """Aircraft must come from the database (spec) - never free text."""
    raw = (form.get(field) or "").strip()
    if not raw:
        errors[field] = "Aircraft Registration is required."
        return None
    try:
        aircraft = db.session.get(Aircraft, int(raw))
    except (TypeError, ValueError):
        aircraft = None
    if aircraft is None or not aircraft.is_active:
        errors[field] = "Select a valid, active aircraft registration."
        return None
    cleaned[field] = aircraft.id
    return aircraft


def _optional_bool(form, field):
    raw = (form.get(field) or "").strip().upper()
    return raw in ("YES", "TRUE", "1", "ON")


def _optional_status(form, field, errors, cleaned, label):
    raw = (form.get(field) or ActivityStatus.OPEN).strip().upper()
    if raw not in ActivityStatus.ALL:
        errors[field] = f"Select a valid {label} status."
        return
    cleaned[field] = raw


def _optional_remarks(form, field, errors, cleaned, max_length=4000):
    raw = (form.get(field) or "").strip()
    if len(raw) > max_length:
        errors[field] = f"Remarks must be {max_length} characters or fewer."
        return
    cleaned[field] = raw or None


# ---------------------------------------------------------------------------
# 1. Ramp Inspection
# ---------------------------------------------------------------------------

def validate_ramp_inspection(form):
    """
    All 4 options require the same field set - see RampInspectionOption
    docstring - so there's no conditional branching beyond the option
    itself needing to be one of the 4 valid values.
    """
    errors = {}
    cleaned = {}

    _require_choice(form, "option", RampInspectionOption.ALL, "Option", errors, cleaned)
    _require_airline(form, errors, cleaned)
    _require_aircraft(form, errors, cleaned)
    _require_text(form, "flight_number", "Flight No.", errors, cleaned, max_length=20)

    cleaned["email_done"] = _optional_bool(form, "email_done")
    cleaned["qa_db_update_done"] = _optional_bool(form, "qa_db_update_done")

    return cleaned, errors


# ---------------------------------------------------------------------------
# 2. Spot Checks
# ---------------------------------------------------------------------------

def validate_spot_check(form):
    errors = {}
    cleaned = {}

    spot_check_type = _require_choice(
        form, "spot_check_type", SpotCheckType.ALL, "Spot Checks Type", errors, cleaned
    )

    area = None
    if spot_check_type == SpotCheckType.AREAS:
        area = _require_choice(form, "area", SpotCheckArea.ALL, "Area", errors, cleaned)
    else:
        cleaned["area"] = None

    needs_aircraft_fields = spot_check_type == SpotCheckType.PCAA or (
        spot_check_type == SpotCheckType.AREAS
        and area in SpotCheckArea.REQUIRES_AIRCRAFT_FIELDS
    )

    if needs_aircraft_fields:
        _require_airline(form, errors, cleaned)
        _require_aircraft(form, errors, cleaned)
        _require_text(form, "flight_number", "Flight No.", errors, cleaned, max_length=20)
    else:
        cleaned["airline_id"] = None
        cleaned["aircraft_id"] = None
        cleaned["flight_number"] = None

    cleaned["email_done"] = _optional_bool(form, "email_done")
    cleaned["qa_db_update_done"] = _optional_bool(form, "qa_db_update_done")

    return cleaned, errors


# ---------------------------------------------------------------------------
# 3. Audit
# ---------------------------------------------------------------------------

def validate_audit(form):
    errors = {}
    cleaned = {}

    _require_choice(form, "audit_type", AuditType.ALL, "Audit Type", errors, cleaned)
    section = _require_choice(form, "section", AuditSection.ALL, "Section/Station", errors, cleaned)

    if section == AuditSection.EXTERNAL:
        _require_text(form, "authority", "Authority", errors, cleaned, max_length=150)
        # "Authority Operator" is optional even for External Audit - not required.
        operator_raw = (form.get("operator") or "").strip()
        cleaned["operator"] = operator_raw[:150] if operator_raw else None
    else:
        cleaned["authority"] = None
        cleaned["operator"] = None

    _require_choice(form, "audit_stage", AuditStage.ALL, "Audit Stage", errors, cleaned)
    _optional_status(form, "stage_status", errors, cleaned, "Audit Stage Status")
    _optional_remarks(form, "stage_remarks", errors, cleaned)

    return cleaned, errors


# ---------------------------------------------------------------------------
# 4. Occurrence Reporting
# ---------------------------------------------------------------------------

def validate_occurrence(form):
    errors = {}
    cleaned = {}

    _require_choice(form, "report_type", OccurrenceReportType.ALL, "Occurrence Report Type", errors, cleaned)
    _require_choice(form, "category", OccurrenceCategory.ALL, "Occurrence", errors, cleaned)

    return cleaned, errors


# ---------------------------------------------------------------------------
# 5. Training
# ---------------------------------------------------------------------------

def validate_training(form):
    errors = {}
    cleaned = {}

    mode = _require_choice(form, "mode", TrainingMode.ALL, "Conduct/Attend", errors, cleaned)
    kind = _require_choice(form, "kind", TrainingKind.ALL, "Training Kind", errors, cleaned)

    if mode and kind:
        allowed = (
            TrainingKind.ALLOWED_FOR_CONDUCT
            if mode == TrainingMode.CONDUCT
            else TrainingKind.ALLOWED_FOR_ATTEND
        )
        if kind not in allowed:
            errors["kind"] = (
                '"Types" is only valid under Attend.'
                if kind == TrainingKind.TYPES
                else "Select a training kind valid for the chosen Conduct/Attend option."
            )
            cleaned.pop("kind", None)

    return cleaned, errors


# ---------------------------------------------------------------------------
# 6. Competence Assessment of Personnel
# ---------------------------------------------------------------------------

def validate_competence_assessment(form):
    errors = {}
    cleaned = {}

    _require_choice(form, "personnel_type", PersonnelType.ALL, "Personnel Type", errors, cleaned)
    _require_text(form, "name", "Name", errors, cleaned, max_length=150)
    _require_text(form, "pno_cno", "PNO/CNO", errors, cleaned, max_length=50)

    return cleaned, errors


# ---------------------------------------------------------------------------
# 7. Certification Authorization
# ---------------------------------------------------------------------------

def validate_certificate_authorization(form):
    errors = {}
    cleaned = {}

    _require_choice(
        form, "option", CertificateAuthorizationOption.ALL, "Option", errors, cleaned
    )

    return cleaned, errors


# ---------------------------------------------------------------------------
# 8. AML Application
# ---------------------------------------------------------------------------

def validate_aml_application(form):
    """
    Type -> Screening -> Outcome. All three are always required regardless
    of the values chosen - the spec shows a linear flow ("Then... Then...")
    with no branch that skips a step, unlike Spot Checks/Investigation.
    """
    errors = {}
    cleaned = {}

    _require_choice(form, "aml_type", AmlApplicationType.ALL, "Type", errors, cleaned)
    _require_choice(form, "screening", AmlScreening.ALL, "Screening", errors, cleaned)
    _require_choice(form, "outcome", AmlOutcome.ALL, "Outcome", errors, cleaned)

    return cleaned, errors


# ---------------------------------------------------------------------------
# 9. Maintenance Experience
# ---------------------------------------------------------------------------

def validate_maintenance_experience(form):
    errors = {}
    cleaned = {}

    _require_choice(
        form, "option", MaintenanceExperienceOption.ALL, "Option", errors, cleaned
    )
    _require_text(form, "name", "Name", errors, cleaned, max_length=150)
    _require_text(form, "pno_cno", "PNO/CNO", errors, cleaned, max_length=50)
    _require_choice(
        form, "action", MaintenanceExperienceAction.ALL, "Action", errors, cleaned
    )

    return cleaned, errors


# ---------------------------------------------------------------------------
# 10. Investigation
# ---------------------------------------------------------------------------

def validate_investigation(form):
    errors = {}
    cleaned = {}

    investigation_type = _require_choice(
        form, "investigation_type", InvestigationType.ALL, "Type", errors, cleaned
    )

    if investigation_type == InvestigationType.MOR:
        _require_choice(
            form, "mor_aircraft_type", MorAircraftType.ALL, "Aircraft Type", errors, cleaned
        )
    else:
        cleaned["mor_aircraft_type"] = None

    return cleaned, errors


# ---------------------------------------------------------------------------
# 11. PCAA
# ---------------------------------------------------------------------------

def validate_pcaa(form):
    errors = {}
    cleaned = {}

    _require_choice(form, "option", PcaaOption.ALL, "Option", errors, cleaned)

    return cleaned, errors


# ---------------------------------------------------------------------------
# 12. Surveillance
# ---------------------------------------------------------------------------

def validate_surveillance(form):
    errors = {}
    cleaned = {}

    _require_choice(form, "option", SurveillanceOption.ALL, "Option", errors, cleaned)

    return cleaned, errors


# ---------------------------------------------------------------------------
# 13. SMS
# ---------------------------------------------------------------------------

def validate_sms(form):
    errors = {}
    cleaned = {}

    _require_choice(form, "option", SmsOption.ALL, "Option", errors, cleaned)

    return cleaned, errors


# ---------------------------------------------------------------------------
# 14. Office Activity
# ---------------------------------------------------------------------------

def validate_office_activity(form):
    errors = {}
    cleaned = {}

    _require_choice(form, "option", OfficeActivityOption.ALL, "Option", errors, cleaned)

    return cleaned, errors


# ---------------------------------------------------------------------------
# Dispatch table used by the routes layer
# ---------------------------------------------------------------------------

from app.models.activity import ActivityType  # noqa: E402  (avoid circular import at module load)

VALIDATORS = {
    ActivityType.RAMP_INSPECTION: validate_ramp_inspection,
    ActivityType.SPOT_CHECKS: validate_spot_check,
    ActivityType.AUDIT: validate_audit,
    ActivityType.OCCURRENCE_REPORTING: validate_occurrence,
    ActivityType.TRAINING: validate_training,
    ActivityType.COMPETENCE_ASSESSMENT: validate_competence_assessment,
    ActivityType.CERTIFICATE_AUTHORIZATION: validate_certificate_authorization,
    ActivityType.AML_APPLICATION: validate_aml_application,
    ActivityType.MAINTENANCE_EXPERIENCE: validate_maintenance_experience,
    ActivityType.INVESTIGATION: validate_investigation,
    ActivityType.PCAA: validate_pcaa,
    ActivityType.SURVEILLANCE: validate_surveillance,
    ActivityType.SMS: validate_sms,
    ActivityType.OFFICE_ACTIVITY: validate_office_activity,
}


# ---------------------------------------------------------------------------
# Edit permissions
# ---------------------------------------------------------------------------

def can_edit_activity(user, activity) -> bool:
    """
    Ownership rule (per spec): a user may only edit an activity they
    themselves created - regardless of role. SUPER_ADMIN, CE_QA and DCE_QA
    are no longer granted blanket Pakistan-wide / station-wide edit access
    to *other* users' activities; no other system rule currently requires
    that, so ownership is the only gate.

      Any role  -> can edit only activities they created (`created_by`).
      AIRCRAFT_ENGINEER -> additionally, only while still OPEN. Once
                            CLOSED, even the creating engineer can no
                            longer edit it.

    Mirrors `app.utils.authz.can_view_activity`'s scoping for visibility,
    but is intentionally stricter here (ownership is required, not just
    station/OPEN visibility), since editing is a state change rather than
    a read.
    """
    if activity.created_by != user.id:
        return False

    if user.role == Role.AIRCRAFT_ENGINEER:
        return activity.status == ActivityStatus.OPEN

    return user.role in (Role.SUPER_ADMIN, Role.CE_QA, Role.DCE_QA)


def can_delete_activity(user, activity) -> bool:
    """
    Deletion permanently destroys an audit-relevant record, so it is
    intentionally stricter than edit:

      Any role -> can delete only activities they themselves created
                  (`created_by`). No role gets blanket delete rights over
                  another user's activity - ownership is required, and is
                  checked here (not just hidden in the UI), so a
                  manually-posted request to another user's activity id
                  is rejected regardless of what the frontend shows.
      AIRCRAFT_ENGINEER -> can never delete activities, even their own,
                            even while still OPEN. This is checked here
                            (not just hidden in the UI), so a manually
                            posted delete request from an engineer is
                            rejected regardless of what the frontend shows.
    """
    if activity.created_by != user.id:
        return False

    if user.role == Role.AIRCRAFT_ENGINEER:
        return False

    return user.role in (Role.SUPER_ADMIN, Role.CE_QA, Role.DCE_QA)
