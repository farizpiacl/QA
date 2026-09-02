"""
Module 3 test suite: Super Admin dashboard shell, User/Station/Shift/
Airline/Aircraft CRUD, the protected Super-Admin-creation flow, and audit
logging of administrative actions.

Run with:  pytest -v
"""

from app.extensions import db
from app.models.user import User, Role
from app.models.station import Station
from app.models.shift import Shift
from app.models.airline import Airline
from app.models.aircraft import Aircraft
from app.models.audit_log import AuditLog
from tests.conftest import login


# --- Access control -----------------------------------------------------------

def test_admin_routes_require_super_admin(client):
    for username in ("ceqa", "dceqa_khi", "engineer"):
        login(client, username)
        for path in ("/admin/", "/admin/users", "/admin/stations", "/admin/shifts",
                     "/admin/airlines", "/admin/aircraft", "/admin/audit-logs"):
            resp = client.get(path)
            assert resp.status_code == 403, f"{username} should be forbidden from {path}"
        client.get("/auth/logout")


def test_admin_routes_require_login(client):
    for path in ("/admin/", "/admin/users"):
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]


def test_dashboard_loads_for_super_admin(client):
    login(client, "super")
    resp = client.get("/admin/")
    assert resp.status_code == 200
    assert b"Super Admin Dashboard" in resp.data


# --- User management -----------------------------------------------------------

