from app.extensions import db
from app.models.mixins import TimestampMixin


class OccurrenceReportType:
    INTERNAL = "INTERNAL"
    PCAA = "PCAA"
    THIRD_PARTY = "THIRD_PARTY"

    CHOICES = [
        (INTERNAL, "Internal"),
        (PCAA, "PCAA"),
        (THIRD_PARTY, "Third Party"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class OccurrenceCategory:
    FOD = "FOD"
    BIRD_HIT = "BIRD_HIT"
    OTHER = "OTHER"

    CHOICES = [
        (FOD, "FOD"),
        (BIRD_HIT, "Bird Hit"),
        (OTHER, "Other"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class OccurrenceDetail(TimestampMixin, db.Model):
    """Module 6: Activity Type 4 - Occurrence Reporting detail row."""

    __tablename__ = "occurrence_details"

    id = db.Column(db.Integer, primary_key=True)

    activity_id = db.Column(
        db.Integer,
        db.ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    report_type = db.Column(db.Enum(*OccurrenceReportType.ALL, name="occurrence_report_type"), nullable=False)
    category = db.Column(db.Enum(*OccurrenceCategory.ALL, name="occurrence_category"), nullable=False)

    # Relationships
    activity = db.relationship("Activity", backref=db.backref("occurrence_detail", uselist=False))

    def __repr__(self):
        return f"<OccurrenceDetail activity={self.activity_id} category={self.category}>"
