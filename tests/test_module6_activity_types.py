"""
Module 6: Activity Types 1-5 (Ramp Inspection, Spot Checks, Audit,
Occurrence Reporting, Training) tests.

Covers: every conditional branch of each type's server-side validation,
saving the parent Activity + specialized detail row together, View Details
rendering, Edit permissions, and audit log entries for create/edit/status
changes.
"""

from datetime import date

import pytest

from app.extensions import db
from app.models.activity import Activity, ActivityStatus, ActivityType
from app.models.airline import Airline
from app.models.aircraft import Aircraft
from app.models.audit_log import AuditLog
from app.models.shift import Shift
from app.models.station import Station
from app.models.user import User

from app.models.ramp_inspection import RampInspectionDetail, RampInspectionOption
from app.models.spot_check import SpotCheckDetail, SpotCheckType, SpotCheckArea
from app.models.audit_detail import AuditDetail, AuditType, AuditSection, AuditStage
from app.models.occurrence import OccurrenceDetail, OccurrenceReportType, OccurrenceCategory
from app.models.training_detail import TrainingDetail, TrainingMode, TrainingKind

from tests.conftest import login


@pytest.fixture()
def shift(app):
    with app.app_context():
        s = Shift(name="Morning", is_active=True)
        db.session.add(s)
        db.session.commit()
        return s.id


@pytest.fixture()
def airline(app):
    with app.app_context():
        a = Airline(code="PK", name="Pakistan International", is_active=True)
        db.session.add(a)
        db.session.commit()
        return a.id


@pytest.fixture()
def aircraft(app, airline):
    with app.app_context():
        ac = Aircraft(registration="AP-BEG", type="A320", airline_id=airline, is_active=True)
        db.session.add(ac)
        db.session.commit()
        return ac.id


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
# 1. RAMP INSPECTION
# ===========================================================================

class TestRampInspection:
    def test_valid_submission_saves_activity_and_detail(self, client, app, shift, airline, aircraft):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({
            "option": RampInspectionOption.EU_SAFA_BOUND_FLIGHT,
            "airline_id": str(airline),
            "aircraft_id": str(aircraft),
            "flight_number": "PK301",
            "email_done": "YES",
            "qa_db_update_done": "NO",
        })

        resp = client.post("/activities/add/ramp-inspection", data=payload, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.RAMP_INSPECTION).first()
            assert activity is not None
            detail = RampInspectionDetail.query.filter_by(activity_id=activity.id).first()
            assert detail is not None
            assert detail.option == RampInspectionOption.EU_SAFA_BOUND_FLIGHT
            assert detail.airline_id == airline
            assert detail.aircraft_id == aircraft
            assert detail.flight_number == "PK301"
            assert detail.email_done is True
            assert detail.qa_db_update_done is False

            log = AuditLog.query.filter_by(entity_type="Activity", entity_id=activity.id, action="CREATE").first()
            assert log is not None

    def test_missing_option_is_rejected(self, client, app, shift, airline, aircraft):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"airline_id": str(airline), "aircraft_id": str(aircraft), "flight_number": "PK301"})

        resp = client.post("/activities/add/ramp-inspection", data=payload)
        assert "Option is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0

    def test_missing_aircraft_is_rejected(self, client, app, shift, airline):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({
            "option": RampInspectionOption.AS_PER_ANNUAL_PLAN,
            "airline_id": str(airline),
            "flight_number": "PK301",
        })

        resp = client.post("/activities/add/ramp-inspection", data=payload)
        assert "Aircraft Registration is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0

    def test_aircraft_must_come_from_database_not_free_text(self, client, app, shift, airline):
        """Posting a non-existent aircraft_id must be rejected, not accepted as free text."""
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({
            "option": RampInspectionOption.PCAA_RAMP_INSPECTION,
            "airline_id": str(airline),
            "aircraft_id": "999999",
            "flight_number": "PK301",
        })

        resp = client.post("/activities/add/ramp-inspection", data=payload)
        assert "valid, active aircraft" in resp.get_data(as_text=True).lower()
        with app.app_context():
            assert Activity.query.count() == 0

    def test_engineer_foreign_station_rejected(self, client, app, shift, airline, aircraft):
        login(client, "engineer")
        with app.app_context():
            lhe = Station.query.filter_by(code="LHE").first().id
        payload = _common(shift, lhe)
        payload.update({
            "option": RampInspectionOption.AS_PER_ANNUAL_PLAN,
            "airline_id": str(airline), "aircraft_id": str(aircraft), "flight_number": "PK1",
        })
        resp = client.post("/activities/add/ramp-inspection", data=payload)
        assert "authorized" in resp.get_data(as_text=True).lower()
        with app.app_context():
            assert Activity.query.count() == 0


