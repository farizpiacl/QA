"""
Module 9: Activities management + Reports.

Centralizes everything the Activities / Open Activities / Recent Activities
/ Reports pages share:

  - extra filters (search, date range, station, type, status, creator,
    airline, aircraft) layered on top of `app.utils.authz.apply_activity_scope`
    - so a filter can only ever narrow what a role is already allowed to
    see, never widen it.
  - the "Sub Type" label shown per activity type on list/report pages.
  - the 19-report registry used by the Reports section, each report reading
    live from the database (never sample/fake data).
  - Excel / PDF export builders shared by every report.

Both `app.routes.main` (CE_QA/DCE_QA/AIRCRAFT_ENGINEER) and
`app.routes.admin` (SUPER_ADMIN) import from here so the two "Activities"
surfaces and the Reports surface behave identically.
"""

from datetime import datetime
from io import BytesIO

from app.extensions import db
from app.models.activity import Activity, ActivityStatus, ActivityType
from app.models.station import Station
from app.models.shift import Shift
from app.models.user import User
from app.models.airline import Airline
from app.models.aircraft import Aircraft

from app.models.ramp_inspection import RampInspectionDetail, RampInspectionOption
from app.models.spot_check import SpotCheckDetail, SpotCheckType
from app.models.audit_detail import AuditDetail, AuditType
from app.models.occurrence import OccurrenceDetail, OccurrenceReportType
from app.models.training_detail import TrainingDetail, TrainingKind
from app.models.competence_assessment import CompetenceAssessmentDetail, PersonnelType
from app.models.certificate_authorization import (
    CertificateAuthorizationDetail,
    CertificateAuthorizationOption,
)
from app.models.aml_application import AmlApplicationDetail, AmlApplicationType
from app.models.maintenance_experience import (
    MaintenanceExperienceDetail,
    MaintenanceExperienceOption,
)
from app.models.investigation import InvestigationDetail, InvestigationType
from app.models.pcaa import PcaaDetail, PcaaOption
from app.models.surveillance import SurveillanceDetail, SurveillanceOption
from app.models.sms import SmsDetail, SmsOption
from app.models.office_activity import OfficeActivityDetail, OfficeActivityOption

from app.utils.authz import apply_activity_scope


# ---------------------------------------------------------------------------
# Sub Type resolution
# ---------------------------------------------------------------------------

# activity_type -> (backref attribute on Activity, sub-type column name on
# the detail row, LABELS dict for that column). Mirrors
# `app.routes.activity_details._DETAIL_ATTR` / `_detail_labels` but scoped
# to just the one field the Activities/Reports tables show as "Sub Type".
_SUB_TYPE_SPEC = {
    ActivityType.RAMP_INSPECTION: ("ramp_inspection_detail", "option", RampInspectionOption.LABELS),
    ActivityType.SPOT_CHECKS: ("spot_check_detail", "spot_check_type", SpotCheckType.LABELS),
    ActivityType.AUDIT: ("audit_detail", "audit_type", AuditType.LABELS),
    ActivityType.OCCURRENCE_REPORTING: ("occurrence_detail", "report_type", OccurrenceReportType.LABELS),
    ActivityType.TRAINING: ("training_detail", "kind", TrainingKind.LABELS),
    ActivityType.COMPETENCE_ASSESSMENT: ("competence_assessment_detail", "personnel_type", PersonnelType.LABELS),
    ActivityType.CERTIFICATE_AUTHORIZATION: (
        "certificate_authorization_detail", "option", CertificateAuthorizationOption.LABELS
    ),
    ActivityType.AML_APPLICATION: ("aml_application_detail", "aml_type", AmlApplicationType.LABELS),
    ActivityType.MAINTENANCE_EXPERIENCE: (
        "maintenance_experience_detail", "option", MaintenanceExperienceOption.LABELS
    ),
    ActivityType.INVESTIGATION: ("investigation_detail", "investigation_type", InvestigationType.LABELS),
    ActivityType.PCAA: ("pcaa_detail", "option", PcaaOption.LABELS),
    ActivityType.SURVEILLANCE: ("surveillance_detail", "option", SurveillanceOption.LABELS),
    ActivityType.SMS: ("sms_detail", "option", SmsOption.LABELS),
    ActivityType.OFFICE_ACTIVITY: ("office_activity_detail", "option", OfficeActivityOption.LABELS),
}


def sub_type_label(activity) -> str:
    """Best-effort 'Sub Type' cell for the Activities table / reports."""
    spec = _SUB_TYPE_SPEC.get(activity.activity_type)
    if spec is None:
        return "—"
    attr, field_name, labels = spec
    detail = getattr(activity, attr, None)
    if detail is None:
        return "—"
    raw = getattr(detail, field_name, None)
    if raw is None:
        return "—"
    return labels.get(raw, raw)


# ---------------------------------------------------------------------------
# Filters shared by Activities / Open Activities / Recent Activities / Reports
# ---------------------------------------------------------------------------

def _parse_date(raw):
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return None


