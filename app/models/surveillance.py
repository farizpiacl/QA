from app.extensions import db
from app.models.mixins import TimestampMixin


class SurveillanceOption:
    REPORTING = "REPORTING"
    LIAISON = "LIAISON"

    CHOICES = [
        (REPORTING, "Reporting"),
        (LIAISON, "Liaison"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class SurveillanceDetail(TimestampMixin, db.Model):
    """Module 8: Activity Type 12 - Surveillance detail row."""

    __tablename__ = "surveillance_details"

    id = db.Column(db.Integer, primary_key=True)

    activity_id = db.Column(
        db.Integer,
        db.ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    option = db.Column(db.Enum(*SurveillanceOption.ALL, name="surveillance_option"), nullable=False)

    # Relationships
    activity = db.relationship("Activity", backref=db.backref("surveillance_detail", uselist=False))

    def __repr__(self):
        return f"<SurveillanceDetail activity={self.activity_id} option={self.option}>"