# ===========================================================================
# 2. SPOT CHECKS
# ===========================================================================

class TestSpotChecks:
    def _payload(self, shift_id, station_id, **overrides):
        p = _common(shift_id, station_id)
        p.update({"email_done": "NO", "qa_db_update_done": "NO"})
        p.update(overrides)
        return p

    def test_area_requiring_aircraft_fields_needs_them(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id, spot_check_type=SpotCheckType.AREAS,
                                 area=SpotCheckArea.AIRCRAFT_SPOT_CHECKS)
        resp = client.post("/activities/add/spot-checks", data=payload)
        body = resp.get_data(as_text=True)
        assert "Airline is required" in body
        assert "Aircraft Registration is required" in body
        with app.app_context():
            assert Activity.query.count() == 0

    def test_area_not_requiring_aircraft_fields_saves_without_them(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id, spot_check_type=SpotCheckType.AREAS,
                                 area=SpotCheckArea.TOOL_STORE)
        resp = client.post("/activities/add/spot-checks", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.SPOT_CHECKS).first()
            detail = SpotCheckDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.area == SpotCheckArea.TOOL_STORE
            assert detail.airline_id is None
            assert detail.aircraft_id is None

    def test_aircraft_area_with_valid_aircraft_fields_saves(self, client, app, shift, airline, aircraft):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id, spot_check_type=SpotCheckType.AREAS,
                                 area=SpotCheckArea.A320_MAINTENANCE, airline_id=str(airline),
                                 aircraft_id=str(aircraft), flight_number="PK500")
        resp = client.post("/activities/add/spot-checks", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.SPOT_CHECKS).first()
            detail = SpotCheckDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.airline_id == airline
            assert detail.aircraft_id == aircraft

    def test_pcaa_type_requires_aircraft_fields(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id, spot_check_type=SpotCheckType.PCAA)
        resp = client.post("/activities/add/spot-checks", data=payload)
        body = resp.get_data(as_text=True)
        assert "Airline is required" in body
        with app.app_context():
            assert Activity.query.count() == 0

    def test_prep_followup_type_needs_no_area_or_aircraft_fields(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id, spot_check_type=SpotCheckType.PREPARATION_FOLLOWUP)
        resp = client.post("/activities/add/spot-checks", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.SPOT_CHECKS).first()
            detail = SpotCheckDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.area is None
            assert detail.airline_id is None

    def test_missing_area_when_type_is_areas_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id, spot_check_type=SpotCheckType.AREAS)
        resp = client.post("/activities/add/spot-checks", data=payload)
        assert "Area is required" in resp.get_data(as_text=True)


# ===========================================================================
# 3. AUDIT
# ===========================================================================

class TestAudit:
    def _payload(self, shift_id, station_id, **overrides):
        p = _common(shift_id, station_id)
        p.update({
            "audit_type": AuditType.SCHEDULED,
            "section": AuditSection.LINE_MAINTENANCE,
            "audit_stage": AuditStage.AUDIT_PREPARATION,
            "stage_status": ActivityStatus.CLOSED, "stage_remarks": "done",
        })
        p.update(overrides)
        return p

    def test_internal_section_saves_without_authority_operator(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id)
        resp = client.post("/activities/add/audit", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.AUDIT).first()
            detail = AuditDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.section == AuditSection.LINE_MAINTENANCE
            assert detail.authority is None
            assert detail.audit_stage == AuditStage.AUDIT_PREPARATION
            assert detail.stage_status == ActivityStatus.CLOSED

    def test_external_section_requires_authority_but_not_operator(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id, section=AuditSection.EXTERNAL)
        resp = client.post("/activities/add/audit", data=payload)
        body = resp.get_data(as_text=True)
        assert "Authority is required" in body
        assert "Operator is required" not in body
        with app.app_context():
            assert Activity.query.count() == 0

    def test_external_section_with_authority_operator_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id, section=AuditSection.EXTERNAL,
                                 authority="PCAA", operator="PIA")
        resp = client.post("/activities/add/audit", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.AUDIT).first()
            detail = AuditDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.authority == "PCAA"
            assert detail.operator == "PIA"

    def test_external_section_without_operator_still_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id, section=AuditSection.EXTERNAL,
                                 authority="PCAA")
        resp = client.post("/activities/add/audit", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.AUDIT).first()
            detail = AuditDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.authority == "PCAA"
            assert detail.operator is None

    def test_audit_stage_is_tracked_via_single_dropdown(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(
            shift, station_id,
            audit_stage=AuditStage.CLOSURE_OF_AUDIT,
            stage_status=ActivityStatus.OPEN,
        )
        client.post("/activities/add/audit", data=payload, follow_redirects=True)
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.AUDIT).first()
            detail = AuditDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.audit_stage == AuditStage.CLOSURE_OF_AUDIT
            assert detail.stage_status == ActivityStatus.OPEN


