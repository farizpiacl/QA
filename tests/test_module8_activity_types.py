"""
Module 8: Activity Types 11-14 (PCAA, Surveillance, SMS, Office Activity)
tests, plus the Delete capability that completes the Activity system.

Mirrors the structure of test_module7_activity_types.py.
"""

from datetime import date

import pytest

from app.extensions import db
from app.models.activity import Activity, ActivityStatus, ActivityType
from app.models.audit_log import AuditLog
from app.models.shift import Shift
from app.models.station import Station
from app.models.user import User

from app.models.pcaa import PcaaDetail, PcaaOption
from app.models.surveillance import SurveillanceDetail, SurveillanceOption
from app.models.sms import SmsDetail, SmsOption
from app.models.office_activity import OfficeActivityDetail, OfficeActivityOption

from tests.conftest import login


@pytest.fixture()
def shift(app):
    with app.app_context():
        s = Shift(name="Morning", is_active=True)
        db.session.add(s)
        db.session.commit()
        return s.id


def _common(shift_id, station_id, status=ActivityStatus.OPEN, remarks="notes"):
    return {
        "activity_date": date.today().isoformat(),
        "shift_id": str(shift_id),
        "station_id": str(station_id),
        "status": status,
        "remarks": remarks,
    }


def _engineer_station(app):
    with app.app_context():
        return User.query.filter_by(username="engineer").first().station_id


# ===========================================================================
# 11. PCAA
# ===========================================================================

class TestPcaa:
    def test_ams_option_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"option": PcaaOption.AMS})

        resp = client.post("/activities/add/pcaa", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.PCAA).first()
            assert activity is not None
            detail = PcaaDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.option == PcaaOption.AMS

            log = AuditLog.query.filter_by(entity_type="Activity", entity_id=activity.id, action="CREATE").first()
            assert log is not None

    def test_liaison_option_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"option": PcaaOption.LIAISON})

        resp = client.post("/activities/add/pcaa", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.PCAA).first()
            detail = PcaaDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.option == PcaaOption.LIAISON

    def test_missing_option_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)

        resp = client.post("/activities/add/pcaa", data=payload)
        assert "Option is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0

    def test_invalid_option_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"option": "NOT_A_REAL_OPTION"})

        resp = client.post("/activities/add/pcaa", data=payload)
        assert "valid option" in resp.get_data(as_text=True).lower()
        with app.app_context():
            assert Activity.query.count() == 0


# ===========================================================================
# 12. SURVEILLANCE
# ===========================================================================

class TestSurveillance:
    def test_reporting_option_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"option": SurveillanceOption.REPORTING})

        resp = client.post("/activities/add/surveillance", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.SURVEILLANCE).first()
            detail = SurveillanceDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.option == SurveillanceOption.REPORTING

    def test_liaison_option_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"option": SurveillanceOption.LIAISON})

        resp = client.post("/activities/add/surveillance", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.SURVEILLANCE).first()
            detail = SurveillanceDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.option == SurveillanceOption.LIAISON

    def test_missing_option_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)

        resp = client.post("/activities/add/surveillance", data=payload)
        assert "Option is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0


# ===========================================================================
# 13. SMS
# ===========================================================================

class TestSms:
    def test_reporting_option_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"option": SmsOption.REPORTING})

        resp = client.post("/activities/add/sms", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.SMS).first()
            detail = SmsDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.option == SmsOption.REPORTING

    def test_liaison_option_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"option": SmsOption.LIAISON})

        resp = client.post("/activities/add/sms", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.SMS).first()
            detail = SmsDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.option == SmsOption.LIAISON

    def test_missing_option_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)

        resp = client.post("/activities/add/sms", data=payload)
        assert "Option is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0


# ===========================================================================
# 14. OFFICE ACTIVITY
# ===========================================================================

class TestOfficeActivity:
    @pytest.mark.parametrize("option", [
        OfficeActivityOption.TNA, OfficeActivityOption.MHP, OfficeActivityOption.HRT,
        OfficeActivityOption.IT, OfficeActivityOption.WORKS, OfficeActivityOption.OTHERS,
        OfficeActivityOption.MISCELLANEOUS,
    ])
    def test_each_option_saves(self, client, app, shift, option):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"option": option})

        resp = client.post("/activities/add/office-activity", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.OFFICE_ACTIVITY).order_by(
                Activity.id.desc()
            ).first()
            detail = OfficeActivityDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.option == option

    def test_missing_option_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)

        resp = client.post("/activities/add/office-activity", data=payload)
        assert "Option is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0

    def test_invalid_option_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"option": "NOT_A_REAL_OPTION"})

        resp = client.post("/activities/add/office-activity", data=payload)
        assert "valid option" in resp.get_data(as_text=True).lower()
        with app.app_context():
            assert Activity.query.count() == 0


