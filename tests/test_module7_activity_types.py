"""
Module 7: Activity Types 6-10 (Competence Assessment, Certificate
Authorization, AML Application, Maintenance Experience, Investigation)
tests.

Covers: every conditional branch of each type's server-side validation,
saving the parent Activity + specialized detail row together, View Details
rendering, Edit permissions, and audit log entries for create/edit/status
changes. Mirrors the structure of test_module6_activity_types.py.
"""

from datetime import date

import pytest

from app.extensions import db
from app.models.activity import Activity, ActivityStatus, ActivityType
from app.models.audit_log import AuditLog
from app.models.shift import Shift
from app.models.station import Station
from app.models.user import User

from app.models.competence_assessment import CompetenceAssessmentDetail, PersonnelType
from app.models.certificate_authorization import (
    CertificateAuthorizationDetail,
    CertificateAuthorizationOption,
)
from app.models.aml_application import (
    AmlApplicationDetail,
    AmlApplicationType,
    AmlScreening,
    AmlOutcome,
)
from app.models.maintenance_experience import (
    MaintenanceExperienceDetail,
    MaintenanceExperienceOption,
    MaintenanceExperienceAction,
)
from app.models.investigation import InvestigationDetail, InvestigationType, MorAircraftType

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
# 6. COMPETENCE ASSESSMENT OF PERSONNEL
# ===========================================================================

class TestCompetenceAssessment:
    def _payload(self, shift_id, station_id, **overrides):
        p = _common(shift_id, station_id)
        p.update({
            "personnel_type": PersonnelType.QA_PERSONNEL,
            "name": "Ali Khan",
            "pno_cno": "PNO-001",
        })
        p.update(overrides)
        return p

    def test_qa_personnel_valid_submission_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id, personnel_type=PersonnelType.QA_PERSONNEL)

        resp = client.post("/activities/add/competence-assessment", data=payload, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.COMPETENCE_ASSESSMENT).first()
            assert activity is not None
            detail = CompetenceAssessmentDetail.query.filter_by(activity_id=activity.id).first()
            assert detail is not None
            assert detail.personnel_type == PersonnelType.QA_PERSONNEL
            assert detail.name == "Ali Khan"
            assert detail.pno_cno == "PNO-001"

            log = AuditLog.query.filter_by(entity_type="Activity", entity_id=activity.id, action="CREATE").first()
            assert log is not None

    def test_maintenance_personnel_valid_submission_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id, personnel_type=PersonnelType.MAINTENANCE_PERSONNEL)

        resp = client.post("/activities/add/competence-assessment", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.COMPETENCE_ASSESSMENT).first()
            detail = CompetenceAssessmentDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.personnel_type == PersonnelType.MAINTENANCE_PERSONNEL

    def test_missing_personnel_type_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id)
        del payload["personnel_type"]

        resp = client.post("/activities/add/competence-assessment", data=payload)
        assert "Personnel Type is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0

    def test_missing_name_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id, name="")

        resp = client.post("/activities/add/competence-assessment", data=payload)
        assert "Name is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0

    def test_missing_pno_cno_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id, pno_cno="")

        resp = client.post("/activities/add/competence-assessment", data=payload)
        assert "PNO/CNO is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0


# ===========================================================================
# 7. CERTIFICATE AUTHORIZATION
# ===========================================================================

class TestCertificateAuthorization:
    def test_conduct_oral_assessment_option_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"option": CertificateAuthorizationOption.CONDUCT_ORAL_ASSESSMENT})

        resp = client.post("/activities/add/certificate-authorization", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.CERTIFICATE_AUTHORIZATION).first()
            detail = CertificateAuthorizationDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.option == CertificateAuthorizationOption.CONDUCT_ORAL_ASSESSMENT

    def test_coordination_option_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"option": CertificateAuthorizationOption.COORDINATION})

        resp = client.post("/activities/add/certificate-authorization", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.CERTIFICATE_AUTHORIZATION).first()
            detail = CertificateAuthorizationDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.option == CertificateAuthorizationOption.COORDINATION

    def test_missing_option_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)

        resp = client.post("/activities/add/certificate-authorization", data=payload)
        assert "Option is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0

    def test_invalid_option_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"option": "NOT_A_REAL_OPTION"})

        resp = client.post("/activities/add/certificate-authorization", data=payload)
        assert "valid option" in resp.get_data(as_text=True).lower()
        with app.app_context():
            assert Activity.query.count() == 0


