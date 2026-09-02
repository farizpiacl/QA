"""
Shared dashboard statistics helper.

Used by both the main blueprint (CE_QA / DCE_QA / AIRCRAFT_ENGINEER
dashboards) and the admin blueprint (SUPER_ADMIN dashboard) so every role's
numbers are computed the same way, scoped through
`app.utils.authz.apply_activity_scope`, and always read live from the
database - never hardcoded or estimated.
"""

from datetime import date

from app.models.activity import Activity, ActivityStatus, ActivityType
from app.utils.authz import apply_activity_scope


def get_dashboard_stats(user, include_open_pool=True, filters=None):
    """
    Returns:
        {
          "totals": {"total": int, "open": int, "closed": int,
                     "today": int, "this_month": int},
          "by_type": [(code, label, icon, count), ...],
        }
    All counts are scoped to what `user` is allowed to see.

    `include_open_pool` is forwarded to `apply_activity_scope` unchanged
    (it only ever affects AIRCRAFT_ENGINEER - see that function's
    docstring). It defaults to True so every existing caller (Analytics,
    the Super Admin dashboard, and the CE_QA/DCE_QA dashboards) keeps
    seeing exactly what it always has. The Engineer's own Dashboard is the
    only caller that passes False, so its personal KPI totals reflect only
    the engineer's own activities - the shared OPEN pool now lives on its
    own "Open Activities in Station" page instead.

    `filters` is an optional `request.args`-like mapping (date_from,
    date_to, station_id, shift_id, created_by, status, type, q, ...)
    layered on top of the role scope via the same `apply_common_filters`
    helper used by the Activities list and Reports pages, so a dashboard
    filter bar and the list page it links into always agree on what a
    given filter means. Every existing caller that doesn't pass `filters`
    is unaffected - the totals/by_type counts are simply the full
    role-scoped set, as before.
    """
    from app.utils.reports import apply_common_filters

    base = apply_activity_scope(Activity.query, user, include_open_pool=include_open_pool)
    if filters:
        base = apply_common_filters(base, filters)

    today = date.today()
    month_start = today.replace(day=1)

    totals = {
        "total": base.count(),
        "open": base.filter(Activity.status == ActivityStatus.OPEN).count(),
        "closed": base.filter(Activity.status == ActivityStatus.CLOSED).count(),
        "today": base.filter(Activity.activity_date == today).count(),
        "this_month": base.filter(Activity.activity_date >= month_start).count(),
    }

    by_type = [
        (code, label, icon, base.filter(Activity.activity_type == code).count())
        for code, label, icon in ActivityType.CHOICES
    ]

    return {"totals": totals, "by_type": by_type}
