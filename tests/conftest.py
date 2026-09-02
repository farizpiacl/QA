import pytest

from app import create_app
from app.extensions import db
from app.models.station import Station
from app.models.user import Role, User


@pytest.fixture()
def app():
    app = create_app("testing")

    with app.app_context():
        db.create_all()

        # create_app() already tried this before the schema existed (and
        # safely no-op'd) - run it again now that tables are in place.
        from app.utils.init_data import create_default_super_admin

        create_default_super_admin()

        hq = Station(code="HQ", name="Headquarters", is_active=True)
        khi = Station(code="KHI", name="Karachi", is_active=True)
        lhe = Station(code="LHE", name="Lahore", is_active=True)
        db.session.add_all([hq, khi, lhe])
        db.session.flush()

        def make_user(username, role, station=None, is_active=True):
            u = User(
                full_name=username.title(),
                username=username,
                employee_no=f"EMP-{username}",
                role=role,
                station_id=station.id if station else None,
                is_active=is_active,
            )
            u.set_password("Password123!")
            db.session.add(u)
            return u

        make_user("super", Role.SUPER_ADMIN)
        make_user("ceqa", Role.CE_QA)
        make_user("dceqa_khi", Role.DCE_QA, station=khi)
        make_user("dceqa_lhe", Role.DCE_QA, station=lhe)
        make_user("engineer", Role.AIRCRAFT_ENGINEER, station=khi)
        make_user("inactive_eng", Role.AIRCRAFT_ENGINEER, station=khi, is_active=False)

        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, username, password="Password123!"):
    return client.post(
        "/auth/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )
