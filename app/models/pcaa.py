from app.extensions import db
from app.models.mixins import TimestampMixin


class PcaaOption:
    AMS = "AMS"
    LIAISON = "LIAISON"

    CHOICES = [
        (AMS, "AMS"),
        (LIAISON, "Liaison"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class PcaaDetail(TimestampMixin, db.Model):
    """Module 8: Activity Type 11 - PCAA detail row."""

    __tablename__ = "pcaa_details"

    id = db.Column(db.Integer, primary_key=True)

    activity_id = db.Column(
        db.Integer,
        db.ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    option = db.Column(db.Enum(*PcaaOption.ALL, name="pcaa_option"), nullable=False)

    # Relationships
    activity = db.relationship("Activity", backref=db.backref("pcaa_detail", uselist=False))

    def __repr__(self):
        return f"<PcaaDetail activity={self.activity_id} option={self.option}>"