# ===========================================================================
# 8. AML APPLICATION
# ===========================================================================

class TestAmlApplication:
    def _payload(self, shift_id, station_id, **overrides):
        p = _common(shift_id, station_id)
        p.update({
            "aml_type": AmlApplicationType.QA_EXAM,
            "screening": AmlScreening.YES,
            "outcome": AmlOutcome.OK,
        })
        p.update(overrides)
        return p

    def test_qa_exam_screening_yes_outcome_ok_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id)

        resp = client.post("/activities/add/aml-application", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.AML_APPLICATION).first()
            detail = AmlApplicationDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.aml_type == AmlApplicationType.QA_EXAM
            assert detail.screening == AmlScreening.YES
            assert detail.outcome == AmlOutcome.OK

    def test_pcaa_screening_no_outcome_return_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(
            shift, station_id,
            aml_type=AmlApplicationType.PCAA, screening=AmlScreening.NO, outcome=AmlOutcome.RETURN,
        )

        resp = client.post("/activities/add/aml-application", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.AML_APPLICATION).first()
            detail = AmlApplicationDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.aml_type == AmlApplicationType.PCAA
            assert detail.screening == AmlScreening.NO
            assert detail.outcome == AmlOutcome.RETURN

    def test_missing_type_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id)
        del payload["aml_type"]

        resp = client.post("/activities/add/aml-application", data=payload)
        assert "Type is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0

    def test_missing_screening_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id)
        del payload["screening"]

        resp = client.post("/activities/add/aml-application", data=payload)
        assert "Screening is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0

    def test_missing_outcome_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id)
        del payload["outcome"]

        resp = client.post("/activities/add/aml-application", data=payload)
        assert "Outcome is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0


# ===========================================================================
# 9. MAINTENANCE EXPERIENCE
# ===========================================================================

class TestMaintenanceExperience:
    def _payload(self, shift_id, station_id, **overrides):
        p = _common(shift_id, station_id)
        p.update({
            "option": MaintenanceExperienceOption.ASSESSMENT,
            "name": "Bilal Ahmed",
            "pno_cno": "CNO-042",
            "action": MaintenanceExperienceAction.OK,
        })
        p.update(overrides)
        return p

    def test_assessment_option_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id, option=MaintenanceExperienceOption.ASSESSMENT)

        resp = client.post("/activities/add/maintenance-experience", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.MAINTENANCE_EXPERIENCE).first()
            detail = MaintenanceExperienceDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.option == MaintenanceExperienceOption.ASSESSMENT
            assert detail.name == "Bilal Ahmed"
            assert detail.pno_cno == "CNO-042"
            assert detail.action == MaintenanceExperienceAction.OK

    def test_sign_by_qa_personnel_option_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id, option=MaintenanceExperienceOption.SIGN_BY_QA_PERSONNEL)

        resp = client.post("/activities/add/maintenance-experience", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.MAINTENANCE_EXPERIENCE).first()
            detail = MaintenanceExperienceDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.option == MaintenanceExperienceOption.SIGN_BY_QA_PERSONNEL

    def test_return_action_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id, action=MaintenanceExperienceAction.RETURN)

        resp = client.post("/activities/add/maintenance-experience", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.MAINTENANCE_EXPERIENCE).first()
            detail = MaintenanceExperienceDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.action == MaintenanceExperienceAction.RETURN

    def test_missing_action_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id)
        del payload["action"]

        resp = client.post("/activities/add/maintenance-experience", data=payload)
        assert "Action is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0

    def test_missing_option_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id)
        del payload["option"]

        resp = client.post("/activities/add/maintenance-experience", data=payload)
        assert "Option is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0

    def test_missing_name_or_pno_cno_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = self._payload(shift, station_id, name="", pno_cno="")

        resp = client.post("/activities/add/maintenance-experience", data=payload)
        body = resp.get_data(as_text=True)
        assert "Name is required" in body
        assert "PNO/CNO is required" in body
        with app.app_context():
            assert Activity.query.count() == 0


