"""
Import every model module here so that:
  1. `from app.models import User, Station, ...` works everywhere.
  2. Flask-Migrate/Alembic's autogenerate sees the full metadata when this
     package is imported (e.g. via the app factory).

When adding a new model (e.g. a specialized activity table in a later
module), import it here too.
"""

from app.models.user import User, Role
from app.models.station import Station
from app.models.shift import Shift
from app.models.airline import Airline
from app.models.aircraft import Aircraft
from app.models.activity import Activity, ActivityStatus, ActivityType
from app.models.audit_log import AuditLog

# Module 6: Activity Types 1-5 detail tables.
from app.models.ramp_inspection import RampInspectionDetail, RampInspectionOption
from app.models.spot_check import SpotCheckDetail, SpotCheckType, SpotCheckArea
from app.models.audit_detail import AuditDetail, AuditType, AuditSection
from app.models.occurrence import OccurrenceDetail, OccurrenceReportType, OccurrenceCategory
from app.models.training_detail import TrainingDetail, TrainingMode, TrainingKind

# Module 7: Activity Types 6-10 detail tables.
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

# Module 8: Activity Types 11-14 detail tables.
from app.models.pcaa import PcaaDetail, PcaaOption
from app.models.surveillance import SurveillanceDetail, SurveillanceOption
from app.models.sms import SmsDetail, SmsOption
from app.models.office_activity import OfficeActivityDetail, OfficeActivityOption

__all__ = [
    "User",
    "Role",
    "Station",
    "Shift",
    "Airline",
    "Aircraft",
    "Activity",
    "ActivityStatus",
    "ActivityType",
    "AuditLog",
    "RampInspectionDetail",
    "RampInspectionOption",
    "SpotCheckDetail",
    "SpotCheckType",
    "SpotCheckArea",
    "AuditDetail",
    "AuditType",
    "AuditSection",
    "OccurrenceDetail",
    "OccurrenceReportType",
    "OccurrenceCategory",
    "TrainingDetail",
    "TrainingMode",
    "TrainingKind",
    "CompetenceAssessmentDetail",
    "PersonnelType",
    "CertificateAuthorizationDetail",
    "CertificateAuthorizationOption",
    "AmlApplicationDetail",
    "AmlApplicationType",
    "AmlScreening",
    "AmlOutcome",
    "MaintenanceExperienceDetail",
    "MaintenanceExperienceOption",
    "MaintenanceExperienceAction",
    "InvestigationDetail",
    "InvestigationType",
    "MorAircraftType",
    "PcaaDetail",
    "PcaaOption",
    "SurveillanceDetail",
    "SurveillanceOption",
    "SmsDetail",
    "SmsOption",
    "OfficeActivityDetail",
    "OfficeActivityOption",
]

# Register Activity Types 1-5 against the Module 5 activity_registry so
# `get_spec(code).detail_model` resolves for the generic engine / dashboards
# even though these 5 types use their own specialized forms+routes (Module 6)
# rather than the generic flat-field renderer - their conditional structure
# (nested type -> sub-type -> conditional fields) goes beyond what the
# generic single-level field list supports.
def _register_module6_activity_types():
    from app.utils.activity_registry import register_activity_type

    register_activity_type(ActivityType.RAMP_INSPECTION, fields=[], detail_model=RampInspectionDetail)
    register_activity_type(ActivityType.SPOT_CHECKS, fields=[], detail_model=SpotCheckDetail)
    register_activity_type(ActivityType.AUDIT, fields=[], detail_model=AuditDetail)
    register_activity_type(ActivityType.OCCURRENCE_REPORTING, fields=[], detail_model=OccurrenceDetail)
    register_activity_type(ActivityType.TRAINING, fields=[], detail_model=TrainingDetail)


_register_module6_activity_types()


# Register Activity Types 6-10 against the same registry (Module 7), for the
# same reason as Module 6 above: their conditional structure goes beyond the
# generic single-level field list, so they use specialized forms+routes
# (app.routes.activity_details) rather than the generic renderer.
def _register_module7_activity_types():
    from app.utils.activity_registry import register_activity_type

    register_activity_type(
        ActivityType.COMPETENCE_ASSESSMENT, fields=[], detail_model=CompetenceAssessmentDetail
    )
    register_activity_type(
        ActivityType.CERTIFICATE_AUTHORIZATION, fields=[], detail_model=CertificateAuthorizationDetail
    )
    register_activity_type(ActivityType.AML_APPLICATION, fields=[], detail_model=AmlApplicationDetail)
    register_activity_type(
        ActivityType.MAINTENANCE_EXPERIENCE, fields=[], detail_model=MaintenanceExperienceDetail
    )
    register_activity_type(ActivityType.INVESTIGATION, fields=[], detail_model=InvestigationDetail)


_register_module7_activity_types()


# Register Activity Types 11-14 against the same registry (Module 8), for the
# same reason as Modules 6-7 above: they use specialized forms+routes
# (app.routes.activity_details) rather than the generic renderer.
def _register_module8_activity_types():
    from app.utils.activity_registry import register_activity_type

    register_activity_type(ActivityType.PCAA, fields=[], detail_model=PcaaDetail)
    register_activity_type(ActivityType.SURVEILLANCE, fields=[], detail_model=SurveillanceDetail)
    register_activity_type(ActivityType.SMS, fields=[], detail_model=SmsDetail)
    register_activity_type(ActivityType.OFFICE_ACTIVITY, fields=[], detail_model=OfficeActivityDetail)


_register_module8_activity_types()
