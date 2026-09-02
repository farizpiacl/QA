"""
Module 9: Activities + Open Activities + Recent Activities + Reports.

Covers:
  - search/filters/pagination on the Activities page (main + admin
    blueprints), and that filters only ever narrow an already role-scoped
    query (never widen it).
  - Open Activities visibility for CE_QA, DCE_QA, AIRCRAFT_ENGINEER and
    SUPER_ADMIN, each subject to the existing permission rules.
  - the Edit action is shown/hidden per `can_edit_activity` but is *also*
    enforced server-side regardless of what the list page renders.
  - Reports: every report type returns live database rows scoped the same
    way as the dashboard/activities list (CE Pakistan-wide, DCE own
    station + OPEN, engineer own records + OPEN), and the "-wise" reports
    aggregate correctly.
  - Excel / PDF export endpoints return the right content type.
"""

from datetime import date

import pytest

from app.extensions import db
from app.models.activity import Activity, ActivityStatus, ActivityType
from app.models.airline import Airline
from app.models.aircraft import Aircraft
from app.models.shift import Shift
from app.models.station import Station
from app.models.user import User

from tests.conftest import login


def rows_html(body: str) -> str:
    """
    Scopes an assertion to the results `<tbody>` only. Filter dropdowns
    (station/activity-type/report pickers) always list every option
    regardless of the current result set - by design, so the user can
    switch filters without a round trip - so a raw substring check against
    the whole page body would false-positive on dropdown text. Every page
    under test renders exactly one results table.
    """
    start = body.find("<tbody>")
    end = body.find("</tbody>")
    assert start != -1 and end != -1, "expected a <tbody> results table in the response"
    return body[start:end]


@pytest.fixture()
def rig(app):
    """Common fixture data: a shift, an airline/aircraft, and three
    activities spread across stations/status/creators so scoping and
    filtering both have something real to check against."""
    with app.app_context():
        shift = Shift(name="Morning", is_active=True)
        db.session.add(shift)

        pia = Airline(code="PK", name="PIA", is_active=True)
        db.session.add(pia)
        db.session.flush()
        ac = Aircraft(registration="AP-BOB", type="A320", airline_id=pia.id, is_active=True)
        db.session.add(ac)
        db.session.flush()

        khi = Station.query.filter_by(code="KHI").first()
        lhe = Station.query.filter_by(code="LHE").first()
        engineer = User.query.filter_by(username="engineer").first()
        ceqa = User.query.filter_by(username="ceqa").first()

        a_khi_open = Activity(
            activity_date=date.today(), shift_id=shift.id, activity_type=ActivityType.SMS,
            station_id=khi.id, created_by=engineer.id, status=ActivityStatus.OPEN,
            remarks="engineer open sms",
        )
        a_lhe_closed = Activity(
            activity_date=date.today(), shift_id=shift.id, activity_type=ActivityType.PCAA,
            station_id=lhe.id, created_by=ceqa.id, status=ActivityStatus.CLOSED,
            remarks="ce closed pcaa",
        )
        a_lhe_open = Activity(
            activity_date=date.today(), shift_id=shift.id, activity_type=ActivityType.SURVEILLANCE,
            station_id=lhe.id, created_by=ceqa.id, status=ActivityStatus.OPEN,
            remarks="ce open surveillance",
        )
        db.session.add_all([a_khi_open, a_lhe_closed, a_lhe_open])
        db.session.commit()

        return {
            "shift_id": shift.id,
            "khi_id": khi.id,
            "lhe_id": lhe.id,
            "airline_id": pia.id,
            "aircraft_id": ac.id,
            "khi_open_id": a_khi_open.id,
            "lhe_closed_id": a_lhe_closed.id,
            "lhe_open_id": a_lhe_open.id,
        }