# ===========================================================================
# 4. OCCURRENCE REPORTING
# ===========================================================================

class TestOccurrenceReporting:
    def test_valid_submission_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"report_type": OccurrenceReportType.PCAA, "category": OccurrenceCategory.BIRD_HIT})
        resp = client.post("/activities/add/occurrence-reporting", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.OCCURRENCE_REPORTING).first()
            detail = OccurrenceDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.report_type == OccurrenceReportType.PCAA
            assert detail.category == OccurrenceCategory.BIRD_HIT

    def test_missing_category_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"report_type": OccurrenceReportType.INTERNAL})
        resp = client.post("/activities/add/occurrence-reporting", data=payload)
        assert "Occurrence is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0


# ===========================================================================
# 5. TRAINING
# ===========================================================================

class TestTraining:
    def test_conduct_with_recurrent_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"mode": TrainingMode.CONDUCT, "kind": TrainingKind.RECURRENT_TRAINING})
        resp = client.post("/activities/add/training", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.TRAINING).first()
            detail = TrainingDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.mode == TrainingMode.CONDUCT
            assert detail.kind == TrainingKind.RECURRENT_TRAINING

    def test_conduct_with_types_is_rejected(self, client, app, shift):
        """'Types' is only a valid Training kind under Attend, not Conduct."""
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"mode": TrainingMode.CONDUCT, "kind": TrainingKind.TYPES})
        resp = client.post("/activities/add/training", data=payload)
        assert "only valid under attend" in resp.get_data(as_text=True).lower()
        with app.app_context():
            assert Activity.query.count() == 0

    def test_attend_with_types_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"mode": TrainingMode.ATTEND, "kind": TrainingKind.TYPES})
        resp = client.post("/activities/add/training", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.TRAINING).first()
            detail = TrainingDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.kind == TrainingKind.TYPES


# ===========================================================================
# View Details
# ===========================================================================

class TestViewDetails:
    def _create_ramp_inspection(self, client, app, shift, airline, aircraft, station_id):
        payload = _common(shift, station_id)
        payload.update({
            "option": RampInspectionOption.AS_PER_ANNUAL_PLAN,
            "airline_id": str(airline), "aircraft_id": str(aircraft), "flight_number": "PK9",
        })
        client.post("/activities/add/ramp-inspection", data=payload, follow_redirects=True)
        with app.app_context():
            return Activity.query.filter_by(activity_type=ActivityType.RAMP_INSPECTION).first().id

    def test_view_renders_detail_fields(self, client, app, shift, airline, aircraft):
        login(client, "engineer")
        station_id = _engineer_station(app)
        activity_id = self._create_ramp_inspection(client, app, shift, airline, aircraft, station_id)

        resp = client.get(f"/activities/{activity_id}")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "PK9" in body
        assert "As per Annual Plan" in body

    def test_view_denied_for_unrelated_engineer_when_closed(self, client, app, shift, airline, aircraft):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id, status=ActivityStatus.CLOSED)
        payload.update({
            "option": RampInspectionOption.AS_PER_ANNUAL_PLAN,
            "airline_id": str(airline), "aircraft_id": str(aircraft), "flight_number": "PK9",
        })
        client.post("/activities/add/ramp-inspection", data=payload, follow_redirects=True)
        with app.app_context():
            activity_id = Activity.query.filter_by(activity_type=ActivityType.RAMP_INSPECTION).first().id

        # A different engineer at the same station did not create it, and
        # it's CLOSED, so per can_view_activity they cannot view it.
        with app.app_context():
            other_station = Station.query.filter_by(code="KHI").first()
        client.get("/auth/logout")
        login(client, "dceqa_lhe")  # different station entirely
        resp = client.get(f"/activities/{activity_id}")
        assert resp.status_code == 403