def get_filter_choices(user):
    """Dropdown option lists for the Activities / Reports filter forms.

    These are option lists only - the actual row-level scoping is always
    enforced by `apply_activity_scope` / `apply_common_filters`, so offering
    a station or user in a dropdown never grants access to it.
    """
    return {
        "stations": Station.query.filter_by(is_active=True).order_by(Station.code).all(),
        "shifts": Shift.query.filter_by(is_active=True).order_by(Shift.name).all(),
        "airlines": Airline.query.filter_by(is_active=True).order_by(Airline.code).all(),
        "aircraft": Aircraft.query.filter_by(is_active=True).order_by(Aircraft.registration).all(),
        "creators": User.query.filter_by(is_active=True).order_by(User.full_name).all(),
        "activity_types": ActivityType.CHOICES,
        "statuses": ActivityStatus.ALL,
    }


def _airline_aircraft_join(query):
    """
    Left-join the two detail tables that can carry an airline/aircraft
    (Ramp Inspection, Spot Checks). Each activity has at most one of the
    two rows (based on its activity_type), so this never duplicates rows.
    """
    return query.outerjoin(
        RampInspectionDetail, RampInspectionDetail.activity_id == Activity.id
    ).outerjoin(
        SpotCheckDetail, SpotCheckDetail.activity_id == Activity.id
    )


def apply_common_filters(query, args):
    """
    Layers the Activities/Reports filter set on top of an already
    role-scoped query. `args` is a `request.args`-like mapping using the
    field names the filter forms submit: q, date_from, date_to, station_id,
    type, status, created_by, airline_id, aircraft_id.
    """
    search = (args.get("q") or "").strip()
    date_from = _parse_date(args.get("date_from"))
    date_to = _parse_date(args.get("date_to"))
    station_id = (args.get("station_id") or "").strip()
    activity_type = (args.get("type") or "").strip().upper()
    status = (args.get("status") or "").strip().upper()
    created_by = (args.get("created_by") or "").strip()
    airline_id = (args.get("airline_id") or "").strip()
    aircraft_id = (args.get("aircraft_id") or "").strip()
    shift_id = (args.get("shift_id") or "").strip()

    if date_from:
        query = query.filter(Activity.activity_date >= date_from)
    if date_to:
        query = query.filter(Activity.activity_date <= date_to)
    if station_id.isdigit():
        query = query.filter(Activity.station_id == int(station_id))
    if activity_type in ActivityType.ALL:
        query = query.filter(Activity.activity_type == activity_type)
    if status in ActivityStatus.ALL:
        query = query.filter(Activity.status == status)
    if created_by.isdigit():
        query = query.filter(Activity.created_by == int(created_by))
    if shift_id.isdigit():
        query = query.filter(Activity.shift_id == int(shift_id))

    if airline_id.isdigit() or aircraft_id.isdigit():
        query = _airline_aircraft_join(query)
        conds = []
        if airline_id.isdigit():
            conds.append(RampInspectionDetail.airline_id == int(airline_id))
            conds.append(SpotCheckDetail.airline_id == int(airline_id))
        if aircraft_id.isdigit():
            conds.append(RampInspectionDetail.aircraft_id == int(aircraft_id))
            conds.append(SpotCheckDetail.aircraft_id == int(aircraft_id))
        query = query.filter(db.or_(*conds))

    if search:
        like = f"%{search}%"
        query = (
            query.join(User, User.id == Activity.created_by)
            .join(Station, Station.id == Activity.station_id)
            .filter(
                db.or_(
                    Activity.remarks.ilike(like),
                    Activity.activity_type.ilike(like),
                    User.full_name.ilike(like),
                    User.username.ilike(like),
                    Station.code.ilike(like),
                    Station.name.ilike(like),
                )
            )
        )

    return query


# ---------------------------------------------------------------------------
# Reports registry
# ---------------------------------------------------------------------------

REPORT_TYPES = [
    ("overall", "Overall Activity"),
    (ActivityType.RAMP_INSPECTION, "Ramp Inspection"),
    (ActivityType.SPOT_CHECKS, "Spot Checks"),
    (ActivityType.AUDIT, "Audit"),
    (ActivityType.OCCURRENCE_REPORTING, "Occurrence Reporting"),
    (ActivityType.TRAINING, "Training"),
    (ActivityType.COMPETENCE_ASSESSMENT, "Competence Assessment"),
    (ActivityType.CERTIFICATE_AUTHORIZATION, "Certification Authorization"),
    (ActivityType.AML_APPLICATION, "AML Application"),
    (ActivityType.MAINTENANCE_EXPERIENCE, "Maintenance Experience"),
    (ActivityType.INVESTIGATION, "Investigation"),
    (ActivityType.PCAA, "PCAA"),
    (ActivityType.SURVEILLANCE, "Surveillance"),
    (ActivityType.SMS, "SMS"),
    (ActivityType.OFFICE_ACTIVITY, "Office Activity"),
    ("open", "Open Activities"),
    ("closed", "Closed Activities"),
    ("station_wise", "Station-wise"),
    ("user_wise", "User-wise"),
    ("airline_wise", "Airline-wise"),
]
REPORT_LABELS = dict(REPORT_TYPES)

_AGGREGATE_REPORTS = {"station_wise", "user_wise", "airline_wise"}