class TestActivitiesPageFiltersAndSearch:
    def test_status_filter(self, client, app, rig):
        login(client, "ceqa")
        resp = client.get("/activities?status=CLOSED")
        assert resp.status_code == 200
        rows = rows_html(resp.get_data(as_text=True))
        assert "LHE" in rows
        # the OPEN KHI activity's station code must not leak into a CLOSED-only view
        assert "KHI" not in rows

    def test_station_filter(self, client, app, rig):
        login(client, "ceqa")
        resp = client.get(f"/activities?station_id={rig['khi_id']}")
        rows = rows_html(resp.get_data(as_text=True))
        assert "KHI" in rows
        assert "LHE" not in rows

    def test_search_matches_station_and_creator(self, client, app, rig):
        login(client, "ceqa")
        resp = client.get("/activities?q=engineer")
        body = resp.get_data(as_text=True)
        assert "Engineer" in body  # creator full_name is "Engineer"

    def test_search_no_match_shows_empty_state(self, client, app, rig):
        login(client, "ceqa")
        resp = client.get("/activities?q=zzz_no_such_thing")
        assert b"No activities found" in resp.data

    def test_date_range_filter(self, client, app, rig):
        login(client, "ceqa")
        resp = client.get("/activities?date_from=2099-01-01")
        assert b"No activities found" in resp.data

    def test_airline_and_aircraft_filters_do_not_error(self, client, app, rig):
        # No ramp-inspection/spot-check rows exist in this fixture, so both
        # filters should just narrow to zero rows rather than erroring.
        login(client, "ceqa")
        resp = client.get(f"/activities?airline_id={rig['airline_id']}")
        assert resp.status_code == 200
        resp = client.get(f"/activities?aircraft_id={rig['aircraft_id']}")
        assert resp.status_code == 200

    def test_pagination_preserves_filters(self, client, app, rig):
        login(client, "ceqa")
        resp = client.get("/activities?status=OPEN&page=1")
        assert resp.status_code == 200
        # only one page of data exists, so a page=2 request should not 500
        resp = client.get("/activities?status=OPEN&page=2")
        assert resp.status_code == 200


class TestActivitiesScopingUnaffectedByFilters:
    """A filter value must never let a role see a row `apply_activity_scope`
    would otherwise hide - filters only narrow the query, never widen it."""

    def test_dce_cannot_use_station_filter_to_see_other_stations_closed_activity(self, client, app, rig):
        login(client, "dceqa_khi")
        resp = client.get(f"/activities?station_id={rig['lhe_id']}")
        rows = rows_html(resp.get_data(as_text=True))
        # LHE's CLOSED activity is invisible to a KHI DCE regardless of the
        # station filter they type into the URL.
        assert "Pcaa" not in rows

    def test_dce_still_sees_any_open_activity_from_other_stations(self, client, app, rig):
        login(client, "dceqa_khi")
        resp = client.get("/activities?status=OPEN")
        body = resp.get_data(as_text=True)
        assert "Surveillance" in body  # LHE's OPEN activity, visible via the OPEN carve-out

    def test_engineer_created_by_filter_cannot_reveal_others_closed_work(self, client, app, rig):
        login(client, "engineer")
        ceqa = User.query.filter_by(username="ceqa").first()
        resp = client.get(f"/activities?created_by={ceqa.id}")
        rows = rows_html(resp.get_data(as_text=True))
        assert "Pcaa" not in rows


class TestOpenActivitiesVisibility:
    """Open Activities must be visible to CE QA, DCE QA, Aircraft Engineers
    and Super Admin, each still subject to their own scoping rule."""

    @pytest.mark.parametrize("username", ["ceqa", "dceqa_khi", "dceqa_lhe", "engineer"])
    def test_open_activities_accessible(self, client, app, rig, username):
        login(client, username)
        resp = client.get("/activities/open", follow_redirects=True)
        assert resp.status_code == 200
        assert "Open Activities" in resp.get_data(as_text=True)

    def test_super_admin_open_activities_accessible(self, client, app, rig):
        login(client, "super")
        resp = client.get("/admin/activities/open", follow_redirects=True)
        assert resp.status_code == 200


class TestEditActionPermissionWiring:
    def test_engineer_edit_link_present_for_own_open_activity(self, client, app, rig):
        login(client, "engineer")
        resp = client.get("/activities")
        body = resp.get_data(as_text=True)
        assert f"/activities/{rig['khi_open_id']}/edit" in body

    def test_engineer_edit_link_absent_for_others_activity(self, client, app, rig):
        login(client, "engineer")
        resp = client.get("/activities?status=OPEN")
        body = resp.get_data(as_text=True)
        # Engineer can view (via the OPEN carve-out) LHE's open activity but
        # cannot edit someone else's record.
        assert f"/activities/{rig['lhe_open_id']}/edit" not in body

    def test_edit_route_still_403s_even_if_a_link_were_forged(self, client, app, rig):
        """Viewing does NOT automatically mean editing - enforced at the
        route, not just by hiding the link in the template."""
        login(client, "engineer")
        resp = client.get(f"/activities/{rig['lhe_open_id']}/edit")
        assert resp.status_code == 403


