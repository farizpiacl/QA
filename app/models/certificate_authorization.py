from app.extensions import db
from app.models.mixins import TimestampMixin


class CertificateAuthorizationOption:
    CONDUCT_ORAL_ASSESSMENT = "CONDUCT_ORAL_ASSESSMENT"
    COORDINATION = "COORDINATION"

    CHOICES = [
        (CONDUCT_ORAL_ASSESSMENT, "Conduct Oral Assessment"),
        (COORDINATION, "Coordination"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class CertificateAuthorizationDetail(TimestampMixin, db.Model):
    """Module 7: Activity Type 7 - Certification Authorization detail row."""

    __tablename__ = "certificate_authorization_details"

    id = db.Column(db.Integer, primary_key=True)

    activity_id = db.Column(
        db.Integer,
        db.ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    option = db.Column(
        db.Enum(*CertificateAuthorizationOption.ALL, name="certificate_authorization_option"),
        nullable=False,
    )

    # Relationships
    activity = db.relationship("Activity", backref=db.backref("certificate_authorization_detail", uselist=False))

    def __repr__(self):
        return f"<CertificateAuthorizationDetail activity={self.activity_id} option={self.option}>"
