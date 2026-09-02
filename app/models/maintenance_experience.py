from app.extensions import db
from app.models.mixins import TimestampMixin


class MaintenanceExperienceOption:
    ASSESSMENT = "ASSESSMENT"
    SIGN_BY_QA_PERSONNEL = "SIGN_BY_QA_PERSONNEL"

    CHOICES = [
        (ASSESSMENT, "Assessment"),
        (SIGN_BY_QA_PERSONNEL, "Sign by QA Personnel"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class MaintenanceExperienceAction:
    """Action taken/decision recorded for this Maintenance Experience entry."""

    OK = "OK"
    RETURN = "RETURN"

    CHOICES = [
        (OK, "OK"),
        (RETURN, "Return"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class MaintenanceExperienceDetail(TimestampMixin, db.Model):
    """Module 7: Activity Type 9 - Maintenance Experience detail row."""

    __tablename__ = "maintenance_experience_details"

    id = db.Column(db.Integer, primary_key=True)

    activity_id = db.Column(
        db.Integer,
        db.ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    option = db.Column(
        db.Enum(*MaintenanceExperienceOption.ALL, name="maintenance_experience_option"),
        nullable=False,
    )
    name = db.Column(db.String(150), nullable=False)
    pno_cno = db.Column(db.String(50), nullable=False)
    action = db.Column(
        db.Enum(*MaintenanceExperienceAction.ALL, name="maintenance_experience_action"),
        nullable=False,
    )

    # Relationships
    activity = db.relationship("Activity", backref=db.backref("maintenance_experience_detail", uselist=False))

    def __repr__(self):
        return f"<MaintenanceExperienceDetail activity={self.activity_id} option={self.option}>"
