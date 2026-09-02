"""
Module 5: Dynamic Activity Engine tests.

Covers: selecting every activity type, correct conditional behavior,
required-field validation (client bypassed — we POST directly, which is
exactly the "never trust client-side validation alone" scenario), OPEN/
CLOSED status handling, and saving the parent Activity record.
"""

from datetime import date

import pytest

from app.extensions import db
from app.models.activity import Activity, ActivityStatus, ActivityType
from app.models.shift import Shift
from app.models.station import Station
from app.models.user import User

from tests.conftest import login


@pytest.fixture()
def shift(app):
    with app.app_context():
        s = Shift(name="Morning", is_active=True)
        db.session.add(s)
        db.session.commit()
        return s.id


def _base_payload(shift_id, station_id, activity_type=ActivityType.RAMP_INSPECTION):
    return {
        "activity_date": date.today().isoformat(),
        "shift_id": str(shift_id),
        "activity_type": activity_type,
        "station_id": str(station_id),
        "status": ActivityStatus.OPEN,
        "remarks": "Test remarks",
    }


class TestAddActivityPageRendersAllTypes:
    def test_get_add_activity_lists_all_14_types(self, client, app, shift):
        login(client, "engineer")
        resp = client.get("/activities/add")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        for code, label, _icon in ActivityType.CHOICES:
            assert code in body
            assert label in body
        assert len(ActivityType.CHOICES) == 14


class TestStationAutoFillAndScope:
    def test_engineer_station_is_locked_to_own_station(self, client, app, shift):
        login(client, "engineer")
        resp = client.get("/activities/add")
        body = resp.get_data(as_text=True)
        # Station select shouldn't be an editable dropdown for a
        # station-bound role.
        assert 'name="station_id"' in body
        assert "disabled readonly" in body

    def test_ceqa_cannot_add_activity(self, client, app, shift):
        """Only DCE_QA and AIRCRAFT_ENGINEER may add activities (per spec);
        CE_QA (Shift Incharge) is blocked server-side even via a direct
        GET, not just by hiding the nav link."""
        login(client, "ceqa")
        resp = client.get("/activities/add")
        assert resp.status_code == 403

    def test_engineer_cannot_submit_for_a_foreign_station(self, client, app, shift):
        login(client, "engineer")
        with app.app_context():
            other_station = Station.query.filter_by(code="LHE").first()
            payload = _base_payload(shift, other_station.id)

        resp = client.post("/activities/add", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "authorized" in body.lower()

        with app.app_context():
            assert Activity.query.count() == 0


class TestRequiredFieldValidation:
    def test_missing_date_is_rejected_server_side(self, client, app, shift):
        login(client, "engineer")
        with app.app_context():
            station_id = User.query.filter_by(username="engineer").first().station_id
        payload = _base_payload(shift, station_id)
        payload["activity_date"] = ""

        resp = client.post("/activities/add", data=payload)
        assert resp.status_code == 200  # re-rendered with errors, not redirected
        assert "Date is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0

    def test_missing_shift_is_rejected(self, client, app, shift):
        login(client, "engineer")
        with app.app_context():
            station_id = User.query.filter_by(username="engineer").first().station_id
        payload = _base_payload(shift, station_id)
        payload["shift_id"] = ""

        resp = client.post("/activities/add", data=payload)
        assert "Shift is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0

    def test_invalid_activity_type_is_rejected(self, client, app, shift):
        login(client, "engineer")
        with app.app_context():
            station_id = User.query.filter_by(username="engineer").first().station_id
        payload = _base_payload(shift, station_id)
        payload["activity_type"] = "NOT_A_REAL_TYPE"

        resp = client.post("/activities/add", data=payload)
        assert "valid activity type" in resp.get_data(as_text=True).lower()
        with app.app_context():
            assert Activity.query.count() == 0

    def test_missing_station_is_rejected(self, client, app, shift):
        login(client, "dceqa_khi")
        payload = _base_payload(shift, 999999)
        payload["station_id"] = ""

        resp = client.post("/activities/add", data=payload)
        assert "Station is required" in resp.get_data(as_text=True)

    def test_server_rejects_even_when_client_js_would_have_allowed_it(self, client, app, shift):
        """
        Simulates a hand-crafted POST bypassing all client-side JS (exactly
        what a disabled-JS browser or a scripted client would send) — the
        server must independently enforce every rule.
        """
        login(client, "engineer")
        resp = client.post("/activities/add", data={})
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "Date is required" in body
        assert "Shift is required" in body
        assert "Activity Type is required" in body
        with app.app_context():
            assert Activity.query.count() == 0


class TestSavingActivity:
    def test_selecting_every_activity_type_saves_correctly(self, client, app, shift):
        login(client, "engineer")
        with app.app_context():
            station_id = User.query.filter_by(username="engineer").first().station_id

        for code, _label, _icon in ActivityType.CHOICES:
            payload = _base_payload(shift, station_id, activity_type=code)
            resp = client.post("/activities/add", data=payload, follow_redirects=True)
            assert resp.status_code == 200

        with app.app_context():
            saved_types = {a.activity_type for a in Activity.query.all()}
            assert saved_types == set(ActivityType.ALL)

    def test_saved_activity_has_correct_common_fields(self, client, app, shift):
        login(client, "engineer")
        with app.app_context():
            engineer = User.query.filter_by(username="engineer").first()
            station_id = engineer.station_id
            engineer_id = engineer.id

        payload = _base_payload(shift, station_id)
        client.post("/activities/add", data=payload, follow_redirects=True)

        with app.app_context():
            activity = Activity.query.first()
            assert activity is not None
            assert activity.activity_type == ActivityType.RAMP_INSPECTION
            assert activity.station_id == station_id
            assert activity.created_by == engineer_id
            assert activity.status == ActivityStatus.OPEN
            assert activity.shift_id == shift
            assert activity.remarks == "Test remarks"

    def test_closed_status_is_saved_correctly(self, client, app, shift):
        login(client, "engineer")
        with app.app_context():
            station_id = User.query.filter_by(username="engineer").first().station_id
        payload = _base_payload(shift, station_id)
        payload["status"] = ActivityStatus.CLOSED

        client.post("/activities/add", data=payload, follow_redirects=True)

        with app.app_context():
            activity = Activity.query.first()
            assert activity.status == ActivityStatus.CLOSED

    def test_invalid_status_value_is_rejected(self, client, app, shift):
        login(client, "engineer")
        with app.app_context():
            station_id = User.query.filter_by(username="engineer").first().station_id
        payload = _base_payload(shift, station_id)
        payload["status"] = "BOGUS"

        resp = client.post("/activities/add", data=payload)
        assert "valid status" in resp.get_data(as_text=True).lower()
        with app.app_context():
            assert Activity.query.count() == 0


class TestAccessControl:
    def test_anonymous_user_redirected_to_login(self, client, app, shift):
        resp = client.get("/activities/add")
        assert resp.status_code in (302, 401)

    def test_super_admin_cannot_use_engineer_add_activity_route(self, client, app, shift):
        # SUPER_ADMIN isn't in the roles_required list for this route —
        # confirms authorization is enforced server-side, not just hidden
        # in the nav.
        login(client, "super")
        resp = client.get("/activities/add")
        assert resp.status_code == 403
