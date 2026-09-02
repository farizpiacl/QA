from app.extensions import db
from app.models.mixins import TimestampMixin


class Airline(TimestampMixin, db.Model):
    __tablename__ = "airlines"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), nullable=False, unique=True, index=True)  # e.g. IATA/ICAO code
    name = db.Column(db.String(150), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    # Relationships
    aircraft = db.relationship("Aircraft", back_populates="airline", lazy="dynamic")

    def __repr__(self):
        return f"<Airline {self.code}>"
