from app.extensions import db
from app.models.mixins import TimestampMixin


class RampInspectionOption:
    """
    The four Ramp Inspection sub-types (spec: "Options"). Every option
    requires the exact same field set (Airline / Aircraft Reg / Flight No /
    Email Done / QA Database Update Done, plus the common Status + Remarks
    already on the parent Activity) - only the option itself differs, so no
    per-option conditional fields are needed here.
    """

    AS_PER_ANNUAL_PLAN = "AS_PER_ANNUAL_PLAN"
    EU_SAFA_BOUND_FLIGHT = "EU_SAFA_BOUND_FLIGHT"
    VERIFICATION_OF_PREVIOUS_FINDINGS = "VERIFICATION_OF_PREVIOUS_FINDINGS"
    PCAA_RAMP_INSPECTION = "PCAA_RAMP_INSPECTION"

    CHOICES = [
        (AS_PER_ANNUAL_PLAN, "As per Annual Plan"),
        (EU_SAFA_BOUND_FLIGHT, "EU SAFA Bound Flight"),
        (VERIFICATION_OF_PREVIOUS_FINDINGS, "Verification of Previous Findings"),
        (PCAA_RAMP_INSPECTION, "PCAA Ramp Inspection"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class RampInspectionDetail(TimestampMixin, db.Model):
    """
    Module 6: Activity Type 1 - Ramp Inspection detail row.

    One-to-one with `activities` (activity_id is unique). Status/Remarks are
    intentionally NOT duplicated here - they already exist on the parent
    Activity row and that's the single source of truth for them.
    """

    __tablename__ = "ramp_inspection_details"

    id = db.Column(db.Integer, primary_key=True)

    activity_id = db.Column(
        db.Integer,
        db.ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    option = db.Column(
        db.Enum(*RampInspectionOption.ALL, name="ramp_inspection_option"),
        nullable=False,
    )

    airline_id = db.Column(
        db.Integer, db.ForeignKey("airlines.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    aircraft_id = db.Column(
        db.Integer, db.ForeignKey("aircraft.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    flight_number = db.Column(db.String(20), nullable=False)

    email_done = db.Column(db.Boolean, nullable=False, default=False)
    qa_db_update_done = db.Column(db.Boolean, nullable=False, default=False)

    # Relationships
    activity = db.relationship("Activity", backref=db.backref("ramp_inspection_detail", uselist=False))
    airline = db.relationship("Airline")
    aircraft = db.relationship("Aircraft")

    def __repr__(self):
        return f"<RampInspectionDetail activity={self.activity_id} option={self.option}>"
