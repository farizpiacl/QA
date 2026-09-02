from app.extensions import db
from app.models.mixins import TimestampMixin


class OfficeActivityOption:
    TNA = "TNA"
    MHP = "MHP"
    HRT = "HRT"
    IT = "IT"
    WORKS = "WORKS"
    OTHERS = "OTHERS"
    MISCELLANEOUS = "MISCELLANEOUS"

    CHOICES = [
        (TNA, "TNA"),
        (MHP, "MHP"),
        (HRT, "HRT"),
        (IT, "IT"),
        (WORKS, "Works"),
        (OTHERS, "Others"),
        (MISCELLANEOUS, "Miscellaneous"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class OfficeActivityDetail(TimestampMixin, db.Model):
    """Module 8: Activity Type 14 - Office Activity detail row."""

    __tablename__ = "office_activity_details"

    id = db.Column(db.Integer, primary_key=True)

    activity_id = db.Column(
        db.Integer,
        db.ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    option = db.Column(db.Enum(*OfficeActivityOption.ALL, name="office_activity_option"), nullable=False)

    # Relationships
    activity = db.relationship("Activity", backref=db.backref("office_activity_detail", uselist=False))

    def __repr__(self):
        return f"<OfficeActivityDetail activity={self.activity_id} option={self.option}>"
