from app.extensions import db
from app.models.mixins import TimestampMixin


class AmlApplicationType:
    QA_EXAM = "QA_EXAM"
    PCAA = "PCAA"

    CHOICES = [
        (QA_EXAM, "QA Exam"),
        (PCAA, "PCAA"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class AmlScreening:
    YES = "YES"
    NO = "NO"

    CHOICES = [
        (YES, "Yes"),
        (NO, "No"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class AmlOutcome:
    OK = "OK"
    RETURN = "RETURN"

    CHOICES = [
        (OK, "OK"),
        (RETURN, "Return"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class AmlApplicationDetail(TimestampMixin, db.Model):
    """
    Module 7: Activity Type 8 - AML Application detail row.

    Flow: Type (QA Exam/PCAA) -> Screening (Yes/No) -> Outcome (OK/Return),
    then the common Status/Remarks fields on the parent Activity close out
    the record. All three fields are always required regardless of the
    values chosen - there is no further branching within this type.
    """

    __tablename__ = "aml_application_details"

    id = db.Column(db.Integer, primary_key=True)

    activity_id = db.Column(
        db.Integer,
        db.ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    aml_type = db.Column(db.Enum(*AmlApplicationType.ALL, name="aml_application_type"), nullable=False)
    screening = db.Column(db.Enum(*AmlScreening.ALL, name="aml_screening"), nullable=False)
    outcome = db.Column(db.Enum(*AmlOutcome.ALL, name="aml_outcome"), nullable=False)

    # Relationships
    activity = db.relationship("Activity", backref=db.backref("aml_application_detail", uselist=False))

    def __repr__(self):
        return f"<AmlApplicationDetail activity={self.activity_id} type={self.aml_type} outcome={self.outcome}>"
