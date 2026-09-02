from app.extensions import db
from app.models.mixins import TimestampMixin


class ActivityStatus:
    OPEN = "OPEN"
    CLOSED = "CLOSED"

    ALL = [OPEN, CLOSED]


class ActivityType:
    """
    The 14 QA activity types tracked by the portal. Kept as a plain constant
    list (not a DB-backed lookup table) since `Activity.activity_type` is a
    free-form indexed string column by design (see the Activity docstring) -
    this list only drives dashboard cards / nav / filters in the UI, it does
    not constrain the column itself.

    Each entry is (code, label, icon) where `icon` is a Bootstrap Icons
    class name used on dashboard cards.
    """

    RAMP_INSPECTION = "RAMP_INSPECTION"
    SPOT_CHECKS = "SPOT_CHECKS"
    AUDIT = "AUDIT"
    OCCURRENCE_REPORTING = "OCCURRENCE_REPORTING"
    TRAINING = "TRAINING"
    COMPETENCE_ASSESSMENT = "COMPETENCE_ASSESSMENT"
    CERTIFICATE_AUTHORIZATION = "CERTIFICATE_AUTHORIZATION"
    AML_APPLICATION = "AML_APPLICATION"
    MAINTENANCE_EXPERIENCE = "MAINTENANCE_EXPERIENCE"
    INVESTIGATION = "INVESTIGATION"
    PCAA = "PCAA"
    SURVEILLANCE = "SURVEILLANCE"
    SMS = "SMS"
    OFFICE_ACTIVITY = "OFFICE_ACTIVITY"

    CHOICES = [
        (RAMP_INSPECTION, "Ramp Inspection", "bi-airplane-engines"),
        (SPOT_CHECKS, "Spot Checks", "bi-search"),
        (AUDIT, "Audit", "bi-clipboard-check"),
        (OCCURRENCE_REPORTING, "Occurrence Reporting", "bi-exclamation-triangle"),
        (TRAINING, "Training", "bi-mortarboard"),
        (COMPETENCE_ASSESSMENT, "Competence Assessment", "bi-award"),
        (CERTIFICATE_AUTHORIZATION, "Certification Authorization", "bi-patch-check"),
        (AML_APPLICATION, "AML Application", "bi-file-earmark-text"),
        (MAINTENANCE_EXPERIENCE, "Maintenance Experience", "bi-tools"),
        (INVESTIGATION, "Investigation", "bi-binoculars"),
        (PCAA, "PCAA", "bi-shield-check"),
        (SURVEILLANCE, "Surveillance", "bi-camera-video"),
        (SMS, "SMS", "bi-diagram-3"),
        (OFFICE_ACTIVITY, "Office Activity", "bi-building"),
    ]

    ALL = [c[0] for c in CHOICES]

    LABELS = {code: label for code, label, _icon in CHOICES}
    ICONS = {code: icon for code, _label, icon in CHOICES}


class Activity(TimestampMixin, db.Model):
    """
    Parent activity table.

    This table intentionally holds only fields common to every activity
    type. Type-specific fields belong on specialized child tables (added in
    later modules) that reference this table's id via a foreign key -
    keeping this table lean regardless of how many activity types exist.

    `activity_type` identifies which specialized table (if any) holds the
    extended details for a given row. It is a free-form string rather than
    an Enum tied to a fixed table set, since new activity types are expected
    to be added over time without a schema migration to this column.
    """

    __tablename__ = "activities"

    id = db.Column(db.Integer, primary_key=True)

    activity_date = db.Column(db.Date, nullable=False, index=True)

    shift_id = db.Column(
        db.Integer,
        db.ForeignKey("shifts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    activity_type = db.Column(db.String(50), nullable=False, index=True)

    station_id = db.Column(
        db.Integer,
        db.ForeignKey("stations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    status = db.Column(
        db.Enum(*ActivityStatus.ALL, name="activity_status"),
        nullable=False,
        default=ActivityStatus.OPEN,
        index=True,
    )

    remarks = db.Column(db.Text, nullable=True)

    updated_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # Relationships
    shift = db.relationship("Shift", back_populates="activities")
    station = db.relationship("Station", back_populates="activities")
    creator = db.relationship(
        "User", foreign_keys=[created_by], back_populates="created_activities"
    )
    updater = db.relationship(
        "User", foreign_keys=[updated_by], back_populates="updated_activities"
    )

    __table_args__ = (
        db.Index("ix_activities_station_date", "station_id", "activity_date"),
        db.Index("ix_activities_type_status", "activity_type", "status"),
    )

    def __repr__(self):
        return f"<Activity {self.id} {self.activity_type} {self.status}>"
