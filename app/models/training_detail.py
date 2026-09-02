from app.extensions import db
from app.models.mixins import TimestampMixin


class TrainingMode:
    CONDUCT = "CONDUCT"
    ATTEND = "ATTEND"

    CHOICES = [
        (CONDUCT, "Conduct"),
        (ATTEND, "Attend"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class TrainingKind:
    """
    The training kind offered under Conduct/Attend. `TYPES` is only a valid
    choice under Attend (spec lists Conduct -> Continuation/Recurrent only;
    Attend -> Continuation/Recurrent/Types).
    """

    CONTINUATION_TRAINING = "CONTINUATION_TRAINING"
    RECURRENT_TRAINING = "RECURRENT_TRAINING"
    TYPES = "TYPES"

    CHOICES = [
        (CONTINUATION_TRAINING, "Continuation Training"),
        (RECURRENT_TRAINING, "Recurrent Training"),
        (TYPES, "Types"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}

    # Allowed kinds per mode.
    ALLOWED_FOR_CONDUCT = {CONTINUATION_TRAINING, RECURRENT_TRAINING}
    ALLOWED_FOR_ATTEND = {CONTINUATION_TRAINING, RECURRENT_TRAINING, TYPES}


class TrainingDetail(TimestampMixin, db.Model):
    """Module 6: Activity Type 5 - Training detail row."""

    __tablename__ = "training_details"

    id = db.Column(db.Integer, primary_key=True)

    activity_id = db.Column(
        db.Integer,
        db.ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    mode = db.Column(db.Enum(*TrainingMode.ALL, name="training_mode"), nullable=False)
    kind = db.Column(db.Enum(*TrainingKind.ALL, name="training_kind"), nullable=False)

    # Relationships
    activity = db.relationship("Activity", backref=db.backref("training_detail", uselist=False))

    def __repr__(self):
        return f"<TrainingDetail activity={self.activity_id} mode={self.mode} kind={self.kind}>"
