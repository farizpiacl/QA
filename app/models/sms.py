from app.extensions import db
from app.models.mixins import TimestampMixin


class SmsOption:
    REPORTING = "REPORTING"
    LIAISON = "LIAISON"

    CHOICES = [
        (REPORTING, "Reporting"),
        (LIAISON, "Liaison"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class SmsDetail(TimestampMixin, db.Model):
    """Module 8: Activity Type 13 - SMS detail row."""

    __tablename__ = "sms_details"

    id = db.Column(db.Integer, primary_key=True)

    activity_id = db.Column(
        db.Integer,
        db.ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    option = db.Column(db.Enum(*SmsOption.ALL, name="sms_option"), nullable=False)

    # Relationships
    activity = db.relationship("Activity", backref=db.backref("sms_detail", uselist=False))

    def __repr__(self):
        return f"<SmsDetail activity={self.activity_id} option={self.option}>"