# ===========================================================================
# 10. INVESTIGATION
# ===========================================================================

class TestInvestigation:
    def test_mor_requires_aircraft_type(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"investigation_type": InvestigationType.MOR})

        resp = client.post("/activities/add/investigation", data=payload)
        assert "Aircraft Type is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0

    def test_mor_with_valid_aircraft_type_saves(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({
            "investigation_type": InvestigationType.MOR,
            "mor_aircraft_type": MorAircraftType.A320,
        })

        resp = client.post("/activities/add/investigation", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.INVESTIGATION).first()
            detail = InvestigationDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.investigation_type == InvestigationType.MOR
            assert detail.mor_aircraft_type == MorAircraftType.A320

    @pytest.mark.parametrize("aircraft_type", [
        MorAircraftType.ATR, MorAircraftType.A320, MorAircraftType.A350,
        MorAircraftType.B777, MorAircraftType.B787, MorAircraftType.OTHER,
    ])
    def test_every_mor_aircraft_type_choice_is_accepted(self, client, app, shift, aircraft_type):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({
            "investigation_type": InvestigationType.MOR,
            "mor_aircraft_type": aircraft_type,
        })

        resp = client.post("/activities/add/investigation", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.INVESTIGATION).order_by(
                Activity.id.desc()
            ).first()
            detail = InvestigationDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.mor_aircraft_type == aircraft_type

    def test_local_issues_does_not_require_or_store_aircraft_type(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"investigation_type": InvestigationType.LOCAL_ISSUES})

        resp = client.post("/activities/add/investigation", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.INVESTIGATION).first()
            detail = InvestigationDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.investigation_type == InvestigationType.LOCAL_ISSUES
            assert detail.mor_aircraft_type is None

    def test_others_does_not_require_aircraft_type(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({"investigation_type": InvestigationType.OTHERS})

        resp = client.post("/activities/add/investigation", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.INVESTIGATION).first()
            detail = InvestigationDetail.query.filter_by(activity_id=activity.id).first()
            assert detail.investigation_type == InvestigationType.OTHERS
            assert detail.mor_aircraft_type is None

    def test_missing_investigation_type_is_rejected(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)

        resp = client.post("/activities/add/investigation", data=payload)
        assert "Type is required" in resp.get_data(as_text=True)
        with app.app_context():
            assert Activity.query.count() == 0

    def test_invalid_mor_aircraft_type_is_rejected_even_if_client_sent_it(self, client, app, shift):
        """A disabled/hidden field can still be POSTed directly - server must re-check."""
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({
            "investigation_type": InvestigationType.MOR,
            "mor_aircraft_type": "CONCORDE",
        })

        resp = client.post("/activities/add/investigation", data=payload)
        assert "valid aircraft type" in resp.get_data(as_text=True).lower()
        with app.app_context():
            assert Activity.query.count() == 0


# ===========================================================================
# View Details
# ===========================================================================

class TestViewDetailsModule7:
    def _create_investigation(self, client, app, shift, station_id, investigation_type=InvestigationType.MOR,
                               mor_aircraft_type=MorAircraftType.B777):
        payload = _common(shift, station_id)
        payload.update({"investigation_type": investigation_type})
        if investigation_type == InvestigationType.MOR:
            payload["mor_aircraft_type"] = mor_aircraft_type
        client.post("/activities/add/investigation", data=payload, follow_redirects=True)
        with app.app_context():
            return Activity.query.filter_by(activity_type=ActivityType.INVESTIGATION).order_by(
                Activity.id.desc()
            ).first().id

    def test_view_renders_mor_aircraft_type(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        activity_id = self._create_investigation(client, app, shift, station_id)

        resp = client.get(f"/activities/{activity_id}")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "MOR" in body
        assert "B777" in body

    def test_view_hides_aircraft_type_row_for_non_mor(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        activity_id = self._create_investigation(
            client, app, shift, station_id, investigation_type=InvestigationType.LOCAL_ISSUES
        )

        resp = client.get(f"/activities/{activity_id}")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "Aircraft Type" not in body

    def test_view_denied_for_unrelated_user_when_closed(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id, status=ActivityStatus.CLOSED)
        payload.update({"option": CertificateAuthorizationOption.COORDINATION})
        client.post("/activities/add/certificate-authorization", data=payload, follow_redirects=True)
        with app.app_context():
            activity_id = Activity.query.filter_by(
                activity_type=ActivityType.CERTIFICATE_AUTHORIZATION
            ).first().id

        client.get("/auth/logout")
        login(client, "dceqa_lhe")  # different station entirely, activity is CLOSED
        resp = client.get(f"/activities/{activity_id}")
        assert resp.status_code == 403


# ===========================================================================
# Edit permissions + audit log
# ===========================================================================

class TestEditPermissionsModule7:
    def _create_open_activity(self, client, app, shift, station_id):
        payload = _common(shift, station_id)
        payload.update({
            "personnel_type": PersonnelType.QA_PERSONNEL, "name": "Original Name", "pno_cno": "PNO-1",
        })
        client.post("/activities/add/competence-assessment", data=payload, follow_redirects=True)
        with app.app_context():
            return Activity.query.filter_by(activity_type=ActivityType.COMPETENCE_ASSESSMENT).first().id

    def test_creator_can_edit_while_open(self, client, app, shift):
        login(client, "engineer")
        station_id = _engineer_station(app)
        activity_id = self._create_open_activity(client, app, shift, station_id)

        resp = client.get(f"/activities/{activity_id}/edit")
        assert resp.status_code == 200

        payload = _common(shift, station_id, remarks="updated remarks")
        payload.update({
            "personnel_type": PersonnelType.MAINTENANCE_PERSONNEL, "name": "Updated Name", "pno_cno": "PNO-2",
        })
        resp = client.post(f"/activities/{activity_id}/edit", data=payload, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            activity = db.session.get(Activity, activity_id)
            assert activity.remarks == "updated remarks"
            detail = CompetenceAssessmentDetail.query.filter_by(activity_id=activity_id).first()
            assert detail.personnel_type == PersonnelType.MAINTENANCE_PERSONNEL
            assert detail.name == "Updated Name"
            assert detail.pno_cno == "PNO-2"

            update_log = AuditLog.query.filter_by(
                entity_type="Activity", entity_id=activity_id, action="UPDATE"
            ).first()
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
        payload.update({
            "personnel_type": PersonnelType.QA_PERSONNEL, "name": "Original Name", "pno_cno": "PNO-1",
        })
        client.post(f"/activities/{activity_id}/edit", data=payload, follow_redirects=True)

        with app.app_context():
            log = AuditLog.query.filter_by(
                entity_type="Activity", entity_id=activity_id, action="STATUS_CHANGE"
            ).first()
            assert log is not None
            assert "OPEN" in log.details and "CLOSED" in log.details

    def test_investigation_edit_can_switch_from_mor_to_local_issues_and_clears_aircraft_type(
        self, client, app, shift
    ):
        login(client, "engineer")
        station_id = _engineer_station(app)
        payload = _common(shift, station_id)
        payload.update({
            "investigation_type": InvestigationType.MOR,
            "mor_aircraft_type": MorAircraftType.ATR,
        })
        client.post("/activities/add/investigation", data=payload, follow_redirects=True)
        with app.app_context():
            activity_id = Activity.query.filter_by(activity_type=ActivityType.INVESTIGATION).first().id

        edit_payload = _common(shift, station_id)
        edit_payload.update({"investigation_type": InvestigationType.LOCAL_ISSUES})
        resp = client.post(f"/activities/{activity_id}/edit", data=edit_payload, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            detail = InvestigationDetail.query.filter_by(activity_id=activity_id).first()
            assert detail.investigation_type == InvestigationType.LOCAL_ISSUES
            assert detail.mor_aircraft_type is None


class TestAddActivityPageLinksToModule7SpecializedForms:
    def test_generic_add_activity_page_links_to_specialized_routes(self, client, app, shift):
        login(client, "engineer")
        resp = client.get("/activities/add")
        body = resp.get_data(as_text=True)
        assert "/activities/add/competence-assessment" in body
        assert "/activities/add/certificate-authorization" in body
        assert "/activities/add/aml-application" in body
        assert "/activities/add/maintenance-experience" in body
        assert "/activities/add/investigation" in body
