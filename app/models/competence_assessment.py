from app.extensions import db
from app.models.mixins import TimestampMixin


class PersonnelType:
    QA_PERSONNEL = "QA_PERSONNEL"
    MAINTENANCE_PERSONNEL = "MAINTENANCE_PERSONNEL"

    CHOICES = [
        (QA_PERSONNEL, "QA Personnel"),
        (MAINTENANCE_PERSONNEL, "Maintenance Personnel"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class CompetenceAssessmentDetail(TimestampMixin, db.Model):
    """Module 7: Activity Type 6 - Competence Assessment of Personnel detail row."""

    __tablename__ = "competence_assessment_details"

    id = db.Column(db.Integer, primary_key=True)

    activity_id = db.Column(
        db.Integer,
        db.ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    personnel_type = db.Column(db.Enum(*PersonnelType.ALL, name="competence_personnel_type"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    pno_cno = db.Column(db.String(50), nullable=False)

    # Relationships
    activity = db.relationship("Activity", backref=db.backref("competence_assessment_detail", uselist=False))

    def __repr__(self):
        return f"<CompetenceAssessmentDetail activity={self.activity_id} type={self.personnel_type}>"
