"""
One-time / idempotent seed script for local & first-deploy setup.

Usage:
    python seed.py

Creates (only if missing):
  - a default station (HQ)
  - a default shift (General)
  - a SUPER_ADMIN user (username: admin / password: ChangeMe123!)

Safe to re-run: every insert is guarded by an existence check, so it never
duplicates or destroys existing data.
"""

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.extensions import db
from app.models.station import Station
from app.models.shift import Shift
from app.models.user import User, Role
from app.utils.init_data import create_default_super_admin


def run():
    # create_app() already triggers create_default_super_admin() internally
    # (it runs automatically on every app start per spec), but importing it
    # explicitly here too keeps `python seed.py` self-documenting and safe
    # to run standalone against a freshly-migrated database.
    app = create_app()
    with app.app_context():
        create_default_super_admin()
        station = Station.query.filter_by(code="HQ").first()
        if station is None:
            station = Station(code="HQ", name="Headquarters", is_active=True)
            db.session.add(station)
            print("Created station: HQ")

        shift = Shift.query.filter_by(name="General").first()
        if shift is None:
            shift = Shift(name="General", is_active=True)
            db.session.add(shift)
            print("Created shift: General")

        db.session.flush()

        admin = User.query.filter_by(username="admin").first()
        if admin is None:
            admin = User(
                full_name="System Administrator",
                username="admin",
                employee_no="ADMIN-0001",
                role=Role.SUPER_ADMIN,
                designation="Super Administrator",
                station_id=station.id,
                is_active=True,
            )
            admin.set_password("ChangeMe123!")
            db.session.add(admin)
            print("Created user: admin / ChangeMe123! (CHANGE THIS PASSWORD)")
        else:
            print("Admin user already exists — skipped.")

        db.session.commit()
        print("Seed complete.")


if __name__ == "__main__":
    run()
