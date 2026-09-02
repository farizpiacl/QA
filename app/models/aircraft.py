from app.extensions import db
from app.models.mixins import TimestampMixin


class Aircraft(TimestampMixin, db.Model):
    __tablename__ = "aircraft"

    id = db.Column(db.Integer, primary_key=True)
    registration = db.Column(db.String(20), nullable=False, unique=True, index=True)  # tail number
    type = db.Column(db.String(50), nullable=True)  # e.g. A320, B777
    airline_id = db.Column(
        db.Integer,
        db.ForeignKey("airlines.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    # Relationships
    airline = db.relationship("Airline", back_populates="aircraft")
    # NOTE: no direct FK from Activity -> Aircraft at the foundation level.
    # The parent `activities` table intentionally holds only common fields;
    # aircraft association belongs on the specialized per-activity-type
    # tables added in later modules (per spec: "Do not put every
    # activity-specific field into the main activities table").

    def __repr__(self):
        return f"<Aircraft {self.registration}>"
