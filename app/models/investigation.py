from app.extensions import db
from app.models.mixins import TimestampMixin


class InvestigationType:
    MOR = "MOR"
    LOCAL_ISSUES = "LOCAL_ISSUES"
    OTHERS = "OTHERS"

    CHOICES = [
        (MOR, "MOR"),
        (LOCAL_ISSUES, "Local Issues"),
        (OTHERS, "Others"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class MorAircraftType:
    """Only relevant when `InvestigationDetail.investigation_type == InvestigationType.MOR`."""

    ATR = "ATR"
    A320 = "A320"
    A350 = "A350"
    B777 = "B777"
    B787 = "B787"
    OTHER = "OTHER"

    CHOICES = [
        (ATR, "ATR"),
        (A320, "A320"),
        (A350, "A350"),
        (B777, "B777"),
        (B787, "B787"),
        (OTHER, "Other"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class InvestigationDetail(TimestampMixin, db.Model):
    """
    Module 7: Activity Type 10 - Investigation detail row.

    `mor_aircraft_type` is only set (and only required) when
    `investigation_type == InvestigationType.MOR` - see
    `app.utils.activity_details.validate_investigation`, never guessed.
    """

    __tablename__ = "investigation_details"

    id = db.Column(db.Integer, primary_key=True)

    activity_id = db.Column(
        db.Integer,
        db.ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    investigation_type = db.Column(db.Enum(*InvestigationType.ALL, name="investigation_type"), nullable=False)
    mor_aircraft_type = db.Column(db.Enum(*MorAircraftType.ALL, name="mor_aircraft_type"), nullable=True)

    # Relationships
    activity = db.relationship("Activity", backref=db.backref("investigation_detail", uselist=False))

    def __repr__(self):
        return f"<InvestigationDetail activity={self.activity_id} type={self.investigation_type}>"