LIST_HEADERS = ["Date", "Activity", "Sub Type", "Station", "Status", "Created By"]
AGGREGATE_HEADERS = ["Group", "Total", "Open", "Closed"]


def run_report(report_code, user, args):
    """
    Runs one report, fully scoped to `user` and filtered by `args`.

    Returns ("list", query) for row-level reports - caller paginates - or
    ("aggregate", rows) for the "-wise" summary reports, where `rows` is
    already a list of plain dicts (small enough to render without paging).
    Every branch reads live from the database; nothing here is sample data.

    For AIRCRAFT_ENGINEER, the shared OPEN-task pool (other engineers'
    OPEN activities) is only included for the "open" report - every other
    report (closed, a specific type, "overall", the -wise aggregates) is
    scoped to that engineer's own activities only, so Reports can't be
    used as a side door into another engineer's activity.
    """
    base = apply_common_filters(
        apply_activity_scope(Activity.query, user, include_open_pool=(report_code == "open")),
        args,
    )

    if report_code == "open":
        return "list", base.filter(Activity.status == ActivityStatus.OPEN).order_by(Activity.activity_date.desc())
    if report_code == "closed":
        return "list", base.filter(Activity.status == ActivityStatus.CLOSED).order_by(Activity.activity_date.desc())
    if report_code in ActivityType.ALL:
        return "list", base.filter(Activity.activity_type == report_code).order_by(Activity.activity_date.desc())

    if report_code == "station_wise":
        rows = (
            base.join(Station, Station.id == Activity.station_id)
            .with_entities(
                Station.code,
                Station.name,
                db.func.count(Activity.id),
                db.func.sum(db.case((Activity.status == ActivityStatus.OPEN, 1), else_=0)),
                db.func.sum(db.case((Activity.status == ActivityStatus.CLOSED, 1), else_=0)),
            )
            .group_by(Station.id, Station.code, Station.name)
            .order_by(Station.code)
            .all()
        )
        return "aggregate", [
            {"label": f"{code} — {name}", "total": total, "open": open_c or 0, "closed": closed_c or 0}
            for code, name, total, open_c, closed_c in rows
        ]

    if report_code == "user_wise":
        rows = (
            base.join(User, User.id == Activity.created_by)
            .with_entities(
                User.full_name,
                User.username,
                db.func.count(Activity.id),
                db.func.sum(db.case((Activity.status == ActivityStatus.OPEN, 1), else_=0)),
                db.func.sum(db.case((Activity.status == ActivityStatus.CLOSED, 1), else_=0)),
            )
            .group_by(User.id, User.full_name, User.username)
            .order_by(User.full_name)
            .all()
        )
        return "aggregate", [
            {"label": f"{name} ({username})", "total": total, "open": open_c or 0, "closed": closed_c or 0}
            for name, username, total, open_c, closed_c in rows
        ]

    if report_code == "airline_wise":
        joined = _airline_aircraft_join(base)
        rows = (
            joined.outerjoin(
                Airline,
                db.or_(
                    Airline.id == RampInspectionDetail.airline_id,
                    Airline.id == SpotCheckDetail.airline_id,
                ),
            )
            .filter(Airline.id.isnot(None))
            .with_entities(
                Airline.code,
                Airline.name,
                db.func.count(db.distinct(Activity.id)),
            )
            .group_by(Airline.id, Airline.code, Airline.name)
            .order_by(Airline.code)
            .all()
        )
        return "aggregate", [
            {"label": f"{code} — {name}", "total": total, "open": None, "closed": None}
            for code, name, total in rows
        ]

    # "overall" (or an unrecognized code) -> every activity the user can see.
    return "list", base.order_by(Activity.activity_date.desc())


def list_export_rows(activities):
    return [
        [
            a.activity_date.isoformat(),
            ActivityType.LABELS.get(a.activity_type, a.activity_type),
            sub_type_label(a),
            a.station.code if a.station else "",
            a.status,
            a.creator.full_name if a.creator else "",
        ]
        for a in activities
    ]


def aggregate_export_rows(rows):
    return [[r["label"], r["total"], r["open"], r["closed"]] for r in rows]


# ---------------------------------------------------------------------------
# Export builders
# ---------------------------------------------------------------------------

# Hard cap on rows pulled for a single export - keeps a broad/unfiltered
# report from loading an unbounded result set into memory.
EXPORT_ROW_LIMIT = 10000


def export_excel(headers, rows, title="Report"):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = (title or "Report")[:31]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        ws.append(row)
    for col_cells in ws.columns:
        length = max((len(str(c.value)) for c in col_cells if c.value is not None), default=10)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max(length + 2, 10), 40)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def export_pdf(headers, rows, title="Report"):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4), topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.2 * cm, rightMargin=1.2 * cm,
    )
    styles = getSampleStyleSheet()
    elements = [Paragraph(title or "Report", styles["Title"]), Spacer(1, 12)]

    data = [headers] + [["" if c is None else str(c) for c in row] for row in rows]
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#212529")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f4f4")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(table)
    doc.build(elements)
    buf.seek(0)
    return buf