def test_create_user(app, client):
    login(client, "super")
    with app.app_context():
        khi = Station.query.filter_by(code="KHI").first()
        station_id = khi.id

    resp = client.post(
        "/admin/users/new",
        data={
            "full_name": "New Engineer",
            "username": "new_eng",
            "employee_no": "EMP-NEW1",
            "designation": "AME",
            "role": Role.AIRCRAFT_ENGINEER,
            "station_id": str(station_id),
            "password": "Password123!",
            "is_active": "on",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"created successfully" in resp.data

    with app.app_context():
        u = User.query.filter_by(username="new_eng").first()
        assert u is not None
        assert u.check_password("Password123!")
        assert u.role == Role.AIRCRAFT_ENGINEER
        assert u.is_active is True

        log = AuditLog.query.filter_by(action="USER_CREATED", entity_id=u.id).first()
        assert log is not None


def test_create_user_cannot_assign_super_admin_role(client):
    """The normal create-user form only offers non-Super-Admin roles; even a
    hand-crafted POST attempting SUPER_ADMIN must be rejected."""
    login(client, "super")
    resp = client.post(
        "/admin/users/new",
        data={
            "full_name": "Sneaky",
            "username": "sneaky",
            "employee_no": "EMP-SNEAK",
            "role": Role.SUPER_ADMIN,
            "password": "Password123!",
        },
        follow_redirects=True,
    )
    assert b"A valid role is required" in resp.data


def test_create_user_duplicate_username_rejected(client):
    login(client, "super")
    resp = client.post(
        "/admin/users/new",
        data={
            "full_name": "Duplicate",
            "username": "engineer",  # already exists in conftest fixture
            "employee_no": "EMP-DUP1",
            "role": Role.AIRCRAFT_ENGINEER,
            "password": "Password123!",
        },
        follow_redirects=True,
    )
    assert b"already in use" in resp.data


def test_edit_user(app, client):
    login(client, "super")
    with app.app_context():
        u = User.query.filter_by(username="engineer").first()
        uid = u.id

    resp = client.post(
        f"/admin/users/{uid}/edit",
        data={
            "full_name": "Engineer Updated",
            "username": "engineer",
            "employee_no": "EMP-engineer",
            "designation": "Senior AME",
            "role": Role.AIRCRAFT_ENGINEER,
            "station_id": "",
            "is_active": "on",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"updated" in resp.data

    with app.app_context():
        u = db.session.get(User, uid)
        assert u.full_name == "Engineer Updated"
        assert u.designation == "Senior AME"
        log = AuditLog.query.filter_by(action="USER_EDITED", entity_id=uid).first()
        assert log is not None


def test_activate_deactivate_user(app, client):
    login(client, "super")
    with app.app_context():
        u = User.query.filter_by(username="engineer").first()
        uid = u.id
        assert u.is_active is True

    resp = client.post(f"/admin/users/{uid}/deactivate", follow_redirects=True)
    assert b"deactivated" in resp.data
    with app.app_context():
        assert db.session.get(User, uid).is_active is False
        assert AuditLog.query.filter_by(action="USER_DEACTIVATED", entity_id=uid).first() is not None

    resp = client.post(f"/admin/users/{uid}/activate", follow_redirects=True)
    assert b"activated" in resp.data
    with app.app_context():
        assert db.session.get(User, uid).is_active is True
        assert AuditLog.query.filter_by(action="USER_ACTIVATED", entity_id=uid).first() is not None


def test_cannot_deactivate_own_account(app, client):
    login(client, "super")
    with app.app_context():
        me = User.query.filter_by(username="super").first()
        my_id = me.id

    resp = client.post(f"/admin/users/{my_id}/deactivate", follow_redirects=True)
    assert b"cannot deactivate your own account" in resp.data
    with app.app_context():
        assert db.session.get(User, my_id).is_active is True


def test_reset_password(app, client):
    login(client, "super")
    with app.app_context():
        u = User.query.filter_by(username="engineer").first()
        uid = u.id

    resp = client.post(
        f"/admin/users/{uid}/reset-password",
        data={"password": "BrandNewPass1", "confirm_password": "BrandNewPass1"},
        follow_redirects=True,
    )
    assert b"Password reset" in resp.data

    with app.app_context():
        u = db.session.get(User, uid)
        assert u.check_password("BrandNewPass1")
        assert AuditLog.query.filter_by(action="PASSWORD_RESET", entity_id=uid).first() is not None


def test_reset_password_mismatch_rejected(app, client):
    login(client, "super")
    with app.app_context():
        uid = User.query.filter_by(username="engineer").first().id

    resp = client.post(
        f"/admin/users/{uid}/reset-password",
        data={"password": "abcdefgh", "confirm_password": "different"},
        follow_redirects=True,
    )
    assert b"do not match" in resp.data


# --- Protected Super Admin creation --------------------------------------------

def test_create_super_admin_requires_password_confirmation(client):
    login(client, "super")
    resp = client.post(
        "/admin/users/create-super-admin",
        data={
            "full_name": "Second Admin",
            "username": "second_admin",
            "employee_no": "EMP-SA2",
            "password": "Password123!",
            "confirming_password": "wrong-password",
        },
        follow_redirects=True,
    )
    assert b"was not confirmed" in resp.data

    with client.application.app_context():
        assert User.query.filter_by(username="second_admin").first() is None


def test_create_super_admin_succeeds_with_correct_confirmation(app, client):
    login(client, "super")
    resp = client.post(
        "/admin/users/create-super-admin",
        data={
            "full_name": "Second Admin",
            "username": "second_admin",
            "employee_no": "EMP-SA2",
            "password": "Password123!",
            "confirming_password": "Password123!",  # matches "super" fixture password
        },
        follow_redirects=True,
    )
    assert b"created successfully" in resp.data

    with app.app_context():
        u = User.query.filter_by(username="second_admin").first()
        assert u is not None
        assert u.role == Role.SUPER_ADMIN
        log = AuditLog.query.filter_by(action="USER_CREATED", entity_id=u.id).first()
        assert log is not None
        assert "SUPER_ADMIN" in log.details


# --- Station management ---------------------------------------------------------

def test_station_crud_and_toggle(app, client):
    login(client, "super")

    resp = client.post(
        "/admin/stations/new",
        data={"code": "isb", "name": "Islamabad", "is_active": "on"},
        follow_redirects=True,
    )
    assert b"created" in resp.data

    with app.app_context():
        station = Station.query.filter_by(code="ISB").first()
        assert station is not None
        sid = station.id
        assert AuditLog.query.filter_by(action="STATION_CREATED", entity_id=sid).first() is not None

    resp = client.post(
        f"/admin/stations/{sid}/edit",
        data={"code": "ISB", "name": "Islamabad Intl", "is_active": "on"},
        follow_redirects=True,
    )
    assert b"updated" in resp.data
    with app.app_context():
        assert db.session.get(Station, sid).name == "Islamabad Intl"

    resp = client.post(f"/admin/stations/{sid}/toggle-active", follow_redirects=True)
    assert b"inactive" in resp.data
    with app.app_context():
        assert db.session.get(Station, sid).is_active is False
        assert AuditLog.query.filter_by(action="STATION_DEACTIVATED", entity_id=sid).first() is not None


def test_station_duplicate_code_rejected(client):
    login(client, "super")
    resp = client.post(
        "/admin/stations/new",
        data={"code": "HQ", "name": "Duplicate HQ", "is_active": "on"},
        follow_redirects=True,
    )
    assert b"already exists" in resp.data


# --- Shift management ------------------------------------------------------------

def test_shift_crud_and_toggle(app, client):
    login(client, "super")

    resp = client.post(
        "/admin/shifts/new",
        data={"name": "Night", "start_time": "22:00", "end_time": "06:00", "is_active": "on"},
        follow_redirects=True,
    )
    assert b"created" in resp.data

    with app.app_context():
        shift = Shift.query.filter_by(name="Night").first()
        assert shift is not None
        shift_id = shift.id
        assert AuditLog.query.filter_by(action="SHIFT_CREATED", entity_id=shift_id).first() is not None

    resp = client.post(f"/admin/shifts/{shift_id}/toggle-active", follow_redirects=True)
    assert b"inactive" in resp.data
    with app.app_context():
        assert db.session.get(Shift, shift_id).is_active is False


# --- Airline management -----------------------------------------------------------

def test_airline_crud_and_toggle(app, client):
    login(client, "super")

    resp = client.post(
        "/admin/airlines/new",
        data={"code": "pk", "name": "Pakistan International Airlines", "is_active": "on"},
        follow_redirects=True,
    )
    assert b"created" in resp.data

    with app.app_context():
        airline = Airline.query.filter_by(code="PK").first()
        assert airline is not None
        aid = airline.id
        assert AuditLog.query.filter_by(action="AIRLINE_CREATED", entity_id=aid).first() is not None

    resp = client.post(f"/admin/airlines/{aid}/toggle-active", follow_redirects=True)
    assert b"inactive" in resp.data


# --- Aircraft management -----------------------------------------------------------

def test_aircraft_crud_uses_db_airline_list(app, client):
    login(client, "super")

    client.post(
        "/admin/airlines/new",
        data={"code": "pk", "name": "Pakistan International Airlines", "is_active": "on"},
        follow_redirects=True,
    )

    # Airline options on the form must come from the DB, not a hardcoded list.
    resp = client.get("/admin/aircraft/new")
    assert b"PK" in resp.data

    with app.app_context():
        airline_id = Airline.query.filter_by(code="PK").first().id

    resp = client.post(
        "/admin/aircraft/new",
        data={"airline_id": str(airline_id), "registration": "ap-bcd", "type": "A320", "is_active": "on"},
        follow_redirects=True,
    )
    assert b"created" in resp.data

    with app.app_context():
        ac = Aircraft.query.filter_by(registration="AP-BCD").first()
        assert ac is not None
        assert ac.airline_id == airline_id
        acid = ac.id
        assert AuditLog.query.filter_by(action="AIRCRAFT_CREATED", entity_id=acid).first() is not None

    resp = client.post(f"/admin/aircraft/{acid}/toggle-active", follow_redirects=True)
    assert b"inactive" in resp.data
    with app.app_context():
        assert db.session.get(Aircraft, acid).is_active is False


def test_aircraft_duplicate_registration_rejected(app, client):
    login(client, "super")
    client.post(
        "/admin/aircraft/new",
        data={"registration": "AP-XYZ", "type": "B777", "is_active": "on"},
        follow_redirects=True,
    )
    resp = client.post(
        "/admin/aircraft/new",
        data={"registration": "AP-XYZ", "type": "B777", "is_active": "on"},
        follow_redirects=True,
    )
    assert b"already exists" in resp.data


# --- Audit log viewer -----------------------------------------------------------

def test_audit_log_records_and_filters(app, client):
    login(client, "super")
    client.post(
        "/admin/stations/new",
        data={"code": "lyp", "name": "Faisalabad", "is_active": "on"},
        follow_redirects=True,
    )

    resp = client.get("/admin/audit-logs")
    assert resp.status_code == 200
    assert b"STATION_CREATED" in resp.data

    resp = client.get("/admin/audit-logs?action=STATION_CREATED")
    assert resp.status_code == 200
    assert b"STATION_CREATED" in resp.data


# --- Administration hub (combines Users/Stations/Shifts/Airlines/Aircraft/Audit) --

def test_administration_hub_links_to_every_admin_section(client):
    login(client, "super")
    resp = client.get("/admin/administration")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    for path in ("/admin/users", "/admin/stations", "/admin/shifts",
                 "/admin/airlines", "/admin/aircraft", "/admin/audit-logs"):
        assert path in body


def test_administration_hub_requires_super_admin(client):
    for username in ("ceqa", "dceqa_khi", "engineer"):
        login(client, username)
        resp = client.get("/admin/administration")
        assert resp.status_code == 403
        client.get("/auth/logout")
