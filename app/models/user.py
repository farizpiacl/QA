from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models.mixins import TimestampMixin


class Role:
    """
    Role constants. Kept as plain string constants (backed by a DB Enum
    column) rather than a separate lookup table, since the role set is
    fixed by the business requirement and referenced directly by
    authorization decorators throughout the app.
    """

    SUPER_ADMIN = "SUPER_ADMIN"
    CE_QA = "CE_QA"
    DCE_QA = "DCE_QA"
    AIRCRAFT_ENGINEER = "AIRCRAFT_ENGINEER"

    ALL = [SUPER_ADMIN, CE_QA, DCE_QA, AIRCRAFT_ENGINEER]


class User(TimestampMixin, UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(db.String(150), nullable=False)
    username = db.Column(db.String(80), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # Employee / PNO / CNO identifier
    employee_no = db.Column(db.String(50), nullable=False, unique=True, index=True)

    role = db.Column(
        db.Enum(*Role.ALL, name="user_role"),
        nullable=False,
        default=Role.AIRCRAFT_ENGINEER,
        index=True,
    )
    designation = db.Column(db.String(100), nullable=True)

    station_id = db.Column(
        db.Integer,
        db.ForeignKey("stations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # NOTE: this column also satisfies Flask-Login's UserMixin.is_active
    # contract (UserMixin's default is a property returning True; declaring
    # a real Column of the same name here takes precedence, so deactivated
    # users are correctly prevented from maintaining an authenticated
    # session).
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    # Forces the password-change flow on next login (used for the default
    # bootstrap Super Admin account so the known default password can never
    # remain active). Regular users created via the admin UI are unaffected
    # (defaults to False).
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)

    # Relationships
    station = db.relationship("Station", back_populates="users")
    created_activities = db.relationship(
        "Activity",
        foreign_keys="Activity.created_by",
        back_populates="creator",
        lazy="dynamic",
    )
    updated_activities = db.relationship(
        "Activity",
        foreign_keys="Activity.updated_by",
        back_populates="updater",
        lazy="dynamic",
    )
    audit_logs = db.relationship("AuditLog", back_populates="user", lazy="dynamic")

    def __repr__(self):
        return f"<User {self.username}>"

    # --- Password helpers ---------------------------------------------------
    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    # --- Role helpers ---------------------------------------------------------
    def has_role(self, *roles) -> bool:
        return self.role in roles

    @property
    def is_super_admin(self) -> bool:
        return self.role == Role.SUPER_ADMIN
