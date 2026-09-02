"""
Module 2 test suite: default super admin, login/logout, session handling,
role-based authorization, and station-scoped URL-tampering protection.

Run with:  pytest -v
"""

from app.models.station import Station
from tests.conftest import login


# --- Default Super Admin -----------------------------------------------------

def test_default_super_admin_created_on_init(app):
    from app.models.user import Role, User

    with app.app_context():
        pia = User.query.filter_by(username="PIA").first()
        assert pia is not None
        assert pia.role == Role.SUPER_ADMIN
        assert pia.check_password("QA@12345")
        # never plaintext
        assert pia.password_hash != "QA@12345"


def test_default_super_admin_not_recreated(app):
    from app.extensions import db
    from app.models.user import User
    from app.utils.init_data import create_default_super_admin

    with app.app_context():
        before_id = User.query.filter_by(username="PIA").first().id
        create_default_super_admin()  # call again
        after = User.query.filter_by(username="PIA").first()
        assert after.id == before_id
        assert User.query.filter_by(username="PIA").count() == 1


# --- Login / logout / sessions ----------------------------------------------

def test_login_each_role(client):
    for username in ("super", "ceqa", "dceqa_khi", "engineer"):
        resp = login(client, username)
        assert resp.status_code == 200
        assert b"Welcome" in resp.data
        client.get("/auth/logout", follow_redirects=True)


def test_invalid_login_rejected(client):
    resp = client.post(
        "/auth/login",
        data={"username": "super", "password": "wrong-password"},
        follow_redirects=True,
    )
    assert resp.status_code == 401
    assert b"Invalid username or password" in resp.data


def test_unknown_username_rejected(client):
    resp = client.post(
        "/auth/login",
        data={"username": "does-not-exist", "password": "whatever"},
        follow_redirects=True,
    )
    assert resp.status_code == 401


def test_inactive_user_cannot_login(client):
    resp = client.post(
        "/auth/login",
        data={"username": "inactive_eng", "password": "Password123!"},
        follow_redirects=True,
    )
    assert resp.status_code == 403
    assert b"deactivated" in resp.data


def test_logout_ends_session(client):
    login(client, "super")
    resp = client.get("/auth/logout", follow_redirects=True)
    assert resp.status_code == 200
    # After logout, protected page should redirect to login
    resp2 = client.get("/", follow_redirects=False)
    assert resp2.status_code in (301, 302)
    assert "/auth/login" in resp2.headers["Location"]


def test_unauthenticated_access_redirects_to_login(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/auth/login" in resp.headers["Location"]


# --- Role-based authorization -------------------------------------------------

def test_admin_panel_super_admin_only(client):
    login(client, "super")
    # Legacy /admin URL now redirects into the Module 3 admin dashboard.
    resp = client.get("/admin")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/admin/")
    assert client.get("/admin/").status_code == 200
    client.get("/auth/logout")

    for username in ("ceqa", "dceqa_khi", "engineer"):
        login(client, username)
        resp = client.get("/admin")
        assert resp.status_code == 403, f"{username} should be forbidden from /admin"
        resp2 = client.get("/admin/")
        assert resp2.status_code == 403, f"{username} should be forbidden from /admin/"
        client.get("/auth/logout")


def test_stations_list_super_admin_and_ceqa_only(client):
    for username in ("super", "ceqa"):
        login(client, username)
        assert client.get("/stations").status_code == 200
        client.get("/auth/logout")

    for username in ("dceqa_khi", "engineer"):
        login(client, username)
        resp = client.get("/stations")
        assert resp.status_code == 403
        client.get("/auth/logout")


def test_my_area_engineer_and_super_admin_only(client):
    for username in ("engineer", "super"):
        login(client, username)
        assert client.get("/my-area").status_code == 200
        client.get("/auth/logout")

    for username in ("ceqa", "dceqa_khi"):
        login(client, username)
        resp = client.get("/my-area")
        assert resp.status_code == 403
        client.get("/auth/logout")


# --- Critical: station-scoped URL tampering protection ------------------------

def test_dce_qa_cannot_view_another_stations_url(app, client):
    with app.app_context():
        khi_id = Station.query.filter_by(code="KHI").first().id
        lhe_id = Station.query.filter_by(code="LHE").first().id

    login(client, "dceqa_khi")

    # Own station: allowed
    resp_own = client.get(f"/stations/{khi_id}")
    assert resp_own.status_code == 200

    # Manually editing the URL to another station's id: must be 403,
    # not silently rendered.
    resp_other = client.get(f"/stations/{lhe_id}")
    assert resp_other.status_code == 403


def test_super_admin_and_ceqa_can_view_any_station(app, client):
    with app.app_context():
        khi_id = Station.query.filter_by(code="KHI").first().id
        lhe_id = Station.query.filter_by(code="LHE").first().id

    for username in ("super", "ceqa"):
        login(client, username)
        assert client.get(f"/stations/{khi_id}").status_code == 200
        assert client.get(f"/stations/{lhe_id}").status_code == 200
        client.get("/auth/logout")


def test_engineer_cannot_view_station_detail(app, client):
    with app.app_context():
        khi_id = Station.query.filter_by(code="KHI").first().id

    login(client, "engineer")
    resp = client.get(f"/stations/{khi_id}")
    assert resp.status_code == 403
