from app.extensions import db
from app.models.mixins import TimestampMixin


class Station(TimestampMixin, db.Model):
    """
    Physical/operational station (e.g. an airport station code).

    Station authorization for users/activities is data-driven via the
    station_id foreign keys elsewhere — never hardcode station codes in
    route logic.
    """

    __tablename__ = "stations"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), nullable=False, unique=True, index=True)
    name = db.Column(db.String(150), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    # Relationships
    users = db.relationship("User", back_populates="station", lazy="dynamic")
    activities = db.relationship("Activity", back_populates="station", lazy="dynamic")

    def __repr__(self):
        return f"<Station {self.code}>"
