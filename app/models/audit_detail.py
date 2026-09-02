from app.extensions import db
from app.models.activity import ActivityStatus
from app.models.mixins import TimestampMixin


class AuditType:
    SCHEDULED = "SCHEDULED"
    UNSCHEDULED = "UNSCHEDULED"
    SPECIAL_PURPOSE_AUDIT = "SPECIAL_PURPOSE_AUDIT"
    VERIFICATION_AUDIT = "VERIFICATION_AUDIT"
    DESKTOP_AUDIT = "DESKTOP_AUDIT"
    PRODUCT_AUDIT = "PRODUCT_AUDIT"

    CHOICES = [
        (SCHEDULED, "Scheduled"),
        (UNSCHEDULED, "Unscheduled"),
        (SPECIAL_PURPOSE_AUDIT, "Special Purpose Audit"),
        (VERIFICATION_AUDIT, "Verification Audit"),
        (DESKTOP_AUDIT, "Desktop Audit"),
        (PRODUCT_AUDIT, "Product Audit"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class AuditStage:
    """Which stage of the audit lifecycle this audit activity currently reflects."""

    AUDIT_PREPARATION = "AUDIT_PREPARATION"
    POST_AUDIT_ACTIVITY = "POST_AUDIT_ACTIVITY"
    CLOSURE_OF_AUDIT = "CLOSURE_OF_AUDIT"
    AUDIT_PERFORMANCE = "AUDIT_PERFORMANCE"

    CHOICES = [
        (AUDIT_PREPARATION, "Audit Preparation"),
        (POST_AUDIT_ACTIVITY, "Post Audit Activity"),
        (CLOSURE_OF_AUDIT, "Closure of Audit"),
        (AUDIT_PERFORMANCE, "Audit Performance"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class AuditSection:
    """Section/Station being audited."""

    AUDIT_OF_QA = "AUDIT_OF_QA"
    LINE_MAINTENANCE = "LINE_MAINTENANCE"
    AWM_TSE = "AWM_TSE"
    FAISALABAD_LM = "FAISALABAD_LM"
    SIALKOT_LM = "SIALKOT_LM"
    MULTAN_LM = "MULTAN_LM"
    BAHAWALPUR_LM = "BAHAWALPUR_LM"
    PCAA = "PCAA"
    EXTERNAL = "EXTERNAL"

    CHOICES = [
        (AUDIT_OF_QA, "Audit of QA"),
        (LINE_MAINTENANCE, "Line Maintenance"),
        (AWM_TSE, "AWM/TSE"),
        (FAISALABAD_LM, "Faisalabad LM"),
        (SIALKOT_LM, "Sialkot LM"),
        (MULTAN_LM, "Multan LM"),
        (BAHAWALPUR_LM, "Bahawalpur LM"),
        (PCAA, "PCAA"),
        (EXTERNAL, "External"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class AuditDetail(TimestampMixin, db.Model):
    """
    Module 6: Activity Type 3 - Audit detail row.

    One-to-one with `activities`. `authority`/`operator` are only required
    when `section == EXTERNAL`.

    `audit_stage` is a single dropdown identifying which stage of the audit
    lifecycle (Audit Preparation / Post Audit Activity / Closure of Audit)
    this record currently reflects, paired with one OPEN/CLOSED status and
    one remarks field for that stage. This replaces the earlier design of
    three separate always-visible stage sections (one column pair each).
    """

    __tablename__ = "audit_details"

    id = db.Column(db.Integer, primary_key=True)

    activity_id = db.Column(
        db.Integer,
        db.ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    audit_type = db.Column(db.Enum(*AuditType.ALL, name="audit_type"), nullable=False)
    section = db.Column(db.Enum(*AuditSection.ALL, name="audit_section"), nullable=False)

    authority = db.Column(db.String(150), nullable=True)  # required iff section == EXTERNAL
    operator = db.Column(db.String(150), nullable=True)  # required iff section == EXTERNAL

    # --- Audit Stage -----------------------------------------------------
    audit_stage = db.Column(
        db.Enum(*AuditStage.ALL, name="audit_stage"),
        nullable=False,
        default=AuditStage.AUDIT_PREPARATION,
    )
    stage_status = db.Column(
        db.Enum(*ActivityStatus.ALL, name="audit_stage_status"),
        nullable=False,
        default=ActivityStatus.OPEN,
    )
    stage_remarks = db.Column(db.Text, nullable=True)

    # Relationships
    activity = db.relationship("Activity", backref=db.backref("audit_detail", uselist=False))

    def __repr__(self):
        return f"<AuditDetail activity={self.activity_id} type={self.audit_type}>"
