from app.extensions import db
from app.models.mixins import TimestampMixin


class SpotCheckType:
    """The 6 Spot Checks sub-flows (spec: "Types")."""

    AREAS = "AREAS"
    PREPARATION_FOLLOWUP = "PREPARATION_FOLLOWUP"
    VERIFICATION = "VERIFICATION"
    REPLY = "REPLY"
    CLOSING = "CLOSING"
    PCAA = "PCAA"

    CHOICES = [
        (AREAS, "Spot Checks Areas"),
        (PREPARATION_FOLLOWUP, "Spot Checks Preparation / Follow-up"),
        (VERIFICATION, "Spot Checks Verification"),
        (REPLY, "Spot Checks Reply"),
        (CLOSING, "Spot Checks Closing"),
        (PCAA, "PCAA"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}


class SpotCheckArea:
    """
    The 13 areas under the "Spot Checks Areas" type. Only relevant when
    `SpotCheckDetail.spot_check_type == SpotCheckType.AREAS`.
    """

    AIRCRAFT_SPOT_CHECKS = "AIRCRAFT_SPOT_CHECKS"
    AIRCRAFT_UNSCHEDULED_RANDOM = "AIRCRAFT_UNSCHEDULED_RANDOM"
    ATR_MAINTENANCE = "ATR_MAINTENANCE"
    A320_MAINTENANCE = "A320_MAINTENANCE"
    B777_MAINTENANCE = "B777_MAINTENANCE"
    PRODUCTION_DCE = "PRODUCTION_DCE"
    PRODUCTION_PLANNING = "PRODUCTION_PLANNING"
    TOOL_STORE = "TOOL_STORE"
    GROUND_EQUIPMENT = "GROUND_EQUIPMENT"
    CARDEX = "CARDEX"
    TECHNICAL_LIBRARY = "TECHNICAL_LIBRARY"
    TECHNICAL_STORE = "TECHNICAL_STORE"
    MISCELLANEOUS = "MISCELLANEOUS"

    CHOICES = [
        (AIRCRAFT_SPOT_CHECKS, "Aircraft Spot Checks"),
        (AIRCRAFT_UNSCHEDULED_RANDOM, "Aircraft Unscheduled / Random"),
        (ATR_MAINTENANCE, "ATR Maintenance Activity / Documentation"),
        (A320_MAINTENANCE, "A320 Maintenance Activity / Documentation"),
        (B777_MAINTENANCE, "B777 Maintenance Activity / Documentation"),
        (PRODUCTION_DCE, "Production DCE"),
        (PRODUCTION_PLANNING, "Production Planning"),
        (TOOL_STORE, "Tool Store"),
        (GROUND_EQUIPMENT, "Ground Equipment"),
        (CARDEX, "Cardex"),
        (TECHNICAL_LIBRARY, "Technical Library"),
        (TECHNICAL_STORE, "Technical Store"),
        (MISCELLANEOUS, "Miscellaneous"),
    ]

    ALL = [c[0] for c in CHOICES]
    LABELS = {code: label for code, label in CHOICES}

    # These 5 areas are the only ones that require Airline / Registration /
    # Flight No (spec: "Only these require Airline / Registration / Flight No").
    REQUIRES_AIRCRAFT_FIELDS = {
        AIRCRAFT_SPOT_CHECKS,
        AIRCRAFT_UNSCHEDULED_RANDOM,
        ATR_MAINTENANCE,
        A320_MAINTENANCE,
        B777_MAINTENANCE,
    }


class SpotCheckDetail(TimestampMixin, db.Model):
    """
    Module 6: Activity Type 2 - Spot Checks detail row.

    One-to-one with `activities`. `area` is only set when
    `spot_check_type == AREAS`. Airline/aircraft/flight are only set when
    required by the chosen type/area combination (see
    `app.utils.activity_details.validate_spot_check`), never guessed.
    """

    __tablename__ = "spot_check_details"

    id = db.Column(db.Integer, primary_key=True)

    activity_id = db.Column(
        db.Integer,
        db.ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    spot_check_type = db.Column(
        db.Enum(*SpotCheckType.ALL, name="spot_check_type"),
        nullable=False,
    )
    area = db.Column(
        db.Enum(*SpotCheckArea.ALL, name="spot_check_area"),
        nullable=True,
    )

    airline_id = db.Column(
        db.Integer, db.ForeignKey("airlines.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    aircraft_id = db.Column(
        db.Integer, db.ForeignKey("aircraft.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    flight_number = db.Column(db.String(20), nullable=True)

    email_done = db.Column(db.Boolean, nullable=False, default=False)
    qa_db_update_done = db.Column(db.Boolean, nullable=False, default=False)

    # Relationships
    activity = db.relationship("Activity", backref=db.backref("spot_check_detail", uselist=False))
    airline = db.relationship("Airline")
    aircraft = db.relationship("Aircraft")

    def __repr__(self):
        return f"<SpotCheckDetail activity={self.activity_id} type={self.spot_check_type}>"
