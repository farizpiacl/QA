from app.extensions import db
from app.models.mixins import TimestampMixin


class Shift(TimestampMixin, db.Model):
    """
    Work shift definition (e.g. Morning, Night). Fully manageable later by
    Super Admin via CRUD UI — no shift values are hardcoded in application
    logic.
    """

    __tablename__ = "shifts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    start_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    # Relationships
    activities = db.relationship("Activity", back_populates="shift", lazy="dynamic")

    def __repr__(self):
        return f"<Shift {self.name}>"