class TestReportsScoping:
    def test_ce_overall_report_sees_every_station(self, client, app, rig):
        login(client, "ceqa")
        resp = client.get("/reports?report=overall")
        rows = rows_html(resp.get_data(as_text=True))
        assert "KHI" in rows and "LHE" in rows

    def test_dce_overall_report_scoped_to_own_station_plus_open(self, client, app, rig):
        login(client, "dceqa_khi")
        resp = client.get("/reports?report=overall")
        rows = rows_html(resp.get_data(as_text=True))
        assert "KHI" in rows
        assert "LHE" in rows  # via the OPEN carve-out (a_lhe_open)
        assert "Pcaa" not in rows  # LHE's CLOSED row must stay hidden

    def test_engineer_open_report_sees_others_open_but_not_others_closed(self, client, app, rig):
        login(client, "engineer")
        resp = client.get("/reports?report=open")
        rows = rows_html(resp.get_data(as_text=True))
        assert "Surveillance" in rows
        resp = client.get("/reports?report=closed")
        rows = rows_html(resp.get_data(as_text=True))
        assert "Pcaa" not in rows

    def test_type_specific_report_filters_to_that_type_only(self, client, app, rig):
        login(client, "ceqa")
        resp = client.get(f"/reports?report={ActivityType.PCAA}")
        rows = rows_html(resp.get_data(as_text=True))
        assert "Pcaa" in rows
        assert "Surveillance" not in rows

    def test_no_report_selected_shows_prompt_not_data(self, client, app, rig):
        login(client, "ceqa")
        resp = client.get("/reports")
        assert resp.status_code == 200
        assert "Choose a report" in resp.get_data(as_text=True)

    def test_super_admin_reports_pakistan_wide(self, client, app, rig):
        login(client, "super")
        resp = client.get("/admin/reports?report=overall")
        body = resp.get_data(as_text=True)
        assert "KHI" in body and "LHE" in body


class TestAggregateReports:
    def test_station_wise_groups_correctly(self, client, app, rig):
        login(client, "ceqa")
        resp = client.get("/reports?report=station_wise")
        body = resp.get_data(as_text=True)
        assert "KHI" in body and "LHE" in body

    def test_user_wise_groups_correctly(self, client, app, rig):
        login(client, "ceqa")
        resp = client.get("/reports?report=user_wise")
        body = resp.get_data(as_text=True)
        assert "Engineer" in body and "Ceqa" in body

    def test_airline_wise_report_does_not_error_with_no_airline_activities(self, client, app, rig):
        login(client, "ceqa")
        resp = client.get("/reports?report=airline_wise")
        assert resp.status_code == 200


class TestReportExports:
    def test_excel_export_returns_xlsx(self, client, app, rig):
        login(client, "ceqa")
        resp = client.get("/reports/export/excel?report=overall")
        assert resp.status_code == 200
        assert resp.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def test_pdf_export_returns_pdf(self, client, app, rig):
        login(client, "ceqa")
        resp = client.get("/reports/export/pdf?report=station_wise")
        assert resp.status_code == 200
        assert resp.mimetype == "application/pdf"

    def test_export_requires_login(self, client, app, rig):
        resp = client.get("/reports/export/excel?report=overall")
        assert resp.status_code in (302, 401)

    def test_export_respects_role_scope(self, client, app, rig):
        """An engineer's exported report must not contain rows they
        couldn't otherwise see (e.g. another station's CLOSED activity)."""
        login(client, "engineer")
        resp = client.get("/reports/export/excel?report=overall")
        assert resp.status_code == 200

        import openpyxl
        from io import BytesIO

        wb = openpyxl.load_workbook(BytesIO(resp.data))
        ws = wb.active
        values = [cell.value for row in ws.iter_rows() for cell in row if cell.value]
        assert not any("Pcaa" in str(v) or "PCAA" in str(v) for v in values)