# ===========================================================================
# View Details
# ===========================================================================

class TestViewDetailsModule8:
    def test_view_renders_pcaa_option(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"option": PcaaOption.AMS})
        client.post("/activities/add/pcaa", data=payload, follow_redirects=True)
        with app.app_context():
            activity_id = Activity.query.filter_by(activity_type=ActivityType.PCAA).first().id

        resp = client.get(f"/activities/{activity_id}")
        assert resp.status_code == 200
        assert "AMS" in resp.get_data(as_text=True)

    def test_view_renders_office_activity_option(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"option": OfficeActivityOption.IT})
        client.post("/activities/add/office-activity", data=payload, follow_redirects=True)
        with app.app_context():
            activity_id = Activity.query.filter_by(activity_type=ActivityType.OFFICE_ACTIVITY).first().id

        resp = client.get(f"/activities/{activity_id}")
        assert resp.status_code == 200
        assert "IT" in resp.get_data(as_text=True)


# ===========================================================================
# Edit permissions + audit log
# ===========================================================================

class TestEditPermissionsModule8:
    def _create_open_pcaa(self, client, app, shift, station_id):
        payload = _common(shift, station_id)
        payload.update({"option": PcaaOption.AMS})
        client.post("/activities/add/pcaa", data=payload, follow_redirects=True)
        with app.app_context():
            return Activity.query.filter_by(activity_type=ActivityType.PCAA).first().id

    def test_creator_can_edit_while_open(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        activity_id = self._create_open_pcaa(client, app, shift, station_id)

        resp = client.get(f"/activities/{activity_id}/edit")
        assert resp.status_code == 200

        payload = _common(shift, station_id, remarks="updated remarks")
        payload.update({"option": PcaaOption.LIAISON})
        resp = client.post(f"/activities/{activity_id}/edit", data=payload, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            activity = db.session.get(Activity, activity_id)
            assert activity.remarks == "updated remarks"
            detail = PcaaDetail.query.filter_by(activity_id=activity_id).first()
            assert detail.option == PcaaOption.LIAISON

            update_log = AuditLog.query.filter_by(
                entity_type="Activity", entity_id=activity_id, action="UPDATE"
            ).first()
            assert update_log is not None

    def test_engineer_cannot_edit_after_activity_is_closed(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        activity_id = self._create_open_pcaa(client, app, shift, station_id)

        with app.app_context():
            activity = db.session.get(Activity, activity_id)
            activity.status = ActivityStatus.CLOSED
            db.session.commit()

        resp = client.get(f"/activities/{activity_id}/edit")
        assert resp.status_code == 403

    def test_status_change_writes_a_status_change_log_entry(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        activity_id = self._create_open_pcaa(client, app, shift, station_id)

        payload = _common(shift, station_id, status=ActivityStatus.CLOSED)
        payload.update({"option": PcaaOption.AMS})
        client.post(f"/activities/{activity_id}/edit", data=payload, follow_redirects=True)

        with app.app_context():
            log = AuditLog.query.filter_by(
                entity_type="Activity", entity_id=activity_id, action="STATUS_CHANGE"
            ).first()
            assert log is not None
            assert "OPEN" in log.details and "CLOSED" in log.details


# ===========================================================================
# Delete permissions + audit log
# ===========================================================================

class TestDeletePermissions:
    def _create_open_pcaa(self, client, app, shift, station_id):
        payload = _common(shift, station_id)
        payload.update({"option": PcaaOption.AMS})
        client.post("/activities/add/pcaa", data=payload, follow_redirects=True)
        with app.app_context():
            return Activity.query.filter_by(activity_type=ActivityType.PCAA).first().id

    def test_engineer_can_never_delete_their_own_activity(self, client, app, shift):
        """Per spec, engineers can never delete activities - not even their
        own, and not even while still OPEN."""
        login(client, "engineer")
        station_id = _engineer_station(app)
        activity_id = self._create_open_pcaa(client, app, shift, station_id)

        resp = client.post(f"/activities/{activity_id}/delete")
        assert resp.status_code == 403
        with app.app_context():
            assert db.session.get(Activity, activity_id) is not None

    def test_engineer_cannot_delete_someone_elses_activity(self, client, app, shift):
        """Ownership rule: an engineer may delete only activities they
        themselves created - never another user's, even one they can see
        (e.g. via the shared OPEN pool)."""
        login(client, "dceqa_khi")
        station_id = _engineer_station(app)
        activity_id = self._create_open_pcaa(client, app, shift, station_id)
        client.get("/auth/logout")

        login(client, "engineer")
        resp = client.post(f"/activities/{activity_id}/delete")
        assert resp.status_code == 403
        with app.app_context():
            assert db.session.get(Activity, activity_id) is not None

    def test_engineer_cannot_delete_their_own_closed_activity(self, client, app, shift):
        """Mirrors the edit rule: once CLOSED, even the creating engineer
        can no longer delete their own record."""
        login(client, "engineer")
        station_id = _engineer_station(app)
        activity_id = self._create_open_pcaa(client, app, shift, station_id)
        with app.app_context():
            activity = db.session.get(Activity, activity_id)
            activity.status = ActivityStatus.CLOSED
            db.session.commit()

        resp = client.post(f"/activities/{activity_id}/delete")
        assert resp.status_code == 403
        with app.app_context():
            assert db.session.get(Activity, activity_id) is not None

    def test_dceqa_cannot_delete_activity_created_by_someone_else_at_own_station(self, client, app, shift):
        """Ownership rule (per spec): DCE_QA no longer gets blanket
        station-wide delete rights over activities they didn't create."""
        login(client, "engineer")
        station_id = _engineer_station(app)  # KHI
        activity_id = self._create_open_pcaa(client, app, shift, station_id)
        client.get("/auth/logout")

        login(client, "dceqa_khi")
        resp = client.post(f"/activities/{activity_id}/delete", follow_redirects=True)
        assert resp.status_code == 403
        with app.app_context():
            assert db.session.get(Activity, activity_id) is not None

    def test_dceqa_cannot_delete_activity_at_a_different_station(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)  # KHI
        activity_id = self._create_open_pcaa(client, app, shift, station_id)
        client.get("/auth/logout")

        login(client, "dceqa_lhe")
        resp = client.post(f"/activities/{activity_id}/delete")
        assert resp.status_code == 403
        with app.app_context():
            assert db.session.get(Activity, activity_id) is not None

    def test_dceqa_can_delete_own_activity(self, client, app, shift):
        login(client, "dceqa_khi")
        station_id = _engineer_station(app)  # KHI, same station as dceqa_khi
        activity_id = self._create_open_pcaa(client, app, shift, station_id)

        resp = client.post(f"/activities/{activity_id}/delete", follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            assert db.session.get(Activity, activity_id) is None
            assert PcaaDetail.query.filter_by(activity_id=activity_id).first() is None
            log = AuditLog.query.filter_by(
                entity_type="Activity", entity_id=activity_id, action="DELETE"
            ).first()
            assert log is not None

    def test_ceqa_cannot_delete_someone_elses_activity(self, client, app, shift):
        """Ownership rule (per spec): CE_QA no longer gets blanket
        Pakistan-wide delete rights over activities they didn't create."""
        login(client, "engineer")
        station_id = _engineer_station(app)
        activity_id = self._create_open_pcaa(client, app, shift, station_id)
        client.get("/auth/logout")

        login(client, "ceqa")
        resp = client.post(f"/activities/{activity_id}/delete", follow_redirects=True)
        assert resp.status_code == 403
        with app.app_context():
            assert db.session.get(Activity, activity_id) is not None

    def test_super_admin_cannot_delete_someone_elses_activity(self, client, app, shift):
        """Ownership rule (per spec): SUPER_ADMIN no longer gets blanket
        delete rights over activities they didn't create."""
        login(client, "engineer")
        station_id = _engineer_station(app)
        activity_id = self._create_open_pcaa(client, app, shift, station_id)
        client.get("/auth/logout")

        login(client, "super")
        resp = client.post(f"/activities/{activity_id}/delete", follow_redirects=True)
        assert resp.status_code == 403
        with app.app_context():
            assert db.session.get(Activity, activity_id) is not None


class TestAddActivityPageLinksToModule8SpecializedForms:
    def test_generic_add_activity_page_links_to_specialized_routes(self, client, app, shift):
        login(client, "engineer")
        resp = client.get("/activities/add")
        body = resp.get_data(as_text=True)
        assert "/activities/add/pcaa" in body
        assert "/activities/add/surveillance" in body
        assert "/activities/add/sms" in body
        assert "/activities/add/office-activity" in body


class TestAllFourteenActivityTypesInDropdown:
    def test_all_14_activity_types_appear_in_add_activity_dropdown(self, client, app, shift):
        login(client, "engineer")
        resp = client.get("/activities/add")
        body = resp.get_data(as_text=True)
        assert len(ActivityType.ALL) == 14
        for label in [l for _code, l, _icon in ActivityType.CHOICES]:
            assert label in body, f"{label!r} missing from Add Activity dropdown"

    def test_all_14_types_have_a_working_specialized_create_link(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        slugs = [
            "ramp-inspection", "spot-checks", "audit", "occurrence-reporting", "training",
            "competence-assessment", "certificate-authorization", "aml-application",
            "maintenance-experience", "investigation", "pcaa", "surveillance", "sms",
            "office-activity",
        ]
        assert len(slugs) == 14
        for slug in slugs:
            resp = client.get(f"/activities/add/{slug}")
            assert resp.status_code == 200, f"GET /activities/add/{slug} failed"
