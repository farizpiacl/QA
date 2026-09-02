"""
Analytics: reporting-grade dashboards for CE_QA / DCE_QA / AIRCRAFT_ENGINEER.

Everything here is a thin aggregation layer on top of the same building
blocks the rest of the app already uses:

  - `apply_activity_scope`  -> row-level visibility per role (never widened)
  - `apply_common_filters`  -> the shared Date Range / Station / Activity
                                Type / Engineer (created_by) filter set

so Analytics can never show a role data it isn't otherwise allowed to see,
and a filter can only ever narrow what's already visible. Every number
below is computed live from the database - nothing is sample/hardcoded.
"""

from calendar import month_abbr
from datetime import date

from app.extensions import db
from app.models.activity import Activity, ActivityStatus, ActivityType
from app.models.shift import Shift
from app.models.station import Station
from app.models.user import Role, User

from app.utils.authz import apply_activity_scope
from app.utils.reports import apply_common_filters


# ---------------------------------------------------------------------------
# Filter dropdown choices
# ---------------------------------------------------------------------------

def get_analytics_filter_choices(user):
    """
    Dropdown option lists for the Analytics filter bar: Date Range (plain
    inputs, no choices needed), Station, Engineer, Activity Type.

    Option lists only - `apply_activity_scope` still enforces what the
    selected value is actually allowed to return.
    """
    return {
        "stations": Station.query.filter_by(is_active=True).order_by(Station.code).all(),
        "engineers": User.query.filter_by(is_active=True, role=Role.AIRCRAFT_ENGINEER)
        .order_by(User.full_name)
        .all(),
        "activity_types": ActivityType.CHOICES,
    }


# ---------------------------------------------------------------------------
# Chart data builders
# ---------------------------------------------------------------------------

def _scoped_filtered_query(user, args):
    return apply_common_filters(apply_activity_scope(Activity.query, user), args)


def _trend_data(base_query, granularity):
    """
    Activities Trend (line chart): count of activities per day, or bucketed
    per month when `granularity == 'month'`. Bucketing happens in Python
    over the (date, count) pairs the DB already grouped by day, so this
    stays portable across the Postgres/SQLite engines the app runs on,
    without relying on a DB-specific date-trunc function.
    """
    rows = (
        base_query.with_entities(Activity.activity_date, db.func.count(Activity.id))
        .group_by(Activity.activity_date)
        .order_by(Activity.activity_date)
        .all()
    )

    if not rows:
        return {"labels": [], "data": [], "granularity": granularity}

    if granularity == "month":
        buckets = {}
        for d, count in rows:
            key = (d.year, d.month)
            buckets[key] = buckets.get(key, 0) + count
        ordered_keys = sorted(buckets.keys())
        labels = [f"{month_abbr[m]} {y}" for y, m in ordered_keys]
        data = [buckets[k] for k in ordered_keys]
    else:
        labels = [d.isoformat() for d, _count in rows]
        data = [count for _d, count in rows]

    return {"labels": labels, "data": data, "granularity": granularity}


def _by_type_data(base_query):
    """Activities by Type (bar chart): count per activity type, live from DB."""
    rows = (
        base_query.with_entities(Activity.activity_type, db.func.count(Activity.id))
        .group_by(Activity.activity_type)
        .all()
    )
    counts = dict(rows)
    # Keep the app-wide type ordering; only include types with >0 activities
    # so an unfiltered chart isn't cluttered with a wall of zero-bars.
    labels, data, icons = [], [], []
    for code, label, icon in ActivityType.CHOICES:
        count = counts.get(code, 0)
        if count:
            labels.append(label)
            data.append(count)
            icons.append(icon)
    return {"labels": labels, "data": data, "icons": icons}


def _by_shift_data(base_query):
    """Activities by Shift (bar chart): count per shift, live from DB."""
    rows = (
        base_query.join(Shift, Shift.id == Activity.shift_id)
        .with_entities(Shift.name, db.func.count(Activity.id))
        .group_by(Shift.id, Shift.name)
        .order_by(Shift.name)
        .all()
    )
    return {"labels": [name for name, _c in rows], "data": [c for _n, c in rows]}


def _by_status_data(base_query):
    """
    Activity Status / Performance (donut chart): count per status. Reads
    whatever distinct status values actually exist in the DB (currently
    Open/Closed) rather than hardcoding the two, so a future added status
    shows up automatically with no code change here.
    """
    rows = (
        base_query.with_entities(Activity.status, db.func.count(Activity.id))
        .group_by(Activity.status)
        .all()
    )
    order = {code: i for i, code in enumerate(ActivityStatus.ALL)}
    rows = sorted(rows, key=lambda r: order.get(r[0], 99))
    labels = [status.title() for status, _c in rows]
    data = [c for _s, c in rows]
    return {"labels": labels, "data": data}


def build_analytics_payload(user, args):
    """
    Full JSON payload for the Analytics section: all 4 charts + summary
    totals, computed from one shared role-scoped + filtered base query so
    every chart on the page reflects exactly the same filter set.
    """
    base = _scoped_filtered_query(user, args)
    granularity = (args.get("granularity") or "day").strip().lower()
    if granularity not in ("day", "month"):
        granularity = "day"

    total = base.count()
    open_count = base.filter(Activity.status == ActivityStatus.OPEN).count()
    closed_count = base.filter(Activity.status == ActivityStatus.CLOSED).count()
    today_count = base.filter(Activity.activity_date == date.today()).count()

    return {
        "generated_at": date.today().isoformat(),
        "totals": {
            "total": total,
            "open": open_count,
            "closed": closed_count,
            "today": today_count,
        },
        "trend": _trend_data(base, granularity),
        "by_type": _by_type_data(base),
        "by_shift": _by_shift_data(base),
        "by_status": _by_status_data(base),
    }