# ===========================================================================
# Edit permissions + audit log
# ===========================================================================

class TestEditPermissions:
    def _create_open_activity(self, client, app, shift, station_id):
        payload = _common(shift, station_id)
        payload.update({"report_type": OccurrenceReportType.INTERNAL, "category": OccurrenceCategory.FOD})
        client.post("/activities/add/occurrence-reporting", data=payload, follow_redirects=True)
        with app.app_context():
            return Activity.query.filter_by(activity_type=ActivityType.OCCURRENCE_REPORTING).first().id

    def test_creator_can_edit_while_open(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        activity_id = self._create_open_activity(client, app, shift, station_id)

        resp = client.get(f"/activities/{activity_id}/edit")
        assert resp.status_code == 200

        payload = _common(shift, station_id, remarks="updated remarks")
        payload.update({"report_type": OccurrenceReportType.THIRD_PARTY, "category": OccurrenceCategory.OTHER})
        resp = client.post(f"/activities/{activity_id}/edit", data=payload, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            activity = db.session.get(Activity, activity_id)
            assert activity.remarks == "updated remarks"
            detail = OccurrenceDetail.query.filter_by(activity_id=activity_id).first()
            assert detail.report_type == OccurrenceReportType.THIRD_PARTY

            update_log = AuditLog.query.filter_by(entity_type="Activity", entity_id=activity_id, action="UPDATE").first()
            assert update_log is not None

    def test_engineer_cannot_edit_after_activity_is_closed(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        activity_id = self._create_open_activity(client, app, shift, station_id)

        with app.app_context():
            activity = db.session.get(Activity, activity_id)
            activity.status = ActivityStatus.CLOSED
            db.session.commit()

        resp = client.get(f"/activities/{activity_id}/edit")
        assert resp.status_code == 403

    def test_dceqa_cannot_edit_activity_created_by_someone_else_at_own_station(self, client, app, shift):
        """Ownership rule (per spec): DCE_QA no longer gets blanket
        station-wide edit rights over activities they didn't create - only
        the creator (or, for engineers, only while OPEN) may edit."""
        login(client, "engineer")
        station_id = _engineer_station(app)  # KHI
        activity_id = self._create_open_activity(client, app, shift, station_id)
        client.get("/auth/logout")

        login(client, "dceqa_khi")
        resp = client.get(f"/activities/{activity_id}/edit")
        assert resp.status_code == 403

    def test_dceqa_cannot_edit_activity_at_a_different_station(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)  # KHI
        activity_id = self._create_open_activity(client, app, shift, station_id)
        client.get("/auth/logout")

        login(client, "dceqa_lhe")
        resp = client.get(f"/activities/{activity_id}/edit")
        assert resp.status_code == 403

    def test_status_change_writes_a_status_change_log_entry(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        activity_id = self._create_open_activity(client, app, shift, station_id)

        payload = _common(shift, station_id, status=ActivityStatus.CLOSED)
        payload.update({"report_type": OccurrenceReportType.INTERNAL, "category": OccurrenceCategory.FOD})
        client.post(f"/activities/{activity_id}/edit", data=payload, follow_redirects=True)

        with app.app_context():
            log = AuditLog.query.filter_by(entity_type="Activity", entity_id=activity_id, action="STATUS_CHANGE").first()
            assert log is not None
            assert "OPEN" in log.details and "CLOSED" in log.details


class TestAddActivityPageLinksToSpecializedForms:
    def test_generic_add_activity_page_links_to_specialized_routes(self, client, app, shift):
        login(client, "engineer")
        resp = client.get("/activities/add")
        body = resp.get_data(as_text=True)
        assert "/activities/add/ramp-inspection" in body
        assert "/activities/add/spot-checks" in body
        assert "/activities/add/audit" in body
        assert "/activities/add/occurrence-reporting" in body
        assert "/activities/add/training" in body