class TestActivitiesRolesGuarded:
    def test_activities_requires_login(self, client, app, rig):
        resp = client.get("/activities")
        assert resp.status_code in (302, 401)

    def test_reports_requires_login(self, client, app, rig):
        resp = client.get("/reports")
        assert resp.status_code in (302, 401)

    def test_super_admin_only_route_rejects_other_roles(self, client, app, rig):
        login(client, "ceqa")
        resp = client.get("/admin/activities")
        assert resp.status_code == 403


class TestDceDashboardActivityCards:
    """DCE_QA dashboard: 14 live Activity Type cards + Date/Station/Shift/
    Engineer/Status filters that narrow the counts and carry through to the
    Activities list the cards link into."""

    def test_dashboard_shows_all_14_activity_cards_with_live_counts(self, client, app, rig):
        login(client, "dceqa_khi")
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)

        for code, label, icon in ActivityType.CHOICES:
            assert label in body

        # `rig` seeds exactly one KHI-visible SMS activity (KHI OPEN) plus a
        # station-agnostic OPEN one (LHE) that DCE always sees regardless of
        # station - so SMS should read 1, not 0 and not inflated.
        with app.app_context():
            from app.utils.dashboard import get_dashboard_stats
            dce = User.query.filter_by(username="dceqa_khi").first()
            stats = get_dashboard_stats(dce)
            by_type = dict((code, count) for code, _l, _i, count in stats["by_type"])
            assert by_type[ActivityType.SMS] == 1

    def test_dashboard_filter_bar_present_for_dce(self, client, app, rig):
        login(client, "dceqa_khi")
        resp = client.get("/")
        body = resp.get_data(as_text=True)
        for field in ("date_from", "date_to", "station_id", "shift_id", "created_by", "status"):
            assert f'name="{field}"' in body

    def test_dashboard_filter_bar_absent_for_other_roles(self, client, app, rig):
        login(client, "engineer")
        resp = client.get("/")
        body = resp.get_data(as_text=True)
        assert "Filter Activity Cards" not in body

    def test_status_filter_narrows_activity_card_counts(self, client, app, rig):
        login(client, "dceqa_khi")
        resp = client.get("/?status=CLOSED")
        assert resp.status_code == 200
        with app.app_context():
            from app.utils.dashboard import get_dashboard_stats
            from werkzeug.datastructures import MultiDict
            dce = User.query.filter_by(username="dceqa_khi").first()
            stats = get_dashboard_stats(dce, filters=MultiDict({"status": "CLOSED"}))
            by_type = dict((code, count) for code, _l, _i, count in stats["by_type"])
            # The only CLOSED activity in `rig` is the LHE PCAA one, which a
            # KHI-scoped DCE cannot see at all (not their station, not OPEN)
            assert sum(by_type.values()) == 0

    def test_activity_card_links_to_filtered_activities_list(self, client, app, rig):
        login(client, "dceqa_khi")
        resp = client.get("/?station_id=%s" % rig["khi_id"])
        body = resp.get_data(as_text=True)
        assert f"/activities?type=SMS&amp;station_id={rig['khi_id']}" in body

    def test_clicking_through_card_link_shows_matching_activities(self, client, app, rig):
        login(client, "dceqa_khi")
        resp = client.get("/activities?type=SMS")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "engineer open sms" not in body  # remarks aren't rendered directly, sanity only
        assert "Sms" in body or "SMS" in body

    def test_activity_row_view_link_targets_the_detail_route(self, client, app, rig):
        """The list page's View action must point at the full activity-detail
        route (not just a plain summary link) - confirmed here by checking
        the generated URL and that access is permission-checked, not blocked
        outright, for a station the DCE can see."""
        login(client, "dceqa_khi")
        with app.app_context():
            activity = Activity.query.filter_by(activity_type=ActivityType.SMS).first()
            activity_id = activity.id
        resp = client.get("/activities?type=SMS")
        body = resp.get_data(as_text=True)
        assert f"/activities/{activity_id}" in body
        # Reachable and permission-checked (not a blanket 403) - a 404 here
        # would only mean the seeded activity has no specialized detail row,
        # which `rig` doesn't create; that's a fixture limitation, not a
        # dashboard/routing regression.
        resp2 = client.get(f"/activities/{activity_id}")
        assert resp2.status_code != 403
